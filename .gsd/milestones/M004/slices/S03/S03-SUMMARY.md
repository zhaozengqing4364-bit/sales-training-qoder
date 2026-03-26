---
id: S03
parent: M004
milestone: M004
provides:
  - 现有 report / replay 页上的 issue-family-driven retry launch contract：两处都能复用同一 `retry_entry.focus_intent` 发起定向再练。
  - 新会话上的 frozen `voice_policy_snapshot.focus_intent` 与 typed `runtime_descriptor.focus_intent`，让 `/practice/{sessionId}` 首屏能明确展示“这次为什么是定向再练”。
  - 一组 focused backend + web regression tests，用来防止 retry-entry contract、runtime descriptor carry-forward 与 practice-page callout 静默漂移。
requires:
  - slice: S01
    provides: stable `main_issue` / `next_goal` learning vocabulary 与可被 retry intent 引用的 completed-session evidence facts
  - slice: S02
    provides: 当前 report / replay 入口链与对齐后的 issue/goal surfaces，保证 replay 可以复用 canonical report retry contract 而不是另造入口
affects:
  - S05
key_files:
  - backend/src/common/api/practice.py
  - backend/src/common/db/schemas.py
  - backend/src/training_runtime/models.py
  - backend/src/training_runtime/service.py
  - backend/tests/contract/test_practice_evidence_contract.py
  - backend/tests/integration/test_practice_evidence_flow.py
  - backend/tests/unit/test_training_runtime_service.py
  - web/src/lib/api/types.ts
  - web/src/lib/api/client.ts
  - web/src/app/(user)/practice/[sessionId]/report/page.tsx
  - web/src/app/(user)/practice/[sessionId]/replay/page.tsx
  - web/src/app/(user)/practice/[sessionId]/runtime-lock.ts
  - web/src/app/(user)/practice/[sessionId]/page.tsx
  - web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
  - web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx
  - web/src/app/(user)/practice/[sessionId]/runtime-lock.test.ts
  - web/src/app/(user)/practice/[sessionId]/page.test.tsx
  - web/src/hooks/use-practice-websocket.test.ts
  - .gsd/PROJECT.md
  - .gsd/DECISIONS.md
key_decisions:
  - 继续把 retry focus 暴露在现有 sales report `retry_entry.focus_intent` 上，并把 create-session 接收到的 focus intent 冻结进 `voice_policy_snapshot.focus_intent`，而不是发明第二套 retry-launch store。
  - report 与 replay 都复用现有 CTA 和 `api.practice.createSession` surface；replay 侧的 retry metadata 必须从 canonical report `retry_entry` 读取，避免出现第二份前端拼接 contract。
  - learner practice page 只消费 typed `runtime_descriptor.focus_intent`；`usePracticeRuntimeLock` 继续作为 `/practice/{sessionId}` 元数据同步 seam，不新增 retry-specific fetch 或 onboarding flow。
patterns_established:
  - 在当前 completed-session evidence → create-session → frozen snapshot → runtime descriptor authority line 上传递 retry focus，而不是在 frontend route state 或 local storage 里临时传递学习意图。
  - 把 report/replay 的“按目标再练一轮”收口成同一个 session-create contract：query params 继续承载可见的场景/agent/persona/presentation 选择，结构化 `focus_intent` 只走 request body。
  - learner practice page 展示 carry-forward focus 时，应优先扩展现有 runtime descriptor / runtime-lock seam，而不是让页面直接解析原始 `voice_policy_snapshot`。
observability_surfaces:
  - Report 与 replay retry 区块都会在配置缺失或创建失败时显示 inline retry hint，而不是静默失效。
  - `/practice/{sessionId}` 首屏会在 sales targeted retry 时显示“定向再练” callout，直出 carried-forward main issue / recovery rule / next goal / rule。
  - Focused backend + frontend suites 覆盖 `retry_entry.focus_intent`、session snapshot persistence、runtime descriptor projection 与 practice-page carry-forward UI。
drill_down_paths:
  - .gsd/milestones/M004/slices/S03/tasks/T01-SUMMARY.md
  - .gsd/milestones/M004/slices/S03/tasks/T02-SUMMARY.md
  - .gsd/milestones/M004/slices/S03/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-03-26T02:11:03.437Z
blocker_discovered: false
---

# S03: 主问题驱动的再练入口

**把当前 report / replay 的主问题与下一轮目标接成现有 create-session 链路上的定向再练，并让新 practice session 首屏明确显示 carry-forward focus。**

## What Happened

S03 继续沿用 M004 的现有 entry chain，没有增加新的 retry 页面或第二套事实线。后端先在 `backend/src/common/api/practice.py` 上把 completed-session 的 `main_issue` / `next_goal` 收敛成 sales-only `retry_entry.focus_intent`，并让现有 `POST /api/v1/practice/sessions` 接受、清洗、校验这份结构化 focus intent；对 sales caller 来说，非法 payload 会明确返回 `[INVALID_RETRY_FOCUS_INTENT]`，合法 payload 则被冻结到新 session 的 `voice_policy_snapshot.focus_intent`。随后 report 与 replay 两个现有页面都改为复用当前 CTA 和 `api.practice.createSession` surface 来发起 retry，其中 replay 不再自造 retry metadata，而是并行读取 canonical report `retry_entry`，确保两个入口共享一条 retry-launch contract。最后，`training_runtime/service.py` 与 `usePracticeRuntimeLock` 把 frozen snapshot 里的 retry focus 投影成 typed `runtime_descriptor.focus_intent`，practice page 顶部会在 sales targeted retry 时展示“定向再练” callout，直出 carried-forward 主问题、修正动作、下一轮目标与判定条件，让用户一进入新 session 就知道这不是普通新建会话，而是在沿着上一轮的核心问题继续练。

