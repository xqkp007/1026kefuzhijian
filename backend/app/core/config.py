import json
from functools import lru_cache
from typing import Dict, List

from pydantic import AnyUrl, Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = Field(default="Agent Evaluation Backend", alias="APP_NAME")

    database_url: AnyUrl = Field(
        default="postgresql+psycopg2://postgres:postgres@localhost:5432/agent_eval",
        alias="DATABASE_URL",
    )
    redis_url: AnyUrl = Field(
        default="redis://localhost:6379/0",
        alias="REDIS_URL",
        description="Celery broker & backend URL",
    )

    agent_api_allowlist: str = Field(default="*", alias="AGENT_API_ALLOWLIST")

    runs_per_item: int = Field(default=5, alias="RUNS_PER_ITEM", ge=1, le=10)
    timeout_seconds: float = Field(default=30.0, alias="TIMEOUT_SECONDS", gt=0)
    request_max_retries: int = Field(default=1, alias="REQUEST_MAX_RETRIES", ge=0, le=5)

    evaluation_concurrency: int = Field(
        default=1, alias="EVALUATION_CONCURRENCY", ge=1, le=16
    )
    rate_limit_per_agent: str = Field(default="1/s", alias="RATE_LIMIT_PER_AGENT")

    max_dataset_rows: int = Field(default=1000, alias="MAX_DATASET_ROWS", ge=1)
    max_dataset_file_size_mb: int = Field(
        default=5, alias="MAX_DATASET_FILE_SIZE_MB", ge=1
    )
    use_stream: bool = Field(default=True, alias="USE_STREAM")
    use_minimal_payload: bool = Field(default=False, alias="USE_MINIMAL_PAYLOAD")

    uploads_dir: str = Field(default="storage/uploads", alias="UPLOADS_DIR")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    agent_api_bearer: str | None = Field(default=None, alias="AGENT_API_BEARER")
    default_agent_api_headers: Dict[str, str] = Field(
        default_factory=dict, alias="DEFAULT_AGENT_API_HEADERS"
    )
    default_agent_extra_fields: Dict[str, str] = Field(
        default_factory=dict, alias="DEFAULT_AGENT_EXTRA_FIELDS"
    )
    zhipu_api_key: str | None = Field(default=None, alias="ZHIPU_API_KEY")
    zhipu_model_id: str = Field(default="glm-4.6", alias="ZHIPU_MODEL_ID")
    zhipu_thinking_type: str = Field(default="disabled", alias="ZHIPU_THINKING_TYPE")
    zhipu_max_tokens: int = Field(default=4096, alias="ZHIPU_MAX_TOKENS", gt=0)
    zhipu_temperature: float = Field(default=0.7, alias="ZHIPU_TEMPERATURE", ge=0, le=2)
    zhipu_dialog_mode: str = Field(default="single", alias="ZHIPU_DIALOG_MODE")
    correction_model_id: str = Field(default="glm-4.6", alias="CORRECTION_MODEL_ID")
    correction_temperature: float = Field(default=0.3, alias="CORRECTION_TEMPERATURE", ge=0, le=2)
    correction_max_tokens: int = Field(default=512, alias="CORRECTION_MAX_TOKENS", gt=0)
    correction_timeout_seconds: float = Field(
        default=30.0, alias="CORRECTION_TIMEOUT_SECONDS", gt=0
    )
    correction_max_retries: int = Field(default=3, alias="CORRECTION_MAX_RETRIES", ge=0, le=5)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @field_validator("agent_api_allowlist")
    @classmethod
    def _normalize_allowlist(cls, value: str) -> str:
        return value.strip()

    @field_validator("default_agent_api_headers", mode="before")
    @classmethod
    def _parse_default_agent_headers(cls, value):
        if value in (None, "", {}):
            return {}
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return {}
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as exc:  # noqa: B904
                raise ValueError("DEFAULT_AGENT_API_HEADERS 必须是合法的 JSON 对象") from exc
            if not isinstance(parsed, dict):
                raise ValueError("DEFAULT_AGENT_API_HEADERS 必须是 JSON 对象")
            return parsed
        if isinstance(value, dict):
            return value
        raise ValueError("DEFAULT_AGENT_API_HEADERS 必须是 JSON 对象或 JSON 字符串")

    @field_validator("default_agent_extra_fields", mode="before")
    @classmethod
    def _parse_default_extra_fields(cls, value):
        if value in (None, "", {}):
            return {}
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return {}
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as exc:  # noqa: B904
                raise ValueError("DEFAULT_AGENT_EXTRA_FIELDS 必须是合法的 JSON 对象") from exc
            if not isinstance(parsed, dict):
                raise ValueError("DEFAULT_AGENT_EXTRA_FIELDS 必须是 JSON 对象")
            return parsed
        if isinstance(value, dict):
            return value
        raise ValueError("DEFAULT_AGENT_EXTRA_FIELDS 必须是 JSON 对象或 JSON 字符串")

    @field_validator("zhipu_api_key", mode="before")
    @classmethod
    def _normalize_zhipu_api_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None

    @field_validator("zhipu_thinking_type")
    @classmethod
    def _validate_zhipu_thinking_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        allowed = {"disabled", "enabled", "sse", "off"}
        if normalized not in allowed:
            raise ValueError(
                f"ZHIPU_THINKING_TYPE 仅支持 {', '.join(sorted(allowed))}，当前为 '{value}'."
            )
        return normalized

    @field_validator("zhipu_dialog_mode")
    @classmethod
    def _validate_zhipu_dialog_mode(cls, value: str) -> str:
        normalized = value.strip().lower()
        allowed = {"single", "multi"}
        if normalized not in allowed:
            raise ValueError(
                f"ZHIPU_DIALOG_MODE 仅支持 {', '.join(sorted(allowed))}，当前为 '{value}'."
            )
        return normalized

    @property
    def allowlist(self) -> List[str]:
        if not self.agent_api_allowlist or self.agent_api_allowlist == "*":
            return ["*"]
        return [item.strip() for item in self.agent_api_allowlist.split(",") if item.strip()]

    @property
    def default_agent_headers(self) -> Dict[str, str]:
        headers = dict(self.default_agent_api_headers or {})
        if self.agent_api_bearer and "Authorization" not in headers:
            headers["Authorization"] = f"Bearer {self.agent_api_bearer}"
        return headers


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
