"""
Admin API for Model Configuration Management

CRUD endpoints for managing AI model configurations.
Requires admin authentication.

References:
- Requirements: R2 (CRUD API)
- Design: model-config-management/design.md
"""

import asyncio
import time
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import and_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from common.ai.config_manager import get_config_manager
from common.ai.encryption import decrypt_api_key, encrypt_api_key, mask_api_key
from common.ai.endpoint_policy import (
    EndpointPolicyError,
    validate_provider_base_url,
    validate_redirect_location,
)
from common.ai.models import ModelConfig, ModelProvider, ModelType
from common.ai.schemas import (
    CreateModelConfigRequest,
    ModelConfigCreateResponse,
    ModelConfigErrorResponse,
    ModelConfigListItem,
    ModelConfigListResponse,
    ModelConfigResponse,
    ModelConfigSuccessResponse,
    TestConfigResponse,
    TestConfigSuccessResponse,
    TestModelConfigRequest,
    UpdateModelConfigRequest,
)
from common.api.server_error import build_server_error
from common.auth.service import get_current_admin_user
from common.db.models import User
from common.db.session import get_db
from common.monitoring.logger import get_logger, get_trace_id

logger = get_logger(__name__)

router = APIRouter(
    prefix="/model-configs",
    tags=["Model Configs"],
    dependencies=[Depends(get_current_admin_user)],
)


SUPPORTED_PROVIDERS_BY_TYPE: dict[ModelType, set[ModelProvider]] = {
    ModelType.LLM: {
        ModelProvider.OPENAI,
        ModelProvider.AZURE,
        ModelProvider.ALIBABA,
        ModelProvider.ANTHROPIC,
    },
    ModelType.EMBEDDING: {
        ModelProvider.OPENAI,
        ModelProvider.AZURE,
    },
    ModelType.ASR: {
        ModelProvider.ALIBABA,
        ModelProvider.LOCAL,
        ModelProvider.LOCAL_STREAMING,
    },
    ModelType.TTS: {
        ModelProvider.ALIBABA,
        ModelProvider.LOCAL,
    },
}


def _is_provider_supported(model_type: ModelType, provider: ModelProvider) -> bool:
    return provider in SUPPORTED_PROVIDERS_BY_TYPE.get(model_type, set())


def _requires_api_key(model_type: ModelType, provider: ModelProvider) -> bool:
    if model_type == ModelType.ASR and provider in {
        ModelProvider.LOCAL,
        ModelProvider.LOCAL_STREAMING,
    }:
        return False
    if model_type == ModelType.TTS and provider == ModelProvider.LOCAL:
        return False
    return True


def _requires_base_url(model_type: ModelType, provider: ModelProvider) -> bool:
    if model_type == ModelType.TTS:
        return False
    if model_type == ModelType.ASR and provider in {
        ModelProvider.LOCAL,
        ModelProvider.LOCAL_STREAMING,
    }:
        return False
    return True


def _error_response(
    response: ModelConfigErrorResponse,
    status_code: int = 400,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=response.model_dump(mode="json", exclude_none=True),
    )


def _validate_config_fields(
    model_type: ModelType,
    provider: ModelProvider,
    base_url: str,
    api_key: str,
) -> ModelConfigErrorResponse | None:
    if not _is_provider_supported(model_type, provider):
        return ModelConfigErrorResponse(
            error=f"Provider '{provider.value}' is not supported for model type '{model_type.value}'",
            error_code="[MODEL_CONFIG_PROVIDER_NOT_SUPPORTED]",
            trace_id=get_trace_id(),
        )

    if _requires_base_url(model_type, provider) and not base_url.strip():
        return ModelConfigErrorResponse(
            error="Base URL is required for this provider",
            error_code="[MODEL_CONFIG_BASE_URL_REQUIRED]",
            trace_id=get_trace_id(),
        )

    if _requires_api_key(model_type, provider) and not api_key.strip():
        return ModelConfigErrorResponse(
            error="API key is required for this provider",
            error_code="[MODEL_CONFIG_API_KEY_REQUIRED]",
            trace_id=get_trace_id(),
        )

    if base_url.strip():
        try:
            validate_provider_base_url(provider, base_url, resolve_dns=False)
        except EndpointPolicyError as exc:
            return ModelConfigErrorResponse(
                error=str(exc),
                error_code="[MODEL_CONFIG_ENDPOINT_POLICY_VIOLATION]",
                trace_id=get_trace_id(),
            )

    return None


