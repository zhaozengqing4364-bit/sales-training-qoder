# S04: PPT 页级学习证据 — UAT

**Milestone:** M004
**Written:** 2026-03-26T03:57:14.146Z

# S04: PPT 页级学习证据 — UAT

**Milestone:** M004  
**Written:** 2026-03-26T03:53:51Z

## UAT Type

- UAT mode: route-driven + artifact-driven
- Why this mode is sufficient: S04 的交付点全部落在现有 PPT report / replay authority line 上，核心验收是“同一份 presentation_review page-level evidence 是否能在当前 report 和 replay route 上被看懂、被定位、被降级说明”。因此本 UAT 以现有 API payload、当前页面路由、query-param page anchor 和 transcript jump 为主，不需要新增独立 PPT 页面或新 API。

## Preconditions

- 存在一个已完成的 presentation session，且 canonical report payload 中包含 `scenario_type: "presentation"` 与 `presentation_review.page_summaries[*].issue_clusters`。
- 至少有一页带可读的 page-level issue cluster（例如 `missing_point` / `off_page` / `forbidden_word` / `weak_qa_handling`）。
- 当前 `/practice/{sessionId}/report` 和 `/practice/{sessionId}/replay` 路由可访问。
- 如果要验证 degraded path，需准备一个：
  - 缺少 `transcript_metadata.page_number` 的历史 presentation session，或
  - 一个带 `page=9&page_anchor_status=missing&page_anchor_reason=page_not_found` 之类 query 的 replay deep link。

## Smoke Test

1. 打开一个带 PPT 页级 issue cluster 的 `/practice/{sessionId}/report`。
2. 在 report 页确认能看到“页级问题总览 / 每页问题簇 / 证据说明”。
3. 从 report 进入 `/practice/{sessionId}/replay?page=2&page_anchor_status=resolved`。
4. **Expected:** replay 页面在当前 route 内显示 PPT page banner、SlideViewer、当前页问题簇，并允许点击“定位到第 N 轮”跳到对应 transcript turn。

## Test Cases

### 1. report API / payload 必须能给出页级问题簇与聚合 diagnostics

1. 调用 canonical `/api/v1/practice/sessions/{sessionId}/report`。
2. 检查 `scenario_type`。
3. **Expected:** `scenario_type === "presentation"`。
4. 检查 `presentation_review.page_summaries[*].issue_clusters`。
5. **Expected:** 至少一个 `page_summary` 带有非空 `issue_clusters`；每个 cluster 至少包含：
   - `issue_type`
   - `summary`
   - `evidence`
   - `turn_numbers`
   - 需要时的 `linked_points` / `linked_phrases` / `related_page_numbers`
6. 检查 `presentation_review.diagnostics.page_issue_cluster_count/page_issue_types`。
7. **Expected:** 聚合计数与页级 cluster 总数一致，`page_issue_types` 反映本场 PPT 实际命中的问题类型。
8. 检查 shared completeness / diagnostics 是否同步带出页级聚合信息。
9. **Expected:** report/read-side completeness 不再只有“页码齐不齐”，还能回答“本场一共命中了哪些页级问题簇”。

### 2. 当前 report route 必须在现有 PPT 分支上显示页级问题总览与逐页证据

1. 打开 `/practice/{sessionId}/report`。
2. 确认页面进入的是现有 PPT report 分支，而不是 sales-only 区块。
3. **Expected:** 页面出现 PPT 相关 heading / summary，不出现 sales-only 的 `main_issue` / `next_goal` 训练结论卡片。
4. 检查页级 overview 区域。
5. **Expected:** 能看到页级问题总数、问题类型 chips 或等价聚合文案，来源应与 `presentation_review.diagnostics.page_issue_cluster_count/page_issue_types` 对齐。
6. 展开或阅读每个 `page_summary` card。
7. **Expected:** 每页都能直接看到：
   - 当前页 summary
   - 已覆盖 / 仍缺失的 required points（如有）
   - issue cluster summary
   - 对应 evidence lines
   - 受影响的 points / phrases / related pages（如有）
8. **Expected:** 页面没有跳到第二个 PPT 学习页面，也没有再造一套 report-only 的 issue 数据结构。

### 3. 当前 replay route 必须复用 shared replay payload 显示页定位、SlideViewer 与问题簇

1. 打开 `/practice/{sessionId}/replay?page=2&page_anchor_status=resolved`。
2. **Expected:** replay 页面仍是当前 `/practice/{sessionId}/replay` route，不是新建的 PPT-only replay route。
3. 检查 banner。
4. **Expected:** 页面显示类似“已定位到第 2 页 / 已打开报告引用的课件页，并同步展示该页问题簇与相关回合”的 resolved banner。
5. 检查当前页上下文。
6. **Expected:** 页面同时存在：
   - SlideViewer 或其文本 fallback
   - 当前页 summary
   - 当前页 issue cluster 列表
   - transcript message list
