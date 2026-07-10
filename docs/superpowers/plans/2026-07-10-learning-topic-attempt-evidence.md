# Learning Topic Attempt Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让商务礼仪和客户常见问答的小测都生成 revision-bound、可回放、可进入 Journey/Readiness 的可信 Attempt 证据。

**Architecture:** 新建通用深 Module `LearningTopicAttemptService` 和规范化 Attempt 表。业务题目来源仍由商务礼仪题库或 FAQ 卡片 Adapter 提供；持久化、幂等、revision lineage、失败保留、次数限制和进度投影集中在一个 Interface 后面。旧商务礼仪表只在迁移/回滚期保留，不再作为新写入真源。

**Tech Stack:** SQLAlchemy AsyncSession、Alembic、Pydantic v2、FastAPI、LLM scoring Adapter、Next.js/TypeScript、Pytest、Vitest。

## Global Constraints

- Attempt 必须在调用 AI 前持久化 `submitted` 状态和题目/答案快照。
- AI 失败时更新同一 Attempt 为 `failed` 并提交 transaction，不得丢失用户提交。
- 当前专题进度只读取与 active topic revision 完全一致的 Attempt。
- 历史 legacy Attempt 可以展示，但必须标为 `legacy_unbound`，不能计入当前专题进度或准备度达标。
- 次数限制按 `user_id + topic_key + learning_unit_key + topic_revision_id` 计算。
- `client_token` 在同一用户和专题内唯一；重复提交返回同一 Attempt，不重复调用 AI。
- 快照不得包含 API key、完整系统 Prompt、raw model chain-of-thought 或敏感日志；保存 Prompt contract hash、模板/revision 标识、provider/model 和结构化评分结果。
- 学习专题保持非必修；本计划只修证据和进度，不改变主路径阻断规则。

---

### Task 1: 建立规范化 Learning Topic Attempt 模型

**Files:**
- Create: `backend/alembic/versions/20260710_1500_093_learning_topic_attempts.py`
- Modify: `backend/src/sales_trainer/models.py`
- Create: `backend/src/sales_trainer/services/learning_topic_attempt_service.py`
- Create: `backend/tests/unit/test_learning_topic_attempt_service.py`

**Interfaces:**
- Produces: `SalesTrainerLearningTopicAttempt`
- Produces: `LearningTopicAttemptCreate`
- Produces: `LearningTopicAttemptService.begin_attempt`
- Produces: `LearningTopicAttemptService.complete_attempt`
- Produces: `LearningTopicAttemptService.fail_attempt`
- Produces: `LearningTopicAttemptService.latest_by_unit`
- Produces: `LearningTopicAttemptService.enforce_attempt_limits`

- [ ] **Step 1: 写 lineage、幂等和 revision 隔离红测**

```python
first = await service.begin_attempt(
    actor=learner,
    command=LearningTopicAttemptCreate(
        attempt_kind="customer_faq_short_answer",
        topic_key="customer_faq",
        learning_unit_key="faq-unit-1",
        learning_unit_title="产品价值与定位",
        client_token="faq-client-token-0001",
        path_revision_id=path_revision_id,
        path_revision_no=1,
        topic_revision_id=topic_revision_id,
        topic_revision_no=3,
        source_revision_id=None,
        source_revision_no=None,
        capability_snapshot={"capability_keys": ["product_understanding"]},
        question_snapshots=[{"card_key": "faq-001", "question": "产品价值是什么？"}],
        answers_snapshot=[{"card_key": "faq-001", "answer_text": "产品通过标准化训练帮助销售稳定表达价值。"}],
    ),
)
replayed = await service.begin_attempt(actor=learner, command=first_command)
assert replayed.attempt_id == first.attempt_id
```

再发布 topic revision 4，调用 `latest_by_unit(user_id=str(learner.user_id), topic_keys=["customer_faq"], topic_revision_id=revision_4, unit_keys=["faq-unit-1"])`，断言不返回 revision 3 Attempt，revision 4 的次数为 0。

