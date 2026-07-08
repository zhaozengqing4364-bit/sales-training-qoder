# Sales Trainer Learning Topic Governance

> Executable backend contract for newcomer-training learning topics managed as future-only asset revisions.

## Scenario: Newcomer Learning Topics Independent From Required Path

### 1. Scope / Trigger

- Trigger: changing `/api/v1/admin/newcomer-training/learning-topics*`, learner `TrainingJourney.learning_topics`, business-etiquette article/quiz access, or AI Coach runtime for `business_skills`.
- Scope: `SalesTrainerAssetRevision` rows with `resource_type="newcomer_learning_topics"` and `logical_id="newcomer_learning_topics_v1"`, plus learner projection and readiness evidence.
- Out of scope: making learning topics block required path completion or adding one-off topic tables.

### 2. Signatures

Admin APIs:

```http
GET  /api/v1/admin/newcomer-training/learning-topics/config
PUT  /api/v1/admin/newcomer-training/learning-topics/config
POST /api/v1/admin/newcomer-training/learning-topics/business-etiquette/generate-draft
POST /api/v1/admin/newcomer-training/learning-topics/publish/preview
POST /api/v1/admin/newcomer-training/learning-topics/publish
GET  /api/v1/admin/newcomer-training/learning-topics/revisions
POST /api/v1/admin/newcomer-training/learning-topics/rollback/preview
POST /api/v1/admin/newcomer-training/learning-topics/rollback
```

Runtime projection:

```python
NEWCOMER_LEARNING_TOPICS_RESOURCE_TYPE = "newcomer_learning_topics"
NEWCOMER_LEARNING_TOPICS_LOGICAL_ID = "newcomer_learning_topics_v1"

class NewcomerLearningTopicsPayload(BaseModel):
    schema_version: Literal["newcomer_learning_topics_v1"]
    topics: list[NewcomerLearningTopicConfig]
```

### 3. Contracts

- First version supports only `topic_key="business_etiquette"` sourced from `source_module_key="business_skills"`.
- Active learning-topic revision controls learner visibility. Working/draft revisions are admin-only.
- `required` and `blocks_next` must remain `false`. Required path progress, readiness gate, and next-stage access must not depend on learning topic completion.
- Score display uses historical quiz attempt score fields: `score`, `max_score`, `passed`, `latest_attempt_id`.
- AI Coach under a learning topic is optional. If enabled, prompt/model bindings must validate before publish or runtime start.
- Readiness may include learning topic quiz attempts as evidence, but learning topic failures must not change required path `training_stage`.

### 4. Validation & Error Matrix

| Condition | Expected behavior |
|---|---|
| No active learning-topic revision | Learner `learning_topics=[]`; business-etiquette endpoints return `[LEARNING_TOPIC_ACTIVE_REVISION_MISSING]` / 404. |
| Topic disabled or missing | Learner topic hidden; business-etiquette endpoints return `[LEARNING_TOPIC_NOT_CONFIGURED]` / 404. |
| Topic sets `required=true` or `blocks_next=true` | Reject save/publish with `[LEARNING_TOPIC_CONFIG_INVALID]` / 422. |
| Enabled topic has no published article | Publish rejects with `[LEARNING_TOPIC_CONTENT_MISSING]` or `[LEARNING_TOPIC_CONTENT_INVALID]`. |
| AI Coach enabled without valid prompt bindings | Publish/runtime rejects with existing AI Coach prompt config errors. |
| Admin publishes or rolls back | Future learner display changes only; historical attempts and scores are preserved. |

### 5. Good/Base/Bad Cases

- Good: admin generates a draft from active path `business_skills`, binds a published learning article, previews impact, publishes, and learner Journey shows one non-blocking learning topic.
- Base: no learning topic is published; required path still works and no fallback topic is invented.
- Bad: `business_skills` remains in `TrainingJourney.modules` as a required quiz module, causing article completion to block PPT/realtime progress.

### 6. Tests Required

- Unit: generate draft from active `business_skills`, publish active topic, and project it under `TrainingJourney.learning_topics`.
- Unit: required path excludes `business_skills` from `modules`, `overall_progress`, and readiness gate.
- Unit: learning topic quiz attempts appear as non-blocking readiness evidence and can complete a retraining task by capability.
- Unit: AI Coach session creation for `business_skills` resolves active learning-topic config instead of required path config.
- Frontend: admin articles index shows learning topic entry and publish/generate actions through the public API facade.

### 7. Wrong vs Correct

#### Wrong

```python
modules = [module for module in active_path.modules if module.module_key == "business_skills"]
overall = required_progress(modules)
```

This keeps learning articles inside the blocking path and makes article/quiz scores affect next-stage readiness.

#### Correct

```python
modules = [module for module in active_path.modules if module.module_key != "business_skills"]
learning_topics = await LearningTopicProjectionService(db).learner_topics(user_id=user_id)
```

Required path and learning-topic evidence are projected separately, so operators can manage articles without changing path gates.
