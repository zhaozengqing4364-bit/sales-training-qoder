---
id: M002
provides:
  - A shared sales-first realtime coaching baseline across classic + StepFun: one canonical five-dimension rubric, one paced primary action surface per turn, and one stage-aware next-turn coaching rule.
  - Projection-backed completed-session alignment that keeps report / replay / history / admin on the same `main_issue` / `next_goal` family as the realtime coaching rule baseline while preserving stable public contract keys.
  - Alignment diagnostics and focused regression coverage that make realtime/read-side drift inspectable instead of implicit.
key_decisions:
  - D033
  - D034
  - D036
  - D037
  - D038
  - D039
  - D041
  - D042
patterns_established:
  - Keep public websocket/report contracts stable and move richer coaching/alignment logic into shared backend seams (`resolve_sales_coaching_focus(...)`, `resolve_sales_report_alignment(...)`) rather than widening client-facing payloads.
  - Treat same-turn score refinements and the latest alignable persisted sales evidence as product-significant facts; do not dedupe them away or blindly trust the newest partial snapshot.
  - Preserve low-level stage / score / fuzzy signals as context, but allow only one primary `action_card` direction per turn on the learner-facing surface.
observability_surfaces:
  - `backend/tests/unit/test_stepfun_realtime_handler.py`
  - `backend/tests/unit/test_capability_processor.py`
  - `backend/tests/unit/test_realtime_feedback_arbiter.py`
  - `backend/tests/unit/test_effectiveness_sales_coaching_focus.py`
  - `backend/tests/unit/test_effectiveness_sales_report_alignment.py`
  - `backend/tests/unit/test_session_evidence_service.py`
  - `backend/tests/contract/test_practice_evidence_contract.py`
  - `backend/tests/integration/test_practice_evidence_flow.py`
  - `web/src/hooks/websocket/message-handlers.test.ts`
  - `web/src/hooks/use-practice-websocket.test.ts`
  - `web/src/components/practice/ScorePanel.test.tsx`
  - `web/src/components/practice/RightPanelContent.test.tsx`
  - `web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx`
  - `web/src/app/admin/users/[id]/page.test.tsx`
  - `practice_session_evidence_projection_built`
requirement_outcomes: []
duration: 2026-03-24 → 2026-03-25 (close-out audit)
verification_result: needs-remediation
completed_at: null
---

# M002: 实时教练闭环

**M002 delivered the core realtime-sales coaching semantics through S01-S04, but the milestone close-out audit did not pass: coach degraded/resumed visibility and the final live end-to-end closure proof are still missing, so the milestone cannot be marked complete.**

## What Happened

M002 materially advanced the product beyond “post-session report only.” S01 put classic and StepFun practice on one five-dimension sales rubric and stopped the practice page from dropping same-turn score/stage refinements. S02 then constrained feedback rhythm so the learner sees one primary action direction per turn instead of competing fuzzy/stage/score/action prompts. S03 made that surviving action direction stage-aware by routing both runtimes through one shared coaching-focus resolver. S04 carried the same sales-first conclusion family onto completed-session read surfaces so report, replay, history, and admin can override stale snapshots without changing the public contract.

The close-out audit then checked whether that assembled work actually satisfied the roadmap, not just the delivered slice summaries. The repository does contain substantial non-`.gsd/` implementation work relative to the integration baseline (`001-ai-practice-system`): fresh diff verification showed 87 changed non-`.gsd/` files. Fresh backend verification passed 88 focused tests spanning realtime scoring, StepFun/classic parity, shared coaching focus, report alignment, projection alignment, and contract/integration evidence flow. Fresh web verification passed 44 focused tests spanning websocket reducers, practice-panel precedence, replay conclusion rendering, and admin aligned labels.

However, the milestone still fails its own close-out gate. The current milestone inventory contains summary artifacts only for S01-S04. Planned remediation slices S07 and S08 are still absent from `.gsd/milestones/M002/slices/`, so the roadmap’s remaining obligations were never retired in the repository state being closed. That means the milestone still lacks verified coach degraded/resumed visibility during live training and still lacks one real end-to-end sales path proving the same session stayed coherent from realtime coaching through final report/replay review.

