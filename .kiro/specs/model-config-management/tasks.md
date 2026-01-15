# Implementation Plan: Model Config Management

## Overview

实现统一的 AI 模型配置管理系统，支持 LLM、Embedding、ASR、TTS 的动态配置。

## Tasks

- [x] 1. 数据模型和数据库迁移
  - [x] 1.1 创建 ModelConfig SQLAlchemy 模型
    - 定义 ModelType、ModelProvider 枚举
    - 定义 model_configs 表结构
    - 添加索引和约束
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_
  - [x] 1.2 创建 Alembic 迁移脚本
    - 生成 model_configs 表
    - _Requirements: 1.1_
  - [x] 1.3 实现 API Key 加密工具
    - 使用 Fernet (AES-256) 加密
    - 实现 encrypt/decrypt/mask 方法
    - _Requirements: 1.6, 7.1, 7.2, 7.3_

- [x] 2. ConfigManager 核心服务
  - [x] 2.1 实现 ConfigManager 单例服务
    - 内存缓存机制
    - 从数据库加载配置
    - get_config / get_default_config 方法
    - _Requirements: 4.1, 4.3, 4.5_
  - [x] 2.2 实现配置刷新机制
    - refresh_cache 方法
    - 配置更新时自动刷新
    - _Requirements: 4.2_
  - [x] 2.3 实现环境变量回退
    - 无数据库配置时使用环境变量
    - _Requirements: 4.4_

- [x] 3. 配置验证服务
  - [x] 3.1 实现 LLM 配置验证
    - 发送简单 completion 请求
    - 10 秒超时
    - _Requirements: 3.1, 3.2, 3.7_
  - [x] 3.2 实现 Embedding 配置验证
    - 嵌入测试字符串
    - 验证向量输出
    - _Requirements: 3.1, 3.3, 3.7_
  - [x] 3.3 实现 ASR/TTS 配置验证
    - 验证 API 凭证
    - _Requirements: 3.1, 3.4, 3.5, 3.7_

- [-] 4. Admin API 端点
  - [x] 4.1 创建 Pydantic schemas
    - CreateModelConfigRequest
    - UpdateModelConfigRequest
    - ModelConfigResponse
    - TestConfigResponse
    - _Requirements: 2.1, 2.2, 2.3_
  - [x] 4.2 实现 CRUD 端点
    - POST /api/v1/admin/model-configs
    - GET /api/v1/admin/model-configs
    - GET /api/v1/admin/model-configs/{id}
    - PUT /api/v1/admin/model-configs/{id}
    - DELETE /api/v1/admin/model-configs/{id}
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_
  - [x] 4.3 实现测试连接端点
    - POST /api/v1/admin/model-configs/{id}/test
    - POST /api/v1/admin/model-configs/test (inline test)
    - _Requirements: 3.1, 3.6_
  - [ ] 4.4 添加审计日志
    - 记录配置变更
    - _Requirements: 7.5_

- [x] 5. Checkpoint - 后端 API 完成
  - 所有 API 测试通过
  - 验证加密功能正常
  - 路由已注册到 main.py
  - ConfigManager 在 lifespan 中初始化

- [x] 6. 重构现有 AI 服务
  - [x] 6.1 重构 LLMService
    - 从 ConfigManager 加载配置
    - 支持多 provider
    - _Requirements: 6.1_
  - [x] 6.2 创建 EmbeddingService
    - 统一的 embedding 接口
    - 支持 OpenAI/Azure
    - _Requirements: 6.2_
  - [x] 6.3 重构 ASR/TTS 服务
    - 从 ConfigManager 加载配置
    - _Requirements: 6.3, 6.4_

- [x] 7. 前端管理界面
  - [x] 7.1 创建模型配置页面
    - /admin/settings/models
    - 分组显示 LLM/Embedding/ASR/TTS
    - _Requirements: 5.1_
  - [x] 7.2 实现配置表单
    - 添加/编辑配置
    - Provider 特定字段
    - API Key 掩码显示
    - _Requirements: 5.2, 5.3_
  - [x] 7.3 实现测试连接功能
    - Test Connection 按钮
    - 显示验证状态
    - _Requirements: 5.4, 5.6_
  - [x] 7.4 实现默认配置切换
    - 设置默认配置
    - _Requirements: 5.5_

- [x] 8. Final Checkpoint
  - 确保所有测试通过
  - 验证前后端集成

## Notes

- API Key 加密密钥需要在环境变量中配置: `MODEL_CONFIG_ENCRYPTION_KEY`
- 首次部署需要运行数据库迁移
- 现有环境变量配置作为回退，确保向后兼容
