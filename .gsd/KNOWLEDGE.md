# Knowledge

- Admin completed-session previews must batch-load `ConversationMessage` rows and run `SessionEvidenceService.build_projection(...)` instead of reusing the legacy 0.4/0.3/0.3 weighting; otherwise admin tables drift from `/practice/{sessionId}/report` even when both point at the same session.
- If local runtime UAT for `/admin/users/{id}` or `/api/v1/admin/users/{id}/sessions` suddenly looks like a frontend/CORS regression, check Alembic first: missing revision `20260317_2310_020` breaks projection reads with `conversation_messages.transcript_metadata does not exist` and can surface in the browser as failed session-preview requests.
- Report-page focused tests need an explicit assertion that `导出报告` is absent; otherwise the dead affordance can drift back into `web/src/app/(user)/practice/[sessionId]/report/page.tsx` without breaking the existing positive-path assertions.
- Standard PPT 这条链的 live contract 在 `/api/v1/presentations`，不是旧的 `/api/v1/admin/presentations`：当前 admin 详情页与用户演练入口都直接消费 `api.presentations`，而 legacy admin backend 仍引用过期 schema；做 replace/version_number/status 修复时应扩展 live surface。
- 本地要跑 S04 presentation/runtime UAT 时，`cd backend && PYTHONPATH=src venv/bin/uvicorn main:app --port 3444` 可能因缺少 `redis` Python 包在启动阶段崩溃并报 `redis package is required for SessionStateService`；先补齐该本地依赖，否则浏览器验证会被环境问题卡住而不是代码回归。
