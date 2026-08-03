# 项目显示名改为演武场

## Goal

把产品面向用户的显示名称从「AI 智能练习平台」等旧文案改为「演武场」，只做浅层文案替换，不改路由、包名、仓库名或数据结构。

## What I already know

* 用户要求：别叫「AI 智能对练平台」了，改叫「演武场」；不要改太深，先改文字。
* 代码里实际文案是「AI 智能练习平台」（非「对练」）：
  * `web/src/app/layout.tsx` — `metadata.title`
  * `web/src/app/(auth)/login/page.tsx` — 登录副文案
* 侧栏/壳层品牌文案当前是「AI 销售教练」：
  * `web/src/components/layout/sidebar.tsx`
  * `web/src/components/layout/dashboard-shell.tsx`
* 后台可配置默认平台名是英文 `Intelligent Coach AI`：
  * `backend/src/common/business_rules/defaults.py`
  * admin settings 表单 fallback 与相关测试

## Assumptions (temporary)

* MVP 只改用户可见产品名文案；不改仓库目录名、npm package name、API path、agent 示例名「销售教练」。
* 是否同步改侧栏「AI 销售教练」与后台默认 `platform_name`，待用户确认。

## Open Questions

* 改名范围：仅「AI 智能练习平台」两处，还是连侧栏品牌与后台默认平台名一并改为「演武场」？

## Requirements (evolving)

* 用户可见产品名统一为「演武场」

## Acceptance Criteria (evolving)

* [ ] 浏览器标签页 title 显示「演武场」
* [ ] 登录页不再出现「AI 智能练习平台」

## Definition of Done (team quality bar)

* 相关文案替换完成
* 若改动默认 platform_name，同步更新对应测试断言
* 不引入无关重构

## Out of Scope (explicit)

* 仓库名 / 包名 / 路由 / 数据库 schema
* 历史审计报告、归档任务产物、specs 文档大面积回溯
* 智能体示例名「销售教练」、场景类型展示名等业务实体名

## Technical Notes

* 复杂度判定：Simple（文案替换，范围明确）
* 关键文件候选见上；最终以用户确认的范围为准
