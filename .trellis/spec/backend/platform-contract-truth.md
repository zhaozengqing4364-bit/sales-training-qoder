# Platform Contract Truth

> Executable contract for test contributor isolation, FastAPI route inventory, and
> committed OpenAPI parity.

> **Implementation-status note (2026-07-18):** Newcomer v2 learner, domain-admin, unified workspace and ReleasePlan surfaces are mounted; experience/performance, Legacy deletion and final release gates have passed. `create_app().openapi()` remains the runtime truth and is checked against the committed contract in the canonical gate.

## Newcomer Foundation Contract Truth

- The runtime schema from `create_app().openapi()` remains the only evidence that a v2 route is implemented; the Markdown contract records status and intent but cannot substitute for runtime proof.
- v2 owns `/api/v1/newcomer-training/**` and `/api/v1/admin/newcomer-training/**`; once a v2 writer passes its end-to-end gate, the corresponding Legacy writer is removed from route composition and OpenAPI in the same slice.
- Do not keep a permanent forwarding router, copied route inventory, dual writer, or hand-edited OpenAPI path.
- OpenAPI deletion tests use the retirement matrix in `docs/architecture/newcomer-foundation-clean-cut.md` and distinguish planned, current Legacy, and removed states.
- Domain contributor bootstrap must register the five target ActivityRuntime adapters explicitly at the composition root; string module/class locators and realtime newcomer registration fail the target contract.
- Formal Path/resource publication is exposed only through `/api/v1/admin/newcomer-training/release-plans/**`. Former direct Path/resource publish tombstones are removed from runtime composition and OpenAPI and must not be restored.

### Durable task composition contract

- `task_runtime` owns one lifecycle only: `queued -> running/retry_wait/cancel_requested -> cancelled/succeeded/dead_letter`. Lease and attempt are execution metadata; `partial_success` and `waiting_input` are typed result kinds, never task states.
- Registry identity is `(task_type, schema_version)`. Enqueue freezes the complete execution policy; recovery must resolve that exact version and use the stored timeout, lease, attempts, retry policy and deadline rather than current registry defaults.
- Task payloads, Outbox payloads and TaskResultRef item groups contain only bounded object/artifact references. Full audio, transcript, Prompt, Provider raw response, credentials or arbitrary result JSON are rejected at the platform seam.
- Worker and Outbox Dispatcher are independent processes with liveness/readiness, bounded leases, graceful drain and fail-closed composition. An empty registry, missing handler or missing production EventTransport is a startup error; a development fake requires explicit environment and feature switches.
- Admin task projection requires both persisted capability and active organization/object scope. Action flags are server projections of the same authorization used by cancel/redrive commands; a role name alone never grants cross-organization access.

## 1. Scope / Trigger

Apply this spec when a change does any of the following:

- adds or removes a FastAPI HTTP/WebSocket route;
- changes request/response schemas exposed through OpenAPI;
- registers a domain contributor, resolver, provider, or handler in a process-global
  registry;
- changes the backend release gate or the committed OpenAPI contract.

The goal is one runtime source of truth. Tests and generated artifacts may adapt that
truth, but must not maintain a second route or contributor inventory.

## 2. Signatures

Production contributor bootstrap:

```python
def register_domain_contributors(
    registrations: Iterable[DomainContributorRegistration] | None = None,
) -> None: ...
```

OpenAPI contract commands, run from `backend/`:

```bash
.venv/bin/python scripts/generate_openapi_contract.py
.venv/bin/python scripts/generate_openapi_contract.py --check
.venv/bin/python scripts/generate_openapi_contract.py --output /tmp/openapi.yaml
```

Default output:

```text
specs/001-ai-practice-system/contracts/openapi.yaml
```

## 3. Contracts

### Contributor registries

- `register_domain_contributors()` is the production composition-root inventory.
- `backend/tests/conftest.py` restores that production inventory before and after
  every test. A test may clear or replace a registry during its Arrange phase; the
  teardown must leave the next test with production defaults.
