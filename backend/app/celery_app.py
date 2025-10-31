from celery import Celery

from app.core.config import settings


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
