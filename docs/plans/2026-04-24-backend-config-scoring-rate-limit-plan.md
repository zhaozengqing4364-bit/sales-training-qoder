# 2026-04-24 Backend Config, Scoring Evidence, and Rate-Limit Safe Slice Plan

## Scope

This is the backend implementation handoff for the roadmap artifacts:

- `/Users/zhaozengqing/github/销售训练qoder/.omx/plans/prd-sales-training-roadmap-20260424.md`
- `/Users/zhaozengqing/github/销售训练qoder/.omx/plans/test-spec-sales-training-roadmap-20260424.md`

The slice stays intentionally small: clean duplicated config helpers, lock the current session-rate-limit behavior with tests, and expose report scoring/evidence metadata where the current projection code can do so safely. It does not introduce a business-rule database, Redis limiter, adaptive difficulty, sharing, or a StepFun rewrite.

## Implemented safe code hooks

### Config helpers

- Runtime config uses a single bounded integer helper, `_env_int`, and a single allowlisted string helper, `_env_choice`.
- Current strategy is intentionally preserved: invalid values fall back to the default, and out-of-range integers clamp to the configured min/max.
- Tests cover valid, invalid, out-of-range, and choice normalization behavior.

### Session creation rate limit

- Active sessions and creation-window counters are separated.
- Ending sessions immediately should not reset the hourly creation counter.
- Creation timestamps expire after `session_window`, even when the user has no active sessions.
- This locks the current in-memory behavior and documents the gap before any Redis backend is added.

### Scoring/report metadata

- Existing session evidence projection carries `ruleset_version`, `score_basis`, and `evidence_completeness`.
- The safe backend path is to propagate those fields from the projection to report/replay/history surfaces without recalculating historical reports.
- The current version remains a projection kernel contract, not a published business ruleset admin workflow.

## Next implementation slices

### Slice 1 — Config inventory without behavior change

1. Keep `_env_int` / `_env_choice` as the only local env helper layer in `common.config`.
2. Add tests before changing any config default.
3. For each new config, document default, min/max or allowlist, read path, fallback, and owning domain.

Exit criteria:

- `backend/tests/unit/common/test_config_helpers.py` passes.
- `ruff check src/common/config.py tests/unit/common/test_config_helpers.py --quiet` passes.

### Slice 2 — Rate-limit contract before Redis

1. Keep in-memory active-session and creation-window counters separate.
2. Add adapter-level contract tests before introducing Redis.
3. If Redis is later added, use atomic increment/expire semantics and keep the in-memory behavior as fallback.
4. Decide fail-open/fail-closed behavior per environment before wiring production Redis.

Exit criteria:

- Focused tests in `backend/tests/unit/test_p0_fixes.py::TestSessionRateLimiter` pass.
- No endpoint behavior changes without integration tests.

### Slice 3 — Scoring ruleset persistence foundation

1. Add schema/table/API only after the ADR fields are confirmed: `ruleset_id`, `version`, `subject`, `status`, `dimensions`, `weights`, `thresholds`, `non_evaluable_reasons`, `evidence_requirements`, `fallback_policy`.
2. Save generated report metadata at generation time: `ruleset_version`, `score_basis`, `evidence_completeness`.
3. For old reports, display legacy compatibility metadata instead of recalculating.
4. Dry-run must be read-only and must not write an active version.

Exit criteria:

- Unit tests cover evaluable, non-evaluable, legacy report compatibility, and dry-run diff payloads.
- Integration tests assert report/replay/history carry the same evidence metadata.

### Slice 4 — Business-rule admin backend

1. Implement generic draft/validate/preview/publish/rollback only after permission and audit contracts are stable.
2. Publish and rollback must require `actor`, `before`, `after`, `version`, `reason`, and `trace_id`.
3. Preview must not mutate active config.
4. Non-admin mutations must be rejected.

Exit criteria:

- Backend integration tests cover create draft, non-admin rejection, invalid publish rejection, preview no-op, publish audit, and rollback audit.

## Verification commands

Recommended focused commands for this safe backend slice:

```bash
cd backend && uv run ruff check src/common/config.py src/common/rate_limit/session_limiter.py tests/unit/common/test_config_helpers.py tests/unit/test_p0_fixes.py --quiet
cd backend && uv run pytest tests/unit/common/test_config_helpers.py tests/unit/test_p0_fixes.py::TestSessionRateLimiter -q --no-cov
cd backend && uv run pytest tests/unit/test_session_evidence_service.py tests/unit/test_session_evidence_service.py::TestSessionEvidenceProjection::test_projection_kernel_contract_includes_ruleset_and_score_basis -q --no-cov
```

If `.venv-test` exists in the integration environment, use the roadmap command:

```bash
cd backend && .venv-test/bin/python -m pytest tests/unit/common tests/integration -q --no-cov
```

## Rollback

- Config helper cleanup is source-local and can be reverted without data migration.
- In-memory rate-limit behavior has no persisted state; rollback is code-only.
- Report metadata propagation must not change historical stored scores; rollback should only remove newly exposed metadata fields from responses if necessary, not rewrite stored reports.
