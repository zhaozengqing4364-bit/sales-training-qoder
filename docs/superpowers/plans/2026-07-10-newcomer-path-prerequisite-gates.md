# Newcomer Path Prerequisite Gates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `unlock_after_unit_ids` 从展示字段变成发布时可校验、Journey 可解释、后端访问不可绕过的真实训练闸门。

**Architecture:** 新建纯规则 Module `path_prerequisite_policy.py`，集中依赖引用校验和运行时解锁计算。TrainingJourney 只对 active revision 的基础 Path Module 计算一次 decision，AI Coach 等派生 Module 按 `base_module_key` 继承，不把重复 `module_key` 送入 policy。旧 Path Projection 删除逐 level 的第二套规则，并以 Journey 的同一 decision 结果覆盖锁定状态；所有直接单元入口继续通过 Journey 的 `locked` 结果 fail-closed。

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
- Modify: `backend/src/app_factory.py`
- Modify: `backend/tests/unit/test_newcomer_training_path_config_revision.py`
- Modify: `backend/tests/integration/test_newcomer_training_path_config_api.py`

**Interfaces:**
- Produces: `PrerequisiteModuleState`
- Produces: `PrerequisiteDecision`
- Produces: `PrerequisiteReferenceError`
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
    module_type: str | None
    order_index: int
    target_unit_ids: tuple[str, ...]
    unlock_after_unit_ids: tuple[str, ...]
    enabled: bool
    completion_satisfied: bool
    completed_target_unit_ids: tuple[str, ...] | None = None
    already_locked: bool = False

@dataclass(frozen=True, slots=True)
class PrerequisiteDecision:
    locked: bool
    unmet_unit_ids: tuple[str, ...]
    reason_code: str | None
    reason: str | None
```

`validate_prerequisite_references()` 建立 `target_unit_id -> owner module` 映射，拒绝空白、重复、未知、同级/后置、停用、跨 Module 重复 target 和不可完成引用。当前 Learning Topic 来源 Module（`business_skills`）由 policy 的显式非阻塞 allowlist 识别，不得成为 prerequisite owner；未来新增来源键时必须同步扩展该领域契约和测试。

Audio group 的 target unit 是精确引用：`completed_target_unit_ids` 记录当前 active revision 中逐档位满足完成规则的 target；完成同组 3 分钟档位不得解锁显式依赖 5 分钟 target 的后续模块。单 target 模块继续使用 `completion_satisfied`，兼容缺少 `target_unit_id` 的旧证据。

纯 policy 不得反向 import `path_config_models.SalesTrainerPathConfigError`，否则形成循环依赖。policy 抛出不带 HTTP 语义的 `PrerequisiteReferenceError`；`validate_path_payload_for_write()` 在写入边界转换成 `[NEWCOMER_PATH_PREREQUISITE_INVALID]` / 422。

- [ ] **Step 3: 实现有序运行时计算**

```python
def evaluate_prerequisites(
    states: list[PrerequisiteModuleState],
) -> dict[str, PrerequisiteDecision]:
    unit_ids = {
        unit_id
        for state in states
        for unit_id in state.target_unit_ids
    }
    owners_by_unit = {
        unit_id: [
            candidate
            for candidate in states
            if unit_id in candidate.target_unit_ids
        ]
        for unit_id in unit_ids
    }
    decisions: dict[str, PrerequisiteDecision] = {}
    for state in sorted(states, key=lambda item: item.order_index):
        invalid = tuple(
            unit_id
            for unit_id in state.unlock_after_unit_ids
            if len(owners_by_unit.get(unit_id, [])) != 1
            or not owners_by_unit[unit_id][0].enabled
            or owners_by_unit[unit_id][0].order_index >= state.order_index
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
            if not owners_by_unit[unit_id][0].completion_satisfied
            or decisions.get(owners_by_unit[unit_id][0].module_key, PrerequisiteDecision(False, (), None, None)).locked
        )
        decisions[state.module_key] = PrerequisiteDecision(
            locked=state.already_locked or bool(unmet),
            unmet_unit_ids=unmet,
            reason_code="[NEWCOMER_PREREQUISITE_NOT_COMPLETED]" if unmet else None,
            reason="请先完成前置训练，再开始本任务。" if unmet else None,
        )
    return decisions
