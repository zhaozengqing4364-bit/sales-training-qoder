# S03: 资产影响面与健康治理 — UAT

**Milestone:** M005
**Written:** 2026-03-26T10:25:21.888Z

# S03: 资产影响面与健康治理 — UAT

**Milestone:** M005
**Written:** 2026-03-26

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: this slice extends current admin routes and pages with deterministic governance summaries and fault-linked asset references, so seeded-route checks and focused page assertions prove the shipped contract directly without a new runtime flow.

## Preconditions

- Backend is running with admin auth enabled and seeded data for at least one knowledge base, persona, presentation, and voice runtime profile.
- The seeded data includes recent sessions and at least one typed runtime anomaly, such as `kb_lock_blocked_search_failed`, `stuck_scoring`, or `presentation_degraded_missing_page_metadata`.
- At least one support/runtime fault carries `diagnostics.linked_asset_changes` references.
- Web admin pages are pointed at the same backend data set.

## Smoke Test

1. Open `/admin/knowledge` as an admin.
2. Confirm the page shows a `治理视图` section and at least one asset row/card with impact, recent-change, and anomaly copy.
3. **Expected:** the current knowledge page already shows governance context inline; there is no separate governance page to open.

## Test Cases

### 1. Knowledge base governance stays on the current page

1. Navigate to `/admin/knowledge`.
2. Locate a seeded knowledge base with recent usage.
3. Verify the page shows the asset name plus governance copy for impact range, recent change label/count, and sample anomaly text.
4. **Expected:** the knowledge asset shows a shared governance summary inline, including impact level, recent session impact, a recent change label, and blocking/warning anomaly context.

### 2. Persona page combines policy audit and runtime governance

1. Navigate to `/admin/personas`.
2. Locate a persona that still carries a policy-health issue such as legacy pressure-model drift.
3. Verify the page shows both the existing Persona policy audit context and the new governance summary for recent impact, recent changes, and anomalies.
4. **Expected:** policy audit and governance context coexist on the same current page, and the governance section uses the same shared vocabulary as the knowledge page.

### 3. Presentation and voice-runtime pages reuse the same governance contract

1. Navigate to `/admin/presentations`.
2. Confirm a presentation row/card shows impact range, recent-change copy, and warning-level anomaly context such as degraded presentation evidence.
3. Navigate to `/admin/voice-runtime`.
4. Confirm the profile list shows governance context and the selected profile pane shows `当前治理上下文` with the same governance summary.
5. **Expected:** both pages render the same governance_summary contract inline on the existing surfaces; the runtime page shows it both in the list and in the selected editor pane.

### 4. Analytics page links runtime faults back to recent asset changes

1. Navigate to `/admin/analytics`.
2. Find the `异常关联资产变更` section.
3. Confirm a blocking or warning fault is shown with its runtime summary.
4. Verify the same card includes one or more linked assets with admin links, impact level badges, and recent change labels.
5. If a session id is present, follow `查看对应报告`.
6. **Expected:** analytics lets the operator move from a runtime anomaly to the affected session report and the likely recent asset change without leaving the current admin chain.

### 5. User detail page surfaces the same fault-linked change context inside session history

1. Navigate to `/admin/users/{id}` for a learner whose recent session is referenced by a linked runtime fault.
2. Locate the affected session row/card.
3. Confirm it shows `最近运行异常：...` plus linked asset chips and recent change labels.
4. Open one linked asset page from the chip.
5. **Expected:** the current user detail page shows the same fault-backed asset-change context inline on the session row, and the asset link lands on the existing admin asset surface.

## Edge Cases

### No linked asset changes on a current fault

1. Open `/admin/analytics` with a data set where current blocking/warning faults have no `linked_asset_changes` payload.
2. Inspect the anomaly-linkage section.
3. **Expected:** the page shows the explicit empty-state copy instead of stale or guessed asset links.

### Low-usage or healthy asset

1. Open any current asset page with an asset that has no recent sessions and no anomalies in the active window.
2. Inspect the governance card.
3. **Expected:** impact stays low and the health section does not fabricate blocking or warning context.

## Failure Signals

- Any current asset route stops returning `governance_summary`.
- The current asset pages render raw JSON/nulls or omit governance copy entirely.
- Analytics or user detail shows a runtime fault but no linked asset context when `diagnostics.linked_asset_changes` is present in the payload.
- Knowledge-base kb-lock faults collapse into a generic `knowledge_search_failed` label instead of preserving the typed `kb_lock_blocked_search_failed` anomaly semantics.
- Presentation degraded evidence is misclassified as blocking when the contract says warning.

## Requirements Proved By This UAT

- none — this slice improves current admin operability surfaces, but it does not change any tracked requirement status by itself.

## Not Proven By This UAT

- Full historical asset audit timelines or per-change causal proof.
- Cohort-level or weekly operating summaries; that belongs to S04.
- Automated supervisor recommendations based on the new governance context.

## Notes for Tester

Use the existing asset pages and current analytics/user-detail routes; there is intentionally no separate governance console. If you automate DOM assertions, remember these admin pages render both mobile-card and desktop-table shells, so asset names may appear more than once in the DOM even when the UI is correct.
