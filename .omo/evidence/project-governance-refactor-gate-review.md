# Project Governance Refactor Gate Review

recommendation: REJECT
verdict: FAIL
confidence: HIGH

## originalIntent

用户通过 `omo:ulw-loop` 要求执行并实现所有 task plans。提交范围 `5fb283c1f7bd6e26ff50028b4af1b6bc93648c56..a4670b80d58f70c2d57a2da1184aef05fa761623` 声称完成 Task 1-24 与 F1-F5 最终验证，用于 project governance refactor。

## desiredOutcome

Task 1-24 的实现、证据、代码审查、自动化验证、浏览器/手工 QA 与 release gate 应共同支持“完成但不夸大”的交付结论；若 release gate 仍为红灯，则不得宣称 release readiness 或门禁通过。

## userOutcomeReview

从用户视角，本次变更覆盖后端、前端、CI、脚本安全、AI coach、runtime boundary、文档与证据治理，属于高风险跨域治理重构。已提交证据显示部分后端和前端 focused gates 通过，但真实 release surface 未通过：critical quality gate 的 Playwright smoke 有 2 个失败，手工 QA 也未形成 release-valid 证据。因此用户想要的“已完成并可通过最终门禁”结果没有达成。

## reviewWorkLaneResult

<verdict>FAIL</verdict>
<confidence>HIGH</confidence>
<summary>提交范围包含大量实现与证据文件，但最终门禁不能通过。F4 明确记录 `bash scripts/critical-quality-gate.sh` 失败，F5 明确记录手工 QA 未执行；此外本次提交范围缺少可适用的 `remove-ai-slops`/`programming` 代码审查覆盖，直接快扫还发现新增超大模块。</summary>

<goal_breakdown>

- [ACHIEVED] Task 1-24 均有提交与 evidence 条目。
  - Evidence: `.omo/evidence/project-governance-refactor/f1-plan-compliance.md` 列出 Task 1-24 到提交的映射。
- [PARTIAL] 后端 focused verification。
  - Evidence: `.omo/evidence/project-governance-refactor/f2-backend-focused-gate.md` 记录 `alembic heads`、runtime dependency contract、363 个 selected pytest 通过。
- [PARTIAL] 前端 focused verification。
  - Evidence: `.omo/evidence/project-governance-refactor/f3-frontend-focused-gate.md` 记录 `npx tsc --noEmit` 与 selected vitest 通过，但也记录 browser QA 未执行。
- [MISSED] release critical gate 通过。
  - Evidence: `.omo/evidence/project-governance-refactor/quality-gate/f4-critical-quality-gate.md` 记录 Playwright smoke `7 passed / 2 failed`。
- [MISSED] release-valid manual QA。
  - Evidence: `.omo/evidence/project-governance-refactor/f5-manual-qa.md` 记录 planned admin/learner routes 未执行为有效手工 QA。

</goal_breakdown>

<constraint_compliance>

- [ACHIEVED] 不基于未提交工作树判断已提交成果。
  - Evidence: 本审查使用 `git show a4670b80:<path>` 读取 F1-F5 提交态内容；当前工作树存在同名模块未提交改动，未作为提交态事实来源。
- [PARTIAL] CodeGraph 优先。
  - Evidence: `.codegraph/` 存在，并已用 `codegraph_explore` 查询 sales-trainer routes、workflow hooks、inventory adapters 等结构线索；由于 CodeGraph 基于当前 dirty worktree，精确提交态证据仍以 `git show` 为准。
- [MISSED] 验证充分且 release readiness 不可在 gate red 时声称。
  - Evidence: F4/F5 均明确要求不要 claim release readiness。
- [MISSED] `remove-ai-slops` 与 `programming` 视角覆盖。
  - Evidence: 提交范围内的 F2/F3 focused gate 文件未包含 slop/overfit/programming coverage；`.omo/ulw-loop/evidence/phase-7-code-review.md` 与 `.omo/evidence/g008-quality-gate-code-review.md` 虽包含该检查，但范围是 G008/path-config governance，且不在本次提交范围内，不能替代当前 5fb283c1..a4670b80 的最终代码审查。
- [MISSED] 最小/可维护修改。
  - Evidence: 直接按 `programming`/`remove-ai-slops` pure LOC 规则扫描新增源码，发现 `web/src/lib/sales-trainer/routes.ts` 为 379 pure LOC、`web/src/app/(dashboard)/sales-trainer/business-skills/use-business-skills-workbench.ts` 为 346 pure LOC，均为本范围新增文件且超过 250 LOC 门槛。

</constraint_compliance>

## findings

- [FAIL] Critical quality gate red.
  - File: `.omo/evidence/project-governance-refactor/quality-gate/f4-critical-quality-gate.md`
  - Evidence: `bash scripts/critical-quality-gate.sh` failed; Playwright smoke `7 passed`, `2 failed`.
