# Code Quality Review: release-verification-stepfun

## Verdict
- verdict: FAIL
- confidence: HIGH
- codeQualityStatus: BLOCK
- recommendation: REQUEST_CHANGES

## Scope Reviewed
- backend/pyproject.toml
- backend/requirements.txt
- backend/src/common/analytics/release_verification_service.py
- backend/src/common/analytics/verification_runner.py
- backend/src/presentation_coach/websocket/presentation_stepfun_realtime_handler.py
- backend/tests/integration/test_release_gate.py
- backend/tests/unit/test_presentation_stepfun_realtime_handler.py
- backend/tests/unit/test_verification_runner.py
- web/package-lock.json

## Skill-Perspective Check
- remove-ai-slops: loaded and applied as a review pass. The diff violates this perspective because several new presentation tests assert helper calls in isolation and miss the real shared `text` route, allowing a production AttributeError to survive.
- programming: loaded and applied; Python README was loaded. A requested `references/python/testing.md` file was unavailable, so the README's testing discipline and shared programming criteria were used. The diff violates this perspective because the shared base contract remains incomplete for `PresentationStepFunRealtimeHandler`, and tests do not lock the user-visible text-message path.

## Findings

### CRITICAL
- None.

### HIGH
- `backend/src/presentation_coach/websocket/presentation_stepfun_realtime_handler.py:411` delegates all non-page messages to `super()._handle_client_text(raw_text)`, but the shared text route still expects sales-stage mixin hooks that this class does not provide. The shared implementation calls `_extract_text_payload` at `backend/src/sales_bot/websocket/stepfun_realtime_policy.py:1222` and then `_analyze_and_emit_sales_stage` at `backend/src/sales_bot/websocket/stepfun_realtime_policy.py:1229`; `PresentationStepFunRealtimeHandler` intentionally does not inherit `StepFunRealtimeSalesStageMixin`, and the current diff only adds `_send_*`, `_persist_message`, response extraction, and sales-context noop hooks. A minimal runtime check confirmed `{"type":"text"}` raises `AttributeError _extract_text_payload`. This breaks a real shared realtime base path and must be fixed before approval.

### MEDIUM
- `backend/tests/unit/test_presentation_stepfun_realtime_handler.py:122` through `backend/tests/unit/test_presentation_stepfun_realtime_handler.py:288` mostly test newly added private helper methods directly with `AsyncMock`, but no test drives `PresentationStepFunRealtimeHandler._handle_client_text` with `type="text"`. This is why the HIGH defect above is not caught. Add a behavior-level test for the shared text route, including the no-sales-stage presentation behavior and persistence/upstream response path.

### LOW
- `web/package-lock.json` contains broad transitive upgrades. `npm install --package-lock-only --ignore-scripts --dry-run` reports the lockfile is consistent, so this is not a blocker, but it should stay tied to the security update rationale in review notes because it increases dependency review surface.

## Positive Checks
- The new security default release check is created and the quality gate treats `security` as critical.
- Missing `bandit` and `safety` now produce failing `SecurityCheckResult`s.
- The security gate test meaningfully verifies failed security results block automated release decisions.
- The ChromaDB `<1.0.0` constraint is consistent with NVD's CVE-2026-45829 description for ChromaDB Python 1.0.0 or later.

## Verification Evidence
- CodeGraph consulted for `StepFunRealtimeSharedHandler`, presentation handler hooks, shared `_handle_client_text`, release gate flow, and message persistence helpers.
- `pytest --no-cov tests/unit/test_verification_runner.py::TestHealthAndSecurityChecks::test_missing_bandit_scanner_fails_security_check tests/unit/test_verification_runner.py::TestHealthAndSecurityChecks::test_missing_safety_scanner_fails_security_check` from `backend`: PASS, 2 passed.
- `pytest --no-cov backend/tests/unit/test_presentation_stepfun_realtime_handler.py` from repo root: PASS, 19 passed.
- `pytest --no-cov backend/tests/integration/test_release_gate.py::TestQualityGateThresholds::test_security_failure_blocks_quality_gate_and_automated_decision`: PASS, 1 passed.
- `python3 -m py_compile` on changed Python source/tests: PASS.
- `node -e "JSON.parse(...package-lock.json...)"`: PASS.
- `npm install --package-lock-only --ignore-scripts --dry-run` from `web`: PASS.
- `git diff --check` on scoped files: PASS.
- Minimal runtime probe with `PresentationStepFunRealtimeHandler._handle_client_text('{"type":"text","data":{"text":"hello"}}')`: FAILS with `AttributeError _extract_text_payload`.

## Blocking Issues
- Fix the incomplete presentation StepFun shared-base contract. At minimum, the presentation handler must support the shared `text` route without inheriting sales-stage behavior accidentally, including `_extract_text_payload` and a presentation-safe substitute for `_analyze_and_emit_sales_stage` or an explicit route override that bypasses sales-only hooks.
- Add a focused behavior test that drives the actual `type="text"` path and would fail on the current `AttributeError`.

## External Reference
- NVD CVE-2026-45829: https://nvd.nist.gov/vuln/detail/CVE-2026-45829
