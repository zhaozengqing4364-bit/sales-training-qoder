# 配置与秘密保留边界

## 用户决定

* 清理完整项目数据面，但只能操作明确的 PostgreSQL、Redis DB/namespace、Chroma 路径、本地数据目录和 COS 项目前缀。
* 已配置的链接地址、密钥、模型名和 API key 必须保留。

## 仓库事实

### 环境与部署 Secret

当前 `backend/.env` 中已配置以下类别的变量（本次只检查变量名是否有值，没有读取或输出具体值）：

* `MODEL_CONFIG_ENCRYPTION_KEY`
* `LLM_*`、`OPENAI_*`、`EMBEDDING_*`、`DASHSCOPE_API_KEY`
* `STEPFUN_API_KEY`、`STEPFUN_REALTIME_URL/MODEL/VOICE`
* `TENCENT_COS_SECRET_ID/SECRET_KEY/BUCKET/REGION`
* `SESSION_STATE_REDIS_URL`
* 销售训练音频存储 backend 选择

这些变量存在于文件或部署 Secret，不应由数据 reset 工具编辑、删除、回显或复制到普通报告。

### PostgreSQL 内的运行时配置

* `model_configs` 保存 provider、base URL、model name、extra config 和加密后的 API key；数据库管理员配置优先，环境变量只是 fallback。
* `rag_profiles` 保存 RAG、cross-encoder 模型和加密后的 API key。
* `voice_runtime_profiles` 保存 StepFun realtime 模型、voice、temperature、audio format 和 tool policy；API key 仍来自环境变量。
* `prompt_templates`、`business_rule_configs`、`scoring_rulesets`、`config_bundles/config_versions` 属于产品控制面配置，不是用户训练历史。
* `agent_voice_policies`、`scenario_prompts`、presentation scope policy 等可能引用 Agent、Scenario 或其他业务对象，不能脱离依赖盲目恢复。

### 加密约束

* `model_configs.api_key_encrypted` 和 RAG cross-encoder key 由 `MODEL_CONFIG_ENCRYPTION_KEY` 对称加密。
* 如果保留数据库 ciphertext，就必须原样保留同一 encryption key；否则恢复后的 key 无法解密。
* 导出、dry-run 和验证只能报告 `configured=true`、数量和不可逆指纹，不能输出明文或完整 ciphertext。

## 推荐保留方式

1. `.env` 和部署 Secret 原地不动，并在 reset 前后只比较变量名集合与不可逆指纹。
2. reset 前导出一份白名单配置快照：连接/模型、RAG、全局 voice runtime、Prompt、发布中的业务规则和评分规则；秘密保持原有 ciphertext。
3. 对存在业务对象外键的配置不直接搬运：先导出逻辑键，重建依赖对象后再解析绑定；无法解析时 fail closed 并列出缺口。
4. 不导出用户、训练记录、会话、提交、任务、审计日志和历史操作人。
5. 新 baseline 后按固定顺序恢复配置，再创建管理员、显式团队和首发资产。
6. Provider smoke 只验证连通性与模型身份，不在日志中输出 endpoint query secret、API key 或响应敏感内容。

## 当前阻塞证据

使用当前默认 backend 数据库配置进行只读配置盘点时，PostgreSQL 返回认证失败。因而实现必须要求调用者显式提供并确认目标连接，且只有配置快照成功、指纹落盘后才允许进入 destructive apply；不能在无法读取旧配置时继续清库。
