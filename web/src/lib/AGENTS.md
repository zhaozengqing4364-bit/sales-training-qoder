# Lib — `web/src/lib/`

Shared non-UI logic: API façade, auth, query, routing helpers, observability.

## Map

| Path | Responsibility |
|------|----------------|
| `api/client.ts` | Single `api` export — all HTTP from UI |
| `api/client-domains.ts` | Domain builders; edit when splitting transport surfaces |
| `api/types.ts` | Shared API types |
| `query/` | React Query client + auth query keys |
| `auth/` + `auth-handler.ts` + `server-auth.ts` | Client/server session |
| `admin/` | Admin read models & asset drill-in helpers |
| `support/` | Support runtime fault copy |
| `observability/` | Trace headers for server `fetch` |
| `debug.ts` | Allowed console seam + inventory |

## Hard Rules

- Pages import `api` from `client.ts` only — not `client-domains.ts`
- No raw `console.*` outside `debug.ts` / instrumentation
- Auth redirects via `auth-handler` + `server-auth`, not `window.location` except inventoried exceptions
- Run `console-boundary.test.ts` after logging changes

## Where to Look

- Add endpoints: extend `client-domains.ts`, wire in `client.ts` `export const api`
- Server gate: `server-auth.ts`
- Support copy: `support/runtime-fault-actions.ts`
