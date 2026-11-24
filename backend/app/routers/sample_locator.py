"""异常样本定位清单接口：按来源与未齐类型定位分片、补录统计、提交抽验。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.services.sample_locator import (
    UNFINISHED_RAW,
    UNFINISHED_VALID,
    sample_locator,
)

router = APIRouter(prefix="/api/sample_locator", tags=["异常样本定位"])


class SupplementPayload(BaseModel):
    采集来源: str | None = None
    source: str | None = None
    批次标识: str | None = None
    batch_label: str | None = None
    分片: int | None = None
    期望行数: int | None = None
    原始行数: int | None = None
    有效行数: int | None = None
    统计版本: str | None = None


class SpotcheckPayload(BaseModel):
    采集来源: str | None = None
    source: str | None = None
    批次标识: str | None = None
    batch_label: str | None = None
    快照: list[dict[str, Any]] = Field(default_factory=list)
    snapshot: list[dict[str, Any]] = Field(default_factory=list)
    保留历史对照: bool = False
    keep_history: bool = False


@router.get("/options")
def sample_options() -> dict[str, Any]:
    """筛选下拉：可用采集来源和未齐类型。"""
    from app.store import store

    sources: list[str] = []
    for row in store.rows("result_store"):
        if not row.get("分片统计"):
            continue
        source = str(row.get("来源配置") or "").strip()
        if source and source not in sources:
            sources.append(source)
    return {
        "采集来源": sources,
        "未齐类型": [UNFINISHED_RAW, UNFINISHED_VALID],
    }


@router.get("/records")
def spotcheck_records() -> dict[str, Any]:
    """已提交的统计抽验记录，按提交时间倒序。"""
    items, total = sample_locator.list_records()
    return {"items": items, "total": total}


@router.get("")
def list_samples(
    采集来源: str | None = Query(default=None),
    未齐类型: str | None = Query(default=None),
    批次标识: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
) -> dict[str, Any]:
    """异常样本定位清单：每条分片一行，带筛选差额和冻结快照。"""
    items, total, snapshot = sample_locator.list_samples(
        source=采集来源,
        unfinished_type=未齐类型,
        batch_label=批次标识,
        keyword=keyword,
        page=page,
        size=size,
    )
    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "快照": snapshot,
        "筛选": {
            "采集来源": 采集来源 or "",
            "未齐类型": 未齐类型 or "",
            "批次标识": 批次标识 or "",
            "keyword": keyword or "",
        },
    }


@router.get("/batch")
def batch_stats(采集来源: str | None = Query(default=None),
                批次标识: str | None = Query(default=None)) -> dict[str, Any]:
    """按来源读取实际落库批次的原始行数、有效行数和存储路径。"""
    from app.services.result_store import ResultStoreService
    from app.services.sample_locator import _as_int, _shards

    if not 采集来源 or not 批次标识:
        return {"ok": False, "message": "同标签批次须按采集来源单独定位，请指定采集来源和批次标识", "entry": None}
    stats = ResultStoreService().domain_read_stats(批次标识, 采集来源)
    if stats is None:
        return {"ok": False, "message": f"未找到来源「{采集来源}」批次「{批次标识}」的实际落库记录", "entry": None}
    shards = _shards(stats)
    return {
        "ok": True,
        "message": "已读取实际落库批次统计",
        "entry": {
            **stats,
            "分片数": len(shards),
            "分片差额": sum(max(_as_int(item.get("期望行数")) - _as_int(item.get("有效行数")), 0) for item in shards),
        },
    }


@router.post("/supplement")
def supplement_statistics(payload: SupplementPayload) -> dict[str, Any]:
    """补录迟到统计；只更新分片统计与批次合计，不动已有抽验记录。"""
    item, message = sample_locator.supplement_statistics(payload.model_dump())
    return {"ok": item is not None, "message": message, "entry": item}


@router.post("/spotcheck")
def submit_spotcheck(payload: SpotcheckPayload) -> dict[str, Any]:
    """按筛选快照提交统计抽验。"""
    record, message = sample_locator.submit_spotcheck(payload.model_dump())
    return {"ok": record is not None, "message": message, "entry": record}
