# 2026-04-24 业务规则配置后台治理计划

## Goal

把首批可调整业务规则从代码默认值、env JSON 和前端固定数组收敛到可版本化、可校验、可审计、可回滚的治理流程。首批域仅覆盖 PRD 指定范围：成就、AI 教练、下一次练习推荐、销售训练组合。

## Non-goals

- 不启用自适应难度。
- 不开放外部分享或企业微信分享。
- 不做视觉重设计或新的后台框架。
- 不引入新依赖；如必须引入，需单独 ADR。
- 不把规则后台化作为重写 StepFun、report、practice 页面的理由。

## Configuration Domains

| Domain | Example keys | Runtime reader | Admin capability | Safe fallback |
| --- | --- | --- | --- | --- |
| 成就 | `achievement.rules`, badge order, unlock copy | growth/achievement service | draft, validate, preview, publish, rollback | 无 active rules 时不解锁新徽章 |
| AI 教练 | `ai_coach.trigger_rules`, notification templates, frequency limit | notification/coach service | draft template/rule, preview target count, publish | 默认 disabled；模板缺失不发送 |
| 下一次练习推荐 | `recommendation.ruleset_version`, weakness threshold, priority order | recommendation service/report surface | dry-run sample sessions, publish | 使用安全默认 ruleset；非法 active 回退上一版本 |
| 销售训练组合 | scenario bundle ordering, visible labels, default personas | training runtime/API | preview frontend payload, publish | API 失败时前端使用兜底数组并记录 fallback reason |

## Required Field Contract

每个配置项必须记录并能在后台展示：

- `key`：稳定配置键。
- `domain`：所属业务域。
- `schema_version`：配置 schema 版本。
- `value`：JSON 值或模板内容。
- `default_value`：安全默认值。
- `type`：int、choice、string、template、rule_json、ordered_list 等。
- `range_or_allowlist`：范围、枚举或 schema。
- `read_path`：运行时读取位置。
- `admin_entry`：管理入口。
- `permission`：可查看、可草稿、可发布角色。
- `audit_policy`：mutation 必写字段。
- `fallback_policy`：缺失、非法、停用时行为。
- `rollback_policy`：上一 published version 或默认 disabled。

## Data and API Shape

### Tables / records

1. `business_rule_configs`
   - `id`, `domain`, `key`, `schema_version`, `status` (`draft|published|archived|disabled`), `version`, `value`, `default_value`, `created_by`, `updated_by`, `created_at`, `updated_at`。
2. `business_rule_config_audit_logs`
   - `id`, `config_key`, `action` (`create_draft|preview|publish|rollback|disable`), `actor_id`, `before_version`, `after_version`, `reason`, `trace_id`, `created_at`。
3. Optional read model per domain only after generic records prove insufficient; do not fork one-off tables prematurely.

### Admin APIs

- `GET /admin/business-rules?domain=...`：列表和 active/draft 状态。
- `POST /admin/business-rules/{key}/drafts`：创建或更新 draft；非 admin/运营授权角色拒绝。
- `POST /admin/business-rules/{key}/validate`：schema 校验，不写 active。
- `POST /admin/business-rules/{key}/preview`：返回影响摘要，不改变 active version。
- `POST /admin/business-rules/{key}/publish`：admin-only，写 actor/before/after/version/reason/trace_id。
- `POST /admin/business-rules/{key}/rollback`：admin-only，回滚到上一 published version。

## Phase Plan

### Phase 1: Read-only inventory and schema lock

- 盘点四个域当前读取位置、默认值、env JSON、前端兜底数组。
- 为每个配置项补字段合同表，确认默认值和非法处理。
- 先写 schema 和 resolver tests，不改用户可见行为。

Exit criteria:

- 配置清单覆盖四个域。
- 每项都有默认值、类型、范围、读取位置、权限、审计、兜底、回滚说明。
- 缺失/非法/停用/回滚测试计划明确。

### Phase 2: Resolver and audit foundation

- 增加统一 resolver：读取 active config，schema 校验，非法时回退 safe default 或上一有效版本。
- 增加 audit writer：mutation 统一写 actor/before/after/version/reason/trace_id。
- 后台 mutation 先接入一个低风险域（推荐规则或 AI 教练模板），验证流程。

Exit criteria:

- 非 admin mutation 被拒绝。
- invalid schema publish 被拒绝。
- preview 不影响 active version。
- publish/rollback 审计字段完整。

### Phase 3: Domain rollout

- 成就：规则发布后只影响未来 unlock，不反向改历史 unlock。
- AI 教练：模板和触发条件后台化；频率限制由 resolver 提供。
- 下一次练习推荐：ruleset 版本化，报告展示推荐依据。
- 销售训练组合：API 成功时前端渲染服务端配置，失败时使用兜底并展示/记录 fallback reason。

Exit criteria:

- 四个域都有 resolver 命中、缺失、非法、停用、回滚测试。
- 权限、审计、隐私说明通过验证。
- 未启用非目标功能。

## Test Strategy

- Backend unit: resolver valid/missing/invalid/disabled/rollback。
- Backend integration: admin create draft, non-admin mutation rejected, invalid publish rejected, preview no active change, publish/rollback audit log。
- Frontend/admin: list, edit draft, validation error, preview summary, publish confirmation。
- Domain tests: 成就不反写历史、AI 教练模板缺失不发送、推荐 fallback、销售组合 API failure fallback。

Recommended commands from the roadmap:

```bash
cd backend && .venv-test/bin/python -m pytest tests/unit/common tests/integration -q --no-cov
cd backend && ruff check src tests --quiet
pnpm --dir web exec tsc --noEmit --pretty false
pnpm --dir web exec vitest run --reporter=dot
```

Use narrower focused tests for each slice before running the broader commands.

## Rollback

- Runtime reads keep the last known good `published` config in preference to a broken active candidate.
- Admin rollback creates a new audit action and points active to the selected prior version.
- If the config service is unavailable, non-critical domains degrade to safe defaults; critical scoring/recommendation domains must surface fallback reason in diagnostics/report copy.