Run: `cd backend && ./.venv/bin/python -m pytest -c pyproject.toml tests/unit/test_learning_topic_attempt_service.py -q --no-cov`

Expected: FAIL because table and service do not exist.

- [ ] **Step 2: 创建 migration 和 ORM model**

```python
class SalesTrainerLearningTopicAttempt(Base):
    __tablename__ = "sales_trainer_learning_topic_attempts"

    attempt_id = Column(String(36), primary_key=True, default=_uuid)
    attempt_kind = Column(String(50), nullable=False, index=True)
    topic_key = Column(String(80), nullable=False, index=True)
    learning_unit_key = Column(String(80), nullable=False, index=True)
    learning_unit_title = Column(String(120), nullable=False)
    user_id = Column(String(36), ForeignKey("users.user_id"), nullable=False, index=True)
    client_token = Column(String(100), nullable=False)
    path_revision_id = Column(String(36), nullable=True, index=True)
    path_revision_no = Column(Integer, nullable=True)
    topic_revision_id = Column(String(36), nullable=True, index=True)
    topic_revision_no = Column(Integer, nullable=True)
    source_revision_id = Column(String(36), nullable=True, index=True)
    source_revision_no = Column(Integer, nullable=True)
    lineage_status = Column(String(30), nullable=False, default="bound")
    capability_snapshot = Column(JSON, nullable=False, default=dict)
    question_snapshots = Column(JSON, nullable=False, default=list)
    answers_snapshot = Column(JSON, nullable=False, default=list)
    scoring_snapshot = Column(JSON, nullable=False, default=dict)
    capability_scores = Column(JSON, nullable=False, default=list)
    weak_capability_keys = Column(JSON, nullable=False, default=list)
    remediation_snapshot = Column(JSON, nullable=False, default=dict)
    total_score = Column(Numeric(5, 2), nullable=True)
    max_score = Column(Numeric(5, 2), nullable=True)
    passed = Column(Boolean, nullable=True)
    status = Column(String(20), nullable=False, default="submitted", index=True)
    failure_code = Column(String(120), nullable=True)
    submitted_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("user_id", "topic_key", "client_token", name="uq_learning_topic_attempt_client_token"),
        CheckConstraint("status IN ('submitted', 'scored', 'failed')", name="ck_learning_topic_attempt_status"),
        CheckConstraint("lineage_status IN ('bound', 'legacy_unbound')", name="ck_learning_topic_attempt_lineage"),
        Index(
            "idx_learning_topic_attempt_current_progress",
            "user_id", "topic_key", "learning_unit_key", "topic_revision_id", "submitted_at",
        ),
    )
```

Migration 创建新表后把旧 `sales_trainer_business_etiquette_quiz_attempts` 复制到新表：沿用原 `attempt_id`，`attempt_kind='business_etiquette_quiz'`、`topic_key='business_etiquette'`、`client_token='legacy:' + attempt_id`、`lineage_status='legacy_unbound'`、`topic_revision_id=NULL`。使用 `WHERE NOT EXISTS (attempt_id)` 保证 upgrade 重跑不重复；旧表不删除，保证应用回滚。

- [ ] **Step 3: 实现 Attempt 状态机**

