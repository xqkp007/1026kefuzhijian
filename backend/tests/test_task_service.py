import io
import types

import pytest
from fastapi import HTTPException
from starlette.datastructures import UploadFile

from app.services import task_service
from app.schemas.evaluation_task import TaskCreateRequest


def test_parse_headers_accepts_json_object():
    headers = task_service.parse_headers('{"Authorization": "Bearer token"}')
    assert headers == {"Authorization": "Bearer token"}


def test_parse_headers_rejects_invalid_json():
    with pytest.raises(HTTPException) as exc:
        task_service.parse_headers("{invalid json}")
    assert exc.value.status_code == 422
    assert exc.value.detail["code"] == "INVALID_AGENT_HEADERS"


@pytest.mark.asyncio
async def test_create_evaluation_task_with_enable_correction(monkeypatch):
    payload = TaskCreateRequest(
        task_name="demo task",
        agent_api_url="http://agent.example.com/api",
        enable_correction=True,
    )

    dataset_file = UploadFile(
        filename="dataset.csv",
        file=io.BytesIO(b"question,standard_answer\nwhat?,answer\n"),
    )

    created_kwargs = {}

    class DummyTask:
        def __init__(self) -> None:
            self.id = "task-123"

    dummy_items = [types.SimpleNamespace(id="item-1")]

    def fake_create_task(db, **kwargs):
        created_kwargs.update(kwargs)
        return DummyTask()

    def fake_bulk_insert_items(db, *, task_id, items):
        assert task_id == "task-123"
        return dummy_items

    def fake_create_initial_runs(db, *, item, runs_per_item):
        assert item.id == "item-1"
        assert runs_per_item == task_service.settings.runs_per_item

    async def fake_load_dataset(upload):
        return (
            [
                {
                    "question_id": "q-1",
                    "question": "Sample question",
                    "standard_answer": "Sample answer",
                }
            ],
            b"raw-bytes",
        )

    class DummySession:
        def __init__(self) -> None:
            self.committed = False
            self.rolled_back = False

        def commit(self) -> None:
            self.committed = True

        def rollback(self) -> None:
            self.rolled_back = True

    dummy_db = DummySession()
    enqueue_calls = []

    monkeypatch.setattr(task_service.repo, "create_task", fake_create_task)
    monkeypatch.setattr(task_service.repo, "bulk_insert_items", fake_bulk_insert_items)
    monkeypatch.setattr(task_service.repo, "create_initial_runs", fake_create_initial_runs)
    monkeypatch.setattr(task_service, "load_dataset", fake_load_dataset)
    monkeypatch.setattr(task_service, "save_dataset_file", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        task_service.run_evaluation_task,
        "delay",
        lambda task_id: enqueue_calls.append(task_id),
    )

    response = await task_service.create_evaluation_task(
        dummy_db,
        payload=payload,
        dataset_file=dataset_file,
    )

    assert dummy_db.committed is True
    assert created_kwargs["enable_correction"] is True
    assert response.enable_correction is True
    assert response.task_id == "task-123"
    assert enqueue_calls == ["task-123"]
