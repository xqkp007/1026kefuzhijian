import io
import pytest
from fastapi import HTTPException
from starlette.datastructures import UploadFile

from app.utils import dataset_loader


@pytest.mark.asyncio
async def test_load_dataset_generates_question_ids():
    csv_content = "question,standard_answer\n中国的首都是哪里？,北京\n上海的别称是什么？,申城\n"
    upload = UploadFile(filename="sample.csv", file=io.BytesIO(csv_content.encode("utf-8")))

    records, raw = await dataset_loader.load_dataset(upload)

    assert len(records) == 2
    assert len(raw) == len(csv_content.encode("utf-8"))
    assert all(record["question_id"] for record in records)
    assert records[0]["question"] == "中国的首都是哪里？"
    assert records[1]["standard_answer"] == "申城"
    assert all("session_group" in record for record in records)


@pytest.mark.asyncio
async def test_load_dataset_missing_required_column():
    csv_content = "question_id,standard_answer\n1,北京\n"
    upload = UploadFile(filename="invalid.csv", file=io.BytesIO(csv_content.encode("utf-8")))

    with pytest.raises(HTTPException) as exc:
        await dataset_loader.load_dataset(upload)

    assert exc.value.status_code == 422
    assert exc.value.detail["code"] == "DATASET_SCHEMA_INVALID"


@pytest.mark.asyncio
async def test_load_dataset_with_session_group_column():
    csv_content = (
        "question,standard_answer,session_group\n"
        "你好,hi, grpA \n"
        "请继续,please continue,\n"
    )
    upload = UploadFile(filename="multi.csv", file=io.BytesIO(csv_content.encode("utf-8")))

    records, _ = await dataset_loader.load_dataset(upload)

    assert records[0]["session_group"] == "grpA"
    assert records[1]["session_group"] is None