```python
class LearningTopicAttemptCreate(BaseModel):
    attempt_kind: Literal["business_etiquette_quiz", "customer_faq_short_answer"]
    topic_key: Literal["business_etiquette", "customer_faq"]
    learning_unit_key: str
    learning_unit_title: str
    client_token: str
    path_revision_id: str | None
    path_revision_no: int | None
    topic_revision_id: str
    topic_revision_no: int
    source_revision_id: str | None
    source_revision_no: int | None
    capability_snapshot: dict[str, Any]
    question_snapshots: list[dict[str, Any]]
    answers_snapshot: list[dict[str, Any]]
    allow_retake: bool = True
    max_attempts: int | None = None

async def begin_attempt(self, *, actor: User, command: LearningTopicAttemptCreate) -> SalesTrainerLearningTopicAttempt:
    await self._db.scalar(
        select(User.user_id)
        .where(User.user_id == str(actor.user_id))
        .with_for_update()
    )
    existing = await self._by_client_token(
        user_id=str(actor.user_id),
        topic_key=command.topic_key,
        client_token=command.client_token,
    )
    if existing is not None:
        return existing
    await self.enforce_attempt_limits(
        user_id=str(actor.user_id),
        topic_key=command.topic_key,
        learning_unit_key=command.learning_unit_key,
        topic_revision_id=command.topic_revision_id,
        allow_retake=command.allow_retake,
        max_attempts=command.max_attempts,
    )
    attempt = SalesTrainerLearningTopicAttempt(
        user_id=str(actor.user_id),
        status="submitted",
        lineage_status="bound",
        **command.model_dump(exclude={"allow_retake", "max_attempts"}),
    )
    self._db.add(attempt)
    await self._db.flush()
    await self._db.commit()
    await self._db.refresh(attempt)
    return attempt
```

`complete_attempt()` 只允许 `submitted -> scored`；`fail_attempt()` 只允许 `submitted -> failed`。两者按 `attempt_id + user_id` 查询，更新 scoring/capability/remediation snapshot 后 commit。已 scored/failed 的幂等重放返回原记录。

- [ ] **Step 4: 实现 current revision 查询和次数限制**

```python
stmt = select(SalesTrainerLearningTopicAttempt).where(
    SalesTrainerLearningTopicAttempt.user_id == user_id,
    SalesTrainerLearningTopicAttempt.topic_key == topic_key,
    SalesTrainerLearningTopicAttempt.learning_unit_key == learning_unit_key,
    SalesTrainerLearningTopicAttempt.topic_revision_id == topic_revision_id,
    SalesTrainerLearningTopicAttempt.lineage_status == "bound",
)
```

任何 current progress、retake count 和 Readiness 证据查询必须包含上述五个条件。

次数限制通过同一 Module 执行：

```python
async def enforce_attempt_limits(
    self, *, user_id: str, topic_key: str, learning_unit_key: str,
    topic_revision_id: str, allow_retake: bool, max_attempts: int | None,
) -> None:
    attempt_count = await self.count_current_revision_attempts(
        user_id=user_id,
        topic_key=topic_key,
        learning_unit_key=learning_unit_key,
        topic_revision_id=topic_revision_id,
    )
    if not allow_retake and attempt_count > 0:
        raise LearningTopicAttemptError(
            "[LEARNING_TOPIC_RETAKE_NOT_ALLOWED]",
            "该学习单元不允许重复小测。",
            409,
        )
    if max_attempts is not None and attempt_count >= max_attempts:
        raise LearningTopicAttemptError(
            "[LEARNING_TOPIC_ATTEMPT_LIMIT_REACHED]",
            "该学习单元已达到最大重测次数。",
            409,
        )
```

- [ ] **Step 5: 运行 migration/服务测试并提交**

Run: `cd backend && ./.venv/bin/alembic upgrade head`

Run: `cd backend && ./.venv/bin/python -m pytest -c pyproject.toml tests/unit/test_learning_topic_attempt_service.py -q --no-cov`

Expected: PASS；相同 token 只有一条 Attempt；不同 revision 完全隔离；legacy 只在历史查询出现。

```bash
git add backend/alembic/versions/20260710_1500_093_learning_topic_attempts.py backend/src/sales_trainer/models.py backend/src/sales_trainer/services/learning_topic_attempt_service.py backend/tests/unit/test_learning_topic_attempt_service.py
git commit -m "feat: add revision-bound learning topic attempts"
```

### Task 2: 将商务礼仪迁入统一 Attempt Interface

**Files:**
- Modify: `backend/src/sales_trainer/services/business_etiquette_quiz_service.py`
- Modify: `backend/src/sales_trainer/schemas.py`
- Modify: `backend/src/sales_trainer/business_etiquette_api.py`
- Modify: `backend/tests/unit/test_business_etiquette_quiz_service.py`
- Modify: `backend/tests/integration/test_business_etiquette_quiz_api.py`

