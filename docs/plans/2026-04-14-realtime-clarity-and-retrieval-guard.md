# Realtime Clarity And Retrieval Guard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove backend-generated filler clarification copy, prevent unmatched queries from being forced into the wrong retrieval profile, and surface backend-managed voice rate metadata on the realtime path without hardcoding new prompt text.

**Architecture:** Keep the change narrow. The response style fix stays in backend post-processing and question-limit enforcement, not prompt text. The retrieval fix lands at the intent-classification fallback seam. The voice-speed change reuses existing persona `tts_config.rate` as metadata propagated through the websocket/realtime payload so frontend-configured playback can honor backend policy without changing StepFun upstream contracts.

**Tech Stack:** Python, FastAPI, websocket realtime handler, existing knowledge-engine compatibility layer, pytest.

---

### Task 1: Remove backend filler phrase from question-limit enforcement

**Files:**
- Modify: `backend/src/sales_bot/services/voice_instruction_compiler.py`
- Test: `backend/tests/unit/test_voice_instruction_compiler.py`

**Step 1: Write a failing test**
- Add a focused assertion that `enforce_question_limit()` truncates extra questions without appending `先回答这一点即可。`.

**Step 2: Run test to verify it fails**
- Run: `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_voice_instruction_compiler.py -q`

**Step 3: Write minimal implementation**
- Keep truncation.
- Remove the hardcoded suffix injection.

**Step 4: Run test to verify it passes**
- Re-run the same focused suite.

### Task 2: Stop routing unmatched knowledge queries into the first available profile

**Files:**
- Modify: `backend/src/common/knowledge_engine/intent_classifier.py`
- Test: `backend/tests/unit/common/test_knowledge_intent_classifier.py` or the nearest focused knowledge-engine unit file

**Step 1: Write a failing test**
- Add a regression proving unmatched queries return no profile key instead of `first_available_profile` fallback.

**Step 2: Run test to verify it fails**
- Run the focused classifier suite.

**Step 3: Write minimal implementation**
- Return empty `profile_key` and explicit fallback reason when no rule matches.

**Step 4: Run test to verify it passes**
- Re-run the focused classifier suite.

### Task 3: Surface backend-managed TTS rate metadata on realtime responses

**Files:**
- Modify: `backend/src/sales_bot/services/voice_runtime_policy.py`
- Modify: `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
- Test: `backend/tests/unit/test_sales_websocket_handler.py` or existing focused StepFun handler tests

**Step 1: Write a failing test**
- Add a focused regression proving resolved voice policy includes normalized realtime playback rate derived from persona `tts_config.rate`, and that realtime `tts_chunk`/fallback payloads expose it.

**Step 2: Run test to verify it fails**
- Run the focused voice-policy / handler suite.

**Step 3: Write minimal implementation**
- Parse persona `tts_config.rate` into a bounded numeric playback multiplier.
- Persist it in effective voice policy / snapshot metadata.
- Include it in websocket audio payload metadata.
- Do not send unsupported rate params to StepFun upstream.

**Step 4: Run tests to verify they pass**
- Re-run focused suites.

### Task 4: Suppress learner-facing idle-timeout reasons and proactively keep the StepFun upstream alive

**Files:**
- Modify: `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`
- Modify: `web/src/hooks/websocket/transport.ts`
- Test: `backend/tests/unit/test_stepfun_realtime_handler.py`
- Test: `web/src/hooks/websocket/transport.test.ts`

**Step 1: Write failing tests**
- Add a focused frontend regression proving `too long without operation` no longer becomes learner-facing reconnect copy.
- Add focused backend regressions proving the StepFun handler sends websocket ping keepalives when the upstream connection sits idle, and skips pings when recent upstream activity already exists.

**Step 2: Run tests to verify they fail**
- Run the focused transport and StepFun handler suites.

**Step 3: Write minimal implementation**
- Keep provider idle-timeout details in diagnostics only; let the learner-facing reconnect copy fall back to generic reconnect messaging.
- Track upstream activity on send/receive.
- Start a lightweight websocket-ping keepalive loop after `session.update` succeeds.
- Stop the keepalive task on upstream close/reconnect cleanup.

**Step 4: Run tests to verify they pass**
- Re-run the focused transport and StepFun handler suites.

### Task 5: Final regression bundle

**Files:**
- Verify only

**Step 1: Run exact regression bundle**
- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_voice_instruction_compiler.py backend/tests/unit/common/test_knowledge_intent_classifier.py backend/tests/unit/test_runtime_dependency_contract.py -q`
- Add the focused realtime handler suite if touched.
- `npm --prefix web test -- --run src/hooks/websocket/transport.test.ts src/hooks/use-streaming-audio-player.test.ts src/hooks/websocket/message-handlers.test.ts`

**Step 2: Sanity-check backend health**
- If local backend is running, hit `/health` after reload.

**Step 3: Summarize prompt guidance separately**
- Provide a frontend-configurable prompt recommendation in Chinese with no `*` characters.
