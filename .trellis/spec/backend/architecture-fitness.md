# Architecture Fitness

> Executable contract for backend cross-package dependencies, migration exceptions, and
> strongly connected component containment.

> **Newcomer implementation status (2026-07-18):** `docs/architecture/newcomer-foundation-guard-policy.yaml` is enforced by the AST edge/SCC guard and the canonical quality gate. Failure probes cover scoped cross-business imports, shared-kernel reverse edges, dynamic Activity locators, direct Provider access and composition-root misuse.

## Newcomer Foundation Guard Extension Contract

The machine guard fails closed on cross-business-module ORM/Repository/table imports; `shared_kernel` reverse dependencies; literal dynamic/string ActivityRuntime locators; business-module Provider SDK/raw endpoint/`.llm.apredict` access; and delivery code that combines ORM mutation/commit with external Provider IO.

An allowed business `stable_edge` is contract-scoped, not a package-wide friendship: the importer may use only the target's `contracts/`, `ports/`, immutable `public/` DTOs, or `identifiers/`. Imports of a foreign `models`, repository, SQLAlchemy adapter/table, concrete adapter, `services`, or `internal` path fail even when the pair appears in `stable_edges`. The `application_root` is governed separately by `composition_root_edges`: it may import concrete adapters/providers only to wire and register lifecycles, but may not own business rules, mutate business ORM, or become a request-time service locator.

The policy file owns target edges, Legacy exceptions, owner, retirement condition, expiry, and failure-probe names. Until target packages exist, the current `module-dependency-policy.yaml` remains runtime truth; do not add non-existent packages to it merely to make the design appear implemented.

Required probes inject one violation for each of the first four rules, assert the stable failure code and source location, remove the probe, then prove both current and target guard suites return green. An expired or stale exception fails closed.

The target probe set also injects a foreign internal-service import across an otherwise allowed business edge and expects `ARCH_BUSINESS_EDGE_SCOPE_FORBIDDEN`. A composition-root fixture proves every declared root edge is accepted, while an undeclared root target and a business mutation inside the root both fail.

## 1. Scope / Trigger

Apply this contract when a backend change:

- adds, removes, or moves an absolute import between top-level packages;
- introduces a literal dynamic import;
- creates, renames, or removes a top-level backend package;
- removes a historical dependency during modular-monolith migration;
- changes `docs/architecture/module-dependency-policy.yaml`, the architecture guard, or
  the canonical quality gate.

The policy controls dependency direction while the modular monolith is migrated. It does
not claim that the current graph is acyclic.

## 2. Signatures

```python
Edge = tuple[str, str]

def collect_edges(
    src_root: Path,
    packages: set[str],
) -> dict[Edge, set[str]]: ...

def strongly_connected_components(
    packages: Iterable[str],
    edges: Iterable[Edge],
) -> list[frozenset[str]]: ...

def validate_repository(
    *,
    src_root: Path = DEFAULT_SRC_ROOT,
    policy_path: Path = DEFAULT_POLICY,
    today: date | None = None,
) -> list[str]: ...
```

Run from the repository root or `backend/`:

```bash
backend/.venv/bin/python backend/scripts/architecture_dependency_guard.py --check
.venv/bin/python scripts/architecture_dependency_guard.py --check
```

Policy shape:

```yaml
version: 1
packages: [common, sales_bot]
stable_edges:
  - [sales_bot, common]
temporary_edges:
  - source: common
    targets: [sales_bot]
    owner: platform-architecture
    reason: transitional composition dependency
    retire_when: composition moves to the application root
    expires_on: 2026-10-31
baseline_sccs:
  - [common, sales_bot]
```

## 3. Contracts

### Import inventory

- An edge points from the importing package to the imported package.
- Scan every Python file under declared packages, including imports inside functions and
  `TYPE_CHECKING` blocks.
- Count absolute `import`/`from` and literal `import_module`/`__import__`; ignore relative
  imports and non-literal plugin paths.
- Locations are stable `path:line` values. Edge and violation output is sorted.
- Non-literal plugin paths remain protected by runtime plugin contract tests; do not guess
  them in the AST guard.

### Policy ownership

- `stable_edges` are approved target directions. They may be absent while modules shrink.
- `temporary_edges` describe observed historical debt. Every group requires non-empty
  `owner`, `reason`, `retire_when`, and ISO `expires_on`.
- A temporary edge disappearing is a successful migration, but the same change must remove
  its stale policy entry.
- Stable and temporary sets may not overlap. All referenced packages must be declared and
  have source directories.

### SCC migration

