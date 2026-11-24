"""异常样本定位清单领域服务。

批次追踪只记录整批总数，没有按批次差额定位到具体分片的入口。本服务把
结果存储里实际落库批次的“分片统计”展开成清单：

* 清单按 **采集来源 + 批次标识 + 分片** 唯一定位，同标签的不同来源批次互不覆盖；
* 可按 ``采集来源`` 和 ``未齐类型`` 筛选，并给出每个分片的差额和统计版本；
* 筛选结果附带冻结快照，提交抽验时按快照里的筛选差额与实际读到的统计版本
  分别留档，方便按批次复核；
* 补录迟到统计只改分片统计并回写批次合计，不影响提交时冻结的筛选快照。
"""
from __future__ import annotations

import time
from typing import Any

from app.services.result_store import ResultStoreService
from app.store import store

RESULT_MODULE = "result_store"
UNFINISHED_RAW = "原始行缺失"
UNFINISHED_VALID = "有效行不足"


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _shards(row: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in (row.get("分片统计") or []) if isinstance(item, dict)]


def _shard_gap(shard: dict[str, Any]) -> dict[str, int]:
    expected = _as_int(shard.get("期望行数"))
    raw = _as_int(shard.get("原始行数"))
    valid = _as_int(shard.get("有效行数"))
    return {"原始差额": max(expected - raw, 0), "有效差额": max(expected - valid, 0)}


def _diff(shard: dict[str, Any]) -> int:
    """单个分片的差额：原始行与有效行谁短得更多就按谁计，不重复累加。"""
    gap = _shard_gap(shard)
    return max(gap["原始差额"], gap["有效差额"])


def _unfinished_types(gap: dict[str, int]) -> list[str]:
    kinds: list[str] = []
    if gap["原始差额"] > 0:
        kinds.append(UNFINISHED_RAW)
    if gap["有效差额"] > 0:
        kinds.append(UNFINISHED_VALID)
    return kinds


def _next_version(current: Any) -> str:
    text = str(current or "").strip()
    if text.startswith("v") and text[1:].isdigit():
        return f"v{int(text[1:]) + 1}"
    return "v1"


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


