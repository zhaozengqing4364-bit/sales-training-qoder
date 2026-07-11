# Gate 2 research: Golden Conversation Contract and migration options

## Golden Contract inventory

The approved design requires every realtime slice to preserve the following categories.
Gate 2 will represent them in a versioned machine-readable inventory, with contract IDs and
test evidence rather than relying on an informal checklist.

| Category | Contract truth to freeze |
|---|---|
| Admission | invalid session, RuntimeGate rejection, invalid token and owner mismatch fail before runtime writes |
| Connection | connected/status ordering, health/degraded/error behavior, clean disconnect |
| Lifecycle | start/pause/resume/end stay aligned with persisted REST transitions |
| Input | text, page change, binary audio chunk/interrupt and backpressure shapes remain compatible |
| Turn | request/response/stream IDs, response.done completion, interruption and timeout are monotonic |
| Grounding | frozen snapshot is consumed, KB lock remains fail-closed, degradation is explicit |
| Reconnect | snapshot restores monotonically increasing connection epoch without duplicate side effects |
| Evidence | transcript/audio audit/score/report are idempotent; insufficient evidence never fabricates a score |
| Roleplay | observation is record-only and cannot block the main conversation |
| Rollout | exactly one runtime path writes for a session; rollback selects the old adapter without rewriting snapshots |

The differential fixture will normalize nondeterministic timestamps and generated IDs while
comparing ordered event types, stable payload fields, terminal state, evidence keys and write
counts. It will not compare internal class names or log strings.

## Option A — composition façade + explicit Engine + compatibility runtime adapter

Recommended for Gate 2.

- Add neutral state/engine modules under `training_runtime/realtime/`.
- Split the shared StepFun constructor so Sales remains the default, while Presentation mode
  does not instantiate Sales capabilities.
- Keep the existing Presentation-specific StepFun behavior in a named compatibility adapter.
- Make the production `PresentationRealtimeEngineHandler` a composition façade, not a
  subclass of the Sales shared handler.
- Persist the Engine snapshot as an additive `realtime_engine` key inside the existing Redis
  snapshot and expose diagnostics.
- Select the new façade by a server-side scenario flag, default enabled after the
  differential suite is green; `false` is the immediate rollback.

Benefits: preserves protocol and hot-path implementation, removes the public inheritance and
Sales capability construction, gives Gate 3 a stable state/Scenario Hook host. Risk is that
the compatibility adapter still reuses StepFun Mixins located in `sales_bot`; this is an
explicit, bounded transition and not presented as final provider neutrality.

## Option B — wrapper-only façade around the unchanged handler

Rejected. It would make the class graph look compositional while the wrapped handler still
constructs enabled Sales capabilities and remains the only state authority. This is a shallow
module and does not satisfy the acceptance criterion.

## Option C — rewrite Presentation StepFun and Provider now

Rejected for Gate 2. Reimplementing connection, upstream codec, grounding, tool execution,
timeouts, reconnect and persistence in one slice duplicates Gate 3 and creates a second-system
failure surface. The current all-green release gate is most valuable when migration remains
incremental.

## Chosen rollout

`PRESENTATION_REALTIME_ENGINE_ENABLED=true` selects the engine façade for persisted
`stepfun_realtime` sessions. `false` selects the named compatibility handler. The flag is
server-side and scenario-scoped; the client cannot override it. Both choices retain the same
route admission, close codes and persisted voice mode. No shadow DB write or dual scoring is
allowed.

Defaulting the flag to `true` is intentional at Gate completion: a default-old flag would
leave the architecture migration unexercised and fail the “production entry no longer
inherits Sales state” outcome. Rollback remains a single environment change.

## State ownership boundary for Gate 2

- Engine is authoritative for the new typed Connection/Turn/Grounding/Evidence snapshot and
  transition invariants.
- The compatibility adapter remains authoritative for StepFun wire protocol and existing
  persistence until Gate 3.
- Engine EvidenceState is record/dedupe metadata only; it does not write score/report rows.
- Existing snapshot fields remain authoritative for backwards reconnect compatibility.
- On restore, missing Engine state means “pre-Gate-2 snapshot” and is reconstructed from the
  existing snapshot without rejecting the session.

This dual representation is temporary but not dual business writing: one representation is
the backward-compatible adapter snapshot, the other is the new orchestration state. Gate 3
retires the duplicated provider/grounding fields as each authority moves.

