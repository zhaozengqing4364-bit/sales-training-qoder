# supervisor — Supervisor Review & Retraining Loop

Supervisor team report review, score calibration, and retraining task orchestration.

## Local Structure

```
backend/src/supervisor/
├── api.py       # Supervisor REST
├── service.py   # Review + retraining application service
└── schemas.py
```

## Where to Look

| Concern | Location |
|---------|----------|
| REST endpoints | `api.py` |
| Review & retraining logic | `service.py` |
| Request/response schemas | `schemas.py` |
| Practice session creation | `common/services/practice_session_service.py` |
| Report data | `common/db/models.py` (ComprehensiveReport, TrainingReportSnapshot) |

## Complexity Hotspot

- **`service.py`** — large monolith (~2300 lines) spanning review, calibration, and retraining.

## Local Cautions

- Retraining task completion may spawn linked training tasks and practice sessions.
- Score calibration changes affect supervisor analytics — preserve auditability.
- Service errors use `SupervisorServiceError` mapped to structured JSON envelopes in `api.py`.

## Hard Rules

- NEVER create retraining sessions without supervisor authorization checks in service layer.
- ALWAYS keep retraining ↔ training_task linkage migrations consistent.

## References

- Training tasks: `backend/src/common/training_tasks/`
- Evaluation snapshots: `backend/src/evaluation/AGENTS.md`
