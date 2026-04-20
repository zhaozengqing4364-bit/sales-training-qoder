---
id: T02
parent: S04
milestone: M001
provides:
  - 管理员可在同一 standard presentation 记录上原位替换 PPT，并在 active session 存在时得到显式阻断；用户入口可继续复用稳定的 presentation_id 同时看到当前版本与材料状态
key_files:
  - backend/src/presentation_coach/api/presentations.py
  - backend/tests/contract/test_presentations.py
  - backend/tests/integration/test_presentation_flow.py
  - web/src/lib/api/client.ts
  - web/src/app/admin/presentations/[id]/page.tsx
  - web/src/app/admin/presentations/[id]/page.test.tsx
  - web/src/app/(dashboard)/agents/[agentId]/page.tsx
  - web/src/app/(dashboard)/agents/[agentId]/page.test.tsx
key_decisions:
  - 标准 PPT 的 replace/version/blocker 合同继续落在 live `/api/v1/presentations` 上，而不是复活 schema 已漂移的 legacy admin API
patterns_established:
  - 用 contract/integration tests 锁住“stable presentation_id + incremented version_number + rebuilt page-scoped metadata + active-session blocker”，再用浏览器只补关键活体验证面
observability_surfaces:
  - GET /api/v1/presentations/{id}
  - POST /api/v1/presentations/{id}/replace
  - web/src/app/admin/presentations/[id]/page.tsx
  - web/src/app/(dashboard)/agents/[agentId]/page.tsx
  - backend/tests/contract/test_presentations.py
  - backend/tests/integration/test_presentation_flow.py
duration: 5h
verification_result: passed
completed_at: 2026-03-23T18:51:08+08:00
blocker_discovered: false
---

# T02: 实现标准 PPT 原位替换并验证下一次演练读取最新页面

**Added in-place standard PPT replacement on the live presentations surface with active-session blocking, rebuilt page metadata, and admin/user version-status visibility.**

## What Happened

我按任务计划核对了本地 reality，发现标准 PPT replace 相关代码与 focused tests 已经在工作区里，但任务 summary 文件缺失、slice plan 也还没勾选，所以这次执行以“验证真实交付 + 补齐任务工件”为主，而不是重新发明一套实现。

本任务实际交付的功能链如下：

1. `backend/src/presentation_coach/api/presentations.py` 已新增 live replace 入口，保持同一 `presentation_id`，在 replace 时递增 `version_number`、重建 `Page`/thumbnail/page-scoped `RequiredTalkingPoint`/`ForbiddenWord`，并在存在非终态 `PracticeSession` 时返回显式 `409 [PRESENTATION_REPLACE_BLOCKED_ACTIVE_SESSION]`。
2. `backend/tests/contract/test_presentations.py` 锁住 replace-in-place API 合同：稳定 ID、版本递增、detail 响应刷新，以及 active session blocker payload。
3. `backend/tests/integration/test_presentation_flow.py` 证明 replace 后旧 `page_id` 不悬挂、页级 coaching 数据会重建，而且下一次新建 presentation session 读取的是最新页面内容 / required points / forbidden words。
4. `web/src/app/admin/presentations/[id]/page.tsx` 与 `web/src/lib/api/client.ts` 已接上线上的 replace 合同，admin 详情页可显示 `version_number`、`processing/ready/failed`、replace CTA、以及被活动会话阻止时的就地错误提示。
5. `web/src/app/(dashboard)/agents/[agentId]/page.tsx` 与对应 tests 已让用户入口继续复用稳定 `presentation_id`，同时展示当前版本、材料状态和页数，避免“换完标准 PPT 但前台还在追新 ID”的歧义。

在活体验证上，我先跑完整个 S04 自动化 gate，随后补了本地 runtime/browser 检查：

- 初次 backend UAT 被本地缺失的 Python `redis` client 卡住；我安装了缺失包后，backend / web 都正常启动。
- 在 admin 详情页对 ready deck `20706b4b-bb22-484a-8f2f-8ecacc43bb3b` 上传真实 PPT 文件后，replace 请求被 live blocker 正确拒绝，页面直接展示 `当前有进行中的演练正在使用该标准PPT，请结束后再替换。`，网络层返回 `409` 且 payload 暴露 `active_session_count`。
- 在用户 `/agents/7199854c-3921-4d9f-9833-fe99ca209c59` 页面，presentation selector 真实展示 `石犀（v1 · 可用 · 36 页）` 与摘要卡 `当前版本：v1 / 材料状态：可用`，并且点击“开始对练”后落到 `/practice/...&presentation_id=20706...`，证明用户入口继续走同一 stable `presentation_id`。

## Verification

已完成并重新运行本 slice 的自动化验证：

- backend knowledge suites 通过
- backend presentation contract + integration suites 通过
- web knowledge/admin-presentation/agent-entry focused tests 通过

已完成 runtime/browser 验证：

- 修复本地缺失 `redis` Python client 后，backend 与 web dev server 均可启动
- admin presentation detail 页 live 验证到 replace blocker 文案与 `409` payload
- user agent page live 验证到当前版本/状态展示，以及新建练习 URL 继续携带稳定 `presentation_id`

