# Implementation Notes

## Deviations

- Task 4 exposed pre-existing platform-admin learner-route assertions after stale
  scenario fixtures were made publishable. Production permission semantics and
  those assertions were intentionally left unchanged; the prerequisite release
  gate uses explicit nodes until the separate permission decision is governed.
- Several unrelated audio-lineage tests still use pre-canonical
  `general_audio_scoring` fixtures for `ppt_explanation` / `elevator_pitch`.
  They were not broadened into this prerequisite slice.

## Verification Notes

- Baseline command collected 88 tests: 79 passed, 9 failed before production changes.
- In-scope stale fixtures: legacy path uses `elevator_pitch + article_exam`; material path binds a non-elevator audio scenario; business-etiquette tests seed the old path source without an active learning-topic revision.
- Out-of-scope baseline failures: four generic QuizService tests create published units without any active path revision; realtime permission test still expects `admin` to be denied although current permission code allows it.
- The user approved proceeding with the registered baseline failures. Tasks 1-3
  implemented the policy and projections; Task 4 added direct-entry regressions,
  canonical learning-topic/material fixtures, API contract updates, and release
  gate targets without additional production changes.
- Task 4 focused prerequisite gate: 61 passed. Full material/audio-lineage/realtime
  isolation: 20 passed, 7 failed, all outside the prerequisite nodes (five stale
  audio-lineage fixtures/assertions and two platform-admin learner-route assertions).
- Task 4 independent review restored the full non-admin material object-scope
  regression to the critical gate and isolated the unresolved platform-admin
  learner-route expectation in a dedicated baseline node. The optional learning
  topic test now asserts the required path is actually prerequisite-locked before
  proving topic access remains available.
- Final cross-layer review found and closed three integration gaps: historical
  blank/duplicate prerequisites now preserve their explicit validation context
  through legacy path-config projection; multi-target audio groups unlock only
  from completion evidence for the exact referenced target; and the legacy
  `/paths` parity regression is now an explicit critical-gate target.
- A fixed 09:00 timestamp in the audio-group regrade regression made latest
  outcome selection depend on wall-clock time. The test now orders regrade
  timestamps relative to the original submission.
- Final task slice: 100 passed. Full-source Ruff, changed-file format check,
  policy mypy, gate shell syntax, and `git diff --check` passed.
- The repository's existing newcomer mypy gate still reports two
  `no-any-return` errors in `_learning_topic_capability_keys`; those lines and
  semantics are outside this task and remain visible rather than being silently
  excluded or repaired here.
