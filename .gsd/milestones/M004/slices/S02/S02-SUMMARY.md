---
id: S02
parent: M004
milestone: M004
provides:
  - 现有 report 页到现有 replay 路由的 stable deep-link contract，可从 `main_issue`、`next_goal` 和高光 evidence 直达相关 turn。
  - Replay landing behavior：命中时自动滚动并高亮目标 turn，失配时继续保留 degraded / missing anchor diagnostics。
  - 一组 focused backend + web regression tests，用来防止 replay-anchor contract 和 fallback copy 静默漂移。
requires:
  - slice: S01
    provides: 现有 replay/highlight `learning_evidence` contract 与 report/replay/highlight 共享的 issue/goal coaching vocabulary
affects:
  - S03
  - S05
key_files:
  - backend/src/common/conversation/replay.py
  - backend/src/common/conversation/api.py
  - backend/tests/unit/test_replay_service.py
  - backend/tests/integration/test_replay_api.py
  - web/src/lib/api/types.ts
  - web/src/lib/api/client.ts
  - web/src/app/(user)/practice/[sessionId]/report/page.tsx
  - web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
  - web/src/app/(user)/practice/[sessionId]/replay/page.tsx
  - web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx
key_decisions:
  - 把 replay deep-link metadata 继续挂在现有 `replay.main_issue` / `replay.next_goal` 上的 nested `replay_anchor`，而不是增加单独的 resolver surface。
  - Anchor 解析继续复用现有 replay messages 与 timeline markers，优先定位 matching highlight，失败时退回 stage marker，再退回 missing-marker diagnostics。
  - Report → replay handoff 固定为现有 replay route query params（`focus`、`message_id`、`turn`、`anchor_status`、`anchor_reason`、`marker_type`、`marker_timestamp_ms`），避免新增第二个跳转协议。
  - Replay 在消费 deep link 时必须把 resolved / degraded / missing 状态显式渲染成 banner，而不是静默失败或偷偷改写目标。
patterns_established:
  - 在现有 read model 上用 nested metadata 承载 deep-link semantics，而不是为跨页定位再造第二条 evidence model。
  - 用 query-string handoff 让 report 保持纯 reader、让 replay 保持唯一 landing route；跨页面共享 contract，而不是共享局部前端状态。
  - 把 anchor drift 当成一等降级路径：优先回退到 stage，再回退到完整 transcript + warning banner，始终保留可见诊断。
observability_surfaces:
  - Report issue/goal cards show inline replay-anchor hints for resolved and degraded targets
  - Replay page shows a persistent anchor banner for resolved / degraded / missing landing states
  - Focused backend + frontend replay-anchor regression suites catch contract drift on the existing report/replay routes
drill_down_paths:
  - .gsd/milestones/M004/slices/S02/tasks/T01-SUMMARY.md
  - .gsd/milestones/M004/slices/S02/tasks/T02-SUMMARY.md
  - .gsd/milestones/M004/slices/S02/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-03-25T17:22:54.338Z
blocker_discovered: false
---

# S02: report 直达 replay 关键片段

**当前 report 页现在可把 `main_issue`、`next_goal` 与高光 evidence 直接深链到现有 replay 路由，而 replay 会落到目标 turn 并在高光/marker 漂移时保留明确的 degraded 或 missing-anchor 提示。**

## What Happened

这条 slice 没有新增学习页面，也没有引入第二条事实线。T01 把 deep-link metadata 压回现有 replay authority line：`backend/src/common/conversation/replay.py` 继续基于 `SessionEvidenceService` projection、现有 replay messages 和 timeline markers 生成 issue/goal 结论，但现在会在 `replay.main_issue` 与 `replay.next_goal` 上挂接 nested `replay_anchor`，并把定位结果明确分成 `resolved`、`degraded` 和 `missing`。exact highlight 不存在时，服务优先回退到现有 stage marker；连 marker 也漂移时，则保留 missing-marker diagnostics，而不是猜一个新目标。

T02 让当前 report 页直接消费这条 contract。`web/src/app/(user)/practice/[sessionId]/report/page.tsx` 没有新增 workflow，而是在现有主问题/下一轮目标 CTA 区里渲染 replay hint 与“定位问题片段 / 定位目标片段”按钮；高光 evidence 也继续复用当前列表入口，用 turn-based fallback 直跳 replay。前端 handoff contract 固定为 replay route query params（`focus`、`message_id`、`turn`、`anchor_status`、`anchor_reason`、`marker_type`、`marker_timestamp_ms`），因此 report 只是把现有 authority line 的定位元数据原样传给 replay。

