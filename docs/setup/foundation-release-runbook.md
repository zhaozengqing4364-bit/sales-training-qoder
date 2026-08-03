# 新人基础训练发布与回滚 Runbook

## 适用范围

本手册用于 Path、Source、LearningUnit、Question、Quiz 依赖闭包的 `ReleasePlan` 发布和已知稳定计划回滚。它不用于 Enrollment 修订迁移，也不允许通过手工改表或临时恢复直发 API 绕过发布治理。

管理入口：`/admin/newcomer-training/releases`。正式 HTTP 合同见 `docs/api-contract/newcomer-training-v2.md`。

## 发布前检查

1. 确认操作者具有 `newcomer.path.publish`，且 capability 投影中 `publish_releases=true`；不得只依据角色名或前端按钮判断。
2. 确认目标是当前 organization/Path 的 working PathRevision，所有活动已有能力映射。
3. 确认 Source 已解析完成，Question 已人工批准，Source–Unit Anchor、Quiz–Question 和其他资源引用完整。
4. 确认需要的评分方案、Coach Profile、Prompt、模型路由和 Provider 健康状态满足发布校验。
5. 记录业务发布依据。发布不是 Enrollment 迁移：现有 Enrollment 将继续冻结在原 PathRevision。

## 标准发布

1. 在发布记录页选择目标 Path working revision，填写发布依据并执行“校验发布计划”。
2. 检查持久计划中的目标修订、依赖图、阻塞/警告、运行时合同 hash 和 Enrollment 影响。阻塞项必须回到对应工作对象修复后重新创建预览；不能在发布页忽略。
3. 仅在页面仍显示同一 preview token/impact hash 且计划版本未变化时确认发布。确认请求必须携带 `If-Match` 和新的 `Idempotency-Key`；网络结果不确定时复用原键查询/重试。
4. 成功后从持久发布记录确认：计划状态为 `published`，Path active plan/published revision 指向目标，上一计划为 `superseded`，审计包含操作者、原因、前后版本和结果。
5. 抽查一个新绑定场景使用新 PathRevision，并确认已有 Enrollment 的 frozen revision 未变化。

## 阻塞与失败处置

| 现象 | 判断 | 处置 |
|---|---|---|
| 计划为 `blocked` | 依赖、能力映射、合同或配置校验未通过 | 按 object/field blocker 修复工作修订，重新预览；不要重试 publish |
| `[NEWCOMER_RELEASE_PREVIEW_EXPIRED]` | 30 分钟预览已过期 | 重新创建计划并重新审阅影响 |
| impact/hash/target changed | 预览后 Path 或依赖发生变化 | 刷新工作对象，重新预览；禁止沿用旧确认数据 |
| 412 conflict | 计划或 active pointer 被并发更新 | 查询最新发布历史，确认当前生效计划后重新决策 |
| 计划为 `failed` | 闭包内某个 publish 失败 | 原 active plan 仍有效；从计划的 `publish_failure` 和对象审计定位目标，修复后创建新计划 |
| 客户端超时/断开 | 结果未知 | 先按 Path 查询计划；使用原幂等键重试同一确认，不创建猜测性第二次发布 |
| 直发接口返回 `[NEWCOMER_RELEASE_PLAN_REQUIRED]` | 消费者仍调用兼容墓碑 | 切换消费者到 ReleasePlan；不得恢复直发实现 |

发布失败时，领域资源和 Path 的发布指针位于嵌套事务内并整体回滚；失败计划和审计在外层事务持久化。不得把 `failed` 计划手工改成 `published`。

## 回滚到已知稳定计划

1. 确认当前 active ReleasePlan 和目标历史计划属于同一 organization、同一 Path；目标状态必须是 `published` 或 `superseded`。
2. 填写具体回滚原因，执行 rollback preview，确认当前/目标 PathRevision、未来 Enrollment 行为以及“活跃 Enrollment 不变”。
3. 在 30 分钟内使用同一 preview token、impact hash、当前 active plan `If-Match` 和幂等键确认回滚。
4. 成功后确认 Path active plan/published revision 指向目标；原 active 计划为 `superseded` 且记录 `rolled_back_by/rolled_back_at`；目标计划重新为 `published`。
5. 验证新 Enrollment 使用恢复后的 PathRevision，既有 Enrollment、Attempt 和 Outcome 未被改写。

回滚只切换正式指针，不物理删除资源或修订，也不会自动迁移 Enrollment。若目标内容本身需要修改，应创建新 working revision 和新的 ReleasePlan，而不是修改历史发布。

## 紧急降级

- 暂停新发布：撤销相关操作者的发布 capability 或在接入层暂时禁用管理写入口；现有 active plan 和学员训练继续可读。
- Provider/解析能力降级：保留 working Source、题目批次和持久 Task 结果位置；待恢复后授权重试，不把未完成对象纳入发布。
- 错误版本已生效：优先执行上述受审计回滚；不得手工更新 `newcomer_paths.active_release_plan_id` 或 `published_revision_id`。
- 无可用稳定历史计划：保持当前版本服务并创建修复 revision/ReleasePlan；若风险不可接受，按事故流程暂停新的 Enrollment，而不是破坏已有冻结 Enrollment。

## 数据库迁移与代码回滚

- ReleasePlan schema 由 Alembic `20260717_1500_006` 引入；发布前必须在目标 PostgreSQL 环境完成 upgrade 并确认唯一 head。
- 只有尚未写入正式 ReleasePlan、Enrollment import 或 Candidate bulk-review 数据的开发/发布回滚环境可执行该 revision 的 downgrade。
- 一旦存在正式历史，代码回滚应保留新表和 published pointers，并把新命令置为只读；不得通过 downgrade 删除审计和发布血缘。
- 恢复服务后先查询发布记录和 Path workspace，确认 active pointer、计划状态和 audit 一致，再开放新发布。

## 验证证据

每次发布或回滚至少保留：Path/Revision、ReleasePlan ID、依赖与 blocker 摘要、impact hash、操作者、原因、时间、最终状态、旧/新 active plan、现有 Enrollment 未迁移的抽查结果，以及失败时的恢复动作。敏感 Prompt、Provider payload、原始 token 和密钥不得进入证据或日志。
