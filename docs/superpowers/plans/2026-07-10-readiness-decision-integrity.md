# Readiness Decision Integrity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让“确认达标、要求重练、人工跟进”成为权限独立、幂等、并发安全、可审计的业务决策。

**Architecture:** 新建深 Module `ReadinessReviewActionService` 作为唯一写 Interface；业务状态写入专用表，OperationLog 通过 Adapter 同事务留痕。Dossier 双读新表与历史日志保证兼容，但所有新状态只写新表。

**Tech Stack:** FastAPI、Pydantic v2、SQLAlchemy AsyncSession、Alembic、React/TypeScript、Pytest、Vitest。

## Global Constraints

- `view_records` 只允许读取，不能隐式授予复核写权限。
- `review_readiness` 只授予平台管理员和培训负责人；培训负责人继续受部门对象范围约束。
- 每个写请求必须携带 `idempotency_key` 和 `expected_latest_review_action_id`。
- 同一 `actor_id + idempotency_key` 只能产生一条业务决策。
- `expected_latest_review_action_id` 与当前最新动作不一致时返回 409，不覆盖并发决定。
- 专用 review action 表采用 append-only history；MVP 不提供 update、delete、撤销或委派写入口。
- OperationLog 仍记录 actor、角色、requestId、IP、User-Agent，但不再是业务状态唯一存储。
- 不删除历史 OperationLog；Dossier 在兼容期合并历史日志和新表记录。

---

### Task 1: 冻结独立复核权限契约

**Files:**
- Modify: `backend/src/sales_trainer/permissions.py`
- Modify: `backend/src/sales_trainer/api.py`
- Modify: `backend/tests/unit/test_newcomer_training_path_permissions.py`
- Modify: `web/src/lib/api/types.ts`
- Modify: `web/src/lib/sales-trainer/routes.ts`
- Modify: `web/src/lib/sales-trainer/routes.test.ts`
- Modify: `web/src/components/layout/admin-sidebar.test.tsx`
- Modify: `web/src/components/admin/sales-trainer/module-nav.test.tsx`
- Modify: `web/src/lib/api/client-domains.test.ts`

**Interfaces:**
- Produces: `can_review_sales_trainer_readiness(user: User) -> bool`
- Produces: `_require_readiness_reviewer(user: User) -> JSONResponse | None`
- Produces: admin capability key `review_readiness`

- [ ] **Step 1: 写角色矩阵失败测试**

```python
def test_readiness_review_permission_is_not_record_view_permission() -> None:
    assert can_review_sales_trainer_readiness(_user("admin"))
    assert can_review_sales_trainer_readiness(_user("support"))
    assert not can_review_sales_trainer_readiness(_user("operations"))
    assert not can_review_sales_trainer_readiness(_user("content_admin"))
    assert can_view_sales_trainer_records(_user("operations"))
```

Run: `cd backend && ./.venv/bin/python -m pytest -c pyproject.toml tests/unit/test_newcomer_training_path_permissions.py -q --no-cov`

Expected: FAIL because `can_review_sales_trainer_readiness` and `review_readiness` do not exist.

- [ ] **Step 2: 实现最小权限函数和路由 guard**

```python
def can_review_sales_trainer_readiness(user: User) -> bool:
    return is_sales_trainer_admin(user) or is_sales_trainer_manager(user)

def _require_readiness_reviewer(user: User) -> JSONResponse | None:
    if can_review_sales_trainer_readiness(user):
        return None
    return _api_error(
        "[READINESS_REVIEW_ROLE_REQUIRED]",
        status_code=403,
        message="当前账号无权执行训练达标复核。",
    )
```

把 `admin_create_readiness_review_action` 的 `_require_records_viewer` 改为 `_require_readiness_reviewer`；Dossier GET 和 Workbench GET 保持 `_require_records_viewer`。

- [ ] **Step 3: 同步能力投影和前端类型**

