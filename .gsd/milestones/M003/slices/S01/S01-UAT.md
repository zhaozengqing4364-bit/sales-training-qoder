# S01: 真实入口 inventory 与 current knowledge 真值线 — UAT

**Milestone:** M003
**Written:** 2026-03-25T02:10:01.360Z

# S01: 真实入口 inventory 与 current knowledge 真值线 — UAT

**Milestone:** M003
**Written:** 2026-03-25T07:31:39+08:00

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: S01 only locks the real code entry chain, current knowledge-status vocabulary, proof boundaries, and verifier contract. No live runtime behavior is claimed yet, so the right UAT is to inspect the repo artifacts and rerun the documented contract checks.

## Preconditions

- Worktree is on the completed M003/S01 slice state.
- No local backend/web server is required.
- Run all commands from the repo root.
- Use quoted or escaped literal Next.js paths when a shell command references `web/src/app/(user)/...` or `[sessionId]`.
- If a prior gate already generated a stale `T##-VERIFY.json` with bad commands, refresh that artifact before judging the slice complete.

## Smoke Test

1. Run:
   ```bash
   test -f backend/src/agent/services/persona_policy.py && \
   test -f backend/src/sales_bot/services/voice_runtime_policy.py && \
   test -f backend/src/sales_bot/services/voice_instruction_compiler.py && \
   test -f backend/src/common/knowledge/kb_lock_guard.py && \
   test -f backend/src/common/conversation/runtime_diagnostics.py && \
   test -f backend/src/common/conversation/api.py && \
   test -f backend/src/common/conversation/replay.py && \
   test -f backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py && \
   test -f backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py && \
   test -f backend/src/common/api/practice.py && \
   test -f backend/src/common/conversation/session_evidence.py && \
   test -f web/src/app/admin/personas/\[id\]/page.tsx && \
   test -f web/src/app/admin/knowledge/\[id\]/page.tsx && \
   test -f web/src/app/\(user\)/practice/\[sessionId\]/page.tsx && \
   test -f web/src/app/\(user\)/practice/\[sessionId\]/report/page.tsx && \
   test -f web/src/app/\(user\)/practice/\[sessionId\]/replay/page.tsx
   ```
2. **Expected:** the command exits 0, proving the slice still points only at real entrypoints and authority modules.

## Test Cases

### 1. Entry-chain contract: roadmap and slice plan must point only at current business routes

1. Open `.gsd/milestones/M003/M003-ROADMAP.md`, `.gsd/milestones/M003/slices/S01/S01-PLAN.md`, and `.gsd/milestones/M003/slices/S01/tasks/T01-PLAN.md`.
2. Confirm they name the current admin Persona page, current admin knowledge page, `POST /api/v1/practice/sessions`, the learner practice page, and the learner report/replay surfaces.
3. Confirm they explicitly keep Silence / Conda / `.env` / lockfile work out of scope.
4. **Expected:** the docs describe one real admin -> session -> practice -> report/replay chain and do not elevate environment/tooling work into M003 scope.

### 2. Knowledge-status contract: learner/admin-visible statuses must stay on the seven live terms

1. Run:
   ```bash
   rg -n "no_knowledge_base|disabled|not_triggered|kb_not_ready|search_failed|miss|hit|blocked_no_kb|blocked_not_ready|blocked_search_failed|blocked_empty" \
     backend/src/common/conversation/runtime_diagnostics.py \
     backend/src/common/knowledge/kb_lock_guard.py \
     backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py \
     .gsd/milestones/M003/M003-ROADMAP.md \
     .gsd/milestones/M003/slices/S01/S01-PLAN.md \
     .gsd/milestones/M003/slices/S01/tasks/T02-PLAN.md
   ```
2. Inspect the matching lines in `runtime_diagnostics.py` and the M003 docs.
3. **Expected:** learner/admin-visible status wording stays on `no_knowledge_base`, `disabled`, `not_triggered`, `kb_not_ready`, `search_failed`, `miss`, and `hit`, while KB-lock `blocked_*` states remain diagnostic-only.

### 3. Proof-boundary contract: replay must stay on the conversation API seam

1. Run:
   ```bash
   rg -n "focused backend|focused web|live UAT|/api/v1/practice/sessions/\{id\}/report|/api/v1/sessions/\{id\}/replay|common/conversation/api.py|common/conversation/replay.py|SessionEvidenceService" \
     .gsd/milestones/M003/M003-ROADMAP.md \
     .gsd/milestones/M003/slices/S01/S01-PLAN.md \
     .gsd/milestones/M003/slices/S01/tasks/T03-PLAN.md
   ```
2. Confirm the docs keep report/knowledge-check on `backend/src/common/api/practice.py` and replay on `backend/src/common/conversation/api.py` + `backend/src/common/conversation/replay.py` over `SessionEvidenceService`.
3. **Expected:** replay is not rebound to `practice.py`, and the slice still carries focused backend / focused web / later live UAT boundaries on current routes.

### 4. Verifier integrity: stale task VERIFY artifacts must use shell-safe commands

1. Open `.gsd/milestones/M003/slices/S01/tasks/T03-VERIFY.json`.
2. Confirm any `web/src/app/(user)/...` commands are stored with escaped literal path segments such as `web/src/app/\\(user\\)/practice/\\[sessionId\\]/page.tsx`.
3. Confirm the artifact is marked `"passed": true` after the refreshed close-out run.
4. **Expected:** the slice no longer ships a verifier artifact that reproduces the old shell syntax error before checking files.

## Edge Cases

### Unescaped Next.js literal path in a shell verifier

1. Compare `test -f web/src/app/(user)/practice/[sessionId]/page.tsx` with the escaped or quoted version used in the slice artifacts.
2. **Expected:** the bare version is recognized as invalid shell syntax, and the slice artifacts keep only the shell-safe form.

### Missing or non-runnable proof surface

1. Review the blocker wording in `.gsd/milestones/M003/M003-ROADMAP.md` and `.gsd/milestones/M003/slices/S01/S01-PLAN.md`.
2. **Expected:** the docs require inventory/spike instead of continuing execution on placeholders whenever a required entrypoint cannot be located in runnable code.

## Failure Signals

- Any file-existence gate fails on a claimed admin/runtime/report/replay seam.
- M003 docs introduce learner/admin-visible knowledge statuses outside the locked seven-term contract.
- Replay proof is moved back under `practice.py` or otherwise loses the explicit conversation API + replay service ownership line.
- A `T##-VERIFY.json` artifact still contains bare `web/src/app/(user)/...` commands that fail with shell syntax errors.
- Silence / Conda / `.env` / lockfile work reappears as slice-acceptance scope for M003 without an explicit milestone re-scope.

## Requirements Proved By This UAT

- R010 — Advances the requirement by proving that M003 now builds on the real admin Persona/knowledge -> practice runtime/report/replay chain, the current seven-status knowledge contract, and an explicit blocker/proof boundary instead of placeholder surfaces.

## Not Proven By This UAT

- S02 behavior: frozen Persona pressure inside `voice_policy_snapshot` and reconnect restore.
- S03-S05 behavior: multi-turn objection persistence, unsupported/evidence-backed truth semantics, and one live objection-heavy runtime proof.

## Notes for Tester

- This slice is successful when the repo artifacts and verifiers stay truthful, not when a live training session is run.
- If a later auto gate fails on a literal Next.js path again, check the relevant `T##-VERIFY.json` before assuming the plan docs regressed.
- For later live M003 UAT, keep using the locked S01 surfaces; do not create a parallel proof route just to make a test easier.
