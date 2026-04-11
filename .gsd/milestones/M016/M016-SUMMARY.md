---
id: M016
title: "Auth / API / admin security contract hardening"
status: complete
completed_at: 2026-04-11T20:48:30.462Z
key_decisions:
  - D188/D189/D190 — keep password reset authority on the service/model/migration seam, enforce lifecycle invariants in the DB, and prove it with focused auth/reset suites
  - D191/D192/D193 — reuse the prompt-template error seam, keep audited route-local 4xx on `error_response(...)`, and keep dependency/auth failures on structured `_raise_auth_http_error(...)` payloads
  - D194/D195/D196 — repair the first legacy admin watch subset at the router modules themselves, centralize shared sink-level redaction, and bound future widening with code-owned inventories plus focused proof
key_files:
  - backend/src/common/services/password_reset.py
  - backend/src/common/db/models.py
  - backend/alembic/versions/20260411_2235_027_password_reset_lifecycle_delivery.py
  - backend/alembic/versions/20260412_0315_028_password_reset_single_active_token.py
  - backend/src/common/auth/api.py
  - backend/src/common/auth/service.py
  - backend/src/presentation_coach/api/presentations.py
  - backend/src/prompt_templates/api/routes.py
  - backend/src/admin/api/security_inventory.py
  - backend/src/common/monitoring/log_safety_inventory.py
  - backend/src/common/monitoring/logger.py
  - web/src/lib/api/client.ts
lessons_learned:
  - In this repository, milestone close-out must compare against `origin/001-ai-practice-system`, not `main`, and backend pytest acceptance should stay serial because repo-root pytest-cov still shares the top-level `.coverage` SQLite file.
  - When a roadmap omits explicit `Success Criteria` or `Horizontal Checklist` sections, the slice overview `After this` outcomes can still be a rigorous acceptance contract as long as the summary records that absence explicitly and ties each outcome to fresh proof.
  - Security hardening stayed tractable because each slice used one authority seam: service/model/migration for password reset, backend/frontend normalization seam for errors, and router/logger inventories for admin security instead of wrapper-local or page-local fixes.
  - Code-owned security inventories were effective at bounding fix-first scope and giving downstream milestones a trustworthy widening point without reopening a blind repo-wide audit.
---

# M016: Auth / API / admin security contract hardening

**M016 turned password reset, audited API error handling, and the first admin security baseline into explicit, durable contracts with fresh focused proof across backend, frontend, and shared observability seams.**

## What Happened

M016 closed three high-risk contract gaps without widening into repo-wide rewrites. S01 formalized auth recovery around the `PasswordResetService` + `PasswordResetToken` + Alembic 026/027/028 seam, added DB-enforced single-active-token lifecycle invariants, and preserved hashed_password-first login compatibility so forgot/reset is durable and auditable instead of handler-local behavior. S02 then reused the existing prompt-template seam to standardize audited prompt-template, presentation, and auth dependency failures onto one outward contract: route-local business 4xx return stable top-level `error/message/trace_id`, dependency/auth/RBAC failures preserve structured `detail={error,message}`, and the web client consumes all of it through `normalizeApiErrorPayload` / `ApiRequestError` instead of page-local guessing. S03 finished the milestone by making the first high-risk admin routers self-guarding at module level, centralizing token/password/cookie/email redaction in `StructuredLogger`, and locking both scopes with code-owned inventories plus focused deny-path and sink-level proof.

These slices integrated cleanly instead of shipping as isolated fixes. S01’s formal auth-recovery and dependency contracts gave S02 and S03 a stable auth error seam; S02’s structured failure contract let admin deny paths remain frontend-normalizable; S03 used the same contract discipline to keep permissions and observability explicit at the router/logger authorities rather than relying on `main.py` wrappers or route-local masking. Fresh milestone-close verification reran the auth/reset gate (25 passed), the audited presentation/error-contract gate (33 passed), the frontend API-client normalization suite (9 passed), and the admin RBAC/logger gate (36 passed), plus a fresh inventory import check showing `fix_first_admin_route_families=0` and `fix_first_sensitive_log_surfaces=0`. Fresh LSP diagnostics were clean on the milestone’s key backend/frontend authority files.

## Decision Re-evaluation

| Decision | Re-evaluation | Status |
| --- | --- | --- |
| D188 / D189 / D190 — keep password reset authority on the service/model/migration seam, enforce lifecycle invariants in DB, and prove auth behavior with narrow focused suites | Still valid. Fresh 25-test auth/reset proof shows the service-model-migration seam and DB-level single-active-token invariant held, while the split auth/reset suites remained sufficient and easier to keep truthful than a new umbrella suite. | Keep |
| D191 / D192 / D193 — reuse the prompt-template seam, keep route-local audited 4xx on `error_response(...)`, and keep dependency/auth failures on structured `_raise_auth_http_error(...)` payloads | Still valid. Fresh backend and web error-contract gates proved the mixed top-level envelope + structured dependency-detail approach is stable and frontend-normalizable without a global FastAPI exception rewrite. | Keep |
| D194 / D195 / D196 — repair the first legacy admin watch subset in router modules themselves, centralize sink-level redaction, and prove the baseline with isolated-router/watch-subset proof plus positive controls | Still valid. Fresh admin/router/logger proof and inventory closure confirmed the fix-first subset is closed and the inventory split still gives the right bounded next step for future widening. | Keep |