```typescript
export type SalesTrainerAdminCapabilityKey =
    | "admin_full_access"
    | "manage_content"
    | "manage_questions"
    | "manage_modules"
    | "manage_prompts"
    | "review_readiness"
    | "view_records"
    | "view_global_records"
    | "retry_jobs"
    | "regrade_history"
    | "view_logs"
    | "view_settings";
```

Readiness 页面仍由 `view_records` 控制可见性；复核表单根据 `routeAccess.capabilities?.capabilities.review_readiness` 显示，ops 看到只读档案。

`SalesTrainerAdminCapabilities["capabilities"]` 是完整 `Record`；同步给 `routes.test.ts`、`admin-sidebar.test.tsx`、`module-nav.test.tsx` 和 `client-domains.test.ts` 的强类型 fixture 增加 `review_readiness`，避免 `tsc` 因缺字段失败。页面中未声明为 `SalesTrainerAdminCapabilities` 的局部 mock 不做机械改写。

- [ ] **Step 4: 运行权限和路由测试**

Run: `cd backend && ./.venv/bin/python -m pytest -c pyproject.toml tests/unit/test_newcomer_training_path_permissions.py -q --no-cov`

Run: `cd web && npx vitest run src/lib/sales-trainer/routes.test.ts src/components/layout/admin-sidebar.test.tsx src/components/admin/sales-trainer/module-nav.test.tsx src/lib/api/client-domains.test.ts`

Expected: 两条命令均 PASS，且 ops 的 `view_records=true`、`review_readiness=false`。

- [ ] **Step 5: 提交权限切片**

```bash
git add backend/src/sales_trainer/permissions.py backend/src/sales_trainer/api.py backend/tests/unit/test_newcomer_training_path_permissions.py web/src/lib/api/types.ts web/src/lib/sales-trainer/routes.ts web/src/lib/sales-trainer/routes.test.ts web/src/components/layout/admin-sidebar.test.tsx web/src/components/admin/sales-trainer/module-nav.test.tsx web/src/lib/api/client-domains.test.ts
git commit -m "fix: separate readiness review permission"
```

### Task 2: 建立专用复核决策存储

**Files:**
- Create: `backend/alembic/versions/20260710_1200_092_readiness_review_actions.py`
- Modify: `backend/src/sales_trainer/models.py`
- Create: `backend/src/sales_trainer/services/readiness_review_action_service.py`
- Create: `backend/tests/unit/test_readiness_review_action_service.py`

**Interfaces:**
- Produces: `SalesTrainerReadinessReviewAction`
- Produces: `ReadinessReviewActionService.create`
- Produces: `ReadinessReviewActionService.list_for_learner`

- [ ] **Step 1: 写存储、幂等和并发失败测试**

```python
first = await service.create(
    learner_id=str(learner.user_id),
    actor=manager,
    decision="approve",
    reason="证据完整。",
    capability_keys=["expression_clarity"],
    source_evidence_ids=["audio_submission:one"],
    idempotency_key="review-request-1",
    expected_latest_review_action_id=None,
)
replayed = await service.create(
    learner_id=str(learner.user_id),
    actor=manager,
    decision="approve",
    reason="证据完整。",
    capability_keys=["expression_clarity"],
    source_evidence_ids=["audio_submission:one"],
    idempotency_key="review-request-1",
    expected_latest_review_action_id=None,
)
assert replayed.action_id == first.action_id
```

再增加一个测试：已有最新 action 后，以错误的 `expected_latest_review_action_id` 提交，断言 `[READINESS_REVIEW_VERSION_CONFLICT]`、HTTP 409。

增加兼容基线测试：先写入一条旧 `operation_log` review action，Dossier 返回其 `log_id` 作为 `latest_review_action.action_id`；新请求携带该 ID 时允许创建第一条专用 action，携带 `null` 时返回版本冲突。

