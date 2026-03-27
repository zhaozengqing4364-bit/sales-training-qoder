---
id: M005
title: "后台治理与规模化运营"
status: complete
completed_at: 2026-03-27T02:14:13.827Z
key_decisions:
  - D074 / admin score-bearing aggregates continue to project from HistoryService + SessionEvidenceService summaries instead of legacy weighted SQL score math.
  - Supervisor workflow state stays durable but minimal via a dedicated `manager_interventions` table on the current admin API chain.
  - `/admin/users/[id]` remains the single supervisor authority surface, with manager-lite and weekly operating-pack cards acting as launchers through explicit focus query params.
  - RuntimeStatusService remains the shared asset-governance seam, with `governance_summary` and `linked_asset_changes` extending current admin routes/pages instead of creating a separate governance console.
  - The weekly operating pack remains a fixed 7-day read model beside broader analytics filters, and cross-page drill-ins preserve context via explicit `focusBucket` / `focusIssueFamily` / `focusNote`.
key_files:
  - backend/src/common/analytics/admin_analytics_service.py
  - backend/src/admin/api/analytics.py
  - backend/src/admin/api/users.py
  - backend/src/admin/api/interventions.py
  - backend/src/common/analytics/history_service.py
  - backend/src/support/services/runtime_status_service.py
  - backend/src/common/knowledge/api.py
  - backend/src/agent/services/persona_service.py
  - backend/src/presentation_coach/api/presentations.py
  - backend/src/admin/api/voice_runtime.py
  - web/src/app/admin/analytics/page.tsx
  - web/src/app/admin/users/[id]/page.tsx
  - web/src/components/admin/manager-lite-panel.tsx
  - web/src/app/admin/knowledge/page.tsx
  - web/src/app/admin/personas/page.tsx
  - web/src/app/admin/presentations/page.tsx
  - web/src/app/admin/voice-runtime/page.tsx
  - web/src/lib/api/types.ts
lessons_learned:
  - One projection-backed evidence line can support admin analytics, supervisor intervention results, weekly operating views, and anomaly triage without inventing a second admin truth source.
  - Manager-lite and weekly-pack cards stay trustworthy when they launch into one authority page with explicit context instead of owning parallel workflow state.
  - Asset governance is more actionable when recent changes and anomalies are rendered inline on the pages operators already use, with direct links back to affected reports/sessions.
  - Milestone close-out should rerun a combined backend/web admin governance suite in addition to reading slice summaries, because assembled-route behavior is the real acceptance surface.
---

# M005: 后台治理与规模化运营

**现有 admin analytics / users / asset pages 现在形成了一条可运营的治理链路：主管能设重点、发提醒、复查结果，运营能在原有页面上看到资产影响与团队周节奏。**

## What Happened

M005 没有再造第二个后台产品，而是把已经存在的 `/admin/analytics*`、`/admin/users*`、知识库 / Persona / PPT / voice runtime 资产页，收口成一条真正可运营的治理链路。S01 先把 admin analytics、manager-lite 和用户 drill-in 统一到 `HistoryService` / `SessionEvidenceService` 的 projection-backed evidence line 上，让 score basis、evaluability、issue family、next-goal family 与 canonical `/practice/{sessionId}/report` 说同一套语言；S02 在同一条 admin 用户链路上加了持久化 `manager_interventions`、提醒状态和 read-side intervention results，让主管可以在 `/admin/users/[id]` 里设训练重点、记录提醒并回看后续结果；S03 再把 `RuntimeStatusService` 扩成 shared governance seam，把 `governance_summary` 与 `linked_asset_changes` 直接挂到当前 knowledge / persona / presentation / voice-runtime / analytics / user-detail 页面上；S04 把这些能力收口成 fixed 7-day operating pack，让团队负责人在当前 `/admin/analytics` 就能看 weekly blocker buckets、department issue views、current-risk / inactive / improving lists，并通过显式 `focusBucket` / `focusIssueFamily` / `focusNote` drill 到同一张 `/admin/users/[id]` authority page；S05 最后在 shipped admin route family 上完成了 analytics → user drill-in → focus/reminder → canonical report/replay review → weekly pack/export/RBAC guardrails 的组织化 UAT，证明整个链路可以按当前产品形态运营起来。

