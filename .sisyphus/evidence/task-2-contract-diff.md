# T2 契约与共享类型基线收敛

日期：2026-04-15

## Scope

- Docs: `docs/api-contract/README.md`, `agents.md`, `analytics.md`, `model-configs.md`, `sessions.md`, `replay.md`
- Backend truth sources: `backend/src/agent/schemas.py`, `backend/src/agent/api/agents.py`, `backend/src/common/api/analytics.py`, `backend/src/admin/api/analytics.py`, `backend/src/admin/api/model_configs.py`, `backend/src/common/db/schemas.py`, `backend/src/common/api/practice.py`, `backend/src/common/conversation/api.py`, `backend/src/common/conversation/replay.py`
- Frontend typing surface: `web/src/lib/api/types.ts`, `web/src/lib/api/client.ts`, `web/src/app/admin/settings/page.tsx`

## Result Summary

- `admin/settings` 的 model-config API 形状不再在页面里本地维护；共享 snake_case API 类型现在集中在 `web/src/lib/api/types.ts`。
- `web/src/lib/api/client.ts` 改为直接消费共享 `AdminModelConfig*` 类型，且不再把 `/admin/model-configs` 声明成“分组对象或旧数组”二选一的漂移返回值。
- 文档已对齐两处高置信度 drift：`model-configs.md` 的列表/创建响应，以及 `replay.md` 的 envelope 示例。

## Contract Diff Baseline

### 1. Agents

| Surface | 文档现状 | 代码真值 | 结论 | 处理 |
|---|---|---|---|---|
| `docs/api-contract/agents.md` vs admin/user routes | 文档声明 `/admin/agents` + `/agents`，统一 `{ success, data }` 包裹，分类限制为 `sales/presentation` | `backend/src/agent/api/agents.py` 与 `backend/src/agent/services/agent_service.py` 真实实现一致；`SUPPORTED_AGENT_CATEGORIES = {"sales", "presentation"}` | 基本对齐 | 未改文档 |
| schema 注释 vs API contract | `backend/src/agent/schemas.py` 注释仍提到 `interview/customer_service` | 运行时 service 明确拒绝这些分类并返回 `[AGENT_CATEGORY_RESTRICTED]` | 注释噪音，不构成外部契约变更 | 记录为代码注释噪音，不改文档 |

### 2. Analytics

| Surface | 文档现状 | 代码真值 | 结论 | 处理 |
|---|---|---|---|---|
| open analytics (`/analytics/*`) | `docs/api-contract/analytics.md` 说明 leaderboard / my-rank / dashboard 直接返回 JSON 对象（非 envelope） | `backend/src/common/api/analytics.py` 与文档一致：`/analytics/leaderboard`、`/analytics/leaderboard/my-rank`、`/analytics/dashboard` 都直接返回对象 | 对齐 | 未改文档 |
| admin analytics (`/admin/analytics/*`) | 当前没有 dedicated contract doc | `backend/src/admin/api/analytics.py` 实现了 `/overview`、`/trends`、`/agents`、`/leaderboard`、`/operating-pack`、`/runtime-metrics`、`/policy-effectiveness`、`/voice-mode-comparison`、`/fallback-metrics`、`/export`，且大多数为 `{ success, data, trace_id }` 包裹 | 文档缺口 | 本任务只记录 baseline，不新增整篇 admin analytics 契约文档 |

### 3. Model Configs