Run: `cd backend && ./.venv/bin/python -m pytest -c pyproject.toml tests/unit/test_readiness_review_action_service.py -q --no-cov`

Expected: FAIL because model/table/service do not exist.

- [ ] **Step 2: 创建 migration 和 ORM model**

先运行 `cd backend && ./.venv/bin/alembic heads` 并检查 `alembic/versions/`。只有当前 head 仍为 `20260707_1200_091` 时使用文件名/revision `20260710_1200_092`；如果并行任务已占用 092，先按实际 head 顺延 revision 和 `down_revision`，再同步本计划、PRD 和后续依赖计划中的编号。

```python
class SalesTrainerReadinessReviewAction(Base):
    __tablename__ = "sales_trainer_readiness_review_actions"

    action_id = Column(String(36), primary_key=True, default=_uuid)
    learner_id = Column(String(36), ForeignKey("users.user_id"), nullable=False, index=True)
    actor_id = Column(String(36), ForeignKey("users.user_id"), nullable=False, index=True)
    actor_role = Column(String(50), nullable=False)
    decision = Column(String(40), nullable=False)
    reason = Column(Text, nullable=False)
    capability_keys = Column(JSON, nullable=False, default=list)
    source_evidence_ids = Column(JSON, nullable=False, default=list)
    retraining_task = Column(JSON, nullable=True)
    idempotency_key = Column(String(100), nullable=False)
    request_hash = Column(String(64), nullable=False)
    expected_previous_action_id = Column(String(36), nullable=True)
    audit_log_id = Column(String(36), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)

    __table_args__ = (
        UniqueConstraint("actor_id", "idempotency_key", name="uq_readiness_review_actor_idempotency"),
        CheckConstraint(
            "decision IN ('approve', 'require_retraining', 'mark_manual_follow_up')",
            name="ck_readiness_review_decision",
        ),
        Index("idx_readiness_review_learner_created", "learner_id", "created_at"),
    )
```

Migration 必须可重复检查表是否存在；downgrade 只删除新表，不接触历史 OperationLog。

- [ ] **Step 3: 实现串行化写 Interface**