**Interfaces:**
- Consumes: `LearningTopicAttemptService`
- Preserves: existing `BusinessEtiquetteUnitQuizAttemptResponse` HTTP shape

- [ ] **Step 1: 写当前 topic revision 绑定红测**

提交商务礼仪小测后断言 canonical Attempt 的：

```python
assert attempt.topic_key == "business_etiquette"
assert attempt.topic_revision_id == str(active_topic_revision.revision_id)
assert attempt.source_revision_id == str(active_training_pack_revision.revision_id)
assert attempt.path_revision_id == str(active_path_revision.revision_id)
assert attempt.lineage_status == "bound"
```

发布新 topic revision 后，旧 Attempt 仍可通过历史列表读取，但 unit progress 为 `not_started`，attempt limit 重新计算。

Run: `cd backend && ./.venv/bin/python -m pytest -c pyproject.toml tests/unit/test_business_etiquette_quiz_service.py -q --no-cov`

Expected: FAIL because `_quiz_context` discards topic revision and writes the old table.

- [ ] **Step 2: 在 `_QuizContext` 保存 topic revision**

```python
topic, topic_revision = await NewcomerLearningTopicConfigService(
    self._db
).active_business_etiquette_topic()

return _QuizContext(
    topic_revision=topic_revision,
    training_pack_revision=training_pack_revision,
    training_pack_key=DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY,
    unit_config=unit_config,
    path_revision_id=str(path_revision.revision_id) if path_revision else None,
    path_revision_no=int(path_revision.revision_no) if path_revision else None,
    capabilities=[capability_map[key] for key in unit_config.capability_keys],
    capability_map=capability_map,
    chapter_bindings=chapter_bindings,
)
```

`_QuizContext.__init__` 增加 `topic_revision: SalesTrainerAssetRevision`，不得通过当前时间或 topic key 猜 revision。

- [ ] **Step 3: 用统一 service 开始并完成 Attempt**

在评分前调用 `begin_attempt()`，`question_snapshots`、原始 `answers_snapshot`、capability snapshot 一次写入。规则题和 AI 短答评分完成后调用：

商务礼仪 command 必须传 `allow_retake=context.unit_config.quiz_allow_retake` 和 `max_attempts=context.unit_config.quiz_max_attempts`；次数校验由 `begin_attempt()` 在 learner row lock 内完成。

```python
attempt = await self._attempts.complete_attempt(
    attempt_id=str(attempt.attempt_id),
    actor=actor,
    total_score=total_score if not has_unscored else None,
    max_score=max_score if not has_unscored else None,
    passed=passed,
    scoring_snapshot={"answers": answers_snapshot},
    capability_scores=[item.model_dump(mode="json") for item in capability_scores],
    weak_capability_keys=weak_capability_keys,
    remediation_snapshot={"recommended_chapter_orders": context.unit_config.source_chapter_orders},
)
```

请求 schema 增加必填 `client_token`；HTTP response 保持既有字段，增加向后兼容字段 `topic_revision_id/no` 和 `lineage_status`。

- [ ] **Step 4: AI 短答失败也完成失败状态**

若一个或多个短答无法评分，不回滚 Attempt：调用 `fail_attempt(failure_code="[SHORT_ANSWER_AI_SCORING_FAILED]", scoring_snapshot={"answers": answers_snapshot, "failure_stage": "short_answer_scoring"})`，API 返回原有错误码并在 `details.attempt_id` 提供可供客服定位的业务记录 id；普通 learner UI 不直接展示 id。

- [ ] **Step 5: 运行商务礼仪回归并提交**

Run: `cd backend && ./.venv/bin/python -m pytest -c pyproject.toml tests/unit/test_business_etiquette_quiz_service.py tests/integration/test_business_etiquette_quiz_api.py -q --no-cov`

Expected: PASS；旧 response 兼容；新写入只进入 canonical table；AI 失败保留 Attempt。

