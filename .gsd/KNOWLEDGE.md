# Knowledge

- Admin completed-session previews must batch-load `ConversationMessage` rows and run `SessionEvidenceService.build_projection(...)` instead of reusing the legacy 0.4/0.3/0.3 weighting; otherwise admin tables drift from `/practice/{sessionId}/report` even when both point at the same session.
- If local runtime UAT for `/admin/users/{id}` or `/api/v1/admin/users/{id}/sessions` suddenly looks like a frontend/CORS regression, check Alembic first: missing revision `20260317_2310_020` breaks projection reads with `conversation_messages.transcript_metadata does not exist` and can surface in the browser as failed session-preview requests.
- Report-page focused tests need an explicit assertion that `导出报告` is absent; otherwise the dead affordance can drift back into `web/src/app/(user)/practice/[sessionId]/report/page.tsx` without breaking the existing positive-path assertions.
