# Gate 4 current ownership and seam inventory

Date: 2026-07-11 UTC

## Authority

- `docs/superpowers/specs/2026-07-10-modular-monolith-2-design.md` sections 6.3–6.5
- `docs/superpowers/plans/2026-07-10-modular-monolith-2-roadmap.md` Gate 4
- `docs/adr/2026-07-10-modular-monolith-2-ai-native-governance.md` decision 4
- `docs/architecture/module-dependency-policy.yaml`

The user has already approved the target design and explicitly requested uninterrupted execution.
No product preference remains open; conservative compatibility, fail-closed behavior and local-only
verification are the binding defaults.

## CodeGraph-first findings

Current AST baseline is 49 cross-package edges. One 12-package SCC contains `admin`, `agent`,
`common`, `curriculum_analytics`, `curriculum_practice`, `evaluation`, `presentation_coach`,
`prompt_templates`, `sales_bot`, `sales_trainer`, `support` and `training_runtime`. New neutral packages
must not be added to this baseline SCC; the guard only permits shrinkage.

### Roleplay ownership

- `backend/src/common/roleplay_contracts.py` owns schema constants, stable contract hash and runtime
  compliance decisions. It has 11 direct consumer files.
- `backend/src/curriculum_practice/services/roleplay_contracts.py` is 1,843 lines and mixes at least
  five responsibilities: compiler, disclosure state/turn context, report projections, Situation Pack
  administration and curriculum-specific adapters.
- The compiler directly imports `agent`, curriculum models/schemas, Situation Pack repository/DTO,
  asset hash/resolution and common business-rule services. Evaluation therefore imports curriculum
  merely to compile deterministic Roleplay fixtures.
- Situation Pack DTO/hash/repository live under curriculum although Sales runtime, Evaluation and
  configuration governance consume their contract semantics.
- Existing hash functions remove volatile audit fields and use sorted compact UTF-8 JSON with a
  `sha256:` prefix. This byte-level behavior is historical evidence and must not change.

### Configuration governance ownership

- `backend/src/admin/config_bundles/lifecycle.py` owns draft, validate, preview, publish, rollback,
  disable, version binding and audit logic.
- `backend/src/admin/config_bundles/adapters.py` owns bundle/version DTOs and the adapter Protocol, but
  also imports admin inventory adapters at runtime and contains a Situation Pack projection hook.
- `evaluation/services/evaluation_run_service.py` and
  `curriculum_practice/services/practice_template_publish_gate_factory.py` import the admin lifecycle
  only to resolve active version identity. This is a delivery-layer reverse dependency.
- The lifecycle's database writes are already async and transaction ownership remains at API/caller
  boundaries. Gate 4 must preserve this boundary; no external I/O may be added inside the DB unit of
  work.

### Evaluation reverse dependencies

The AST inventory currently reports these four temporary outgoing edges:

- `evaluation -> admin`
  - `evaluation/api.py:13`
  - `evaluation/services/evaluation_run_service.py:12`
- `evaluation -> curriculum_practice`
  - `evaluation/services/roleplay_contract_eval.py:8`
- `evaluation -> presentation_coach`
  - `evaluation/services/comprehensive_report.py:43`
- `evaluation -> sales_bot`
  - `evaluation/services/comprehensive_report.py:350`

The presentation report service also imports Evaluation report DTOs inside `build_report`, creating a
scenario/evaluation two-way dependency. The Evaluation service chooses Presentation implementation
internally and reads Sales in-memory context as a legacy fallback. Both concrete choices belong in
application-root wiring or scenario adapters.

### Presentation compatibility edge

`presentation_coach/websocket/presentation_stepfun_realtime_handler.py` still imports Sales:

- StepFun event payload helpers;
- text extraction helpers;
- message persistence helpers;
- `TRANSCRIPTION_DUPLICATE_WINDOW_SECONDS` and `StepFunRealtimeSharedHandler`.

Gate 3 intentionally left this compatibility edge. Gate 4 moves reusable message/Roleplay/report
owners behind neutral seams; Gate 6 removes the remaining inheritance/Mixin compatibility path only
after differential and canonical evidence exist.

## Selected approach

Use two explicit neutral bounded contexts and ports owned by the consumer:

1. `roleplay` owns Roleplay/Situation Pack DTOs, hashing, compile decisions, disclosure transitions,
   turn context and compliance decisions. It has no dependency on curriculum, Sales, Presentation,
   Evaluation or Admin.
2. `configuration_governance` owns ConfigBundle lifecycle DTOs, adapter/repository ports and lifecycle
   orchestration. Admin supplies delivery and inventory adapters. Runtime consumers read immutable
   version bindings through their own narrow projection ports instead of importing Admin.
3. `evaluation` owns `SessionEvidencePort` and `ScenarioEvaluationPort`. SQL evidence and scenario
   implementations are adapters; application-root composition selects them. Evaluation never imports
   a concrete scenario package.
4. Compatibility imports remain named and rollback-capable during Gate 4. Gate 6 deletes them after
   consumer/impact proof; no historical hash or report is recomputed.

This choice follows dependency inversion without creating a generic service locator. Ports are small,
typed and capability-oriented. Composition is explicit, deterministic and frozen after bootstrap.

## Rejected approaches

- Move everything into `common`: rejected because it enlarges the shared kernel and hides domain
  ownership.
- Let Evaluation dynamically import scenario implementations: rejected because literal dynamic
  imports are guarded and non-literal plugin strings would hide compile-time contracts.
- Rewrite the 1,843-line Roleplay file in one change: rejected because the review and rollback radius
  is too large. The strangler moves stable responsibilities behind differential fixtures first.
- Split services: rejected because the approved ADR requires a modular monolith and no new
  infrastructure.

## Risk controls

- Golden fixtures pin contract/situation hashes, frozen snapshots, compliance decisions and report
  payloads before ownership moves.
- Every migration factory has exactly one default-on flag and a named legacy rollback path until
  Gate 6; constructor-time selection prevents split authority.
- Ports do not expose ORM rows across domains. Compatibility adapters may temporarily translate rows
  to immutable DTOs.
- Missing Evidence remains `non_evaluable`; missing scenario adapter/config binding fails closed or
  uses the already documented bundled default, never fabricates a score.
- No schema, table, REST, WebSocket, close-code or frontend response shape changes are planned.
