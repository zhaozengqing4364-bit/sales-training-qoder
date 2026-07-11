# Gate 2 implementation notes

## Assumptions

- The approved Modular Monolith 2.0 design and Goal provide requirement confirmation; no
  additional user question is required.
- `PRESENTATION_REALTIME_ENGINE_ENABLED=true` is the completion default; `false` is the
  scenario-wide rollback.
- Gate 2 does not extract the Provider codec or consolidate Grounding caches; those remain
  Gate 3 acceptance criteria.

## Deviations

- Whole-branch review found that per-frame audio evidence also recorded rejected frames and
  caused quadratic snapshot growth. The implementation changed to an accepted-only O(1)
  per-turn SHA-256 accumulator flushed once at the local commit boundary.
- Review found two Golden inventory entries pointed at semantically unrelated Sales tests.
  They now point at real Presentation admission, differential, and pre-Gate reconnect tests.
- Trellis check found snapshot scenario normalization and scalar coercion could hide corrupt
  persisted state. Restore now preserves the persisted scenario and rejects coercible wrong
  scalar and Evidence collection types without partially mutating the Engine.
- The first attempted final canonical run after `3443320e` was intentionally terminated during
  the opening backend phase when the remaining Evidence collection coercion was discovered; it
  was not used as evidence. The only final evidence is the later clean-start natural exit 0.

## Evidence log

- CodeGraph confirmed current Presentation StepFun inheritance and Sales capability
  construction/disable cycle.
- CodeGraph impact identified Presentation unit tests and Sales reconnect as mandatory
  regression surfaces.
- Final independent whole-branch review: Approved, Critical/Important/Minor finding = 0.
- Final Trellis check: Approved, finding = 0 after commits `3443320e` and `5f275113`.
- Focused strict snapshot and realtime regression: 475 passed; post-commit Engine state suite:
  194 passed; Ruff, mypy (629 source files), compileall and architecture guard passed.
- Final clean-start canonical gate (`08:11:40` to `08:48:46` UTC) naturally exited 0:
  backend unit+contract 2903 passed / 1 skipped; Vitest 1329 passed / 6 skipped;
  Playwright generic/smoke/newcomer/presentation/sales 3/9/11/2/1 passed with one existing
  paid-provider conditional skip; selected backend 598 passed / 21 skipped; backend coverage
  70.51%; changed executable lines 802/878 (91.34%); critical changed missing lines 0.
- Final authority evidence commit: `047c2b91`.
