from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Tuple

from zai import ZhipuAiClient

from app.core.config import settings

logger = logging.getLogger(__name__)

APP_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = APP_DIR.parent
PROMPT_DIR = APP_DIR / "prompts" / "zhipu"
DEFAULT_PROMPT_PATH = PROMPT_DIR / "default_chat_prompt.txt"


class ZhipuConfigurationError(RuntimeError):
    """Raised when Zhipu runner cannot be configured properly."""


def _read_text_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        logger.warning("Zhipu prompt file not found: %s", path)
        return ""
    except OSError as exc:
        logger.warning("Failed to read prompt file %s: %s", path, exc)
        return ""


def _resolve_prompt_text(task, item) -> str:
    # Priority: per-item system prompt → task header prompt → prompt file → default.
    if getattr(item, "system_prompt", None):
        return item.system_prompt.strip()

    headers: Dict[str, str] = getattr(task, "agent_api_headers", {}) or {}
    direct_prompt = headers.get("prompt_override") or headers.get("prompt")
    if isinstance(direct_prompt, str) and direct_prompt.strip():
        return direct_prompt.strip()

    prompt_path_value = headers.get("prompt_path")
    if isinstance(prompt_path_value, str) and prompt_path_value.strip():
        prompt_path = Path(prompt_path_value.strip())
        if not prompt_path.is_absolute():
            prompt_path = PROJECT_ROOT / prompt_path
        return _read_text_file(prompt_path)

    if DEFAULT_PROMPT_PATH.exists():
        return _read_text_file(DEFAULT_PROMPT_PATH)

    return ""


def _build_user_message(item) -> str:
    question = (item.question or "").strip()
    if not question:
        return ""
    context = getattr(item, "user_context", None)
    if context:
        context_str = context.strip()
        if context_str:
            return f"{context_str}\n\n{question}"
    return question


def _extract_content(choice) -> Tuple[str, str | None]:
    message = getattr(choice, "message", None)
    if message is None:
        return "", "Response missing message field"

    collected: List[str] = []
    content = getattr(message, "content", None)
    if isinstance(content, str) and content.strip():
        collected.append(content.strip())
    elif isinstance(content, list):
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text" and block.get("text"):
                    collected.append(str(block["text"]))
            elif isinstance(block, str):
                collected.append(block)

    reasoning = getattr(message, "reasoning_content", None)
    if isinstance(reasoning, str) and reasoning.strip():
        collected.append(f"<think>\n{reasoning.strip()}\n</think>")

    if collected:
        return "\n\n".join(part for part in collected if part.strip()), None

    return "", "Empty response content"


class ZhipuRunner:
    def __init__(self) -> None:
        if not settings.zhipu_api_key:
            raise ZhipuConfigurationError("ZHIPU_API_KEY 未配置，无法调用智谱模型")
        self.client = ZhipuAiClient(api_key=settings.zhipu_api_key)
        self.model_id = settings.zhipu_model_id
        self.max_tokens = settings.zhipu_max_tokens
        self.temperature = settings.zhipu_temperature
        self.dialog_mode = settings.zhipu_dialog_mode
        self.thinking_type = settings.zhipu_thinking_type

    def execute(self, task, item, run) -> Tuple[str, str | None, str | None, int]:
        started = time.perf_counter()
        context = f"task={task.id} item={item.question_id} run={run.run_index}"
        prompt_text = _resolve_prompt_text(task, item)
        user_message = _build_user_message(item)

        if not user_message:
            logger.warning("Zhipu request [%s] user message为空，跳过调用", context)
            latency_ms = int((time.perf_counter() - started) * 1000)
            return "", "INVALID_INPUT", "Question content is empty", latency_ms

        messages: List[Dict[str, str]] = []
        if prompt_text:
            messages.append({"role": "system", "content": prompt_text})
        messages.append({"role": "user", "content": user_message})

        request_payload: Dict[str, object] = {
            "model": self.model_id,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }
        if self.thinking_type not in {"", "disabled", "off"}:
            request_payload["thinking"] = {"type": self.thinking_type}

        logger.info("Zhipu request [%s]: %s", context, json.dumps(request_payload, ensure_ascii=False))

        try:
            response = self.client.chat.completions.create(**request_payload)
        except Exception as exc:  # noqa: BLE001
            latency_ms = int((time.perf_counter() - started) * 1000)
            logger.exception("Zhipu request失败 [%s]: %s", context, exc)
            return "", "ZHIPU_ERROR", str(exc), latency_ms

        latency_ms = int((time.perf_counter() - started) * 1000)
        response_dump = json.dumps(response.model_dump(), ensure_ascii=False)
        logger.info("Zhipu response [%s]: %s", context, response_dump)

        choice = response.choices[0] if getattr(response, "choices", None) else None
        if not choice:
            return "", "ZHIPU_ERROR", "Response missing choices", latency_ms

        content, warning = _extract_content(choice)
        if warning:
            logger.warning("Zhipu response内容异常 [%s]: %s", context, warning)
            return "", "ZHIPU_EMPTY", warning, latency_ms

        return content, None, None, latency_ms


__all__ = ["ZhipuRunner", "ZhipuConfigurationError"]
