# Findings

本文件记录 Playwright 审计、代码审计和修复回归结果。编号格式：`F-<序号>`。

## 模板

- 编号：
- 严重性：P0 / P1 / P2 / P3
- 页面 / URL：
- 截图：
- 复现步骤：
- 用户影响：
- 根因文件：
- 修复：
- 回归验证：
- 状态：Open / Fixed / Deferred

## 发现清单

### F-01

- 严重性：P1
- 页面 / URL：`/sales-trainer`、`/sales-trainer/audio/result/:submissionId`
- 截图：`playwright-audit/screenshots/L-01-desktop-sales-trainer.png`、`playwright-audit/screenshots/L-08-desktop-sales-trainer-audio-result-*.png`
- 复现步骤：以新人训练学员登录，打开新人训练入口和录音结果页。
- 用户影响：前台暴露 `E2E`、`seed`、内部评分模型等工程字段，且历史 seed 音频文件缺少可播放本地文件，录音回放请求失败。
- 根因文件：`backend/scripts/seed_newcomer_training_path.py`、`web/src/app/(dashboard)/sales-trainer/audio/result/[submissionId]/page.tsx`
- 修复：将学员/负责人 seed 账号和音频文件名改为业务可读命名；生成可播放 WAV 占位文件并写入受控本地音频目录；迁移旧 seed 录音展示名；前台学员录音结果页只显示“AI 评分”，不展示内部模型名。
- 回归验证：前台专项 Playwright 22 个页面结果 0 失败；闭环 smoke 中录音结果页通过且不展示 `seed-deterministic-scorer`。
- 状态：Fixed

### F-02

- 严重性：P1
- 页面 / URL：`/sales-trainer`、`/admin/sales-trainer/analytics`
- 截图：`playwright-audit/screenshots/A-23-desktop-admin-sales-trainer-analytics.png`
- 复现步骤：业务技巧同时存在非阻塞学习考卷和 AI 教练结果时，打开 Journey 分析。
- 用户影响：后台分析页 React key 冲突，说明前端仍把同一个 `module_key` 下的不同能力混为一个展示身份。
- 根因文件：`backend/src/sales_trainer/services/training_journey_service.py`、`web/src/app/admin/sales-trainer/analytics/page.tsx`
- 修复：后端 analytics 按 `module_key + kind` 聚合，前端卡片和筛选选项用 `module_key + kind + module_type + title` 作为展示身份；保留 `module_key` 筛选兼容。
- 回归验证：后台专项 Playwright 34 个路由、68 个桌面/移动结果 0 失败，控制台无 key 冲突。
- 状态：Fixed

### F-03

- 严重性：P1
- 页面 / URL：`/sales-trainer`
- 截图：`playwright-audit/screenshots/L-01-desktop-sales-trainer.png`
- 复现步骤：业务技巧考卷未通过时，查看新人训练路径阶段。
- 用户影响：学习专题本应只展示得分，不应阻塞后续关卡；旧逻辑把同模块下的学习考卷混入必修阶段计算。
- 根因文件：`backend/src/sales_trainer/services/training_journey_service.py`
- 修复：学习专题考卷作为非阻塞 `required=false` 模块返回，阶段计算只使用必修模块；仍保留得分、状态和下一步入口。
- 回归验证：`tests/unit/test_sales_trainer_training_journey_service.py` 覆盖 optional quiz failed 不阻塞；前台专项 Playwright 入口页通过。
- 状态：Fixed

### F-04

- 严重性：P2
- 页面 / URL：`/sales-trainer/learn/:unitId`
- 截图：`playwright-audit/screenshots/L-04-desktop-sales-trainer-learn-*.png`
- 复现步骤：打开单元学习动态页。
- 用户影响：Playwright 审计规格只匹配旧“章节/讲义”文案，无法稳定识别当前 COO 章节阅读器的有效页面状态。
- 根因文件：`web/tests/e2e/newcomer-training-route-manifest.ts`
- 修复：审计期望改为当前页面契约：新人训练、章节进度、标记已读、开始本章测验、无法阅读本章。
- 回归验证：前台专项 Playwright 22 个页面结果 0 失败。
- 状态：Fixed
