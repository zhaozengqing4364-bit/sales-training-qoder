"""
Application Configuration
Centralized configuration management for the AI Practice System
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    """Read a bounded integer env config with safe fallback."""
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, value))


def _env_choice(name: str, default: str, allowed: set[str]) -> str:
    """Read an allowlisted string env config with safe fallback."""
    value = os.getenv(name, default).strip().lower()
    return value if value in allowed else default


class Settings:
    """Application settings"""

    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"

    # API
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "Enterprise AI Intelligent Practice System"
    VERSION: str = "1.0.0"

    # CORS
    CORS_ORIGINS: list[str] = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3445,http://localhost:5173,http://localhost:3000,http://127.0.0.1:3445,http://127.0.0.1:5173,http://127.0.0.1:3000",
    ).split(",")

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "sqlite+aiosqlite:///./ai_practice.db"
    )

    # Redis (for production)
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    SESSION_STATE_REDIS_URL: str = os.getenv("SESSION_STATE_REDIS_URL", REDIS_URL)
    SESSION_STATE_KEY_PREFIX: str = os.getenv(
        "SESSION_STATE_KEY_PREFIX", "ws:session_state:"
    )
    SESSION_STATE_TTL_SECONDS: int = int(os.getenv("SESSION_STATE_TTL_SECONDS", "1800"))
    SESSION_STATE_CLEANUP_INTERVAL_SECONDS: int = int(
        os.getenv("SESSION_STATE_CLEANUP_INTERVAL_SECONDS", "300")
    )

    # JWT Authentication
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "43200")
    )  # 30 days

    # WeChat Integration
    WECHAT_CORP_ID: str = os.getenv("WECHAT_CORP_ID", "")
    WECHAT_AGENT_ID: str = os.getenv("WECHAT_AGENT_ID", "")
    WECHAT_SECRET: str = os.getenv("WECHAT_SECRET", "")

    # ASR Service (qwen3-asr-flash)
    ASR_API_KEY: str = os.getenv("ASR_API_KEY", "")
    ASR_API_URL: str = os.getenv(
        "ASR_API_URL", "wss://dashscope.aliyuncs.com/api-ws/v1/realtime"
    )
    ASR_USE_API: bool = os.getenv("ASR_USE_API", "true").lower() == "true"

    # TTS Service (edge-tts)
    TTS_VOICE: str = os.getenv("TTS_VOICE", "zh-CN-XiaoxiaoNeural")
    TTS_RATE: str = os.getenv("TTS_RATE", "+0%")

    # LLM Service (DeepSeek / Qwen)
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "deepseek-chat")
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.7"))
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "2000"))
    LLM_TIMEOUT_SECONDS: int = int(os.getenv("LLM_TIMEOUT_SECONDS", "10"))

    # ChromaDB
    CHROMA_PERSIST_DIRECTORY: str = os.getenv(
        "CHROMA_PERSIST_DIRECTORY", "./data/chroma"
    )
    CHROMA_COLLECTION_NAME: str = os.getenv("CHROMA_COLLECTION_NAME", "presentations")

    # File Storage
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./uploads")
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "100"))

    # Cost Control
    MAX_COST_PER_SESSION: float = float(os.getenv("MAX_COST_PER_SESSION", "1.0"))  # ¥1
    COST_WARNING_THRESHOLD: float = float(
        os.getenv("COST_WARNING_THRESHOLD", "0.8")
    )  # ¥0.8

    # Performance
    MAX_WEBSOCKET_CONNECTIONS: int = int(os.getenv("MAX_WEBSOCKET_CONNECTIONS", "50"))
    WEBSOCKET_MAX_MESSAGE_QUEUE_SIZE: int = _env_int(
        "WEBSOCKET_MAX_MESSAGE_QUEUE_SIZE",
        300,
        minimum=1,
        maximum=5000,
    )
    WEBSOCKET_BACKPRESSURE_POLICY: str = _env_choice(
        "WEBSOCKET_BACKPRESSURE_POLICY",
        "drop_newest",
        allowed={"drop_newest", "drop_oldest"},
    )
    ASR_STREAMING_TIMEOUT_MS: int = int(os.getenv("ASR_STREAMING_TIMEOUT_MS", "5000"))
    INTERRUPTION_DETECTION_TIMEOUT_MS: int = int(
        os.getenv("INTERRUPTION_DETECTION_TIMEOUT_MS", "100")
    )
    TTS_DEFAULT_SAMPLE_RATE_HZ: int = _env_int(
        "TTS_DEFAULT_SAMPLE_RATE_HZ",
        16000,
        minimum=8000,
        maximum=48000,
    )
    TTS_BYTES_PER_SAMPLE: int = _env_int(
        "TTS_BYTES_PER_SAMPLE",
        2,
        minimum=1,
        maximum=4,
    )
    TTS_CHANNELS: int = _env_int("TTS_CHANNELS", 1, minimum=1, maximum=2)
    PRESENTATION_FEEDBACK_SESSION_TTL_SECONDS: int = _env_int(
        "PRESENTATION_FEEDBACK_SESSION_TTL_SECONDS",
        86400,
        minimum=60,
        maximum=604800,
    )
    PRESENTATION_FEEDBACK_MAX_SESSIONS: int = _env_int(
        "PRESENTATION_FEEDBACK_MAX_SESSIONS",
        10000,
        minimum=100,
        maximum=100000,
    )
    CACHE_MEMORY_MAX_ENTRIES: int = _env_int(
        "CACHE_MEMORY_MAX_ENTRIES",
        10000,
        minimum=100,
        maximum=1000000,
    )
    SALES_BOT_SESSION_TTL_SECONDS: int = _env_int(
        "SALES_BOT_SESSION_TTL_SECONDS",
        3600,
        minimum=60,
        maximum=86400,
    )
    SALES_BOT_MAX_ACTIVE_SESSIONS: int = _env_int(
        "SALES_BOT_MAX_ACTIVE_SESSIONS",
        1000,
        minimum=1,
        maximum=100000,
    )

    # Service Preloading
    PRELOAD_SERVICES: bool = os.getenv("PRELOAD_SERVICES", "false").lower() == "true"

    # Audio archival scheduling. Disabled by default because the archival job moves
    # files and updates session rows; operators must opt in after storage paths are
    # configured for the deployment.
    AUDIO_ARCHIVAL_SCHEDULER_ENABLED: bool = (
        os.getenv("AUDIO_ARCHIVAL_SCHEDULER_ENABLED", "false").lower() == "true"
    )
    AUDIO_ARCHIVAL_INTERVAL_SECONDS: int = _env_int(
        "AUDIO_ARCHIVAL_INTERVAL_SECONDS",
        86400,
        minimum=300,
        maximum=604800,
    )
    AUDIO_ARCHIVAL_BATCH_SIZE: int = _env_int(
        "AUDIO_ARCHIVAL_BATCH_SIZE",
        100,
        minimum=1,
        maximum=10000,
    )

    # Monitoring
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    SENTRY_DSN: str = os.getenv("SENTRY_DSN", "")
    PROMETHEUS_PORT: int = int(os.getenv("PROMETHEUS_PORT", "9090"))

    # Feature Flags
    ENABLE_BROWSER_ASR_FALLBACK: bool = (
        os.getenv("ENABLE_BROWSER_ASR_FALLBACK", "true").lower() == "true"
    )
    ASR_BROWSER_FALLBACK_PROVIDER: str = os.getenv(
        "ASR_BROWSER_FALLBACK_PROVIDER",
        "browser_web_speech",
    )
    ASR_BROWSER_HANDOFF_MESSAGE: str = os.getenv(
        "ASR_BROWSER_HANDOFF_MESSAGE",
        "语音识别服务暂时不可用，请切换到浏览器语音识别或文本输入。",
    )
    ASR_BROWSER_HANDOFF_ACTION: str = os.getenv(
        "ASR_BROWSER_HANDOFF_ACTION",
        "请启用浏览器麦克风权限，或改用文本输入继续练习。",
    )
    ENABLE_ANALYTICS: bool = os.getenv("ENABLE_ANALYTICS", "true").lower() == "true"
    ENABLE_LEADERBOARD: bool = os.getenv("ENABLE_LEADERBOARD", "true").lower() == "true"


settings = Settings()


class Config:
    """FastAPI config"""

    case_sensitive = True
    env_file = ".env"
