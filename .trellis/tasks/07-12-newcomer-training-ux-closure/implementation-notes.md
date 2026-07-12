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