def _normalized_provider_base_url(
    model_type: ModelType,
    provider: ModelProvider,
    base_url: str,
) -> str:
    if not base_url.strip():
        return base_url
    return validate_provider_base_url(
        provider,
        base_url,
        resolve_dns=False,
    ).base_url


async def _find_replacement_default(
    db: AsyncSession,
    model_type: str,
    exclude_id: str,
) -> ModelConfig | None:
    stmt = (
        select(ModelConfig)
        .where(
            and_(
                ModelConfig.model_type == model_type,
                ModelConfig.id != exclude_id,
                ModelConfig.is_active.is_(True),
            )
        )
        .order_by(ModelConfig.is_default.desc(), ModelConfig.updated_at.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def _refresh_runtime_services() -> None:
    """Refresh cache and hot-reload singleton services after config changes."""
    await get_config_manager().refresh_cache()

    try:
        from common.ai.llm_service import reload_llm_service

        await reload_llm_service()
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Failed to reload LLM service: {exc}")

    try:
        from common.ai.embedding_service import reload_embedding_service

        await reload_embedding_service()
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Failed to reload Embedding service: {exc}")

    try:
        from common.audio.asr_service import reload_asr_service

        await reload_asr_service()
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Failed to reload ASR service: {exc}")

    try:
        from common.audio.tts_service import reload_tts_service

        await reload_tts_service()
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Failed to reload TTS service: {exc}")

    try:
        from common.audio.tts_factory import reset_tts_service_with_fallback

        reset_tts_service_with_fallback()
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Failed to reset TTS fallback service: {exc}")


def _config_to_response(
    config: ModelConfig, api_key_plain: str | None = None
) -> ModelConfigResponse:
    """Convert ModelConfig to response with masked API key"""
    if api_key_plain is not None:
        masked_key = mask_api_key(api_key_plain) if api_key_plain else "未设置"
    else:
        masked_key = "****" if config.api_key_encrypted else "未设置"

    return ModelConfigResponse(
        id=config.id,
        name=config.name,
        model_type=config.model_type,
        provider=config.provider,
        base_url=config.base_url,
        api_key_masked=masked_key,
        model_name=config.model_name,
        extra_config=config.extra_config or {},
        is_default=config.is_default,
        is_active=config.is_active,
        last_tested_at=config.last_tested_at,
        last_test_status=config.last_test_status,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


@router.post("", response_model=ModelConfigSuccessResponse, status_code=201)
async def create_model_config(
    request: CreateModelConfigRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Create a new model configuration.

    - Encrypts API key before storage
    - If is_default=True, clears other defaults for this type
    """
    try:
        validation_error = _validate_config_fields(
            model_type=request.model_type,
            provider=request.provider,
            base_url=request.base_url,
            api_key=request.api_key,
        )
        if validation_error:
            return _error_response(validation_error)

        # Check for duplicate
        stmt = select(ModelConfig).where(
            and_(
                ModelConfig.model_type == request.model_type.value,
                ModelConfig.provider == request.provider.value,
                ModelConfig.model_name == request.model_name,
            )
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            return ModelConfigErrorResponse(
                error="Configuration already exists",
                error_code="[MODEL_CONFIG_DUPLICATE]",
                trace_id=get_trace_id(),
            )

        api_key_encrypted = ""
        if request.api_key.strip():
            encrypt_result = encrypt_api_key(request.api_key)
            if not encrypt_result.is_success:
                return ModelConfigErrorResponse(
                    error="Failed to encrypt API key",
                    error_code="[ENCRYPTION_ERROR]",
                    trace_id=get_trace_id(),
                )
            api_key_encrypted = encrypt_result.value

        # If setting as default, clear other defaults
        if request.is_default:
            await _clear_defaults(db, request.model_type)

        # Create config
        config = ModelConfig(
            id=str(uuid.uuid4()),
            name=request.name,
            model_type=request.model_type.value,
            provider=request.provider.value,
            base_url=_normalized_provider_base_url(
                request.model_type, request.provider, request.base_url
            ),
            api_key_encrypted=api_key_encrypted,
            model_name=request.model_name,
            extra_config=request.extra_config,
            is_default=request.is_default,
            is_active=True,
        )

        db.add(config)
        await db.commit()
        await db.refresh(config)

        await _refresh_runtime_services()

        logger.info(
            "Model config created",
            admin_user_id=str(current_user.user_id),
            config_id=config.id,
            model_type=config.model_type,
            provider=config.provider,
            is_default=config.is_default,
        )

        return ModelConfigSuccessResponse(
            data=ModelConfigCreateResponse(
                id=config.id,
                name=config.name,
                model_type=config.model_type,
                provider=config.provider,
                model_name=config.model_name,
                is_default=config.is_default,
                created_at=config.created_at,
            ),
            trace_id=get_trace_id(),
        )

    except SQLAlchemyError as e:
        logger.error(f"Failed to create model config: {e}")
        await db.rollback()
        return ModelConfigErrorResponse(
            error=str(e),
            error_code="[MODEL_CONFIG_CREATE_FAILED]",
            trace_id=get_trace_id(),
        )


@router.get("", response_model=ModelConfigSuccessResponse)
async def list_model_configs(
    model_type: ModelType | None = Query(None, description="Filter by model type"),
    db: AsyncSession = Depends(get_db),
):
    """
    List all model configurations, grouped by type.

    - API keys are masked in response
    - Can filter by model_type
    """
    try:
        stmt = select(ModelConfig)
        if model_type:
            stmt = stmt.where(ModelConfig.model_type == model_type.value)
        stmt = stmt.order_by(ModelConfig.model_type, ModelConfig.is_default.desc())

        result = await db.execute(stmt)
        configs = result.scalars().all()

        # Group by type
        grouped = ModelConfigListResponse(
            llm=[],
            embedding=[],
            asr=[],
            tts=[],
            total=len(configs),
        )

        for config in configs:
            item = ModelConfigListItem(
                id=config.id,
                name=config.name,
                model_type=config.model_type,
                provider=config.provider,
                model_name=config.model_name,
                is_default=config.is_default,
                is_active=config.is_active,
                last_test_status=config.last_test_status,
            )

            if config.model_type == "llm":
                grouped.llm.append(item)
            elif config.model_type == "embedding":
                grouped.embedding.append(item)
            elif config.model_type == "asr":
                grouped.asr.append(item)
            elif config.model_type == "tts":
                grouped.tts.append(item)

        return ModelConfigSuccessResponse(data=grouped, trace_id=get_trace_id())

    except SQLAlchemyError as e:
        logger.error(f"Failed to list model configs: {e}")
        return ModelConfigErrorResponse(
            error=str(e),
            error_code="[MODEL_CONFIG_LIST_FAILED]",
            trace_id=get_trace_id(),
        )


@router.get("/{config_id}", response_model=ModelConfigSuccessResponse)
async def get_model_config(
    config_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a single model configuration by ID.
    """
    try:
        stmt = select(ModelConfig).where(ModelConfig.id == config_id)
        result = await db.execute(stmt)
        config = result.scalar_one_or_none()

        if not config:
            return ModelConfigErrorResponse(
                error="Configuration not found",
                error_code="[MODEL_CONFIG_NOT_FOUND]",
                trace_id=get_trace_id(),
            )

        api_key_plain: str | None = None
        if config.api_key_encrypted:
            decrypt_result = decrypt_api_key(config.api_key_encrypted)
            if decrypt_result.is_success:
                api_key_plain = decrypt_result.value

        return ModelConfigSuccessResponse(
            data=_config_to_response(config, api_key_plain), trace_id=get_trace_id()
        )

    except SQLAlchemyError as e:
        logger.error(f"Failed to get model config: {e}")
        return ModelConfigErrorResponse(
            error=str(e),
            error_code="[MODEL_CONFIG_GET_FAILED]",
            trace_id=get_trace_id(),
        )


@router.api_route(
    "/{config_id}", methods=["PUT", "PATCH"], response_model=ModelConfigSuccessResponse
)
async def update_model_config(
    config_id: str,
    request: UpdateModelConfigRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Update a model configuration (partial update).

    - Only provided fields are updated
    - If updating API key, it will be re-encrypted
    """
    try:
        stmt = select(ModelConfig).where(ModelConfig.id == config_id)
        result = await db.execute(stmt)
        config = result.scalar_one_or_none()

        if not config:
            return ModelConfigErrorResponse(
                error="Configuration not found",
                error_code="[MODEL_CONFIG_NOT_FOUND]",
                trace_id=get_trace_id(),
            )

        provider = ModelProvider(config.provider)
        model_type = ModelType(config.model_type)

        if request.base_url is not None:
            try:
                config.base_url = _normalized_provider_base_url(
                    model_type, provider, request.base_url
                )
            except EndpointPolicyError as exc:
                return _error_response(
                    ModelConfigErrorResponse(
                        error=str(exc),
                        error_code="[MODEL_CONFIG_ENDPOINT_POLICY_VIOLATION]",
                        trace_id=get_trace_id(),
                    )
                )

        # Update fields
        if request.name is not None:
            config.name = request.name
        if request.model_name is not None:
            config.model_name = request.model_name
        if request.extra_config is not None:
            config.extra_config = request.extra_config
        if request.is_active is not None:
            config.is_active = request.is_active

        # Handle API key update
        if request.api_key is not None:
            if request.api_key.strip():
                encrypt_result = encrypt_api_key(request.api_key)
                if not encrypt_result.is_success:
                    return ModelConfigErrorResponse(
                        error="Failed to encrypt API key",
                        error_code="[ENCRYPTION_ERROR]",
                        trace_id=get_trace_id(),
                    )
                config.api_key_encrypted = encrypt_result.value
            elif _requires_api_key(model_type, provider):
                return ModelConfigErrorResponse(
                    error="API key is required for this provider",
                    error_code="[MODEL_CONFIG_API_KEY_REQUIRED]",
                    trace_id=get_trace_id(),
                )
            else:
                config.api_key_encrypted = ""

        # Handle default flag
        if request.is_default is not None and request.is_default:
            await _clear_defaults(db, model_type)
            config.is_default = True
        elif config.is_default and (
            request.is_default is False or request.is_active is False
        ):
            replacement = await _find_replacement_default(
                db, config.model_type, config.id
            )
            if not replacement:
                return ModelConfigErrorResponse(
                    error="Cannot remove the only active default configuration for this type",
                    error_code="[CANNOT_UNSET_DEFAULT]",
                    trace_id=get_trace_id(),
                )
            replacement.is_default = True
            config.is_default = False

        config.updated_at = datetime.now(UTC)

        await db.commit()
        await db.refresh(config)

        await _refresh_runtime_services()

        logger.info(
            "Model config updated",
            admin_user_id=str(current_user.user_id),
            config_id=config.id,
            model_type=config.model_type,
            provider=config.provider,
            is_default=config.is_default,
            is_active=config.is_active,
        )

        return ModelConfigSuccessResponse(
            data=_config_to_response(config),
            trace_id=get_trace_id(),
        )

    except SQLAlchemyError as e:
        logger.error(f"Failed to update model config: {e}")
        await db.rollback()
        return ModelConfigErrorResponse(
            error=str(e),
            error_code="[MODEL_CONFIG_UPDATE_FAILED]",
            trace_id=get_trace_id(),
        )


@router.delete("/{config_id}", response_model=ModelConfigSuccessResponse)
async def delete_model_config(
    config_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Delete a model configuration.

    - Cannot delete if it's the only default for its type
    """
    try:
        stmt = select(ModelConfig).where(ModelConfig.id == config_id)
        result = await db.execute(stmt)
        config = result.scalar_one_or_none()

        if not config:
            return ModelConfigErrorResponse(
                error="Configuration not found",
                error_code="[MODEL_CONFIG_NOT_FOUND]",
                trace_id=get_trace_id(),
            )

        replacement_config: ModelConfig | None = None

        # Check if it's the only default
        if config.is_default:
            replacement_config = await _find_replacement_default(
                db, config.model_type, config.id
            )
            if not replacement_config:
                return ModelConfigErrorResponse(
                    error="Cannot delete the only active configuration for this type",
                    error_code="[CANNOT_DELETE_DEFAULT]",
                    trace_id=get_trace_id(),
                )

            replacement_config.is_default = True

        await db.delete(config)
        await db.commit()

        await _refresh_runtime_services()

        logger.info(
            "Model config deleted",
            admin_user_id=str(current_user.user_id),
            deleted_config_id=config.id,
            model_type=config.model_type,
            replacement_default_id=replacement_config.id
            if replacement_config
            else None,
        )

        return ModelConfigSuccessResponse(data=None, trace_id=get_trace_id())

    except SQLAlchemyError as e:
        logger.error(f"Failed to delete model config: {e}")
        await db.rollback()
        return ModelConfigErrorResponse(
            error=str(e),
            error_code="[MODEL_CONFIG_DELETE_FAILED]",
            trace_id=get_trace_id(),
        )


async def _clear_defaults(db: AsyncSession, model_type: ModelType) -> None:
    """Clear is_default flag for all configs of a type"""
    stmt = select(ModelConfig).where(
        and_(
            ModelConfig.model_type == model_type.value,
            ModelConfig.is_default.is_(True),
        )
    )
    result = await db.execute(stmt)
    configs = result.scalars().all()

    for config in configs:
        config.is_default = False


# ========== Test Connection Endpoint ==========


@router.post("/{config_id}/test", response_model=TestConfigSuccessResponse)
async def test_model_config(
    config_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Test a model configuration by making a simple API call.

    - LLM: Send a simple completion request
    - Embedding: Embed a test string
    - ASR/TTS: Validate credentials
    - Timeout: 10 seconds
    """
    try:
        stmt = select(ModelConfig).where(ModelConfig.id == config_id)
        result = await db.execute(stmt)
        config = result.scalar_one_or_none()

        if not config:
            return ModelConfigErrorResponse(
                error="Configuration not found",
                error_code="[MODEL_CONFIG_NOT_FOUND]",
                trace_id=get_trace_id(),
            )

        api_key = ""
        if config.api_key_encrypted:
            key_result = decrypt_api_key(config.api_key_encrypted)
            if not key_result.is_success:
                return TestConfigSuccessResponse(
                    data=TestConfigResponse(
                        success=False,
                        message="Failed to decrypt API key",
                        latency_ms=0,
                    )
                )
            api_key = key_result.value or ""

        model_type = ModelType(config.model_type)

        # Run test with timeout
        start_time = time.time()
        try:
            test_result = await asyncio.wait_for(
                _run_model_test(model_type, config, api_key), timeout=10.0
            )
        except TimeoutError:
            test_result = TestConfigResponse(
                success=False,
                message="Test timed out (>10s)",
                latency_ms=10000,
            )

        latency_ms = int((time.time() - start_time) * 1000)
        test_result.latency_ms = latency_ms

        # Update test status in database
        config.last_tested_at = datetime.now(UTC)
        config.last_test_status = "success" if test_result.success else "failed"
        await db.commit()

        logger.info(
            "Model config tested",
            admin_user_id=str(current_user.user_id),
            config_id=config.id,
            status="success" if test_result.success else "failed",
            latency_ms=latency_ms,
        )

        return TestConfigSuccessResponse(data=test_result)

    except (
        ConnectionError,
        TimeoutError,
        ValueError,
        RuntimeError,
        OSError,
        SQLAlchemyError,
    ) as e:
        logger.error("Failed to test model config", error_type=type(e).__name__)
        return TestConfigSuccessResponse(
            data=TestConfigResponse(
                success=False,
                message=_safe_test_error_message(e),
                latency_ms=0,
            )
        )


@router.post("/test", response_model=TestConfigSuccessResponse)
async def test_model_config_inline(
    request: TestModelConfigRequest,
    current_user: User = Depends(get_current_admin_user),
):
    """
    Test a model configuration before saving (inline test).

    Useful for validating credentials before creating a config.
    """
    try:
        validation_error = _validate_config_fields(
            model_type=request.model_type,
            provider=request.provider,
            base_url=request.base_url,
            api_key=request.api_key,
        )
        if validation_error:
            return TestConfigSuccessResponse(
                data=TestConfigResponse(
                    success=False,
                    message=validation_error.error,
                    latency_ms=0,
                )
            )

        # Create a temporary config object
        temp_config = ModelConfig(
            id="temp",
            name="temp",
            model_type=request.model_type.value,
            provider=request.provider.value,
            base_url=_normalized_provider_base_url(
                request.model_type, request.provider, request.base_url
            ),
            api_key_encrypted="",  # Not used
            model_name=request.model_name,
            extra_config=request.extra_config,
        )

        start_time = time.time()
        try:
            test_result = await asyncio.wait_for(
                _run_model_test(request.model_type, temp_config, request.api_key),
                timeout=10.0,
            )
        except TimeoutError:
            test_result = TestConfigResponse(
                success=False,
                message="Test timed out (>10s)",
                latency_ms=10000,
            )

        latency_ms = int((time.time() - start_time) * 1000)
        test_result.latency_ms = latency_ms

        logger.info(
            "Inline model config tested",
            admin_user_id=str(current_user.user_id),
            model_type=request.model_type.value,
            provider=request.provider.value,
            status="success" if test_result.success else "failed",
            latency_ms=latency_ms,
        )

        return TestConfigSuccessResponse(data=test_result)

    except (ConnectionError, TimeoutError, ValueError, RuntimeError, OSError) as e:
        logger.error("Failed to test model config inline", error_type=type(e).__name__)
        return TestConfigSuccessResponse(
            data=TestConfigResponse(
                success=False,
                message=_safe_test_error_message(e),
                latency_ms=0,
            )
        )


def _safe_test_error_message(exc: Exception) -> str:
    if isinstance(exc, EndpointPolicyError):
        return str(exc)
    return (
        "Model configuration test failed before a safe provider response was received."
    )


async def _run_model_test(
    model_type: ModelType, config: ModelConfig, api_key: str
) -> TestConfigResponse:
    """
    Run the actual model test based on type.
    """
    if model_type == ModelType.LLM:
        return await _test_llm(config, api_key)
    elif model_type == ModelType.EMBEDDING:
        return await _test_embedding(config, api_key)
    elif model_type == ModelType.ASR:
        return await _test_asr(config, api_key)
    elif model_type == ModelType.TTS:
        return await _test_tts(config, api_key)
    else:
        return TestConfigResponse(
            success=False,
            message=f"Unknown model type: {model_type}",
        )


async def _test_llm(config: ModelConfig, api_key: str) -> TestConfigResponse:
    """Test LLM configuration with a simple completion"""
    try:
        import httpx

        endpoint = validate_provider_base_url(
            ModelProvider(config.provider), config.base_url, resolve_dns=True
        )

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        # Simple completion request
        payload = {
            "model": config.model_name,
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 5,
        }

        async with httpx.AsyncClient(
            timeout=endpoint.timeout_seconds, follow_redirects=False
        ) as client:
            response = await client.post(
                endpoint.child_url("chat/completions"),
                headers=headers,
                json=payload,
            )

        if response.is_redirect:
            try:
                validate_redirect_location(
                    ModelProvider(config.provider),
                    endpoint.base_url,
                    response.headers.get("location", ""),
                    resolve_dns=True,
                )
            except EndpointPolicyError:
                pass
            return TestConfigResponse(
                success=False,
                message="LLM API redirect blocked by endpoint policy",
                details={"status_code": response.status_code, "redirect_blocked": True},
            )

        if response.status_code == 200:
            return TestConfigResponse(
                success=True,
                message="LLM connection successful",
                details={"model": config.model_name},
            )
        else:
            return TestConfigResponse(
                success=False,
                message=f"LLM API error: {response.status_code}",
                details={
                    "status_code": response.status_code,
                    "response_redacted": True,
                },
            )

    except (ConnectionError, TimeoutError, ValueError, RuntimeError, OSError) as e:
        return TestConfigResponse(
            success=False,
            message=f"LLM test failed: {_safe_test_error_message(e)}",
        )


async def _test_embedding(config: ModelConfig, api_key: str) -> TestConfigResponse:
    """Test Embedding configuration"""
    try:
        import httpx

        endpoint = validate_provider_base_url(
            ModelProvider(config.provider), config.base_url, resolve_dns=True
        )

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": config.model_name,
            "input": "test",
        }

        async with httpx.AsyncClient(
            timeout=endpoint.timeout_seconds, follow_redirects=False
        ) as client:
            response = await client.post(
                endpoint.child_url("embeddings"),
                headers=headers,
                json=payload,
            )

        if response.is_redirect:
            try:
                validate_redirect_location(
                    ModelProvider(config.provider),
                    endpoint.base_url,
                    response.headers.get("location", ""),
                    resolve_dns=True,
                )
            except EndpointPolicyError:
                pass
            return TestConfigResponse(
                success=False,
                message="Embedding API redirect blocked by endpoint policy",
                details={"status_code": response.status_code, "redirect_blocked": True},
            )

        if response.status_code == 200:
            data = response.json()
            embedding_dim = len(data.get("data", [{}])[0].get("embedding", []))
            return TestConfigResponse(
                success=True,
                message="Embedding connection successful",
                details={"model": config.model_name, "dimensions": embedding_dim},
            )
        else:
            return TestConfigResponse(
                success=False,
                message=f"Embedding API error: {response.status_code}",
                details={
                    "status_code": response.status_code,
                    "response_redacted": True,
                },
            )

    except (ConnectionError, TimeoutError, ValueError, RuntimeError, OSError) as e:
        return TestConfigResponse(
            success=False,
            message=f"Embedding test failed: {_safe_test_error_message(e)}",
        )


async def _test_asr(config: ModelConfig, api_key: str) -> TestConfigResponse:
    """Test ASR configuration (credential validation)"""
    try:
        provider = ModelProvider(config.provider)

        if provider == ModelProvider.ALIBABA:
            if not api_key:
                return TestConfigResponse(
                    success=False,
                    message="ASR API key is required for Alibaba provider",
                )
            # For Alibaba ASR, we just validate the token can be generated
            # Full test would require audio data
            return TestConfigResponse(
                success=True,
                message="ASR credentials format valid (full test requires audio)",
                details={"provider": "alibaba", "app_key": config.model_name},
            )
        if provider in {ModelProvider.LOCAL, ModelProvider.LOCAL_STREAMING}:
            return TestConfigResponse(
                success=True,
                message="Local ASR configuration valid",
                details={"provider": provider.value, "model": config.model_name},
            )

        else:
            return TestConfigResponse(
                success=False,
                message=f"ASR provider not supported: {provider}",
            )

    except (ConnectionError, TimeoutError, ValueError, RuntimeError, OSError) as e:
        return TestConfigResponse(
            success=False,
            message=f"ASR test failed: {str(e)}",
        )


async def _test_tts(config: ModelConfig, api_key: str) -> TestConfigResponse:
    """Test TTS configuration"""
    try:
        provider = ModelProvider(config.provider)

        if provider == ModelProvider.LOCAL:
            # Edge TTS doesn't need API key validation
            return TestConfigResponse(
                success=True,
                message="TTS configuration valid (Edge TTS)",
                details={"voice": config.model_name},
            )
        elif provider == ModelProvider.ALIBABA:
            if not api_key:
                return TestConfigResponse(
                    success=False,
                    message="TTS API key is required for Alibaba provider",
                )
            return TestConfigResponse(
                success=True,
                message="TTS configuration valid (Alibaba DashScope)",
                details={
                    "provider": provider.value,
                    "voice": config.model_name,
                },
            )
        else:
            return TestConfigResponse(
                success=False,
                message=f"TTS provider not supported: {provider}",
            )

    except (ConnectionError, TimeoutError, ValueError, RuntimeError, OSError) as e:
        return TestConfigResponse(
            success=False,
            message=f"TTS test failed: {str(e)}",
        )


# ========== TTS Preview Endpoint ==========


@router.post("/tts/preview")
async def preview_tts(
    text: str = Query("你好，这是一段语音试听测试。", description="Text to synthesize"),
    voice: str = Query("zh-CN-XiaoxiaoNeural", description="Voice name"),
    rate: str = Query("+0%", description="Speech rate"),
    volume: str = Query("+0%", description="Volume"),
    pitch: str = Query("+0Hz", description="Pitch"),
):
    """
    Preview TTS with specified parameters.

    Returns audio stream for playback.

    Note: This endpoint returns raw audio stream (not JSON) for direct playback.
    Error responses still follow the standard format.
    """
    import io

    import edge_tts
    from fastapi.responses import StreamingResponse

    try:
        # Limit text length for preview
        if len(text) > 200:
            text = text[:200]

        communicate = edge_tts.Communicate(
            text,
            voice,
            rate=rate,
            volume=volume,
            pitch=pitch,
        )

        # Collect audio chunks
        audio_buffer = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_buffer.write(chunk["data"])

        audio_buffer.seek(0)

        return StreamingResponse(
            audio_buffer,
            media_type="audio/mpeg",
            headers={"Content-Disposition": "inline; filename=preview.mp3"},
        )

    except (ConnectionError, TimeoutError, ValueError, RuntimeError, OSError) as e:
        return build_server_error(
            "[TTS_PREVIEW_FAILED]",
            message=f"TTS preview failed: {str(e)}",
            exc=e,
        )
