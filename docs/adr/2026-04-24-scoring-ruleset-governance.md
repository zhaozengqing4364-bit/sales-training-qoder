# ADR 2026-04-24: 评分 ruleset 治理与报告口径版本化

## Status

Accepted for the sales-training trust/governance roadmap.

## Context

销售训练系统已经有实时评分、报告评分、趋势对比和下一次练习推荐，但评分维度、阈值、推荐口径与 PPT/销售场景规则仍分散在运行时代码、env JSON、前端兜底数组和历史报告展示逻辑中。继续让新规则直接覆盖现有算法会带来三类风险：

1. **历史报告不可解释**：新权重发布后，旧报告若被静默重算，学员看到的分数与当时训练证据不再一致。
2. **不可评估场景被伪分**：证据缺失、音频/转写失败或规则不适用时，如果仍给出数值分，会误导学员和运营。
3. **规则发布不可审计**：教研/运营需要预览规则影响，管理员需要发布/回滚，但当前缺少版本、dry-run、审批和审计边界。

本 ADR 仅确立治理决策和执行边界；不直接修改评分算法，不启用自适应难度，不重算历史报告。

## Decision

采用“版本化 ruleset + 报告生成时固化口径 + 发布前 dry-run”的治理模型。

1. **统一 ruleset schema**
   - 至少覆盖销售对练与 PPT 训练两类 subject。
   - 每个 ruleset 声明 `ruleset_id`、`version`、`subject`、`status`、`dimensions`、`weights`、`thresholds`、`non_evaluable_reasons`、`evidence_requirements`、`fallback_policy`。
   - 权重总和、分值范围、必需证据、枚举字段由 schema 校验；非法规则不可发布。

2. **报告保存生成时口径**
   - 新报告必须记录 `ruleset_version`、`score_basis`、`evidence_completeness`。
   - `score_basis` 描述评分来源与关键规则摘要，例如 `sales_v1: completed transcript + realtime score snapshot`。
   - `evidence_completeness` 描述证据充分性，例如 `complete`、`partial_transcript`、`missing_audio`、`insufficient_turns`。
   - 旧报告不因新 ruleset 发布而重算；展示层按报告已保存的版本和证据摘要解释分数。

3. **不可评估优先给 reason，不伪分**
   - 当证据不满足 ruleset 的 `evidence_requirements` 时，结果必须进入 non-evaluable 路径。
   - non-evaluable 输出必须包含稳定 reason code 和用户可理解说明。
   - 不允许为了趋势、推荐或排行榜补一个“看起来合理”的默认分。

4. **发布前 dry-run，不影响 active version**
   - 教研/运营可提交 draft ruleset 并选择历史样本做 dry-run。
   - dry-run 输出新旧 ruleset 分数差异、不可评估变化、受影响样本数量和代表性样本。
   - dry-run 不写入 active ruleset，不修改报告，不触发推荐结果持久化。

5. **权限与审计**
   - 教研/内容管理员可以创建 draft、编辑 draft、发起 preview/dry-run。
   - 只有管理员或后续审批流允许 publish/rollback。
   - publish/rollback 必须记录 actor、before、after、version、reason、trace_id、created_at。

## Consequences

### Positive

- 报告、趋势、推荐都能说明“按哪一版规则、基于哪些证据”生成。
- 规则演进可以先 dry-run，再小步发布；线上历史报告保持稳定。
- 不可评估场景明确暴露证据缺口，避免伪分和错误激励。

### Negative

- 初期需要补 ruleset schema、版本表、审计记录和管理入口，交付速度慢于直接改算法。
- 展示层需要兼容旧报告缺少 `ruleset_version` 的情况，并给出 legacy 说明。
- dry-run 需要采样策略和运行资源预算，不能默认全量扫描所有历史数据。

## Rejected Options

- **直接修改现有评分常量** — 拒绝，因为会让历史报告口径和线上推荐不可解释。
- **只用 env JSON 管理评分规则** — 拒绝作为长期方案，因为缺少后台校验、预览、权限和审计；可作为过渡只读 seed 来源。
- **发布后批量重算历史报告** — 拒绝，因为 PRD 明确要求旧报告不重算，且重算会改变学员已看到的结果。
- **在证据不足时给默认分** — 拒绝，因为不可评估必须给 reason，不得伪分。

## Follow-up Implementation Plan

1. 建立 ruleset schema 与默认 seed：销售 ruleset、PPT ruleset 各一份 `published` 基线。
2. 增加报告生成字段：`ruleset_version`、`score_basis`、`evidence_completeness`；旧报告展示为 `legacy_unversioned`。
3. 增加 dry-run API 与后台预览页：只读运行，不写 active version。
4. 增加 publish/rollback API：admin-only mutation，写审计日志。
5. 增加测试矩阵：可评估、不可评估、旧报告兼容、新旧 ruleset dry-run、非法 schema publish rejected、rollback。
