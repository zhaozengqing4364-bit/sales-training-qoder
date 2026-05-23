# evaluation — Staged Evaluation & Report Generation

Trigger-based staged evaluation, comprehensive reports, evaluation runs, and post-session report automation.

## Local Structure

```
backend/src/evaluation/
├── api.py           # Evaluation REST
├── services/        # Staged eval, comprehensive report, snapshots, triggers
├── triggers/        # turn_count, keyword, stage_transition, time_interval
└── websocket/       # Evaluation event broadcaster
```

## Where to Look

| Concern | Location |
|---------|----------|
| Evaluation REST | `api.py` |
| Staged evaluation engine | `services/staged_evaluation.py` |
| Comprehensive reports | `services/comprehensive_report.py` |
| Session-end auto report | `services/report_generation_trigger.py` |
| Evaluation run records | `services/evaluation_run_service.py` |
| Report snapshots | `services/training_report_snapshot_service.py` |
| Trigger plugins | `triggers/` |
| Scoring rulesets (admin) | `backend/src/admin/api/scoring_rulesets.py` |

## Local Cautions

- Report generation runs fire-and-forget after session end; failures must update `ReportGenerationStatus`, not crash the client path.
- Trigger additions require matching unit tests under `tests/unit/evaluation/triggers/`.
- Prompt template rendering for scoring goes through `prompt_templates.service`.

## Hard Rules

- NEVER block session teardown waiting for full report generation.
- ALWAYS use `Result[T]` or structured error envelopes for report API failures.

## References

- Effectiveness kernel: `backend/src/common/effectiveness/`
- Prompt templates: `backend/src/prompt_templates/AGENTS.md`
