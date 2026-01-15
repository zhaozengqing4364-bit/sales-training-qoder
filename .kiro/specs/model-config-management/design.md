# Design Document: Model Config Management

## Overview

统一的 AI 模型配置管理系统，支持 LLM、Embedding、ASR、TTS 四种模型类型的动态配置。管理员可通过前端界面配置各种 AI 服务，后端统一管理、验证和调用。

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Admin Frontend                          │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │  LLM Config │ │Embed Config │ │ ASR/TTS     │           │
│  │  - OpenAI   │ │ - OpenAI    │ │ - Alibaba   │           │
│  │  - Azure    │ │ - Local     │ │ - Azure     │           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Admin API Layer                          │
│  POST /api/v1/admin/model-configs                           │
│  GET  /api/v1/admin/model-configs                           │
│  PUT  /api/v1/admin/model-configs/{id}                      │
│  DELETE /api/v1/admin/model-configs/{id}                    │
│  POST /api/v1/admin/model-configs/{id}/test                 │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   Config Manager Service                    │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  In-Memory Cache (refreshed on config change)        │  │
│  │  - default_configs: Dict[ModelType, ModelConfig]     │  │
│  │  - all_configs: Dict[str, ModelConfig]               │  │
│  └──────────────────────────────────────────────────────┘  │
│                            │                                │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  get_config(model_type, provider?) -> ModelConfig    │  │
│  │  refresh_cache() -> None                             │  │
│  │  validate_config(config) -> Result[bool]             │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   AI Service Layer                          │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │ LLMService  │ │EmbedService │ │ ASR/TTS     │           │
│  │ (refactored)│ │   (new)     │ │ (refactored)│           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      Database                               │
│  model_configs table (encrypted api_key)                    │
└─────────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### 1. ModelConfig Entity

```python
class ModelType(str, Enum):
    LLM = "llm"
    EMBEDDING = "embedding"
    ASR = "asr"
    TTS = "tts"

class ModelProvider(str, Enum):
    OPENAI = "openai"
    AZURE = "azure"
    ALIBABA = "alibaba"
    LOCAL = "local"

class ModelConfig(Base):
    __tablename__ = "model_configs"
    
    id: str  # UUID
    name: str  # 显示名称，如 "GPT-4o 主力模型"
    model_type: ModelType  # llm/embedding/asr/tts
    provider: ModelProvider  # openai/azure/alibaba/local
    
    # Connection settings
    base_url: str  # API endpoint
    api_key_encrypted: str  # AES-256 encrypted
    model_name: str  # e.g., "gpt-4o", "text-embedding-3-small"
    
    # Provider-specific config (JSON)
    extra_config: dict  # temperature, max_tokens, etc.
    
    # Status
    is_default: bool  # 是否为该类型的默认配置
    is_active: bool  # 是否启用
    last_tested_at: datetime | None
    last_test_status: str | None  # success/failed
    
    # Audit
    created_at: datetime
    updated_at: datetime
```

### 2. ConfigManager Service

```python
class ConfigManager:
    """Singleton service for managing model configurations"""
    
    _instance: ConfigManager | None = None
    _cache: dict[str, ModelConfig] = {}
    _defaults: dict[ModelType, ModelConfig] = {}
    
    async def initialize(self) -> None:
        """Load all configs from database on startup"""
        
    async def refresh_cache(self) -> None:
        """Refresh in-memory cache from database"""
        
    def get_config(
        self,
        model_type: ModelType,
        provider: ModelProvider | None = None
    ) -> ModelConfig | None:
        """Get config, returns default if provider not specified"""
        
    def get_default_config(self, model_type: ModelType) -> ModelConfig | None:
        """Get default config for a model type"""
        
    async def validate_config(self, config: ModelConfig) -> Result[bool]:
        """Test if config is valid by making a minimal API call"""
```

### 3. Admin API Endpoints

