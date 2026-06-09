# 发布治理修订模型实现型 Goal 提示词

复制下面整段 `/goal` 命令开启实现目标模式。

```text
/goal 基于当前仓库 `/Users/zhaozengqing/github/销售训练qoder`，按照 `.omo/plans/published-governance-revision-plan.md`、`.omo/plans/published-governance-revision-execution-pack.md`、`.omo/plans/published-governance-revision-acceptance-checklist.md`、`.omo/plans/published-governance-revision-test-matrix.md`、`.omo/plans/published-governance-revision-risk-register.md` 分阶段落地统一发布治理修订模型。目标是把全系统里“发布后不可修改 / 只能复制草稿 / 管理员被迫理解底层状态机”的治理方式，升级为管理员可自然编辑、系统底层自动生成新修订、冻结历史快照、只影响未来、可审计、可回滚、可显式高风险重评的统一模型：`logical_id + revision_id + active pointer + immutable snapshot + audit + rollback + regrade`。

执行前必须读取并遵守：`AGENTS.md`、`CLAUDE.md`、`CONTEXT.md`、`backend/AGENTS.md`、`backend/src/sales_trainer/AGENTS.md`、`web/src/app/admin/sales-trainer/AGENTS.md`、`docs/api-contract/sales-trainer.md`、`docs/architecture/config-asset-center.md`、`docs/adr/2026-05-27-config-asset-b2-hitl-governance.md`、`.trellis/spec/backend/index.md`、`.trellis/spec/frontend/index.md`、`scripts/critical-quality-gate.sh`、`web/package.json`、`backend/pyproject.toml`。不得把业务规则、文案、阈值、流程开关、权限映射散落或硬编码在页面/路由；后端路由不得直接改 ORM，必须通过 service/rules/audit/permission 层；用户可见名称必须是“新人训练路径”，`sales_trainer` 只作为兼容技术命名。

请按依赖顺序实施，不要先改 UI 文案掩盖底层问题：

阶段 0：全局对象盘点和契约基线。先更新或新增契约文档，明确 `logical_id`、`revision_id`、`active_revision_id`、`working_revision_id`、`snapshot`、`binding_revision`、`rollback`、`regrade_run`、`audit_event`；列出所有当前 draft-only 锁点、所有运行时 snapshot 字段和所有 in-scope/out-of-scope published 对象。必须说明 `ConfigVersion` 不满足直接作为 immutable revision 存储，只能复用 lifecycle 体验。

阶段 1：统一 revision/snapshot/audit 基础设施。新增或等价实现不可变 revision 存储、active pointer、audit event、字段风险分类、impact preview。published revision payload 不可原地修改；active pointer 变更只影响未来；rollback 只移动 active pointer；高风险字段包括正确答案、分值、通过线、AI 评分 prompt、评分规则集，不能被普通配置降级为低风险。

阶段 2：优先改新人训练路径配置中心。把 `/admin/sales-trainer/paths` 从 Unit 聚合诊断页升级为路径级发布配置真源，建立 `newcomer_training_path_v1` 或等价 logical object；从 `SalesTrainerUnit.config.path` backfill；`new_seller_modules_v1` 只读兼容；学员端首页从 path active revision 读取模块标题、顺序、启停、说明、按钮、绑定状态和解锁规则。配置中心必须支持编辑、保存 working revision、发布、回滚、历史版本、学员端预览和运维诊断。

阶段 3：迁移 `sales_trainer` 资产。训练单元、商务技巧文章绑定、考卷、题目、录音评分标准、训练材料主档与版本、AI prompt 都要接入 `logical_id + revision_id + active pointer` 或等价模型；考卷 revision 固化题目 revision refs、顺序、分值、通过线、评分策略；题目 revision 固化题干、类型、选项、正确答案、解析、分值、AI prompt；材料版本保留文件 hash 和 current pointer；商务技巧文章绑定进入 path/module binding revision；quiz attempt 和 audio submission/result 必须补 revision lineage，旧数据无法可靠匹配时标记 `legacy_snapshot_only`，不得伪造历史 revision。

阶段 4：改管理端自然编辑 UI。管理员页面统一文案为“编辑将生成新修订，只影响后续学员”；列表、详情、编辑、历史版本抽屉、发布确认、回滚确认、影响范围预览、重评弹窗、操作日志摘要必须闭环。普通管理员默认不显示 `module_key`、`unit_id`、`paper_key`、`path_key`、`sales_trainer`、raw JSON config；这些字段只在诊断展开区出现。不要把“复制草稿 / 换绑”作为普通编辑主路径。

阶段 5：对齐 `curriculum_practice`。将 `PracticeTemplate`、`CaseItem`、`RoleProfile`、`ExaminerAgent`、`LearningContent`、通用 TestBank Question 对齐 revision 语义；保留并升级 `published_asset_refs`，让其引用 revision id + hash；`curriculum_snapshot` 增加 revision lineage；发布门禁和回滚门禁都要校验依赖资产可用；旧 session snapshot 不得从 latest asset 重建。

阶段 6：统一权限、审计、诊断、回滚、重评。权限至少区分超级管理员、内容管理员、培训负责人、运维人员、学员。所有发布、回滚、归档、重评、绑定变更、路径配置变更必须写审计事件，字段至少包含 actor、action、target、before/after 或 before_revision/after_revision、reason、trace_id、created_at、影响范围。运维诊断页必须显示 active revision、绑定 revision、缺失依赖、草稿/归档引用、ASR 配置、AI 评分服务配置、最近错误码、legacy 数据量和修复入口。重评历史记录必须是显式高风险动作，需权限、范围预览、原因、before/after、trace_id，默认追加 regrade result，不覆盖原始结果。

阶段 7：测试和浏览器验收。必须补充后端 unit/integration/contract 测试、前端 Vitest、浏览器验收证据。验证命令使用真实命令：`cd web && npx tsc --noEmit`、`cd web && npm test` 或聚焦 `cd web && npx vitest run 'src/app/admin/sales-trainer/paths/page.test.tsx' 'src/lib/sales-trainer/config-center.test.ts' 'src/lib/sales-trainer/admin-display.test.ts'`、`cd backend && venv/bin/python -m pytest tests/unit/test_newcomer_training_path_papers.py tests/unit/test_newcomer_training_path_audit_logs.py tests/integration/test_newcomer_training_path_paper_api.py --no-cov`、必要时 `cd backend && venv/bin/ruff check src/`、`cd backend && venv/bin/mypy src/`、`cd backend && venv/bin/alembic upgrade head`，最终执行 `bash scripts/critical-quality-gate.sh`。如果全量命令因既有失败无法通过，必须保存失败输出，说明是否与本次变更相关，并提供聚焦测试替代证据，不能谎称通过。

浏览器验收必须覆盖：管理员编辑已发布商务技巧考卷题目后，旧学员考试记录仍显示旧题，新学员看到新题；管理员编辑 AI prompt 后，旧评分仍能解释旧 prompt 或旧 prompt hash，新评分使用新 prompt；管理员回滚路径配置后，新学员看到回滚后的路径，旧 attempt/session/result 不变；运维诊断页能定位缺绑定、非法引用、服务配置和最近错误码；操作日志能查到发布、回滚、绑定变更和重评事件。

失败标准必须严格执行：只要管理员仍需理解复制草稿/换绑才能普通编辑，就判失败；只要历史学员记录被新内容污染，就判失败；只要 UI 仍把 `module_key`/`unit_id`/`paper_key`/`sales_trainer` 当主要概念，就判失败；只要“回滚”没有 API/审计/未来生效语义，就判失败；只要路径配置中心仍只是 Unit 聚合视图，没有路径级发布配置真源，就判失败；只要测试不覆盖历史快照、未来生效、审计和权限，就判失败；只要高风险重评能无原因、无范围、无 before/after、无 trace_id 地覆盖历史成绩，就判失败。

完成时请给出：修改文件清单、可配置项清单、稳定代码规则及原因、配置读取/管理/校验/兜底/权限/审计说明、执行过的验证命令和结果、浏览器验收证据、已知既有失败证据、残留风险。不要提交 git commit，除非用户另行要求。
```
