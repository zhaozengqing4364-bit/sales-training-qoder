---
estimated_steps: 1
estimated_files: 1
skills_used: []
---

# T03: Write the final export and permission acceptance guardrails for M005

Validate that the same current admin chain can produce an export/operating pack with the right permission boundary and evidence semantics, and write the final acceptance notes. This is the last guardrail before calling M005 operationally usable.

## Inputs

- `.gsd/milestones/M005/M005-ROADMAP.md`
- `.gsd/milestones/M005/slices/S05/S05-UAT.md`
- `backend/src/admin/api/analytics.py`
- `web/src/app/admin/analytics/page.tsx`

## Expected Output

- `.gsd/milestones/M005/slices/S05/tasks/T03-PLAN.md`

## Verification

rg -n "export|permission|weekly|drill-in" .gsd/milestones/M005/slices/S05/tasks/T03-PLAN.md
