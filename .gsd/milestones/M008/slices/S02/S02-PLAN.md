# S02: knowledge-check 与 report 共用检索真相

**Goal:** 让 `/knowledge-check` 和 canonical report 通过 `runtime_diagnostics` + `SessionEvidenceService` 读取同一条 persisted retrieval ledger，并对同一 session 给出一致解释。
**Demo:** After this: 对同一条 completed session 连续请求 `/api/v1/practice/sessions/{id}/knowledge-check` 和 `/api/v1/practice/sessions/{id}/report`，两边返回一致的 retrieval 事实与分层解释。

## Tasks
