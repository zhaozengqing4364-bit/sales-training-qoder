---
estimated_steps: 4
estimated_files: 8
skills_used:
  - safe-grow
  - test-driven-development
  - agent-browser
  - react-best-practices
  - vercel-react-best-practices
  - baseline-ui
  - accessibility
  - best-practices
  - verification-before-completion
---

# T02: 实现标准 PPT 原位替换并验证下一次演练读取最新页面

**Slice:** S04 — 知识库更新即生效链路
**Milestone:** M001

## Description

这个任务只解决 R004 的“标准 PPT”半条链：管理员必须能在同一条标准 PPT 记录上做替换/更新，而不是每次上传都制造新的 `presentation_id` 让前台重新找；同时因为 presentation runtime 会按 `presentation_id + page_number` 实时读数据库，所以替换不能偷偷污染进行中的演练。任务目标是把“稳定 `presentation_id` + 递增 `version_number` + 活动会话阻断 + 下一次新建 session 读取最新页内容”做成有测试、有 UI 状态、有用户入口提示的一条闭环。

## Steps

1. 先在 `backend/tests/contract/test_presentations.py` 和 `backend/tests/integration/test_presentation_flow.py` 写/补 failing tests，锁住 replace-in-place 合同：保持同一 `presentation_id`、递增 `version_number`、重建 pages/thumbnail 数据、活动会话存在时返回明确阻断错误、下一次新建 session 读取最新页内容与规则。
2. 在 `backend/src/presentation_coach/api/presentations.py` 实现最小 replace 入口：复用现有上传/解析管线，把替换后的文件、页面、缩略图与 presentation 状态收口到同一记录；显式处理 page 级 coaching 数据重建，避免旧 `page_id` 悬挂；替换前检查是否有非终态 `PracticeSession` 正引用该 presentation。
3. 在 `web/src/lib/api/client.ts`、`web/src/app/admin/presentations/[id]/page.tsx` 和 `web/src/app/(dashboard)/agents/[agentId]/page.tsx` 接线：admin 详情页显示 `version_number`、replace CTA 与 processing/ready/failed 状态；用户演练入口继续复用同一 `presentation_id`，但把当前版本与材料状态显示出来，避免“换完标准 PPT 还在用旧记录”的歧义。
4. 用 `web/src/app/admin/presentations/[id]/page.test.tsx` 与 `web/src/app/(dashboard)/agents/[agentId]/page.test.tsx` 先补 failing tests，再完成实现并跑完 backend + web targeted suites；browser 复查只覆盖“替换被阻断”和“下一次新建 session 读取最新版本”两条关键路径。

## Must-Haves

- [ ] 管理员必须能在 `web/src/app/admin/presentations/[id]/page.tsx` 对标准 PPT 做原位替换，并看到 `version_number` 与 `processing/ready/failed` 状态变化；如果存在非终态 session，替换要被明确阻止而不是静默生效。
- [ ] backend + frontend tests 必须证明：替换后仍是同一 `presentation_id`，但下一次新建 presentation session 读取的是最新 `Page` / `RequiredTalkingPoint` / `ForbiddenWord`；用户入口不需要追新 ID 才能拿到新材料。

## Verification

- `cd backend && pytest tests/contract/test_presentations.py tests/integration/test_presentation_flow.py`
- `cd web && npm test -- --run 'src/app/admin/presentations/[id]/page.test.tsx' 'src/app/(dashboard)/agents/[agentId]/page.test.tsx'`

## Observability Impact

- Signals added/changed: presentation replace 响应中的 `presentation_id/version_number/status/total_pages`、replace 被活动会话阻止的错误、admin 详情页版本/状态文案、用户入口的版本标签。
- How a future agent inspects this: 查看 `GET /presentations/{id}` / replace 响应、`web/src/app/admin/presentations/[id]/page.tsx` 的版本 UI、`web/src/app/(dashboard)/agents/[agentId]/page.tsx` 的选择器标签，以及 contract/integration/UI tests。
- Failure state exposed: replace 在 active session 下被阻断、解析失败导致 `status=failed`、页级 coaching 数据未重建导致测试失败、以及用户入口仍显示旧版本信息的前端回归。

## Inputs

- `backend/src/presentation_coach/api/presentations.py` — 当前上传只会创建新的 `presentation_id`，没有标准 PPT 原位替换能力。
- `backend/src/presentation_coach/services/coach_service.py` — runtime 通过 `presentation_id + page_number` 读取最新 `Page` / `RequiredTalkingPoint` / `ForbiddenWord`，是“下一次新建 session 读新材料”的权威读面。
- `backend/src/common/db/models.py` — `Presentation.version_number` 与 `PracticeSession.presentation_id` 已存在，可支撑稳定身份与版本诊断。
- `backend/tests/contract/test_presentations.py` — 现有 presentations contract 测试较浅，适合补 replace-in-place 合同。
- `backend/tests/integration/test_presentation_flow.py` — 现有 presentation flow 测试多为占位/skip，适合收口为 replace + next-session proof。
- `web/src/lib/api/client.ts` — 现有 presentations client 只有 upload/delete/talking-points/forbidden-words 调用。
- `web/src/app/admin/presentations/[id]/page.tsx` — 当前只支持页内容、要点、禁忌词维护，没有 replace/version 状态面。
- `web/src/app/(dashboard)/agents/[agentId]/page.tsx` — 用户创建 presentation 练习时会选择 `presentation_id`，是保持 stable ID 生效的关键入口。

## Expected Output

- `backend/src/presentation_coach/api/presentations.py` — 新增标准 PPT 原位替换入口与活动会话阻断、版本递增、页面重建逻辑。
- `backend/tests/contract/test_presentations.py` — 锁住 replace-in-place 的 API 合同与版本语义。
- `backend/tests/integration/test_presentation_flow.py` — 证明替换后下一次新建 presentation session 会读取最新页面内容与规则。
- `web/src/lib/api/client.ts` — 接入 replace presentation 的客户端调用与返回值处理。
- `web/src/app/admin/presentations/[id]/page.tsx` — 展示 `version_number`、replace CTA、processing/ready/failed 状态与阻断提示。
- `web/src/app/admin/presentations/[id]/page.test.tsx` — 覆盖 replace CTA、版本显示、阻断提示与状态切换的 focused tests。
- `web/src/app/(dashboard)/agents/[agentId]/page.tsx` — 在用户演练材料选择器中显示当前版本/状态并继续复用稳定 `presentation_id`。
- `web/src/app/(dashboard)/agents/[agentId]/page.test.tsx` — 覆盖用户入口对版本/状态文案与新建 session 参数的回归测试。