Close-out verification 也重新跑了一遍，而不是只复述 slice 内结论：`git diff --stat HEAD $(git merge-base HEAD 001-ai-practice-system) -- ':!.gsd/'` 返回大量非 `.gsd` 代码改动，满足“不是只产出规划工件”的硬门禁；为了避免集成基线过宽，我们还对 `d3fb63e`（M004 complete commit）做了 milestone-local diff，确认 M005 自身包含 39 个非 `.gsd` 文件差异。Fresh verification 重新执行了 backend admin analytics / users / interventions / asset governance / RBAC / analytics contract suites（49 passed）以及 web admin analytics / asset governance / user detail / manager-lite suites（4 files / 19 tests passed）。同时，现有 `.gsd/milestones/M005/M005-VALIDATION.md` verdict 为 `pass`，明确记录 success criteria、slice delivery audit、cross-slice integration 与 requirement coverage 全部闭合。

### Decision Re-evaluation

| Decision | Current assessment | Evidence from delivered milestone | Next-mile input |
|---|---|---|---|
| **D074 / admin aggregates must project from `HistoryService` + `SessionEvidenceService` instead of legacy weighted SQL math** | **Still valid** | S01 与 S04 都建立在同一条 projection-backed summary line 上；fresh backend suite 的 `test_admin_analytics_service`、`test_admin_users_api`、`test_analytics` 继续通过。 | 继续作为 admin score/evaluability 的唯一默认做法。 |
| **Use a dedicated `manager_interventions` table instead of stretching current admin routes into a generic task system** | **Still valid** | S02 证明 create / remind / result / resolving-session linkage 可以在最小 durable workflow state 下闭合；fresh `test_admin_interventions_api` 通过。 | 仅当未来明确进入外部通知、多负责人协作或批量队列场景时再评估更通用的 workflow model。 |
| **Keep `/admin/users/[id]` as the supervisor authority page; manager-lite and weekly pack act as launchers** | **Still valid** | S02/S04/S05 的 drill-in 和 live UAT 都复用了同一 authority surface，没有出现第二套表单/状态编排。 | 继续保留单一 authority page，避免 manager-lite 或 weekly pack 漂成 shadow console。 |
| **Reuse `RuntimeStatusService` as the shared governance seam and surface `governance_summary` / `linked_asset_changes` inline on current pages** | **Still valid** | S03 在四类资产页、analytics、user detail 上都复用了这一 seam；fresh `test_asset_governance_api` 与前端 asset-governance tests 继续通过。 | 如果后续需要更长时间跨度的资产审计，应该在这个 seam 上扩历史层，而不是重做第二套治理 API。 |
| **Treat the weekly operating pack as its own fixed 7-day read model and preserve context with explicit `focusBucket` / `focusIssueFamily` / `focusNote` query params** | **Still valid** | S04/S05 证明 weekly pack 与 broader analytics filters 可以并存而不互相篡改语义，risk/improving drill-ins 也保持上下文一致。 | 只有在未来明确需要 monthly / custom cadence pack 时，才考虑新增 read model；不要让现有 weekly pack 被全局过滤器吞掉。 |

## Success Criteria Results

Fresh close-out verification reran the milestone's current admin surfaces: backend suite `tests/unit/common/test_admin_analytics_service.py tests/unit/test_support_runtime_service.py tests/integration/test_admin_users_api.py tests/integration/test_admin_interventions_api.py tests/integration/test_asset_governance_api.py tests/integration/test_rbac_access_control_api.py tests/contract/test_analytics.py` passed **49/49**; web suite `src/app/admin/analytics/page.test.tsx src/app/admin/asset-governance.test.tsx src/app/admin/users/[id]/page.test.tsx src/components/admin/manager-lite-panel.test.tsx` passed **19/19**. `M005-VALIDATION.md` verdict is `pass`.

