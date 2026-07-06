# Research: implementation scope

- Query: 审计报告 8 项整改全部闭环的可执行实施切片计划
- Scope: internal codebase + existing audit evidence
- Date: 2026-07-06

## Inputs

- Active task: `.trellis/tasks/07-06-architecture-audit-remediation-closure`
- Primary audit: `docs/project-analysis/audit-2026-07-03-independent-architecture-review.md`
- Review evidence: `.trellis/tasks/07-03-2026-07-03/review-evidence.md`
- Earlier research artifact: `.trellis/tasks/07-03-2026-07-03/research/implementation-scope.md`

## CodeGraph note

The repository does have a `.codegraph/` directory. The main session used CodeGraph for the relevant flows:

- `BaseWebSocketHandler send_json ConnectionManager send_json callers`
- `SessionStateService init_session_state_service app_lifespan Redis required health`
- `require_role get_current_admin_user AdminRolePermission sales_trainer permissions prompt_templates permissions current-user roles`
- `metrics track_websocket_connection track_tts_request track_asr_request track_llm_request common monitoring metrics`
- `sales_trainer import curriculum_practice adapter runtime_dependency_contract`
- `practice session report knowledge-check enhanced-report audio segments _can_read_session`

The earlier research file incorrectly stated that CodeGraph was unavailable. Treat that as stale context; code and the main-session CodeGraph checks are the source of truth.

## Minimal closure order

1. Lock runtime failure semantics: `send_json` should return a structured result, increment failure/error metrics, and keep call sites from assuming delivery when the socket send failed.
2. Make Redis startup dependency explicit: default fail-fast remains safest, but optional/disabled modes must be named, tested, and visible through health state.
3. Centralize RBAC vocabulary: replace scattered role sets with a shared backend authority and keep frontend route visibility based on backend capability projection.
4. Add IDOR tests around practice-session sensitive projections: report, knowledge-check, enhanced-report, and report-trends.
5. Expand `critical-quality-gate.sh` only with tests that pass independently.
6. Wire Prometheus helpers from real runtime/business call sites, not only helper-level unit tests.
7. Enforce the sales-trainer/curriculum-practice boundary with an AST scan and a narrow adapter allowlist.
8. For process-local async work, record the durable task contract first; schema/worker rollout should follow the ADR to avoid a half-built queue.

## Known follow-up risks for quality check

- `newcomer_content_admin` exceeds `User.role String(20)`; the role vocabulary fix is not fully closed until the schema width is addressed or the role is no longer stored in that column.
- Existing boundary tests may still fail if old string-scan rules catch non-adapter references in `sales_trainer` services after the new adapter is introduced.
- Prometheus acceptance should verify true call sites for WS and at least one LLM/ASR/TTS or approved helper path; helper tests alone are not enough.
- Async task persistence is a Phase 0 contract/ADR unless a migration, repository, and worker pilot are implemented.
