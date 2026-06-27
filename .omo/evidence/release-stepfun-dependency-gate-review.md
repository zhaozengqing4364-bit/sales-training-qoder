# Release StepFun Dependency Gate Review

recommendation: REJECT
verdict: FAIL
confidence: HIGH

## originalIntent

用户在 post-implementation review 后通过 `omo:ulw-loop` 要求“全量修复实现”。本轮提交声称修复：

- release/security gate 缺口，security 必须成为阻断门禁；
- `bandit` / `safety` 等安全扫描器缺失时不得被当作通过或静默跳过；
- Presentation StepFun realtime 缺失运行时方法；
- ChromaDB / npm dependency security 问题；
- 通过完整 critical quality gate 验证。

## desiredOutcome

用户可见结果应是：发布门禁遇到安全问题会显式 no-go；扫描器缺失会失败；Presentation StepFun realtime 的真实输入路径不再因 sales/presentation 共享基类拆分而崩溃；依赖审计无已知漏洞；最终证据包含通过的自动化门禁、真实路径 QA、代码审查和 slop/overfit 审查。

## userOutcomeReview

从用户视角，release/security gate 与依赖审计部分已有强证据支持，但 Presentation StepFun realtime 仍未满足“缺失运行时方法全量修复”。`PresentationStepFunRealtimeHandler._handle_client_text` 对非 `page_change` 消息仍委托共享基类；真实 `{"type":"text"}` 路径会访问未由 presentation handler 提供的 `_extract_text_payload`，当前可复现 `AttributeError _extract_text_payload`。这意味着真实文本输入路径仍会崩溃，新增 helper 单测没有覆盖用户可见路径，不能通过最终验收。

## goalBreakdown

- [ACHIEVED] ReleaseVerificationService 默认创建 security 检查。
  - Evidence: `backend/src/common/analytics/release_verification_service.py:220` adds `check_type="security"` to `DEFAULT_CHECKS`; tests now expect 6 default checks in `backend/tests/integration/test_release_gate.py`.
- [ACHIEVED] Security quality gate is critical and blocks automated go/no-go.
  - Evidence: `backend/src/common/analytics/release_verification_service.py:850` sets security `threshold: 0` and `critical: True`; `:907` appends blocking security failure text; `:1024` makes blocking failures `no_go`.
- [ACHIEVED] Missing `bandit` / `safety` fail visibly.
  - Evidence: `backend/src/common/analytics/verification_runner.py:1385` and `:1466` return failed `SecurityCheckResult` with `tool_missing` details; `backend/tests/unit/test_verification_runner.py` covers both missing scanner paths.
- [MISSED] Presentation StepFun realtime missing runtime methods fully fixed.
  - Evidence: `backend/src/presentation_coach/websocket/presentation_stepfun_realtime_handler.py:411` delegates non-page messages to `super()._handle_client_text`; `backend/src/sales_bot/websocket/stepfun_realtime_policy.py:1222` calls `_extract_text_payload`; `rg` finds `_extract_text_payload` only on `StepFunRealtimeSalesStageMixin`, not on `PresentationStepFunRealtimeHandler`; runtime probe reproduces `AttributeError _extract_text_payload`.
- [PARTIAL] Tests cover added helpers but overfit private methods.
  - Evidence: `backend/tests/unit/test_presentation_stepfun_realtime_handler.py:122-288` mostly asserts `_send_*`, `_persist_message`, and noop helper calls with mocks; no test drives `type="text"` through `_handle_client_text`.
- [ACHIEVED] Dependency security checks for this scoped review are green.
  - Evidence: `npm audit --package-lock-only --audit-level=moderate` returned `found 0 vulnerabilities`; `bash scripts/dependency-governance.sh backend-audit` returned `No known vulnerabilities found`; ChromaDB is constrained to `<1.0.0` in `backend/pyproject.toml` and `backend/requirements.txt`.
- [ACHIEVED] Full critical quality gate now passes.
  - Evidence: `bash scripts/critical-quality-gate.sh` passed; included secret scan, web typecheck, 161 Vitest tests, 9 Playwright smoke tests, 2 Presentation Phase 4 E2E tests, 1 Sales Phase 4 E2E test, 113 backend tests, and 58 backend smoke regression tests; script stopped ports 3444/3445.
- [MISSED] In-scope code review approval.
  - Evidence: `.omo/evidence/release-verification-stepfun-code-review.md` is a same-scope code review and has `verdict: FAIL`, `recommendation: REQUEST_CHANGES`, with the Presentation text path blocker above.

## constraintCompliance

- [PASS] Chinese reporting: this review report is Chinese.
- [PASS] No production edits in this review: only this gate-review artifact was written.
- [PASS] Do not revert unrelated dirty files: no revert performed; workspace has unrelated dirty files outside this review scope.
- [PASS] No new unnecessary direct dependencies: scoped diff changes constraints/lockfile but does not add a new top-level dependency.
- [PASS] Security gate must fail visibly: missing scanners and security gate failures now fail/no-go.
- [PARTIAL] Minimal/surgical changes: release/security changes are small; Presentation handler adds many private parity helpers but misses a real shared-route contract, so the change is not sufficient despite being localized.
- [FAIL] Slop/overfit criteria: direct remove-ai-slops pass finds overfit helper tests that do not exercise the real text route and allow a production AttributeError.
- [FAIL] Required code review coverage: the in-scope report includes `remove-ai-slops` and `programming` coverage, but its verdict is FAIL and no later approval artifact was found.