没有在浏览器里强行跑“成功 replace 同一 ready deck”的 destructive live swap，因为本地唯一 ready deck 当时已有两个与本任务无关的进行中 session 正在占用；该成功路径由 `backend/tests/contract/test_presentations.py` 与 `backend/tests/integration/test_presentation_flow.py` 明确覆盖。

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && pytest tests/integration/test_knowledge_api.py tests/integration/test_knowledge_upload_persistence.py tests/integration/test_knowledge_flow.py` | 0 | ✅ pass | 12.82s |
| 2 | `cd backend && pytest tests/contract/test_presentations.py tests/integration/test_presentation_flow.py` | 0 | ✅ pass | 11.31s |
| 3 | `cd web && npm test -- --run 'src/app/admin/knowledge/[id]/page.test.tsx' 'src/app/admin/presentations/[id]/page.test.tsx' 'src/app/(dashboard)/agents/[agentId]/page.test.tsx'` | 0 | ✅ pass | 1.55s |
| 4 | `Browser UAT — /admin/presentations/20706b4b-bb22-484a-8f2f-8ecacc43bb3b 上传真实 PPT 并触发 replace blocker` | 0 | ✅ pass | ~4m |
| 5 | `Browser UAT — /agents/7199854c-3921-4d9f-9833-fe99ca209c59 验证版本/状态并创建新的 presentation session` | 0 | ✅ pass | ~3m |

## Diagnostics

后续 agent 可通过以下面快速确认本任务是否仍成立：

- `GET /api/v1/presentations/{id}`
  - `presentation_id`
  - `version_number`
  - `status`
  - `total_pages`
- `POST /api/v1/presentations/{id}/replace`
  - blocker 时应返回 `409`
  - `error=[PRESENTATION_REPLACE_BLOCKED_ACTIVE_SESSION]`
  - `details.active_session_count`
  - `details.active_sessions[]`
- `web/src/app/admin/presentations/[id]/page.tsx`
  - 版本 badge
  - `processing/ready/failed` 文案
  - replace CTA
  - blocker alert 文案
- `web/src/app/(dashboard)/agents/[agentId]/page.tsx`
  - selector option 中的 `v{version} · {status} · {pages}`
  - 摘要卡中的 `当前版本 / 材料状态 / 页数`
  - 新建 session URL 中继续携带原始 `presentation_id`
- 权威自动化证明
  - `backend/tests/contract/test_presentations.py`
  - `backend/tests/integration/test_presentation_flow.py`
  - `web/src/app/admin/presentations/[id]/page.test.tsx`
  - `web/src/app/(dashboard)/agents/[agentId]/page.test.tsx`

## Deviations

- 浏览器活体验证前，我先修复了本地环境缺失的 Python `redis` client（安装到 `backend/venv`），否则 backend 无法启动，manual UAT 会被环境问题而不是任务代码卡住。
- live browser replace-success 路径没有直接对唯一 ready deck 强行执行，因为该 deck 当时已有两个与本任务无关的 `in_progress` session；我保留了真实 blocker 行为，并把 replace-success + next-session-read-latest 的证明落回已通过的 backend contract/integration suites。

## Known Issues

- 本地数据里的两个历史 `in_progress` presentation session 会持续阻止对 ready deck `20706b4b-bb22-484a-8f2f-8ecacc43bb3b` 做 destructive live replace；如果后续要补完整 browser success-swap UAT，需要先结束这些占用中的会话，或准备一个未被占用的 ready deck。
- 现有 ready deck 在 admin 详情页会有大量 `thumbnail 404` 噪声日志；这不影响本任务的 version/status/blocker 合同，但会污染浏览器控制台与网络错误列表。

## Files Created/Modified

- `backend/src/presentation_coach/api/presentations.py` — 新增 stable `presentation_id` 的 in-place replace 入口、版本递增、页级 metadata 重建与 active-session blocker
- `backend/tests/contract/test_presentations.py` — 锁住 replace-in-place 的 API 合同与 blocker payload
- `backend/tests/integration/test_presentation_flow.py` — 证明 replace 后新 session 读取最新页面内容与规则，且旧 `page_id` 依赖被重建
- `web/src/lib/api/client.ts` — 接入 presentation replace client 与 live error mapping
- `web/src/app/admin/presentations/[id]/page.tsx` — 展示版本/状态/replace CTA 并就地暴露 blocker 错误
- `web/src/app/admin/presentations/[id]/page.test.tsx` — 覆盖版本展示、replace CTA 与 blocker 提示
- `web/src/app/(dashboard)/agents/[agentId]/page.tsx` — 在用户演练入口显示当前版本与材料状态并继续复用 stable `presentation_id`
- `web/src/app/(dashboard)/agents/[agentId]/page.test.tsx` — 覆盖 selector 文案与新建 session 参数回归
- `.gsd/milestones/M001/slices/S04/S04-PLAN.md` — 将 T02 标记为完成
- `.gsd/milestones/M001/slices/S04/tasks/T02-SUMMARY.md` — 记录本任务执行与验证证据