## Cross-Slice Verification

- **Implementation-backed milestone, not planning-only:** because `main` does not exist in this repo, the diff audit used the actual integration baseline `001-ai-practice-system`. Fresh verification showed `git diff --shortstat HEAD "$(git merge-base HEAD 001-ai-practice-system)" -- ':!.gsd/'` => **87 files changed, 2154 insertions, 14735 deletions**.
- **Fresh automated verification passed for the delivered slices:**
  - `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_realtime_scoring.py backend/tests/unit/test_stepfun_realtime_handler.py backend/tests/unit/test_capability_processor.py backend/tests/unit/test_realtime_feedback_arbiter.py backend/tests/unit/test_effectiveness_sales_coaching_focus.py backend/tests/unit/test_effectiveness_sales_report_alignment.py backend/tests/unit/test_session_evidence_service.py backend/tests/contract/test_practice_evidence_contract.py backend/tests/integration/test_practice_evidence_flow.py` → **88 passed**.
  - `npm --prefix web test -- --run 'src/hooks/websocket/message-handlers.test.ts' 'src/hooks/use-practice-websocket.test.ts' 'src/components/practice/ScorePanel.test.tsx' 'src/components/practice/RightPanelContent.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx' 'src/app/admin/users/[id]/page.test.tsx'` → **44 passed across 6 test files**.
- **Slice inventory check failed milestone close-out:** `find .gsd/milestones/M002/slices -maxdepth 2 -name 'S*-SUMMARY.md'` returned only **S01-S04**. Required roadmap slices **S07** and **S08** are missing.

### Success Criteria Audit

1. **用户能看到围绕价值表达 / 客户收益连接 / 证据使用 / 异议处理 / 推进下一步的实时评分变化** — **met**.
   - Fresh backend verification passed `test_realtime_scoring.py`, `test_stepfun_realtime_handler.py`, and `test_capability_processor.py`, proving canonical five-dimension sales `score_update` / `action_card` behavior across both runtimes.
   - Fresh web verification passed `message-handlers.test.ts` and `ScorePanel.test.tsx`, proving the practice page keeps same-turn sales refinements and renders the sales-first rubric.

2. **每一轮最多一个主要动作方向，提示不刷屏不互相打架** — **met**.
   - Fresh backend verification passed `test_realtime_feedback_arbiter.py`, StepFun same-turn suppression cases, and classic duplicate-suppression cases.
   - Fresh web verification passed `RightPanelContent.test.tsx` and websocket hook/reducer coverage proving `action_card` remains the sole primary textual coach surface while stale turn-bound hints are cleared.

3. **训练中主提示方向与训练后 `main_issue` / `next_goal` 保持一致，不再漂移** — **not fully met**.
   - Fresh backend verification passed `test_effectiveness_sales_report_alignment.py`, `test_session_evidence_service.py`, `test_practice_evidence_contract.py`, and `test_practice_evidence_flow.py`, which proves completed-session report/replay alignment and stale-snapshot override behavior.
   - Fresh web verification passed replay/admin read-side tests, proving aligned conclusions render correctly outside the report page.
   - But the roadmap required proof that the same session stays coherent from live coaching to final conclusion. The repository still lacks S08’s live end-to-end closure artifact, so this criterion is not retired at milestone level.

4. **教练链路部分失败、静音或重连恢复时，训练主链路继续可用且明确暴露降级状态** — **not met**.
   - No S07 slice summary/UAT artifact exists.
   - The close-out inventory and code/test evidence in this repo state do not provide a verified learner-facing `coach degraded / data unavailable / resumed` surface for the live practice flow.

### Definition of Done Audit

