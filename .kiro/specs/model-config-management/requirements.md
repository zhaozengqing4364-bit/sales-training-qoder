# Requirements Document

## Introduction

统一的 AI 模型配置管理系统，允许管理员通过前端界面配置各种 AI 服务（LLM、Embedding、ASR、TTS），后端统一管理、验证和调用。解决当前配置分散在环境变量中、无法动态切换的问题。

## Glossary

- **Model_Provider**: AI 模型提供商（如 OpenAI、阿里云、Azure）
- **Model_Config**: 单个模型的配置（base_url、api_key、model_name 等）
- **Model_Type**: 模型类型枚举（llm、embedding、asr、tts）
- **Config_Manager**: 后端配置管理服务
- **Admin_UI**: 管理员配置界面

## Requirements

### Requirement 1: 模型配置数据模型

**User Story:** As an administrator, I want to store AI model configurations in the database, so that I can manage them dynamically without restarting the server.

#### Acceptance Criteria

1. THE Model_Config entity SHALL store provider, model_type, base_url, api_key (encrypted), model_name, and additional parameters
2. THE Model_Config entity SHALL support multiple model types: llm, embedding, asr, tts
3. THE Model_Config entity SHALL have a unique constraint on (provider, model_type, model_name)
4. THE Model_Config entity SHALL track is_default flag to identify the default config for each model_type
5. THE Model_Config entity SHALL store created_at and updated_at timestamps
6. WHEN storing api_key, THE System SHALL encrypt it before persisting to database

### Requirement 2: 模型配置 CRUD API

**User Story:** As an administrator, I want to create, read, update, and delete model configurations through API, so that I can manage AI services from the admin panel.

#### Acceptance Criteria

1. WHEN an admin creates a model config, THE System SHALL validate required fields and store the configuration
2. WHEN an admin lists model configs, THE System SHALL return configs grouped by model_type with masked api_keys
3. WHEN an admin updates a model config, THE System SHALL validate and update only provided fields
4. WHEN an admin deletes a model config, THE System SHALL check if it's in use before deletion
5. IF a model config is the only default for its type, THEN THE System SHALL prevent deletion
6. THE API SHALL support filtering by model_type and provider

### Requirement 3: 模型配置验证

**User Story:** As an administrator, I want to test model configurations before saving, so that I can ensure they work correctly.

#### Acceptance Criteria

1. WHEN an admin requests config validation, THE System SHALL attempt a minimal API call to verify connectivity
2. FOR LLM configs, THE System SHALL send a simple completion request and verify response
3. FOR Embedding configs, THE System SHALL embed a test string and verify vector output
4. FOR ASR configs, THE System SHALL verify API credentials are valid
5. FOR TTS configs, THE System SHALL verify API credentials are valid
6. THE validation endpoint SHALL return success/failure with error details
7. THE validation SHALL timeout after 10 seconds

### Requirement 4: 动态模型切换

**User Story:** As a system, I want to load model configurations from database at runtime, so that configuration changes take effect without restart.

#### Acceptance Criteria

1. WHEN the application starts, THE Config_Manager SHALL load all active model configs from database
2. WHEN a model config is updated via API, THE Config_Manager SHALL refresh the in-memory cache
3. WHEN requesting a model service, THE System SHALL use the default config for that model_type
4. IF no database config exists, THEN THE System SHALL fallback to environment variables
5. THE Config_Manager SHALL provide a method to get config by (model_type, provider, model_name)

### Requirement 5: 前端配置界面

**User Story:** As an administrator, I want a settings page to configure AI models, so that I can easily manage LLM, Embedding, ASR, and TTS services.

#### Acceptance Criteria

1. WHEN an admin visits the settings page, THE Admin_UI SHALL display model configs grouped by type (LLM, Embedding, ASR, TTS)
2. THE Admin_UI SHALL provide forms to add new model configurations with provider-specific fields
3. THE Admin_UI SHALL mask api_key fields and only show last 4 characters
4. THE Admin_UI SHALL provide a "Test Connection" button for each config
5. THE Admin_UI SHALL allow setting a default config for each model type
6. THE Admin_UI SHALL show validation status (success/failed/untested) for each config

### Requirement 6: 服务层抽象

**User Story:** As a developer, I want a unified interface to access AI services, so that business code doesn't need to know about specific providers.

#### Acceptance Criteria

1. THE LLM_Service SHALL load configuration from Config_Manager instead of environment variables
2. THE Embedding_Service SHALL be created with the same abstraction pattern
3. THE ASR_Service SHALL support dynamic provider switching based on config
4. THE TTS_Service SHALL support dynamic provider switching based on config
5. WHEN a service is requested, THE System SHALL return the service configured with the default provider
6. THE service abstraction SHALL support provider-specific parameters through a generic config dict

### Requirement 7: 安全性

**User Story:** As a system administrator, I want API keys to be stored securely, so that sensitive credentials are protected.

#### Acceptance Criteria

1. THE System SHALL encrypt api_key using AES-256 before storing in database
2. THE System SHALL use a separate encryption key stored in environment variables
3. WHEN returning model configs via API, THE System SHALL mask api_key (show only last 4 chars)
4. THE admin API endpoints SHALL require admin role authentication
5. THE System SHALL log all config changes with admin user ID for audit