```

新 revision 调用前必须通过配置引用校验；运行时 state 通过 `module_key + module_type` 复用同一 owner eligibility，仍对历史非法 active revision fail-closed，返回配置诊断而不是抛出 KeyError 或忽略未知/停用/歧义/realtime/Learning Topic unit id。基础 Path Module 的 `module_key` 必须唯一；历史重复 key 也按配置异常锁定处理。

- [ ] **Step 4: 在写入校验处调用 policy**

`validate_path_payload_for_write()` 完成 canonical key/type 基础检查后调用 `validate_prerequisite_references(payload.modules)`。Pydantic validator 同时拒绝 `unlock_after_unit_ids` 中空值和重复值，并使用可识别的 `PydanticCustomError` type；全局 RequestValidationError handler 只对 path-config 请求中的该 error type 映射 `[NEWCOMER_PATH_PREREQUISITE_INVALID]` / 422，不得吞并其他请求校验错误。

`payload_from_revision()` 使用显式 validation context 容错读取历史 blank/duplicate prerequisite，让原始值进入 runtime policy；新保存请求仍保持严格。历史兼容只放宽读取，不允许重新保存非法 payload。

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

在 `_base_module()` 和 group/realtime 构造处从 active revision config 复制 `unlock_after_unit_ids`，不得从旧 unit 表重新推断。`ai_coach` 等派生 Module 不单独进入 prerequisite owner/decision 映射，避免同一 `module_key` 覆盖基础 Module decision。

- [ ] **Step 3: 在生成公开 payload 前执行 policy**

```python
def _apply_prerequisite_decisions(
    self,
    modules: list[JourneyModule],
    outcomes: dict[str, list[dict[str, Any]]],
) -> None:
    states = []
    for module in modules:
        if module.kind == "ai_coach":
            continue
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
                module_type=module.module_type,
                order_index=module.order_index,
                target_unit_ids=target_unit_ids,
                unlock_after_unit_ids=module.unlock_after_unit_ids,
                enabled=module.enabled,
                completion_satisfied=self._completion_satisfied(module, latest),
                completed_target_unit_ids=self._completed_prerequisite_target_unit_ids(module, history),
                already_locked=module.locked,
            )
        )
    decisions = evaluate_prerequisites(states)
    for module in modules:
        decision = decisions.get(module.base_module_key)
        if decision is None:
            continue
        if decision.reason_code:
            module.locked = True
            config_invalid = decision.reason_code == "[NEWCOMER_PATH_PREREQUISITE_CONFIG_INVALID]"
            module.lock_status = "error_terminal" if config_invalid else "not_started"
            module.block_reason = module.block_reason or decision.reason
            module.diagnostics.append(self._diagnostic(decision.reason_code, decision.reason or "", severity="warning" if config_invalid else "info", terminal=config_invalid))
