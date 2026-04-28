"""FastAPI lifespan wiring for the backend application."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from common.auth.api import get_auth_config_diagnostics
from common.auth.service import get_wecom_provider_diagnostics
from common.db.session import STARTUP_DB_AUTHORITY, init_db
from common.monitoring.logger import get_logger
from common.monitoring.otel import initialize_otel

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan events."""
    logger.info("Starting AI Practice System backend")
    initialize_otel(app)

    from common.auth.service import JWT_SECRET
    from common.config import settings

    env = settings.ENVIRONMENT
    if env != "development" and (not settings.SECRET_KEY or settings.SECRET_KEY == ""):
        raise RuntimeError(
            "SECRET_KEY must be set in production via environment variable"
        )
    if (
        env != "development"
        and JWT_SECRET == "your-super-secret-key-change-in-production-min-32-chars"
    ):
        raise RuntimeError(
            "JWT_SECRET must be set in production via environment variable"
        )

    logger.info(
        "Database authority map resolved for startup",
        startup_initializer=STARTUP_DB_AUTHORITY["startup_initializer"],
        schema_migration_entrypoint=STARTUP_DB_AUTHORITY["schema_migration_entrypoint"],
        legacy_schema_repair_entrypoint=STARTUP_DB_AUTHORITY[
            "legacy_schema_repair_entrypoint"
        ],
        auth_bootstrap_entrypoint=STARTUP_DB_AUTHORITY["auth_bootstrap_entrypoint"],
        startup_compatibility_guards=STARTUP_DB_AUTHORITY[
            "startup_compatibility_guards"
        ],
    )
    await init_db()

    auth_config = get_auth_config_diagnostics()
    wecom_config = get_wecom_provider_diagnostics()
    if env != "development":
        if not auth_config["user_overrides_valid"]:
            raise RuntimeError(
                "AUTH_USER_PASSWORDS_JSON is invalid in non-development environment"
            )
        if not auth_config["credentials_ready"]:
            raise RuntimeError(
                "Auth credentials are not configured. Set AUTH_SHARED_PASSWORD "
                "or AUTH_USER_PASSWORDS_JSON before startup."
            )
        if not wecom_config["configured"]:
            raise RuntimeError(
                "WeCom SSO is not configured. Set WECHAT_CORP_ID/WECHAT_SECRET/WECHAT_AGENT_ID "
                "(or WECOM_CORP_ID/WECOM_SECRET/WECOM_AGENT_ID) before startup."
            )

    if auth_config["credentials_ready"] and auth_config["user_overrides_valid"]:
        logger.info(
            "Auth credentials configured",
            shared_password=auth_config["shared_password_configured"],
            user_overrides=auth_config["user_override_count"],
        )
    elif auth_config["credentials_ready"] and not auth_config["user_overrides_valid"]:
        logger.warning(
            "Auth user overrides are invalid JSON; fallback to shared password only",
            shared_password=auth_config["shared_password_configured"],
        )
    else:
        logger.warning(
            "Auth credentials are not configured; login endpoint will return 503",
            shared_password=auth_config["shared_password_configured"],
            user_overrides=auth_config["user_override_count"],
        )

    if wecom_config["configured"]:
        logger.info(
            "WeCom SSO configured",
            corp_id_configured=wecom_config["corp_id_configured"],
            agent_id_configured=wecom_config["agent_id_configured"],
        )
    else:
        logger.warning(
            "WeCom SSO is not configured",
            corp_id_configured=wecom_config["corp_id_configured"],
            agent_id_configured=wecom_config["agent_id_configured"],
        )

    try:
        from common.ai.config_manager import initialize_config_manager

        await initialize_config_manager()
        logger.info("ConfigManager initialized")
    except (RuntimeError, ValueError, OSError) as e:
        logger.warning(f"ConfigManager initialization failed: {str(e)}")

    if settings.PRELOAD_SERVICES:
        logger.info("Preloading critical services (PRELOAD_SERVICES=true)")
        try:
            from common.audio.asr_service import get_asr_service

            get_asr_service()
            logger.info("Service preloading complete")
        except (RuntimeError, ValueError, OSError) as e:
            logger.warning(f"Service preloading failed: {str(e)}")

    from common.jobs.audio_archival import (
        init_audio_archival_scheduler,
        shutdown_audio_archival_scheduler,
    )
    from common.websocket.session_manager import (
        init_session_manager,
        shutdown_session_manager,
    )
    from common.websocket.session_state_service import (
        init_session_state_service,
        shutdown_session_state_service,
    )

    await init_session_manager()
    await init_session_state_service()
    await init_audio_archival_scheduler(
        enabled=settings.AUDIO_ARCHIVAL_SCHEDULER_ENABLED,
        interval_seconds=settings.AUDIO_ARCHIVAL_INTERVAL_SECONDS,
        batch_size=settings.AUDIO_ARCHIVAL_BATCH_SIZE,
    )

    yield

    await shutdown_audio_archival_scheduler()
    await shutdown_session_state_service()
    await shutdown_session_manager()
    logger.info("Shutting down AI Practice System backend")
