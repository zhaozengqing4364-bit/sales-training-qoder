---
estimated_steps: 4
estimated_files: 4
skills_used:
  - using-superpowers
  - safe-grow
  - test-driven-development
  - fullstack-dev
  - systematic-debugging
  - verification-before-completion
---

# T02: Route classic arbitration through the shared coaching-focus rule

**Slice:** S03 — 阶段推进教练与下一轮规则闭环
**Milestone:** M002

## Description

Apply the new coaching-focus contract to the classic runtime first. `CapabilityProcessor` already has the richest stage and scoring context, but `RealtimeFeedbackArbiter` currently ignores most of it and still builds action cards from pass flags plus one suggestion. This task should make the arbiter consume the shared focus rule, then prove the classic path changes `action_card` text when stage or weakest/declining dimension changes while preserving S02’s single-action suppression behavior.

## Steps

1. Extend `backend/tests/unit/test_realtime_feedback_arbiter.py` with failing cases that prove stage context and weakest/declining dimension can change the chosen `issue`, `replacement`, and `next_turn_rule` without breaking same-turn duplicate suppression or context preservation.
2. Extend `backend/tests/unit/test_capability_processor.py` with failing classic-path cases that feed full `stage_data` plus raw realtime-scoring output and assert the emitted `action_card` now follows the shared coaching-focus rule.
3. Update `backend/src/sales_bot/websocket/realtime_feedback_arbiter.py` and `backend/src/sales_bot/websocket/components/capability_processor.py` so the arbiter passes rich stage/score context into `build_action_card(...)` and keeps the existing websocket payload shapes unchanged.
4. Re-run the focused backend suites and confirm classic-mode `fuzzy_detection` / `stage_update` / `score_update` messages still surface as context while `action_card` remains the only primary textual coach surface.

## Must-Haves

- [ ] The arbiter uses stage-aware and dimension-aware context when building the primary `action_card`.
- [ ] Classic-mode websocket payload shapes remain stable for the existing training-page consumer.
- [ ] S02 duplicate suppression and context-message preservation still pass after the refactor.

## Verification

- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_feedback_arbiter.py tests/unit/test_capability_processor.py`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_feedback_arbiter.py tests/unit/test_capability_processor.py -vv`

## Observability Impact

- Signals added/changed: arbiter expectations for stage-aware focus selection, classic emitted `action_card` payloads, and preserved contextual `fuzzy_detection` / `stage_update` / `score_update` messages.
- How a future agent inspects this: run the focused pytest commands and inspect `backend/tests/unit/test_realtime_feedback_arbiter.py` and `backend/tests/unit/test_capability_processor.py` for the exact stage/dimension combinations that should change the action-card output.
- Failure state exposed: if classic mode falls back to pass-flags-only behavior or loses same-turn suppression, the focused arbiter/classic suites fail with explicit expected `action_card` values.

## Inputs

- `backend/src/common/effectiveness/evaluator.py` — shared coaching-focus helper and updated `build_action_card(...)` from T01.
- `backend/src/sales_bot/websocket/realtime_feedback_arbiter.py` — current single-turn pacing and duplicate-suppression seam.
- `backend/src/sales_bot/websocket/components/capability_processor.py` — classic runtime orchestration that already has full `stage_data` and raw scoring output.
- `backend/tests/unit/test_realtime_feedback_arbiter.py` — current arbiter behavior coverage.
- `backend/tests/unit/test_capability_processor.py` — current classic runtime behavior coverage.

## Expected Output

- `backend/src/sales_bot/websocket/realtime_feedback_arbiter.py` — arbiter wired to the shared coaching-focus contract.
- `backend/src/sales_bot/websocket/components/capability_processor.py` — classic runtime feeding rich stage/score context into the arbiter.
- `backend/tests/unit/test_realtime_feedback_arbiter.py` — focused arbiter regressions for stage-aware and dimension-aware action selection.
- `backend/tests/unit/test_capability_processor.py` — classic-path regressions proving the smarter action-card output and preserved S02 pacing behavior.
