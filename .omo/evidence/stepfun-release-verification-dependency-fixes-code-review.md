# StepFun / Release Verification / Dependency Fixes Code Review

## Verdict
- PASS/FAIL/INCONCLUSIVE: **FAIL**
- Confidence: **0.82**
- codeQualityStatus: **BLOCK**
- recommendation: **REQUEST_CHANGES**

## Skill Perspective Check
- `omo:remove-ai-slops`: ran by loading `/Users/zhaozengqing/.codex/plugins/cache/sisyphuslabs/omo/4.12.1/skills/remove-ai-slops/SKILL.md`.
- `omo:programming`: ran by loading `/Users/zhaozengqing/.codex/plugins/cache/sisyphuslabs/omo/4.12.1/skills/programming/SKILL.md`, plus Python/TypeScript README and code-smells reference.
- Result: StepFun text-route tests are materially improved and no longer only mock helpers. Release verification still violates both perspectives because the Safety test overfits an unrealistic successful exit code and gives false confidence in JSON vulnerability parsing.

## CRITICAL
- None.

## HIGH
- `backend/src/common/analytics/verification_runner.py:1426` and `backend/src/common/analytics/verification_runner.py:1488`: `_run_safety_scan` only parses JSON when `safety check --json` returns `0`. Safety's current official exit-code docs state scans with vulnerabilities return non-zero exit codes, so the real vulnerable-dependency path falls into the generic "Safety scan failed to complete" branch and loses vulnerability details/severity. Probe result with `returncode=64` and vulnerability JSON: `passed=False`, `issues_found=1`, `high_severity=0`, `error_message="Safety scan failed to complete"`, `details=None`. This blocks release, but it is not auditable and does not satisfy the claimed safety JSON parsing behavior. Source consulted: https://docs.safetycli.com/safety-docs/safety-cli/scanning-for-vulnerable-and-malicious-packages/exit-codes
- `backend/tests/unit/test_verification_runner.py:418`: `test_safety_json_vulnerabilities_fail_security_check` sets `completed.returncode = 0`, so it proves parsing only for the no-vulnerability success exit class. This is an overfit test under the `remove-ai-slops`/`programming` perspectives: it mirrors the implementation branch instead of the scanner contract and would not fail for the real non-zero vulnerability path.

## MEDIUM
- Several touched Python files remain far above the 250 pure-LOC programming threshold, including `presentation_stepfun_realtime_handler.py` at 663 pure LOC and `verification_runner.py` at 1583 pure LOC. This review does not block solely on inherited file size because the immediate fixes are localized, but adding more behavior to these files increases review and regression risk.

## LOW
- The first focused pytest run without `--no-cov` ended with exit code 1 because the selected subset triggered the project-wide coverage fail-under (`33.08% < 48%`). The same 62 tests passed with `--no-cov`; report subset coverage failures separately from test behavior.

## Rechecked Original Blockers
- Presentation text route now has `_extract_text_payload` and presentation-safe `_analyze_and_emit_sales_stage` no-op at `backend/src/presentation_coach/websocket/presentation_stepfun_realtime_handler.py:318`.
- The real text-route regression exists at `backend/tests/unit/test_presentation_stepfun_realtime_handler.py:220` and calls `_handle_client_text` without mocking `_extract_text_payload` or `_analyze_and_emit_sales_stage`; this would catch the prior AttributeError class.
- Invalid-token close behavior is covered and passed.
- Presentation DB access now uses `_db_session_factory`, with tests covering page requirements, AI policy, and interruption guidance.
- Release API `CheckType` and docs enum are synced in the inspected diff.

## Verification Run
- `uv run pytest tests/unit/test_presentation_stepfun_realtime_handler.py tests/unit/test_verification_runner.py tests/contract/test_release_verification_contract.py`
  - Result: 62 tests passed, command failed only because subset coverage was below global fail-under.
- `uv run pytest --no-cov tests/unit/test_presentation_stepfun_realtime_handler.py tests/unit/test_verification_runner.py tests/contract/test_release_verification_contract.py`
  - Result: 62 passed, 2 warnings.
- `uv run --project backend ruff check $(git diff --name-only -- '*.py')`
  - Result: all checks passed.
- Local tool availability probe:
  - `safety_path None`
  - `bandit_path None`
- Safety non-zero JSON probe:
  - Result confirms current code does not parse vulnerability JSON when Safety returns non-zero.

## Blocking Issues
- Fix `_run_safety_scan` so JSON vulnerability output is parsed for vulnerability exit codes as well as success exit codes, while still distinguishing malformed output and true execution failure.
- Add/adjust a unit test where Safety returns a non-zero vulnerability exit code with JSON stdout and assert vulnerability count/severity/details are preserved.
