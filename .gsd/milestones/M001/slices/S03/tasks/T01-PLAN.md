---
estimated_steps: 4
estimated_files: 6
skills_used:
  - safe-grow
  - react-best-practices
  - vercel-react-best-practices
  - baseline-ui
  - accessibility
  - fixing-accessibility
  - best-practices
  - make-interfaces-feel-better
  - test-driven-development
  - verification-before-completion
---

# T01: 重排单次报告首屏并替换占位建议文案

**Slice:** S03 — 单次报告可读化（学员 + 主管）
**Milestone:** M001

## Description

这个任务只做一件事：把 S02 已经可信的 unified evidence contract 翻译成学员能立即采取行动的单次报告首屏。不要新建评分逻辑，不要把 ComprehensiveReport 当权威，也不要继续保留 generic suggestion / fake export 这种会伤害信任的占位层。完成后，报告第一屏必须先回答“结果如何、卡在哪、下一轮怎么练、证据是什么”，其余 diagnostics 只做增强层。

## Steps

1. 在 `backend/src/common/api/practice.py` 为 `/practice/sessions/{session_id}/report` 增加 deterministic suggestions builder，只使用 `overall_result`、`main_issue`、`next_goal`、`evaluable`、`not_evaluable_reason`、`stage_summary` 等 unified projection 字段生成建议，并在 `backend/tests/contract/test_practice_evidence_contract.py` 锁定新 contract。
2. 更新 `web/src/lib/session-evidence.ts` 与 `web/src/lib/api/types.ts`，补齐 evidence completeness 的人类标签（尤其 `presentation`、`message_scores`、`stage_evidence`）并保持 report 类型与新 suggestion semantics 一致。
3. 重构 `web/src/app/(user)/practice/[sessionId]/report/page.tsx`：首屏改成结论 / 主问题 / 下一轮唯一目标 / 关键证据四段式；knowledge check、voice policy snapshot、enhanced report、highlights 继续保留但下沉；保留 non-evaluable / completeness 提示；移除无 handler 的“导出报告”按钮。
4. 在 `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx` 先补 failing tests，再完成实现，覆盖 deterministic suggestions、首屏主路径排序、not-evaluable 清晰提示、enhanced/highlights 缺失时的稳定降级。

## Must-Haves

- [ ] `report.suggestions` 不再返回占位英文文案，而是基于 unified evidence 字段生成具体、可执行、可测试的建议。
- [ ] 报告首屏在 enhanced/highlights 缺失时仍能基于 unified evidence contract 清楚展示结论、主问题、下一轮和关键证据，不再把 diagnostics 挤到主阅读路径前面。

## Verification

- `cd backend && pytest tests/contract/test_practice_evidence_contract.py`
- `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'`

## Observability Impact

- Signals added/changed: report payload 的 `suggestions` 现在可作为 deterministic coaching copy 诊断面；现有 `[Report]` debug logs 继续区分 unified evidence、enhanced fallback、highlights fallback。
- How a future agent inspects this: 直接查看 `/practice/sessions/{id}/report` 响应、`web/src/app/(user)/practice/[sessionId]/report/page.test.tsx` 断言，以及页面上方的 non-evaluable / completeness 提示文案。
- Failure state exposed: 未来若 suggestion builder 回退成占位文本、evidence completeness 标签退回机器字段、或首屏排序再次漂移，contract test 和 page test 都会直接失败。

## Inputs

- `backend/src/common/api/practice.py` — 当前 report API 仍返回 `Review your performance and practice again!` 这类占位建议。
- `backend/tests/contract/test_practice_evidence_contract.py` — 已验证 report/replay 共享 unified evidence contract，适合补 suggestion-level contract 断言。
- `web/src/lib/api/types.ts` — report contract 的前端类型边界。
- `web/src/lib/session-evidence.ts` — completeness / stage 文案翻译层，当前仍会暴露机器字段。
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx` — 当前单次报告主页面，信息层级仍混杂。
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx` — 现有 focused tests，只锁 unified-evidence / degraded-enhancement 的一部分行为。

## Expected Output

- `backend/src/common/api/practice.py` — report API 改为输出 deterministic suggestions，而不是占位文案。
- `backend/tests/contract/test_practice_evidence_contract.py` — 锁住 report suggestion 与 unified evidence contract 的关系。
- `web/src/lib/api/types.ts` — report 类型与 deterministic suggestion / completeness labels 对齐。
- `web/src/lib/session-evidence.ts` — 对 evidence completeness 中的缺失字段给出可读标签。
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx` — 首屏重排为结论 / 主问题 / 下一轮 / 关键证据，且去掉死的导出按钮。
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx` — focused tests 覆盖首屏排序、建议文案与降级行为。
