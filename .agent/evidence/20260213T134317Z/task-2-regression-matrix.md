# Historical P0/P1 Regression Matrix (20260213T134317Z)

| Legacy Item | Current Status | Classification | Evidence |
|---|---|---|---|
| P0-1 PPT ASR not integrated | presentation handler now contains queue + streaming ASR pipeline (`_enqueue_asr_audio`, `_start_asr_stream`, `_run_asr_stream`) | fixed | `.agent/evidence/20260213T134317Z/task-2-regression-evidence.log`, `backend/src/presentation_coach/websocket/presentation_handler.py` |
| P0-2 PPT interruption detection incomplete | interruption flow includes detector decision + interruption response path (`_check_and_interrupt`, `interruption_detector.should_interrupt`, `_send_interruption`) | fixed | `.agent/evidence/20260213T134317Z/task-2-regression-evidence.log`, `backend/src/presentation_coach/websocket/presentation_handler.py` |
| P0-3 Sales persona hardcoded | personas loaded from DB join (`AgentPersona` + `Persona`) and no hardcoded `impatient_ceo` list | fixed | `.agent/evidence/20260213T134317Z/task-2-regression-evidence.log`, `backend/src/sales_bot/api/scenarios.py` |
| P0-4 Field mismatch (`runtime_profile_id` vs `voice_runtime_profile_id`) | compatibility bridge exists in FE client and backend schema exports normalized `runtime_profile_id` with internal alias | fixed | `.agent/evidence/20260213T134317Z/task-2-regression-evidence.log`, `web/src/lib/api/client.ts`, `backend/src/common/db/schemas.py` |
| P1-5 StepFunRealtimeHandler too large | handler still large (1835 lines) though helper modules were extracted | still failing | `.agent/evidence/20260213T134317Z/task-2-regression-evidence.log`, `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` |
| P1-6 Deprecated datetime API usage | `datetime.now(UTC)` used; no `utcnow()` in presentation handler | fixed | `.agent/evidence/20260213T134317Z/task-2-regression-evidence.log`, `backend/src/presentation_coach/websocket/presentation_handler.py` |
| P1-7 TTSComponent lacked streaming support | streaming path present (`synthesize_streaming`, `tts_chunk`) with fallback handling | fixed | `.agent/evidence/20260213T134317Z/task-2-regression-evidence.log`, `backend/src/sales_bot/websocket/components/tts_component.py` |
| P1-8 Missing API contract docs | contract docs set includes `model-configs.md`, `voice-runtime.md`, `release-verification.md` | fixed | `.agent/evidence/20260213T134317Z/task-2-regression-evidence.log`, `docs/api-contract/` |

## Coverage Check
- Total historical P0/P1 items evaluated: 8
- Unclassified: 0
