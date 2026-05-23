# curriculum_practice — Curriculum & Examiner Runtime

Curriculum plans, practice templates, learning contents, test banks, learner profiles, and examiner voice sessions.

## Local Structure

```
backend/src/curriculum_practice/
├── api.py           # Multiple routers in one module
├── models.py        # Curriculum-specific ORM
├── services/        # Templates, gates, snapshots, learning, examiner
└── websocket/       # /ws/curriculum/examiner
```

## Where to Look

| Concern | Location |
|---------|----------|
| Admin curriculum APIs | `api.py` (`router`, `learning_content_router`, `test_bank_router`) |
| Learner-facing APIs | `api.py` (`learner_router`, `study_router`) |
| Publish gates | `services/publishing_gates.py` |
| Session snapshots | `services/session_snapshots.py`, `services/snapshots.py` |
| Examiner agents | `services/examiner_agents.py` |
| Examiner scoring | `services/examiner_scoring_service.py` |
| Examiner WS | `websocket/router.py`, `websocket/examiner_runtime.py` |
| Template permissions | `permissions.py` |

## Complexity Hotspot

- **`api.py`** — monolithic multi-router module (~2100 lines).
- **`websocket/examiner_runtime.py`** — realtime examiner session orchestration.

## Local Cautions

- Snapshot and lineage fields affect training report provenance; do not rename without migration.
- Publishing gates block premature template/content release — keep gate checks on all publish paths.
- Examiner WS auth follows the same owner/session binding pattern as sales WS.

## Hard Rules

- NEVER publish curriculum artifacts without passing `publishing_gates`.
- ALWAYS register new routers in `router_registry.py` with correct admin vs user Depends.

## References

- Curriculum analytics: `backend/src/curriculum_analytics/`
- Admin analytics: `backend/src/admin/api/analytics_curriculum.py`
