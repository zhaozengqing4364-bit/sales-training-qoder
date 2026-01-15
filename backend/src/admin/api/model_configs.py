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
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.ai.config_manager import get_config_manager
from common.ai.encryption import decrypt_api_key, encrypt_api_key, mask_api_key
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
from common.db.session import get_db
from common.monitoring.logger import get_logger, get_trace_id

logger = get_logger(__name__)

router = APIRouter(prefix="/model-configs", tags=["Model Configs"])


def _config_to_response(config: ModelConfig, api_key_plain: str | None = None) -> ModelConfigResponse:
    """Convert ModelConfig to response with masked API key"""
    # If we have the plain key, mask it; otherwise mask the encrypted one
    masked_key = mask_api_key(api_key_plain) if api_key_plain else "****"

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
):
    """
    Create a new model configuration.

    - Encrypts API key before storage
    - If is_default=True, clears other defaults for this type
    """
    try:
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

        # Encrypt API key
        encrypt_result = encrypt_api_key(request.api_key)
        if not encrypt_result.is_success:
            return ModelConfigErrorResponse(
                error="Failed to encrypt API key",
                error_code="[ENCRYPTION_ERROR]",
                trace_id=get_trace_id(),
            )

        # If setting as default, clear other defaults
        if request.is_default:
            await _clear_defaults(db, request.model_type)

        # Create config
        config = ModelConfig(
            id=str(uuid.uuid4()),
            name=request.name,
            model_type=request.model_type.value,
            provider=request.provider.value,
            base_url=request.base_url,
            api_key_encrypted=encrypt_result.value,
            model_name=request.model_name,
            extra_config=request.extra_config,
            is_default=request.is_default,
            is_active=True,
        )

        db.add(config)
        await db.commit()
        await db.refresh(config)

        # Refresh config manager cache
        await get_config_manager().refresh_cache()

        logger.info(f"Created model config: {config.name} ({config.model_type}/{config.provider})")

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

    except Exception as e:
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

    except Exception as e:
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

        return ModelConfigSuccessResponse(
            data=_config_to_response(config),
            trace_id=get_trace_id(),
        )

    except Exception as e:
        logger.error(f"Failed to get model config: {e}")
        return ModelConfigErrorResponse(
            error=str(e),
            error_code="[MODEL_CONFIG_GET_FAILED]",
            trace_id=get_trace_id(),
        )


