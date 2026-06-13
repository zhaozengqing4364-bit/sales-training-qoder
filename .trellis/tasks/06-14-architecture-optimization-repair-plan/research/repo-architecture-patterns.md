# Repo Architecture Pattern Research

## Question

How should we repair the Brooks audit findings using patterns already present in this repository, without inventing a new framework?

## Findings

### Existing good patterns to reuse

* `support/services/runtime_contributors.py` defines contributor callables and registries in the consuming surface, while `sales_bot`, `presentation_coach`, and `curriculum_practice` register their own contributors from the composition root.
* `common/question_bank/ports.py` defines `QuestionBankProvider` and `ResolvedQuestion` DTOs. `curriculum_practice` registers the provider, and `sales_trainer` consumes the port through `QuestionBankAdapter`.
* `training_runtime/plugins.py` uses Protocol-based scenario plugins and a registry to keep runtime dispatch inspectable.
* Frontend `client-domains.ts` already extracts some domain builders with injectable dependencies and has `client-domains.test.ts` coverage.

### Constraints from project specs

* `backend/src/common/AGENTS.md` says `common` is a shared platform kernel and must not introduce single-domain business logic.
* `backend/src/sales_trainer/AGENTS.md` says Sales Trainer is not a realtime runtime and must not import `sales_bot`, `training_runtime`, or practice session runtime logic.
* `backend/src/curriculum_practice/AGENTS.md` says cross-domain reuse must be explicit and reviewed.
* `web/src/lib/AGENTS.md` currently requires pages to import `api` from `client.ts`, not `client-domains.ts`, so API splitting must maintain a compatibility facade while reducing internal file size.
* `.trellis/spec/frontend/type-safety.md` requires API types to remain centralized in `lib/api/types.ts`, with normalizers and tests instead of page-local DTOs.

### Recommended direction

Use incremental port extraction:

1. Add dependency-contract tests before moving code.
2. Turn `common` reverse dependencies into ports/contributors owned by `common` or `support`, registered from `router_registry.py` / WebSocket composition roots.
3. Move domain-specific runtime assembly back into domain packages.
4. Keep public API/WS paths stable.
5. Split frontend API builders by domain behind the existing `api` export, then migrate only safe internal imports after compatibility is proven.

### Alternatives considered

* Big-bang package split: faster to describe, risky to execute; too many runtime paths and dirty worktree context.
* Keep current import shape and document exceptions: low effort but does not prevent regression and leaves Brooks Critical unresolved.
* Introduce a generic plugin framework: unnecessary because repo already has Protocol/registry patterns.

