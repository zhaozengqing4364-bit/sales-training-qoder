# AI 与实时 Provider 治理

新人训练中的 AI Coach、录音评分和 StepAudio 由现有治理能力提供，活动配置只保存已发布 Profile/Rubric/Runtime Profile 的标识。

- Prompt、模型、温度、超时、重试、限流和输出 schema 集中版本化。
- attempt 冻结所用 revision；结果必须标明来源和失败状态，不把生成内容当作已验证事实。
- AI Coach 每轮使用客户端幂等 token；服务端锁定会话并保存 token 哈希。
- StepAudio 会话冻结 `activity_id`、`path_revision_id` 和 runtime binding；Provider 不可用时明确降级，不伪造完成。
- 工具与外部调用执行权限、对象范围、超时、审计和补偿策略。
- 密钥只从服务端受控配置读取，不进入前端、数据库 payload、日志、测试快照或提交。
- CI 使用 Fake/local Provider；真实 Provider 只在显式 gate 中少量验证。
