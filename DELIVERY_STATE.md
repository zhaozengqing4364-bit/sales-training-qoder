# DELIVERY_STATE

## Execution Rules

- Current phase must advance serially from Phase 1 to Phase 5.
- Every atomic task must be verified, committed, and recorded here before the next atomic task starts.
- If an external dependency cannot be resolved, a loop is detected, or the same atomic test fails more than 3 times, pause immediately and record the blocker.
- Existing unrelated worktree changes are not part of this delivery state unless explicitly recorded as an atomic task.

## Current Status

- Overall status: in_progress
- Current phase: Phase 1 - Baseline Falsification and Routing Audit
- Current atomic task: Phase 1.3 - Backend and frontend lint/type baseline
- Last commit: Phase 1.3 lint and frontend type baseline blocker snapshot commit
- Blocker: Backend mypy baseline is not production-clean. `mypy` was absent from the project test environment and project dependency files; after installing it into local `.venv-test` only for verification, `PYTHONPATH=src ./.venv-test/bin/mypy src` fails package discovery with duplicate `api` modules, while `MYPYPATH=src ./.venv-test/bin/mypy --explicit-package-bases src` reaches real checking but reports 2430 errors in 164 files.

## Implementation-Before-Coding Judgment

### Phase 1.0 - Delivery State Bootstrap

- Stable code logic: delivery progress must be tracked in a root `DELIVERY_STATE.md`; phase order and pause criteria are execution controls.
- Configurable business rules: none in this atomic task.
- New configuration items: none.
- Reused configuration items: none identified.
- Configuration source: not applicable.
- Configuration manager: not applicable.
- Configuration validation: not applicable.
- Missing configuration fallback: not applicable.
- Illegal configuration handling: not applicable.
- Logic that must not be hardcoded: future business thresholds, copy, permissions, switches, scoring rules, routing policies, and admin rules must not be introduced as scattered constants during later phases.

Based on the currently inspected code, the existing configuration system cannot yet be confirmed. Later feature work must inspect configuration modules, admin management modules, dictionary tables, permission modules, or system settings code before introducing adjustable business rules.

## Phase Checklist

### Phase 1.1 - API Routing Audit

- Stable code logic: route registration, audit evidence collection, and contract comparison are stable engineering controls.
- Configurable business rules: none introduced.
- New configuration items: none.
- Reused configuration items: `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_WS_URL`, existing backend auth/CORS environment settings.
- Configuration source: existing frontend environment variables and backend environment reads only observed.
- Configuration manager: unchanged.
- Configuration validation: unchanged.
- Missing configuration fallback: current defaults remain `http://localhost:3444/api/v1` and `ws://localhost:3444`.
- Illegal configuration handling: unchanged.
- Logic that must not be hardcoded: future scoring ruleset route aliases, admin permission mappings, business thresholds, and operational copy.

### Phase 1.2 - API Contract Alignment

- Stable code logic: committed OpenAPI contract should be generated from the runtime FastAPI schema; operation IDs must be unique.
- Configurable business rules: none introduced.
- New configuration items: none.
- Reused configuration items: none changed.
- Configuration source: not applicable.
- Configuration manager: not applicable.
- Configuration validation: OpenAPI path parity is validated by `test_committed_openapi_contract_matches_runtime_paths`.
- Missing configuration fallback: not applicable.
- Illegal configuration handling: not applicable.
- Logic that must not be hardcoded: scoring-ruleset target route migration remains a Phase 2 router/client compatibility task, not an ad hoc alias hidden in Phase 1.

### Phase 1.3 - Backend and Frontend Lint/Type Baseline

- Stable code logic: import ordering, unused import cleanup, TypeScript fixture shape consistency, and verification-tool execution are stable engineering controls.
- Configurable business rules: none introduced.
- New configuration items: none.
- Reused configuration items: existing `pyproject.toml` ruff/mypy settings and frontend TypeScript/ESLint configuration.
- Configuration source: existing repo tool configuration only.
- Configuration manager: unchanged.
- Configuration validation: `ruff check src tests`, `npx eslint . --quiet`, and `npx tsc --noEmit` now pass; backend mypy remains blocked by existing type debt.
- Missing configuration fallback: not applicable.
- Illegal configuration handling: not applicable.
- Logic that must not be hardcoded: no business thresholds, copy, permission mappings, scoring rules, or operational switches were introduced.

### Phase 1: Baseline Falsification and Routing Audit

- [x] Phase 1.0: Create and maintain `DELIVERY_STATE.md`.
- [x] Phase 1.1: Generate `api_routing_audit.md` with OpenAPI paths, router sources, permission dependencies, and frontend call mapping.
- [x] Phase 1.2: Fix all unmounted or wrongly mounted routes and reach 100% frontend/backend API contract consistency.
- [ ] Phase 1.3: Fix all frontend/backend lint errors and TypeScript type errors. Backend/frontend lint and frontend TypeScript are fixed; backend mypy baseline remains blocked.
- [ ] Phase 1.4: Adjust Vitest to isolate `node_modules`.
- [ ] Phase 1.5: Add tests until total coverage is at least 60%, and core domains `scoring`, `auth`, and `practice` are at least 70%.

### Phase 2: Admin Governance Foundation and RBAC Loop

- [ ] Phase 2.1: Migrate scoring rulesets to `/api/v1/admin/scoring-rulesets` with CRUD, publish, rollback, and dry-run.
- [ ] Phase 2.2: Sync frontend client and legacy path compatibility for scoring rulesets.
- [ ] Phase 2.3: Design and implement RBAC tables and audit log migrations.
- [ ] Phase 2.4: Seed roles `admin`, `operations`, `content_admin`, `support`, and `readonly_auditor`.
- [ ] Phase 2.5: Add action-level permission checks and audit persistence to all high-risk admin APIs.
- [ ] Phase 2.6: Build RBAC admin UI.
- [ ] Phase 2.7: Render frontend menus/buttons by permission and force 403 on unauthorized direct access.

