# Phase 8 前端 fail-closed 第一切片记录

## 本轮目标

- learner 首页不再从 catalog/unit/legacy module fallback 伪造训练入口。
- `module-path` 只接受后端 active path projection 中显式给出的模块身份；未知/legacy module fail-closed。
- admin 配置中心至少一个吞错点不再把 403/500/network 错误当成“未绑定”。
- 小范围顺手修复 `passed=null` 误显示与录音结果页 `70` 硬兜底。

## 已落地

### learner 端

- `web/src/app/(dashboard)/sales-trainer/page.tsx`
  - 删除 `CatalogSection`。
  - 页面主态改为只看 `listPaths()` 投影；无 path 时显示“新人训练路径暂未开放”空态。
  - 不再因为 `units` 仍有数据就拼 quiz/audio 目录入口。

- `web/src/lib/sales-trainer/module-path.ts`
  - 删除 legacy module 组装回退。
  - `buildModuleViews()` 在缺后端模块标识时直接返回空数组，由模块卡组件显示不可用诊断。
  - `filterPathsForHome()` 不再混入 `new_seller_goal_path` legacy 组合。

### admin 端

- `web/src/app/admin/sales-trainer/paths/page-data.ts`
  - `loadBoundArticle()` 对 404 之外的错误不再吞成 `null`。
  - 读取失败时保留 `getApiErrorMessage()` 结果，trace_id 会跟随后端错误文案一并传递。

- `web/src/lib/sales-trainer/config-center.ts`
  - 新增 `article_binding_unavailable` 诊断。
  - 绑定读取失败时，不再降级成 `article_missing`。
  - 如果 path revision 里仍能解析到文章标题，页面会保留绑定信息，同时显式展示“绑定态读取失败”警告。

### 顺手修复

- `web/src/app/(dashboard)/sales-trainer/audio/result/[submissionId]/page.tsx`
  - `getUnit()` 失败时不再伪造 `70` 分通过线。

- `web/src/app/admin/sales-trainer/audio-submissions/[submissionId]/page.tsx`
  - `passed === null` 改为显示“待判定”。
  - 失败态改为显示“待重试”，不再统一落成“否”。

## 本轮未解决

### capability / 直链 fail-open 仍在

- `SalesTrainerAdminModuleNav` 仍未接 capability。
- workbench 卡片仍未按 capability 过滤。
- `/admin/sales-trainer/*` 直链仍主要依赖页面各自接口报错，而不是统一 route-level fail-closed gate。

### admin 绑定态读取仍走 learner 端点

- 本轮只修了“吞错伪装成未绑定”。
- 真正的后续正确方向仍是提供 admin 专用的绑定态读取接口/DTO，避免 admin 页面继续借 learner 端点侧推后台配置。

## 建议后续切片

1. 给 `module-nav` / workbench links / route shell 建 capability-aware 统一过滤器。
2. 为 sales-trainer admin 增加直链 fail-closed 页面态，至少保留 capability key 与 trace_id。
3. 把 `getModuleArticle()` 的 admin 读取语义从 learner API 中拆出。
