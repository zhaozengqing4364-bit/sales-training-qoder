# Newcomer Path Prerequisite Gates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `unlock_after_unit_ids` 从展示字段变成发布时可校验、Journey 可解释、后端访问不可绕过的真实训练闸门。

**Architecture:** 新建纯规则 Module `path_prerequisite_policy.py`，集中依赖引用校验和运行时解锁计算。TrainingJourney 与旧 Path Projection 共用该 Module；所有直接单元入口继续通过 Journey 的 `locked` 结果 fail-closed。

**Tech Stack:** Python 3.12、Pydantic v2、SQLAlchemy AsyncSession、FastAPI、Pytest、TypeScript/Vitest。

## Global Constraints

- 保留字段名 `unlock_after_unit_ids`，不制造破坏性数据迁移。
- 前置引用只能指向当前 revision 中更早、已启用、可完成的主路径 Module target unit。
- 学习专题 `required=false`、`blocks_next=false`，不得作为主路径 prerequisite。
- realtime roleplay 继续以 Readiness approve 和 provider readiness 为最终闸门，不用 prerequisite 绕过人工复核。
- 锁定状态必须提供用户语言原因；不能把正常等待前置任务标成终态系统错误。
- Journey、旧 `/paths` 投影和直接 API 访问必须对同一学员得出相同结果。

---

### Task 1: 冻结 prerequisite 配置规则

**Files:**
- Create: `backend/src/sales_trainer/services/path_prerequisite_policy.py`
- Create: `backend/tests/unit/test_path_prerequisite_policy.py`
- Modify: `backend/src/sales_trainer/services/path_config_models.py`
- Modify: `backend/src/sales_trainer/schemas.py`
- Modify: `backend/tests/unit/test_newcomer_training_path_config_revision.py`

**Interfaces:**
- Produces: `PrerequisiteModuleState`
- Produces: `PrerequisiteDecision`
- Produces: `validate_prerequisite_references(modules) -> None`
- Produces: `evaluate_prerequisites(states) -> dict[str, PrerequisiteDecision]`

- [ ] **Step 1: 写非法引用失败测试**

```python
@pytest.mark.parametrize(
    ("dependencies", "expected_fragment"),
    [
        (["missing-unit"], "不存在"),
        (["second-unit"], "必须早于"),
        (["first-unit", "first-unit"], "重复"),
    ],
)
def test_rejects_invalid_prerequisite_references(dependencies, expected_fragment):
    payload = _path_payload(second_unlock_after=dependencies)
    with pytest.raises(SalesTrainerPathConfigError) as exc:
        validate_path_payload_for_write(payload)
    assert exc.value.code == "[NEWCOMER_PATH_PREREQUISITE_INVALID]"
    assert expected_fragment in exc.value.message
```

另加测试：依赖停用 Module、依赖 realtime/无 target unit、依赖学习专题 source module 均拒绝发布。

Run: `cd backend && ./.venv/bin/python -m pytest -c pyproject.toml tests/unit/test_path_prerequisite_policy.py tests/unit/test_newcomer_training_path_config_revision.py -q --no-cov`

Expected: FAIL because policy Module and error code do not exist.

- [ ] **Step 2: 定义纯规则数据结构**

```python
@dataclass(frozen=True, slots=True)
class PrerequisiteModuleState:
    module_key: str
    order_index: int
    target_unit_ids: tuple[str, ...]
    unlock_after_unit_ids: tuple[str, ...]
    enabled: bool
    completion_satisfied: bool
    already_locked: bool = False

@dataclass(frozen=True, slots=True)
class PrerequisiteDecision:
    locked: bool
    unmet_unit_ids: tuple[str, ...]
    reason_code: str | None
    reason: str | None
```

`validate_prerequisite_references()` 建立 `target_unit_id -> owner module` 映射，拒绝空白、重复、未知、同级/后置、停用和不可完成引用。

- [ ] **Step 3: 实现有序运行时计算**

