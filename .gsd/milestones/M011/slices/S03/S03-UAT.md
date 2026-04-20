# S03: Coverage answerability、answer assembly 与 compatibility seam — UAT

**Milestone:** M011
**Written:** 2026-03-31T05:37:18.036Z

# S03: Coverage answerability、answer assembly 与 compatibility seam — UAT

**Milestone:** M011  
**Written:** 2026-03-31

## UAT Type

- UAT mode: focused backend/runtime compatibility verification on the shipped knowledge-answer seams.
- Why this mode is sufficient: S03 ships backend/runtime behavior, persisted audit rows, and compatibility readers on existing realtime/runtime/replay surfaces. Acceptance therefore depends on proving the exact shipped seams: slot-coverage answerability, deterministic grounded assembly, persisted audit runs, StepFun runtime guardrails, runtime diagnostics propagation, and replay metadata preservation.

## Preconditions

- Repo root: `/Users/zhaozengqing/github/销售训练qoder`
- Backend dependencies installed in `backend/venv`.
- Run the backend verification commands **serially**, not in parallel, because repo-root pytest shares the top-level `.coverage` SQLite file.
- Current slice-plan verification commands are available from repo root:
  1. `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_answerability.py -q`
  2. `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_answer_assembler.py -q`
  3. `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_answer_audit_repo.py backend/tests/unit/common/test_knowledge_answer_engine.py backend/tests/unit/test_stepfun_realtime_handler.py backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py backend/tests/unit/test_replay_service.py -q`

## Smoke Test

1. Run the three slice-plan commands serially.
2. **Expected:** all 142 focused tests pass (5 + 3 + 134).
3. **Expected:** the third command proves the shipped compatibility seam across audit persistence, engine orchestration, realtime payloads, runtime diagnostics, and replay metadata.

## Test Cases

### 1. Coverage-based answerability distinguishes sufficient / partial / insufficient / blocked

1. Run `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_answerability.py -q`.
2. Inspect the focused cases.
3. **Expected:** when required and optional slots are covered, answerability is `sufficient`.
4. **Expected:** when only part of required coverage lands, answerability is `partial`.
5. **Expected:** when hits exist but required coverage misses the partial bar, answerability is `insufficient`.
6. **Expected:** when retrieval failed before evidence existed, answerability is `blocked` and preserves the blocked reason.
7. **Expected:** when no answerability profile exists, the evaluator degrades to count-based compatibility behavior instead of failing closed.

### 2. Deterministic answer assembly only emits snippet-backed claims into learner-facing final text

1. Run `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_answer_assembler.py -q`.
2. Inspect the grounded-answer case.
3. **Expected:** `final_text` is deterministic, numbered, and built only from rows with normalized snippets.
4. **Expected:** `citations` are normalized and retain the supporting snippet/document metadata.
5. **Expected:** `rewritten_queries` and compact retrieval summary are preserved on the assembled result.
6. Inspect the blocked-answer case.
7. **Expected:** blocked answerability emits one fixed learner-safe `blocked_text` and no citations.
8. Inspect the unsupported-content case.
9. **Expected:** rows with only content text and no quoteable snippet are preserved in `unsupported_claims` and do not leak into `final_text`.

### 3. Engine orchestration persists one answer run plus ordered audit steps

1. Run `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_answer_audit_repo.py backend/tests/unit/common/test_knowledge_answer_engine.py -q`.
2. Inspect the happy-path engine test.
3. **Expected:** the engine normalizes `请介绍一下世袭科技` to the canonical entity, executes the planned retrieval steps, produces `answerability == "sufficient"`, and returns one snippet-backed answer with citations.
4. **Expected:** `result.audit_run_id` is populated.
5. **Expected:** the persisted `KnowledgeAnswerRun` row records the entrypoint, answerability, and retrieval summary, and the ordered `KnowledgeAnswerRunStep` rows preserve step order and payloads.
6. Inspect the no-config case.
7. **Expected:** the engine degrades to the placeholder/unanswered contract without raising and without fabricating an audit row.

### 4. StepFun strict KB mode blocks unsupported grounded answers with learner-safe copy

1. Run `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_stepfun_realtime_handler.py -q`.
2. Inspect `test_create_response_blocks_when_strict_kb_answerability_is_insufficient`.
3. **Expected:** when `require_kb_grounding` is true and answerability is `insufficient`, StepFun does **not** forward a normal upstream response request.
4. **Expected:** it emits a learner-safe blocked `tts_audio` payload instead.
5. **Expected:** the blocked copy tells the learner there is not enough internal KB evidence and asks for more specific product/version keywords.

