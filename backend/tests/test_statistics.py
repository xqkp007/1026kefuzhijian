from types import SimpleNamespace

from app.services.statistics import CorrectionAggregator


def make_run(status: str, correction_status: str | None = None, correction_result=None):
    return SimpleNamespace(
        status=status,
        correction_status=correction_status,
        correction_result=correction_result,
        correction_reason=None,
        correction_error_message=None,
    )


def test_correction_aggregator_counts():
    aggregator = CorrectionAggregator()

    pass_item = SimpleNamespace(
        question_id="Q1",
        is_passed=True,
        runs=[make_run("SUCCEEDED", "SUCCESS", True) for _ in range(5)],
    )
    partial_item = SimpleNamespace(
        question_id="Q2",
        is_passed=False,
        runs=[make_run("SUCCEEDED", "SUCCESS", False) for _ in range(5)],
    )
    failed_item = SimpleNamespace(
        question_id="Q3",
        is_passed=False,
        runs=[make_run("FAILED", "FAILED", None) for _ in range(5)],
    )

    for item in [pass_item, partial_item, failed_item]:
        aggregator.observe_item(item)

    stats = aggregator.to_stats()

    assert stats.total_items == 3
    assert stats.passed == 1
    assert stats.partial_error_count == 1
    assert stats.correction_failed_count == 1
    assert aggregator.item_failure_types["Q1"] == "PASS"
    assert aggregator.item_failure_types["Q2"] == "PARTIAL_ERROR"
    assert aggregator.item_failure_types["Q3"] == "CORRECTION_FAILED"