```bash
git add backend/src/sales_trainer/services/business_etiquette_quiz_service.py backend/src/sales_trainer/schemas.py backend/src/sales_trainer/business_etiquette_api.py backend/tests/unit/test_business_etiquette_quiz_service.py backend/tests/integration/test_business_etiquette_quiz_api.py
git commit -m "refactor: unify business etiquette attempts"
```

### Task 3: 让客户问答生成持久、幂等的 Attempt

**Files:**
- Modify: `backend/src/sales_trainer/services/customer_faq_short_answer_service.py`
- Modify: `backend/src/sales_trainer/customer_faq_api.py`
- Modify: `backend/src/sales_trainer/schemas.py`
- Modify: `backend/tests/unit/test_customer_faq_short_answer_service.py`
- Create: `backend/tests/integration/test_customer_faq_api.py`
- Modify: `web/src/lib/api/types.ts`
- Modify: `web/src/lib/api/domains/newcomer-training.ts`
- Modify: `web/src/app/(dashboard)/sales-trainer/learning-topics/customer-faq/page.tsx`
- Modify: `web/src/app/(dashboard)/sales-trainer/learning-topics/customer-faq/page.test.tsx`

**Interfaces:**
- Changes: `submit_unit_short_answer_attempt(unit_key, payload, *, actor)`
- Request adds: `client_token: str`
- Response adds: `attempt_id`, `topic_revision_id/no`, `status`, `submitted_at`

- [ ] **Step 1: 写 actor、幂等和失败保留红测**

```python
result = await service.submit_unit_short_answer_attempt(
    "faq-unit-1",
    CustomerFaqShortAnswerSubmitRequest(
        client_token="faq-attempt-token-0001",
        answers=[{"card_key": "faq-001", "answer_text": "我的回答"}],
    ),
    actor=learner,
)
assert result.attempt_id
assert result.status == "scored"
```

同 token 再调用一次，断言 scorer 调用次数仍为 1；scorer 失败时查询数据库，断言 Attempt status 为 `failed` 且保存题目、答案和 failure code。

Run: `cd backend && ./.venv/bin/python -m pytest -c pyproject.toml tests/unit/test_customer_faq_short_answer_service.py tests/integration/test_customer_faq_api.py -q --no-cov`

Expected: FAIL because service has no actor/client token/persistence.

- [ ] **Step 2: 评分前持久化快照**

```python
attempt = await self._attempts.begin_attempt(
    actor=actor,
    command=LearningTopicAttemptCreate(
        attempt_kind="customer_faq_short_answer",
        topic_key=CUSTOMER_FAQ_TOPIC_KEY,
        learning_unit_key=unit.unit_key,
        learning_unit_title=unit.title,
        client_token=payload.client_token,
        path_revision_id=str(path_revision.revision_id) if path_revision else None,
        path_revision_no=int(path_revision.revision_no) if path_revision else None,
        topic_revision_id=str(topic_revision.revision_id),
        topic_revision_no=int(topic_revision.revision_no),
        source_revision_id=None,
        source_revision_no=None,
        capability_snapshot={"capability_keys": list(unit.capability_keys)},
        question_snapshots=[_faq_card_snapshot(cards_by_key[item.card_key]) for item in payload.answers],
        answers_snapshot=[item.model_dump(mode="json") for item in payload.answers],
        allow_retake=unit.quiz_allow_retake,
        max_attempts=unit.quiz_max_attempts,
    ),
)
```

`active_customer_faq_topic()` 返回的 revision 必须直接写入；不能在评分结束后重新读取 active revision。

在开始 Attempt 前用 `SalesTrainerAssetRevisionService.active_revision(resource_type=NEWCOMER_PATH_RESOURCE_TYPE, logical_id=NEWCOMER_PATH_LOGICAL_ID)` 读取一次 active path revision。次数限制参数传入 command，由 `begin_attempt()` 在 learner row lock 内调用 `enforce_attempt_limits()`，避免并发请求同时越过上限。