### 5. Partial answerability keeps the grounded seam visible and trims unsupported generated sentences

1. In the same StepFun handler suite, inspect `test_create_response_marks_partial_answerability_when_overview_query_only_has_one_citation`.
2. **Expected:** partial grounded answers keep a knowledge-answer diagnostics bundle on the handler and inject the “若信息不足，请明确说明不确定之处” overlay into the response instructions.
3. Inspect `test_flush_active_response_trims_unsupported_sentences_in_partial_mode`.
4. **Expected:** the final emitted and persisted text is trimmed down to only the supported cited sentence.
5. Inspect `test_flush_active_response_falls_back_when_partial_mode_has_no_supported_sentence` if present in the local branch.
6. **Expected:** when no generated sentence is actually supported by the citation bundle, the handler falls back to the safer grounded copy rather than preserving unsupported marketing-style claims.

### 6. Realtime payloads carry the same answerability / audit / citation line

1. In the same StepFun handler suite, inspect `test_flush_active_response_emits_runtime_answer_diagnostics_and_citations`.
2. **Expected:** emitted `tts_audio` payloads include `knowledge_answer_diagnostics`.
3. **Expected:** that bundle contains `answerability`, `audit_run_id`, `rewritten_queries`, and `citations`.
4. **Expected:** citation metadata still contains the expected supporting document title.

### 7. Runtime diagnostics surface live knowledge-answer diagnostics without inventing a second contract

1. Run `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py -q`.
2. Inspect `test_build_session_runtime_diagnostics_surfaces_live_answer_diagnostics_when_present`.
3. **Expected:** `build_session_runtime_diagnostics(...)` returns `knowledge_answer_diagnostics` unchanged when live diagnostics are present.
4. **Expected:** the runtime diagnostics bundle includes `answerability`, `audit_run_id`, `rewritten_queries`, and `citations`.
5. **Expected:** this seam coexists with existing retrieval-facts / KB-lock diagnostics rather than replacing them.

### 8. Replay preserves knowledge-answer diagnostics inside assistant transcript metadata

1. Run `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_replay_service.py -q`.
2. Inspect `test_get_replay_data_keeps_message_knowledge_answer_diagnostics_in_transcript_metadata`.
3. **Expected:** replay payloads keep `messages[*].transcript_metadata.knowledge_answer_diagnostics` intact.
4. **Expected:** the replay message still carries `answerability == "sufficient"`, the original `audit_run_id`, and citation metadata including the supporting document title.
5. **Expected:** replay does not rebuild or rename the knowledge-answer seam; it preserves the runtime-generated metadata line.

## Edge Cases

### No answerability profile configured
- **Expected:** the evaluator falls back to hit-count semantics instead of breaking the answer path.

### Evidence rows lose snippets but keep content
- **Expected:** such rows degrade into `unsupported_claims`; they do not become learner-facing supported claims.

### Retrieval blocked or search failed before evidence exists
- **Expected:** answerability is `blocked` and learner-facing output stays on fixed safe blocked copy.

### Serial verification only
- **Expected:** focused repo-root backend verification is run serially; parallel execution can create false negatives because of shared `.coverage` state.

## Failure Signals

- `audit_run_id` disappears from emitted runtime diagnostics or replay metadata after a grounded answer.
- StepFun strict KB mode starts forwarding unsupported responses instead of blocking with learner-safe copy.
- Partial-mode flush stops trimming unsupported sentences.
- `KnowledgeAnswerRunStep` ordering or payload persistence drifts, forcing downstream tooling to reconstruct execution from handler-local state.
- Runtime diagnostics or replay invent a second answerability schema instead of reusing the compatibility seam.

## Requirements Proved By This UAT

- None change status at S03 close-out. This UAT proves the new grounded-answer seam and auditability needed for downstream debug/eval/report work.

## Not Proved By This UAT

- A dedicated recent-run debug API.
- Canonical completed-session report parity for the new knowledge-answer audit fields.
- Eval-case closure for M011/S04.

## Notes For The Next Slice

- Build S04 on the persisted `KnowledgeAnswerRun` / `KnowledgeAnswerRunStep` seam plus the existing compatibility payloads.
- Do not reconstruct answerability or execution order from handler-local state.
- Do not assume the current async StepFun helper must already be refactored to call the synchronous engine directly; preserve the current compat contract while exposing a better inspection surface.
