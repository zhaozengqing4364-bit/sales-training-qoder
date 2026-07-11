# 模块化单体 2.0 Gate 5：训练闭环与 Locality

## Goal

把新人训练路径、训练达标档案、训练报告和共享 ORM 注册中心从“修改一个领域就必须同时理解
全局 DTO、全局 client、巨型页面和跨域 ORM”的结构，迁移为具有高 Depth 的投影、ViewModel、
领域 transport/type 和物理模型注册 Module；保持所有用户路径、REST/WS、权限、冻结证据、审计、
表结构和历史 import 完全兼容。

## What I already know

- Gate 0A–4 已实现、提交、验证和 Trellis 归档；Gate 4 clean-start canonical gate 自然通过。
- Gate 5 的目标设计已在总体设计、ADR 和 roadmap 获批，用户授权不中断执行且禁止派发子代理。
- CodeGraph、共变和基线证据见 `research/current-locality-and-model-registry.md`。
- 本 Gate 不改变产品视觉方向、不新增训练类型、不拆微服务、不改变数据库部署或 Alembic 历史。

## Requirements

### Training Journey / Readiness projection locality

- 定义 immutable Learner、Practice/Roleplay outcome projection 和 repository/port；Sales Trainer
  application code 不再直接读取 `common.db.models.User/PracticeSession`。
- SQLAlchemy adapter 负责权限范围内的查询和 ORM → immutable projection 映射；投影 Module 不
  导入 SQLAlchemy、FastAPI 或跨域 ORM。
- `TrainingJourneyService` 只编排 active revision、outcome readers 和 projection；确定性的 module
  stage、next action、overall progress、analytics、level/capability projection 不再散落于 route/ORM。
- `ReadinessDossierService` 只编排 Journey、records、review log、transaction 和权限；evidence、
  competency、status、realtime gate、workbench grouping 和 retraining comparison 由纯投影 Module
  负责。
- 缺 active revision、旧 lineage、缺 provider、配置异常、证据不足继续 fail closed，不伪造分数
  或达标；复核写入仍单事务、对象级权限、审计和幂等语义不变。

### Report ViewModel / mapper / actions locality

- Session report transport DTO、ViewModel mapper、状态/分数/证据标签、replay/retraining/navigation
  action builder 放到 report route 的局部 Module；页面只负责编排和渲染 ViewModel。
- action builder 对 session/replay/page 参数使用 `URLSearchParams` 和稳定编码，禁止页面散落 URL
  协议知识；清理/写入 retraining link 的副作用集中在 action seam。
- mapper 必须覆盖 evaluable/non-evaluable、partial/stale evidence、Presentation/Sales、pending/
  failed report、无 supervisor 权限等现有状态；普通用户不显示 raw enum/trace/raw JSON。
- 现有 report page 外观、文案语义、加载/错误/重试和测试选择保持兼容；本 Gate 不做 UI 重设计。

### Frontend domain type and transport locality

- Journey/Readiness 和 Session Report 的真实 type definitions 移入领域 type Module；
  `types.ts` 只保留向后兼容 re-export，不再重复定义这些知识。
- Sales Trainer 与 session/report transport factory 从领域 type Module import；`client.ts` 只组合
  request/auth/error/trace seams 和领域 builder，不拥有领域 endpoint/mapping 规则。
- Gate 5 范围内页面、hook、ViewModel 和测试改为领域 import；历史外部消费者可继续使用全局
  barrel，Gate 6 根据实际消费者证明退役。
- 增加静态 locality contract：新增 Journey/Readiness/report 字段或 endpoint 时，无须同时修改
  全局 `types.ts`、全局 `client.ts` 和页面根文件。

### Physical ORM registry split

- `common/db/models.py` 变为稳定 compatibility registry；实体 Implementation 按 identity、
  governance、training/evidence、evaluation/supervision、platform/operations、knowledge 分组到
  `common/db/model_registry/`。
- 所有实体继续继承同一个 `Base`，65 个既有公开 enum/entity class 加 `Base`、52 个 mapped table、
  table name、column、FK、index、
  constraint、relationship、default 和 metadata 注册完全一致；不得生成 migration。
- `from common.db.models import X` 保持对象 identity；Alembic `target_metadata`、test create_all、
  runtime startup bootstrap 继续看到完整 metadata。
- 新 projection/repository adapter 直接 import 所属 model Module；业务投影不从 compatibility
  registry 或其他 bounded context 导入 ORM。
- 增加 model inventory/identity/metadata parity、import-order 和 Alembic no-diff contract。

### Architecture, rollout and evidence

- 使用 compatibility re-export/registry 作为 Gate 5 rollback seam；Gate 6 才删除已无消费者入口。
- 不新增 dependency-policy 临时例外；若实际边消失必须同提交收缩 policy，SCC 不得扩大。
- 每个切片执行 TDD Red → Green → Refactor、CodeGraph impact/affected、Ruff/mypy/TypeScript/Vitest
  和聚焦合同测试，并形成逻辑化本地提交。
- 最终 Brooks architecture audit 与 Trellis check blocking finding=0，唯一 canonical gate 从 clean
  start 自然 exit 0。