- [ ] **Step 3: 保存评分 contract snapshot**

扩展 `ShortAnswerScoreOutcome`：

```python
@dataclass(frozen=True)
class ShortAnswerScoreOutcome:
    score: float
    passed: bool
    feedback: str
    reason: str | None
    raw_response: dict[str, Any] | None
    scoring_source: str = "ai_llm"
    scoring_provider: str | None = None
    scoring_model: str | None = None
    scoring_latency_ms: int | None = None
    model_config_id: str | None = None
    prompt_contract_hash: str | None = None
    prompt_source: Literal["configured", "default"] = "default"
```

hash 使用 `sha256` 计算 prompt template、system message、model_config_id 和固定输出 schema version `short_answer_score_v1` 的规范 JSON，不包含用户答案。Attempt 只保存 hash、`prompt_source`、provider、model、latency、score、feedback、reason，不保存完整 Prompt 或 raw provider response；使用内置模板时必须明确记录 `prompt_source="default"`，不得伪装成已治理 Prompt。

- [ ] **Step 4: 完成或失败同一 Attempt**

全部评分成功调用 `complete_attempt()`；任一评分失败调用 `fail_attempt()` 并 commit，然后抛出：

```python
raise CustomerFaqShortAnswerServiceError(
    "[CUSTOMER_FAQ_SHORT_ANSWER_SCORING_FAILED]",
    "客户常见问答简答评分暂不可用，请稍后重试。",
    503,
    details={"attempt_id": str(attempt.attempt_id)},
)
```

总分通过线使用归一化后的同一个值，避免 unit 未配置阈值时返回 `passed=None`：

```python
effective_pass_threshold = float(
    unit.quiz_pass_threshold
    if unit.quiz_pass_threshold is not None
    else DEFAULT_SHORT_ANSWER_PASS_THRESHOLD
)
passed = total_score >= effective_pass_threshold
```

API `_api_error` 增加 `details`，但 learner 页面只展示用户文案和重试操作。

- [ ] **Step 5: 前端稳定复用 client token**

```typescript
const [attemptToken, setAttemptToken] = useState(() => crypto.randomUUID());
await api.newcomerTraining.submitCustomerFaqShortAnswerAttempt(unitKey, {
    client_token: attemptToken,
    answers,
});
setAttemptToken(crypto.randomUUID());
```

网络错误保留 token；用户修改任何答案后生成新 token。提交中禁用重复点击，成功后展示 Attempt 结果并从 Journey 重新取进度。

- [ ] **Step 6: 运行端到端定向测试并提交**

Run: `cd backend && ./.venv/bin/python -m pytest -c pyproject.toml tests/unit/test_customer_faq_short_answer_service.py tests/integration/test_customer_faq_api.py -q --no-cov`

Run: `cd web && npx vitest run 'src/app/(dashboard)/sales-trainer/learning-topics/customer-faq/page.test.tsx' src/lib/api/newcomer-training.test.ts && npx tsc --noEmit`

Expected: PASS；重复 token 不重复评分；刷新后结果仍存在；失败 Attempt 可由管理端查询。

```bash
git add backend/src/sales_trainer/services/customer_faq_short_answer_service.py backend/src/sales_trainer/customer_faq_api.py backend/src/sales_trainer/schemas.py backend/tests/unit/test_customer_faq_short_answer_service.py backend/tests/integration/test_customer_faq_api.py web/src/lib/api/types.ts web/src/lib/api/domains/newcomer-training.ts 'web/src/app/(dashboard)/sales-trainer/learning-topics/customer-faq/page.tsx' 'web/src/app/(dashboard)/sales-trainer/learning-topics/customer-faq/page.test.tsx'
git commit -m "feat: persist customer faq attempts"
```

### Task 4: 统一 Journey、Learning Topic 和 Readiness 证据投影

