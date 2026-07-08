# Implementation Notes

## 执行约束

- 输出和交付说明使用中文。
- 最多使用 3 个 agent；当前通过 `tool_search` 未发现可调用的 multi-agent spawn 工具，因此由主 agent 按三条轨道执行：
  - 前台学习端审计
  - 后台管理端审计
  - 路由、权限、测试与兼容审计
- 仓库存在 `.codegraph/`，理解链路优先使用 CodeGraph，再使用 `rg` 精查文件。
- 不触碰排除范围：销售训练、实时对练、`/practice/*`、`/admin/business-rules/sales-trainer-phase2`。
- 不做破坏性数据迁移，不删除旧路由，优先保持兼容。

## 当前计划

1. [x] 固化 PRD、审计矩阵、findings、实施备注和 Trellis check/implement 文件。
2. [x] 使用 CodeGraph 与源码审计确认新人训练前后台页面、导航、权限和 API 依赖。
3. [x] 建立 Playwright 专项审计规格和截图证据目录。
4. [x] 运行 Playwright 审计，记录 findings。
5. [x] 修复 P0/P1/P2 问题，P3 记录后续。
6. [x] 运行相关 Vitest、Playwright、类型检查。
7. [x] Trellis check、提交、归档。

## 偏离记录

- Playwright Chromium 系统依赖无法通过 sudo 安装；改为在 `/tmp/playwright-libs` 解包所需 deb 动态库，并通过 `LD_LIBRARY_PATH` 运行审计。
- `web/.env.local` 指向远端 API，导致本地 Playwright 登录 cookie 与前端 host 不一致；在 E2E `global-setup` 中显式给本地栈设置 `NEXT_PUBLIC_API_URL=http://localhost:3444/api/v1`。
- 未发现可调用的 multi-agent spawn 工具；按三条审计轨道由主 agent 完成。
- 归档后再次运行专项 Playwright 会按 helper 默认选择 archive evidence root，避免重新生成 `.trellis/tasks/07-08-newcomer-path-playwright-audit-governance/` 活动目录；如需新一轮审计，可显式设置 `NEWCOMER_TRAINING_AUDIT_ROOT`。

## 未验证项

- 未运行全量仓库所有测试；CodeGraph affected 列出 47 个潜在测试文件，本次按影响范围选择 TrainingJourney 核心单测、录音结果页/Analytics 页面单测、TypeScript、lint、生产构建、Playwright 前后台专项和闭环 smoke 作为回归证据。

## 验证记录

- `cd backend && ./.venv/bin/python -m pytest tests/unit/test_sales_trainer_training_journey_service.py -q --no-cov`：19 passed。
- `cd web && npx tsc --noEmit`：通过。
- `cd web && npx vitest run 'src/app/(dashboard)/sales-trainer/audio/result/[submissionId]/page.test.tsx'`：11 passed。
- `cd web && LD_LIBRARY_PATH=/tmp/playwright-libs/usr/lib/x86_64-linux-gnu PLAYWRIGHT_SKIP_BROWSER_INSTALL=1 SMOKE_EVIDENCE_PREFIX=newcomer-training-governance npx playwright test tests/e2e/newcomer-training-learner.spec.ts --reporter=line`：1 passed，学习端 11 个路由、22 个桌面/移动结果 0 失败。
- `cd web && LD_LIBRARY_PATH=/tmp/playwright-libs/usr/lib/x86_64-linux-gnu PLAYWRIGHT_SKIP_BROWSER_INSTALL=1 SMOKE_EVIDENCE_PREFIX=newcomer-training-governance npx playwright test tests/e2e/newcomer-training-admin.spec.ts --reporter=line`：1 passed，后台 34 个路由、68 个桌面/移动结果 0 失败。
- `cd web && LD_LIBRARY_PATH=/tmp/playwright-libs/usr/lib/x86_64-linux-gnu PLAYWRIGHT_SKIP_BROWSER_INSTALL=1 SMOKE_EVIDENCE_PREFIX=newcomer-training-governance npx playwright test tests/e2e/newcomer-training-closed-loop.spec.ts -g "seeded audio and AI Coach outcomes are replayable" --reporter=line`：1 passed。
- `codegraph affected <d38bda36 changed files>`：列出 47 个受影响测试文件，用于选择后端核心 journey、前端页面单测和专项 E2E 回归。
- `codegraph impact TrainingJourneyService`：确认影响范围覆盖 learner/admin journey、analytics、readiness、training record、path service 和 seed 脚本。
- `cd web && npx playwright --version`：Version 1.59.1。
- `cd web && npm run lint`：通过，保留 81 个既有 warning，无 error。
- `cd web && npx vitest run 'src/app/(dashboard)/sales-trainer/audio/result/[submissionId]/page.test.tsx' src/app/admin/sales-trainer/analytics/page.test.tsx`：2 files passed，17 tests passed。
- `cd web && npm run build`：通过，Next.js 生产构建成功，生成 114 个静态页面。
- `cd web && LD_LIBRARY_PATH=/tmp/playwright-libs/usr/lib/x86_64-linux-gnu PLAYWRIGHT_SKIP_BROWSER_INSTALL=1 SMOKE_EVIDENCE_PREFIX=newcomer-training-governance npx playwright test tests/e2e/newcomer-training-admin.spec.ts tests/e2e/newcomer-training-learner.spec.ts --reporter=line`：2 passed，组合验证学习端和后台专项规格。
- `git diff --check`：通过。
- `cd web && npx eslint tests/e2e/newcomer-training-audit-helpers.ts`：通过。
- `cd web && npx tsc --noEmit`：补丁后复跑通过。
