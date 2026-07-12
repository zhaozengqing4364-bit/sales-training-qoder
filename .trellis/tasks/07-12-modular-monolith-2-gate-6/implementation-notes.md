# Gate 6 implementation notes

## Baseline

- 15 governed packages, 52 dependency edges, one seven-package SCC.
- `presentation_coach -> sales_bot`: one import location.
- `common -> roleplay`: two import locations.
- Backend model compatibility importers: 222; frontend global type barrel importers: 262.

## Deviations

- None.

## TDD log

- Task 1 Red: `test_gate6_compatibility_retirement.py` collected 7 tests; 6 failed for the intended pre-Gate-6
  facts and the model/frontend retention floor passed. Failures were the two executable handler string fields,
  `ScenarioPluginEntrypoint`, missing root composition map, Presentation's Sales import, the Common Roleplay
  forwarding file and the 52-edge graph.
- CodeGraph impact: `ScenarioRuntimeHandlerSelection` affects 10 symbols; `dispatch_scenario_plugin` 13;
  `LegacyPresentationStepFunRealtimeHandler` 129 (dominated by the two Presentation suites plus shared StepFun
  regressions); `common.roleplay_contracts` 6. These sets define the affected verification matrix.
