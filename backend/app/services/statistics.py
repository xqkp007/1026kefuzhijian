from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from app.db.models.evaluation_task import EvaluationItem


@dataclass
class CorrectionStats:
    total_items: int
    passed: int
    partial_error_count: int
    correction_failed_count: int

    @property
    def failed_total(self) -> int:
        return self.total_items - self.passed

    @property
    def accuracy_rate(self) -> float:
        return (self.passed / self.total_items * 100) if self.total_items else 0.0


class CorrectionAggregator:
    """Aggregate correction results for a task and classify per-item failure type."""

    def __init__(self) -> None:
        self.total_items = 0
        self.passed = 0
        self.partial_error_count = 0
        self.correction_failed_count = 0
        self.item_failure_types: Dict[str, str] = {}

    def observe_item(self, item: EvaluationItem) -> None:
        self.total_items += 1
        if item.is_passed is True:
            self.passed += 1
            self.item_failure_types[item.question_id] = "PASS"
            return

        has_incorrect = False
        correction_failed = False

        for run in item.runs:
            if run.status != "SUCCEEDED":
                correction_failed = True
                continue

            status = getattr(run, "correction_status", None)
            if status == "SUCCESS":
                if getattr(run, "correction_result", None) is False:
                    has_incorrect = True
            elif status in {"FAILED", "SKIPPED"}:
                correction_failed = True

        if correction_failed:
            self.correction_failed_count += 1
            self.item_failure_types[item.question_id] = "CORRECTION_FAILED"
        elif has_incorrect:
            # 矫正成功但存在判错
            self.partial_error_count += 1
            self.item_failure_types[item.question_id] = "PARTIAL_ERROR"
        else:
            # 未能归类，视作矫正失败场景
            self.correction_failed_count += 1
            self.item_failure_types[item.question_id] = "UNDETERMINED"

    def to_stats(self) -> CorrectionStats:
        return CorrectionStats(
            total_items=self.total_items,
            passed=self.passed,
            partial_error_count=self.partial_error_count,
            correction_failed_count=self.correction_failed_count,
        )