T03 让当前 replay 路由真正吃下这份 handoff。`web/src/app/(user)/practice/[sessionId]/replay/page.tsx` 现在会解析 query params、在现有 transcript/timeline 中查找目标 turn 或 marker、自动滚动并高亮命中的 turn；如果 report 传来的是 degraded anchor，就把“已定位到目标片段，但只是 stage fallback”明确写在 banner 上；如果 turn 和 marker 都失效，就保留 missing-anchor banner 与完整 transcript 供手动查找。结果是：report → replay 的关键片段定位建立在现有 replay/highlight/timeline fact line 上，happy path 能直达，drift path 也不会静默失败。

## Verification

按 slice plan 跑了全部 fresh gate，并读取完整输出确认通过：

1. `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_replay_service.py tests/integration/test_replay_api.py`
   - 48 passed
   - 覆盖 `replay_anchor` 解析、resolved/degraded/missing fallback、legacy normalization 与现有 `/api/v1/sessions/{id}/replay` contract。

2. `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'`
   - 1 test file / 8 tests passed
   - 覆盖 report issue/goal CTA deep links、degraded anchor hint copy、highlights turn fallback。

3. `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'`
   - 2 test files / 12 tests passed
   - 重点确认 replay page 真正消费了 query contract：resolved anchor 会滚动并高亮目标 turn，degraded anchor 会显示 stage fallback banner，missing target 会保留 warning banner 和完整 transcript。

另外核对了 slice plan 要求的 diagnostics surface：report 页会显式展示“回放将定位到第 X 轮高光片段”或“未找到精确高光，回放将定位到某阶段”的提示；replay 页会持续显示 resolved/degraded/missing anchor banner，而不是静默丢掉定位请求。

## Requirements Advanced

- R011 — 把现有 report 页、replay 路由、replay API 与 highlights/timeline authority line 连成一条可跳转的学习证据链：用户现在能从主问题、下一轮目标和高光 evidence 直接落到对应回放片段，且 anchor 漂移时仍看到可解释的 degraded/missing state。

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

None.

## Known Limitations

Exact landing 仍依赖现有 highlights / timeline markers：当 highlight 与 marker 都不存在时，replay 只能保留 warning banner 并让用户在完整 transcript 中手动查找。该 slice 也只覆盖 completed-session 的 report → replay 深链；基于主问题驱动的新一轮定向再练仍由 S03 负责。

## Follow-ups

S03 应直接复用这次落下来的 `focus/message_id/turn/...` query contract 与 issue/goal family 语义来做 report/replay → targeted retry bootstrap，而不是再造一套片段选择模型；S05 live UAT 也应把 report → replay 的 resolved 与 degraded anchor 路径一起纳入最终学习闭环验收。

## Files Created/Modified

- `backend/src/common/conversation/replay.py` — 在现有 replay authority line 上为 `main_issue` / `next_goal` 生成 nested `replay_anchor`，并把定位结果区分为 resolved / degraded / missing。
- `backend/src/common/conversation/api.py` — 保持 `/api/v1/sessions/{id}/replay` 作为现有事实入口，同时输出 anchor-enriched issue/goal payload。
- `backend/tests/unit/test_replay_service.py` — 锁定 replay service 的 anchor 解析、stage fallback、missing-marker degrade 和 legacy normalization 行为。
- `backend/tests/integration/test_replay_api.py` — 锁定 replay API 对 resolved/degraded anchor contract 的序列化与 completed-session gate。
- `web/src/lib/api/types.ts` — 补齐 replay anchor 的 typed contract，供 report 与 replay 页面共享。
- `web/src/lib/api/client.ts` — 让现有 session client 继续承载 anchor-enriched replay/report payload，而不新增第二条路由封装。
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx` — 在当前 report CTA 区渲染 replay hint，并把主问题、下一轮目标与高光 evidence 深链到现有 replay 路由。
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx` — 验证 resolved anchor URL、degraded fallback hint，以及高光 evidence 的 turn-based replay jump。
- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx` — 解析 replay query contract、自动滚动并高亮目标 turn，并在 fallback / missing-target 时展示持续可见的 anchor banner。
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx` — 验证 resolved landing、stage fallback 与 missing-anchor manual-search banner 的实际 UI 行为。
- `.gsd/REQUIREMENTS.md` — 把 M004/S02 的 report→replay proof 追加到 R011 的验证记录中。
- `.gsd/PROJECT.md` — 更新当前项目状态，记录 M004/S02 已把 report 直达 replay 的关键片段链路落到现有入口上。
