# S04: 训练中建议与报告结论一致性

**Goal:** 让已完成的 sales session 在练中主建议、练后 `main_issue` / `next_goal`、以及 replay / history / admin 读到的结论共用同一套 sales-first 判断基线；同一 session 不再出现 realtime coach 说 A、report 总结说 B 的漂移。
**Demo:** 对一个带有最新 `sales_stage` 与 `score_snapshot.dimension_scores` 的 completed sales session，`SessionEvidenceService` 会用与 S03 `resolve_sales_coaching_focus(...)` 兼容的读侧 helper 重算 `main_issue` / `next_goal`；`/practice/{id}/report` 与 `/practice/{id}/replay` 返回一致结论，replay 页可视化展示同一主问题 / 下一轮目标，admin / history 继续沿用同一词汇显示这些结论。
**Requirement focus:** R009（advanced）

## Must-Haves

- `common.effectiveness` 提供一条 report/replay alignment helper：使用最新 persisted `sales_stage` + normalized `score_snapshot`，并与 S03 的 coaching-focus rule family 保持兼容，产出不改名的 `main_issue` / `next_goal` 结论。
- `SessionEvidenceService.build_projection(...)` 对 completed sales sessions 走 projection-side override；旧或 stale 的 `effectiveness_snapshot` 不能继续让 report / replay / history / admin 漂移，但 public report/replay keys、websocket contract、数据库 schema 都保持稳定。
- Replay 页显式展示与 report 相同的主问题 / 下一目标，`web/src/lib/session-evidence.ts` 覆盖当前 sales issue/goal vocabulary，避免 replay/admin badge 回退为空或继续使用旧词汇。

## Proof Level

- This slice proves: integration
- Real runtime required: no
- Human/UAT required: no

## Verification

- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_report_alignment.py tests/unit/test_session_evidence_service.py tests/unit/test_replay_service.py tests/unit/test_history_service_evidence_projection.py`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_session_evidence_service.py -k 'sales_alignment or stale_snapshot or insufficient_sales_evidence' -vv`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_session_evidence_service.py -k 'insufficient_sales_evidence' -vv`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_report_alignment.py -k 'insufficient_sales_evidence' -vv`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py tests/integration/test_practice_evidence_flow.py tests/integration/test_sales_value_training_flow.py`
- `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'`

## Observability / Diagnostics

- Runtime signals: `practice_session_evidence_projection_built` 增加 sales alignment 是否启用、来源 stage / fallback reason 等读侧诊断字段；report / replay / history / admin 继续暴露 `main_issue`、`next_goal`、`evaluable`、`evidence_completeness`。
- Inspection surfaces: `backend/tests/unit/test_effectiveness_sales_report_alignment.py`、`backend/tests/unit/test_session_evidence_service.py`、`backend/tests/unit/test_replay_service.py`、`backend/tests/unit/test_history_service_evidence_projection.py`、report/replay JSON payload、replay 页结论卡片、admin 用户详情页 badges。
- Failure visibility: stale snapshot 继续生效、缺少 stage/score 证据、或 label map 漂移时，会由具名 focused tests 明确指出是 override 未触发、fallback 走错、还是前端词汇未覆盖，而不是只在浏览器里表现成“看起来不一致”。
- Redaction constraints: 诊断日志只记录 issue/goal type、stage id、布尔 override/fallback 状态与会话 id；不记录 transcript 文本、密钥或真实客户 PII。

## Integration Closure

- Upstream surfaces consumed: `backend/src/common/effectiveness/evaluator.py`、S03 的 `resolve_sales_coaching_focus(...)`、persisted message `sales_stage` / `score_snapshot` / `ai_feedback`、`backend/src/common/conversation/session_evidence.py`。
- New wiring introduced in this slice: 一条共享读侧 alignment helper 由 projection 调用，既有 replay / report / history / admin contract 继续承载同一份 `main_issue` / `next_goal`，replay UI 只渲染这份共享结论而不在客户端重算规则。
- What remains before the milestone is truly usable end-to-end: S05 仍需补齐 coach degraded / resume 可见性；S06 仍需完成 live end-to-end / UAT 证明。S04 本身不再引入额外 schema 或 runtime-mode alignment 待办。

## Tasks

