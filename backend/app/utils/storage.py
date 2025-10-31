from pathlib import Path

from app.core.config import settings


def get_task_upload_dir(task_id: str) -> Path:
    root = Path(settings.uploads_dir)
    task_dir = root / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    return task_dir


def save_dataset_file(task_id: str, filename: str, content: bytes) -> Path:
    task_dir = get_task_upload_dir(task_id)
    path = task_dir / filename
    path.write_bytes(content)
    return path