7. **Expected:** replay 上的 PPT issue 数据来自 shared replay payload 的 `presentation_review`，而不是 report 页面重新 fetch 一套本地拼装数据。

### 4. 从页级问题簇跳到 transcript turn 时，当前 turn 必须高亮且可读

1. 在 replay 页找到一个带 `turn_numbers` 的 issue cluster。
2. 点击“定位到第 N 轮”。
3. **Expected:** 页面滚动到对应 transcript message，目标 turn 高亮或有等价 active state。
4. **Expected:** transcript 中能读到与该 issue cluster evidence 相呼应的真实表达，不是跳到随机 turn。
5. 如果该页有多个 issue clusters，分别点击多个 turn jump。
6. **Expected:** 每次跳转都只更新当前 active turn，不会把 replay 带离当前 PPT route。

### 5. 缺页或坏锚点时，replay 必须显式降级，不得静默失败

1. 打开一个带坏锚点的 replay deep link，例如：
   `/practice/{sessionId}/replay?page=9&page_anchor_status=missing&page_anchor_reason=page_not_found`
2. 检查 banner 与当前页状态。
3. **Expected:** 页面明确显示“未找到第 9 页，已回退到第 1 页继续查看”之类 missing/degraded 文案。
4. **Expected:** 页面仍保留可读的默认页 summary / issue clusters / transcript，不应空白，也不应假装已经精确定位成功。
5. 如果使用缺少 page metadata 的历史 presentation session 打开 report / replay。
6. **Expected:** report/replay 都应显示明确 degraded note，说明当前只能做 summary-level fallback，不能伪造逐页定位或问题簇。

### 6. 缩略图缺失不应破坏 PPT replay 的学习证据阅读

1. 在 replay 页打开一个 thumbnail 不可用或加载失败的 presentation page。
2. **Expected:** SlideViewer 即使拿不到 thumbnail，也仍保留当前页 summary、issue clusters、turn jump controls 或文本 fallback。
3. **Expected:** 缩略图失败属于 best-effort degraded，不应把整块 PPT replay 区域打成无法继续使用。

## Edge Cases

### 页级问题簇为空的页面应保持“可读但不夸大”

1. 打开一个 `page_summary.issue_clusters=[]` 的页面。
2. **Expected:** 页面可以继续展示该页 summary、matched/missing required points，但不会硬造一个不存在的问题簇。

### 相同 issue_type 在多页出现时，overview 与逐页 evidence 都要保真

1. 准备一个在多页都触发同类问题（例如多个 `missing_point`）的 presentation session。
2. **Expected:** overview 中的 `page_issue_types` 只做类型聚合；逐页卡片仍按页展示真实 evidence，不会把不同页的问题合并成一张丢页码的总卡。

## Failure Signals

- report API 没有 `presentation_review.page_summaries[*].issue_clusters`，或 diagnostics/completeness 看不到页级问题簇聚合信息。
- report 页面为了显示 PPT 学习证据又新增了第二个 PPT-only 页面/面板，而不是复用现有 shared report route。
- replay 页面不消费 `scenario_type/presentation_id/presentation_review`，导致 PPT route 仍只能看 transcript，不能看 slide context 和页级问题簇。
- page anchor 缺失时页面静默失败、跳到错误页、或直接空白，而不是保留显式 degraded / missing banner。
- 点击 issue cluster 的 transcript jump 后，没有跳到对应 turn，或高亮状态与实际问题 evidence 对不上。

## Requirements Proved By This UAT

- 直接证明了 M004/S04 的 slice goal：在当前 PPT report / replay routes 上，learner 能看见“哪一页有哪些问题簇，以及为什么要重讲”。
- 间接强化了 R008 的 shared presentation review authority line：PPT 复盘不再只是整场泛总结，而能给出页级学习证据。

## Not Proven By This UAT

- 不证明 sales route 的完整学习闭环；那属于 M004/S05 的 combined sales + PPT final verification。
- 不证明 learner 已经基于这些页级问题成功完成下一轮 live 演讲改讲；那也属于 S05 的 live loop proof。

## Notes for Tester

- 这是一条“现有 route 增强”slice：report 与 replay 都必须停留在当前 entry chain 上，不接受新 PPT 学习页或第二条 replay authority line。
- 遇到缺页码、坏 page anchor、缩略图不可用时，正确行为是显式 degraded / fallback，而不是安静失败或硬拼假定位。

