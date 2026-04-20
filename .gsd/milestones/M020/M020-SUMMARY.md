---
id: M020
title: "Security / multi-instance runtime / recovery hardening"
status: complete
completed_at: 2026-04-14T01:19:17.475Z
key_decisions:
  - D219 — Codify explicit auth transport authority and treat websocket query token plus env password paths as compatibility only.
  - D220 — Document shipped auth authority plus compatibility off-ramp conditions rather than aspirational hardening.
  - D221 — Adopt an allowlist-first admin/support log redaction policy.
  - D222 — Make backend-supplied ordered diagnostics and policy metadata the only admin logs visibility contract.
  - D223 — Require future admin/support observability surfaces to reuse the same diagnostics contract.
  - D224 — Keep SessionManager as process-local live websocket authority and SessionStateService as shared reconnect authority.
  - D225 — Expose live runtime diagnostics and restart-safe snapshot diagnostics on separate runtime surfaces.
  - D226 — Keep /api/v1/support/runtime as release-health summary rather than cluster-state control surface.
  - D227 — Use scripts/recovery_drill_baseline.py as the single recovery-drill authority inventory.
  - D228 — Have the recovery runner execute baseline metadata directly and emit summary/log evidence.
  - D229 — Pair single-node deploy health with repo-local drill evidence for release/recovery proof.
key_files:
  - backend/src/common/auth/service.py
  - backend/src/common/auth/api.py
  - backend/src/sales_bot/websocket/router.py
  - web/src/lib/api/client.ts
  - backend/src/common/monitoring/logger.py
  - backend/src/admin/api/system_logs.py
  - web/src/app/admin/logs/page.tsx
  - backend/src/common/websocket/session_manager.py
  - backend/src/common/websocket/session_state_service.py
  - backend/src/sales_bot/websocket/stepfun_realtime_handler.py
  - scripts/recovery_drill_baseline.py
  - scripts/recovery_drill_runner.py
  - backend/scripts/bootstrap_auth_admin.py
  - docs/setup/auth-local.md
  - docs/api-contract/websocket.md
  - docs/api-contract/support-runtime.md
  - docs/backup-recovery-runbook.md
  - .sisyphus/deploy/ai-backend.service
  - .sisyphus/deploy/ai-frontend.service
  - .sisyphus/deploy/ai-practice.nginx.conf
lessons_learned:
  - Production hardening held only when each concern had one code-owned authority seam and downstream docs/tests rendered that seam rather than reinterpreting it locally.
  - Safe observability requires backend-owned policy plus explicit rendering contracts; leaving API/UI to rediscover 'safe fields' reopens leakage drift immediately.
  - Runtime visibility must be split by survivability: process-local live connection truth and restart-safe shared snapshot truth are different operational surfaces.
  - Recovery proof is a paired evidence problem: node-local `/health` is necessary but insufficient without the latest repo-local drill summary/log evidence.
---

# M020: Security / multi-instance runtime / recovery hardening

**Closed M020 by hardening auth transport, admin/support observability redaction, websocket runtime authority, and executable recovery-drill evidence into one production-truth baseline.**

## What Happened

M020 took four previously loose or partially implicit production seams and turned them into explicit, code-owned authority lines with focused proof. S01 hardened auth transport around one shared backend seam: non-development session/CSRF cookies are forced `Secure`, cookie-backed unsafe requests require double-submit CSRF validation, websocket auth resolves as `Authorization -> session cookie -> query token compatibility`, and login compatibility is exposed through explicit auth-authority headers instead of hidden fallback behavior. S02 then applied the same “one authority seam” pattern to observability: `StructuredLogger`, `/api/v1/admin/system-logs`, and `/admin/logs` now share one allowlist-first diagnostics contract so support/admin retain `trace_id`/`error_code`/`phase`/`session_id`/`target_user_id` while raw details, exact identifiers/IPs, and secret-adjacent provider/request/config payloads remain backend-only. S03 made runtime survivability boundaries explicit by keeping `SessionManager` as the process-local live websocket authority and `SessionStateService` as the shared Redis reconnect-snapshot authority, while preserving request/pacing continuity and intentionally excluding stale `latest_action_card` UI from reconnect persistence. S04 converted the prior markdown-only recovery baseline into a repo-local drill inventory and runner, aligned deploy/support/runbook surfaces to the same authority metadata, and produced machine-readable drill evidence that shows both passing recovery checks and the still-open Alembic revision-drift blocker truthfully.