- [FAIL] User-visible smoke failures remain unresolved.
  - Files:
    - `.sisyphus/evidence/task-9-test-results/smoke-full-stack-smoke-baseline-practice-session-smoke-chromium/error-context.md`
    - `.sisyphus/evidence/task-9-test-results/smoke-full-stack-smoke-baseline-support-runtime-smoke-chromium/error-context.md`
  - Evidence: practice session `page.goto` timed out after 30000ms; support runtime login remained at `/login` instead of `/`.
- [FAIL] Manual QA evidence is not release-valid.
  - File: `.omo/evidence/project-governance-refactor/f5-manual-qa.md`
  - Evidence: `/admin/sales-trainer/paths`, `/admin/sales-trainer/operation-logs`, `/sales-trainer/business-skills`, `/sales-trainer/business-skills/coach` planned routes were not executed as a release-valid pass.
- [FAIL] Required slop/programming report coverage is absent for this range.
  - Files checked: F2, F3, F4, F5 committed evidence; `.omo/ulw-loop/evidence/phase-7-code-review.md`; `.omo/evidence/g008-quality-gate-code-review.md`
  - Evidence: committed F2/F3 are focused command summaries only; the available slop/programming report is scoped to G008 and not part of the committed range under review.
- [FAIL] Direct slop pass found unresolved oversized newly added modules.
  - Files:
    - `web/src/lib/sales-trainer/routes.ts` - 379 pure LOC
    - `web/src/app/(dashboard)/sales-trainer/business-skills/use-business-skills-workbench.ts` - 346 pure LOC
  - Evidence: measured from `git show a4670b80:<path>` excluding blank/comment lines.
- [WARN] Dependency governance remains explicitly blocked, not green.
  - File: `.omo/evidence/project-governance-refactor/task-21-ci-dependency-governance.txt`
  - Evidence: `pip_audit`, `pip-licenses`, and backend pyproject extras drift are recorded as blockers/prerequisites before claiming backend vulnerability/license proof.

## blocking_issues

1. Rerun and pass `bash scripts/critical-quality-gate.sh`, or obtain explicit release-owner waiver with evidence that the red Playwright smoke failures are external and accepted.
2. Execute and record release-valid manual QA for the planned admin/learner routes after the full stack is stable.
3. Produce an in-scope code review report for this committed range that explicitly covers `remove-ai-slops` overfit/slop criteria and `programming` criteria, supported by artifact paths.
4. Resolve or explicitly justify the newly added >250 pure LOC modules under the loaded `programming`/`remove-ai-slops` rules.
5. Do not claim release readiness until the dependency governance blockers in Task 21 are closed or formally waived.

## checkedArtifactPaths

- `.omo/evidence/project-governance-refactor/f1-plan-compliance.md`
- `.omo/evidence/project-governance-refactor/f2-backend-focused-gate.md`
- `.omo/evidence/project-governance-refactor/f3-frontend-focused-gate.md`
- `.omo/evidence/project-governance-refactor/quality-gate/f4-critical-quality-gate.md`
- `.omo/evidence/project-governance-refactor/f5-manual-qa.md`
- `.omo/evidence/project-governance-refactor/task-21-ci-dependency-governance.txt`
- `.omo/evidence/project-governance-refactor/task-20-script-inventory.txt`
- `.sisyphus/evidence/task-9-quality-gate.txt`
- `.sisyphus/evidence/task-9-test-results/smoke-full-stack-smoke-baseline-practice-session-smoke-chromium/error-context.md`
- `.sisyphus/evidence/task-9-test-results/smoke-full-stack-smoke-baseline-support-runtime-smoke-chromium/error-context.md`
- `.omo/ulw-loop/evidence/phase-7-code-review.md`
- `.omo/ulw-loop/evidence/phase-7-gate-review.md`
- `.omo/ulw-loop/evidence/phase-7-qa-review.md`
- `.omo/evidence/g008-quality-gate-code-review.md`
- `.omo/evidence/qa-review-5fb283c1-a4670b80/notepad.md`

## exactEvidenceGaps

- No in-range final code review artifact proving `remove-ai-slops` and `programming` coverage for the actual `5fb283c1..a4670b80` committed range.
- No release-valid browser/manual QA for the four planned sales-trainer routes after the F4 red gate.
- No green rerun of `bash scripts/critical-quality-gate.sh` after the two Playwright smoke failures.
- No committed artifact closing Task 21 dependency governance blockers (`pip_audit`, `pip-licenses`, backend pyproject extras drift).
- No accepted waiver documenting that the smoke failures, manual QA gap, slop/programming coverage gap, and dependency governance blockers are release-approved despite remaining open.
