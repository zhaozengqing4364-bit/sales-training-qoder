# 切片 7 实施记录

## 用户与主流程

- 学员：从唯一的“当前训练”入口查看后端投影的当前阶段、当前任务、主操作、最近进展和阻塞原因；进入五类 Activity；长任务可离开并从通知/任务中心恢复。
- 培训负责人/经理：在既有统一管理工作台中通过服务端筛选和分页处理学员及复核队列，不创建第二套管理界面。
- 普通用户界面只使用业务语言；Realtime 客户语音对练不进入导航或首发 Activity 注册表。

## 权威与页面模型

- Journey、门禁、进度、主操作和 Activity 可用命令继续由后端 Projection/Application Service 唯一提供；前端只做 DTO 归一化和用户语言 ViewModel 映射。
- 五类 Activity 继续使用一个 `ActivityShell` 和封闭 Runner 注册表；Runner 只执行后端公开命令，不自行判定通过、权限或下一活动。
- 长任务状态真源为 PostgreSQL Durable Task；通知真源为持久化 Notification；正式结果仍落到对应 Activity/Outcome/Dossier，而不是只存在于通知文案。
- 学员入口采用服务端首屏读取，客户端仅负责交互、恢复刷新和后台状态更新。

## 状态矩阵

- Journey：loading、未分配、active、待处理、blocked、completed、stale、permission/error recovery。
- Activity：loading/slow、idle、submitting、background processing、poll degradation、recoverable/terminal failure、cancelled、offline、conflict、success。
- 通知/任务中心：loading、empty、filtered no-result、partial data、terminal task、retry/cancel availability、result location。
- 管理列表：loading、empty、filtered no-result、error/retry、URL filter、server pagination、permission boundary。

## 性能与验证目标

- Journey 首屏 p75 ≤ 2s；普通 API p95 ≤ 500ms；Coach 1.5s 内出现可见运行反馈；Audio finalize ≤ 2s；Dossier base ≤ 2s。
- 本切片以服务端首屏、无重复请求、有界列表/轮询、隐藏页降频和针对性渲染检查提供开发证据；真实 p95、并发压测和最终全量门禁由切片 8 执行。
- 仅运行修改相关 ESLint、TypeScript、Vitest/Pytest 和针对性浏览器检查；不在本切片运行全量构建或全量测试。

## 实施计划

1. 收口学员导航、服务端 Journey 首屏和面向任务的 Journey/Activity ViewModel。
2. 实现本人范围的持久通知和有界任务列表，增加通知/任务中心及任务结果恢复路径。
3. 补齐统一 Shell 状态、Coach 稳定视口、音频 transcript/恢复说明及可访问性细节。
4. 将学员/复核大列表收口为服务端分页与稳定 URL 状态，避免重复/瀑布请求。
5. 执行针对性静态、组件、接口与实际渲染验证；更新父任务证据、Spec 与合同。

## 保守假设与偏差

- 不重做视觉系统、不制作原型；只复用现有 token、组件、圆角、颜色和布局模式。
- 不删除旧路由源码；本切片先让旧入口不可达，物理清理、架构门禁和重定向清除留给明确的切片 8。
- 通知只承担提醒和恢复入口，不复制 Activity/Outcome/Dossier 正式业务结果。
- 若 Browser 插件不可用，按前端验证技能使用仓库现有 Playwright，并把缺失原因和残余风险记录在本文件。
- 用户明确禁止自动 commit/push/PR；Trellis 收口使用 `--no-commit`。

## 历史问题与未纳入事项

- 旧 `/training`、排行榜、旧 Journey Phase/Module 类型和旧 Realtime 类型仍存在于代码库；本切片仅移除学员可见入口，切片 8 按 Clean Cut 清理。
- 现有通用 Dashboard/Sidebar 仍含历史品牌装饰；本切片不做全站品牌重塑，只移除与新人训练单入口直接冲突的导航和装饰性 AI 表述。

## 执行历史

- 2026-07-17：完成 Trellis 激活、任务校验、项目规范/设计规范注入和 CodeGraph 优先链路探索；确认主要缺口为客户端 Journey 首屏、未挂载通知中心、任务列表缺失、管理列表 URL/分页不完整及 Coach 固定视口未收口。
- 2026-07-18：将学员 Journey 改为服务端首屏投影，统一五类 Activity 的 Shell、状态、任务恢复和用户语言错误；补齐持久通知/任务中心、音频 transcript/本地草稿/分段上传、Coach 稳定视口、隐私安全 UX 事件及学员单一导航。
- 2026-07-18：新增管理端 v2 学员列表/详情查询，以 `PathRevision -> Stage -> ActivityDefinition` 的 Journey Projection 为唯一读模型，并迁移管理学员、团队列表和团队详情消费者；列表筛选、排序、分页由服务端执行，1 行与 7 行 fixture 的 SELECT 数保持不变。
- 2026-07-18：实际启动本地前后端，使用标准训练包种子验证学员入口、Lesson、Quiz、Audio、AI Coach、异步客户场景录音，以及管理总览、路径、学员、题目、复核档案。15 个管理桌面/移动路由全部返回 200，控制台错误、网络错误、内部术语、缺失正文和横向溢出均为 0；学员与五类 Activity 共保存 12 张桌面/移动截图，管理端保存 15 张截图。
- 2026-07-18：以 8 个新浏览器上下文测得 Journey 主操作可见 `p75=834.8ms`；每个 API 预热后顺序采样 30 次，Journey、Dossier、本人任务列表、管理学员列表 `p95` 分别为 `20.4ms`、`17.2ms`、`11.0ms`、`14.4ms`，失败数均为 0。Journey 首屏浏览器 GET API 为 0，仅有一个非阻塞 UX 事件 POST。