- A current multi-package SCC is allowed only when it is a subset of one declared baseline.
- Baseline SCCs may split or shrink without rewriting a test to a new exact count.
- A component that absorbs a package outside its baseline fails.
- Never hard-code the current total edge count or exact historical SCC membership as a
  permanent test assertion. Record those numbers as dated audit evidence instead.

### Time semantics

- Repository validation uses the current UTC date and fails after an exception expires.
- Synthetic policy tests inject a fixed `today`; only the current-repository test is allowed
  to exercise real-date expiry.

## 4. Validation & Error Matrix

| Condition | Required result |
|---|---|
| Actual edge is in neither stable nor temporary policy | Fail with source, target, and sorted `path:line` locations |
| Temporary edge no longer exists | Fail as stale; remove the policy entry in the same change |
| Temporary group is incomplete, empty, invalid, or expired | Fail closed with the field/group identified |
| Stable and temporary policy contain the same edge | Fail as overlapping ownership |
| Policy references an undeclared package | Fail |
| Declared package directory is missing | Fail |
| Stable/temporary edge is duplicated | Fail |
| Current SCC is a subset of a baseline | Pass |
| Current SCC contains a package outside every baseline | Fail as expanded SCC |
| New undeclared edge stays inside an existing SCC | Fail as unexpected edge even though SCC size is unchanged |
| YAML is missing or invalid | Fail with a deterministic policy error |
| Non-literal plugin path is encountered | Ignore statically; runtime contract remains responsible |
| Stable business edge imports target `contracts/ports/public/identifiers` | Pass |
| Stable business edge imports target ORM/repository/adapter/service/internal path | Fail with `ARCH_CROSS_MODULE_ORM_FORBIDDEN` or `ARCH_BUSINESS_EDGE_SCOPE_FORBIDDEN` |
| `application_root` imports a declared concrete adapter only for wiring | Pass under `composition_root_edges` |
| `application_root` imports an undeclared target or owns business ORM mutation | Fail closed; a stable business edge cannot be used as a root exemption |

## 5. Good / Base / Bad Cases

- **Good**: a migration removes `evaluation -> sales_bot` and removes the matching temporary
  exception in the same commit; the historical SCC shrinks and the guard passes.
- **Base**: no dependency change; the current graph is fully explained, no exception is stale
  or expired, and both CLI entry points return zero.
- **Bad**: a feature imports `supervisor` from `sales_bot` and then adds a permanent allowlist
  entry without owner, retirement condition, expiry, ADR rationale, or failure probe.

## 6. Tests Required

- Unit: collect top-level, function-local, `TYPE_CHECKING`, and literal dynamic imports;
  prove relative and non-literal imports do not create cross-package edges.
- Unit: Tarjan output is deterministic for multiple SCCs and isolated packages.
- Unit: invalid YAML, missing fields, duplicate/overlapping edges, undeclared packages,
  missing directories, invalid/expired dates, and stale exceptions fail.
- Unit: a baseline component may shrink; a component may not expand.
- Unit: an undeclared edge within an already-existing SCC still fails.
- Repository: `validate_repository()` returns no violations using the real UTC date.
- Failure probe: a temporary `sales_bot -> supervisor` import reports both unexpected edge
  and expanded SCC; delete the probe and prove the CLI returns to green.
- Target failure probes: foreign business ORM import, foreign internal-service import across an
  allowed edge, shared-kernel reverse import, literal dynamic Activity import, and direct business
  Provider import each report its stable code and location.
- Composition root: every declared `composition_root_edge` passes; undeclared targets, request-time
  service-location and business ORM mutation in the root fail.
- Regression: run architecture guard tests together with runtime, newcomer path, and knowledge
  import boundary tests; run Ruff, Bash syntax, and `git diff --check`.

## 7. Wrong vs Correct

### Wrong: freeze historical debt in a test

```python
assert len(edges) == 49
assert components == [HISTORICAL_TWELVE_PACKAGE_SCC, {"supervisor"}]
```

This fails when the architecture improves and contradicts the policy's shrink-only migration
semantics.

### Correct: validate the governed relationship

```python
def test_current_repository_dependency_policy_is_valid() -> None:
    assert validate_repository() == []


def test_should_allow_a_baseline_component_to_shrink(tmp_path: Path) -> None:
    # The current SCC may be any subset of the declared historical baseline.
    assert validate_repository(
        src_root=tmp_path / "src",
        policy_path=tmp_path / "policy.yaml",
        today=date(2026, 7, 10),
    ) == []
```

Current counts belong in dated audit evidence. Executable tests protect direction,
exception lifecycle, and monotonic SCC reduction.
