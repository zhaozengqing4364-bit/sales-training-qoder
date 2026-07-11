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

## Evidence

- Planning artifact audit: three rounds; final result `AUDIT CLEAN (0 hard errors)`.
- Pre-implementation task context validation: 15 implementation and 14 check entries valid.
- Pre-implementation architecture policy: `dependency policy satisfied`.
- Implementation base commit: `dd6202c1`.