```python
@dataclass(frozen=True, slots=True)
class ReadinessAuditContext:
    request_id: str | None
    ip_address: str | None
    user_agent: str | None

ReadinessDecision = Literal["approve", "require_retraining", "mark_manual_follow_up"]

def _review_request_hash(
    *, learner_id: str, decision: ReadinessDecision, reason: str,
    capability_keys: list[str], source_evidence_ids: list[str],
) -> str:
    canonical = json.dumps(
        {
            "learner_id": learner_id,
            "decision": decision,
            "reason": reason.strip(),
            "capability_keys": sorted(capability_keys),
            "source_evidence_ids": sorted(source_evidence_ids),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

async def create(self, *, learner_id: str, actor: User, team_department: str | None,
                 decision: ReadinessDecision,
                 reason: str, capability_keys: list[str], source_evidence_ids: list[str],
                 idempotency_key: str, expected_latest_review_action_id: str | None,
                 audit_context: ReadinessAuditContext) -> SalesTrainerReadinessReviewAction:
    if not can_review_sales_trainer_readiness(actor):
        raise ReadinessReviewActionError(
            "[READINESS_REVIEW_ROLE_REQUIRED]",
            "当前账号无权执行训练达标复核。",
            403,
        )
    learner = await self._db.scalar(
        select(User).where(User.user_id == learner_id).with_for_update()
    )
    if learner is None or (
        team_department is not None and str(learner.department or "") != team_department
    ):
        raise ReadinessReviewActionError(
            "[TRAINING_RECORD_NOT_FOUND]",
            "学员训练记录不存在。",
            404,
        )
    request_hash = _review_request_hash(
        learner_id=learner_id,
        decision=decision,
        reason=reason,
        capability_keys=capability_keys,
        source_evidence_ids=source_evidence_ids,
    )
    replay = await self._find_idempotent(actor_id=str(actor.user_id), key=idempotency_key)
    if replay is not None:
        if str(replay.request_hash) != request_hash:
            raise ReadinessReviewActionError(
                "[READINESS_IDEMPOTENCY_KEY_REUSED]",
                "该提交标识已用于另一项复核内容，请刷新后重新提交。",
                409,
            )
        return replay
    latest_id = await self._latest_version_id_for_learner(learner_id)
    if latest_id != expected_latest_review_action_id:
        raise ReadinessReviewActionError(
            "[READINESS_REVIEW_VERSION_CONFLICT]",
            "档案已被其他复核动作更新，请刷新后重试。",
            409,
            details={"latest_review_action_id": latest_id},
        )
    action = SalesTrainerReadinessReviewAction(
        learner_id=learner_id,
        actor_id=str(actor.user_id),
        actor_role=str(actor.role),
        decision=decision,
        reason=reason.strip(),
        capability_keys=capability_keys,
        source_evidence_ids=source_evidence_ids,
        retraining_task=None,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        expected_previous_action_id=latest_id,
    )
    self._db.add(action)
    await self._db.flush()
    if decision == "require_retraining":
        action.retraining_task = {
            "task_id": f"retraining:{action.action_id}",
            "status": "pending",
            "source": "readiness_review_action",
            "capability_keys": capability_keys,
            "source_evidence_ids": source_evidence_ids,
            "target_learner_id": learner_id,
        }
    log = await self._logs.record(
        actor=actor,
        action=REVIEW_ACTION_CREATED,
        target_type=READINESS_DOSSIER_TARGET_TYPE,
        target_id=learner_id,
        request_id=audit_context.request_id,
        ip_address=audit_context.ip_address,
        user_agent=audit_context.user_agent,
        metadata={
            "action_id": str(action.action_id),
            "decision": decision,
            "reason": reason.strip(),
            "capability_keys": capability_keys,
            "source_evidence_ids": source_evidence_ids,
            "retraining_task": action.retraining_task,
            "state_storage": "readiness_review_action",
        },
    )
    action.audit_log_id = str(log.log_id)
    await self._db.commit()
    await self._db.refresh(action)
    return action

async def _latest_version_id_for_learner(self, learner_id: str) -> str | None:
    stored = await self._latest_for_learner(learner_id)
    legacy_logs, _ = await self._logs.list_logs(
        target_type=READINESS_DOSSIER_TARGET_TYPE,
        target_id=learner_id,
        limit=200,
    )
    candidates: list[tuple[datetime, str]] = []
    if stored is not None:
        candidates.append((stored.created_at, str(stored.action_id)))
    for log in legacy_logs:
        metadata = log.metadata_json if isinstance(log.metadata_json, dict) else {}
        if log.action != REVIEW_ACTION_CREATED:
            continue
        if metadata.get("state_storage") == "readiness_review_action":
            continue
        candidates.append((log.created_at, str(log.log_id)))
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]
```

幂等命中必须在版本冲突判断前返回旧结果；业务决策和审计日志必须使用同一个 transaction。并发版本基线必须合并专用 action 和 legacy OperationLog，且排除新 action 对应的审计镜像，避免上线后的第一次写入被错误阻断。

- [ ] **Step 4: 运行 migration 和服务测试**

Run: `cd backend && ./.venv/bin/alembic upgrade head`

Run: `cd backend && ./.venv/bin/python -m pytest -c pyproject.toml tests/unit/test_readiness_review_action_service.py -q --no-cov`

Expected: migration exit 0；重复 key 返回相同 action；陈旧 expected id 返回 409；数据库只有一条 action 和一条对应审计日志。

- [ ] **Step 5: 提交持久化切片**

```bash
git add backend/alembic/versions/20260710_1200_092_readiness_review_actions.py backend/src/sales_trainer/models.py backend/src/sales_trainer/services/readiness_review_action_service.py backend/tests/unit/test_readiness_review_action_service.py
git commit -m "feat: persist readiness review decisions safely"
```

