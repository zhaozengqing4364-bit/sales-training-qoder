# 架构审计整改闭环

## Goal

把 2026-07-03 架构审计报告中列出的关键整改项做成可验证闭环，优先以最小可发布切片修复运行时可靠性、权限口径、对象级权限测试、CI 门禁、观测指标、跨域边界门禁，并为异步任务持久化给出可落地方案与首个安全切片。

## User Request

用户要求全部完美闭环以下事项：

- `send_json` 失败语义修复
- Redis 启动期硬依赖治理
- RBAC 角色口径统一
- practice session 对象级权限测试
- 关键测试纳入 `critical-quality-gate`
- Prometheus 核心业务指标接线
- Adapter 跨域 import 扫描门禁
- 进程内异步任务持久化方案

## Scope

### 必须直接落地

- WebSocket `send_json` 不再静默吞失败；关键发送路径有可测试的失败语义。
- SessionStateService 的 Redis 启动依赖有明确 fail-fast / optional 策略、健康状态和测试覆盖。
- RBAC 角色词表至少有单一代码权威或映射层，admin / super_admin / content / ops / auditor 等口径不再互相漂移。
- Practice session 对象级权限新增越权测试，锁住 403/404 与数据不泄露语义。
- `critical-quality-gate.sh` 纳入 supervisor、presentation StepFun、observability、roleplay record-only 等关键测试。
- Prometheus 核心业务指标至少接入 WS connect/disconnect/send failure、TTS/ASR/LLM 或可观测 helper 的最小链路。
- Adapter 跨域 import 扫描测试进入测试门禁。

### 必须形成闭环方案

- 进程内异步任务持久化：如果一次性引入队列风险过高，必须先落地 ADR/方案文档 + 可执行 tests 或首个持久任务表/接口切片；不能只写聊天结论。

## Constraints

- 优先最小可验证改动，不做大范围重构。
- 不回滚已有用户改动；工作区很脏，必须只触碰本任务相关文件。
- 高风险路径先补 characterization tests，再改行为。
- 对无法完全实现的“大方案”必须以 ADR / runbook / tests 形式留下可继续执行的闭环证据。

## Acceptance Criteria

- [x] `send_json` 失败语义有测试覆盖，关键调用点不会静默吞掉失败。
- [x] Redis session state 启动行为有配置化策略、健康状态和测试覆盖。
- [x] RBAC 角色词表/映射层统一，相关后端/前端测试通过。
- [x] Practice session 对象级权限越权测试覆盖至少 report / knowledge-check / enhanced-report 或等价敏感投影。
- [x] `critical-quality-gate.sh` 包含新增关键测试集合。
- [x] Prometheus 核心业务指标有真实调用点和 tests。
- [x] Adapter 跨域 import 扫描门禁能拦截违规 import。
- [x] 异步任务持久化方案以 ADR/文档和首个安全实现切片闭环。
- [x] 相关 targeted tests 运行并记录结果。

## Closure Evidence

- Multiple implementation agents handled disjoint runtime, RBAC/permission, CI/adapter, and async-persistence slices.
- `trellis-check` performed a second deep pass and fixed schema width, send-result call sites, LLM/TTS metrics, boundary scan robustness, and gate membership.
- Main verification reran the backend gate target list and the full `critical-quality-gate.sh` with `PLAYWRIGHT_SKIP_BROWSER_INSTALL=1`; both passed.

## Reference Inputs

- `docs/project-analysis/audit-2026-07-03-independent-architecture-review.md`
- `.trellis/tasks/07-03-2026-07-03/review-evidence.md`
- `docs/AGENTS.md`
- `backend/AGENTS.md`
- `web/AGENTS.md`
- `scripts/AGENTS.md`
