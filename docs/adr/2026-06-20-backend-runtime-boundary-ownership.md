# ADR 2026-06-20: 后端运行时边界与 contributor bootstrap 所有权

## Status

Accepted. 本 ADR 记录 `project-governance-refactor` Wave 1 对后端运行时组合根、domain contributor、common port 和 Roleplay Contract 共享边界的决策。

## 背景

后端已有多个运行时相关域：

- `common/` 承载 `PracticeSession`、runtime gate、repair service、report contributor registry 等共享平台能力。
- `sales_bot/` 承载 StepFun realtime sales runtime、voice policy 编译和 sales WebSocket。
- `curriculum_practice/` 承载课程化内容、examiner runtime、Roleplay Contract、Situation Pack 和 runtime snapshot。
- `presentation_coach/` 承载 presentation runtime 适配。
- `training_runtime/` 承载 runtime descriptor 和 scenario plugin dispatch。

治理扫描发现两个边界风险：

1. `router_registry.py` 同时承担 HTTP route mounting 和 domain contributor registration，导致组合根职责混在路由表中。
2. `common/services/session_runtime_repair_service.py` 直接导入 `sales_bot.services.voice_runtime_policy.VoiceRuntimePolicyService`，形成 `common -> sales_bot` 反向依赖。

这些问题不会立刻改变用户路径，但会让后续 runtime、repair、release gate 和 Roleplay Contract 重构更难验证。

## 决策

### 1. HTTP router registry 只负责 HTTP route mounting

`backend/src/router_registry.py` 保留为非 WebSocket HTTP router 的挂载入口。它不再直接维护 domain contributor/provider 注册清单，只在挂载路由前调用独立组合根：

```text
domain_contributor_bootstrap.register_domain_contributors()
```

`domain_contributor_bootstrap.py` 是当前 domain contributor registration 的权威顺序清单。新增 contributor 时必须进入该清单，并通过 `backend/tests/unit/test_domain_contributor_bootstrap.py` 锁定顺序。

### 2. Domain contributor 是跨域注册的唯一允许形态

业务域需要向 common/support/training_runtime 暴露能力时，必须通过 contributor 注册：

- sales voice policy repair factory：`sales_bot.services.runtime_repair_contributor`
- sales / presentation / curriculum practice session contributors
- curriculum runtime gate contributors
- support runtime contributors
- report contributors
- knowledge governance contributors
- training runtime practice session contributor

禁止在 `common/` 里为了单个业务域直接导入具体实现。

### 3. Common 只能拥有 port/protocol，不拥有具体 domain runtime

`common/services/session_runtime_repair_service.py` 拥有 `VoiceRuntimePolicyResolver` 协议和 resolver factory 注册点。`sales_bot/` 负责把 `VoiceRuntimePolicyService` 注册进该 port。

独立脚本 `backend/scripts/repair_runtime_snapshots.py` 不经过 FastAPI app bootstrap，因此必须显式注册 `sales_bot` repair contributor 后再运行 repair service。

### 4. Runtime readiness 与 runtime repair 分离

`RuntimeGate` 继续表达“当前 session 是否可运行”的 readiness/admission 结果。`SessionRuntimeRepairService` 继续表达 operator 显式执行的 dry-run/apply repair 流程。

WebSocket 或预检路径不得隐式调用 repair service 重建历史 snapshot。repair 仍然是操作员触发、默认 dry-run、可审计的路径。

### 5. Roleplay Contract 属于共享契约，当前实现仍由 curriculum_practice 承载

当前 Roleplay Contract compiler/hash/freeze 实现仍在 `curriculum_practice/`。从边界所有权看，Roleplay Contract 是 runtime、snapshot、evaluation、Situation Pack 共同消费的共享契约 primitive，不应长期被视作 curriculum-only 内部实现。

本 ADR 先锁定所有权原则：后续抽取只能移动共享 interface/hash helper 到中立边界，不得改变 compiler/hash/freeze 语义，不得让 runtime 读取 latest admin config 重拼历史 session。

## 备选方案

### 方案 A：继续把 contributor 注册留在 `router_registry.py`

优点是 diff 最小。缺点是 HTTP route mounting 与跨域能力注册继续混在一起，后续新增 contributor 很容易被误认为“注册一个路由”，也无法单独测试 contributor 顺序。

### 方案 B：把所有 contributor 注册塞进 app lifespan

优点是接近应用启动生命周期。缺点是 standalone scripts、unit tests、CLI repair 路径并不总经过 lifespan，会让非 HTTP 入口缺少注册或重复补丁。

### 方案 C：在 common 中直接 lazy import sales_bot

优点是调用点少。缺点是仍然保留 `common -> sales_bot` 反向依赖，只是把静态 import 变成运行时 import，依赖合同无法收缩。

### 方案 D：独立 contributor bootstrap + common port

采用。它保持 HTTP route 行为不变，同时给 app bootstrap、脚本入口和测试提供明确注册点；common 只依赖协议，domain 实现由 contributor 注入。

## 取舍

采用方案 D 的代价是新增一个轻量 bootstrap 文件和一个 sales_bot repair contributor 文件。这个成本小于继续让 `common` 了解 sales runtime 具体实现的长期成本。

不在本 ADR 中抽取 Roleplay Contract 代码，因为 Task 17 会单独处理共享 primitive 的物理迁移。当前只记录所有权原则，避免把尚未完成的迁移写成既成事实。

## 影响

### 代码影响

- `router_registry.py` 的 HTTP `include_router` 顺序不变。
- `domain_contributor_bootstrap.py` 成为 contributor/provider 注册顺序的权威清单。
- `common/services/session_runtime_repair_service.py` 不再导入 `sales_bot`。
- `sales_bot/services/runtime_repair_contributor.py` 负责注册 sales voice policy resolver factory。
- `backend/scripts/repair_runtime_snapshots.py` 显式注册 repair contributor，保持 standalone operator 路径可用。

### 权限与状态影响

- 不新增权限。
- 不改变 `PracticeSession.status`、runtime gate admission 结果或 repair apply 语义。
- repair 仍默认 dry-run；只有 `--apply` 才会写入可修复字段。

### 测试影响

边界由以下测试固定：

- `backend/tests/unit/test_domain_contributor_bootstrap.py`
- `backend/tests/unit/test_runtime_dependency_contract.py`
- `backend/tests/unit/test_session_runtime_repair_service.py`

### 运维影响

运行 `backend/scripts/repair_runtime_snapshots.py` 时不需要手动调用 app bootstrap。脚本内部会注册 sales_bot repair contributor。

## 回滚

如该决策导致启动或 repair 路径问题，可以按以下顺序回滚：

1. 保留测试失败证据，先恢复 `router_registry.py` 中的 contributor 调用顺序。
2. 将 `SessionRuntimeRepairService` 临时改回直接注入 `runtime_policy_service` 的调用方式，但不得恢复 `common -> sales_bot` allowlist 作为长期状态。
3. 如果 standalone script 失败，只回滚 `backend/scripts/repair_runtime_snapshots.py` 的 contributor 注册入口，并保留 common port。
4. Roleplay Contract 的未来抽取如果失败，应回退共享 helper 的物理移动，保持现有 compiler/hash/freeze 行为不变。
