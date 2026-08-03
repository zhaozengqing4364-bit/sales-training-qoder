"""Typed, safe failure taxonomy for the AI platform."""

from __future__ import annotations

from ai_platform.contracts import AIErrorClassification


class AIPlatformError(Exception):
    def __init__(
        self,
        *,
        code: str,
        classification: AIErrorClassification,
        message: str,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.classification = classification
        self.safe_message = message
        self.retryable = retryable


class PromptRevisionNotPublishedError(AIPlatformError):
    def __init__(self) -> None:
        super().__init__(
            code="AI_PROMPT_REVISION_NOT_PUBLISHED",
            classification=AIErrorClassification.PROMPT_REVISION_NOT_PUBLISHED,
            message="指定的提示词修订版不存在或尚未发布。",
        )


class PromptRevisionIntegrityError(AIPlatformError):
    def __init__(self) -> None:
        super().__init__(
            code="AI_PROMPT_REVISION_INTEGRITY_FAILED",
            classification=AIErrorClassification.PROMPT_CONTRACT_MISMATCH,
            message="已发布提示词修订版完整性校验失败。",
        )


class ModelRouteNotPublishedError(AIPlatformError):
    def __init__(self) -> None:
        super().__init__(
            code="AI_MODEL_ROUTE_NOT_PUBLISHED",
            classification=AIErrorClassification.MODEL_ROUTE_NOT_PUBLISHED,
            message="指定的模型路由修订版不存在或尚未发布。",
        )


class ModelRouteIntegrityError(AIPlatformError):
    def __init__(self) -> None:
        super().__init__(
            code="AI_MODEL_ROUTE_INTEGRITY_FAILED",
            classification=AIErrorClassification.MODEL_ROUTE_NOT_PUBLISHED,
            message="已发布模型路由修订版完整性校验失败。",
        )


class PromptContractMismatchError(AIPlatformError):
    def __init__(self) -> None:
        super().__init__(
            code="AI_PROMPT_CONTRACT_MISMATCH",
            classification=AIErrorClassification.PROMPT_CONTRACT_MISMATCH,
            message="提示词契约与预览时的已发布版本不一致。",
        )


class EmptyProviderResponseError(AIPlatformError):
    def __init__(self) -> None:
        super().__init__(
            code="AI_PROVIDER_EMPTY_RESPONSE",
            classification=AIErrorClassification.EMPTY_RESPONSE,
            message="模型返回了空结果。",
            retryable=True,
        )


class ProviderResponseInvalidError(AIPlatformError):
    def __init__(self) -> None:
        super().__init__(
            code="AI_PROVIDER_RESPONSE_INVALID",
            classification=AIErrorClassification.OUTPUT_SCHEMA_INVALID,
            message="模型返回的结构化结果无效。",
            retryable=True,
        )


class CircuitOpenError(AIPlatformError):
    def __init__(self) -> None:
        super().__init__(
            code="AI_PROVIDER_CIRCUIT_OPEN",
            classification=AIErrorClassification.CIRCUIT_OPEN,
            message="模型服务熔断保护已开启，请稍后重试。",
            retryable=True,
        )


class ProviderTimeoutError(AIPlatformError):
    def __init__(self) -> None:
        super().__init__(
            code="AI_PROVIDER_TIMEOUT",
            classification=AIErrorClassification.TIMEOUT,
            message="模型服务响应超时。",
            retryable=True,
        )


class ProviderRateLimitError(AIPlatformError):
    def __init__(self) -> None:
        super().__init__(
            code="AI_PROVIDER_RATE_LIMITED",
            classification=AIErrorClassification.RATE_LIMITED,
            message="模型服务当前请求过多，请稍后重试。",
            retryable=True,
        )


class ProviderUnavailableError(AIPlatformError):
    def __init__(self, *, status_code: int = 503) -> None:
        super().__init__(
            code=f"AI_PROVIDER_HTTP_{status_code}",
            classification=AIErrorClassification.PROVIDER_UNAVAILABLE,
            message="模型服务暂时不可用。",
            retryable=True,
        )


class ProviderCancelledError(AIPlatformError):
    def __init__(self) -> None:
        super().__init__(
            code="AI_PROVIDER_CANCELLED",
            classification=AIErrorClassification.CANCELLED,
            message="模型调用已取消。",
            retryable=False,
        )


class FallbackNotCalibratedError(AIPlatformError):
    def __init__(self) -> None:
        super().__init__(
            code="AI_FALLBACK_NOT_CALIBRATED",
            classification=AIErrorClassification.POLICY_NOT_CALIBRATED,
            message="备用模型尚未通过正式评分校准。",
        )


class PrimaryRouteNotCalibratedError(AIPlatformError):
    def __init__(self) -> None:
        super().__init__(
            code="AI_PRIMARY_ROUTE_NOT_CALIBRATED",
            classification=AIErrorClassification.POLICY_NOT_CALIBRATED,
            message="主模型尚未通过正式评分校准。",
        )


class DataClassificationNotAllowedError(AIPlatformError):
    def __init__(self) -> None:
        super().__init__(
            code="AI_DATA_CLASSIFICATION_NOT_ALLOWED",
            classification=AIErrorClassification.DATA_CLASSIFICATION_NOT_ALLOWED,
            message="该模型路由未获准处理当前数据分级。",
        )


class ProviderWorkloadMismatchError(AIPlatformError):
    def __init__(self) -> None:
        super().__init__(
            code="AI_PROVIDER_WORKLOAD_MISMATCH",
            classification=AIErrorClassification.MODEL_ROUTE_NOT_PUBLISHED,
            message="Provider adapter 与受治理 workload 类型不匹配。",
        )


class ProviderUsageCurrencyMismatchError(AIPlatformError):
    def __init__(self) -> None:
        super().__init__(
            code="AI_PROVIDER_USAGE_CURRENCY_MISMATCH",
            classification=AIErrorClassification.UNKNOWN,
            message="Provider 返回的用量币种与模型路由预算币种不一致。",
        )
