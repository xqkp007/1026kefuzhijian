from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
import re
from pathlib import Path
from typing import Optional

from zai import ZhipuAiClient

from app.core.config import settings

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "correction_prompt.txt"


class CorrectionConfigurationError(RuntimeError):
    """Raised when correction service cannot be configured."""


@dataclass
class CorrectionOutcome:
    status: str
    is_correct: Optional[bool]
    reason: Optional[str]
    error_message: Optional[str]
    retries: int


class CorrectionService:
    def __init__(self) -> None:
        if not settings.zhipu_api_key:
            raise CorrectionConfigurationError("ZHIPU_API_KEY 未配置，无法执行矫正")
        self.client = ZhipuAiClient(api_key=settings.zhipu_api_key)
        self.model_id = settings.correction_model_id
        self.temperature = settings.correction_temperature
        self.max_tokens = settings.correction_max_tokens
        self.max_retries = settings.correction_max_retries
        self._prompt_template = self._load_prompt()

    def _load_prompt(self) -> str:
        try:
            return PROMPT_PATH.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            logger.error("矫正提示词文件缺失: %s", PROMPT_PATH)
        except OSError as exc:
            logger.error("读取矫正提示词失败 %s: %s", PROMPT_PATH, exc)
        return (
            "你是一名答案判定专家，请严格对比给定的标准答案和智能体输出，"
            "仅返回 JSON，例如 {\"is_correct\": true, \"reason\": \"...\"}。"
        )

    def _build_messages(self, question: str, standard_answer: str, agent_output: str) -> list[dict[str, str]]:
        prompt = self._prompt_template.format(
            question=question,
            standard_answer=standard_answer,
            agent_output=agent_output,
        )
        return [
            {"role": "system", "content": "你是一名严格的答案判定专家。"},
            {"role": "user", "content": prompt},
        ]

    @staticmethod
    def _extract_raw_text(choice) -> str:
        """Extract text from Zhipu choice message supporting list blocks and json objects."""
        msg = getattr(choice, "message", None)
        if msg is None:
            return ""
        content = getattr(msg, "content", None)
        if isinstance(content, str) and content.strip():
            return content.strip()
        collected: list[str] = []
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    btype = block.get("type")
                    if btype in {"text", "input_text"} and block.get("text"):
                        collected.append(str(block["text"]))
                    elif btype in {"json", "json_object"} and block.get("json") is not None:
                        try:
                            collected.append(
                                json.dumps(block["json"], ensure_ascii=False)
                            )
                        except Exception:
                            # 兜底：转成字符串
                            collected.append(str(block["json"]))
                    elif block.get("content"):
                        collected.append(str(block.get("content")))
                elif isinstance(block, str):
                    collected.append(block)
        if collected:
            return "\n".join(part for part in collected if str(part).strip()).strip()
        # 附加：有些模型把 reasoning_content 分开放在 message 上
        reasoning = getattr(msg, "reasoning_content", None)
        if isinstance(reasoning, str) and reasoning.strip():
            return reasoning.strip()
        return ""

    def _parse_content(self, content: str) -> tuple[Optional[bool], Optional[str], Optional[str]]:
        # 预处理：去除围栏、前缀说明，尝试提取首个 JSON 对象
        text = content.strip()
        # 处理 ```json ... ``` 或 ``` ... ```
        if "```" in text:
            m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
            if m:
                text = m.group(1).strip()
        # 若仍解析失败，尝试提取第一个大括号包裹的 JSON 对象
        def _extract_first_json(s: str) -> str | None:
            start = s.find('{')
            if start == -1:
                return None
            depth = 0
            for i in range(start, len(s)):
                if s[i] == '{':
                    depth += 1
                elif s[i] == '}':
                    depth -= 1
                    if depth == 0:
                        return s[start:i+1]
            return None
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            candidate = _extract_first_json(text)
            if candidate is None:
                logger.warning("矫正结果解析失败: Invalid JSON format")
                return None, None, "Invalid JSON format"
            try:
                payload = json.loads(candidate)
            except json.JSONDecodeError as exc:
                logger.warning("矫正结果解析失败: %s", exc)
                return None, None, "Invalid JSON format"

        is_correct = payload.get("is_correct") if isinstance(payload, dict) else None
        reason = payload.get("reason") if isinstance(payload, dict) else None

        if isinstance(is_correct, bool):
            return is_correct, reason if isinstance(reason, str) else None, None

        return None, None, "Missing is_correct field"

    def evaluate(self, *, question: str, standard_answer: str, agent_output: str) -> CorrectionOutcome:
        if not agent_output:
            return CorrectionOutcome(
                status="FAILED",
                is_correct=False,
                reason=None,
                error_message="Agent output is empty",
                retries=0,
            )

        messages = self._build_messages(question, standard_answer, agent_output)
        retries = 0
        last_error = None
        start = time.perf_counter()

        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_id,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    # 强制 JSON 输出，若服务端支持该参数，将提升可解析性
                    response_format={"type": "json_object"},
                    thinking={"type": "disabled"},
                )
                response_dump = response.model_dump()
                # 用 info 级别记录一次，便于现场排查
                logger.info(
                    "Correction response (attempt %s): %s",
                    attempt + 1,
                    json.dumps(response_dump, ensure_ascii=False),
                )

                choice = response.choices[0] if getattr(response, "choices", None) else None
                if not choice:
                    raise ValueError("Response missing choices")

                content = self._extract_raw_text(choice)
                if not content:
                    raise ValueError("Empty response content")

                is_correct, reason, error_message = self._parse_content(content)
                if error_message:
                    raise ValueError(error_message)
                logger.info(
                    "Correction succeeded (attempt %s, latency=%sms)",
                    attempt + 1,
                    int((time.perf_counter() - start) * 1000),
                )
                return CorrectionOutcome(
                    status="SUCCESS",
                    is_correct=is_correct,
                    reason=reason,
                    error_message=None,
                    retries=retries,
                )
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
                logger.warning(
                    "Correction attempt %s failed: %s | raw=%r",
                    attempt + 1,
                    last_error,
                    content if 'content' in locals() else None,
                )
                retries = attempt + 1

        return CorrectionOutcome(
            status="FAILED",
            is_correct=False,
            reason=None,
            error_message=last_error,
            retries=retries,
        )


__all__ = ["CorrectionService", "CorrectionOutcome", "CorrectionConfigurationError"]
