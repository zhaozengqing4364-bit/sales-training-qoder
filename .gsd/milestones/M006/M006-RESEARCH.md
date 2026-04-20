# M006 Research — 后台抽象与可复用化

## Question
M005 已经把后台治理链路做出来，但这些能力是否已经抽象成稳定可复用 seam？如果后续继续新增 admin 功能、资产类型或 supervisor workflow，现状能否低成本复用？

## Findings

### 已成型的共享 seam
1. **Completed-session evidence seam**：`SessionEvidenceService` + `HistoryService` 已经把 completed-session 事实线统一给 report / replay / history / admin 使用。
2. **Admin analytics aggregation seam**：`AdminAnalyticsService` 已经承接 overview / trends / leaderboard / operating-pack 聚合，而不是把语义散在 route 和页面里。
3. **Supervisor intervention durable state**：`ManagerIntervention` + admin intervention API 已经把主管重点 / 提醒状态持久化下来，`HistoryService.build_manager_intervention_results(...)` 负责 read-side 结果解释。
4. **Asset governance seam**：`RuntimeStatusService.build_asset_governance_summary(...)` 与前端 `AssetGovernanceSummaryCard` 已经把 impact / recent change / health 收口成统一治理语言。

### 还未完全抽干净的重复点
1. **前端 linked-asset 解析重复**：analytics 页和 user detail 页各自维护 `parseLinkedAssetChanges` / `assetLabel` 逻辑。
2. **weekly drill-in URL/context 重复**：manager-lite、users list、user detail 各自处理 `focusBucket` / `focusIssueFamily` / `focusNote`。
3. **governance_summary 弱类型**：前端仍有多处 `Record<string, unknown>`，说明 contract 已共享、但强类型消费还没闭合。
4. **领域语义与状态耦合**：supervisor intervention 目前更像 sales/admin 专用骨架，而不是可扩展 workflow engine。

## Recommended Refactor Order
1. 把 admin drill-in context 提升成 shared helper。
2. 把 `linked_asset_changes` 提升成共享 typed parser + UI。
3. 把 `governance_summary` 做成端到端强类型。
4. 抽 `ManagerInterventionService` 和 read-side result resolver。
5. 引入 asset registry / adapter seam。
6. 最后收口 shared admin read-model adapters，并用完整 regression pack 证明无行为漂移。

## Planning Conclusion
建议以 **一个里程碑** 完成这批工作，而不是继续把这些重复点混进后续 feature 里。里程碑目标不是新增页面，而是把现有 M005 路由家族的共享 contract、shared parser、service seam、asset registry 和 regression proof 补齐，使后续新增更接近“沿 seam 扩展”而不是“复制页面 glue code”。

## Post-Refactor Proof (T03)

T03 已按计划重跑完整 current M005 admin regression pack，并在当前仓库状态下全部通过：

- Backend：`tests/unit/common/test_admin_analytics_service.py`、`tests/unit/test_support_runtime_service.py`、`tests/integration/test_admin_users_api.py`、`tests/integration/test_admin_interventions_api.py`、`tests/integration/test_asset_governance_api.py`、`tests/integration/test_rbac_access_control_api.py`、`tests/contract/test_analytics.py`
- Web：`src/app/admin/analytics/page.test.tsx`、`src/app/admin/asset-governance.test.tsx`、`src/app/admin/users/[id]/page.test.tsx`、`src/components/admin/manager-lite-panel.test.tsx`

这说明在完成 shared admin read-model adapter 收口后，当前 shipped admin route family（analytics / users / user detail / asset governance / manager-lite / intervention + RBAC seams）仍保持原有行为合同，没有因为前端 seam 提取而引入跨页语义漂移。

## Seam Lessons Locked For Next Milestone

1. **shared seam 继续保持 route-shaped，而不是再抽象成 generic dashboard state**：现在被证明稳定的是围绕 admin route family 的读模型 adapter/helpers，而不是一套跨领域状态管理框架。
2. **验收要看 route family，不看单页 helper**：后续如果触碰 `web/src/lib/admin/read-models.ts`、`web/src/lib/admin/runtime-faults.ts`，或消费这些 seam 的 analytics/users/detail 页面，必须至少重跑这组 full admin regression pack，才能证明“去重”没有换来行为漂移。
3. **backend + web 要一起回归**：前端 seam 抽取虽然发生在 `web/src/lib/admin/*`，但 acceptance 仍必须覆盖 analytics contract、RBAC、intervention、asset governance、support/runtime-linked governance 这些 backend authority line，因为 admin 页面只是这些事实线的消费面。
4. **当前 seam 的价值是把共享读模型 glue 收进 helper，同时保留页面入口语义不变**：后续扩新资产类型、drill-in launcher 或 users/detail 变体时，应继续沿这个 seam 加 helper / adapter，而不是把页面改造成新的全局 store 或第二套 admin domain contract。