- ✅ **S01 semantic closure on current admin analytics and user drill-in** — Evidence: S01 summary/UAT plus fresh backend analytics/user tests show `/admin/analytics`、manager-lite、`/admin/users/[id]` all read from the same projection-backed evidence line as learner/supervisor reports, with explicit `score_basis`、evaluability、issue-family and canonical report drill-ins.
- ✅ **S02 supervisor focus/reminder loop works on current admin surfaces** — Evidence: S02 summary/UAT plus fresh `test_admin_interventions_api` and `test_admin_users_api` prove persisted `manager_interventions`, manager-lite deep links into `/admin/users/[id]`, reminder lifecycle state, and projection-backed `manager_intervention_results` on the shipped user-detail surface.
- ✅ **S03 operators can see recent changes, health anomalies, and likely impact range on current asset pages** — Evidence: S03 summary/UAT plus fresh `test_asset_governance_api` and `asset-governance.test.tsx` prove inline `governance_summary` on knowledge/persona/presentation/voice-runtime pages and `linked_asset_changes` on analytics/user detail without a separate governance console.
- ✅ **S04 team leads can see weekly issue buckets, risk lists, improving lists, and a one-week operating summary on current admin entrypoints** — Evidence: S04 summary/UAT, fresh `test_admin_analytics_service` / `test_analytics`, and passing `admin/analytics` + `admin/users/[id]` web suites prove `GET /api/v1/admin/analytics/operating-pack`, department/cohort buckets, evidence-insufficient / degraded breakdowns, and context-preserving weekly drill-ins.
- ✅ **S05 proves one real workflow across the shipped admin chain** — Evidence: S05 summary/UAT plus the fresh regression pack confirm analytics → user drill-in → focus/reminder → canonical report/replay review → weekly pack/export/RBAC guardrails on the shipped `/admin/analytics*` and `/admin/users/[id]` route family.
- ✅ **Milestone vision is met on the approved roadmap scope** — Combined evidence from S01-S05 and `M005-VALIDATION.md` shows the current admin routes now support evidence-aligned analytics, supervisor intervention, asset-health governance, weekly operating cadence, and an organized acceptance workflow without introducing a shadow admin product.

## Definition of Done Results

- ✅ **All roadmap slices are complete** — The preloaded `M005-ROADMAP.md` slice overview shows S01-S05 all marked done, and `gsd_complete_milestone` accepted the milestone only after validating slice completion in the DB.
- ✅ **All slice summaries and UAT artifacts exist on disk** — `find .gsd/milestones/M005/slices -maxdepth 2 -type f \( -name 'S*-SUMMARY.md' -o -name 'S*-UAT.md' -o -name 'S*-PLAN.md' \) | sort` returned `S01`-`S05` plan/summary/UAT files for every slice.
- ✅ **Cross-slice integration works on the promised boundaries** — `M005-VALIDATION.md` verdict is `pass`; its cross-slice audit records S01→S02, S01→S03, S02+S03→S04, S04→S05, and the milestone-wide current-route boundary as aligned with no material mismatch.
- ✅ **The milestone contains real implementation code, not only planning artifacts** — Required integration-branch proof `git diff --stat HEAD $(git merge-base HEAD 001-ai-practice-system) -- ':!.gsd/'` returned extensive non-`.gsd` code changes; a narrower milestone-local diff against `d3fb63e` (the M004 complete commit) also showed **39** non-`.gsd` files changed for M005 itself.
- ✅ **Fresh automated verification passed at close-out** — Backend admin governance suite passed **49/49** and web admin governance suite passed **19/19** in this close-out run.
- ℹ️ **Horizontal checklist** — No separate unretired horizontal-checklist items were surfaced by the rendered M005 roadmap/validation artifacts used for close-out.

## Requirement Outcomes

- **R012: Active → Validated**
  - Proof chain 1: S01 made current admin analytics, manager-lite, and user drill-in truthful on the same projection-backed evidence line as learner/supervisor reports.
  - Proof chain 2: S02 added persistent supervisor focus / reminder / result workflow on the current admin user surfaces via `manager_interventions` and read-side intervention results.
  - Proof chain 3: S03 added runtime-backed asset governance (`governance_summary`) and anomaly-to-change linkage (`linked_asset_changes`) on the current asset, analytics, and user-detail pages.
  - Proof chain 4: S04 added the fixed-cadence weekly operating pack with blocker buckets, risk/inactive/improving lists, and context-preserving drill-ins; S05 then proved the integrated workflow and operational guardrails on shipped routes.
  - Milestone-level proof: `M005-VALIDATION.md` verdict `pass`, fresh backend verification **49/49**, fresh web verification **19/19**.

- **R009: remains Active** — M005 reused but did not replace the existing M002 ownership; no status transition is claimed here.
- **R010: remains Active** — M005 reused but did not replace the existing M003 ownership; no status transition is claimed here.

## Deviations

None.

## Follow-ups

If the product later needs real reminder delivery, the current remind action should fan out to an external notification channel while `manager_interventions` remains the source of truth. If operators need a longer historical asset audit or non-weekly operating cadences, extend the current `governance_summary` / operating-pack seams instead of replacing them with a separate console.
