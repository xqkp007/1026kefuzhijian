from types import SimpleNamespace

import pytest

from app.db.models.evaluation_task import RunStatus
from app.services.correction_service import CorrectionOutcome
from app.services.evaluation_runner import (
    _build_group_session_id,
    _process_multi_turn_group,
    _run_corrections_for_item,
)


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


class DummySession:
    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1


def _make_run(run_index: int, status=RunStatus.RETRYING):
    return SimpleNamespace(
        run_index=run_index,
        status=status,
        response_body=None,
        error_code=None,
        error_message=None,
        latency_ms=None,
    )


def test_process_multi_turn_group_executes_sessions(monkeypatch):
    task = SimpleNamespace(
        id="task-xyz",
        runs_per_item=2,
        enable_correction=False,
        progress_processed=0,
        total_items=2,
    )
    item1 = SimpleNamespace(
        id="item-1",
        question_id="Q1",
        question="你好",
        standard_answer="hi",
        session_group="grpA",
        runs=[_make_run(1), _make_run(2)],
    )
    item2 = SimpleNamespace(
        id="item-2",
        question_id="Q2",
        question="请继续",
        standard_answer="continue",
        session_group="grpA",
        runs=[_make_run(1), _make_run(2)],
    )
    db = DummySession()

    executed_calls = []

    def fake_execute(client, task_arg, item_arg, run_arg, *, session_id):
        executed_calls.append(
            {
                "item": item_arg.question_id,
                "run_index": run_arg.run_index,
                "session_id": session_id,
            }
        )
        return "resp", None, None, 42

    updated_runs = []

    def fake_update_run_result(db_arg, run_arg, **kwargs):
        run_arg.status = kwargs["status"]
        run_arg.response_body = kwargs["response_body"]
        updated_runs.append((run_arg.run_index, kwargs["status"]))

    progress_updates = []

    def fake_increment_task_progress(db_arg, task_arg, increment=1):
        task_arg.progress_processed = min(task_arg.progress_processed + increment, task_arg.total_items)
        progress_updates.append((task_arg.id, increment))

    monkeypatch.setattr("app.services.evaluation_runner._execute_single_run", fake_execute)
    monkeypatch.setattr(
        "app.services.evaluation_runner.repo.update_run_result",
        fake_update_run_result,
    )
    monkeypatch.setattr(
        "app.services.evaluation_runner.repo.increment_task_progress",
        fake_increment_task_progress,
    )

    _process_multi_turn_group(
        db,
        task=task,
        group_key="grpA",
        items=[item1, item2],
        client=object(),
        use_zhipu=False,
        correction_service=None,
    )

    assert len(executed_calls) == 4
    expected_session_ids = {
        ("grpA", 1): _build_group_session_id(task.id, "grpA", 1),
        ("grpA", 2): _build_group_session_id(task.id, "grpA", 2),
    }
    assert {call["session_id"] for call in executed_calls if call["run_index"] == 1} == {expected_session_ids[("grpA", 1)]}
    assert {call["session_id"] for call in executed_calls if call["run_index"] == 2} == {expected_session_ids[("grpA", 2)]}
    assert all(status == RunStatus.SUCCEEDED for _, status in updated_runs)
    assert len(progress_updates) == 2
    assert task.progress_processed == 2


def test_process_multi_turn_group_skips_when_no_pending(monkeypatch):
    task = SimpleNamespace(
        id="task-done",
        runs_per_item=1,
        enable_correction=False,
        progress_processed=0,
        total_items=1,
    )
    item = SimpleNamespace(
        id="item-1",
        question_id="Q1",
        question="你好",
        standard_answer="hi",
        session_group="grpZ",
        runs=[_make_run(1, RunStatus.SUCCEEDED)],
    )

    execute_calls = []

    def fake_execute(*args, **kwargs):
        execute_calls.append(1)
        return "resp", None, None, 1

    monkeypatch.setattr("app.services.evaluation_runner._execute_single_run", fake_execute)
    monkeypatch.setattr(
        "app.services.evaluation_runner.repo.update_run_result",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "app.services.evaluation_runner.repo.increment_task_progress",
        lambda *args, **kwargs: None,
    )

    _process_multi_turn_group(
        DummySession(),
        task=task,
        group_key="grpZ",
        items=[item],
        client=object(),
        use_zhipu=False,
        correction_service=None,
    )

    assert execute_calls == []
