# AI 治理合同

> 状态：新人销售基础训练 AI 治理与最终质量门禁已完成（2026-07-18）。学习、录音、结构化 Coach 与 Readiness 摘要统一经过 AIInvocation/Prompt/Schema/持久任务边界；摘要只作带 Evidence 引用的辅助草稿，不能授予正式结论。

## 责任边界

- 业务模块拥有：business purpose、上下文允许清单、Prompt 变量、输入/输出 Schema、Rubric、确定性通过规则、风险与失败政策。
- `ai_platform` 拥有：Provider Adapter、任务模型路由、timeout/retry/rate limit/budget、调用幂等、血缘、Schema 校验、成本/延迟观测与脱敏。
- Prompt 由集中治理拥有工作修订、校验、发布、回滚和 Contract Hash；运行时冻结 template/revision/hash。业务模块不得本地拼出正式 Prompt 后绕过治理。
- 所有 LLM/ASR 通过 `AIInvocationPort`；业务代码不得导入 Provider SDK、直连 endpoint、访问底层 `.llm` 或自行构造 Provider。

`GovernedAIRequest` 至少携带：business purpose、organization/actor/object scope、Prompt revision/contract hash（ASR 可用 profile revision）、model routing profile revision、input/output schema version、timeout/retry policy ref、idempotency key、data classification、trace/correlation/causation、正式评分是否允许换模。

`AIInvocationResult` 至少携带：invocation_id、status、validated output 或 typed failure、provider/model revision、Prompt/profile lineage、token/时长/成本摘要、degradation、evidence refs 与 created_at。Raw Provider payload 只能进入受控、受保留策略约束的诊断存储，不能进入业务事件或普通 UI。

## 正式结果与降级

- 输出明确区分 `fact`、`rule`、`computation`、`inference`、`recommendation`、`draft`；AI 不得把推断标成事实。
- AI 只产生初评、证据、建议和不确定性。总分、红线、Gate 和状态由确定性领域规则计算；`foundation_ready` 只能由人工命令授予。
- 正式评分缺 Prompt、Schema、校准模型、证据或置信度时 fail closed 到 `needs_review/processing_failed`，不静默换模，不生成固定 60/70 分。
- 草稿生成可返回 partial/degraded，但必须标明缺失、保留用户输入并提供重试/人工路径。
- 高风险动作只返回 preview/建议；执行仍需权限、对象范围、confirm、幂等、审计和补偿。
- Readiness 摘要的事实引用必须属于当前冻结 Snapshot；无引用、越界引用、非法 Schema 或 Provider 失败保存为 `rejected/failed`，确定性档案与人工复核继续可用。学员投影不返回摘要原始草稿，Reviewer 也不能通过摘要绕过 eligibility、Snapshot freshness 或人工身份校验。

## Prompt 与模型生命周期

Prompt：`draft -> validating -> ready -> published -> archived`；published 内容不可变，回滚通过重新激活已发布修订或发布新修订，不原地修改。模型路由、temperature、max tokens、timeout、retry、rate limit 和预算全部来自已发布 profile；调用 Adapter 必须实际传递已解析参数，而不是只读取配置。

正式评分的 Prompt/model/rubric 变更必须有影响预览、Gold Set 结果、Owner、理由与回滚点。未校准新模型只能 shadow，不得影响正式 Outcome。

## Fake Provider、Contract Test 与 Gold Set

- Fake LLM/ASR 必须确定性支持 success、timeout、rate_limit、invalid_schema、partial、cancel、retry_then_success、low_confidence 和 duplicate delivery。
- Contract test 对每个 Provider Adapter 验证输入最小化、参数传递、错误分类、Schema 拒绝、幂等与 lineage，不在单测调用真实 Provider。
- Gold Set 版本化保存输入引用、预期约束、评分方法与审核人；不得把敏感原文复制进仓库 fixture。
- 上线顺序：Fake/integration -> Gold Set -> shadow -> canary -> scoped rollout；每级都有错误率、延迟、成本、公平性/偏差观察和回滚阈值。

### Foundation Gold Set 与真实 Provider staging