```python
def evaluate_prerequisites(
    states: list[PrerequisiteModuleState],
) -> dict[str, PrerequisiteDecision]:
    owner_by_unit = {
        unit_id: state
        for state in states
        for unit_id in state.target_unit_ids
    }
    decisions: dict[str, PrerequisiteDecision] = {}
    for state in sorted(states, key=lambda item: item.order_index):
        invalid = tuple(
            unit_id
            for unit_id in state.unlock_after_unit_ids
            if unit_id not in owner_by_unit
            or owner_by_unit[unit_id].order_index >= state.order_index
        )
        if invalid:
            decisions[state.module_key] = PrerequisiteDecision(
                locked=True,
                unmet_unit_ids=invalid,
                reason_code="[NEWCOMER_PATH_PREREQUISITE_CONFIG_INVALID]",
                reason="训练路径前置关系配置异常，请联系培训负责人。",
            )
            continue
        unmet = tuple(
            unit_id
            for unit_id in state.unlock_after_unit_ids
            if not owner_by_unit[unit_id].completion_satisfied
            or decisions.get(owner_by_unit[unit_id].module_key, PrerequisiteDecision(False, (), None, None)).locked
        )
        decisions[state.module_key] = PrerequisiteDecision(
            locked=state.already_locked or bool(unmet),
            unmet_unit_ids=unmet,
            reason_code="[NEWCOMER_PREREQUISITE_NOT_COMPLETED]" if unmet else None,
            reason="请先完成前置训练，再开始本任务。" if unmet else None,
        )
    return decisions
```

新 revision 调用前必须通过配置引用校验；运行时仍对历史非法 active revision fail-closed，返回配置诊断而不是抛出 KeyError 或忽略未知 unit id。

- [ ] **Step 4: 在写入校验处调用 policy**

`validate_path_payload_for_write()` 完成 canonical key/type 基础检查后调用 `validate_prerequisite_references(payload.modules)`。Pydantic validator 同时拒绝 `unlock_after_unit_ids` 中空值和重复值。

- [ ] **Step 5: 运行配置测试并提交**

Run: `cd backend && ./.venv/bin/python -m pytest -c pyproject.toml tests/unit/test_path_prerequisite_policy.py tests/unit/test_newcomer_training_path_config_revision.py -q --no-cov`

Expected: PASS，所有非法关系在保存/发布前返回 422。

```bash
git add backend/src/sales_trainer/services/path_prerequisite_policy.py backend/src/sales_trainer/services/path_config_models.py backend/src/sales_trainer/schemas.py backend/tests/unit/test_path_prerequisite_policy.py backend/tests/unit/test_newcomer_training_path_config_revision.py
git commit -m "fix: validate newcomer path prerequisites"
```

### Task 2: 在 TrainingJourney 中应用真实锁定状态

**Files:**
- Modify: `backend/src/sales_trainer/services/training_journey_service.py`
- Modify: `backend/tests/unit/test_sales_trainer_training_journey_service.py`

**Interfaces:**
- Consumes: `evaluate_prerequisites`
- Produces: Journey module fields `locked`, `block_reason`, diagnostic `[NEWCOMER_PREREQUISITE_NOT_COMPLETED]`

- [ ] **Step 1: 写 Journey 红测**

```python
journey = await service.get_learner_journey(str(learner.user_id), viewer=learner)
second = next(item for item in journey["modules"] if item["module_key"] == "company_product_demo")
assert second["locked"] is True
assert second["status"] == "not_started"
assert second["next_action"]["disabled"] is True
assert second["next_action"]["disabled_reason"] == "请先完成前置训练，再开始本任务。"
assert any(item["code"] == "[NEWCOMER_PREREQUISITE_NOT_COMPLETED]" for item in second["diagnostics"])
```

提交第一关通过证据后再次请求 Journey，断言第二关 `locked=false` 且 action 可用。

另加一条历史坏 revision 测试：引用不存在的 unit 时 Journey 返回锁定和 `[NEWCOMER_PATH_PREREQUISITE_CONFIG_INVALID]`，请求本身不出现 500。

Run: `cd backend && ./.venv/bin/python -m pytest -c pyproject.toml tests/unit/test_sales_trainer_training_journey_service.py -q --no-cov`

Expected: FAIL because `unlock_after_unit_ids` is not carried into `JourneyModule`.

- [ ] **Step 2: 扩展内部 JourneyModule**