class SampleLocatorService:
    """异常样本定位清单：批次差额 -> 分片定位 -> 统计抽验。"""

    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []
        self._seq = 0
        self._result_store = ResultStoreService()

    # ------------------------------------------------------------------ 定位
    def _resolve_batch(self, source: str, batch_label: str) -> dict[str, Any] | None:
        """按“采集来源 + 批次标识”取唯一落库批次，同标签不同来源必须分开。"""
        matches = [
            row for row in self._result_store.domain_find_batches(batch_label)
            if str(row.get("来源配置", "")).strip() == source
        ]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            token = source.casefold()
            loose = [
                row for row in self._result_store.domain_find_batches(batch_label)
                if token and token in str(row.get("来源配置", "")).casefold()
            ]
            if len(loose) == 1:
                return loose[0]
        return None

    def _resolve_error(self, source: str, batch_label: str) -> str:
        same_label = self._result_store.domain_find_batches(batch_label)
        if same_label:
            others = "、".join(str(row.get("来源配置", "")) for row in same_label)
            return (
                f"批次标签「{batch_label}」在采集来源 {others} 下都有落库批次，"
                f"请按采集来源单独定位，未找到来源「{source}」的批次"
            )
        return f"未找到批次标签「{batch_label}」的实际落库记录"

    def _build_item(self, row: dict[str, Any], shard: dict[str, Any]) -> dict[str, Any]:
        gap = _shard_gap(shard)
        kinds = _unfinished_types(gap)
        return {
            "id": f"{row.get('id')}-{shard.get('分片')}",
            "清单编号": f"SL-{row.get('id')}-{shard.get('分片')}",
            "批次记录": row.get("id"),
            "批次标识": row.get("批次标识"),
            "采集来源": row.get("来源配置"),
            "批次状态": row.get("status"),
            "存储路径": row.get("存储路径"),
            "分片": shard.get("分片"),
            "分片范围": shard.get("分片范围"),
            "期望行数": _as_int(shard.get("期望行数")),
            "原始行数": _as_int(shard.get("原始行数")),
            "有效行数": _as_int(shard.get("有效行数")),
            "原始差额": gap["原始差额"],
            "有效差额": gap["有效差额"],
            "差额": _diff(shard),
            "未齐类型": kinds,
            "未齐类型文本": "、".join(kinds),
            "统计版本": str(shard.get("统计版本") or "v1"),
            "统计时间": shard.get("统计时间"),
            "批次原始行数": _as_int(row.get("原始行数")),
            "批次有效行数": _as_int(row.get("有效行数")),
        }

    def list_samples(
        self,
        *,
        source: str | None = None,
        unfinished_type: str | None = None,
        batch_label: str | None = None,
        keyword: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int, list[dict[str, Any]]]:
        """返回 (当前页清单, 过滤后总数, 覆盖全部过滤结果的筛选快照)。"""
        matched: list[dict[str, Any]] = []
        for row in store.rows(RESULT_MODULE):
            for shard in _shards(row):
                item = self._build_item(row, shard)
                if item["差额"] <= 0:
                    continue
                if source and source.casefold() not in str(item["采集来源"]).casefold():
                    continue
                if unfinished_type and unfinished_type not in item["未齐类型"]:
                    continue
                if batch_label and batch_label.casefold() not in str(item["批次标识"]).casefold():
                    continue
                if keyword:
                    haystack = " ".join(
                        str(item.get(field) or "")
                        for field in ("批次标识", "采集来源", "存储路径", "分片范围")
                    ).casefold()
                    if keyword.casefold() not in haystack:
                        continue
                matched.append(item)

        matched.sort(key=lambda item: (str(item["采集来源"]), int(item["批次记录"]), int(item["分片"])))
        total = len(matched)
        snapshot = [
            {
                "清单编号": item["id"],
                "采集来源": item["采集来源"],
                "批次标识": item["批次标识"],
                "分片": item["分片"],
                "分片范围": item["分片范围"],
                "差额": item["差额"],
                "原始差额": item["原始差额"],
                "有效差额": item["有效差额"],
                "统计版本": item["统计版本"],
                "存储路径": item["存储路径"],
            }
            for item in matched
        ]
        start = (page - 1) * size
        return matched[start:start + size], total, snapshot

    # -------------------------------------------------------------- 迟到统计
    def supplement_statistics(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        """补录某个分片迟到的行数统计，统计版本自动递增。"""
        source = str(payload.get("采集来源") or payload.get("source") or "").strip()
        batch_label = str(payload.get("批次标识") or payload.get("batch_label") or "").strip()
        if not source:
            return None, "同标签批次须按采集来源单独定位，请指定采集来源"
        if not batch_label:
            return None, "缺少批次标识"
        if payload.get("分片") is None:
            return None, "缺少分片"

        row = self._resolve_batch(source, batch_label)
        if row is None:
            return None, self._resolve_error(source, batch_label)
        shard_no = _as_int(payload.get("分片"), -1)
        shard = next((item for item in _shards(row) if _as_int(item.get("分片"), -1) == shard_no), None)
        if shard is None:
            return None, f"批次「{batch_label}」没有第 {shard_no} 片的分片统计"

        provided = False
        changed = False
        for field in ("期望行数", "原始行数", "有效行数"):
            if payload.get(field) is None:
                continue
            provided = True
            value = _as_int(payload.get(field))
            if _as_int(shard.get(field)) != value:
                shard[field] = value
                changed = True
        if not provided:
            return None, "补录统计至少需要提供原始行数或有效行数"
        if not changed:
            return self._build_item(row, shard), "统计与当前记录一致，版本未变更"

        explicit_version = str(payload.get("统计版本") or "").strip()
        shard["统计版本"] = explicit_version or _next_version(shard.get("统计版本"))
        shard["统计时间"] = _now()
        self._recalc_batch(row)
        return self._build_item(row, shard), "分片统计已补录"

    def _recalc_batch(self, row: dict[str, Any]) -> None:
        shards = _shards(row)
        row["原始行数"] = str(sum(_as_int(item.get("原始行数")) for item in shards))
        row["有效行数"] = str(sum(_as_int(item.get("有效行数")) for item in shards))

    # ---------------------------------------------------------------- 抽验
    def _freeze(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        raw = payload.get("快照") or payload.get("snapshot") or []
        if not isinstance(raw, list):
            return []
        return [entry for entry in raw if isinstance(entry, dict)]

    def submit_spotcheck(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        """按筛选快照提交统计抽验，只对实际仍有差额的分片取数。"""
        source = str(payload.get("采集来源") or payload.get("source") or "").strip()
        batch_label = str(payload.get("批次标识") or payload.get("batch_label") or "").strip()
        if not source:
            return None, "同标签批次须按采集来源单独定位，请指定采集来源"
        if not batch_label:
            return None, "缺少批次标识"

        row = self._resolve_batch(source, batch_label)
        if row is None:
            return None, self._resolve_error(source, batch_label)

        keep_history = bool(payload.get("保留历史对照") or payload.get("keep_history"))
        frozen = [
            entry for entry in self._freeze(payload)
            if str(entry.get("采集来源", "")).strip() == source
            and str(entry.get("批次标识", "")).strip() == batch_label
        ]
        if not frozen:
            frozen = [
                {
                    "采集来源": row.get("来源配置"),
                    "批次标识": row.get("批次标识"),
                    "分片": shard.get("分片"),
                    "分片范围": shard.get("分片范围"),
                    "差额": _diff(shard),
                    "统计版本": str(shard.get("统计版本") or "v1"),
                    "存储路径": row.get("存储路径"),
                }
                for shard in _shards(row) if _diff(shard) > 0
            ]
        if not frozen:
            return None, "筛选范围内没有可抽验的分片差额"

        by_shard: dict[int, dict[str, Any]] = {}
        for entry in frozen:
            by_shard[_as_int(entry.get("分片"), -1)] = entry
        by_shard.pop(-1, None)
        if not by_shard:
            return None, "筛选快照没有有效的分片"

        details: list[dict[str, Any]] = []
        adopted: list[dict[str, Any]] = []
        controls: list[dict[str, Any]] = []
        for shard_no in sorted(by_shard):
            entry = by_shard[shard_no]
            shard = next(
                (item for item in _shards(row) if _as_int(item.get("分片"), -1) == shard_no), None)
            if shard is None:
                continue
            current_gap = _shard_gap(shard)
            current_diff = _diff(shard)
            frozen_diff = _as_int(entry.get("差额"))
            detail = {
                "分片": shard_no,
                "分片范围": shard.get("分片范围"),
                "筛选时差额": frozen_diff,
                "筛选时统计版本": str(entry.get("统计版本") or ""),
                "实际差额": current_diff,
                "实际统计版本": str(shard.get("统计版本") or "v1"),
                "实际原始行数": _as_int(shard.get("原始行数")),
                "实际有效行数": _as_int(shard.get("有效行数")),
                "期望行数": _as_int(shard.get("期望行数")),
                "原始差额": current_gap["原始差额"],
                "有效差额": current_gap["有效差额"],
                "是否采用": current_diff > 0,
            }
            if current_diff > 0:
                detail["说明"] = "提交时仍有差额，纳入抽验范围"
                detail["采用"] = True
                adopted.append({**detail, "存储分片": shard})
            elif keep_history:
                detail["说明"] = "筛选时有差额、提交前已补齐，保留为历史对照"
                detail["采用"] = False
                controls.append(detail)
            else:
                detail["说明"] = "筛选时有差额、提交前已补齐，未纳入抽验"
                detail["采用"] = False
                # 不保留历史对照时不进入分片明细，但仍留在筛选快照中。
                continue
            details.append(detail)

        if not adopted:
            return None, "筛选范围内当前已没有仍存在差额的分片，无需提交抽验"

        adopted_shards = [entry["存储分片"] for entry in adopted]
        raw_total = sum(_as_int(shard.get("原始行数")) for shard in adopted_shards)
        valid_total = sum(_as_int(shard.get("有效行数")) for shard in adopted_shards)
        expected_total = sum(_as_int(shard.get("期望行数")) for shard in adopted_shards)
        ranges = [str(shard.get("分片范围")) for shard in adopted_shards]
        version_map = {str(entry["分片"]): entry["实际统计版本"] for entry in adopted}

        self._seq += 1
        record = {
            "id": f"SC-{self._seq:04d}",
            "抽验编号": f"SC-{self._seq:04d}",
            "提交时间": _now(),
            "采集来源": row.get("来源配置"),
            "批次标识": row.get("批次标识"),
            "存储路径": row.get("存储路径"),
            "采用范围": ranges,
            "对照范围": [str(entry.get("分片范围")) for entry in controls],
            "采用分片": [entry["分片"] for entry in adopted],
            "触发前范围": [
                {
                    "分片": _as_int(entry.get("分片")),
                    "分片范围": entry.get("分片范围"),
                    "差额": _as_int(entry.get("差额")),
                    "统计版本": entry.get("统计版本"),
                }
                for entry in frozen
            ],
            "触发后范围": [
                {
                    "分片": entry["分片"],
                    "分片范围": entry["分片范围"],
                    "差额": entry["实际差额"],
                    "统计版本": entry["实际统计版本"],
                }
                for entry in adopted
            ],
            "筛选时差额": sum(_as_int(entry.get("差额")) for entry in frozen),
            "实际差额": sum(entry["实际差额"] for entry in adopted),
            "筛选时统计版本": {
                str(entry.get("分片")): str(entry.get("统计版本") or "")
                for entry in frozen
            },
            "实际统计版本": version_map,
            "返回行数": {
                "记录数": len(adopted),
                "分片数": len(adopted_shards),
                "原始行数": raw_total,
                "有效行数": valid_total,
                "期望行数": expected_total,
            },
            "结果存储": {
                "采集来源": row.get("来源配置"),
                "批次标识": row.get("批次标识"),
                "存储路径": row.get("存储路径"),
                "原始行数": raw_total,
                "有效行数": valid_total,
                "期望行数": expected_total,
                "分片范围": "、".join(ranges),
                "统计版本": "、".join(f"第{key}片:{value}" for key, value in version_map.items()),
            },
            "分片明细": details,
            "保留历史对照": keep_history,
            "筛选快照": frozen,
        }
        self.records.append(record)
        message = (
            f"抽验 {record['抽验编号']} 已提交：{record['采集来源']} / {record['批次标识']} "
            f"采用 {len(adopted_shards)} 个分片、有效行 {valid_total} 行"
        )
        return record, message

    def list_records(self) -> tuple[list[dict[str, Any]], int]:
        return list(reversed(self.records)), len(self.records)


sample_locator = SampleLocatorService()
