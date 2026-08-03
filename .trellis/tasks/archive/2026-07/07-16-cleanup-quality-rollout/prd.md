# 切片 8：旧链路清理、质量门禁与受控首发

## Goal

完成新人销售基础训练平台的最终收口：删除已替代的旧权威和临时兼容，建立架构、契约、测试、安全、AI、性能和运维门禁，在干净环境和受控 Provider 环境中证明从学员分配到 `foundation_ready` 的完整闭环可发布、可观察、可回滚。

本切片不是“最后再跑一下测试”，而是验证父任务的产品承诺和 Definition of Done。

## Dependencies

- 切片 0–7 功能和契约全部完成。
- 所有前序切片的 `implementation-notes.md`、迁移矩阵和未完成项可用。

## Requirements

### R1. Authority Inventory

- 重新运行 CodeGraph，盘点以下写权威：
  - Path/Enrollment；
  - Learning/Question/Quiz；
  - Audio/Transcript/Score；
  - AI Coach；
  - Evidence/Readiness；
  - Prompt/AI Invocation；
  - Task/Outbox；
  - 前端路由和 API Facade。
- 每个业务对象只允许一个正式写权威。
- 对仍存在的重复实现给出删除、只读审计或明确阻塞结论。

### R2. Remove Old Routes And Facades

- 删除或禁用已替代的旧学员入口、旧管理写入口、旧 Activity 提交 API 和旧题目确认 API。
- 删除短期重定向和兼容 Facade，除非父任务明确批准且有删除期限。
- OpenAPI 不再暴露首发不使用的 realtime 新人训练路由。
- 前端不再调用旧 endpoint 或读取旧 DTO。

### R3. Remove Direct Provider And Ephemeral Work

- 业务模块不得直接调用 LLM/ASR/对象存储 SDK。
- 正式长任务不得使用进程内 BackgroundTask、fire-and-forget 或请求内长耗时 Provider IO。
- 所有活动类型通过显式 Registry，不使用动态字符串导入。
- 静态扫描和 Architecture Guard 阻止回归。

### R4. Database Cleanup

- 完成旧表/列/索引/约束清理或记录明确保留理由。
- 删除前执行影响统计、dry-run、备份/导出和回滚方案。
- migration 在空库、当前开发库快照和从指定旧基线升级三种路径验证。
- seed/reset 可重复执行。
- 无孤立外键、重复业务身份、不可达 revision 和悬空 artifact ref。

### R5. Architecture Fitness

- 自动化检查至少覆盖：
  - shared kernel 不反向依赖业务域；
  - 无新增 SCC/循环依赖；
  - 无跨模块 ORM/Repository；
  - Controller 不直接编排事务和 Provider；
  - Activity/Task/Card 使用显式 Registry；
  - 业务模块不直连 Provider；
  - 前端页面不直接消费 ORM/原始 DTO；
  - 前端不计算正式达标；
  - 运行时 OpenAPI 与文档一致。
- 基线只能改善，不允许用扩大白名单解决新增违规。

### R6. Contract Verification

- OpenAPI snapshot/diff。
- 前后端生成/手写类型一致性。
- ActivityDefinition、Task、Card、Outcome、Evidence、Dossier 的 schema contract tests。
- Prompt contract hash、模型输出 schema 和 Provider adapter tests。
- 错误码/用户错误映射完整，不出现未映射内部错误。

### R7. State Machine Verification

- 对所有核心状态机做 transition table 测试。
- 覆盖非法转移、重复命令、并发、取消、超时、重试、失效、stale 和人工恢复。
- 对任务成功/业务 reconcile 失败、Provider 成功/事务失败等跨层边界做故障注入。
- 不以 happy path 测试替代完整状态验证。

### R8. Permission And Security Verification

- 完整角色/capability/对象级权限矩阵。
- 跨组织 IDOR、批量操作越权、签名 URL 越权、导出越权、Prompt 管理越权。
- 文件上传内容/格式/大小、对象 key、恶意文件和重复 complete。
- 日志、审计、错误和前端 payload 的敏感信息扫描。
- AI prompt injection、工具参数、数据范围和输出执行安全。
- 高风险操作有 preview/confirm/reason/audit/rollback。

### R9. AI Quality Gate

- 为题目生成、短答评分、录音评分、Coach 卡片/评估和 Dossier 摘要建立 gold set。
- 指标至少包含 schema validity、依据覆盖、事实错误、幻觉、拒答/降级、稳定性和成本。
- 使用 deterministic fake 作为 CI 主门禁；受控真实 Provider 做 staging 验证。
- Prompt/模型升级必须通过回归对比，不只人工抽看。
- AI 失败不阻塞可确定性流程或正式人工复核。

### R10. End-To-End Scenarios

- 正常路径：
  - 管理员发布标准包；
  - 创建 Cohort/Enrollment；
  - 新人完成 Lesson、Quiz、Audio、Coach、异步场景录音；
  - Evidence/Dossier 更新；
  - Reviewer 授予 `foundation_ready`。
- 补练路径：
  - Quiz/Audio/Coach 未达标；
  - 系统显示薄弱能力；
  - 分配补练；
  - 重试；
  - 重新复核。
- 故障路径：
  - 上传中断续传；
  - ASR/AI 超时；
  - Worker 重启；
  - reconcile 失败重放；
  - 发布失败旧版本仍有效。
- 权限路径：跨组织访问被拒绝。
- 申诉路径：申诉、重评、Snapshot stale、复核重开。

### R11. Performance And Capacity

