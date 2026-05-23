# presentation_coach — PPT Practice Runtime Domain

Voice-driven presentation coaching: PPT upload, talking-point tracking, realtime feedback, and post-session reports.

## Local Structure

```
backend/src/presentation_coach/
├── api/           # User-facing presentation REST
├── services/      # Parsing, coaching, scoring, AI policy, progress
└── websocket/     # Realtime handlers (StepFun + legacy)
```

## Where to Look

| Concern | Location |
|---------|----------|
| Presentation CRUD / upload | `api/presentations.py` |
| PPT parsing | `services/ppt_parser.py` |
| Coaching workflow | `services/coach_service.py` |
| AI policy resolution | `services/presentation_ai_policy_service.py` |
| Prompt role binding | `services/prompt_role_resolver.py` |
| Talking-point / forbidden-word matching | `services/point_tracker.py`, `services/forbidden_matcher.py` |
| Interruption detection | `services/interruption_detector.py` |
| StepFun realtime handler | `websocket/presentation_stepfun_realtime_handler.py` |
| Legacy ASR/TTS handler | `websocket/presentation_handler.py` |
| WS route registration | `backend/src/websocket_routes.py` |
| Runtime plugin selection | `backend/src/training_runtime/plugins.py` |

## Complexity Hotspot

- **`websocket/`** — two parallel realtime paths; runtime selection goes through `training_runtime`.
- **`api/presentations.py`** — large upload/replace surface with documented resource-race inventory.

## Local Cautions

- NEVER surface raw exceptions to the client during practice (Constitution I).
- ALWAYS keep StepFun and legacy handler selection aligned with `PresentationScenarioPlugin`.
- Upload/replace/delete must respect active-session blockers documented in `presentations.py`.
- Changing talking-point or forbidden-word shapes affects both runtime scoring and stored sessions.

## Hard Rules

- NEVER bypass `presentation_validator` on upload paths.
- ALWAYS route WebSocket changes through `websocket_routes.py` registration.

## References

- Backend coding rules: `.kiro/steering/backend-principles.md`
- Shared kernel: `backend/src/common/AGENTS.md`
- Training runtime: `backend/src/training_runtime/AGENTS.md`
- API contracts: `docs/api-contract/`