## Acceptance Criteria

- [ ] Training Journey/Readiness application Module 不直接 import `User` 或 `PracticeSession` ORM；
      SQL adapter 只返回 immutable projections。
- [ ] Journey、analytics、Readiness dossier/workbench/review differential fixtures 与 Gate 4 baseline
      完全一致，缺失/异常路径仍 fail closed。
- [ ] report ViewModel/mapper/action Module 通过 Sales、Presentation、partial、non-evaluable、retraining
      和 supervisor 权限矩阵；页面根文件不再拥有 transport mapping/URL policy。
- [ ] Journey/Readiness/report 的真实 TS definitions 和 transport 实现在领域文件；全局 files 只组合
      或 re-export，locality contract 可执行。
- [ ] 65 个 enum/entity class 加 `Base` 的 `common.db.models` 公开 symbol identity/qualified-name
      compatibility 与 52 个 mapped table 的完整 `Base.metadata` 表/约束快照不变；
      `common/db/models.py` 为小型 registry，未产生 Alembic schema diff。
- [ ] 新 Journey/Readiness application code 通过 repository/projection 访问 identity/practice 数据，
      不扩大任何跨包边或 SCC。
- [ ] Backend focused/affected、frontend focused/affected、OpenAPI、architecture、Ruff、mypy、typecheck、
      lint、Vitest、selected E2E 和 changed coverage 满足 canonical gate。
- [ ] Brooks audit 与 Trellis check blocking finding=0；文档、ADR、roadmap、Trellis、代码事实一致。

## Definition of Done

- TDD 和偏离计划证据持续写入 `implementation-notes.md`。
- `.trellis/spec/backend/`、`.trellis/spec/frontend/` 记录投影、领域 locality 和 model registry 合同。
- Gate 5 详细实施计划的所有 checkbox 完成，authority docs 写入 exact canonical evidence。
- task 验证、归档和 journal 完成；工作区只剩用户 readiness 文档改动。

## Technical Approach

采用 vertical strangler + compatibility registry。先冻结 model/type/import/behavior parity，再建立
immutable projection seam 和纯 mapper，随后迁移 production composition，最后物理移动实体和前端
definitions。每个新 Module 必须通过 deletion test：删除它会使规则重新散落到多个调用者，而不是
让复杂度消失。

### Public interfaces

```python
@dataclass(frozen=True, slots=True)
class JourneyLearnerProjection:
    learner_id: str
    name: str | None
    department: str | None
    role: str
    is_active: bool

class JourneyReadRepository(Protocol):
    async def learner(self, learner_id: str) -> JourneyLearnerProjection | None: ...
    async def learners(self, query: JourneyLearnerQuery) -> JourneyLearnerPage: ...
    async def roleplay_outcomes(self, query: RoleplayOutcomeQuery) -> tuple[RoleplayOutcomeProjection, ...]: ...

class ReadinessDossierProjection:
    def dossier(self, source: ReadinessProjectionSource) -> Mapping[str, object]: ...
    def workbench(self, dossiers: Sequence[Mapping[str, object]], total: int, query: WorkbenchQuery) -> Mapping[str, object]: ...
```

```typescript
export function toSessionReportViewModel(report: PracticeSessionReport): SessionReportViewModel;
export function buildSessionReportActions(input: SessionReportActionInput): SessionReportActions;
export function createSessionsDomain(deps: SessionsDomainDependencies): SessionsDomain;
```

Concrete field sets may grow from characterization tests, but projections are immutable and contain no
ORM rows; global barrels remain compatibility-only.

## Decision (ADR-lite)

**Context**: The system behavior is mature, but Journey/Dossier/report/model knowledge lives in global
hotspots. Historical data shows report + types co-change 22 times and global types + client 55 times.

**Decision**: Deepen four Modules: Journey/Readiness projection, report route model/actions, domain
transport/types and physical ORM registry. Keep old import surfaces as tested compatibility seams until
Gate 6.

**Consequences**: There is temporary re-export/composition code and more explicit DTO mapping, but a
domain change becomes local, tests exercise stable interfaces, ORM metadata stays unified, and future AI
work does not need to load 20K lines of unrelated global files.

## Assumptions

- Existing migrations and production schema are authoritative; model movement is source-only.
- Existing domain builders are retained and deepened instead of introducing another frontend client.
- Compatibility imports are acceptable in Gate 5 only when they are identity-preserving, rule-free and
  covered by a Gate 6 retirement inventory.

## Out of Scope

- UI redesign, new page flow, new training module or new competency semantics.
- Microservices, queues, database/schema migration or new infrastructure dependency.
- Final deletion of all global barrels, legacy handlers, flags and temporary policy edges (Gate 6).
- Push, PR, deployment, production data mutation or paid real Provider invocation.

## Open Questions

None. Approved authority docs and the Goal fix scope; conservative compatibility is the default.

## Technical Notes

- Research: `research/current-locality-and-model-registry.md`
- Baseline commit: `6be88ef7` (Gate 4 journal)
- User-owned dirty file excluded from every commit:
  `docs/superpowers/plans/2026-07-10-readiness-decision-integrity.md`