| Surface | 文档现状 | 代码真值 | 结论 | 处理 |
|---|---|---|---|---|
| `GET /api/v1/admin/model-configs` | `docs/api-contract/model-configs.md` 仍写成“分页列表”，并声明 `provider/is_active/page/page_size` 查询参数 | `backend/src/admin/api/model_configs.py:list_model_configs` 只接受 `model_type?`，且返回 `{ llm, embedding, asr, tts, total }` 分组对象 | 文档漂移 | 已更新 `docs/api-contract/model-configs.md` |
| `POST /api/v1/admin/model-configs` 返回值 | 文档此前未明确说明创建响应是否为详情 | `create_model_config` 返回 `ModelConfigCreateResponse` 摘要：`id/name/model_type/provider/model_name/is_default/created_at` | 文档遗漏 | 已更新 `docs/api-contract/model-configs.md` |
| 错误码 | 文档只列出基础 CRUD 错误码 | 实现额外暴露 `[MODEL_CONFIG_DUPLICATE]`、`[MODEL_CONFIG_LIST_FAILED]`、`[MODEL_CONFIG_GET_FAILED]`、`[CANNOT_UNSET_DEFAULT]`、`[CANNOT_DELETE_DEFAULT]`、`[ENCRYPTION_ERROR]` | 文档遗漏 | 已更新 `docs/api-contract/model-configs.md` |
| Frontend shared types | `admin/settings` 本地定义 `ModelType/ModelProvider/ModelConfig*`，`client.ts` 也有私有 `AdminModelConfig*` 类型族 | Backend schema authority 在 `backend/src/common/ai/schemas.py`；frontend raw API layer 应保留 snake_case | 前端共享类型漂移 | 已收敛到 `web/src/lib/api/types.ts` + `web/src/lib/api/client.ts` |

### 4. Sessions

| Surface | 文档现状 | 代码真值 | 结论 | 处理 |
|---|---|---|---|---|
| 会话 envelope / lifecycle / report fields | `docs/api-contract/sessions.md` 记录统一 `{ success, data, trace_id }`、lifecycle、`voice_policy_snapshot_ref`、`effectiveness_snapshot`、`retry_entry` | `backend/src/common/db/schemas.py` + `backend/src/common/api/practice.py` 与这些主字段一致 | 主干对齐 | 未改文档 |
| `SessionCreate.focus_intent` | 文档未公开 | `backend/src/common/db/schemas.py:259-262` 接受 `focus_intent`; `backend/src/common/api/practice.py:_build_retry_entry` 会把 retry focus 回写进 `retry_entry.focus_intent` | additive contract gap | 记录为后续是否公开的未决项；本任务未扩大 sessions 文档范围 |

### 5. Replay

| Surface | 文档现状 | 代码真值 | 结论 | 处理 |
|---|---|---|---|---|
| `messages/replay/highlights` 示例 | `docs/api-contract/replay.md` 顶部说统一 envelope，但各端点示例仍是裸 payload | `backend/src/common/conversation/api.py` 真实返回 `ConversationMessagesSuccessResponse` / `ReplayDataSuccessResponse` / `HighlightsSuccessResponse`，均为 `{ success, data, trace_id }` | 文档自相矛盾 | 已更新 `docs/api-contract/replay.md` 示例 |
| `audio` endpoint | 文档说明直接 redirect/file stream | `backend/src/common/conversation/api.py:get_audio` 真实行为一致 | 对齐 | 未改文档 |

## Shared Type Boundary Chosen

- **API layer authority**：`web/src/lib/api/types.ts` 持有与后端 wire format 对齐的 `AdminModelConfig*` snake_case 类型。
- **API client authority**：`web/src/lib/api/client.ts` 直接引用共享类型，不再私有复制 model-config 契约。
- **Page-level boundary**：`web/src/app/admin/settings/page.tsx` 允许对共享类型做 import alias 以保留页面语义，但不再拥有独立 API shape。
- **Internal UI-only state**：`MODEL_TYPE_CONFIG`、`PROVIDER_OPTIONS`、`MODEL_PROVIDER_MAP` 等界面配置继续保留在页面本地；它们不是 wire contract。

## Remaining Follow-ups (not expanded in this task)

1. `docs/api-contract/analytics.md` 之外仍缺一份 dedicated `/admin/analytics/*` 契约文档。
2. `web/src/app/admin/agents/[id]/page.tsx` 仍保留本地 `ModelConfigListItem/ModelConfigListResponse` 镜像类型；本任务按范围只优先处理 `admin/settings` 与共享 client surface。
3. 是否把 `SessionCreate.focus_intent` 从 additive internal field 升级为公开 contract，需要后续任务与 report/replay 需求一起定稿。
