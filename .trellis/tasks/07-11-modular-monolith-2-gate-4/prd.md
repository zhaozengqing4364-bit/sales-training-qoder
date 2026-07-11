# 模块化单体 2.0 Gate 4：Roleplay、配置与评估所有权

## Goal

把 Roleplay Contract/Situation Pack、ConfigBundle 生命周期和 Evaluation 的输入/场景选择从
Curriculum、Admin、Sales/Presentation 具体实现中中立化，使新增场景不修改 Sales runtime，
Evaluation 只消费冻结 Evidence、Roleplay Contract、Ruleset 和 Scenario Adapter，同时保持当前
REST、WebSocket、冻结快照、Roleplay hash、评分和报告完全兼容。

## What I already know

- Gate 0A–3 已完成、提交并归档；Gate 3 canonical gate 自然通过。
- 用户已批准 Modular Monolith 2.0 目标设计，并授权在不询问的情况下持续实施全部 Gate。
- 当前 Roleplay compiler 在 curriculum 下，ConfigBundle lifecycle 在 admin 下，Evaluation 有
  `admin/curriculum_practice/presentation_coach/sales_bot` 四条具体实现反向边。
- Gate 4 只做模块化单体内的所有权和依赖迁移，不拆服务、不改数据库部署、不调用真实 Provider。
- 详细证据见 `research/current-ownership-and-seams.md`。

## Requirements

### Neutral Roleplay bounded context

- 新增顶层 `roleplay` package，拥有 schema/version、immutable DTO、hash/freeze、compiler、
  disclosure state、turn context、compliance decision 和 Situation Pack domain contract。
- Roleplay domain 不导入 curriculum、agent、sales_bot、presentation_coach、evaluation 或 admin。
- Curriculum 通过 reference/Situation Pack adapters 提供发布资产；Sales、Presentation 和
  Evaluation 只消费 Roleplay public API。
- 旧 `common.roleplay_contracts` 与 curriculum import path 在 Gate 4 是命名 compatibility
  adapter；默认生产路径使用中立实现，单 flag 可回滚，Gate 6 依据消费者证明删除。
- 历史 `contract_hash`、Situation Pack content hash、frozen snapshot 和 record-only sidecar
  语义逐字节保持。

### Configuration Governance

- 新增顶层 `configuration_governance` package，拥有 ConfigBundle DTO、adapter/repository ports、
  draft/validate/preview/publish/rollback/disable/version/audit orchestration。
- `admin` 只保留权限、HTTP payload/response、事务提交和 inventory adapter 组合。
- Evaluation/Curriculum 不导入 Admin；只通过自己的 immutable binding projection port 读取
  `bundle_id/version_id`。
- 发布/回滚 Situation Pack 仍同步 head projection；失败诊断、审计 reason/trace 和现有 API
  错误码保持不变。

### Evaluation Evidence and Scenario ports

- Evaluation 定义 immutable `SessionEvidence`、`EvaluationScenarioInput/Result`、
  `SessionEvidencePort` 和 `ScenarioEvaluationPort`。
- SQL Evidence adapter 从冻结 PracticeSession、ConversationMessage 和 audit rows 组装 Evidence；
  不读取 latest 资产重拼。
- Presentation/其他场景通过 application-root composition 注册 adapter；Evaluation 不直接导入
  场景 service/ORM/context manager。
- 缺少 adapter、证据不足、旧 session 缺字段时保持可诊断的 non-evaluable/fallback 行为；不得
  生成虚假低分或完整报告。
- 报告持久化继续单 writer、幂等；reconnect 不重复评分或报告。

### Architecture and rollout

- `module-dependency-policy.yaml` 声明新 package 和目标稳定方向；所有临时例外包含 owner、reason、
  retire_when、expires_on。
- Gate 4 删除 `evaluation -> admin/curriculum_practice/presentation_coach/sales_bot` 四条实际边和
  对应 stale exceptions；不扩大任何 baseline SCC。
- 每条默认迁移路径都有一个构造期 flag、命名 Legacy rollback 和 differential tests；Gate 6
  清除无消费者 flag/compatibility。
- 不改变外部 REST/WS、close code、二进制音频、权限、RuntimeGate、KB fail-closed、epoch、评分、
  报告和 OpenAPI。

## Acceptance Criteria

- [ ] Golden fixtures 证明迁移前后 Roleplay/Situation Pack hash、frozen snapshot、disclosure、
      compliance decision 完全一致。
- [ ] `roleplay` public API 可被 Curriculum、Sales、Presentation、Evaluation 使用，且其 AST
      imports 不含任何场景/Admin package。
- [ ] Neutral compiler 通过发布/legacy/缺资产/版本冲突/prompt 冲突/visible-hidden/trigger matrix；
      Legacy flag differential 无差异。
- [ ] `configuration_governance` lifecycle 覆盖 draft/validate/preview/publish/rollback/disable、审计、
      Situation Pack projection，并与现有 Admin API contract 一致。