The milestone therefore delivered the promised production-hardening outcome as an assembled system, not four isolated slice claims: auth transport, safe diagnostics exposure, reconnect/restart semantics, and recovery proof now share code-owned seams, focused verification, and matching docs/runbooks. The most important milestone-level behavior change is epistemic as much as technical: compatibility paths are no longer silent defaults, support surfaces are no longer free to reinterpret sensitive payloads, process-local versus shared-state runtime visibility is no longer ambiguous, and recovery readiness can no longer be overclaimed from `/health` alone.

## Decision Re-evaluation

| Decision | Re-evaluation | Evidence | Revisit next milestone? |
| --- | --- | --- | --- |
| D219 | Still valid. The explicit HTTP bearer-or-cookie, websocket bearer/cookie-first with query-token compatibility, and managed-password authority line matches shipped code. | S01 summary plus focused auth/websocket proof. | Revisit only when query-token and env-password compatibility paths are retired. |
| D220 | Still valid. Docs/contracts now describe shipped authority plus compatibility off-ramp conditions instead of aspirational hardening. | S01 updated docs and architecture scan. | No immediate revisit. |
| D221 | Still valid. Allowlist-first masking preserved triage value without re-exposing raw details. | S02 logger/API/UI contract and redaction tests. | No. |
| D222 | Still valid. Backend-owned ordered `diagnostics` plus policy metadata kept logger/API/UI aligned. | S02 API/UI contract and page test. | No. |
| D223 | Still valid. Future admin/support observability work should continue to reuse the same diagnostics contract. | S02 inventories and architecture scan. | Revisit when M021 quality/cost/failure surfaces ship. |
| D224 | Still valid. Process-local live connection truth and Redis reconnect-snapshot truth remain separate and explicit. | S03 runtime authority summary and reconnect proof. | No. |
| D225 | Still valid. Runtime diagnostics belong on tracked live sessions while restart-safe snapshot fields belong on `SessionStateService` stats. | S03 status-contract tests and docs. | No. |
| D226 | Still valid. `/api/v1/support/runtime` remains a release-health summary, not a cluster drain API. | S03 docs/runbook alignment. | Revisit only if real orchestrator/LB-aware drain controls are introduced. |
| D227 | Still valid. One repo-local drill inventory is the correct recovery authority seam. | S04 baseline script and tests. | No. |
| D228 | Still valid. The runner now executes baseline metadata directly and emits per-drill logs plus `summary.json` evidence. | S04 runner proof and fresh baseline check. | No. |
| D229 | Still valid. Single-node deploy health must still be paired with drill evidence for recovery/release proof. | S04 deploy docs plus recorded `db_migration` blocker despite healthy-node checks. | Revisit when multi-instance deployment and orchestrated drain become real. |

## Success Criteria Results

Roadmap acceptance for M020 was verified against the slice overview `After this` outcomes. The roadmap did not provide a separate success-criteria block, so milestone close-out used those explicit shipped outcomes as the acceptance source.

- [x] **Auth/cookie/websocket transport policy became real code plus focused tests rather than compatibility-default guesswork.** Evidence: S01 closed on `backend/src/common/auth/service.py`, `backend/src/common/auth/api.py`, `backend/src/sales_bot/websocket/router.py`, and `web/src/lib/api/client.ts`; backend proof (`test_auth_login_api.py`, `test_password_reset_api.py`, `test_websocket_status_contract.py`) passed with 35 tests green; frontend auth transport proof (`client.auth.test.ts`, `auth-handler.test.ts`) passed with 16 tests green; the shipped docs now encode the same authority line.
- [x] **Support/admin diagnostics are useful without leaking sensitive fields.** Evidence: S02 unified `backend/src/common/monitoring/logger.py`, `backend/src/admin/api/system_logs.py`, `web/src/app/admin/logs/page.tsx`, and the supporting inventories; backend redaction/API proof passed (`test_system_logs_redaction.py`, `test_admin_users_api.py`, `test_admin_users_api_models.py`), and the frontend admin logs page test passed while rendering only backend-supplied masked diagnostics.
- [x] **Runtime connection visibility, session snapshot, reconnect, and drain semantics are explicit for single-instance and multi-instance reasoning.** Evidence: S03 made `SessionManager.get_stats()` the process-local live-connection authority and `SessionStateService.get_stats()` the shared Redis snapshot authority; focused backend proof (`test_websocket_status_contract.py`, `test_sales_realtime_reconnect_flow.py`) passed 11/11 with request epoch continuity, pacing-state persistence, and non-persistence of stale action-card UI verified.
- [x] **The M018 recovery baseline was upgraded into executable drills/scripts that validate the hardened seams.** Evidence: S04 shipped `scripts/recovery_drill_baseline.py` and `scripts/recovery_drill_runner.py`, recorded fresh drill evidence under `.dev/recovery-drills/20260414T010316Z/summary.json`, and revalidated the authority inventory. In this close-out turn, `python3 scripts/recovery-drill-baseline.py check` passed fresh and confirmed all referenced authority paths exist. The drill bundle truthfully records the still-open `db_migration` Alembic blocker instead of masking it behind healthy-node status, which is consistent with the shipped recovery-proof contract.