## findings

- [BLOCKER] Presentation text input still crashes.
  - File: `backend/src/presentation_coach/websocket/presentation_stepfun_realtime_handler.py:411`
  - Evidence: runtime probe with `PresentationStepFunRealtimeHandler._handle_client_text('{"type":"text","data":{"text":"hello"}}')` prints `AttributeError _extract_text_payload`.
  - User impact: browser/client text messages on the presentation realtime WebSocket can fail instead of reaching StepFun.
- [BLOCKER] Same-scope code review is failing.
  - File: `.omo/evidence/release-verification-stepfun-code-review.md`
  - Evidence: `verdict: FAIL`, `recommendation: REQUEST_CHANGES`, blocker requires fixing `_extract_text_payload` and `_analyze_and_emit_sales_stage` / route override.
- [BLOCKER] Tests give false confidence for the broken path.
  - File: `backend/tests/unit/test_presentation_stepfun_realtime_handler.py:122`
  - Evidence: helper-level tests pass, but no behavior test covers `type="text"` route.
- [WARN] Dependency governance still records pyproject extras drift.
  - Evidence: `bash scripts/dependency-governance.sh status` says backend pyproject extras drift exists and requirements.txt remains the backend dependency authority. This is not the current release/security blocker because backend audit passes, but it should stay visible.

## blockers

1. Add a presentation-safe implementation for the shared text route: either implement `_extract_text_payload` and presentation-safe `_analyze_and_emit_sales_stage`, or explicitly override/bypass sales-only hooks for `type="text"` while preserving persistence/upstream behavior.
2. Add a behavior-level regression test that drives `PresentationStepFunRealtimeHandler._handle_client_text` with `{"type":"text"}` and fails on the current `AttributeError`.
3. Rerun the focused backend tests and `bash scripts/critical-quality-gate.sh` after the runtime fix.
4. Obtain or create a new in-scope code review artifact that changes `.omo/evidence/release-verification-stepfun-code-review.md` from FAIL/REQUEST_CHANGES to approval, with `remove-ai-slops` and `programming` coverage still explicit.

## checkedArtifactPaths

- `backend/pyproject.toml`
- `backend/requirements.txt`
- `backend/src/common/analytics/release_verification_service.py`
- `backend/src/common/analytics/verification_runner.py`
- `backend/src/presentation_coach/websocket/presentation_stepfun_realtime_handler.py`
- `backend/tests/integration/test_release_gate.py`
- `backend/tests/unit/test_presentation_stepfun_realtime_handler.py`
- `backend/tests/unit/test_verification_runner.py`
- `web/package-lock.json`
- `.omo/evidence/release-verification-stepfun-code-review.md`
- `.omo/evidence/release-stepfun-dependency-qa/context.txt`
- `.omo/evidence/release-stepfun-dependency-qa/s1-git-diff-check.txt`
- `.omo/evidence/release-stepfun-dependency-qa/s2-backend-focused-pytest.txt`
- `.omo/evidence/release-stepfun-dependency-qa/s3-backend-audit.txt`
- `.omo/evidence/release-stepfun-dependency-qa/s4-web-audit.txt`
- `.omo/ulw-loop/019ee4d7-review-fix/brief.md`
- `.omo/ulw-loop/019ee4d7-review-fix/goals.json`
- `.omo/ulw-loop/019ee4d7-review-fix/ledger.jsonl`

## directVerification

- `git diff --check -- <scoped files>`: PASS.
- `uv run pytest tests/unit/test_verification_runner.py tests/unit/test_presentation_stepfun_realtime_handler.py tests/integration/test_release_gate.py --no-cov`: PASS, 59 passed.
- Same pytest command without `--no-cov`: FAIL due coverage report data error / fail-under, while all 59 tests passed. This is not counted as clean gate evidence.
- `npm audit --package-lock-only --audit-level=moderate` in `web`: PASS, 0 vulnerabilities.
- `bash scripts/dependency-governance.sh status`: PASS, but reports backend pyproject extras drift.
- `bash scripts/dependency-governance.sh web-audit`: PASS, 0 vulnerabilities.
- `bash scripts/dependency-governance.sh backend-audit`: PASS, no known vulnerabilities.
- `bash scripts/critical-quality-gate.sh`: PASS.
- `lsof -nP -iTCP:3444 -sTCP:LISTEN`: no listener after gate cleanup.
- `lsof -nP -iTCP:3445 -sTCP:LISTEN`: no listener after gate cleanup.
- `PYTHONPATH=src uv run python <PresentationStepFunRealtimeHandler text probe>`: FAILS with `AttributeError _extract_text_payload`.

## exactEvidenceGaps

- No passing behavior test for the real Presentation StepFun `type="text"` route.
- No fixed implementation evidence for `_extract_text_payload` / sales-stage hook replacement or explicit presentation text-route override.
- No later in-scope code review approval after `.omo/evidence/release-verification-stepfun-code-review.md` reported FAIL.
- `.omo/evidence/release-stepfun-dependency-qa/s1-git-diff-check.txt` and `s3-backend-audit.txt` are empty artifacts and cannot support their claimed checks.
- The scoped pytest suite passes with `--no-cov`, but the same targeted command under configured coverage failed in this environment; full critical gate later passed and is stronger release evidence, but the targeted coverage failure remains a noted verification anomaly.