- [ ] Admin API 只做 delivery/permission/transaction；Evaluation/Curriculum 实际 import graph 不再
      指向 Admin。
- [ ] Evaluation ports 覆盖 Sales 和 Presentation；缺 Evidence 返回 non-evaluable，报告 writer
      仍幂等且 Presentation payload differential 一致。
- [ ] AST inventory 中不存在 `evaluation -> admin/curriculum_practice/presentation_coach/sales_bot`。
- [ ] 新场景可通过注册 `ScenarioEvaluationPort` 接入，无须修改 Sales runtime 或 Evaluation core。
- [ ] architecture guard 通过、SCC 不扩大、消失 exception 同提交删除。
- [ ] Roleplay/config/evaluation focused tests、affected tests、unit+contract、Vitest、selected E2E 和
      changed coverage 均满足 canonical gate。
- [ ] Brooks audit 和 Trellis check 阻塞 finding=0，文档/ADR/roadmap/Trellis/代码事实一致。

## Definition of Done

- TDD Red → Green → Refactor 证据写入 `implementation-notes.md`。
- 每个切片有聚焦测试、Ruff、mypy、architecture impact 和逻辑化本地 commit。
- `.trellis/spec/backend/` 新增 Gate 4 可执行 7-section contract。
- `docs/architecture.md`、设计、ADR、roadmap、Gate 4 实施计划同步真实完成证据。
- `critical-quality-gate.sh` 从 clean start 自然 exit 0；不调用收费真实 Provider。
- Trellis task 完成验证、归档和 journal 记录；工作区只剩用户的 readiness 文档改动。

## Technical Approach

采用 Strangler + Dependency Inversion：先以 Golden fixtures 固化行为，再建立两个中立 bounded
context 和 Evaluation-owned ports，随后逐个迁移调用者。兼容入口只转发，不新增规则；所有
composition 在 root 或 delivery adapter 完成。Gate 4 保留可回滚路径，Gate 6 在完整影响证明后
删除旧 owner、Mixin 写入和 stale exception。

### Public interfaces

```python
@dataclass(frozen=True, slots=True)
class RoleplayContractSnapshot:
    schema_version: str
    contract_hash: str
    payload: Mapping[str, object]

class RoleplayReferenceReader(Protocol):
    async def read(self, asset_type: str, asset_id: str) -> Mapping[str, object] | None: ...

class SituationPackPort(Protocol):
    def get_published(self, code: str) -> SituationPackSnapshot | None: ...

class ConfigBundleAdapter(Protocol):
    bundle_key: str
    async def bundle(self) -> ConfigBundleSnapshot: ...
    async def versions(self) -> list[ConfigVersionSnapshot]: ...

class SessionEvidencePort(Protocol):
    async def load(self, session_id: str) -> SessionEvidence: ...

class ScenarioEvaluationPort(Protocol):
    scenario_type: str
    async def evaluate(self, evidence: SessionEvidence) -> EvaluationScenarioResult: ...
```

Concrete signatures may use immutable mapping/tuple fields but must retain these responsibility
boundaries. ORM rows are not part of any public domain port.

## Decision (ADR-lite)

**Context**: Current code implements the right behavior but assigns domain authority to Curriculum,
Admin and concrete scenario packages, creating cycles and making each new scenario touch Sales/Evaluation.

**Decision**: Introduce `roleplay` and `configuration_governance` bounded contexts; let Evaluation own
its Evidence/Scenario ports; compose concrete adapters at the application boundary. Use compatibility
adapters and differential tests during Gate 4, then retire them in Gate 6.

**Consequences**: More explicit DTO mapping and composition code is required, but each module exposes a
small stable surface, historical hashes stay frozen, and future scenarios/providers do not expand the
Sales/Evaluation change radius.

## Assumptions

- Existing database schema and `Base.metadata` remain unchanged until Gate 5 physical model split.
- Bundled defaults remain the fallback authority when governed config is missing/disabled/invalid.
- A missing real external Provider is not a Gate 4 blocker; local fakes and existing conditional skip are
  the acceptance surface.

## Out of Scope

- Microservices, queues, distributed transactions or new infrastructure dependencies.
- Frontend Training Journey locality and `common/db/models.py` physical split (Gate 5).
- Final deletion of Presentation Sales inheritance and all compatibility flags (Gate 6).
- Production deployment, push, PR, production data mutation or paid Provider invocation.

## Open Questions

None. The approved authority documents and Goal resolve scope and trade-offs; conservative compatibility
is the required default.

## Technical Notes

- Plan: `docs/superpowers/plans/2026-07-11-gate-4-domain-ownership.md`
- Architecture policy: `docs/architecture/module-dependency-policy.yaml`
- Gate 3 baseline commit: `5647155c` (journal after archive); Gate 4 starts from this code truth.
