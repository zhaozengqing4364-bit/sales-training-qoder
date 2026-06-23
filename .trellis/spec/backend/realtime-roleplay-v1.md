# Realtime Roleplay V1 Runtime Contract

> Executable backend contract for the fixed information-technology-leader roleplay v1 in `sales_bot`.

## Scenario: IT Leader First-Visit Roleplay V1

### 1. Scope / Trigger

- Trigger: changing the fixed v1 realtime customer roleplay for state-owned, central-enterprise, government, education, or healthcare information-technology leaders.
- Scope: `sales_bot` platform direct-practice runtime only: `VoiceRuntimePolicyService`, `VoiceInstructionCompiler`, StepFun realtime policy/state helpers, knowledge search degradation, offline scoring/report projection, and v1 regression fixtures.
- Not scope: `sales_trainer` newcomer-training realtime placeholder, curriculum `PracticeTemplate` entry, DB migrations, new realtime handlers, large admin UI, live LLM/TTS/StepFun calls in tests.

### 2. Signatures

Enable v1 through persona policy:

```python
persona_policy = {
    "it_leader_roleplay_v1": {
        "enabled": True,
    },
}
```

Runtime snapshot fields:

```python
voice_policy_snapshot = {
    "roleplay_contract": dict,
    "roleplay_contract_hash": "sha256:<hex>",
    "session_state_card": {
        "state_card_version": int,
        "sequence": int,
        "current_phase": str,
        "customer_attitude": str,
        "confirmed_facts": list[str],
        "learner_actions": list[str],
        "missing_actions": list[str],
        "objections": list[str],
        "next_pressure": str | None,
        "quality_flags": list[str],
    },
}
```

Observable runtime fields:

```python
roleplay_observability = {
    "roleplay_contract_hash": str | None,
    "state_card_version": int | None,
    "violation_count": int,
    "blocking_violation_count": int,
    "knowledge_timeout_count": int,
    "quality_flags": list[str],
    "manual_review_required": bool,
}
```

### 3. Contracts

- V1 runs through platform direct practice only. Do not create a new WebSocket runtime or activate `sales_trainer` realtime.
- Runtime consumes the frozen `voice_policy_snapshot`. Reconnect/restore must use persisted `roleplay_contract`, `roleplay_contract_hash`, and `session_state_card`; it must not rebuild from latest Persona/KB assets.
- Realtime instructions may include only short phase/state anchors. Hidden information, scorer-only content, answer keys, and rubric internals must not enter customer-visible instructions or tool payloads.
- Knowledge tools may expose customer-visible background and limited product facts. Missing, not-ready, timeout, or no-hit retrieval must return a grounded customer challenge plus quality flags; it must not invent product capabilities.
- Offline scoring uses the v1 six-item 100-point rubric, learner-turn evidence only, confidence, manual-review flags, and separate learner/admin/supervisor/ops projections.
- Unknown report roles fail closed. Learners never receive raw scoring JSON, transcript, hidden fields, state card internals, or admin-only quality diagnostics.

### 4. Validation & Error Matrix

| Condition | Expected behavior |
|---|---|
| `it_leader_roleplay_v1.enabled` missing or false | Keep legacy direct-practice policy; no v1 phase/state anchors |
| V1 enabled | Snapshot includes contract, hash, default state card, and short instruction anchors |
| State-card update has stale sequence/version | Ignore update and preserve previous state |
| State-card update is invalid | Reject/ignore update and preserve previous state |
| Reconnect has persisted runtime state | Restore persisted contract hash and state-card version |
| Scorer-only KB binding appears in v1 policy | Omit/reject it from realtime customer context |
| KB missing/not-ready/timeout/no-hit | Return natural challenge, `quality_flags`, and `knowledge_timeout_count`/equivalent |
| Output violates roleplay contract with blocking action | Increment blocking count and mark report/manual review; do not blind-retry |
| Scoring evidence comes from AI customer turn | Reject report |
| Score total mismatches dimension scores | Reject report |
| Unknown report role | Fail closed / deny projection |

### 5. Good/Base/Bad Cases

- Good: v1-enabled Persona opens a direct-practice session; snapshot freezes roleplay contract/hash/state card; instructions show only phase and state summary; missing product facts produce a customer request for PoC evidence.
- Base: v1 disabled session continues through existing direct-practice policy with no v1-specific fields.
- Bad: realtime prompt includes hidden budget, scorer answer key, or full rubric; reconnect rebuilds from latest assets; unit tests call live StepFun/LLM/TTS.

### 6. Tests Required

- Unit: v1 asset contract validates visible/hidden knowledge boundaries, forbidden behaviors, four roleplay phases, 100-point rubric, and 9 regression samples.
- Unit: state card accepts valid updates, rejects stale/invalid updates, and serializes `state_card_version`.
- Unit: voice policy/instruction compiler proves disabled/enabled behavior and no hidden/scorer-only leakage.
- Unit: knowledge search/tool policy proves scorer-only KB omission and grounded degradation on missing/not-ready/timeout/no-hit.
- Unit: report projection proves learner/admin/supervisor/ops separation and unknown-role fail-closed behavior.
- Unit: runtime restore proves persisted contract/state restoration, quality flag aggregation, and blocking violation observability.
- Unit: regression harness validates all nine samples and emits JSON evidence without live external calls.

### 7. Wrong vs Correct

#### Wrong

```python
instructions += latest_persona.prompt + latest_case.hidden_information
```

This leaks mutable latest assets and hidden information into the hot realtime path.

#### Correct

```python
snapshot = effective_policy["voice_policy_snapshot"]
instructions = compiler.compile(
    roleplay_contract=snapshot["roleplay_contract"],
    session_state_card=snapshot["session_state_card"],
)
```

The realtime path consumes the frozen contract/state and renders only short anchors.

#### Wrong

```python
if not kb_result:
    return "石犀平台一定支持该能力。"
```

This fabricates product capability when retrieval is missing.

#### Correct

```python
return {
    "answer": "这个能力需要你们给出可验证材料或 PoC 指标。",
    "quality_flags": ["knowledge_unavailable"],
    "knowledge_timeout_count": 1,
}
```

The customer stays natural while the runtime records quality risk for later review.
