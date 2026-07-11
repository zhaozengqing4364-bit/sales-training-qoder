# Gate 3 implementation notes

## Assumptions

- Continue in the existing dedicated `codex/newcomer-training-v0-9-closure` branch. The branch
  already contains the preceding Gate commits and the only unrelated dirty file is the user's
  `docs/superpowers/plans/2026-07-10-readiness-decision-integrity.md`; creating a second worktree
  would detach this active Trellis/Goal state rather than improve isolation.
- Real or paid StepFun Provider calls are outside the Goal authorization. Provider correctness is
  proved with the neutral fake, raw-wire local fixture, contract tests, differential tests and all
  credential-independent quality gates.
- Gate 3 neutralizes Provider and Grounding ownership only. The complete
  `presentation_coach -> sales_bot` edge also carries persistence, prompt, Roleplay and report
  helpers, so its policy exception remains until the Gate 4 migration and Gate 6 graph-based
  retirement.
- Existing Engine grounding diagnostics remain schema v1. The Grounding decision's exact cache
  disposition is projected to existing `cache_hit` and counter fields; no silent Engine schema
  extension is introduced in this Gate.

## Deviations

- Task 3 freezes Provider selection during shared-handler construction, but creates the selected
  Provider object lazily at the first upstream connect. This preserves the existing behavior that
  a handler can be constructed before `STEPFUN_API_KEY` admission reports a user-safe missing-key
  error; the factory is still invoked at most once and reconnect reuses the same Provider object.
- Task 3 also touches the shared diagnostics producer and Presentation façade allowlist so the
  required sanitized `provider_port_enabled` / `selected_provider_path` selection is observable.
  These two mechanical files were not listed in the brief's initial file inventory but are the
  existing single diagnostics path; no second diagnostics writer was added.
- After the user prohibited sub-agent dispatch, the main agent completed Task 3 Review 8 directly.
  The lifecycle fix unifies proactive refresh and disconnect recovery with the same generation
  rollover authority rather than retaining direct close/connect paths. This expands the Task 3
  production slice only within the already planned Provider rollout/reconnect invariant.

## Evidence

- Planning artifact audit: three rounds; final result `AUDIT CLEAN (0 hard errors)`.
- Pre-implementation task context validation: 15 implementation and 14 check entries valid.
- Pre-implementation architecture policy: `dependency policy satisfied`.
- Implementation base commit: `dd6202c1`.
- Task 3 Review 8 Red: four deterministic failures covering stale successful Legacy receive,
  proactive refresh generation drift, failed pause cleanup retry and close-only intent upgrade.
- Task 3 Review 8 Green: focused lifecycle matrix `12 passed`; brief suite `342 passed`; CodeGraph
  affected suite `825 passed`; Ruff, mypy (632 files), architecture guard and diff check passed.
- Task 4 Red: the neutral Grounding module import failed during collection as planned.
- Task 4 Green: 36 focused Grounding/common parity tests and 267 Provider/Engine/Grounding
  compatibility tests passed; Ruff, mypy (634 source files), architecture guard and diff check
  passed. No production handler uses the new module before Task 5.
- Task 5 Red: the default-selection test failed because the handler had no
  `_grounding_module_enabled` selection state.
- Task 5 Green: the default path now owns one `RealtimeGroundingModule` and one bounded cache;
  strict/prefetch/tool retrieval shares the same immutable request/result authority, while the
  exact former Pipeline plus result-cache behavior is isolated in the named Legacy adapter.
  Focused behavior matrix `267 passed`, affected realtime matrix `873 passed`, architecture guard
  `19 passed`, Ruff passed, and mypy passed across `635 source files`.
- Task 6 Red: compatibility diagnostics had no exact cache disposition, late results could overwrite
  a newer decision, timeout left no immutable result, and Presentation generated a separate Engine
  decision ID.
- Task 6 Green: one immutable result now projects closed Engine schema v1, bounded Legacy fields and
  redacted frontend diagnostics; generation-aware application rejects stale results and the
  low-level durable metric callback remains the only query-bearing writer. Focused matrix
  `529 passed`, broad affected realtime matrix `887 passed`, architecture guard `19 passed`, Ruff
  passed and mypy passed across `635 source files`.
- Task 7 differential expanded Sales selection to Provider/Grounding 2x2 and Presentation selection
  plus real Golden conversation to Engine/Provider/Grounding 2x2x2. The unchanged external Golden
  fixture preserves wire/snapshot/persistence/reconnect/single-writer behavior; focused Gate 3
  verification is `812 passed` with architecture policy, Ruff and mypy (635 source files) green.
- Task 7 documentation audit traced every public Provider/Grounding symbol and exact rollout test.
  The real `presentation_coach -> sales_bot` edge remains; only its stale reason/retire condition
  was corrected to the remaining persistence/prompt/Roleplay/report ownership and Gate 4/6 exit.
- Task 8 whole-branch Brooks audit scored 100/100 with 0 Critical, Warning or Suggestion findings.
  CodeGraph impact covered the Provider, codec, Grounding, cache, shared handler and Presentation
  façade; the architecture dependency guard and diff check passed. Conway alignment was not scored
  because repository team-ownership data is unavailable.
- Task 8 independent Trellis check found one workflow-context drift: Task 7's new executable
  Provider/Grounding spec was not yet listed in the task JSONL. Both lists now include it and
  validate at 16 implement / 15 check entries. The repeated focused matrix is `812 passed`; Ruff,
  architecture policy and mypy (`635 source files`) are green. Canonical clean-start gate remains.
