---
estimated_steps: 4
estimated_files: 5
skills_used:
  - using-superpowers
  - safe-grow
  - test-driven-development
  - fullstack-dev
  - systematic-debugging
  - code-refactoring
  - verification-before-completion
---

# T01: Add a shared backend arbiter for single-turn coaching

**Slice:** S02 — 提示节奏收口与单轮唯一动作卡
**Milestone:** M002

## Description

Build the backend seam S02 needs before any UI cleanup matters: one shared arbiter that runs after fuzzy detection, stage analysis, and realtime scoring complete, then decides which coaching signal is primary for this turn, which duplicates to suppress, and which low-level capability signals must remain untouched. This task should first lock those rules with focused failing tests, then wire classic-mode `CapabilityProcessor` to emit only arbiter-approved coaching while preserving S01’s sales payload vocabulary.

## Steps

1. Add failing cases in `backend/tests/unit/test_realtime_feedback_arbiter.py` and `backend/tests/unit/test_capability_processor.py` covering highest-priority issue selection, duplicate `action_card` suppression for the same turn/signature, and preservation of stage/score context without extra competing coaching.
2. Implement `backend/src/sales_bot/websocket/realtime_feedback_arbiter.py` as the single policy seam that accepts fuzzy detections, score suggestions, stage context, pass flags, and prior emission state, then returns the primary coaching decision plus any pacing metadata needed by callers.
3. Refactor `backend/src/sales_bot/websocket/components/capability_processor.py` to use that helper instead of independently sending every fuzzy/score/action output, while keeping `build_action_card(...)` contract fields unchanged and leaving `FuzzyDetectionCapability`’s own cooldown behavior intact.
4. Re-run the focused backend suites, including the existing fuzzy cooldown test selection, and keep the rule behavior documented through assertions rather than hidden comments or magic values.

## Must-Haves

- [ ] The new arbiter chooses one primary coaching direction per turn instead of letting fuzzy and score tips compete blindly.
- [ ] Classic-mode websocket payloads keep S01’s existing field names and sales-first vocabulary.
- [ ] `FuzzyDetectionCapability` local cooldown behavior is preserved rather than replaced by a second low-level throttle.

## Verification

- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_realtime_feedback_arbiter.py tests/unit/test_capability_processor.py`
- `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_fuzzy_detection.py -k cooldown`

## Observability Impact

- Signals added/changed: explicit arbiter-decision expectations for primary issue selection, duplicate suppression, and classic-mode emitted coaching.
- How a future agent inspects this: run the focused pytest commands and inspect `backend/tests/unit/test_realtime_feedback_arbiter.py` for the expected signatures/cooldowns the runtime now enforces.
- Failure state exposed: repeated action-card bursts or priority regressions fail deterministically in unit tests instead of surfacing later as noisy browser behavior.

## Inputs

- `backend/src/sales_bot/websocket/components/capability_processor.py` — classic-mode realtime feedback orchestration that currently emits each capability output independently.
- `backend/src/common/effectiveness/evaluator.py` — existing `build_action_card(...)` contract that must remain stable.
- `backend/src/agent/capabilities/fuzzy_detection.py` — existing category-level cooldown behavior that S02 must not break.
- `backend/tests/unit/test_capability_processor.py` — current classic-path handler coverage.
- `backend/tests/unit/test_fuzzy_detection.py` — low-level cooldown regression coverage to keep intact.

## Expected Output

- `backend/src/sales_bot/websocket/realtime_feedback_arbiter.py` — shared backend pacing / priority helper.
- `backend/src/sales_bot/websocket/components/capability_processor.py` — classic-mode orchestration routed through the arbiter.
- `backend/tests/unit/test_realtime_feedback_arbiter.py` — focused arbiter contract tests.
- `backend/tests/unit/test_capability_processor.py` — classic-mode regression coverage for single-turn primary coaching.
