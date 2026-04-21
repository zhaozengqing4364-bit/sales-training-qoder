# ADR: Lane A deferred items after task-9 runtime safety slices

Date: 2026-04-21  
Status: accepted for task-9 closeout  
Worker: worker-1

## Context

Task 9 covered Backend Safety / Runtime Stability. The implemented slices have fresh targeted tests and commits for Q-03/Q-04/Q-05/Q-07/Q-08/Q-09/Q-10/Q-11/Q-12/Q-13/Q-25/Q-29.

Leader escalation on 2026-04-21T07:03Z requested closing the current scoped evidence and explicitly marking remaining large items deferred/blocked instead of expanding task scope further.

## Deferred items

| ID | Status | Reason | Next boundary |
| --- | --- | --- | --- |
| Q-23 | deferred-with-adr | Redis-backed/distributed rate limiting changes affect auth/session/API limiter semantics and need cross-process integration tests plus deployment-mode fail-open/fail-closed policy. | Create a dedicated Rate Limit backend task with Redis/memory concurrency tests and admin/env policy documentation. |
| Q-24 | deferred-with-adr | ASR provider fallback touches audio provider selection, browser handoff contracts, and user-visible failure modes. It needs scenario-level websocket tests and compatibility review. | Create a dedicated ASR fallback chain task: Alibaba -> local -> browser handoff, with provider failure matrix. |
| Q-30 | deferred-with-adr | Magic-number governance is cross-cutting and needs a rule/config inventory across scoring, UX, rate limits, cache, websocket, and growth features. | Create a config-governance sweep with per-domain owners; only convert values with tests and ownership. |

## Decision

Do not expand task 9 further. Close task 9 with implemented runtime safety slices and this ADR for remaining items.

## Consequences

- Task 9 remains evidence-backed and integrable.
- Remaining items are not hidden or marked done-ish.
- Follow-up work has explicit boundaries and required tests.