## 主要实现与证据

- 后端：Journey 共享投影、本人范围 Durable Task/Notification 查询、通知 API、转写批量投影，以及对象级权限保护的管理学员列表/详情 v2 API。
- 前端：服务端优先的 Journey、DTO → Domain → ViewModel、统一 Activity Shell、任务与通知恢复页、音频草稿/上传恢复、Coach 固定工作区、管理端 URL 筛选与分页，以及封闭且不含敏感内容的 UX 事件词表。
- 合同与规范：更新 `docs/api-contract/newcomer-training-v2.md`、`docs/newcomer-foundation-contract-index.md`、`docs/testing.md` 和 `.trellis/spec/frontend/newcomer-foundation-view-models.md`。
- 浏览器证据位于 `playwright-audit/`；性能原始样本位于 `playwright-audit/newcomer-training-performance-report.json`。

## 验证结果

- `backend/.venv/bin/ruff check backend/src/newcomer_training/admin_queries.py backend/src/newcomer_training/journey.py backend/src/foundation_admin_api.py backend/tests/unit/newcomer_training/test_admin_api.py`：通过。
- `cd backend && ./.venv/bin/pytest --no-cov -q tests/unit/newcomer_training/test_journey_projection.py tests/unit/newcomer_training/test_admin_api.py`：`13 passed`；仅有既有 passlib/crypt 弃用警告。
- `cd web && npx tsc --noEmit`：通过。
- `cd web && npx vitest run <26 个与 Journey、Activity、任务、通知、音频、Coach、管理列表、ViewModel 和错误映射直接相关的测试文件>`：`26 files / 100 tests passed`。
- `cd web && npx eslint 'src/app/admin/sales-trainer/readiness/[learnerId]/page.tsx' src/components/newcomer-training/journey-home.tsx src/lib/newcomer-training/ux-events.ts tests/e2e/newcomer-training-performance.spec.ts tests/e2e/newcomer-training-admin.spec.ts src/components/admin/newcomer-training/question-review-workspace.tsx`：通过。
- `cd web && SMOKE_REUSE_EXISTING_STACK=1 PLAYWRIGHT_SKIP_BROWSER_INSTALL=1 SMOKE_EVIDENCE_PREFIX=slice7-experience CI=1 npx playwright test tests/e2e/newcomer-training-learner.spec.ts tests/e2e/newcomer-training-admin.spec.ts --reporter=dot`：`4 passed`。
- `cd web && SMOKE_REUSE_EXISTING_STACK=1 PLAYWRIGHT_SKIP_BROWSER_INSTALL=1 SMOKE_EVIDENCE_PREFIX=slice7-performance CI=1 npx playwright test tests/e2e/newcomer-training-performance.spec.ts --reporter=dot`：`1 passed`。
- `python3 .trellis/scripts/task.py validate .trellis/tasks/07-16-frontend-experience-performance`、`git diff --check` 及本切片最终针对性 ESLint：通过。
- CodeGraph impact 确认管理查询只影响 v2 管理路由；共享 Journey 投影只影响学员 Journey、管理查询及对应测试；UX 事件只影响已覆盖的 Activity/复核页面。`codegraph affected` 因共享 `foundation_admin_api` 扩展到大量历史测试，按本切片“最小验证”约束未运行无直接调用关系的全量集合。

## 偏差、未验证项与历史问题

- Browser 插件在当前环境不可用，按前端验证规范使用仓库 Playwright 完成实际渲染、桌面/移动、200% zoom、长文本、键盘/焦点、控制台、网络和横向溢出检查；没有因此降低验收范围。
- 开发机报告中的 JavaScript 是 Next.js 开发模式未压缩资源（32 个、5,987,344 bytes），不能作为生产 bundle 结论；生产构建体积、100 并发基线和完整发布性能门禁按父计划由切片 8 验证，已在 `docs/testing.md` 记录为可接受偏差。
- 首次浏览器检查遇到未热重载的旧后端进程并暴露已失去写权威的 Legacy 学员 Journey 端点；重启本地栈后，以新的 v2 学员查询迁移消费者，没有恢复 Legacy 写权威。
- 一次单文件 Pytest 因全项目覆盖率阈值而命令失败，测试本身通过；该阈值不适用于本切片局部验证，随后使用 `--no-cov` 得到 `13 passed`，未修改全局覆盖率配置。
- 最终发布 smoke 的历史 bootstrap 脚本会命中 `voice_runtime_profiles_name_key` 非幂等冲突；该问题属于切片 8 明确要求的空库/seed/启动发布门禁，本切片只记录，不顺带修复。
- 旧 `/training`、Legacy Journey/Realtime 类型、墓碑路由和物理源码仍按计划留给切片 8 Clean Cut；本切片只保证普通用户入口不可见且新链路不消费旧权威。

## 风险、发布与回滚

- 风险等级：P1/P2。核心风险是 Journey 投影共享和管理消费者迁移；对象级权限、稳定 DTO、常量查询数及桌面/移动实际渲染已覆盖。
- 发布：随切片 8 的迁移、seed、全量门禁和灰度步骤统一发布；先挂载 v2 API 和服务端页面，再验证任务/通知恢复和管理列表指标。
- 降级：Provider/长任务异常时保留 Durable Task 与业务结果位置，页面显示可恢复/等待状态；通知失败不改变正式业务结果。
- 回滚：回退本切片应用代码和路由消费者即可；本切片没有数据迁移或破坏性写入，不回滚已产生的业务数据。用户明确禁止 commit/push/PR，因此 Trellis 归档使用 `--no-commit`。