**Files:**
- Modify: `backend/src/sales_trainer/services/learning_topic_projection_service.py`
- Modify: `backend/src/sales_trainer/services/readiness_dossier_service.py`
- Modify: `backend/tests/unit/test_sales_trainer_training_journey_service.py`
- Modify: `backend/tests/unit/test_sales_trainer_readiness_dossier_service.py`
- Modify: `backend/tests/unit/test_learning_topic_attempt_service.py`

**Interfaces:**
- Consumes: `LearningTopicAttemptService.latest_by_unit`
- Produces record type: `learning_topic_attempt`
- Produces snapshot ref: `learning_topic_attempt_snapshot`

- [ ] **Step 1: 写 revision 污染红测**

创建 revision 1 passed Attempt，发布 revision 2 后请求 Journey/Dossier：

```python
assert journey["learning_topics"][0]["units"][0]["status"] == "not_started"
assert not any(
    item["source_record_id"] == legacy_attempt_id
    for item in dossier["evidence"]
    if item.get("counts_for_current_readiness") is True
)
```

再提交 revision 2 Attempt，断言 Journey 变为 passed，Dossier evidence 的 `topic_revision_id` 等于 revision 2。

Run: `cd backend && ./.venv/bin/python -m pytest -c pyproject.toml tests/unit/test_sales_trainer_training_journey_service.py tests/unit/test_sales_trainer_readiness_dossier_service.py -q --no-cov`

Expected: FAIL because projection currently reads old business table without topic revision filter.

- [ ] **Step 2: LearningTopicProjection 只读 active revision Attempt**

```python
attempts = await self._attempts.latest_by_unit(
    user_id=user_id,
    topic_keys=[topic.topic_key for topic in topics],
    topic_revision_id=str(revision.revision_id),
    unit_keys=[unit.unit_key for topic in topics for unit in topic.learning_units if unit.enabled],
)
```

key 使用 `(topic_key, learning_unit_key)`，避免不同专题复用 unit key 时串数据。

- [ ] **Step 3: Journey sidecar 和 Dossier 使用 canonical Attempt payload**

```python
latest_attempt = None if attempt is None else {
    "attempt_id": str(attempt.attempt_id),
    "record_type": "learning_topic_attempt",
    "status": str(attempt.status),
    "score": float(attempt.total_score) if attempt.total_score is not None else None,
    "max_score": float(attempt.max_score) if attempt.max_score is not None else None,
    "passed": attempt.passed,
    "submitted_at": attempt.submitted_at,
    "completed_at": attempt.completed_at,
    "path_revision_id": attempt.path_revision_id,
    "path_revision_no": attempt.path_revision_no,
    "topic_revision_id": attempt.topic_revision_id,
    "topic_revision_no": attempt.topic_revision_no,
    "snapshot_ref": {
        "snapshot_type": "learning_topic_attempt_snapshot",
        "legacy_snapshot_only": attempt.lineage_status != "bound",
    },
}
```

把 `latest_attempt` 放入 Journey `learning_topics[].units[]`，Dossier 从该字段生成 evidence。Dossier evidence 增加明确 `topic_revision_id/no`、`scoring_snapshot_ref` 和 `counts_for_current_readiness`；只有 `lineage_status == "bound"` 且 topic revision 等于 Journey source revision 时该字段为 true，legacy_unbound 永远为 false。

- [ ] **Step 4: 删除错误的当前 revision 冒充逻辑**

删除从当前 topic source 生成旧 Attempt `snapshot_ref` 的代码；快照引用必须来自 Attempt 自身。移除 `SalesTrainerBusinessEtiquetteQuizAttempt` 在 LearningTopicProjection 的直接查询；TrainingJourney 继续通过 LearningTopicProjection 获取 sidecar，不新增第二套 Attempt 查询。

- [ ] **Step 5: 运行 Journey/Dossier 回归并提交**

Run: `cd backend && ./.venv/bin/python -m pytest -c pyproject.toml tests/unit/test_learning_topic_attempt_service.py tests/unit/test_sales_trainer_training_journey_service.py tests/unit/test_sales_trainer_readiness_dossier_service.py -q --no-cov`