- [x] **T01: Add a shared sales report-alignment helper in `common.effectiveness`** `est:90m`
  - Why: S03 已经有 realtime 的 authoritative coaching seam，但 report-side `main_issue` / `next_goal` 仍主要从 rollup metrics 派生；S04 需要先在 shared effectiveness layer 建立与 realtime 兼容的 read-side 对照规则。
  - Files: `backend/src/common/effectiveness/evaluator.py`, `backend/src/common/effectiveness/schemas.py`, `backend/src/common/effectiveness/__init__.py`, `backend/tests/unit/test_effectiveness_sales_report_alignment.py`
  - Do: 先加 focused failing tests，锁定 discovery/evidence、objection/handling、closing/next-step 三类 sales stage + score 组合应落到什么 `main_issue` / `next_goal`；再新增一个 shared helper，把 persisted stage/score evidence 映射为兼容现有 report contract 的结论，并在证据不足时保留当前 evaluator fallback；不要改 websocket、DB schema 或 report key 名称。
  - Verify: `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_report_alignment.py`
  - Done when: shared helper 能稳定输出与 S03 coaching-focus 同方向的 `main_issue` / `next_goal`，且缺少有效 sales evidence 时仍回退到既有 evaluator 语义。
- [x] **T02: Override stale sales conclusions in session evidence projection** `est:2h`
  - Why: 当前漂移主要发生在读侧：projection 会复用 session 上已有 snapshot，导致旧结论继续穿透到 report / replay / history / admin；必须在 shared projection seam 统一收口。
  - Files: `backend/src/common/conversation/session_evidence.py`, `backend/tests/unit/test_session_evidence_service.py`, `backend/tests/unit/test_replay_service.py`, `backend/tests/unit/test_history_service_evidence_projection.py`, `backend/tests/contract/test_practice_evidence_contract.py`, `backend/tests/integration/test_practice_evidence_flow.py`, `backend/tests/integration/test_sales_value_training_flow.py`
  - Do: 让 `SessionEvidenceService.build_projection(...)` 对 completed sales sessions 使用最新 persisted `sales_stage` + normalized `score_snapshot` 生成 aligned conclusion，并在 snapshot stale 时 override 读侧 `main_issue` / `next_goal`；补一个最小的 projection log signal 说明 alignment 是否应用与为何 fallback；扩展 unit / contract / integration tests 证明 replay / report / history 看到的是同一份结论。后端 pytest 命令必须串行执行，不并行，以避开 repo 现有 `pytest-cov` combine race。
  - Verify: `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_effectiveness_sales_report_alignment.py tests/unit/test_session_evidence_service.py tests/unit/test_replay_service.py tests/unit/test_history_service_evidence_projection.py && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py tests/integration/test_practice_evidence_flow.py tests/integration/test_sales_value_training_flow.py`
  - Done when: completed sales projection 即使遇到 stale persisted snapshot 也会向 report / replay / history 输出同一份 aligned `main_issue` / `next_goal`，并且 evidence 不足时 fallback 原因可通过 log/test 直接定位。
- [ ] **T03: Surface the aligned coach conclusion on replay and admin read surfaces** `est:90m`
  - Why: 只修后端还不够；如果 replay 不显示 `main_issue` / `next_goal`，用户仍然无法肉眼对照“练中建议”和“练后报告”，admin labels 也会继续漏掉新 sales vocabulary。
  - Files: `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`, `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`, `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`, `web/src/app/admin/users/[id]/page.test.tsx`, `web/src/lib/session-evidence.ts`
  - Do: 扩展 `session-evidence` label maps，覆盖 S04 会暴露出来的 sales issue/goal types；在 replay 页新增只读的“本场教练结论”区块，直接渲染现有 API 返回的 `main_issue` / `next_goal`，位置放在阶段证据前，禁止在客户端另写 heuristic；更新 replay / report / admin focused tests，证明 report 与 replay 呈现同一结论族，admin badges 继续可读。
  - Verify: `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'`
  - Done when: replay 页面可见与 report 同源的主问题 / 下一目标，admin 页面能渲染当前 sales vocabulary，对齐逻辑没有被挪到前端重算。

## Files Likely Touched

- `backend/src/common/effectiveness/evaluator.py`
- `backend/src/common/effectiveness/schemas.py`
- `backend/src/common/effectiveness/__init__.py`
- `backend/src/common/conversation/session_evidence.py`
- `backend/tests/unit/test_effectiveness_sales_report_alignment.py`
- `backend/tests/unit/test_session_evidence_service.py`
- `backend/tests/unit/test_replay_service.py`
- `backend/tests/unit/test_history_service_evidence_projection.py`
- `backend/tests/contract/test_practice_evidence_contract.py`
- `backend/tests/integration/test_practice_evidence_flow.py`
- `backend/tests/integration/test_sales_value_training_flow.py`
- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx`
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx`
- `web/src/app/admin/users/[id]/page.test.tsx`
- `web/src/lib/session-evidence.ts`