- 在真实规模假设下做基线：
  - 学员首页/Journey；
  - 管理待办与大列表；
  - 并发任务创建；
  - Worker 队列吞吐；
  - 大文件直传；
  - Evidence/Dossier rebuild；
  - 发布校验；
  - 前端首屏、bundle 和交互。
- 明确测试数据量、硬件、Provider fake/真实条件。
- 所有慢查询提供 explain 和索引依据。
- 长任务不占用 Web 请求至完成。
- 结果与父任务 SLO 对照，偏差必须阻塞或有明确批准。

### R12. Observability And Alerting

- Dashboard/指标覆盖：
  - API 错误率和延迟；
  - 任务队列、Lease、重试、死信、reconcile；
  - 上传失败；
  - ASR/AI 延迟、错误、Token、成本；
  - Activity 完成漏斗；
  - Evidence/Dossier lag；
  - Review 等待时间；
  - 发布成功/失败。
- 告警有阈值、责任人、Runbook 和降噪策略。
- trace/request/task/invocation/business object 可关联。
- 日志不泄露录音、答案、手机号、Token 或密钥。

### R13. Developer Experience

- 提供一键：
  - reset；
  - migrate；
  - seed standard pack；
  - start API/Worker/Web；
  - run focused tests；
  - run full verify。
- 默认本地使用 deterministic fake Provider，可选择显式启用真实 Provider。
- 文档说明常见故障、任务重放、对账、清理本地录音草稿和重建 Dossier。
- 不要求开发者手动改数据库才能完成正常流程。

### R14. Runbooks

- 至少包含：
  - Worker 队列堆积；
  - AI/ASR Provider 故障；
  - 对象存储故障；
  - 上传 orphan 清理；
  - task/reconcile 修复；
  - Evidence/Dossier rebuild；
  - 发布失败；
  - Prompt/模型回滚；
  - 数据泄露/权限事件；
  - 快速关闭某 Activity Type。
- 每个 Runbook 有观察信号、诊断命令、安全动作、升级路径和恢复验证。

### R15. Feature Flags And Rollout

- 使用最少且有期限的 feature flag：
  - 新学员入口；
  - 新 Audio Pipeline；
  - 结构化 Coach；
  - 新 Admin Workspace；
  - 正式 Readiness。
- flag 有默认值、组织范围、审计和删除任务。
- rollout 顺序：
  1. 内部/测试组织；
  2. 小 Cohort；
  3. 扩大 Cohort；
  4. 默认启用；
  5. 删除旧代码与 flag。
- 不长期维持两个写权威。

### R16. Release And Rollback Rehearsal

- 在 staging/等价环境实际演练：
  - migration；
  - seed；
  - 发布标准包；
  - 创建用户数据；
  - 中断 Worker；
  - Provider 故障；
  - 回滚应用；
  - 回滚 ReleasePlan；
  - 重建 Projection。
- 记录时间、命令、结果和发现。
- 回滚不删除用户录音、答案、Evidence 或审计。

### R17. Documentation Closure

- 更新 `docs/architecture.md`、领域词典、UIUX、API、安全、测试、AI Governance 和相关 ADR。
- 更新 Trellis Spec，使其与最终代码一致。
- 旧任务中与本任务冲突的设计标记为 superseded，保留历史但不再作为权威。
- 父任务 acceptance matrix 每项附验证证据或明确未通过原因。

## Acceptance Criteria

- [x] 每个核心业务对象只有一个写权威。
- [x] 旧学员/管理写路由、进程内长任务、直接 Provider 调用和动态 Activity import 已清理。
- [x] 架构 Guard、OpenAPI diff、contract、状态机和权限测试进入 CI。
- [x] 空库与旧基线 migration/seed/reset 均可重复执行。
- [x] 正常、补练、故障、权限和申诉 E2E 全部通过。
- [x] AI gold set 和真实 Provider staging 验证达到冻结门槛。
- [x] 性能 SLO 有可复现测量证据。
- [x] 关键指标、告警和 Runbook 已验证。
- [x] rollout 和 rollback 至少演练一次。
- [x] Realtime 首发完全不可见且无默认运行依赖。
- [x] 父任务 acceptance matrix 无未解释空项。
- [x] 所有长期 feature flag、兼容层和临时白名单都有删除结果或阻塞批准。

## Verification Command Groups

具体命令以仓库 `docs/testing.md` 和各 package script 为准，最终报告必须列出实际命令与结果：

- backend lint/type/unit/integration/contract；
- migration upgrade/downgrade/upgrade；
- frontend lint/type/unit/component/build；
- browser E2E 和可访问性；
- architecture/affected/OpenAPI checks；
- performance/load/provider staging；
- full reset-seed-start-verify。

## Definition Of Done

- 父任务全部业务、架构、数据、安全、AI、性能和体验验收通过。
- 用户可在干净环境完成真实的首发闭环。
- 发布、故障、重试、申诉和回滚都有证据。
- 没有“当前能跑但不可恢复/不可追溯/不可运营”的残余链路。
- 未纳入首发的 Realtime 有清晰后续边界，但不污染当前代码路径。

## Out Of Scope

- 不在最终收口中顺手建设 Realtime。
- 不扩展为通用 LMS、CRM 或 HR 系统。
- 不为追求抽象纯度拆成微服务。
- 不处理与新人销售基础训练无关的全仓历史技术债。

## Risk And Rollback

- 风险等级：P0/P1（涉及旧权威删除、migration 和首发切换）。
- 删除前必须证明新权威可用并有数据/结果核对。
- 破坏性 migration 必须 dry-run、备份/补偿和演练。
- 任何正式结论或用户生成内容不得在回滚中丢失。
- 若首发失败，关闭新入口和任务创建，保留数据与审计，恢复稳定 ReleasePlan 和前一应用版本。
