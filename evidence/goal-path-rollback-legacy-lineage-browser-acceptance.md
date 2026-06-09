# Goal Slice Evidence: Path Rollback Future-Only Lineage

Timestamp: 2026-06-04T05:18:00Z

Scope:

- Verified that a quiz attempt created while a temporary path revision was active keeps its original path lineage.
- Verified that the learner path returned after rollback uses the restored active path revision.
- Verified operation-log browser evidence for rollback audit metadata already saved in this slice's screenshots.

QA marker:

- `QA路径回滚lineage-5cabdce5`

Key objects:

- Attempt: `71f70d36-3606-4abe-b9b0-fe55ef439132`
- Temporary path revision: `e05d2a6c-8a93-4e9b-b455-d34dbddde91b`, revision no `5`
- Restored active path revision: `6ee0eded-6705-49a3-8db7-89e135614d44`, revision no `3`
- Legacy paper revision: `00b20686-20c8-4eb6-aef8-27bf71b0ca40`

API evidence:

- `evidence/goal-path-rollback-legacy-lineage-api.json`

Important fields from the API response:

```json
{
  "attempt_context": {
    "path_key": "newcomer_training_path_v1",
    "module_key": "business_skills",
    "module_type": "article_exam",
    "path_revision_id": "e05d2a6c-8a93-4e9b-b455-d34dbddde91b",
    "path_revision_no": 5,
    "paper_revision_id": "00b20686-20c8-4eb6-aef8-27bf71b0ca40",
    "legacy_snapshot_only": false
  },
  "current_learner_path": {
    "path_revision_id": "6ee0eded-6705-49a3-8db7-89e135614d44",
    "path_revision_no": 3,
    "business_level_title": "第2关：商务技巧"
  }
}
```

Browser screenshots:

- `evidence/goal-path-rollback-legacy-attempt-detail.png`
- `evidence/goal-path-rollback-learner-home-after-rollback.png`
- `evidence/goal-path-rollback-operation-log-expanded.png`

Previously run focused tests for this behavior:

```bash
cd backend && venv/bin/python -m pytest tests/unit/test_newcomer_training_path_attempt_lineage.py::test_should_freeze_path_revision_lineage_for_legacy_paper_attempt -q --no-cov
cd backend && venv/bin/python -m pytest tests/unit/test_newcomer_training_path_attempt_lineage.py tests/integration/test_newcomer_training_path_paper_api.py tests/unit/test_newcomer_training_path_papers.py tests/unit/test_newcomer_training_path_audit_logs.py -q --no-cov
cd backend && venv/bin/ruff check src/sales_trainer/services/exam_paper_service.py src/sales_trainer/services/quiz_attempt_context_update.py tests/unit/test_newcomer_training_path_attempt_lineage.py
```

Acceptance result:

- Old attempt retains `path_revision_id=e05d2a6c-8a93-4e9b-b455-d34dbddde91b`.
- Current learner path uses `path_revision_id=6ee0eded-6705-49a3-8db7-89e135614d44`.
- Rollback is future-only; historical attempt lineage is not overwritten.

Remaining goal scope:

- AI prompt old/new browser acceptance remains open.
- Broader operation-log publish / rollback / binding audit rollup remains open.
- Final completion audit and full quality gate remain open.
