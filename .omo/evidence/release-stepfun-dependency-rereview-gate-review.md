# Release StepFun Dependency Re-review Gate Review

recommendation: APPROVE
confidence: HIGH

## blockers

None.

## originalIntent

复核修复是否真正关闭前一次失败：Presentation StepFun 真实 `{"type":"text"}` 路径曾因缺少 `_extract_text_payload` 抛出 `AttributeError`，同时确认本轮声明的 StepFun 鉴权关闭、Presentation DB factory 注入、release verification 枚举契约、安全 JSON 失败判定和依赖审计仍成立。

## desiredOutcome

用户可见结果应为：

- Presentation StepFun realtime 的真实文本输入路径不再崩溃，且 presentation 场景不误触 sales stage。
- StepFun token 无效时关闭 WebSocket `4401 unauthorized` 并停止后续连接流程。
- Presentation 自身 DB 查询使用注入的 session factory。
- Release verification API 与文档共享完整 `CheckType` 枚举，包含 `security` 与服务内部 check values。
- Security gate 对缺失 scanner 和 safety JSON vulnerability 都产生失败结果，并阻断 release gate。
- 依赖安全审计无已知漏洞。

## userOutcomeReview

当前代码满足用户期望。直接运行探针调用 `PresentationStepFunRealtimeHandler._handle_client_text('{"type":"text","data":{"text":"hello"}}')` 已不再触发原 AttributeError，结果持久化参数中的 `sales_stage` 为 `None`，并调用 `_create_response(count_turn=True)`。这说明真实 shared text route 已经接通，且 presentation 场景安全绕过 sales stage。

## checkedArtifactPaths

- `backend/pyproject.toml`
- `backend/requirements.txt`
- `backend/src/admin/api/release_verification.py`
- `backend/src/common/analytics/release_verification_service.py`
- `backend/src/common/analytics/verification_runner.py`
- `backend/src/presentation_coach/websocket/presentation_stepfun_realtime_handler.py`
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
- `backend/tests/contract/test_release_verification_contract.py`
- `backend/tests/integration/test_release_gate.py`
- `backend/tests/unit/test_presentation_stepfun_realtime_handler.py`
- `backend/tests/unit/test_verification_runner.py`
- `docs/api-contract/release-verification.md`
- `web/package-lock.json`
- `.omo/evidence/release-verification-stepfun-code-review.md`
- `.omo/evidence/release-stepfun-dependency-gate-review.md`
- `.omo/evidence/release-stepfun-dependency-qa/`

## directVerification

- CodeGraph consulted for Presentation StepFun shared text route, `_extract_text_payload`, `_analyze_and_emit_sales_stage`, StepFun `handle_connection`, `CheckType`, `ReleaseVerificationService`, `_run_safety_scan`, `_run_bandit_scan`.
- `cd backend && venv/bin/python -m pytest tests/unit/test_presentation_stepfun_realtime_handler.py tests/unit/test_verification_runner.py::TestHealthAndSecurityChecks::test_safety_json_vulnerabilities_fail_security_check tests/contract/test_release_verification_contract.py -q --no-cov`: PASS, 31 passed.
- Direct Presentation StepFun text probe: PASS, `persist_sales_stage None`, `create_response {'count_turn': True}`.
- `git diff --check -- <13 scoped files>`: PASS.
- `cd backend && venv/bin/ruff check <scoped py files>`: PASS.
- `bash scripts/dependency-governance.sh backend-audit`: PASS, no known vulnerabilities found.
- `bash scripts/dependency-governance.sh web-audit`: PASS, 0 vulnerabilities.
- `cd backend && venv/bin/python -m pytest tests/integration/test_release_gate.py::TestQualityGateThresholds::test_security_failure_blocks_quality_gate_and_automated_decision -q --no-cov`: PASS, 1 passed.
- `cd backend && venv/bin/python -m pytest tests/unit/test_presentation_stepfun_realtime_handler.py::test_handle_connection_closes_on_invalid_token tests/unit/test_presentation_stepfun_realtime_handler.py::test_handle_client_text_routes_shared_text_without_sales_stage -q --no-cov`: PASS, 2 passed.
- `cd backend && venv/bin/python -m pytest tests/unit/test_verification_runner.py::TestHealthAndSecurityChecks::test_missing_bandit_scanner_fails_security_check tests/unit/test_verification_runner.py::TestHealthAndSecurityChecks::test_missing_safety_scanner_fails_security_check tests/unit/test_verification_runner.py::TestHealthAndSecurityChecks::test_safety_json_vulnerabilities_fail_security_check -q --no-cov`: PASS, 3 passed.

## skillPerspectiveReview

- `remove-ai-slops`: direct pass found the new blocker test is behavior-level, not deletion-only or tautological. It drives `PresentationStepFunRealtimeHandler._handle_client_text` through the real `type="text"` route and asserts presentation-specific no-sales-stage behavior plus response creation. Helper-level tests still exist, but they cover presentation event/message adapter contracts and no longer substitute for the missing route test.
- `programming`: direct pass found no new untyped route bypass or unsupported public API widening in the fix. The adapter methods are necessary to satisfy the shared StepFun base contract without inheriting sales-stage behavior.
- Historical code review report `.omo/evidence/release-verification-stepfun-code-review.md` explicitly included `remove-ai-slops` and `programming` coverage and identified the original blocker. It is a stale FAIL artifact from before these fixes, not current passing evidence; current direct probes and tests close the named blocker.

## exactEvidenceGaps

- No updated standalone code-review artifact replacing the stale FAIL report was present. This gate review directly rechecked the named failure and skill criteria.
- A synthetic probe showed `safety` with non-zero exit code plus JSON vulnerability output fails the check but does not parse vulnerability details (`high_severity=0`). This is not blocking for the stated release-safety outcome because the check still fails and blocks release; it is a precision improvement opportunity.