- A test-only contributor that is intentionally absent from the production bootstrap
  may be registered explicitly after `register_domain_contributors()`. This exception
  must be named next to the fixture; it must not become a copied production inventory.
- Registrars used by the bootstrap must tolerate repeated registration in one process.

### Route inventory

- Runtime schema is `create_app().openapi()`.
- Route-integrity tests must inspect both direct routes and included-router effective
  contexts. When an effective WebSocket context has no path, the canonical path comes
  from `original_route.path`.
- The FastAPI compatibility adapter belongs in tests. Do not add framework-shape
  inspection to production routing code only to satisfy a test.

### OpenAPI artifact and gate

- Generation writes a deterministic YAML representation of the runtime schema.
- `--check` is read-only and compares parsed YAML with the runtime schema semantically;
  formatting-only changes do not cause drift.
- Current contract returns exit code `0`; missing, invalid, or semantically stale
  contract returns non-zero. A normal generation command may create parent directories.
- The existing `scripts/critical-quality-gate.sh` is the only release gate. OpenAPI
  parity runs after backend Ruff and before frontend checks.

## 4. Validation & Error Matrix

| Condition | Required result |
|---|---|
| Test clears a process-global contributor registry | The next test sees production registrations |
| Registrar is called repeatedly | Same effective registration; no duplicate behavior or exception |
| FastAPI stores routes under an included-router wrapper | Integrity checks still see every HTTP method/path |
| Effective WebSocket context has an empty path | Read `original_route.path` and retain both supported WS paths |
| Committed YAML is semantically equal but formatted differently | `--check` exits `0` |
| Contract is missing, invalid, or semantically stale | `--check` exits non-zero and never rewrites the file |
| Runtime adds or removes an OpenAPI path/schema | Generation updates the committed artifact; CI fails until synchronized |
| Generator runs twice without source changes | Byte-identical output |

## 5. Good / Base / Bad Cases

- **Good**: a new API route is added, the runtime contract is regenerated, route
  integrity sees the included route, `--check` passes, and the critical gate protects it.
- **Base**: no API or registration change; repeated generation is byte-identical and
  repeated contributor bootstrap calls preserve the same effective defaults.
- **Bad**: a test copies individual registrar calls into its own list, clears the
  registry without teardown restoration, reads only `app.router.routes`, or edits the
  OpenAPI YAML manually without comparing it to runtime.

## 6. Tests Required

- Unit: render a representative schema and assert parsed YAML equality plus terminal
  newline.
- Unit: write a current contract and a drifted contract; assert semantic check returns
  true then false. Include missing/invalid input behavior when that behavior changes.
- Unit: route inventory asserts no duplicate method/path pairs, canonical routes,
  WebSocket legacy/path modes, and static-before-dynamic ordering.
- Contract/order regression: run a registry-clearing test before a consumer test and
  assert the consumer still resolves the production contributor.
- Determinism: generate twice in isolated files and compare bytes; compare the generated
  file with the committed artifact.
- Gate: run `generate_openapi_contract.py --check`, changed-file Ruff, focused pytest,
  `bash -n scripts/critical-quality-gate.sh`, and `git diff --check`.

## 7. Wrong vs Correct

### Wrong: copied contributor inventory and flattened route assumption

```python
register_sales_bot_practice_session_contributor()
register_support_knowledge_contributor()

paths = {route.path for route in app.router.routes}
```

This silently drifts when production adds a contributor or FastAPI wraps included
routers.

### Correct: production bootstrap and test-local effective route adapter

```python
@pytest.fixture(autouse=True)
def restore_default_domain_contributors():
    register_domain_contributors()
    yield
    register_domain_contributors()


def effective_routes(app):
    for route in app.router.routes:
        contexts = getattr(route, "effective_route_contexts", None)
        if callable(contexts):
            yield from contexts()
        else:
            yield route
```

The bootstrap remains authoritative, while the test adapter absorbs framework route
representation changes without changing production behavior.
