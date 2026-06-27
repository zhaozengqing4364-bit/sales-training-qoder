# PRD: ADR — dual-read 观察窗未启用状态记录

## 背景

P0/依赖漏洞任务期间,风险扫描发现 Config Asset Center B1 切换的关键不变量"dual-read 零 mismatch 观察窗"在生产从未真正运行:

- 开关 `SITUATION_PACK_DUAL_READ` 默认 `False`(`backend/src/common/config.py`)
- 审计写入 `record_dual_read_projection_mismatch_audits` 只在 `SituationPackRepository.from_database` 内同步调用,且依赖开关开启
- `dual_read_promotion_gate` 的 `promotion_ready` 查 `SystemLog.action == situation_pack_dual_read_mismatch`:开关关 → 审计从不运行 → 永远零 mismatch 记录 → gate 默认放行

CONTEXT.md 第 144 行承诺"B1 切换须满足 #96 定义的 ≥14 日双读零 mismatch 观察窗后方可人工批准"。但代码现状使该承诺**可被静默满足**(无人写日志即零 mismatch),属于 AGENTS.md §VII.1 反模式变体(在门禁层用缺席证明安全)。

## 决策(本任务)

**只记债,不改代码**。撰写一条 ADR 记录以下决策点:

1. **现状声明**:dual-read 观察窗在当前生产环境未启用(开关默认关);B1 切换的"零 mismatch"承诺尚未被真实观察验证过。
2. **启用前置条件**:B1 切换前必须显式设置 `SITUATION_PACK_DUAL_READ=true`,并维持 ≥14 日(常量 `PROMOTION_WINDOW_DAYS`),期间 `SystemLog` 须有审计记录证明审计在运行(非空窗)。
3. **风险标注**:当前 gate 的 promotion_ready 在开关关时可被静默满足——这是已知技术债,不在本任务修(修法见"未来工作")。
4. **与 ADR 2026-05-27 的关系**:本 ADR 补充 2026-05-27 的 B2 HITL 治理,明确 B1 切换的观察窗启用前提。

## 范围

### 必改
- 新建 `docs/adr/2026-06-27-dual-read-observation-window-status.md`(或等价日期命名):记录上述 4 个决策点。

### 不改(明确边界)
- 不改 `config.py` 默认值(开关默认关是分期交付的合理状态)
- 不改 `dual_read_promotion_gate.py`(gate 逻辑本身正确,问题在"靠缺席证明"——记债而非改代码)
- 不在 ADR 里规定"何时切 B1"(那是业务决策,不在本任务)

## 未来工作(ADR 里标注,不在本任务做)

- 给 `dual_read_promotion_gate` 加"发布时即时比对 frozen vs latest + fail-fast"兜底,让"零 mismatch"从缺席证明变为当场验证。
- B1 切换时增加"开关必须开启 + 审计日志非空"的硬前置校验。

## 验收标准

- [ ] ADR 文件创建,遵循仓库 ADR 格式(参考 `docs/adr/2026-05-27-*.md`)
- [ ] 4 个决策点全部覆盖
- [ ] 引用 CONTEXT.md 第 144 行 + ADR 2026-05-27
- [ ] 标注"未来工作"两项,不与当前任务混淆

## 不属于本任务

- P3 WebSocket 深查(下一任务)
- dual-read gate 代码修复(未来工作)
