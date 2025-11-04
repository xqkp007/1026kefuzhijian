from types import SimpleNamespace

import pytest

from app.db.models.evaluation_task import RunStatus
from app.services.correction_service import CorrectionOutcome
from app.services.evaluation_runner import _run_corrections_for_item


class DummyDB:
    def add(self, obj):  # noqa: D401 - simple stub
        return None


class DummyCorrectionService:
    def __init__(self, outcomes):
        self.outcomes = outcomes
        self.calls = []

    def evaluate(self, **kwargs):
        self.calls.append(kwargs)
        return self.outcomes.pop(0)


@pytest.fixture(autouse=True)
def patch_repo(monkeypatch):
    recorded = {"runs": [], "item": []}

    def fake_update_run_correction(db, run, **kwargs):
        kwargs["run_index"] = run.run_index
        recorded["runs"].append(kwargs)

    def fake_update_item_pass_status(db, item, is_passed):
        item.is_passed = is_passed
        recorded["item"].append(is_passed)

    monkeypatch.setattr("app.services.evaluation_runner.repo.update_run_correction", fake_update_run_correction)
    monkeypatch.setattr("app.services.evaluation_runner.repo.update_item_pass_status", fake_update_item_pass_status)

    yield recorded


def test_run_corrections_all_success(patch_repo):
    task = SimpleNamespace(id="task-1")
    item = SimpleNamespace(
        question="Q?",
        standard_answer="A",
        question_id="Q1",
        runs=[
            SimpleNamespace(run_index=1, status=RunStatus.SUCCEEDED, response_body="answer", error_message=None),
            SimpleNamespace(run_index=2, status=RunStatus.SUCCEEDED, response_body="answer", error_message=None),
        ],
    )

    service = DummyCorrectionService(
        outcomes=[
            CorrectionOutcome(status="SUCCESS", is_correct=True, reason="ok", error_message=None, retries=0),
            CorrectionOutcome(status="SUCCESS", is_correct=True, reason="ok", error_message=None, retries=0),
        ]
    )

    _run_corrections_for_item(DummyDB(), task=task, item=item, correction_service=service)

    assert item.is_passed is True
    assert len(service.calls) == 2
    assert all(entry["result"] for entry in patch_repo["runs"][:2])


def test_run_corrections_service_unavailable(patch_repo):
    task = SimpleNamespace(id="task-2")
    item = SimpleNamespace(
        question="Q?",
        standard_answer="A",
        question_id="Q2",
        runs=[SimpleNamespace(run_index=1, status=RunStatus.SUCCEEDED, response_body="answer", error_message=None)],
    )

    _run_corrections_for_item(DummyDB(), task=task, item=item, correction_service=None)

    assert item.is_passed is False
    assert patch_repo["runs"][0]["status"] == "SKIPPED"