```python
# POST /api/v1/admin/model-configs
class CreateModelConfigRequest(BaseModel):
    name: str
    model_type: ModelType
    provider: ModelProvider
    base_url: str
    api_key: str  # Plain text, will be encrypted
    model_name: str
    extra_config: dict = {}
    is_default: bool = False

# GET /api/v1/admin/model-configs?model_type=llm
class ModelConfigListResponse(BaseModel):
    configs: list[ModelConfigResponse]
    
class ModelConfigResponse(BaseModel):
    id: str
    name: str
    model_type: ModelType
    provider: ModelProvider
    base_url: str
    api_key_masked: str  # "sk-...xxxx"
    model_name: str
    extra_config: dict
    is_default: bool
    is_active: bool
    last_tested_at: datetime | None
    last_test_status: str | None

# POST /api/v1/admin/model-configs/{id}/test
class TestConfigResponse(BaseModel):
    success: bool
    message: str
    latency_ms: int | None
```

### 4. Refactored LLMService

```python
class LLMService:
    """LLM service that loads config from ConfigManager"""
    
    def __init__(self, config: ModelConfig | None = None):
        self._config_manager = get_config_manager()
        self._config = config or self._config_manager.get_default_config(ModelType.LLM)
        self._init_client()
    
    def _init_client(self):
        """Initialize LLM client based on provider"""
        if self._config.provider == ModelProvider.OPENAI:
            self.llm = ChatOpenAI(
                openai_api_key=self._decrypt_key(),
                openai_api_base=self._config.base_url,
                model=self._config.model_name,
                **self._config.extra_config
            )
        elif self._config.provider == ModelProvider.AZURE:
            # Azure-specific initialization
            pass
```

### 5. New EmbeddingService

```python
class EmbeddingService:
    """Embedding service for vector generation"""
    
    def __init__(self, config: ModelConfig | None = None):
        self._config_manager = get_config_manager()
        self._config = config or self._config_manager.get_default_config(ModelType.EMBEDDING)
        self._init_client()
    
    async def embed(self, text: str) -> Result[list[float]]:
        """Generate embedding vector for text"""
        
    async def embed_batch(self, texts: list[str]) -> Result[list[list[float]]]:
        """Generate embeddings for multiple texts"""
```

## Data Models

### Database Schema

```sql
CREATE TABLE model_configs (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    model_type VARCHAR(20) NOT NULL,  -- llm/embedding/asr/tts
    provider VARCHAR(20) NOT NULL,     -- openai/azure/alibaba/local
    
    base_url VARCHAR(500) NOT NULL,
    api_key_encrypted TEXT NOT NULL,
    model_name VARCHAR(100) NOT NULL,
    extra_config JSON DEFAULT '{}',
    
    is_default BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    last_tested_at TIMESTAMP,
    last_test_status VARCHAR(20),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(model_type, provider, model_name)
);

CREATE INDEX idx_model_configs_type ON model_configs(model_type);
CREATE INDEX idx_model_configs_default ON model_configs(model_type, is_default);
```

### API Key Encryption

```python
from cryptography.fernet import Fernet

class KeyEncryption:
    """AES-256 encryption for API keys"""
    
    def __init__(self):
        key = os.getenv("MODEL_CONFIG_ENCRYPTION_KEY")
        self.fernet = Fernet(key)
    
    def encrypt(self, plain_key: str) -> str:
        return self.fernet.encrypt(plain_key.encode()).decode()
    
    def decrypt(self, encrypted_key: str) -> str:
        return self.fernet.decrypt(encrypted_key.encode()).decode()
    
    @staticmethod
    def mask_key(key: str) -> str:
        """Mask API key for display: sk-...xxxx"""
        if len(key) <= 8:
            return "****"
        return f"{key[:3]}...{key[-4:]}"
```

## Error Handling

| Error Code | HTTP Status | Description |
|------------|-------------|-------------|
| `[MODEL_CONFIG_NOT_FOUND]` | 404 | 配置不存在 |
| `[MODEL_CONFIG_IN_USE]` | 400 | 配置正在使用中，无法删除 |
| `[MODEL_CONFIG_VALIDATION_FAILED]` | 400 | 配置验证失败 |
| `[MODEL_CONFIG_DUPLICATE]` | 409 | 配置已存在 |
| `[CANNOT_DELETE_DEFAULT]` | 400 | 无法删除默认配置 |
| `[ENCRYPTION_ERROR]` | 500 | 加密/解密失败 |

## Testing Strategy

### Unit Tests
- ConfigManager cache operations
- API key encryption/decryption
- Config validation logic

### Integration Tests
- CRUD API endpoints
- Config refresh on update
- Service initialization with config

### Manual Tests
- Frontend config UI
- Test connection functionality