新人基础训练使用同一份版本化清单 `backend/tests/golden/foundation/foundation-ai-quality-v1.json` 覆盖题目生成、短答评分、录音评分、Coach 卡片、Coach 回答评估和 Dossier 摘要。CI 主门禁由 `backend/scripts/evaluate_foundation_ai_gold_set.py` 确定性执行，同时验证非法 Schema 拒绝与 Provider 超时降级；证据写入 `.sisyphus/evidence/foundation-ai-gold-set.json`。

冻结阈值为：Schema、非法输出拒绝、依据覆盖、降级合同和稳定性均为 `100%`；事实错误率与越界引用率均为 `0%`；确定性清单总成本不高于 `20` 个最小货币单位。任何单项或总阈值失败都阻止发布，不能以人工抽看覆盖机器结论。

这里的“稳定性”是业务合同稳定性，不要求生成式文本逐字相同。重复调用都必须独立通过 Schema、依据覆盖、事实约束和引用边界；同时比较会影响业务的结构与决定，例如题型/依据、简答得分与 Rubric 命中、录音维度得分、Coach 得分/不确定性和 Dossier 事实依据。允许措辞变化。Coach 输出中的 `mastered` 只作为审计草稿保存，正式掌握度由冻结 Profile 的得分与不确定性规则计算，因此稳定性比较不把该草稿字段当作状态权威。

真实 Provider 只允许在受控 staging 门禁中显式执行：

```bash
CRITICAL_GATE_MODE=foundation-ai-real-provider \
  LLM_API_KEY='通过环境或密钥系统注入' \
  LLM_BASE_URL='受安全策略允许的 HTTPS endpoint' \
  LLM_MODEL='已批准模型' \
  bash scripts/critical-quality-gate.sh
```

门禁内部还必须设置一次性 `FOUNDATION_AI_REAL_PROVIDER_CONFIRM=1` 才会发起网络调用；普通开发、单测和完整门禁默认不会调用真实 Provider。staging 使用受治理调用服务、冻结 Prompt revision/hash、模型路由 revision、输出 Schema、超时/重试、预算和 `allow_fallback=False`，只在证据中保存调用血缘、状态、用量、延迟和输出哈希，不保存 Prompt、学员原文或模型原始输出。缺少配置、Endpoint 策略失败、Provider 错误、Schema/依据/事实/稳定性或成本失败均不得记为通过。

Prompt 或模型升级必须分别保存旧版本与候选版本在同一 manifest、repeat count、成本上限和 staging 环境下的报告，比较所有指标及逐用例失败；候选版本只有在不降低冻结阈值且 Owner 完成审核后才能进入 shadow/canary。回滚通过恢复已发布 Prompt/路由修订完成，不原地修改历史修订，也不自动改变正式评分结果。

## 当前已知偏差

新人基础训练的学习任务已在切片 2、完整文件录音 ASR/评分已在切片 3、结构化 Coach 已在切片 4 切换到 `AIInvocationPort`。音频与 Coach 业务模块不再直接构造 Provider；旧同步/进程内音频 writer 和自由聊天式 Coach writer 已退役。录音评分及 Coach 卡片生成、语言评估、受限讲解都使用本次真实动态变量严格编译 Prompt contract hash，不能把静态 hash 当作正式调用合同。

Coach 的确定性选择/排序卡不调用模型；语言输出明确记录 `result_source=ai_inference`、不确定性、来源以及 Prompt/模型修订，最终掌握由 Profile 快照规则计算。答案在 AI 任务前持久化；非法 Schema、越界来源、高不确定性或两轮补练上限分别进入可恢复或人工帮助路径，不能伪造分数/完成。CoachOutcome 只在三个 checkpoint 完成后产生，且不授予 `foundation_ready`。

仓库其他产品域仍可能存在直接获取 LLMService、`.llm.apredict` 或不一致降级语义；它们是各自 Legacy 迁移清单，不能被新人训练复用或当成本合同的永久例外。Foundation 范围已由 Guard、消费者清单、确定性 Gold Set 和受控真实 Provider staging 证明清零并达到冻结阈值。