No separate `Success Criteria` or `Horizontal Checklist` sections existed in the roadmap file, so close-out used the slice overview `After this` outcomes as the milestone acceptance contract and recorded that absence explicitly instead of inventing extra criteria.

## Success Criteria Results

- ✅ **Password reset/auth recovery became a durable backend contract.** S01 delivered the `PasswordResetService` + `PasswordResetToken` + Alembic 026/027/028 authority seam, lifecycle observability fields, and the DB partial unique index enforcing one active token per user. Fresh proof: `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py backend/tests/integration/test_password_reset_api.py -x -q` passed **25/25**.
- ✅ **Audited high-noise API surfaces now return a stable, shared error contract.** S02 aligned prompt-template, presentation, and auth dependency failures onto the documented top-level envelope / structured dependency-detail split, and `web/src/lib/api/client.ts` remains the single normalization seam. Fresh proof: `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_presentations.py backend/tests/contract/test_practice_evidence_contract.py backend/tests/integration/test_presentation_flow.py -x -q` passed **33/33** and `npm --prefix web test -- --run src/lib/api/client.auth.test.ts` passed **9/9**.
- ✅ **The first admin security baseline is explicit and provable.** S03 moved the fix-first legacy admin routers onto module-level `get_current_admin_user`, centralized token/password/cookie/email redaction in `StructuredLogger`, and closed the fix-first inventories to zero. Fresh proof: `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_admin_users_api.py backend/tests/unit/admin/test_admin_users_api_models.py -x -q` passed **36/36** and a fresh inventory import check returned `fix_first_admin_route_families=0` and `fix_first_sensitive_log_surfaces=0`.
- ℹ️ **Roadmap structure note:** `.gsd/milestones/M016/M016-ROADMAP.md` contains the slice overview but no separate `Success Criteria` section, so milestone acceptance was verified against the three shipped `After this` outcomes above.

## Definition of Done Results

- ✅ **All roadmap slices are complete.** `gsd_milestone_status(M016)` reported S01, S02, and S03 as `complete`, each with `done=3/3` tasks.
- ✅ **All slice summaries exist.** `find .gsd/milestones/M016 -maxdepth 5 -name '*-SUMMARY.md' | sort` returned the three slice summaries plus all nine task summaries.
- ✅ **All slice UAT artifacts exist.** `find .gsd/milestones/M016 -maxdepth 3 \( -name '*-SUMMARY.md' -o -name '*-UAT.md' \) | sort` returned `S01-UAT.md`, `S02-UAT.md`, and `S03-UAT.md` alongside the slice summaries.
- ✅ **Cross-slice integration held.** S02 explicitly reused S01’s formal auth seam for structured auth failures, S03 explicitly depended on S01/S02 for durable auth and error payloads, and the fresh milestone acceptance bundle stayed green across auth/reset, error-contract/frontend normalization, and admin RBAC/logger proof.
- ✅ **The branch contains real non-`.gsd` implementation changes.** `git diff --stat HEAD $(git merge-base HEAD origin/001-ai-practice-system) -- ':!.gsd/'` returned a large non-`.gsd` diff, so this milestone did not produce planning-only artifacts.
- ℹ️ **Horizontal checklist note:** the roadmap file has no separate `Horizontal Checklist` section, so there were no additional checklist rows to audit beyond the shipped slice outcomes.

## Requirement Outcomes

- **No requirement status transitions were applied during M016 close-out.**
- **R029 remained validated rather than changing status.** M016/S01 materially hardened the already-validated self-service password-reset capability by adding the durable lifecycle table contract, DB-enforced single-active-token invariant, and fresh focused auth/reset proof (**25/25** on the combined auth/reset gate), but that work strengthened an existing validated requirement rather than creating a new validation transition.
- No requirements were deferred, blocked, invalidated, or moved out of scope during this milestone.

## Deviations

None.

## Follow-ups

- Replace the default console-backed password-reset delivery path with provider-backed telemetry while preserving the existing `EmailService` seam and lifecycle table.
- Extend the audited error-contract pattern to additional route families only when they justify the focused proof burden; do not jump straight to a framework-wide FastAPI exception rewrite.
- Use `backend/src/admin/api/security_inventory.py` and `backend/src/common/monitoring/log_safety_inventory.py` watch lists as the bounded entry point for any future admin/logging security widening.
