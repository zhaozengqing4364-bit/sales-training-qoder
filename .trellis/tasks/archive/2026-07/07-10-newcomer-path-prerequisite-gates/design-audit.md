# Newcomer Path Prerequisite Gates — Design Artifact Audit

## Overall Conclusion

方向正确：active path revision 是唯一配置真源，纯 prerequisite policy 负责发布校验和运行时 decision，Journey 是直接访问的统一锁定真源，旧 `/paths` 不再维护第二套解锁算法。

首轮七维审计发现四个硬问题，均已在实施计划和 PRD 中修正；第二轮对照真实类型、调用点和测试后没有未解决硬错误，可以进入 TDD 实施。

## Dimension 1: Reference Pattern Reality

### Verified

- `unlock_after_unit_ids` 同时存在于 `NewcomerPathModuleConfig`、`SalesTrainerPathConfig` 和旧 Path Projection。
- `TrainingJourneyService` 从 active revision 构建 Module，并按 active revision id/no 查询 outcome。
- `learner_unit_access.py` 是材料、录音、测验、AI Coach 和 realtime 直接访问的统一 Journey guard。
- `SalesTrainerPathService` 已调用 Journey 做 visibility overlay，但旧 payload 仍先自行计算 `completed_unit_ids/missing`。

### Result

无需新权限体系、schema 或直接入口分叉；新增领域内纯 policy 并收敛两个读模型即可。

## Dimension 2: Dependency Direction

### 🔴 Fixed: policy error could create a circular import

Evidence:

- `path_config_models.py` 将 import 新 policy。
- 如果 policy 为了稳定 API 错误反向 import `SalesTrainerPathConfigError`，会形成循环依赖。

Correction:

- policy 只抛无 HTTP 语义的 `PrerequisiteReferenceError`。
- `validate_path_payload_for_write()` 在写入边界转换为 `[NEWCOMER_PATH_PREREQUISITE_INVALID]` / 422。

## Dimension 3: Type and Field Completeness

### 🔴 Fixed: Journey has duplicate public module keys

Evidence:

- `_journey_modules()` 为有 AI Coach 的 Path Module 追加派生 `JourneyModule`。
- 基础 Module 和 AI Coach 使用相同 `module_key`，仅 `kind`/bucket 不同。
- 原计划把所有 Journey Module 放入 `dict[module_key, decision]`，后者会覆盖前者。

Correction:

- policy 只接收基础 Path Module。
- 派生 Module 按 `base_module_key` 继承 decision；同一 prerequisite 只计算一次。

### Verified

- group Module 的真实 target IDs 来自 `duration_options`，普通 Module 来自 `target_unit_id`。
- realtime roleplay 可以没有 target unit，但可以消费更早 prerequisite；它本身不能成为 prerequisite owner。
- 当前 Path 中唯一 Learning Topic source Module 是 `business_skills`，领域契约明确其非阻塞语义。

## Dimension 4: Transaction and IO Boundary

### Verified

- policy 是纯计算，不增加 DB transaction 或外部 IO。
- revision save/publish 继续沿用现有事务和审计路径。
- Journey outcome 读取顺序不变；policy 在结果装配阶段执行一次。

## Dimension 5: Caller Semantics

### 🔴 Fixed: old projection cannot safely run policy per level

Evidence:

- `audio_scoring_group` 会在 `_projection_items()` 中展开多个 duration option，每个 level 拥有相同 `module_key`。
- 旧 `load_latest_*_progress` 不是 prerequisite 的 active-revision 权威完成来源。
- 原计划按 level 构造 policy state，会覆盖重复 key，并与 Journey 的 Module 完成语义继续漂移。

Correction:

- `build_path_payload()` 变成 prerequisite-neutral serializer。
- `SalesTrainerPathService` 用 Journey 已应用的 decision 精确覆盖 level 锁定，并重算 current/next/completed 汇总。

### 🔴 Fixed: config-invalid and normal-waiting status were conflated

Evidence:

- 正常等待前置训练必须是 `not_started` 非终态。
- 历史非法 active revision 是配置故障，不能伪装成普通等待。
- 原计划对两种 reason code 都写 `not_started` / `terminal=false`。

Correction:

- `[NEWCOMER_PREREQUISITE_NOT_COMPLETED]` 使用 `not_started`、非终态。
- `[NEWCOMER_PATH_PREREQUISITE_CONFIG_INVALID]` 使用 `error_terminal`、终态诊断，但 Journey 请求保持成功响应。
- prerequisite 只增加锁定，不覆盖 provider/learner-level 等既有更强 block reason。

## Dimension 6: Immediate Test Impact

### Verified

- `test_sales_trainer_services.py` 存在漂移 fixture：`elevator_pitch` 被错误用于 `article_exam`。该两关 quiz fixture 不能机械改成 `business_skills`，因为 canonical path 只有一个 Learning Topic source；parity 回归必须改用合法的 `ppt_explanation -> company_product_demo` audio prerequisite 或复用 Journey helper，不能放宽生产注册表。
- material integration 已有锁定 404 基线，可扩展当前/旧 revision 证据断言。
- Journey fixture 直接创建 published revision，适合构造“历史非法 active revision”而不经过新写入校验。
- realtime、quiz、audio submission 均已有统一 access guard 调用点，可做 prerequisite-specific 防绕过回归。

## Dimension 7: Artifact Internal Consistency

### Verified

- PRD、实施计划和总整改索引都保持执行顺序：Readiness 完成后处理 prerequisite，Learning Topic Attempt 另行处理。
- 所有产物一致保留字段名、不迁移、不新增依赖、不改 Learning Topic 阻塞语义。
- Acceptance Criteria 可对应到 policy、Journey parity、直接入口和 release gate 测试。

## Second-Pass Verification

- 重新对照 `path_config_models.py`、`schemas.py`、`training_journey_service.py`、`path_projection_payloads.py`、`path_service.py`、`learner_unit_access.py` 和 Learning Topic executable spec。
- 确认 policy 异常依赖方向、基础/派生 Module 唯一性、group option 展开、active revision outcome 和直接入口调用链均已在计划中显式处理。
- 硬错误剩余：0。
- 未决需求：0。
- 建议项：实现时保持 policy 输入/输出无 ORM/DB 依赖，并用 RED 测试证明每条错误分支。
