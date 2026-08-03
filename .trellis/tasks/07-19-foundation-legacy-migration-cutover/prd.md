# 旧新人训练数据迁移、切换与旧入口退役

## Goal

将当前 Legacy 中仍有效的 `石犀ppt讲解`、`demo讲解`、对应 PPT 材料及可验证评分配置迁入 Foundation，合并到新的完整新人训练路径并通过 ReleasePlan 发布；随后切断新人训练 Legacy 写入口，确保系统只有一个数据权威且可回滚。

## Dependencies

- 合同、全部资源 Authoring、管理端导航和路径内绑定任务完成。
- 目标 Foundation 路径、资源和 ReleasePlan 接口稳定。

## Migration Workflow

严格执行：

```text
inspect → dry-run → resolve conflicts → apply → verify → release preview → confirm → cut over
```

默认命令只做 inspect/dry-run。`apply` 必须显式指定组织、迁移计划 ID、impact hash、操作者和原因；生产环境不能因脚本存在而自动运行。

## Requirements

### R1. 迁移身份与审计

- 每个 Legacy 对象使用 `source_system + organization_id + legacy_type + legacy_id + source_revision/hash` 形成稳定迁移键。
- 保存 MigrationPlan、逐项映射、状态、错误、目标 ID/revision、操作者、时间和审计。
- 相同输入重复 apply 返回原结果；输入 hash 变化必须重新 dry-run。
- 不记录完整 Prompt、文件内容、个人敏感数据或密钥。

### R2. 材料迁移

- 读取 Legacy `SalesTrainerMaterial` 和有效 published version，验证文件存在、hash、MIME/签名、purpose 和组织范围。
- 将 PPT 建为 Foundation slide deck SourceDocument working revision，运行新解析/预览流程并保留 legacy lineage。
- 同名同 hash 合并为同一逻辑资源；同名不同 hash、一个版本被多个逻辑材料引用等情况列为冲突，不自动覆盖。
- 文件缺失时计划进入 `needs_input`，在当前迁移工作区提供重新上传/选择已有材料并自动续跑；不得伪造成功。

### R3. 讲解资源迁移

- `石犀ppt讲解` 映射为独立 `audio_material` + `scoring_scheme` + v2 `audio_assessment` Activity。
- `demo讲解` 映射为独立 Demo 内容/脚本、`audio_material` + `scoring_scheme` + v2 `audio_assessment` Activity。
- 只迁移能通过新 Schema/来源/AI contract 校验的旧评分配置；无法验证的 Prompt 转为待人工补充，不作为已发布合同。
- 保留 Legacy logical ID/revision/hash 作为 lineage，不复制内部 raw payload 到普通 UI。

### R4. Path 合并策略

- 从当前 Foundation published PathRevision 克隆新的 working revision，保留已有 Lesson、Quiz、Coach 和异步场景。
- 按稳定 activity key upsert PPT/Demo 讲解：已存在同源活动为 no-op/更新绑定候选，不重复追加；语义冲突进入人工确认。
- 活动位置、前置依赖、必修、能力映射和预计时长在 dry-run 中清晰展示。
- 正式生效只走 ReleasePlan；不直接改 published pointer。
- 新发布只供未来 Enrollment；活跃 Enrollment 不自动迁移。

### R5. 验证

verify 至少检查：

- 目标逻辑资源和修订数量；
- 文件 hash/预览、来源 refs、评分合同和能力映射；
- Path 依赖闭包和 Runtime compile；
- 学员安全投影可读取；
- 同一迁移键唯一；
- Legacy 写入口无新写；
- 回滚目标 ReleasePlan 可用。

任何验证失败均保持旧 active ReleasePlan，不把部分迁移显示为已切换。

### R6. 旧入口退役

- 删除或只读封存仅用于新人训练的 Legacy orchestration/material/path writer 与 UI 消费者。
- 其他产品仍使用的 `sales_trainer` 代码/表不因本任务被全局删除；以调用者/路由 inventory 精确判断。
- 旧管理 URL 不作为长期转发写入口；需要审计时指向只读 MigrationPlan/Legacy export。
- 添加 OpenAPI/importer/route consumer gate，防止新人路径重新依赖 Legacy writer。

### R7. 回滚

- 切换失败或用户验收不通过时重新激活迁移前稳定 ReleasePlan；既有 Enrollment 保持冻结。
- 新建 working/published revisions 和 MigrationPlan 保留审计，不手工删表或覆盖历史。
- Legacy writer 只有在目标切换尚未承载新业务数据且经明确回滚步骤时才能临时恢复；不得与 Foundation 双写。

## Acceptance Criteria

- [ ] 当前数据库 dry-run 明确列出两个讲解活动、PPT、评分配置、目标对象和冲突/缺失项。
- [ ] 同一计划重复 apply 不创建重复资源、修订、活动或发布计划。
- [ ] PPT 经新内容资产流程可预览，PPT/Demo 各绑定独立材料和评分方案。
- [ ] 新 Path 在保留标准学习/测验/Coach/场景的同时包含两个迁移活动，无重复 stable key。
- [ ] ReleasePlan 发布成功后，新 Enrollment 的 `/newcomer-training` 可读取迁移内容；活跃 Enrollment 不移动。
- [ ] 文件缺失、Prompt 不可信、同名不同 hash、跨组织和并发变化均阻止或部分挂起，不伪造完成。
- [ ] 切换后新人训练 Legacy writer 无前端/API 消费者，旧数据仍可只读审计。
- [ ] 回滚演练恢复旧 ReleasePlan，历史 Attempt/Outcome/Evidence 不丢失。

## Minimal Verification

- 迁移纯映射单元测试；空库、当前 Legacy fixture、重复 apply、冲突和缺文件集成测试。
- OpenAPI/consumer/architecture gate 证明无新人 Legacy writer 回流。
- 一个真实开发库 dry-run；只有明确目标环境和计划后才 apply。
- 针对性浏览器验证新 Enrollment 看到 PPT/Demo；不运行全站测试。
- 迁移涉及核心跨模块接口，允许运行 Foundation migration/release/learner 相关完整套件。

## Out of Scope

- 不迁移历史录音、旧评分结果、旧 Coach 会话或缺 lineage 的正式 Evidence。
- 不自动迁移活跃 Enrollment。
- 不删除仍服务其他产品域的 `sales_trainer` 数据和功能。
- 不建立长期双读、双写或隐式兼容 Facade。

## Risk And Rollback

- 风险等级：P1；若面向生产执行则按 P0 数据变更标准审批。
- apply 前必须备份/导出映射和 active ReleasePlan；所有写入可通过发布指针回滚，迁移记录追加保留。

## Likely Areas

- 新 `backend/scripts/migrations/` 或项目既定 migration command；
- Legacy material/asset revision 只读 adapters；
- Foundation learning/audio/path/release application ports；
- Legacy route/importer retirement tests 和迁移管理工作区。

## Execution Constraints

遵守父任务 [`execution-policy.md`](../07-19-newcomer-training-content-authoring-closure/execution-policy.md)，未获得目标环境明确授权不得执行 apply。

