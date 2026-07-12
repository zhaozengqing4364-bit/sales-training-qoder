# Gate 6 compatibility retirement inventory

Date: 2026-07-12 UTC

## Current graph and migration baseline

- The governed backend graph has 15 packages, 52 directed edges and one seven-package SCC:
  `agent/common/curriculum_practice/evaluation/prompt_templates/sales_trainer/support`.
- `presentation_coach -> sales_bot` has one source location:
  `presentation_coach/websocket/presentation_stepfun_realtime_handler.py:39`.
- `common -> roleplay` has two source locations: the forwarding
  `common/roleplay_contracts.py` module and the active business-rule default registry.
- Gate 5 left 222 backend source importers of `common.db.models` and 262 frontend source importers of the global
  API type barrel. The model façade also has an explicit one-release deprecation-window condition that has not
  elapsed.
- Gate 5 co-change baselines remain the comparison authority: report + global types changed together 22 times;
  global types + client changed together 55 times. Local Journey/Dossier/report authorities now own their rules.

## Consumer-backed classification

| Compatibility surface | Production consumer truth | Gate 6 decision |
|---|---|---|
| `ScenarioPluginEntrypoint.service_path/method_name` plus lifecycle/evidence/report descriptor methods | No production caller; only tests assert these descriptive strings | Delete the shallow operational surface |
| `ScenarioRuntimeHandlerSelection.handler_factory_path/name` | Two production roots dynamically import the strings | Replace with closed `RuntimeHandlerFactoryKey` and explicit root factories |
| `presentation_coach` inheritance from `sales_bot.StepFunRealtimeSharedHandler` | Active default and rollback runtime | Remove the package import by making Presentation behavior a mixin and composing the concrete adapter only at the application root |
| `common.roleplay_contracts` | One production importer in Curriculum plus compatibility-only tests | Migrate the consumer to `roleplay`, update tests, delete the forwarding module |
| `common.business_rules.defaults -> roleplay.defaults` | Active 49-file business-rule registry | Retain the temporary edge; moving the whole registry is a separate owner migration, not a compatibility deletion |
| `LegacyRealtimeGroundingAdapter` / `LegacyToolResultCache` | Constructed whenever `REALTIME_GROUNDING_MODULE_ENABLED=false` | Retain until rollout telemetry and a release deprecation window prove the rollback path unused |
| Presentation Engine false path | Active explicit rollback contract | Retain; removing it without deployment evidence would remove the only scenario rollback |
| `common.db.models` | 222 production source importers; Alembic/import-order authority | Retain the identity-preserving registry |
| Global frontend type/client façades | 262 source importers and no external/generated-client inventory | Retain; no replacement global barrel will be introduced |

## Chosen architecture

1. Runtime selection becomes data without executable strings: a frozen selection carries a closed enum key;
   application roots own enum-to-factory maps and reject unknown keys fail-closed.
2. Presentation owns only Presentation behavior. A root composition module combines that mixin with the legacy
   Sales StepFun transport base. This removes the static domain edge without pretending the rollback adapter has
   disappeared.
3. Retained compatibility is not reported as completed migration. Each retained surface gets a named reason,
   retirement condition, owner and verification evidence in the ADR/spec.
4. Benefits are measured against the same scanners used by the executable architecture policy: edge count, SCC,
   fan-in, CodeGraph affected tests, changed coverage and clean-start canonical verification.

## Safety constraints

- REST/WS wire payloads, route paths, status transitions, snapshots, persistence, evaluation/report single writer
  and user-visible behavior remain unchanged.
- Closed factory selection must preserve Sales StepFun, Presentation legacy voice, Presentation Engine default and
  Presentation Engine flag-false rollback.
- The application-root composition must not be hidden in a domain package or exempted from tests.
- No database schema, migration, external provider call, deployment or production data mutation is in scope.

## CodeGraph impact selection

- `ScenarioRuntimeHandlerSelection`: 10 affected symbols across plugin selection, both roots and their tests.
- `dispatch_scenario_plugin`: 13 affected symbols including both WebSocket entry paths.
- `LegacyPresentationStepFunRealtimeHandler`: 129 affected symbols; required coverage includes Presentation
  adapter/Engine, StepFun shared handler/upstream, payload snapshots and practice evidence.
- `common.roleplay_contracts`: 6 affected imports; one production Curriculum consumer and five compatibility-test
  imports/locations.