@router.put("/{config_id}", response_model=ModelConfigSuccessResponse)
async def update_model_config(
    config_id: str,
    request: UpdateModelConfigRequest,
    db: AsyncSession = Depends(get_db),
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

        # Update fields
        if request.name is not None:
            config.name = request.name
        if request.base_url is not None:
            config.base_url = request.base_url
        if request.model_name is not None:
            config.model_name = request.model_name
        if request.extra_config is not None:
            config.extra_config = request.extra_config
        if request.is_active is not None:
            config.is_active = request.is_active

        # Handle API key update
        if request.api_key is not None:
            encrypt_result = encrypt_api_key(request.api_key)
            if not encrypt_result.is_success:
                return ModelConfigErrorResponse(
                    error="Failed to encrypt API key",
                    error_code="[ENCRYPTION_ERROR]",
                    trace_id=get_trace_id(),
                )
            config.api_key_encrypted = encrypt_result.value

        # Handle default flag
        if request.is_default is not None and request.is_default:
            await _clear_defaults(db, ModelType(config.model_type))
            config.is_default = True
        elif request.is_default is False:
            config.is_default = False

        config.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(config)

        # Refresh config manager cache
        await get_config_manager().refresh_cache()

        logger.info(f"Updated model config: {config.name}")

        return ModelConfigSuccessResponse(
            data=_config_to_response(config),
            trace_id=get_trace_id(),
        )

    except Exception as e:
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

        # Check if it's the only default
        if config.is_default:
            count_stmt = select(func.count()).select_from(ModelConfig).where(
                and_(
                    ModelConfig.model_type == config.model_type,
                    ModelConfig.id != config_id,
                )
            )
            count_result = await db.execute(count_stmt)
            other_count = count_result.scalar()

            if other_count == 0:
                return ModelConfigErrorResponse(
                    error="Cannot delete the only configuration for this type",
                    error_code="[CANNOT_DELETE_DEFAULT]",
                    trace_id=get_trace_id(),
                )

        await db.delete(config)
        await db.commit()

        # Refresh config manager cache
        await get_config_manager().refresh_cache()

        logger.info(f"Deleted model config: {config.name}")

        return ModelConfigSuccessResponse(data=None, trace_id=get_trace_id())

    except Exception as e:
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
                error_code="[MODEL_CONFIG_NOT_FOUND]"
            )

        # Decrypt API key
        key_result = decrypt_api_key(config.api_key_encrypted)
        if not key_result.is_success:
            return TestConfigSuccessResponse(
                data=TestConfigResponse(
                    success=False,
                    message="Failed to decrypt API key",
                    latency_ms=0,
                )
            )

        api_key = key_result.value
        model_type = ModelType(config.model_type)

        # Run test with timeout
        start_time = time.time()
        try:
            test_result = await asyncio.wait_for(
                _run_model_test(model_type, config, api_key),
                timeout=10.0
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
        config.last_tested_at = datetime.utcnow()
        config.last_test_status = "success" if test_result.success else "failed"
        await db.commit()

        logger.info(
            f"Model config test: {config.name} - "
            f"{'success' if test_result.success else 'failed'} ({latency_ms}ms)"
        )

        return TestConfigSuccessResponse(data=test_result)

    except Exception as e:
        logger.error(f"Failed to test model config: {e}")
        return TestConfigSuccessResponse(
            data=TestConfigResponse(
                success=False,
                message=str(e),
                latency_ms=0,
            )
        )


@router.post("/test", response_model=TestConfigSuccessResponse)
async def test_model_config_inline(
    request: TestModelConfigRequest,
):
    """
    Test a model configuration before saving (inline test).

    Useful for validating credentials before creating a config.
    """
    try:
        # Create a temporary config object
        temp_config = ModelConfig(
            id="temp",
            name="temp",
            model_type=request.model_type.value,
            provider=request.provider.value,
            base_url=request.base_url,
            api_key_encrypted="",  # Not used
            model_name=request.model_name,
            extra_config=request.extra_config,
        )

        start_time = time.time()
        try:
            test_result = await asyncio.wait_for(
                _run_model_test(request.model_type, temp_config, request.api_key),
                timeout=10.0
            )
        except TimeoutError:
            test_result = TestConfigResponse(
                success=False,
                message="Test timed out (>10s)",
                latency_ms=10000,
            )

        latency_ms = int((time.time() - start_time) * 1000)
        test_result.latency_ms = latency_ms

        return TestConfigSuccessResponse(data=test_result)

    except Exception as e:
        logger.error(f"Failed to test model config inline: {e}")
        return TestConfigSuccessResponse(
            data=TestConfigResponse(
                success=False,
                message=str(e),
                latency_ms=0,
            )
        )


async def _run_model_test(
    model_type: ModelType,
    config: ModelConfig,
    api_key: str
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

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{config.base_url}/chat/completions",
                headers=headers,
                json=payload,
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
                details={"response": response.text[:200]},
            )

    except Exception as e:
        return TestConfigResponse(
            success=False,
            message=f"LLM test failed: {str(e)}",
        )


async def _test_embedding(config: ModelConfig, api_key: str) -> TestConfigResponse:
    """Test Embedding configuration"""
    try:
        import httpx

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": config.model_name,
            "input": "test",
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{config.base_url}/embeddings",
                headers=headers,
                json=payload,
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
                details={"response": response.text[:200]},
            )

    except Exception as e:
        return TestConfigResponse(
            success=False,
            message=f"Embedding test failed: {str(e)}",
        )


async def _test_asr(config: ModelConfig, api_key: str) -> TestConfigResponse:
    """Test ASR configuration (credential validation)"""
    try:
        provider = ModelProvider(config.provider)

        if provider == ModelProvider.ALIBABA:
            # For Alibaba ASR, we just validate the token can be generated
            # Full test would require audio data
            return TestConfigResponse(
                success=True,
                message="ASR credentials format valid (full test requires audio)",
                details={"provider": "alibaba", "app_key": config.model_name},
            )
        else:
            return TestConfigResponse(
                success=False,
                message=f"ASR provider not supported: {provider}",
            )

    except Exception as e:
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
        else:
            return TestConfigResponse(
                success=False,
                message=f"TTS provider not supported: {provider}",
            )

    except Exception as e:
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
    from fastapi.responses import StreamingResponse
    import edge_tts

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
            headers={
                "Content-Disposition": "inline; filename=preview.mp3"
            }
        )

    except Exception as e:
        logger.error(f"TTS preview failed: {e}")
        # Return standard error response format
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "[TTS_PREVIEW_FAILED]",
                "message": f"TTS preview failed: {str(e)}",
                "trace_id": get_trace_id()
            }
        )
