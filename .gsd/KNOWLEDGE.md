# Knowledge

- Admin completed-session previews must batch-load `ConversationMessage` rows and run `SessionEvidenceService.build_projection(...)` instead of reusing the legacy 0.4/0.3/0.3 weighting; otherwise admin tables drift from `/practice/{sessionId}/report` even when both point at the same session.
