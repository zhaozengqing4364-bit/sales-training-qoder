# Spec Audit Notes

## Scope

Audit current `.trellis/spec/` against project docs and representative source. GitNexus/ABCoder MCP tools were not available in this Codex session, so evidence comes from direct source reads.

## Evidence Read

Project docs:

- `CLAUDE.md`
- `backend/AGENTS.md`
- `web/AGENTS.md`

Spec tree:

- `.trellis/spec/backend/*.md`
- `.trellis/spec/frontend/*.md`
- `.trellis/spec/guides/*.md`

Representative backend source:

- `backend/src/router_registry.py`
- `backend/src/websocket_routes.py`
- `backend/src/sales_trainer/router_registration.py`
- `backend/tests/contract/*`
- `backend/tests/integration/*`

Representative frontend source:

- `web/src/lib/api/client.ts`
- `web/src/lib/api/client-domains.ts`
- `web/src/lib/api/domains/shared.ts`
- `web/src/lib/api/domains/newcomer-training.ts`
- `web/src/lib/api/client-domains.test.ts`
- `web/src/lib/api/types.ts`

## Findings

### Existing specs are mostly project-specific

The spec tree is not an empty bootstrap. Backend and frontend indexes already point to concrete local files and include several executable contracts, including business-rule policy governance, prompt-template governance, frontend score projection, and admin-console route patterns.

### Backend structure guidance still matches current code

`backend/src/router_registry.py` remains the central HTTP router mount point and `backend/src/websocket_routes.py` remains the root WebSocket registry. Domain-level registration exists for `sales_trainer` through `backend/src/sales_trainer/router_registration.py`, which is already compatible with `.trellis/spec/backend/directory-structure.md`.

No broad backend spec rewrite is justified from this pass.

### Frontend API client guidance is stale at one seam

Specs currently describe domain methods as living in `web/src/lib/api/client-domains.ts`. That file still exists and remains the outward aggregation seam, but newer domains have been split into `web/src/lib/api/domains/*`:

- `domains/shared.ts` defines `ApiRequest`, `ApiStream`, `ApiUpload`, and shared normalizers.
- `domains/practice.ts`
- `domains/support-runtime.ts`
- `domains/sales-trainer.ts`
- `domains/newcomer-training.ts`

`web/src/lib/api/client.ts` wires these domain factories behind the public `api` facade. `web/src/lib/api/client-domains.test.ts` contains a boundary test named `keeps UI layers importing the public api facade instead of domain internals`, proving that UI code must not import `client-domains` or `domains/*` directly.

Recommended spec refresh:

- Update frontend directory/type-safety/quality guidance to describe `client-domains.ts` as an aggregation seam, not the only place for new domain methods.
- Add a rule: new or high-growth domains should live under `lib/api/domains/<domain>.ts`, expose factory functions, and be wired through `client-domains.ts` + `client.ts`.
- Preserve the public import rule: pages/hooks/components import only `api` from `lib/api/client.ts`.
- Mention the boundary test in `client-domains.test.ts`.

## Proposed Implementation Scope

Update only frontend specs:

- `.trellis/spec/frontend/directory-structure.md`
- `.trellis/spec/frontend/type-safety.md`
- `.trellis/spec/frontend/quality-guidelines.md`

Potentially update `.trellis/spec/frontend/index.md` only if the final topic list changes. No new spec file appears necessary.