```python
unlock_after_unit_ids: tuple[str, ...] = ()
locked: bool = False
block_reason: str | None = None
lock_status: TrainingStage = "not_started"
```

在 `_base_module()` 和 group/realtime 构造处从 active revision config 复制 `unlock_after_unit_ids`，不得从旧 unit 表重新推断。

- [ ] **Step 3: 在生成公开 payload 前执行 policy**

```python
def _apply_prerequisite_decisions(
    self,
    modules: list[JourneyModule],
    outcomes: dict[str, list[dict[str, Any]]],
) -> None:
    states = []
    for module in modules:
        latest = (outcomes.get(self._bucket_key(module)) or [None])[0]
        target_unit_ids = tuple(
            dict.fromkeys(
                value
                for value in (*module.target_unit_ids, module.target_unit_id)
                if value
            )
        )
        states.append(
            PrerequisiteModuleState(
                module_key=module.module_key,
                order_index=module.order_index,
                target_unit_ids=target_unit_ids,
                unlock_after_unit_ids=module.unlock_after_unit_ids,
                enabled=module.enabled,
                completion_satisfied=self._completion_satisfied(module, latest),
                already_locked=module.locked,
            )
        )
    decisions = evaluate_prerequisites(states)
    for module in modules:
        decision = decisions[module.module_key]
        if decision.reason_code:
            module.locked = True
            module.lock_status = "not_started"
            module.block_reason = decision.reason
            module.diagnostics.append(self._diagnostic(decision.reason_code, decision.reason or "", severity="info", terminal=False))
```

过滤 `""` 后再构造 `target_unit_ids`；计算结果只执行一次并复用，不在循环中重复调用 `evaluate_prerequisites`。

- [ ] **Step 4: 运行 Journey 回归**

Run: `cd backend && ./.venv/bin/python -m pytest -c pyproject.toml tests/unit/test_sales_trainer_training_journey_service.py tests/unit/test_path_prerequisite_policy.py -q --no-cov`

Expected: PASS；正常等待前置任务不进入 `error_terminal`，配置异常仍保持原诊断。

- [ ] **Step 5: 提交 Journey 切片**

```bash
git add backend/src/sales_trainer/services/training_journey_service.py backend/tests/unit/test_sales_trainer_training_journey_service.py
git commit -m "fix: enforce prerequisites in training journey"
```

### Task 3: 统一旧 Path Projection，消除双规则

**Files:**
- Modify: `backend/src/sales_trainer/services/path_projection_payloads.py`
- Modify: `backend/src/sales_trainer/services/path_service.py`
- Modify: `backend/tests/unit/test_sales_trainer_services.py`
- Modify: `backend/tests/unit/test_sales_trainer_path_projection_ai_coach.py`

- [ ] **Step 1: 写 parity 红测**

同一学员、同一 active revision，分别请求 `SalesTrainerPathService.list_paths_for_user()` 与 `TrainingJourneyService.get_learner_journey()`；将 unit id 对齐后断言 `locked` 完全一致。

Run: `cd backend && ./.venv/bin/python -m pytest -c pyproject.toml tests/unit/test_sales_trainer_services.py tests/unit/test_sales_trainer_path_projection_ai_coach.py -q --no-cov`

Expected: 当前测试至少出现旧投影与 Journey 结果不一致；现有已漂移 fixture 也会暴露 canonical type 问题。

- [ ] **Step 2: 将旧 payload 构建改为共用 policy**

```python
states = [
    PrerequisiteModuleState(
        module_key=str(level["module_key"]),
        order_index=int(level["order_index"]),
        target_unit_ids=(str(level["unit_id"]),),
        unlock_after_unit_ids=tuple(level["unlock_after_unit_ids"]),
        enabled=not bool(level["locked"]),
        completion_satisfied=level["status"] == "completed",
        already_locked=bool(level["locked"]),
    )
    for level in levels
]
decisions = evaluate_prerequisites(states)
```

删除 `build_path_payload()` 中自行计算 `completed_unit_ids/missing` 的重复规则；保留现有 target path、文案和 public stripping。

- [ ] **Step 3: 修复旧测试 fixture 而非放宽生产 canonical 校验**

`elevator_pitch` 必须继续使用 `audio_scoring_group`；需要 article_exam 场景的测试改用 canonical `business_skills`，不得为了旧测试修改生产注册表。

