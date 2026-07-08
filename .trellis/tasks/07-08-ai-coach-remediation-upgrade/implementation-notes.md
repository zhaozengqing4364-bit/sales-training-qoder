# Implementation Notes

## Scope

- Start with PR1 backend stability: align next-action validation with the API contract and add a deterministic fallback training card when LLM next-action generation fails.
- Add the smallest PR3 frontend workbench slice: make the current training card/action the primary area, collapse full coach conversation into an evidence panel, and keep follow-up prompts actionable outside the collapsed log.

## Deviations

- None yet.

## Verification

- Backend targeted unit tests: `6 passed, 54 deselected`.
- Backend ruff check: passed.
- Backend `py_compile`: passed.
- Frontend coach page tests: `15 passed`.
- Frontend lint for touched coach files: passed.