### Task 3: 让 Dossier 使用新决策 Module 并兼容历史日志

**Files:**
- Modify: `backend/src/sales_trainer/services/readiness_dossier_service.py`
- Modify: `backend/src/sales_trainer/schemas.py`
- Modify: `backend/tests/unit/test_sales_trainer_readiness_dossier_service.py`

**Interfaces:**
- Consumes: `ReadinessReviewActionService.create` and `.list_for_learner`
- Produces: `ReadinessDossierReviewAction.state_storage` values `readiness_review_action | operation_log`

- [ ] **Step 1: 写双读与新写失败测试**

测试先插入一条旧 OperationLog，再通过新 service 创建一条 action；断言 Dossier 返回两条、按 `created_at` 倒序、新 action 为 latest，且新 action 的 `state_storage == "readiness_review_action"`。

Run: `cd backend && ./.venv/bin/python -m pytest -c pyproject.toml tests/unit/test_sales_trainer_readiness_dossier_service.py -q --no-cov`

Expected: FAIL because Dossier only reads OperationLog.

- [ ] **Step 2: 将 create_review_action 改成编排而不是存储**

```python
audit_context = ReadinessAuditContext(
    request_id=request_id,
    ip_address=ip_address,
    user_agent=user_agent,
)
try:
    action = await self._review_action_service.create(
        learner_id=learner_id,
        actor=actor,
        team_department=team_department,
        decision=decision,
        reason=reason.strip(),
        capability_keys=normalized_capabilities,
        source_evidence_ids=evidence_ids,
        idempotency_key=idempotency_key,
        expected_latest_review_action_id=expected_latest_review_action_id,
        audit_context=audit_context,
    )
except ReadinessReviewActionError as exc:
    raise ReadinessDossierError(
        exc.code,
        exc.message,
        exc.status_code,
        details=exc.details,
    ) from exc
return self._stored_review_action_payload(action)
```

保留 Dossier 的 evidence/capability/approve 前置校验；删除生成时间戳 task id 和直接 `_logs.record()` 的写逻辑。重练 task id 改为 `retraining:{action_id}`。Dossier 校验、learner row lock、action 写入和 OperationLog flush 都是数据库 IO；该 transaction 内不得加入通知、HTTP 或其他慢速外部 IO。

- [ ] **Step 3: 实现有限兼容双读**

```python
stored = await self._review_action_service.list_for_learner(learner_id, limit=200)
legacy_logs, _ = await self._logs.list_logs(
    target_type=READINESS_DOSSIER_TARGET_TYPE,
    target_id=learner_id,
    limit=200,
)
items = [self._stored_review_action_payload(item) for item in stored]
items.extend(self._legacy_review_action_payload(log) for log in legacy_logs if log.action == REVIEW_ACTION_CREATED)
return sorted(items, key=lambda item: _datetime_or_none(item.get("created_at")) or datetime.min.replace(tzinfo=UTC), reverse=True)
```

以 `audit_log_id` 去重，避免新 action 对应的审计日志被双重展示。

- [ ] **Step 4: 运行 Dossier 回归测试**

Run: `cd backend && ./.venv/bin/python -m pytest -c pyproject.toml tests/unit/test_sales_trainer_readiness_dossier_service.py tests/unit/test_readiness_review_action_service.py -q --no-cov`

Expected: PASS；历史动作可见，新动作状态来源为专用表，realtime gate 仍只在 approve 后开放。

- [ ] **Step 5: 提交 Dossier 切片**

```bash
git add backend/src/sales_trainer/services/readiness_dossier_service.py backend/src/sales_trainer/schemas.py backend/tests/unit/test_sales_trainer_readiness_dossier_service.py
git commit -m "refactor: make readiness decisions canonical"
```

