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
- Task 2 Red replaced string assertions with four closed factory choices; 8 tests failed for missing enum values,
  mandatory string fields and the old root lookup. Green removes the unused descriptor surface and dynamic imports:
  plugin/Main routing `34 passed`; touched Ruff and mypy pass. The Gate 6 contract advanced from 1/7 to 3/7
  passing; the four remaining failures belong exactly to Tasks 3–4.
- Task 3 added two Red contracts for root composition and mandatory Engine adapter injection. The concrete
  `PresentationStepFunRealtimeAdapter` now has an explicit cooperative MRO:
  Presentation behavior → neutral `StepFunRuntimeAdapterPort` → retained Sales transport. This makes the former
  hidden inheritance requirements inspectable without a Presentation-to-Sales import. Presentation/Engine/Main/
  practice-evidence affected matrix passes 112 of 113 cases; the only excluded Red is Task 4's Common Roleplay
  façade deletion. Ruff and full mypy (`678 source files`) pass. Architecture policy passes with 51 edges,
  `presentation_coach -> sales_bot` absent, and the seven-package SCC unchanged.
- Deviation: the initial plan described one exhaustive root map. Review showed that making the Sales domain router
  import a global composition root would invert delivery ownership. The final design keeps one Sales-local root
  map and one top-level Presentation composition map; their disjoint union is exhaustively tested against the
  closed enum. No factory implementation or string locator is duplicated.
- Task 4 migrated the sole production forwarding consumer and compatibility tests to `roleplay.contracts`, deleted
  `common.roleplay_contracts`, and kept the remaining `common -> roleplay` policy edge because
  `common.business_rules.defaults` is still an active source. Roleplay/Gate 4/Gate 6 matrix is `33 passed`; Ruff,
  full mypy (`677 source files`) and architecture policy pass. Gate 6 contracts are now 9/9 Green.
