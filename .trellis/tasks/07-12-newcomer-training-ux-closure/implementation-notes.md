# Implementation Notes

## Accepted Design

- User approved the full remediation described by the 2026-07-12 newcomer-training UX audit.
- Preserve the activity-orchestration architecture and existing visual language.
- Execute inline without subagents and without further product questions.

## Deviations

- The plan referenced generic orchestration test filenames; the repository's actual authoritative tests are `test_newcomer_orchestration_revision_service.py`, `test_newcomer_orchestration_admin_api.py`, and `test_newcomer_orchestration_journey_service.py`. Execution uses those files.
- Work continues on the existing dedicated `codex/newcomer-training-v0-9-closure` branch because the user requested uninterrupted full execution and this workspace already contains the approved plan plus a protected unrelated local edit. No linked worktree was created.
- The Playwright runtime initially lacked `libnspr4.so`; the repository-bundled browser library directory was supplied through `LD_LIBRARY_PATH`, after which both end-to-end audits passed.

## Verification Log

- Baseline backend orchestration tests: 7 behavior tests passed; repository coverage wrapper failed only because the focused invocation imported modules outside its configured `src` coverage root. All subsequent focused pytest runs use `--no-cov` and report behavior separately.
- Baseline frontend newcomer tests: 5 files / 11 tests passed.
- Backend revision + journey focused suite: 15 tests passed.
- Browser recorder/activity result suite: 3 files / 12 tests passed.
- Admin path/resource/API/operations suite: 6 files / 18 tests passed.
- Final backend orchestration suite: 20 tests passed (`--no-cov`); Ruff and mypy passed for all changed orchestration modules.
- Final frontend newcomer suite: 14 files / 39 tests passed; TypeScript and targeted ESLint passed.
- Next.js production build passed and generated all 86 routes, including the two new learner-operations routes.
- Playwright full-stack smoke audit: 2 scenarios passed, covering learner desktop/mobile, admin path resource partial failure and targeted retry, publish-impact confirmation, learner progress and learner detail flows.

## 2026-07-13 Audio Preparation Pack

### Accepted Design

- Replace the direct “打开材料” handoff with an inline, default-expanded preparation pack ordered as material, scoring focuses, example transcript, and confirmation.
- Reuse the existing versioned material and scoring-rubric resources; add only one optional `example_transcript` field to the immutable path revision. No database migration or PPT renderer.
- Freeze the exact scoring-rubric revision shown to the learner when the client supplies its revision ID; retain active-revision fallback only for older clients that omit the new field.

### Deviations

- The written test command used `uv run`, but `uv` is not installed globally in this workspace. Focused backend tests use the repository interpreter at `backend/.venv/bin/pytest --no-cov`; the first baseline invocation also confirmed the repository coverage wrapper is unsuitable for focused root-level test paths.
- Textarea values are preserved while the administrator types, then trimmed and blank-normalized at the path-save boundary and again by the backend contract. Trimming on every keystroke would remove intentional spaces and make the editor difficult to use.
- The user explicitly prohibited subagents, so the `executing-plans` workflow is performed inline despite the skill's general preference for delegated execution.
- The public production audit exposed normal Next.js RSC prefetch cancellations (`net::ERR_ABORTED ...?_rsc=...`) as blocking network failures. The audit filter now ignores only that explicit cancellation shape; HTTP 4xx/5xx, console errors, and other failed requests remain blocking.

### Verification Log

- Backend configuration/journey projection: 15 focused tests passed before the blank-normalization addition.
- Backend exact rubric freezing: 4 focused tests passed, covering exact revision plus wrong logical resource, wrong type, and unpublished revision.
- Frontend admin/API/runner/shell: 4 files / 16 tests passed before final normalization and E2E additions.
- Final backend newcomer orchestration unit suite: 38 tests passed; learner API and seed integration suite: 4 tests passed.
- Final frontend newcomer suite: 12 files / 41 tests passed; focused editor/runner/API suite: 5 files / 24 tests passed.
- Backend Ruff passed for all changed Python files. Isolated mypy passed for all changed backend source files; repository-wide mypy still reports pre-existing errors in unrelated knowledge, agent, prompt-template, and legacy service modules.
- Frontend TypeScript, targeted ESLint, and Next.js production build passed; build generated all 86 routes.
- CodeGraph affected-test analysis identified the learner API and seed integrations in addition to the unit/frontend suites; both were added to verification.
- Public production Playwright at `http://186.241.123.157:3445`: 2 scenarios passed, including desktop/mobile route audit, preparation confirmation gating, and proof that opening the original file keeps the activity page in place.
- Public frontend, backend health, and activity route returned HTTP 200; production logs contained no errors after the browser run.