### Task 4: 前端提交幂等、版本前置和确认交互

**Files:**
- Modify: `web/src/lib/api/types.ts`
- Modify: `web/src/lib/api/domains/sales-trainer.ts`
- Modify: `web/src/app/admin/sales-trainer/readiness/[learnerId]/page.tsx`
- Modify: `web/src/app/admin/sales-trainer/readiness/[learnerId]/page.test.tsx`
- Modify: `backend/src/sales_trainer/schemas.py`
- Modify: `backend/src/sales_trainer/api.py`
- Create: `backend/tests/integration/test_sales_trainer_readiness_api.py`
- Modify: `backend/tests/integration/test_sales_trainer_api.py`
- Modify: `web/src/lib/api/sales-trainer.test.ts`

**Interfaces:**
- Produces request fields: `idempotency_key: string`, `expected_latest_review_action_id: string | null`
- Produces conflict code: `[READINESS_REVIEW_VERSION_CONFLICT]`

- [ ] **Step 1: 写 API 和页面失败测试**

```typescript
expect(createReadinessReviewActionMock).toHaveBeenCalledWith("learner-1", {
    decision: "require_retraining",
    reason: "表达结构仍需重练。",
    capability_keys: ["expression_clarity"],
    source_evidence_ids: ["audio_submission:submission-1"],
    idempotency_key: expect.any(String),
    expected_latest_review_action_id: dossier.latest_review_action?.action_id ?? null,
});
```

页面测试还要断言第一次点击只打开确认区，第二次明确确认才发送请求；ops 只读时表单不存在。

更新现有 `test_sales_trainer_api.py` 中两处 review-action POST，为请求补齐 `idempotency_key` 和显式 `expected_latest_review_action_id: null`；普通 learner 的预期错误改为 `[READINESS_REVIEW_ROLE_REQUIRED]`。在 `web/src/lib/api/sales-trainer.test.ts` 增加 domain 请求测试，锁定两个字段原样进入 JSON body。

Run: `cd web && npx vitest run 'src/app/admin/sales-trainer/readiness/[learnerId]/page.test.tsx'`

Expected: FAIL because request fields and confirmation do not exist.

- [ ] **Step 2: 扩展请求 schema 并透传到业务 Module**

```python
class ReadinessDossierReviewActionCreate(BaseModel):
    decision: ReadinessReviewDecision
    reason: str = Field(..., min_length=1, max_length=1000)
    capability_keys: list[str] = Field(default_factory=list, max_length=20)
    source_evidence_ids: list[str] = Field(default_factory=list, max_length=50)
    idempotency_key: str = Field(..., min_length=16, max_length=100)
    expected_latest_review_action_id: str | None = Field(..., min_length=1, max_length=36)
```

API 将两个字段传给 `ReadinessDossierService.create_review_action`。`expected_latest_review_action_id` 的 JSON key 必填，但首个决定允许值为 `null`；缺少任一前置字段由 Pydantic 返回 422，不生成业务记录。

- [ ] **Step 3: 实现一次提交一个稳定 token**

```typescript
const [pendingIdempotencyKey, setPendingIdempotencyKey] = useState<string | null>(null);
const idempotencyKey = pendingIdempotencyKey ?? crypto.randomUUID();
setPendingIdempotencyKey(idempotencyKey);
await api.admin.salesTrainer.createReadinessReviewAction(learnerId, {
    decision,
    reason: trimmedReason,
    capability_keys: selectedCapabilityKeys,
    source_evidence_ids: selectedEvidenceIds,
    idempotency_key: idempotencyKey,
    expected_latest_review_action_id: dossier.latest_review_action?.action_id ?? null,
});
setPendingIdempotencyKey(null);
```

网络失败保留 token 供“重试”复用；用户修改 decision/reason/capability/evidence 时清空 token。409 时提示“档案已更新”，刷新 Dossier，不自动重放。

- [ ] **Step 4: 添加明确确认区**

