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
- Newcomer Training Path (异步学习/录音/考卷, **separate contract**): `backend/src/sales_trainer/AGENTS.md` and `docs/api-contract/sales-trainer.md`
- Realtime sales practice (StepFun WebSocket): `backend/src/sales_bot/AGENTS.md`

> 边界提示：本域的"Examiner 实时语音考核" (`/ws/curriculum/examiner/{session_id}`) 是独立 WS 协议, **不**与 `sales_bot` 实时销售对练或 `sales_trainer` 异步学习复用。任何跨域复用须经显式登记与 review。
