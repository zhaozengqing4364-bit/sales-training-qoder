---
estimated_steps: 1
estimated_files: 2
skills_used: []
---

# T03: 回填后续 slices 的 verification baseline

把每个后续 slice 所需的 focused command 回填到里程碑/切片计划中，形成统一 verification contract。

## Inputs

- `docs/plans/2026-04-08-system-audit-remediation-plan.md`
- `.gsd/milestones/M014/M014-ROADMAP.md`
- `.gsd/milestones/M015/M015-ROADMAP.md`
- `.gsd/milestones/M016/M016-ROADMAP.md`
- `.gsd/milestones/M017/M017-ROADMAP.md`
- `.gsd/milestones/M018/M018-ROADMAP.md`

## Expected Output

- `docs/plans/2026-04-08-system-audit-remediation-plan.md`
- `.gsd/milestones/M013/M013-ROADMAP.md`

## Verification

rg -n "npm --prefix web test|backend/venv/bin/python -m pytest" .gsd/milestones/M01{4,5,6,7,8}*/**/*.md docs/plans/2026-04-08-system-audit-remediation-plan.md

## Observability Impact

none
