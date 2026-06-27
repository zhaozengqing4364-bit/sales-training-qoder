# ADR 2026-06-27: dual-read 观察窗未启用状态记录

## Status

**Accepted (记债).** 本 ADR 记录一个已知现状与技术债,**不改代码**。B1 authority 切换前必须满足本文档 §Decision.2 的启用前置条件。

## Context

Config Asset Center 分期落地中,Phase B1 切换的硬性前置条件之一是 [CONTEXT.md 第 144 行](../../CONTEXT.md) 承诺的:

> B1 切换须满足 #96 定义的 **≥14 日双读零 mismatch** 观察窗后方可人工批准。

代码层面的实现:

- 开关 `SITUATION_PACK_DUAL_READ` 默认 `False`(`backend/src/common/config.py`:`_env_bool("SITUATION_PACK_DUAL_READ", False)`)。
- 审计写入 `record_dual_read_projection_mismatch_audits` 仅在 `SituationPackRepository.from_database` 内同步调用,且仅在开关开启时执行。
- `dual_read_promotion_gate`(`backend/src/curriculum_practice/services/roleplay/dual_read_promotion_gate.py`)的 `promotion_ready` 判定:查 `SystemLog.action == situation_pack_dual_read_mismatch` 在 `PROMOTION_WINDOW_DAYS=14` 日窗口内是否为零。

**现状问题**:开关默认关 → 审计从不运行 → `SystemLog` 永无 mismatch 记录 → gate 的 `_has_mismatch_in_window` 永远返回 False → `promotion_ready` 在请求切换时**可被静默满足**。

这属于 [AGENTS.md §VII.1](../../AGENTS.md) 反模式变体:**在门禁层用缺席证明安全**(无人写日志即零 mismatch)。当前 `promotion_ready=True` 不代表"双读已验证一致",只代表"无人记录过不一致"。

## Purpose

1. **声明现状**:dual-read 观察窗在当前生产环境**从未真正运行过**,B1 切换的"零 mismatch"承诺尚未被真实观察验证。
2. **锁定启用前置条件**:防止未来操作者在开关未开、审计未运行的情况下误判 B1 可切换。
3. **标注技术债**:明确"靠缺席证明安全"是已知债,并将其与未来的硬前置校验工作区分。

## Decision

### 1. 现状声明

dual-read 观察窗在当前生产环境**未启用**(`SITUATION_PACK_DUAL_READ` 默认 `False`)。截至本 ADR 日期(2026-06-27),`promotion_ready` 的"零 mismatch"判定**不可作为 B1 已验证的依据**——它当前只反映"审计未运行",不反映"双读已一致"。

### 2. B1 切换启用前置条件(必须全部满足)

| # | 条件 | 验证方式 |
|---|------|---------|
| a | `SITUATION_PACK_DUAL_READ=true` 在生产环境显式设置 | 环境变量/运行时配置核查 |
| b | 开关持续开启 ≥ `PROMOTION_WINDOW_DAYS`(14) 日 | 部署时间 + 配置历史 |
| c | 观察窗内 `SystemLog` 有审计运行记录(证明审计非空窗) | 查 `situation_pack_dual_read_mismatch` 或等价审计 action 的存在性 |
| d | 观察窗内零 mismatch 记录 | `dual_read_promotion_gate.promotion_ready == True` |

**关键**:`c` 是新增的隐性条件——当前 gate 只查 `d`(零 mismatch),不查 `c`(审计是否在运行)。在 §Future Work 的硬前置校验落地前,操作者必须**人工确认 c**,不得仅凭 `promotion_ready=True` 切换 B1。

### 3. 技术债标注

当前 `dual_read_promotion_gate` 的 `promotion_ready` 在开关关闭时可被静默满足(因审计不运行 → 无 mismatch 记录)。这是**已知技术债**,本 ADR 仅记录,不在当前阶段修复(见 §Future Work)。

### 4. 与 ADR 2026-05-27 的关系

本 ADR **补充** [ADR 2026-05-27: Config Asset B2 HITL 治理](./2026-05-27-config-asset-b2-hitl-governance.md):

- 2026-05-27 定义了 B2 启动门禁与 HITL 审批边界,把 B1 authority 切换列为 **HITL-Approve**。
- 本 ADR 明确该 HITL-Approve 的**观察窗启用前提**:审批者必须先确认 §Decision.2 的 a–d 全部满足,尤其 `c`(审计在运行)——否则 HITL-Approve 缺乏事实依据。

两者不冲突:2026-05-27 管"何时需人工批",本 ADR 管"批之前双读观察窗必须真跑过"。

## Future Work(不在本 ADR 范围)

1. **硬前置校验**:在 `dual_read_promotion_gate` 增加"开关必须开启 + 观察窗内审计日志非空"的硬断言,让 `promotion_ready` 在审计空窗时返回 False 而非 True。
2. **发布时即时比对**:给 B1 切换加"frozen vs latest 即时 hash 比对 + fail-fast"兜底,使"零 mismatch"从缺席证明变为当场验证(参考 [AGENTS.md §III.4 失败可分类](../../AGENTS.md))。

以上两项属实现工作,需单独建任务,不在本记债 ADR 内完成。

## References

- [CONTEXT.md §角色扮演情景](../../CONTEXT.md) 第 144 行:B1 切换 ≥14 日双读零 mismatch 承诺
- [ADR 2026-05-27: Config Asset B2 HITL 治理](./2026-05-27-config-asset-b2-hitl-governance.md)
- [AGENTS.md §VII 反模式](../../AGENTS.md) 第 1 条
- 代码:`backend/src/common/config.py`(开关)、`backend/src/curriculum_practice/services/roleplay/dual_read_promotion_gate.py`(gate)、`situation_pack_repository.py`(审计写入)
