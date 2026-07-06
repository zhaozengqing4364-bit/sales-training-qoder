# phase-3-publish-impact-preview-slice-1

## Goal

为新人训练路径配置补一个管理端 `publish preview` 第一切片。发布前先给出影响范围、风险等级、审计字段与回滚提示；严格复用现有 publish 校验，禁止从 legacy backfill 伪造可发布预览。

## What I already know

- 用户明确限制本次只做后端，不做前端、数据库迁移或 realtime/runtime 接入。
- 允许修改文件范围仅包含 `path_config_api.py`、`path_config_service.py`、`schemas.py`、相关测试和 `docs/api-contract/sales-trainer.md`。
- 现有 `SalesTrainerPathConfigService.publish_config()` 已是发布权威：要求 working revision、执行 `validate_path_payload_for_write()`、`_validate_ai_coach_prompt_bindings()`、`_validate_publish_payload()`，然后调用 asset revision publish。
- 现有 `/path-config/rollback/preview` 已定义 impact/audit 响应风格，可作为 `publish preview` 的对齐基线。
- API 契约已明确：`legacy_snapshot_only=true` 只能用于管理端迁移/诊断，不得把 unit backfill 当成 active revision 或正式发布真源。

## Assumptions (temporary)

- `publish preview` 第一切片不落库、不写操作日志，只返回与未来发布动作一致的治理信息。
- `risk_level` 可先按现有 revision `change_class` 与是否变更 active revision 做静态映射，不额外引入新治理枚举表。
- 不修改 `asset_revision_service` 发布语义；preview 只复用发布前校验和 revision snapshot。

## Open Questions

- 无阻塞问题；当前代码与用户要求足以实现最小切片。

## Requirements (evolving)

- 新增 `POST /api/v1/admin/newcomer-training/path-config/publish/preview`。
- 权限与 `publish` 相同，若待发布修订涉及 AI 教练高风险字段，则仍需 `sales_trainer.manage_prompts`。
- 无 working revision 时返回 `[NEWCOMER_PATH_WORKING_REVISION_REQUIRED]`，且 message 明确禁止从 legacy backfill 直接预览发布。
- preview 必须复用现有 publish 校验；坏 payload、PromptTemplate 绑定错误、realtime placeholder/runtime binding 非法等都必须 typed fail。
- preview 响应至少包含：
  - `active_revision_id`
  - `working_revision_id`
  - `will_change_active_revision`
  - `future_learner_paths_changed`
  - `historical_attempts_changed=false`
  - `historical_submissions_changed=false`
  - `historical_regrade_required=false`
  - `affected_module_keys`
  - `changed_module_keys`
  - `requires_reason`
  - `requires_trace_id`
  - `rollback_available`
- 响应还需要覆盖风险等级、审计字段、回滚提示。
- 更新 API 契约文档。

## Acceptance Criteria (evolving)

- [ ] `publish preview` 在存在 working revision 时返回成功响应，包含影响范围、风险等级、审计字段、回滚提示。
- [ ] 无 working revision 时返回 `[NEWCOMER_PATH_WORKING_REVISION_REQUIRED]`。
- [ ] 至少一个发布前校验阻断场景通过 preview 暴露 typed fail。
- [ ] `pytest --no-cov tests/integration/test_newcomer_training_path_config_api.py -q` 通过。
- [ ] `ruff check src/sales_trainer/path_config_api.py src/sales_trainer/services/path_config_service.py tests/integration/test_newcomer_training_path_config_api.py` 通过。

## Definition of Done (team quality bar)

- Tests added/updated (integration and/or unit where appropriate)
- Lint passes for touched backend files
- Docs updated for API contract changes
- No unrelated file changes or formatting churn

## Out of Scope (explicit)

- 前端展示
- 数据库模型 / Alembic migration
- realtime runtime 真正接入或发布执行
- `asset_revision_service` 基础发布语义调整

## Technical Notes

- 需对齐现有 `rollback_preview()` 响应结构与 `newcomer_path_config.publish` 审计事件字段。
- 需保留 active revision 与 working revision 的分离语义，只影响未来学员。
