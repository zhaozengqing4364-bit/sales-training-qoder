from __future__ import annotations

AI_COACH_STREAM_TIMEOUT_CODE = "[AI_COACH_STREAM_TIMEOUT]"
AI_COACH_STREAM_TIMEOUT_MESSAGE = "AI 教练生成超时，已保留当前训练局。"


class AiCoachChatGenerationError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class AiCoachChatServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def service_error_from_exception(exc: Exception) -> AiCoachChatServiceError:
    if hasattr(exc, "code") and hasattr(exc, "message"):
        return AiCoachChatServiceError(
            str(getattr(exc, "code")),
            str(getattr(exc, "message")),
            int(getattr(exc, "status_code", 400)),
        )
    return AiCoachChatServiceError(
        "[AI_COACH_ANSWER_PAYLOAD_INVALID]",
        "AI 教练提交内容不符合要求。",
        422,
    )
