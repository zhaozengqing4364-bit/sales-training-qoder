# S02: Persona / scenario / industry pack 运营化 — UAT

**Milestone:** M022
**Written:** 2026-04-14T07:36:48.959Z

# S02 UAT — Persona / scenario / industry pack 运营化

## Preconditions
- Use an environment with at least one sales Agent, one linked Persona, one bound knowledge base, and one sales Scenario.
- The Persona should contain customer-pressure configuration (for example pressure axes / expected questions / follow-up style) and at least one knowledge binding.
- Use an admin account that can open `/admin/personas/[id]` and `/admin/agents/[id]`.
- Have API access to fetch the created practice session detail/report/replay payloads.

## Test Case 1 — Admin persona detail exposes the industry-pack contract on the existing entrypoint
1. Open `/admin/personas/{personaId}` for a sales persona that has customer-pressure content and knowledge bindings.
   - Expected: the existing persona detail page loads normally; no second content-management surface is introduced.
2. Find the `Industry Pack 合同` card.
   - Expected: the card explains which field groups belong to persona/customer pressure/knowledge bundle and which runtime/report targets they affect.
3. Confirm the card shows the runtime/evidence targets instead of only prompt prose.
   - Expected: the UI makes it clear that persona/customer pressure affects runtime behavior and report evidence, and that the same contract is inspectable rather than hidden in free-form prompt text.
4. Save the persona with an allowed content edit (for example updating pressure copy without removing the structure).
   - Expected: save succeeds, the page stays on the editor, and the contract card remains visible after the updated fetch.

## Test Case 2 — Admin agent detail explains the runtime shell boundary without inventing a new platform
1. Open `/admin/agents/{agentId}` for an agent linked to the persona above.
   - Expected: the page loads through the existing agent detail route.
2. Find the `Industry Pack 运行合同` card.
   - Expected: the card explains that the agent owns runtime shell/capability defaults, while composed industry-pack behavior still depends on persona/knowledge/scenario surfaces.
3. Verify the page does not imply a standalone `industry_pack` CRUD surface.
   - Expected: copy stays aligned with the composed-asset model and points back to existing admin entrypoints.

## Test Case 3 — A created sales session freezes runtime provenance in `voice_policy_snapshot_ref.runtime_binding`
1. Create a new sales practice session using the configured agent/persona/scenario.
   - Expected: session creation succeeds and returns a session id.
2. Fetch the session detail payload (`GET /api/v1/practice/sessions/{sessionId}`).
   - Expected: `voice_policy_snapshot_ref.runtime_binding` is present.
3. Inspect the frozen `runtime_binding` payload.
   - Expected: it identifies the customer-pressure source, sales focus / pressure behavior, bound knowledge bases, and the surfaces affected by the contract.
4. Fetch the canonical report payload for the same session (`GET /api/v1/practice/sessions/{sessionId}/report`) and the replay payload (`GET /api/v1/sessions/{sessionId}/replay`).
   - Expected: both surfaces expose the same frozen `voice_policy_snapshot_ref.runtime_binding` contract rather than recomputing from current admin data.

## Test Case 4 — Frozen provenance survives later admin edits
1. After creating the session above, edit the underlying persona or knowledge selection in admin.
   - Expected: admin save succeeds.
2. Re-fetch the already-created session detail/report/replay payloads.
   - Expected: the previously created session keeps the original `voice_policy_snapshot_ref.runtime_binding`; the historic session does not drift to the newly edited admin state.
3. Create one additional new sales session after the edit.
   - Expected: the new session reflects the updated contract, showing that S02 changed future runtime behavior without mutating historical provenance.

## Edge Cases
- If the scenario package narrative changes but persona/knowledge bindings do not, the session entry copy may change, but `runtime_binding` must still point to persona/customer-pressure/knowledge bundle authorities rather than claiming the scenario package is the runtime truth source.
- If the knowledge bundle is removed from a persona, the admin/persona contract should still render, and newly created sessions should show the changed frozen knowledge-binding state explicitly instead of silently borrowing old evidence provenance.
- If a runtime/report/replay fetch is missing `voice_policy_snapshot_ref.runtime_binding`, treat that as a blocking regression for this slice because downstream manager/admin work depends on that frozen provenance seam.