Horizontal checklist note: the roadmap did not expose a separate Horizontal Checklist section, so there were no additional unchecked horizontal items to carry forward beyond the explicit follow-ups recorded below.

## Definition of Done Results

- [x] **All roadmap slices are complete.** Fresh `gsd_milestone_status(M020)` shows S01-S04 all `complete`, each with 3/3 tasks done.
- [x] **All slice close-out artifacts exist.** `find .gsd/milestones/M020/slices -maxdepth 2 \( -name 'S*-SUMMARY.md' -o -name 'S*-UAT.md' \)` confirmed summary and UAT artifacts for S01, S02, S03, and S04.
- [x] **The milestone shipped real non-`.gsd` code/docs, not planning artifacts only.** A fresh branch diff against the repository's real integration branch (`origin/001-ai-practice-system`) showed non-`.gsd` changes across the auth, observability, websocket-runtime, recovery-drill, deploy, docs, and frontend seams touched by M020.
- [x] **Cross-slice integration closure is satisfied where the roadmap established real dependency-bearing seams.** S04 explicitly requires and consumes S01's auth/bootstrap authority, S02's allowlist-first diagnostics contract, and S03's SessionManager/SessionStateService authority split; its drill inventory, runner, runbook, deploy bundle, and support-runtime contract are written on top of those upstream seams. S03 itself had no declared upstream dependencies, so the absence of extra consumer prose for informal `affects` relations was treated as a documentation caveat, not a delivery failure.
- [x] **Verification evidence is present across contract, integration, and operational classes.** Slice summaries record focused backend/frontend tests for auth, admin redaction, websocket reconnect/runtime, and recovery-drill automation; this close-out turn also reran the recovery baseline inventory check successfully.
- [x] **No extra roadmap checklist sections were left unverified.** The roadmap used slice-overview outcomes as the acceptance source and did not define a separate horizontal checklist or standalone definition-of-done block beyond assembled slice completion and shipped outcome proof.

## Requirement Outcomes

No requirement status transitions were applied during M020 close-out, so no `gsd_requirement_update` calls were needed.

- **R001** remained active. Evidence from S03 advances reconnect/runtime continuity semantics, but the milestone did not claim full end-to-end validation of the broader multi-round stability requirement.
- **R002** remained active. Evidence from S01, S03, and S04 advances diagnosable recovery/degradation paths for auth, websocket, reconnect, and recovery-drill surfaces, but the milestone did not claim full validation across the entire ASR/LLM/TTS/knowledge-retrieval failure surface.

This milestone therefore advanced requirement evidence without over-claiming validation or changing requirement statuses.

## Deviations

Milestone close-out did not widen scope to repair the already-exposed Alembic revision blocker. Instead, M020 kept the promised recovery-hardening outcome focused on making the drill inventory, runner, deploy/runbook contract, and failure evidence truthful and executable. Requirement evidence for R001/R002 was advanced, but neither requirement was reclassified as validated in this milestone.

## Follow-ups

1. Repair the missing Alembic revision / migration-graph state behind `20260412_0315_028`, then rerun the `db_migration` drill until the recovery bundle is fully green.
2. Keep future M021 quality/cost/failure admin-support surfaces on S02's backend-owned diagnostics contract instead of inventing a second support payload.
3. Keep future multi-instance/runtime work on S03's SessionManager-vs-SessionStateService authority split and add real orchestrator/LB-aware drain controls outside `/api/v1/support/runtime` if cluster rollout is introduced.
4. Retire websocket query-token and env-password compatibility paths once their remaining callers are migrated to the hardened auth authority line.
