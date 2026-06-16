from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from prompt_templates.compiled_contract import CompiledPromptContract
from sales_trainer.ai_coach_chat_schemas import (
    AiCoachChatResponseInternalV1,
    AiCoachQuizCardDraftInteractionPublicV1,
    AiCoachQuizCardDraftPayloadPublicV1,
)
from sales_trainer.schemas import AiCoachConfig, AiCoachPublicInteractionOptionV1
from sales_trainer.services.ai_coach_chat_errors import AiCoachChatGenerationError
from sales_trainer.services.ai_coach_chat_generation_parser import (
    AiCoachChatResponseParser,
)

AiCoachGenerationDeltaHandler = Callable[
    [AiCoachQuizCardDraftPayloadPublicV1],
    Awaitable[None],
]
AiCoachResponseValidator = Callable[[AiCoachChatResponseInternalV1], None]


@dataclass(frozen=True)
class AiCoachStreamedResponseResult:
    response: AiCoachChatResponseInternalV1


class AiCoachQuizCardDraftExtractor:
    def __init__(self, *, session_id: str) -> None:
        self._session_id = session_id
        self._last_fingerprint: str | None = None

    def extract_changed(
        self,
        buffer: str,
    ) -> AiCoachQuizCardDraftPayloadPublicV1 | None:
        draft = self.extract(buffer)
        if draft is None:
            return None
        fingerprint = draft.model_dump_json(exclude_none=True)
        if fingerprint == self._last_fingerprint:
            return None
        self._last_fingerprint = fingerprint
        return draft

    def extract(self, buffer: str) -> AiCoachQuizCardDraftPayloadPublicV1 | None:
        if '"quiz_card"' not in buffer and '"interaction"' not in buffer:
            return None

        training_card_type = self._string_field(buffer, "training_card_type")
        interaction_type = self._string_field(buffer, "interaction_type")
        stem = self._partial_string_field(buffer, "stem")
        options = self._options(buffer)
        capability_keys = self._string_array_field(buffer, "capability_keys")
        source_chapter_orders = self._int_array_field(buffer, "source_chapter_orders")
        explanation = self._partial_string_field(buffer, "explanation")

        if not any(
            [
                training_card_type,
                interaction_type,
                stem,
                options,
                capability_keys,
                source_chapter_orders,
            ]
        ):
            return None

        constraints: dict[str, int] = {}
        if interaction_type == "single_choice":
            constraints = {"min_selected": 1, "max_selected": 1}
        elif interaction_type == "multiple_choice" and options:
            constraints = {"min_selected": 1, "max_selected": len(options)}
        elif interaction_type == "short_answer":
            constraints = {"min_length": 1, "max_length": 8000}

        return AiCoachQuizCardDraftPayloadPublicV1(
            interaction=AiCoachQuizCardDraftInteractionPublicV1(
                interaction_id=f"stream-{self._session_id}",
                session_id=self._session_id,
                training_card_type=(
                    training_card_type
                    if training_card_type in {
                        "scenario_judgment",
                        "expression_rewrite",
                        "role_response",
                    }
                    else None
                ),
                interaction_type=(
                    interaction_type
                    if interaction_type in {
                        "single_choice",
                        "multiple_choice",
                        "short_answer",
                    }
                    else None
                ),
                stem=stem,
                options=options or None,
                answer_constraints=constraints,
                capability_keys=capability_keys,
                source_chapter_orders=source_chapter_orders,
                is_complete=False,
            ),
            explanation=explanation,
        )

    @staticmethod
    def _string_field(buffer: str, field: str) -> str | None:
        match = re.search(
            rf'"{re.escape(field)}"\s*:\s*"((?:\\.|[^"\\])*)"',
            buffer,
            flags=re.DOTALL,
        )
        if match is None:
            return None
        try:
            value = json.loads(f'"{match.group(1)}"')
        except json.JSONDecodeError:
            return None
        if not isinstance(value, str):
            return None
        value = value.strip()
        return value or None

    @classmethod
    def _partial_string_field(cls, buffer: str, field: str) -> str | None:
        field_match = re.search(
            rf'"{re.escape(field)}"\s*:\s*"',
            buffer,
            flags=re.DOTALL,
        )
        if field_match is None:
            return None

        start = field_match.end()
        raw_pieces: list[str] = []
        escaped = False
        closed = False
        for char in buffer[start:]:
            if escaped:
                raw_pieces.append(f"\\{char}")
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == '"':
                closed = True
                break
            raw_pieces.append(char)

        raw_value = "".join(raw_pieces)
        if not raw_value:
            return None

        if closed:
            try:
                value = json.loads(f'"{raw_value}"')
            except json.JSONDecodeError:
                return None
        else:
            value = cls._decode_partial_json_string(raw_value)
        if not isinstance(value, str):
            return None
        value = value.strip()
        return value or None

    @staticmethod
    def _decode_partial_json_string(raw_value: str) -> str:
        candidate = raw_value.rstrip("\\")
        while candidate:
            try:
                decoded = json.loads(f'"{candidate}"')
                return decoded if isinstance(decoded, str) else ""
            except json.JSONDecodeError:
                if candidate.endswith("\\u") or re.search(r"\\u[0-9a-fA-F]{0,3}$", candidate):
                    candidate = candidate.rsplit("\\u", 1)[0]
                    continue
                return (
                    candidate.replace(r"\"", '"')
                    .replace(r"\\", "\\")
                    .replace(r"\n", "\n")
                    .replace(r"\t", "\t")
                )
        return ""

    @classmethod
    def _string_array_field(cls, buffer: str, field: str) -> list[str]:
        fragment = cls._array_fragment(buffer, field)
        if not fragment:
            return []
        values: list[str] = []
        for match in re.finditer(r'"((?:\\.|[^"\\])*)"', fragment, flags=re.DOTALL):
            try:
                value = json.loads(f'"{match.group(1)}"')
            except json.JSONDecodeError:
                continue
            if isinstance(value, str) and value.strip() and value not in values:
                values.append(value.strip())
        return values[:10]

    @classmethod
    def _int_array_field(cls, buffer: str, field: str) -> list[int]:
        fragment = cls._array_fragment(buffer, field)
        if not fragment:
            return []
        values: list[int] = []
        for match in re.finditer(r"\b\d+\b", fragment):
            value = int(match.group(0))
            if value >= 1 and value not in values:
                values.append(value)
        return values[:20]

    @staticmethod
    def _array_fragment(buffer: str, field: str) -> str:
        field_index = buffer.find(f'"{field}"')
        if field_index < 0:
            return ""
        open_index = buffer.find("[", field_index)
        if open_index < 0:
            return ""
        close_index = buffer.find("]", open_index + 1)
        end_index = close_index if close_index >= 0 else len(buffer)
        return buffer[open_index + 1 : end_index]

    @classmethod
    def _options(cls, buffer: str) -> list[AiCoachPublicInteractionOptionV1]:
        fragment = cls._array_fragment(buffer, "options")
        if not fragment:
            return []
        options: list[AiCoachPublicInteractionOptionV1] = []
        seen_ids: set[str] = set()
        for match in re.finditer(r"\{[^{}]*\}", fragment, flags=re.DOTALL):
            try:
                raw = json.loads(match.group(0))
            except json.JSONDecodeError:
                continue
            if not isinstance(raw, dict):
                continue
            option_id = raw.get("option_id")
            text = raw.get("text")
            if not isinstance(option_id, str) or not isinstance(text, str):
                continue
            option_id = option_id.strip()
            text = text.strip()
            if not option_id or not text or option_id in seen_ids:
                continue
            seen_ids.add(option_id)
            options.append(
                AiCoachPublicInteractionOptionV1(
                    option_id=option_id,
                    text=text,
                )
            )
        return options[:8]


