# 组长页面与发布加固

## Goal

实现销售组长只读工作台，并完成真实界面、性能、权限、可访问性和灰度回滚验证。

## Scope

* 多团队/单团队和周期筛选。
* 新人训练路径、额外任务、风险分组和完整成员列表。
* 风险原因下钻与成员时间线，不展示排行榜或任务发布入口。
* loading、empty、no-result、permission、stale、partial、error/retry 状态。
* 按根目录 `DESING.md` 选择 Dashboard–Drilldown 页面模型，复用 Modern Soft UI token 和现有组件，避免同权卡片墙。
* API 性能预算、缓存失效、响应式、键盘、焦点和 E2E。
* feature flag、发布门禁和回滚演练。

## Acceptance Criteria

* [x] 组长 3 秒内能理解团队状态、需要关注的成员及原因。
* [x] 只有一个团队时不显示冗余选择器，多团队切换同步刷新所有区域。
* [x] 页面没有个人分数排行榜、禁用任务按钮或内部术语。
* [x] 320/375/390/430/1400px、200% zoom、键盘和长文本验证通过。
* [x] 权限、性能、E2E、灰度和回滚检查通过后才允许发布。

## Dependencies

* Parent: `../07-14-account-team-lead/prd.md`
* Requires: `../07-14-bulk-provisioning-ui/prd.md`, `../07-14-team-lead-insights/prd.md`
