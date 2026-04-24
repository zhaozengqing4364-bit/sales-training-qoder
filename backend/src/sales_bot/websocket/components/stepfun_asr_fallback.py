"""ASR fallback policy and websocket status helpers for StepFun realtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from sales_bot.websocket.components.stepfun_event_payloads import build_status_event

ASRFallbackState = Literal["healthy", "fallback_required", "fallback_unavailable"]
ASR_BROWSER_HANDOFF_CODE = "[ASR_BROWSER_HANDOFF_REQUIRED]"
ASR_FALLBACK_REQUIRED_ERROR_CODE = "[ASR_FALLBACK_REQUIRED]"

_ASR_ERROR_KEYWORDS = (
    "asr",
    "speech",
    "transcription",
    "transcript",
    "input_audio",
    "audio transcription",
)


@dataclass(frozen=True)
class ASRFallbackPolicy:
    """Client-visible policy for ASR provider failure handling."""

    state: ASRFallbackState = "fallback_required"
    primary_provider: str = "stepfun_realtime"
    fallback_provider: str = "browser_web_speech"
    user_message: str = "语音识别服务暂时不可用，请切换到浏览器语音识别或文本输入。"
    user_action: str = "请启用浏览器麦克风权限，或改用文本输入继续练习。"
    retryable: bool = True

    def as_payload(self, *, reason: str) -> dict[str, Any]:
        return {
            "state": self.state,
            "reason": reason,
            "primary_provider": self.primary_provider,
            "fallback_provider": self.fallback_provider,
            "fallback_code": ASR_BROWSER_HANDOFF_CODE,
            "message": self.user_message,
            "user_action": self.user_action,
            "retryable": self.retryable,
        }


DEFAULT_ASR_FALLBACK_POLICY = ASRFallbackPolicy()


def extract_asr_error_reason(event: dict[str, Any]) -> str | None:
    """Return an ASR-specific failure reason from a StepFun error event."""
    candidates: list[str] = []
    error_obj = event.get("error")
    if isinstance(error_obj, dict):
        for key in ("code", "type", "message", "param"):
            value = error_obj.get(key)
            if isinstance(value, str) and value.strip():
                candidates.append(value.strip())
    for key in ("code", "type", "message"):
        value = event.get(key)
        if isinstance(value, str) and value.strip():
            candidates.append(value.strip())

    searchable = " ".join(candidates).lower()
    if not searchable:
        return None
    if any(keyword in searchable for keyword in _ASR_ERROR_KEYWORDS):
        return candidates[0]
    return None


def build_asr_fallback_status_event(
    *,
    reason: str,
    session_status: str,
    ai_state: str,
    turn_count: int,
    trace_id: str,
    policy: ASRFallbackPolicy = DEFAULT_ASR_FALLBACK_POLICY,
) -> dict[str, Any]:
    """Build a normal status event with explicit ASR fallback metadata."""
    event = build_status_event(
        session_status=session_status,
        ai_state=ai_state,
        turn_count=turn_count,
        trace_id=trace_id,
    )
    event["data"]["asr_status"] = policy.as_payload(reason=reason)
    return event
