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

## Final Acceptance Guardrails

### Export surface stays on the current admin chain

- `web/src/app/admin/analytics/page.tsx` keeps `导出报表` on the shipped `/admin/analytics` route and forwards the currently selected `time_range` to the existing CSV export call.
- `backend/src/admin/api/analytics.py` keeps `GET /api/v1/admin/analytics/export` on the same admin analytics surface and returns the current CSV attachment with `系统概览` / `分数分布` / `趋势数据` / `用户排行榜` sections.
- Existing execution proof remains valid here: `web/src/app/admin/analytics/page.test.tsx` covers the current-window export click, and `backend/tests/contract/test_analytics.py` confirms the export stays on the current CSV contract.

### Permission boundary is enforced on both web and API entrypoints

- `web/src/app/admin/layout.tsx` gates the admin shell with `requireServerSession({ requiredRoles: ["admin"], unauthorizedRedirectTo: "/" })`, so a non-admin cannot open the current analytics page.
- `backend/src/main.py` mounts `admin_analytics_router` with `dependencies=[Depends(get_current_admin_user)]`, so the same permission boundary applies to `/admin/analytics/operating-pack` and `/admin/analytics/export`.
- T03 adds a targeted backend RBAC regression so non-admin tokens now explicitly prove both admin analytics routes return `403` with the standard traceable error envelope instead of relying on broad admin-route coverage alone.

### Weekly pack and drill-in evidence semantics remain aligned

- The weekly operating pack on `/admin/analytics` still uses the unified evidence score basis `session_evidence_projection_evaluable_only`, so weekly counts, blocker families, and manager lists stay aligned with the same semantics proven in S05 UAT.
- The live drill-in route remains the current `/admin/users/{id}` entry with carried weekly context, and review still stays on the canonical `/practice/{sessionId}/report` and `/practice/{sessionId}/replay` surfaces documented in `.gsd/milestones/M005/slices/S05/S05-UAT.md`.
- Non-blocking carry-forward findings from T02 remain unchanged: the persisted intervention card still shows the raw issue-family key and the optional enhanced-report path still emits fallback noise, but neither finding breaks the weekly pack → drill-in → reminder → report/replay operating chain.

## Final Acceptance Notes

M005 now has the last operational guardrails it needed on the current admin chain: the weekly pack is still the real analytics entrypoint, the export stays on the shipped admin CSV surface, and the permission boundary is explicit at both the web shell and backend route layer. With these guardrails plus the T01 regression pack and T02 live workflow evidence, S05 can treat the current admin analytics → drill-in → focus/reminder → report/replay flow as operationally usable without introducing a separate acceptance-only surface.
