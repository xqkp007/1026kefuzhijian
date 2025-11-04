from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Sequence

from dotenv import load_dotenv
from zai import ZhipuAiClient

APP_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = APP_DIR.parent
DEFAULT_PROMPT_PATH = APP_DIR / "prompts" / "zhipu" / "default_chat_prompt.txt"
DEFAULT_USER_MESSAGE = "智谱AI开放平台"


class PromptFormatError(RuntimeError):
    """Raised when prompt variable formatting fails."""


def parse_prompt_vars(raw_pairs: Sequence[str]) -> Dict[str, str]:
    variables: Dict[str, str] = {}
    for pair in raw_pairs:
        if "=" not in pair:
            raise PromptFormatError(
                f"Invalid prompt variable '{pair}'. Expected format 'key=value'."
            )
        key, value = pair.split("=", 1)
        key = key.strip()
        if not key:
            raise PromptFormatError("Prompt variable key cannot be empty.")
        variables[key] = value.strip()
    return variables


def load_prompt(path: Path, variables: Dict[str, str]) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    template = path.read_text(encoding="utf-8")
    if not variables:
        return template
    try:
        return template.format(**variables)
    except KeyError as exc:
        missing_key = exc.args[0]
        raise PromptFormatError(
            f"Prompt template '{path}' requires variable '{missing_key}', "
            "but it was not provided."
        ) from exc


def load_history(path: Path | None) -> List[Dict[str, str]]:
    if path is None:
        return []
    if not path.exists():
        raise FileNotFoundError(f"History file not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("History file must contain a JSON array of messages.")
    messages: List[Dict[str, str]] = []
    for entry in payload:
        if not isinstance(entry, dict):
            raise ValueError("History entries must be JSON objects.")
        role = entry.get("role")
        content = entry.get("content")
        if role not in {"system", "user", "assistant"}:
            raise ValueError(f"Invalid role '{role}' in history entry.")
        if not isinstance(content, str):
            raise ValueError("Message content must be a string.")
        messages.append({"role": role, "content": content})
    return messages


def build_messages(
    system_prompt: str | None,
    user_message: str,
    history: Sequence[Dict[str, str]],
    dialog_mode: str,
) -> List[Dict[str, str]]:
    messages: List[Dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    if dialog_mode == "multi":
        messages.extend(history)
    messages.append({"role": "user", "content": user_message})
    return messages


def coerce_int(value: str | None, default: int, name: str) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got '{value}'.") from exc


def coerce_float(value: str | None, default: float, name: str) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a float, got '{value}'.") from exc


def _resolve_path(raw_path: Path) -> Path:
    return raw_path if raw_path.is_absolute() else (PROJECT_ROOT / raw_path).resolve()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a minimal ZhipuAI chat completion call using zai-sdk."
    )
    parser.add_argument(
        "--prompt-path",
        type=Path,
        default=DEFAULT_PROMPT_PATH,
        help="Path to the system prompt file (default: %(default)s).",
    )
    parser.add_argument(
        "--user-message",
        type=str,
        default=DEFAULT_USER_MESSAGE,
        help="User prompt to send with the request.",
    )
    parser.add_argument(
        "--history-path",
        type=Path,
        default=None,
        help=(
            "Optional JSON file containing prior messages "
            "(only used when dialog mode is 'multi')."
        ),
    )
    parser.add_argument(
        "--prompt-var",
        metavar="key=value",
        action="append",
        default=[],
        help="Placeholder variables used to format the prompt template.",
    )
    args = parser.parse_args()

    load_dotenv(PROJECT_ROOT / ".env")
    load_dotenv(PROJECT_ROOT / ".env.local", override=True)

    api_key = os.getenv("ZHIPU_API_KEY")
    if not api_key:
        print("❌ ZHIPU_API_KEY is not set. Please configure it in backend/.env.", file=sys.stderr)
        return 1

    model_id = os.getenv("ZHIPU_MODEL_ID", "glm-4.6")
    thinking_type = os.getenv("ZHIPU_THINKING_TYPE", "disabled").lower()
    max_tokens = coerce_int(os.getenv("ZHIPU_MAX_TOKENS"), default=4096, name="ZHIPU_MAX_TOKENS")
    temperature = coerce_float(
        os.getenv("ZHIPU_TEMPERATURE"), default=0.7, name="ZHIPU_TEMPERATURE"
    )
    dialog_mode = os.getenv("ZHIPU_DIALOG_MODE", "single").lower()
    if dialog_mode not in {"single", "multi"}:
        print(
            f"⚠️  Unsupported ZHIPU_DIALOG_MODE '{dialog_mode}'. Falling back to 'single'.",
            file=sys.stderr,
        )
        dialog_mode = "single"

    prompt_path = _resolve_path(args.prompt_path)
    history_path = _resolve_path(args.history_path) if args.history_path else None

    try:
        prompt_variables = parse_prompt_vars(args.prompt_var)
        system_prompt = load_prompt(prompt_path, prompt_variables)
        history_messages = load_history(history_path)
        if dialog_mode == "single" and history_messages:
            print(
                "⚠️  History file provided but dialog mode is 'single'; history will be ignored.",
                file=sys.stderr,
            )
            history_messages = []
        messages = build_messages(
            system_prompt=system_prompt,
            user_message=args.user_message.strip(),
            history=history_messages,
            dialog_mode=dialog_mode,
        )
    except (PromptFormatError, FileNotFoundError, ValueError) as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1

    thinking_payload = None
    if thinking_type not in {"", "disabled", "off"}:
        thinking_payload = {"type": thinking_type}

    print("🚀 Dispatching request to ZhipuAI with the following parameters:")
    print(f"   • Model: {model_id}")
    print(f"   • Dialog mode: {dialog_mode}")
    print(f"   • Max tokens: {max_tokens}")
    print(f"   • Temperature: {temperature}")
    print(f"   • Prompt file: {prompt_path}")
    if prompt_variables:
        print(f"   • Prompt variables: {prompt_variables}")
    if history_path:
        print(f"   • History file: {history_path}")
    if thinking_payload:
        print(f"   • Thinking enabled: {thinking_payload}")
    else:
        print("   • Thinking: disabled (default)")

    client = ZhipuAiClient(api_key=api_key)
    request_payload = {
        "model": model_id,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if thinking_payload:
        request_payload["thinking"] = thinking_payload

    try:
        response = client.chat.completions.create(**request_payload)
    except Exception as exc:  # Broad catch to surface SDK/network issues to CLI users.
        print(f"❌ Request failed: {exc}", file=sys.stderr)
        return 1

    choice = None
    if getattr(response, "choices", None):
        choice = response.choices[0]
    if not choice:
        print("⚠️  Received response without choices.", file=sys.stderr)
        return 1

    message = getattr(choice, "message", None)
    content = getattr(message, "content", None)
    role = getattr(message, "role", "assistant")
    reasoning_content = getattr(message, "reasoning_content", None)

    print("\n✅ ZhipuAI response received:")
    if content:
        print(f"{role}: {content}")
    elif reasoning_content:
        print(f"{role} (reasoning): {reasoning_content}")
        print(
            "\n⚠️  当前响应主体为空，智谱将推理内容放在 reasoning_content 中。"
            " 可适当提升 ZHIPU_MAX_TOKENS 或开启思考模式以获得完整回答。"
        )
    else:
        print(f"{role}: <empty response>")

    request_id = getattr(response, "id", None) or getattr(response, "request_id", None)
    if request_id:
        print(f"\nℹ️  Request ID: {request_id}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
