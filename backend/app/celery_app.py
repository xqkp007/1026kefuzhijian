from __future__ import annotations

import types

try:
    from celery import Celery
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    Celery = None

from app.core.config import settings


if Celery is not None:
    celery_app = Celery(
        "agent_evaluation",
        broker=str(settings.redis_url),
        backend=str(settings.redis_url),
        include=["app.services.evaluation_runner"],
    )

    celery_app.conf.update(
        task_routes={
            "app.services.evaluation_runner.run_evaluation_task": {
                "queue": "evaluation",
            },
        },
        task_acks_late=True,
        worker_concurrency=settings.evaluation_concurrency,
        task_default_rate_limit=settings.rate_limit_per_agent,
    )
else:  # pragma: no cover - lightweight fallback for local/unit usage
    class _DummyCelery:
        def __init__(self) -> None:
            self.conf = types.SimpleNamespace(update=lambda **kwargs: None)

        def task(self, name: str | None = None, **kwargs):  # noqa: D401 - signature parity
            def decorator(func):
                def delay(*args, **inner_kwargs):
                    return func(*args, **inner_kwargs)

                func.delay = delay
                return func

            return decorator

    celery_app = _DummyCelery()