### Phase 3: User Dictionary Full Business Chain

- [ ] Phase 3.1: Add versioned and audited user dictionary data model.
- [ ] Phase 3.2: Build user dictionary admin CRUD UI.
- [ ] Phase 3.3: Normalize ASR final transcripts through dictionary correction and persist mapping evidence to session messages.
- [ ] Phase 3.4: Apply normalized text to knowledge retrieval grounding queries.
- [ ] Phase 3.5: Show correction traces in scoring evidence, six-dimensional reports, and Replay pages.

### Phase 4: Stable E2E for Both Training Flows

- [ ] Phase 4.1: Build auditable local mock provider for AI, ASR, and TTS dependencies.
- [ ] Phase 4.2: Build standard test fixtures including corrupted PPT fixtures.
- [ ] Phase 4.3: Add sales training E2E covering login, session creation, WebSocket, dialogue, finish, and report generation success/degraded paths.
- [ ] Phase 4.4: Add presentation training E2E covering PPT upload, parsing, forbidden-word configuration, realtime feedback capture, and six-dimensional report output.
- [ ] Phase 4.5: Run both main E2E flows locally 3 consecutive times.
- [ ] Phase 4.6: Verify core API p95 latency below 500ms.

### Phase 5: Security Gate and Release Closure

- [ ] Phase 5.1: Scan and extract scattered frontend business thresholds and operational copy into business configuration dictionaries with defaults and validation fallback.
- [ ] Phase 5.2: Run production-grade secret scan with 0 high-risk findings.
- [ ] Phase 5.3: Ensure logs redact tokens and cookies.
- [ ] Phase 5.4: Force-disable dev-login and default secrets in production.
- [ ] Phase 5.5: Output final `Release_Checklist.md` with execution evidence.

## Atomic Task Log

| Time | Phase | Task | Verification | Commit |
| --- | --- | --- | --- | --- |
| 2026-05-06 | Phase 1.0 | Delivery state bootstrap | `test -f DELIVERY_STATE.md && test -f tasks/todo.md && rg -n "Phase 1|Phase 2|Phase 3|Phase 4|Phase 5|api_routing_audit.md|Release_Checklist.md|Current atomic task|Atomic Task Log" DELIVERY_STATE.md tasks/todo.md` | Phase 1.0 delivery state bootstrap commit |
| 2026-05-06 | Phase 1.1 | API routing audit generated | `test -f api_routing_audit.md && rg -n "OpenAPI|Router Sources|Permission Dependencies|Frontend Call Mapping|/api/v1/admin/scoring-rulesets|/api/v1/evaluation/admin/scoring-rulesets|POST /api/v1/auth/wechat|BACKEND_MISSING_SPEC_COUNT|HAS_NEW_SCORING_ROUTE False" api_routing_audit.md` | Phase 1.1 API routing audit commit |
| 2026-05-06 | Phase 1.2 | Runtime OpenAPI contract alignment | `PYTHONPATH=src ./.venv-test/bin/pytest tests/unit/common/test_route_integrity.py -q --no-cov`; `PYTHONPATH=src ./.venv-test/bin/python -W error::UserWarning - <<'PY' ... assert runtime/committed path parity, no /auth/wechat, WeCom routes present, unique operation IDs ... PY` | Phase 1.2 API contract alignment commit |
| 2026-05-06 | Phase 1.3 | Lint and frontend TypeScript baseline fixed; backend mypy blocker recorded | `ruff check src tests`; `npx eslint . --quiet`; `npx tsc --noEmit`; `npx vitest run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'`; `PYTHONPATH=src ./.venv-test/bin/pytest tests/unit/test_app_factory.py tests/unit/common/test_route_integrity.py -q --no-cov`; `PYTHONPATH=src ./.venv-test/bin/pytest tests/integration/test_auth_login_api.py tests/integration/test_prompt_templates_api_rbac.py tests/integration/test_staged_evaluation_db.py tests/integration/test_support_runtime_api.py tests/unit/admin/test_model_config_security.py tests/unit/admin/test_presentation_upload_safety.py tests/unit/test_runtime_dependency_contract.py tests/unit/test_secret_hygiene_scan.py -q --no-cov`; blocker evidence: `MYPYPATH=src ./.venv-test/bin/mypy --explicit-package-bases src` fails with 2430 errors in 164 files | Phase 1.3 lint and frontend type baseline blocker snapshot commit |

## Non-Blocking Verification Notes

- `PYTHONPATH=src ./.venv-test/bin/pytest tests/unit/common/test_route_integrity.py -q` collected and passed 6 route assertions, then failed global coverage because the project applies `--cov-fail-under=48` to all pytest runs. The coverage gate is tracked under Phase 1.5; the same targeted route test passed with `--no-cov`.

## Pause Log

- 2026-05-06 Phase 1.3: paused before Phase 1.4 because backend mypy is not clean. The project test environment initially lacked `mypy`; local verification installed `mypy==1.20.2` into `.venv-test` via `uv pip install --python ./.venv-test/bin/python 'mypy>=1.10'`. Direct `mypy src` fails package discovery due duplicate `api` module names; the corrected package-base invocation reaches real analysis but reports 2430 errors in 164 files. This is broad existing type debt and should be split into dedicated type-baseline subtasks before continuing the serial delivery plan.