Expected: PASS；旧 revision 不污染当前进度；新 Attempt 可进入 Journey 和 Dossier。

```bash
git add backend/src/sales_trainer/services/learning_topic_projection_service.py backend/src/sales_trainer/services/readiness_dossier_service.py backend/tests/unit/test_learning_topic_attempt_service.py backend/tests/unit/test_sales_trainer_training_journey_service.py backend/tests/unit/test_sales_trainer_readiness_dossier_service.py
git commit -m "fix: project trusted learning topic evidence"
```

### Task 5: 契约、发布门禁和回滚验证

**Files:**
- Modify: `docs/api-contract/sales-trainer.md`
- Modify: `docs/adr/2026-07-08-newcomer-learning-topics-independent-governance.md`
- Modify: `.trellis/spec/backend/sales-trainer-learning-topic-governance.md`
- Modify: `scripts/critical-quality-gate.sh`

- [ ] **Step 1: 更新证据契约**

文档明确 Attempt 的 revision lineage、client token、失败保留、legacy_unbound、current progress 过滤和 Dossier 使用规则；FAQ response 补充 `attempt_id/status/topic_revision`。

- [ ] **Step 2: 把所有相关测试加入 critical gate**

Backend list 至少加入：

```bash
tests/unit/test_learning_topic_attempt_service.py
tests/unit/test_business_etiquette_quiz_service.py
tests/unit/test_customer_faq_short_answer_service.py
tests/integration/test_business_etiquette_quiz_api.py
tests/integration/test_customer_faq_api.py
tests/unit/test_sales_trainer_readiness_dossier_service.py
```

Frontend list 加入 FAQ learner page；Playwright route audit 增加“提交后刷新仍显示结果”和“新 revision 不继承旧通过状态”。

- [ ] **Step 3: 运行代码质量和定向测试**

Run: `cd backend && ./.venv/bin/ruff check src/sales_trainer tests/unit/test_learning_topic_attempt_service.py tests/unit/test_business_etiquette_quiz_service.py tests/unit/test_customer_faq_short_answer_service.py tests/integration/test_business_etiquette_quiz_api.py tests/integration/test_customer_faq_api.py`

Run: `cd backend && ./.venv/bin/python -m pytest -c pyproject.toml tests/unit/test_learning_topic_attempt_service.py tests/unit/test_business_etiquette_quiz_service.py tests/unit/test_customer_faq_short_answer_service.py tests/unit/test_sales_trainer_training_journey_service.py tests/unit/test_sales_trainer_readiness_dossier_service.py tests/integration/test_business_etiquette_quiz_api.py tests/integration/test_customer_faq_api.py -q --no-cov`

Run: `cd web && npx eslint 'src/app/(dashboard)/sales-trainer/learning-topics/customer-faq/page.tsx' src/lib/api/domains/newcomer-training.ts && npx tsc --noEmit`

Expected: 所有命令 exit 0。

- [ ] **Step 4: 验证 migration downgrade/upgrade 和数据保留**

在测试数据库插入一条旧商务礼仪 Attempt，且不创建 canonical-only FAQ Attempt，再执行：

Run: `cd backend && ./.venv/bin/alembic upgrade head && ./.venv/bin/alembic downgrade 20260710_1200_092 && ./.venv/bin/alembic upgrade head`

Expected: 旧表记录始终存在；重新 upgrade 后 canonical 表只出现一条相同 attempt_id 的 backfill，不重复。

生产或任何已产生 canonical-only Attempt 的环境只回滚应用并保留 additive 新表，不执行 downgrade；这是 FAQ 证据不丢失的正式回滚策略。

- [ ] **Step 5: 提交治理切片**

```bash
git add docs/api-contract/sales-trainer.md docs/adr/2026-07-08-newcomer-learning-topics-independent-governance.md .trellis/spec/backend/sales-trainer-learning-topic-governance.md scripts/critical-quality-gate.sh
git commit -m "docs: govern learning topic attempt evidence"
```
