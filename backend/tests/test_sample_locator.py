"""异常样本定位清单：来源隔离、分页快照、迟到统计和抽验范围测试。"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import copy

import pytest

from app.services.result_store import ResultStoreService
from app.services.sample_locator import (
    SampleLocatorService,
    UNFINISHED_RAW,
    UNFINISHED_VALID,
)
from app.store import store

LABEL = "BATCH-20261124-A"


@pytest.fixture()
def locator():
    """每个用例独立服务实例，并还原两个来源批次的分片统计。"""
    rows = {row["id"]: row for row in store.rows("result_store")}
    backup = {entry_id: copy.deepcopy(rows[entry_id]) for entry_id in (4, 5)}
    service = SampleLocatorService()
    yield service
    for entry_id, row in backup.items():
        row.clear()
        row.update(copy.deepcopy(backup[entry_id]))


def test_same_label_split_by_source(locator):
    jia, jia_total, jia_snapshot = locator.list_samples(source="来源甲")
    yi, yi_total, yi_snapshot = locator.list_samples(source="来源乙")

    assert jia_total == 2
    assert yi_total == 2
    assert {item["采集来源"] for item in jia} == {"来源甲"}
    assert {item["采集来源"] for item in yi} == {"来源乙"}
    assert {entry["清单编号"] for entry in jia_snapshot} == {"4-2", "4-3"}
    assert {entry["清单编号"] for entry in yi_snapshot} == {"5-1", "5-2"}

    stats = ResultStoreService().domain_read_stats(LABEL, "来源甲")
    assert stats["存储路径"].endswith("/jia/BATCH-20261124-A.json.gz")
    assert stats["原始行数"] == "2000"


def test_filter_by_unfinished_type(locator):
    items, total, _ = locator.list_samples(source="来源甲", unfinished_type=UNFINISHED_VALID)
    assert total == 2
    assert all(UNFINISHED_VALID in item["未齐类型"] for item in items)

    items, total, _ = locator.list_samples(source="来源乙", unfinished_type=UNFINISHED_RAW)
    assert total == 1
    assert items[0]["分片"] == 1
    assert items[0]["原始差额"] == 40


def test_pagination_snapshot_keeps_both_shards(locator):
    page1, total, snapshot = locator.list_samples(source="来源甲", page=1, size=1)
    page2, _, snapshot2 = locator.list_samples(source="来源甲", page=2, size=1)

    assert total == 2
    assert len(page1) == 1 and len(page2) == 1
    assert page1[0]["分片"] == 2 and page2[0]["分片"] == 3
    # 快照覆盖全部筛选结果，而不是当前页
    assert len(snapshot) == len(snapshot2) == 2
    assert {entry["分片"] for entry in snapshot} == {2, 3}


def test_duplicate_label_requires_source(locator):
    item, message = locator.supplement_statistics(
        {"批次标识": LABEL, "分片": 2, "有效行数": 500})
    assert item is None
    assert "采集来源" in message

    record, message = locator.submit_spotcheck({"批次标识": LABEL})
    assert record is None
    assert "采集来源" in message

    item, message = locator.supplement_statistics(
        {"采集来源": "来源丙", "批次标识": LABEL, "分片": 2, "有效行数": 500})
    assert item is None
    assert "来源甲" in message and "来源乙" in message


def test_late_stat_supplement_keeps_snapshot(locator):
    _, _, snapshot = locator.list_samples(source="来源甲", unfinished_type=UNFINISHED_VALID)
    frozen = {entry["分片"]: entry for entry in snapshot}
    assert frozen[2]["差额"] == 120
    assert frozen[2]["统计版本"] == "v1"

    item, _ = locator.supplement_statistics(
        {"采集来源": "来源甲", "批次标识": LABEL, "分片": 2, "有效行数": 500})
    assert item["有效行数"] == 500
    assert item["差额"] == 0
    assert item["统计版本"] == "v2"

    record, message = locator.submit_spotcheck({
        "采集来源": "来源甲",
        "批次标识": LABEL,
        "快照": snapshot,
        "保留历史对照": True,
    })
    assert record is not None
    assert record["采用分片"] == [3]
    # 筛选时差额与统计版本来自冻结快照
    assert record["筛选时差额"] == 200
    assert record["筛选时统计版本"] == {"2": "v1", "3": "v1"}
    # 实际读到的统计版本来自提交时的落库批次
    assert record["实际统计版本"] == {"3": "v1"}
    # 第 2 片作为历史对照保留
    assert record["对照范围"] == ["501-1000"]
    # 结果存储只反映实际采用的范围
    assert record["结果存储"]["采集来源"] == "来源甲"
    assert record["结果存储"]["原始行数"] == 500
    assert record["结果存储"]["有效行数"] == 420
    assert record["结果存储"]["分片范围"] == "1001-1500"
    assert record["返回行数"]["分片数"] == 1
    assert "第2片:v2" not in record["结果存储"]["统计版本"]


def test_late_stat_without_history(locator):
    _, _, snapshot = locator.list_samples(source="来源甲", unfinished_type=UNFINISHED_VALID)
    locator.supplement_statistics(
        {"采集来源": "来源甲", "批次标识": LABEL, "分片": 2, "有效行数": 500})
    record, _ = locator.submit_spotcheck({
        "采集来源": "来源甲",
        "批次标识": LABEL,
        "快照": snapshot,
    })
    assert record["采用分片"] == [3]
    assert record["对照范围"] == []
    assert all(detail["分片"] != 2 for detail in record["分片明细"])


def test_spotcheck_reads_late_stat_version_before_submit(locator):
    """第 2 片统计迟到但已在提交前写入，重新筛选后只剩第 3 片有差额。"""
    locator.supplement_statistics(
        {"采集来源": "来源甲", "批次标识": LABEL, "分片": 2, "有效行数": 500})
    _, total, snapshot = locator.list_samples(source="来源甲", unfinished_type=UNFINISHED_VALID)
    assert total == 1
    assert [entry["分片"] for entry in snapshot] == [3]
    record, _ = locator.submit_spotcheck({
        "采集来源": "来源甲",
        "批次标识": LABEL,
        "快照": snapshot,
    })
    assert record["采用分片"] == [3]
    assert record["触发前范围"] == [
        {"分片": 3, "分片范围": "1001-1500", "差额": 80, "统计版本": "v1"}
    ]


def test_supplement_batch_totals_recalc(locator):
    locator.supplement_statistics(
        {"采集来源": "来源甲", "批次标识": LABEL, "分片": 2, "有效行数": 500})
    stats = ResultStoreService().domain_read_stats(LABEL, "来源甲")
    assert stats["有效行数"] == "1920"  # 1800 + 120
    assert stats["原始行数"] == "2000"
