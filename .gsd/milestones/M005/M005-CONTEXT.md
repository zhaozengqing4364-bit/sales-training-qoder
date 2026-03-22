# M005: 后台治理与规模化运营 — Context

**Gathered:** 2026-03-23
**Status:** Ready for planning

## Project Description

M005 面向系统长期运营与规模化使用。此前 milestones 先证明训练闭环、实时教练、知识真实性和复盘学习闭环成立；M005 才补齐系统内的主管动作、资产治理深度、组织化分析、后续集成边界以及桌面端之外的扩展能力。

## Why This Milestone

用户当前接受第一版主管在线下辅导、系统先不做外部集成，也先不把移动端首发绑进范围。但如果产品要被组织长期采用，就需要进一步补齐管理动作、治理能力、组织指标与后续扩展边界。M005 负责把“可用产品”推进成“可运营平台”。

## User-Visible Outcome

### When this milestone is complete, the user can:

- 主管或培训负责人在系统内完成更完整的管理动作，而不只读报告。
- 更稳定地管理训练资产、版本和组织级分析视角。
- 评估是否接入企业微信、SSO、CRM 或其它外部系统，并拥有清晰集成边界。

### Entry point / environment

- Entry point: 管理后台 `/admin/*`，必要时扩展到组织入口 / 外部集成入口
- Environment: 桌面浏览器为主，视后续决定扩展到移动端 / 企业系统环境
- Live dependencies involved: 管理后台 API、分析服务、训练资产服务、可能的外部系统接口

## Completion Class

- Contract complete means: 管理动作、资产治理、趋势分析和外部集成边界具备明确契约。
- Integration complete means: 主管动作、组织分析和训练闭环之间能真实协作。
- Operational complete means: 长期运营所需的版本、权限、扩展边界可持续演进。

## Final Integrated Acceptance

To call this milestone complete, we must prove:

- 系统内主管动作能够建立组织化训练节奏，而不是只依赖线下约定。
- 训练资产治理和组织视图支持长期迭代，而不是越用越乱。
- 需要接入的外部系统有明确边界、收益和验收标准，避免无序集成。

## Risks and Unknowns

- 过早引入组织级复杂度会分散前几个 milestone 的价值证明。
- 管理动作若没有建立在可信训练闭环之上，只会放大噪声。
- 外部系统集成会显著提高变更成本和验收复杂度。

## Existing Codebase / Prior Art

- `web/src/app/admin/*` — 现有管理后台骨架。
- `web/src/app/admin/records/page.tsx` — 训练记录管理基础页面。
- `web/src/app/admin/knowledge/page.tsx` — 知识库治理基础页面。
- `docs/business-usage-growth-analysis-2026-02.md` — 组织级采用与经理驱动建议。
- `docs/business-usage-growth-execution-playbook-2026-02.md` — 经理周节奏与组织运营执行建议。

> See `.gsd/DECISIONS.md` for all architectural and pattern decisions — it is an append-only register; read it during planning, append to it during execution.

## Relevant Requirements

- R012 — 后台治理能力支持长期运营。
- R017 — 系统内主管动作（已延期，后续收回）。
- R018 — 移动端 / 企业微信场景（已延期，后续评估）。
- R019 — 外部系统集成（已延期，后续评估）。

## Scope

### In Scope

- 系统内主管动作与组织化训练节奏。
- 更深的训练资产治理与版本化能力。
- 组织级趋势分析与运营支持。
- 外部系统 / 移动端扩展边界评估与必要接入。

### Out of Scope / Non-Goals

- 在前几个 milestone 尚未证明训练闭环时，抢先做大规模组织运营功能。
- 为了“看起来完整”而引入无明确收益的外部集成。

## Technical Constraints

- 任何组织级功能都必须建立在前几个 milestone 已经证明的训练闭环之上。
- 集成边界必须清晰，不允许把外部系统依赖提前注入核心训练链路。

## Integration Points

- Admin analytics and records.
- Training asset governance modules.
- Potential external auth / CRM / enterprise entrypoints.

## Open Questions

- 哪些组织级动作最值得系统内化，哪些继续保留在线下管理流程 — 当前倾向只内化高频、低摩擦、可验证收益的动作。
