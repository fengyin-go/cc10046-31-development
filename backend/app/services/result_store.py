"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class ResultStoreService(BaseModuleService):
    MODULE = "result_store"
    ENTITY = "存储批次"
    OPERATION_TERM = "采集"
    LIST_FIELDS = ["批次标识", "来源配置", "采集时间", "原始行数", "有效行数", "存储路径", "压缩格式", "校验摘要"]
    REQUIRED_FIELDS = ["批次标识", "来源配置", "采集时间"]
    STATUS_ORDER = ["存储中", "已落库", "校验未过", "已归档"]
    ACTION_RULES = {"执行校验": "已落库", "发起归档": "已落库"}
    NEGATIVE_ACTIONS = []

    def domain_store_result(self, batch_id: str, source_config: str,
                            row_count: int, valid_count: int) -> dict:
        """结构化存储采集结果。"""
        from app.store import store
        import time
        rows = store.rows(self.MODULE)
        store_path = f"/data/results/{batch_id}.json.gz"
        entry = {
            "id": max((int(r.get("id", 0)) for r in rows), default=0) + 1,
            "批次标识": batch_id,
            "来源配置": source_config,
            "采集时间": time.strftime("%Y-%m-%d"),
            "原始行数": str(row_count),
            "有效行数": str(valid_count),
            "存储路径": store_path,
            "压缩格式": "gzip",
            "校验摘要": f"md5:{batch_id[:8]}",
            "status": "已落库",
            "pending": False,
            "abnormal": False,
        }
        rows.append(entry)
        return entry

    def domain_find_batches(self, batch_label: str) -> list[dict]:
        """按批次标签取实际落库记录；同标签可能对应多个来源批次。"""
        from app.store import store
        token = str(batch_label or "").strip()
        if not token:
            return []
        return [
            row for row in store.rows(self.MODULE)
            if str(row.get("批次标识", "")).strip() == token
        ]

    def domain_read_stats(self, batch_label: str, source: str) -> dict | None:
        """按来源读取实际落库批次的原始行数、有效行数和存储路径。"""
        for row in self.domain_find_batches(batch_label):
            if str(row.get("来源配置", "")).strip() == str(source or "").strip():
                return {
                    "批次记录": row.get("id"),
                    "批次标识": row.get("批次标识"),
                    "采集来源": row.get("来源配置"),
                    "原始行数": row.get("原始行数"),
                    "有效行数": row.get("有效行数"),
                    "存储路径": row.get("存储路径"),
                    "分片统计": [dict(item) for item in (row.get("分片统计") or [])],
                }
        return None
