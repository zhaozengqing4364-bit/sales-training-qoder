# 销售训练 qoder Growth Roadmap

> 日期：2026-03-23
> 目标：把 M001 之后的增长路线从“有方向”收敛为“有证据、有优先级、有最小切片”的后续 milestone 规划。

## Current System Understanding

这个项目已经不是从零做销售训练，而是在一个具备双场景训练、后台资产治理、实时语音链路、报告/回放/历史与管理分析骨架的平台上做闭环增强。当前最关键的事实有三条：

1. **M001 已把底座收紧到统一事实线**：销售训练生命周期、统一 session evidence、报告/回放/历史/趋势共享事实源、知识/PPT 更新生效链已落地。
2. **当前主风险从“能不能跑起来”转向“教得准不准、学得会不会、管理是否能持续运转”**。
3. **现有仓库已经有未来能力的骨架**：实时评分/阶段/模糊词、Persona/knowledge policy、回放/高光/综合报告、admin analytics/manager-lite 都已经存在，但很多还停在“能展示”而不是“能稳定驱动行为改变”。

## Strengths Worth Preserving

- `PracticeSession` + `ConversationMessage` + `SessionEvidenceService` 已经形成统一证据线，后续不要再做第二套 read-side scorer。
- `voice_policy_snapshot` / `knowledge-check` 已经形成材料生效 authority line，后续不要为知识真实性再发明平行证据面。
- 桌面端优先、移动端和外部集成后置的范围控制是正确的；不要提前把复杂度重新注入主链路。
- 销售与 PPT 两条 runtime 分离、报告/回放尽量共享事实源的架构边界值得继续保留。

## Top Bottlenecks Ordered by Leverage

| Candidate | User leverage | Core leverage | Evidence | Compounding | Validation ease | Blast radius | Total |
|---|---:|---:|---:|---:|---:|---:|---:|
| M002 实时教练闭环 | 5 | 5 | 5 | 5 | 4 | 2 | 22 |
| M003 知识与角色真实性 | 5 | 5 | 4 | 5 | 3 | 3 | 19 |
| M004 复盘与学习闭环增强 | 4 | 4 | 4 | 4 | 4 | 2 | 18 |
| M005 后台治理与规模化运营 | 4 | 3 | 4 | 5 | 3 | 3 | 16 |

### Why this order

1. **先做 M002**：用户已经能在训练后看报告，但训练中仍缺少稳定、克制、与最终报告一致的教练体验；这是系统从“复盘工具”到“教练系统”的最短跃迁。
2. **再做 M003**：如果实时教练继续基于泛泛对话而不是真实材料和 Persona，教练只会把用户推向“练错方向”。
3. **随后做 M004**：当训练中和训练后的判断都更可信时，再把学习证据做深，才不会把浅层总结包装成“复盘闭环”。
4. **最后做 M005**：组织运营、任务派发、资产治理、导出/集成边界都应建立在前面三条可信链已经站稳之后。

## Horizons

### Horizon A — Finish launch proof
- 完成 M001/S05, S06, S07, S08
- 把销售价值表达语义、近期变化、PPT 会后复盘和首发验收补齐

### Horizon B — Real-time coaching becomes trustworthy
- M002: 把实时评分、阶段提示、动作卡和最终报告语义收紧到同一条训练事实线

### Horizon C — Training becomes materially more real and more learnable
- M003: 让 Persona + 材料真实驱动价格/竞品/证据追问
- M004: 让回放/高光/逐轮点评/再练路径真正服务学习，而不是只做展示

### Horizon D — Product becomes operable at team scale
- M005: 恢复系统内主管动作、资产治理、组织分析、对外数据包与入口边界

## Immediate Next 3-5 Safe Execution Candidates

1. **继续完成 M001/S05**
   - 让 persona policy 与实时 UI 消费面完全对齐新的销售语义
   - 补齐 live/runtime 验证与前端 score/action surface
2. **推进 M001/S06**
   - 把主管连续变化视图建立在统一 evidence projection 上，而不是旧 weighted analytics
3. **推进 M001/S07**
   - 在最新标准 PPT 材料上做会后统一复盘，而不是另起一套报告链
4. **完成 M001/S08**
   - 做桌面端真实闭环验收与失败诊断收口
5. **M002/S01**
   - 先把实时教练 contract 与 practice 右侧面板统一到销售语义，再谈更多提示策略

## Anti-goals

- 不做第二条“实时教练专用评分线”或“管理看板专用评分线”。
- 不在 M002/M003 前就做更多组织运营 UI，掩盖训练本体还不够真实的问题。
- 不提前接入 SSO / CRM / 企业微信去制造“平台感”。
- 不用更多页面、更多榜单、更多导出替代真正的训练价值提升。

## Likely Success Signals

### User-facing
- 用户在训练中看到的“唯一动作”和训练后报告的“主问题/下一目标”一致。
- 用户在价格/竞品/证据问题上遇到的 AI 客户追问更贴近真实业务。
- 用户能从报告直接进入针对主问题的下一练，而不是只停留在阅读。
- 主管能在系统里完成低摩擦管理动作，而不是只看静态看板。

### System-facing
- 统一 evidence contract 持续覆盖 realtime/report/replay/history/admin surfaces。
- 知识命中、检索失败、Persona drift、coach degrade 等状态均有明确诊断面。
- 管理分析和组织视图改为 projection/effectiveness-backed，而不是各处自算分数。