- **“实时教练使用的销售维度、阶段语义和动作卡规则已经与当前销售训练基线对齐”** — met by S01-S03 and the fresh backend/web verification above.
- **“训练页不会同时堆叠多条相互竞争的建议；用户能明确知道这一轮最该改什么”** — met by S02 plus fresh arbiter/right-panel verification.
- **“报告页、回放页和实时训练页对同一 session 的主问题与下一目标不再各说各话”** — not fully met at milestone close-out, because S04 proves completed-session read-side alignment but S08’s same-session live closure proof is still missing.
- **“训练链路在教练模块降级时仍能继续，且降级状态对用户和排障都可见”** — not met; no S07 evidence exists.
- **“至少一条真实销售训练路径完成 live UAT”** — not met; no S08 live UAT artifact exists.
- **“all slices are [x] / all slice summaries exist / cross-slice integration points work correctly”** — not met; only four of the six planned roadmap slices have summary artifacts.

## Requirement Changes

- **No requirement status transitions were validated in this close-out audit.**
- **R009 remains active.** M002 materially advanced it through S01-S04: the sales rubric is now realtime, paced, stage-aware, and projection-aligned on completed-session read surfaces. But the milestone still lacks the proof needed to validate R009 fully: explicit degraded/resumed coach visibility and one live end-to-end coaching → report closure path for the same session.

## Forward Intelligence

### What the next remediation turn should know
- S07 and S08 are not optional cleanup. They are the missing proof layers that separate “good component slices” from “a closed milestone.” Do not re-open S01-S04 semantics unless new evidence shows regression; focus on degraded/resumed coach visibility and one real same-session closure path.

### What's fragile
- The shipped M002 behavior depends on shared internal seams staying authoritative. If classic/StepFun/report/replay/admin start rebuilding sales heuristics locally instead of reusing `resolve_sales_coaching_focus(...)` and `resolve_sales_report_alignment(...)`, drift will return even if the public payload keys stay unchanged.

### Authoritative diagnostics
- For semantic drift: start with `backend/tests/unit/test_effectiveness_sales_coaching_focus.py`, `backend/tests/unit/test_effectiveness_sales_report_alignment.py`, and `backend/tests/unit/test_session_evidence_service.py`.
- For learner-surface pacing drift: start with `backend/tests/unit/test_realtime_feedback_arbiter.py`, `backend/tests/unit/test_stepfun_realtime_handler.py`, `web/src/hooks/websocket/message-handlers.test.ts`, and `web/src/components/practice/RightPanelContent.test.tsx`.
- For missing milestone closure proof: start with the slice inventory under `.gsd/milestones/M002/slices/` before trusting any prompt that says all slices are done.

### What assumptions changed
- The delivered core semantics are real, but milestone closure is not implied by passing component suites. This milestone demonstrated that you can have correct realtime scoring, pacing, shared coaching rules, and read-side alignment while still missing the operational proof layers the roadmap explicitly promised.

## Files Created/Modified

- `backend/src/agent/capabilities/realtime_scoring.py` — locked the five-dimension sales realtime scoring baseline.
- `backend/src/sales_bot/websocket/components/capability_processor.py` — aligned classic-mode realtime coaching with the shared sales semantics and arbiter path.
- `backend/src/sales_bot/websocket/realtime_feedback_arbiter.py` — enforced one primary action direction per turn and duplicate suppression.
- `backend/src/sales_bot/websocket/stepfun_realtime_handler.py` — carried the same coaching/pacing/alignment behavior onto StepFun while keeping the public snapshot stable.
- `backend/src/common/effectiveness/evaluator.py` — added the shared realtime coaching-focus seam and completed-session sales report-alignment seam.
- `backend/src/common/effectiveness/schemas.py` — typed the shared sales stage/focus vocabulary.
- `backend/src/common/conversation/session_evidence.py` — aligned completed-session projections and exposed alignment diagnostics.
- `web/src/hooks/websocket/message-handlers.ts` — preserved same-turn score refinements and cleared stale coach state on new final transcripts.
- `web/src/components/practice/ScorePanel.tsx` — kept the practice page sales-first while suppressing duplicate textual suggestion noise.
- `web/src/components/practice/RightPanelContent.tsx` — made `action_card` the sole primary textual coach surface.
- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx` — rendered the aligned coach conclusion directly on replay.
- `web/src/lib/session-evidence.ts` — centralized the aligned sales issue/goal vocabulary for replay/admin readability.
