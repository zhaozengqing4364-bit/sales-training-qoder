# S02: Persona 压力模型 snapshot 化 — UAT

**Milestone:** M003
**Written:** 2026-03-25T03:09:08.016Z

## UAT Type

- UAT mode: mixed
- Why this mode is sufficient: this slice changes an admin editing surface plus a frozen runtime/session contract, so the strongest proof is a combination of focused automated gates and a short operator script that inspects the actual snapshot fields instead of judging Persona behavior from prose.

## Preconditions

- Backend and web apps are running against a development dataset with admin access.
- At least one sales Agent is linked to a ready knowledge base.
- You have two Personas bound to the same Agent/knowledge base, or can create them on the current admin Persona page.
- If you need to inspect persistence directly, you can query the created sales session through the existing session detail/report/replay APIs or database.

## Smoke Test

1. Open `/admin/personas/{personaId}` for a sales Persona.
2. Confirm the page shows the `当前 Persona 压力模型` section.
3. Change `主压测方向` and save.
4. Reopen the page.
5. **Expected:** the changed pressure direction is still present, and the page describes the model as a structure that runtime snapshots can audit.

## Test Cases

### 1. Edit and persist an explicit pressure model on the current Persona detail page

1. Open `/admin/personas/{personaId}` for a Persona that is linked to a knowledge base.
2. In `当前 Persona 压力模型`, set:
   - `主压测方向` = `价格` or `案例证据`
   - `价值维度` = two newline-separated entries
   - `异议维度` = two newline-separated entries
   - `追问策略` = `单点追问` or `递进追问`
   - toggle `回避时继续追问` / `必须给出证据`
   - add one example follow-up question
3. Click `保存`.
4. Reopen the same Persona detail page.
5. **Expected:** all edited values persist; the page still shows the nested pressure-model state instead of falling back to blank/generic prompt text.

### 2. Audit a legacy-only Persona row on the current list/audit surface

1. Use or seed a Persona whose `persona_policy` still only has flat `sales_focus` / `value_axes` / `objection_axes` / `expected_customer_questions` fields and no nested `customer_pressure`.
2. Open the current admin Persona list/policy-health surface.
3. Inspect the health/audit output for that Persona.
4. Save the Persona once through the current detail page without changing anything else.
5. Refresh the policy-health surface.
6. **Expected:** before resave, the row is flagged with `pressure_model_legacy_only`; after resave, the current GET/detail surface shows a nested `customer_pressure` contract and the legacy-only audit issue no longer represents that row.

### 3. Freeze different pressure contracts into different sessions using the same knowledge base

1. Prepare two Personas bound to the same Agent and knowledge base:
   - Persona A focuses on `案例证据` / proof and requires revisiting evasion.
   - Persona B focuses on `价格` and does not revisit evasion.
2. Create one new sales session for Persona A and one new sales session for Persona B through `POST /api/v1/practice/sessions`.
3. Inspect each created session’s `voice_policy_snapshot` via the current session detail route or database.
4. Compare `voice_policy_snapshot.customer_pressure`, `voice_policy_snapshot.source.customer_pressure_source`, and `instruction_contract_hash` across the two sessions.
5. **Expected:** the two sessions preserve different frozen pressure directions/behaviors even though they share the same knowledge base; `customer_pressure_source` is `explicit`; the instruction contract hashes differ.

### 4. Confirm later admin edits do not rewrite an existing session’s frozen contract

1. Create a new sales session from a Persona with a known pressure model.
2. Capture that session’s `voice_policy_snapshot.customer_pressure`.
3. Edit the Persona on `/admin/personas/{personaId}` and change the pressure model.
4. Re-read the original session via session detail, report, or replay inspection.
5. **Expected:** the already-created session still exposes the original frozen `customer_pressure` snapshot; only newly created sessions pick up the new pressure model.

### 5. Confirm the snapshot baseline remains stable when runtime diagnostics append later

1. Create a new sales session and note its `voice_policy_snapshot_ref` fields.
2. Let runtime diagnostics append `runtime_metrics` to the snapshot, or simulate the append in a seeded/dev fixture.
3. Read the same session through session detail plus report/replay snapshot references.
4. **Expected:** mutable runtime diagnostics can append under `runtime_metrics`, but the immutable snapshot reference baseline remains stable across the detail/report/replay reads.

## Edge Cases

### Legacy row canonicalization

1. Open a Persona that still came from flat legacy fields.
2. Save it through the current detail page without adding a new management step.
3. **Expected:** the persisted Persona now carries a nested `customer_pressure` contract and stops relying on read-time legacy-only derivation.

### Empty pressure model

1. Clear the pressure direction, value axes, objection axes, and sample follow-up fields on the current detail page.
2. Save the Persona.
3. **Expected:** the saved model resolves to no explicit pressure context instead of inventing a fake direction; downstream inspection should show `source: none` rather than a random fallback behavior.

## Failure Signals

- The admin Persona detail page renders only prompt text and no structured `当前 Persona 压力模型` section.
- Saving a Persona updates flat `sales_focus` fields but leaves `persona_policy.customer_pressure` missing.
- `/api/v1/admin/personas/policy-health` cannot distinguish `pressure_model_legacy_only` rows from healthy rows.
- Two sessions created from different Personas on the same knowledge base end up with the same `voice_policy_snapshot.customer_pressure` unexpectedly.
- Editing a Persona after session creation mutates the old session’s frozen snapshot.
- Snapshot refs drift across detail/report/replay after runtime metrics append.

## Requirements Proved By This UAT

- R010 — Persona configuration on the current admin surface now materially changes the frozen runtime/session contract instead of staying as prompt-only flavor, and that contract is inspectable on the live session snapshot chain.

## Not Proven By This UAT

- S03’s multi-turn objection ledger and whether unresolved objections survive topic drift across live conversation turns.
- S04’s unsupported/evidence-pending/evidence-backed truth contract.
- S05’s full objection-heavy live runtime/browser UAT with real reconnect behavior and user-perceived realism.

## Notes for Tester

Judge the slice by the frozen snapshot fields and audit surfaces, not by whether one short chat transcript “feels” more aggressive. The reliable inspection points are `persona_policy.customer_pressure`, `PracticeSession.voice_policy_snapshot.customer_pressure`, `voice_policy_snapshot.source.customer_pressure_source`, and the current policy-health output on admin Personas.