async def emit_streamed_response(
    *,
    llm,
    parser: AiCoachChatResponseParser,
    contract: CompiledPromptContract,
    config: AiCoachConfig,
    session_id: str,
    max_attempts: int,
    failure_message: str,
    on_generation_delta: AiCoachGenerationDeltaHandler,
    validate_response: AiCoachResponseValidator | None = None,
) -> AiCoachStreamedResponseResult:
    last_error: AiCoachChatGenerationError | None = None
    for _attempt in range(max_attempts):
        prompt = prompt_for_attempt(contract.rendered_prompt, last_error)
        buffer = ""
        extractor = AiCoachQuizCardDraftExtractor(session_id=session_id)
        try:
            async for token in llm.stream_generate(
                prompt=prompt,
                session_id=session_id,
                system_message=contract.system_message,
                allow_fallback_response=False,
            ):
                buffer += token
                draft = extractor.extract_changed(buffer)
                if draft is not None:
                    await on_generation_delta(draft)
            if not buffer.strip():
                last_error = AiCoachChatGenerationError(
                    "[AI_COACH_LLM_GENERATION_FAILED]",
                    failure_message,
                    502,
                )
                continue
            parsed = parser.parse_model_response(buffer, config)
            if validate_response is not None:
                validate_response(parsed)
            return AiCoachStreamedResponseResult(response=parsed)
        except AiCoachChatGenerationError as exc:
            last_error = exc
            continue
        except (ConnectionError, TimeoutError, RuntimeError, ValueError, OSError) as exc:
            last_error = AiCoachChatGenerationError(
                f"[AI_COACH_LLM_GENERATION_FAILED:{type(exc).__name__}]",
                failure_message,
                502,
            )
            continue
    if last_error is not None:
        raise last_error
    raise AiCoachChatGenerationError(
        "[AI_COACH_LLM_GENERATION_FAILED]",
        failure_message,
        502,
    )


def prompt_for_attempt(
    base_prompt: str,
    last_error: AiCoachChatGenerationError | None,
) -> str:
    if last_error is None:
        return base_prompt
    return (
        f"{base_prompt}\n\n"
        "上一轮输出未通过后端契约校验。请只重新输出一份合法 JSON，"
        f"错误码：{last_error.code}。"
        "不要解释错误，不要输出 Markdown。"
    )