```

过滤 `""` 后再构造 `target_unit_ids`；多 target Module 必须按 outcome 的真实 `target_unit_id` 计算逐 target 完成集合。计算结果只执行一次并复用，不在循环中重复调用 `evaluate_prerequisites`。正常未完成前置训练使用 `not_started` 非终态；历史配置异常保留 `error_terminal`，且 prerequisite 不得覆盖 provider/learner-level 等更强的既有 block reason。

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
- Modify: `backend/src/sales_trainer/services/training_journey_service.py`
- Modify: `backend/tests/unit/test_sales_trainer_services.py`
- Modify: `backend/tests/unit/test_sales_trainer_path_projection_ai_coach.py`
- Modify: `backend/tests/unit/test_sales_trainer_training_journey_service.py`

- [ ] **Step 1: 写 parity 红测**

同一学员、同一 active revision，分别请求 `SalesTrainerPathService.list_paths_for_user()` 与 `TrainingJourneyService.get_learner_journey()`；将 unit id 对齐后断言 `locked` 完全一致。

Run focused RED: `cd backend && ./.venv/bin/python -m pytest -c pyproject.toml tests/unit/test_sales_trainer_services.py -q --no-cov -k 'project_sales_trainer_path_with_unlock_progress or prerequisite_parity'`

Expected: 当前测试至少出现旧投影与 Journey 结果不一致；现有已漂移 fixture 也会暴露 canonical type 问题。

- [ ] **Step 2: 删除旧 payload 的逐 level 双规则，复用 Journey decision**

`build_path_payload()` 只序列化 unit progress，不再自行计算 `completed_unit_ids/missing`。`SalesTrainerPathService._apply_journey_visibility()` 按 Journey Module 的 `target_unit_ids` 对齐 level，并把 `locked` 精确覆盖为 Journey decision（既能锁定也能解锁），同步 `lock_reason/status` 后重算 `current_level_id`、`next_level_id` 和 `completed_levels`。

这样可避免 `audio_scoring_group` 的多个 duration option 以相同 `module_key` 重复进入 policy，也避免旧投影用未按 active revision 隔离的 progress 自行决定 prerequisite；保留现有 target path、文案和 public stripping。

旧投影的 `latest_result` 和 `goal_context` 也必须由 Journey 的 active-revision `latest_outcome` 覆盖后重建，不能让旧 revision 的更晚记录继续驱动首页推荐。Journey 已移除的 Learning Topic source level 必须从 legacy 主路径 `levels/total/completed/current/next/goal_context` 排除；专题仍通过独立 Learning Topic API 访问，不得作为 unmatched 普通关卡继续导航。

Journey audio/quiz/regrade outcome 必须携带真实 `target_unit_id`；legacy adapter 对 audio group 按 level unit id 从 `outcome_history` 选择对应最新证据，禁止把一个 duration option 的录音复制到所有 option level 或重复生成 evidence。

- [ ] **Step 3: 修复旧测试 fixture 而非放宽生产 canonical 校验**

`elevator_pitch` 必须继续使用 `audio_scoring_group`。现有“两关 quiz/article_exam” fixture 不能简单把第二关改成 `business_skills`：canonical path 只有一个 `business_skills`，且 Learning Topic source 不得成为 prerequisite owner。parity 测试应改用 canonical `ppt_explanation -> company_product_demo` audio Module，或直接复用 Journey 的合法 prerequisite fixture/证据 helper；不得为了旧测试修改生产注册表，也不得让 `business_skills` 重新进入阻塞主路径。

- [ ] **Step 4: 运行 parity 和既有 path tests**

Run: `cd backend && ./.venv/bin/python -m pytest -c pyproject.toml tests/unit/test_sales_trainer_services.py -q --no-cov -k 'project_sales_trainer_path_with_unlock_progress or prerequisite_parity'`

Run: `cd backend && ./.venv/bin/python -m pytest -c pyproject.toml tests/unit/test_sales_trainer_training_journey_service.py tests/unit/test_sales_trainer_path_projection_ai_coach.py -q --no-cov`

Expected: focused parity 与 Journey/path projection tests PASS；`test_sales_trainer_services.py` 全文件仍允许保留已登记的 4 个“无 active revision 的通用 QuizService”基线失败，不得在本切片扩修。

- [ ] **Step 5: 提交 parity 切片**

```bash
git add backend/src/sales_trainer/services/path_projection_payloads.py backend/src/sales_trainer/services/path_service.py backend/tests/unit/test_sales_trainer_services.py backend/tests/unit/test_sales_trainer_path_projection_ai_coach.py
git commit -m "refactor: share path prerequisite policy"
```

### Task 4: 验证所有直接入口不能绕过闸门

**Files:**
- Modify: `backend/tests/integration/test_business_etiquette_quiz_api.py`
- Modify: `backend/tests/integration/test_newcomer_training_path_material_api.py`
- Modify: `backend/tests/unit/test_newcomer_training_path_audio_lineage.py`
- Modify: `backend/tests/unit/test_sales_trainer_realtime_roleplay_start.py`
- Modify: `backend/tests/unit/test_sales_trainer_training_journey_service.py`
- Modify: `scripts/critical-quality-gate.sh`
- Modify: `docs/api-contract/sales-trainer.md`

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

Run: `cd backend && ./.venv/bin/python -m pytest -c pyproject.toml tests/integration/test_business_etiquette_quiz_api.py tests/integration/test_newcomer_training_path_material_api.py tests/unit/test_newcomer_training_path_audio_lineage.py tests/unit/test_sales_trainer_training_journey_service.py -q --no-cov`

Run: `cd backend && ./.venv/bin/python -m pytest -c pyproject.toml tests/unit/test_sales_trainer_realtime_roleplay_start.py -q --no-cov -k 'not test_realtime_roleplay_enter_permission_is_learner_only'`

Expected: PASS，且锁定/解锁只由当前 active revision 证据决定。`test_realtime_roleplay_enter_permission_is_learner_only` 是开发前已确认的独立权限基线失败，本任务不改变该语义。

- [ ] **Step 4: 加入 release gate 并更新契约**

将上述 policy、Journey、两个 integration test、audio lineage 和 realtime start unit test 加入 `critical-quality-gate.sh`；在 `docs/api-contract/sales-trainer.md` 记录 `unlock_after_unit_ids` 约束、Journey outcome 的 `target_unit_id`、当前 active revision 证据语义，以及错误码 `[NEWCOMER_PATH_PREREQUISITE_INVALID]`、`[NEWCOMER_PATH_PREREQUISITE_CONFIG_INVALID]` 和 `[NEWCOMER_PREREQUISITE_NOT_COMPLETED]`。

- [ ] **Step 5: 最终验证和提交**

Run: `cd backend && ./.venv/bin/ruff check src/sales_trainer/services/path_prerequisite_policy.py src/sales_trainer/services/path_config_models.py src/sales_trainer/services/training_journey_service.py src/sales_trainer/services/learner_unit_access.py`

Run: `cd backend && ./.venv/bin/python -m pytest -c pyproject.toml tests/unit/test_path_prerequisite_policy.py tests/unit/test_sales_trainer_training_journey_service.py tests/unit/test_newcomer_training_path_audio_lineage.py tests/integration/test_business_etiquette_quiz_api.py tests/integration/test_newcomer_training_path_material_api.py -q --no-cov`

Run: `cd backend && ./.venv/bin/python -m pytest -c pyproject.toml tests/unit/test_sales_trainer_realtime_roleplay_start.py -q --no-cov -k 'not test_realtime_roleplay_enter_permission_is_learner_only'`

Run: `cd backend && ./.venv/bin/python -m pytest -c pyproject.toml tests/unit/test_sales_trainer_services.py -q --no-cov`

Expected: Ruff 和前两条 pytest 命令 exit 0。`test_sales_trainer_services.py` 仍只保留开发前记录的 4 条“无 active path revision”旧夹具失败，不在本任务中扩大权限/兼容范围。

```bash
git diff --check
```

完成验证后交给用户确认，再决定是否提交。