确认区必须展示新人姓名、决定、原因、能力项数量和证据数量；approve 使用“确认新人达标并开放下一阶段”，require_retraining 使用“确认下发重练”，不得使用通用“确定”。

- [ ] **Step 5: 运行 API、页面、类型检查**

Run: `cd backend && ./.venv/bin/python -m pytest -c pyproject.toml tests/integration/test_sales_trainer_readiness_api.py tests/integration/test_sales_trainer_api.py tests/unit/test_sales_trainer_readiness_dossier_service.py -q --no-cov`

Run: `cd web && npx vitest run 'src/app/admin/sales-trainer/readiness/[learnerId]/page.test.tsx' src/lib/api/sales-trainer.test.ts src/lib/sales-trainer/routes.test.ts && npx tsc --noEmit`

Expected: 全部 PASS；无复核权限的账号不能看到或调用写动作；重复请求只产生一个 action。

- [ ] **Step 6: 提交端到端切片**

```bash
git add backend/src/sales_trainer/schemas.py backend/src/sales_trainer/api.py backend/tests/integration/test_sales_trainer_readiness_api.py backend/tests/integration/test_sales_trainer_api.py web/src/lib/api/types.ts web/src/lib/api/domains/sales-trainer.ts web/src/lib/api/sales-trainer.test.ts 'web/src/app/admin/sales-trainer/readiness/[learnerId]/page.tsx' 'web/src/app/admin/sales-trainer/readiness/[learnerId]/page.test.tsx'
git commit -m "fix: make readiness review submissions safe"
```

### Task 5: 契约、门禁和回滚验证

**Files:**
- Modify: `docs/api-contract/sales-trainer.md`
- Modify: `docs/adr/2026-06-27-newcomer-training-closed-loop.md`
- Modify: `scripts/critical-quality-gate.sh`

- [ ] **Step 1: 更新 API 契约**

记录 `review_readiness`、必填幂等键、expected latest id、409 conflict、双读兼容和 ops 只读行为；明确这是协调发布的内部契约变更。

- [ ] **Step 2: 把新测试加入 release gate**

在 backend test list 中加入：

```bash
tests/unit/test_readiness_review_action_service.py
tests/unit/test_sales_trainer_readiness_dossier_service.py
tests/integration/test_sales_trainer_readiness_api.py
tests/unit/test_newcomer_training_path_permissions.py
```

在 frontend test list 中加入 readiness detail page 和 routes tests。

- [ ] **Step 3: 运行完整相关验证**

Run: `cd backend && ./.venv/bin/ruff check src/sales_trainer tests/unit/test_readiness_review_action_service.py tests/unit/test_sales_trainer_readiness_dossier_service.py tests/integration/test_sales_trainer_readiness_api.py`

Run: `cd backend && ./.venv/bin/python -m pytest -c pyproject.toml tests/unit/test_readiness_review_action_service.py tests/unit/test_sales_trainer_readiness_dossier_service.py tests/unit/test_newcomer_training_path_permissions.py tests/integration/test_sales_trainer_readiness_api.py -q --no-cov`

Run: `cd web && npx eslint 'src/app/admin/sales-trainer/readiness/[learnerId]/page.tsx' src/lib/sales-trainer/routes.ts && npx tsc --noEmit`

Expected: 所有命令 exit 0。

- [ ] **Step 4: 验证 downgrade**

Run: `cd backend && ./.venv/bin/alembic downgrade 20260707_1200_091 && ./.venv/bin/alembic upgrade head`

Expected: downgrade 只删除 readiness action 新表；重新 upgrade 成功；历史 OperationLog 未丢失。

- [ ] **Step 5: 提交治理切片**

```bash
git add docs/api-contract/sales-trainer.md docs/adr/2026-06-27-newcomer-training-closed-loop.md scripts/critical-quality-gate.sh
git commit -m "docs: govern readiness review decisions"
```