- [ ] **Step 4: 运行 parity 和既有 path tests**

Run: `cd backend && ./.venv/bin/python -m pytest -c pyproject.toml tests/unit/test_sales_trainer_services.py tests/unit/test_sales_trainer_training_journey_service.py tests/unit/test_sales_trainer_path_projection_ai_coach.py -q --no-cov`

Expected: PASS；两套读模型锁定结果一致。

- [ ] **Step 5: 提交 parity 切片**

```bash
git add backend/src/sales_trainer/services/path_projection_payloads.py backend/src/sales_trainer/services/path_service.py backend/tests/unit/test_sales_trainer_services.py backend/tests/unit/test_sales_trainer_path_projection_ai_coach.py
git commit -m "refactor: share path prerequisite policy"
```

### Task 4: 验证所有直接入口不能绕过闸门

**Files:**
- Modify: `backend/tests/integration/test_business_etiquette_quiz_api.py`
- Modify: `backend/tests/integration/test_newcomer_training_path_material_api.py`
- Modify: `backend/tests/unit/test_sales_trainer_realtime_roleplay_start.py`
- Modify: `backend/tests/unit/test_sales_trainer_training_journey_service.py`
- Modify: `scripts/critical-quality-gate.sh`

- [ ] **Step 1: 添加锁定直接访问测试**

```python
response = await client.get(
    f"/api/v1/sales-trainer/materials/versions/{locked_version.version_id}/file",
    headers=learner_headers,
)
assert response.status_code == 404
assert response.json()["error"] == "[MATERIAL_FILE_NOT_FOUND]"
```

覆盖录音材料、录音提交和 realtime start。锁定资源保持 404，避免泄露隐藏单元是否存在。另加商务礼仪专题正向测试，证明可选专题不会因为主路径 prerequisite 被错误锁定。

- [ ] **Step 2: 添加解锁后的正向测试**

插入属于 active path revision 的前置通过证据后，重复相同请求，断言 200；旧 revision 的通过证据仍返回 404。

- [ ] **Step 3: 运行 integration tests**

Run: `cd backend && ./.venv/bin/python -m pytest -c pyproject.toml tests/integration/test_business_etiquette_quiz_api.py tests/integration/test_newcomer_training_path_material_api.py tests/unit/test_sales_trainer_realtime_roleplay_start.py tests/unit/test_sales_trainer_training_journey_service.py -q --no-cov`

Expected: PASS，且锁定/解锁只由当前 active revision 证据决定。

- [ ] **Step 4: 加入 release gate 并更新契约**

将上述 policy、Journey、两个 integration test 和 realtime start unit test 加入 `critical-quality-gate.sh`；在 `docs/api-contract/sales-trainer.md` 记录错误码 `[NEWCOMER_PATH_PREREQUISITE_INVALID]`、`[NEWCOMER_PATH_PREREQUISITE_CONFIG_INVALID]` 和 `[NEWCOMER_PREREQUISITE_NOT_COMPLETED]`。

- [ ] **Step 5: 最终验证和提交**

Run: `cd backend && ./.venv/bin/ruff check src/sales_trainer/services/path_prerequisite_policy.py src/sales_trainer/services/path_config_models.py src/sales_trainer/services/training_journey_service.py src/sales_trainer/services/learner_unit_access.py`

Run: `cd backend && ./.venv/bin/python -m pytest -c pyproject.toml tests/unit/test_path_prerequisite_policy.py tests/unit/test_sales_trainer_training_journey_service.py tests/unit/test_sales_trainer_services.py tests/unit/test_sales_trainer_realtime_roleplay_start.py tests/integration/test_business_etiquette_quiz_api.py tests/integration/test_newcomer_training_path_material_api.py -q --no-cov`

Expected: 两条命令 exit 0。

```bash
git add backend/tests/integration/test_business_etiquette_quiz_api.py backend/tests/integration/test_newcomer_training_path_material_api.py backend/tests/unit/test_sales_trainer_realtime_roleplay_start.py scripts/critical-quality-gate.sh docs/api-contract/sales-trainer.md
git commit -m "test: gate newcomer path prerequisites"
```