## Verification

Fresh verification passed on all slice-plan gates and the carry-forward focus seam: `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/contract/test_practice_evidence_contract.py tests/integration/test_practice_evidence_flow.py` (9 passed); `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx'` (2 files / 14 tests passed); `cd web && npm test -- --run 'src/hooks/use-practice-websocket.test.ts'` (1 file / 11 tests passed). Additional focused hardening also passed: `cd backend && venv/bin/python -m pytest -c pyproject.toml tests/unit/test_training_runtime_service.py` (2 passed) and `cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/page.test.tsx' 'src/app/(user)/practice/[sessionId]/runtime-lock.test.ts' 'src/hooks/use-practice-websocket.test.ts'` (3 files / 15 tests passed). `lsp diagnostics` also returned no diagnostics for `backend/src/common/api/practice.py` and `backend/src/training_runtime/service.py`.

## Requirements Advanced

- R011 — 把现有 report / replay / practice 入口连成同一条 issue-family-driven learning loop：用户可以从当前 report 或 replay 页面发起定向再练，并在新 session 首屏看到 carry-forward focus。

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

No product-scope deviations. Delivering the carry-forward UI through the existing typed metadata seam required extra plumbing in `backend/src/training_runtime/models.py`, `web/src/app/(user)/practice/[sessionId]/runtime-lock.ts`, `runtime-lock.test.ts`, and `page.test.tsx`, but this stayed within the planned current-entry-chain boundary.

## Known Limitations

This slice only carries structured `focus_intent` for sales report/replay retries; presentation retries still reuse the existing base retry config without a sales-style focus callout. If a historical session lacks `agent_id` / `persona_id` (or a presentation session lacks `presentation_id`), report/replay intentionally block retry with an explicit hint instead of guessing defaults. The full live proof that the carried-forward focus survives into the next real training round remains part of S05.

## Follow-ups

S05 should include one live sales proof that starts from a completed report or replay page, launches a targeted retry, lands on the new `/practice/{sessionId}` screen with the carried-forward focus visible, and confirms that reconnect / initial websocket hydration do not drop that focus before the learner starts the next round.

## Files Created/Modified

- `backend/src/common/api/practice.py` — Added structured retry-focus sanitization/build helpers, exposed `retry_entry.focus_intent` on report responses, and persisted validated `focus_intent` into new sales sessions' frozen voice policy snapshots.
- `backend/src/common/db/schemas.py` — Extended the existing `SessionCreate` contract with optional `focus_intent` so targeted retries still use the canonical create-session API.
- `backend/src/training_runtime/models.py` — Added `focus_intent` to the typed training runtime descriptor model.
- `backend/src/training_runtime/service.py` — Projected sales retry focus from `voice_policy_snapshot.focus_intent` onto `runtime_descriptor.focus_intent` while keeping non-sales runtimes clean.
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx` — Reused the current retry CTA to call `api.practice.createSession` with canonical `retry_entry.focus_intent`, while surfacing inline blocked/error hints.
- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx` — Loaded retry metadata from the canonical report `retry_entry` and reused the same targeted retry launch flow on the replay page.
- `web/src/app/(user)/practice/[sessionId]/runtime-lock.ts` — Threaded `runtime_descriptor.focus_intent` through the existing session metadata lock seam so the practice page can consume carry-forward focus without a second fetch.
- `web/src/app/(user)/practice/[sessionId]/page.tsx` — Rendered a top-of-page targeted-retry callout showing the carried-forward main issue, recovery rule, next goal, and success rule on the existing practice entry screen.
- `backend/tests/contract/test_practice_evidence_contract.py` — Locked the `retry_entry.focus_intent` contract and report/replay evidence parity.
- `backend/tests/integration/test_practice_evidence_flow.py` — Verified that the report-derived retry focus survives the existing create-session flow and persists on the new session snapshot.
- `backend/tests/unit/test_training_runtime_service.py` — Verified that only sales runtimes project `runtime_descriptor.focus_intent`.
- `web/src/app/(user)/practice/[sessionId]/report/page.test.tsx` — Covered report-page targeted retry launch behavior and scenario/query carry-forward.
- `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx` — Covered replay-page retry launch behavior and reuse of canonical report retry metadata.
- `web/src/app/(user)/practice/[sessionId]/runtime-lock.test.ts` — Covered consumption of `runtime_descriptor.focus_intent` by the existing runtime-lock hook.
- `web/src/app/(user)/practice/[sessionId]/page.test.tsx` — Covered the learner-visible carry-forward focus callout on the practice page.
- `.gsd/PROJECT.md` — Updated project state to record that M004/S03 now delivers a report/replay → targeted-retry learning-loop skeleton on current routes.
- `.gsd/DECISIONS.md` — Appended the missing slice-level decision that replay retry launches must read the canonical report `retry_entry` and reuse the existing create-session / practice-route chain.
