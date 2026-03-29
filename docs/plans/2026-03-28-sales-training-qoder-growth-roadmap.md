# 销售训练 qoder Growth Roadmap

**Date:** 2026-03-28
**Planner mode:** growth-architect
**Scope:** post-M007 roadmap after the core learner/runtime/report/replay/admin foundations are closed

---

## 1. Current System Understanding

### What the product already does well

The product is no longer a thin AI demo. It now has a real training core:

- sales practice and PPT practice both exist on the shipped user route family
- realtime coaching, canonical report, replay, and retry-entry all share a real evidence line
- admin governance for knowledge / persona / presentation / runtime assets is already in place
- supervisor-facing analytics, trend views, intervention records, and operating-pack surfaces exist on current admin routes
- M007 closed the last honest realtime-coaching proof gap: one localhost same-session StepFun sales path now truthfully moves from practice to report to replay, and R009 is validated

### Strengths worth preserving

1. **Single-source evidence design**
   - `SessionEvidenceService`, projection-backed report/replay/history/admin, and shared learner vocabulary are the project’s biggest architectural advantage.
2. **Shipped-route discipline**
   - Most recent milestones deliberately solved problems on real `/practice/{sessionId}`, `/report`, `/replay`, `/admin/*` surfaces rather than debug-only routes.
3. **Operational/admin seam maturity**
   - M005/M006 already hardened admin analytics, intervention, asset governance, and shared read-model seams enough to support incremental product growth.
4. **Live-proof culture**
   - Later milestones increasingly required localhost/browser/API proof instead of only unit tests. That should remain the bar for user-visible claims.

---

## 2. Product Promise

This product should help teams run **repeatable sales and PPT training that changes behavior**, not just generate AI-looking conversations.

It should not drift into:

- entertainment-style AI practice without measurable learning value
- page proliferation that hides missing core-loop behavior
- enterprise integration work before the internal training loop is truly self-sustaining

---

## 3. Current Evidence Snapshot

### Strong evidence

- `.gsd/PROJECT.md` documents M001–M007 closure with the main user loop, report/replay, and admin governance all delivered.
- `.gsd/REQUIREMENTS.md` shows **R001–R015 validated**.
- `backend/src/admin/services/manager_intervention_service.py` and `backend/src/admin/api/interventions.py` prove there is already a persisted intervention workflow seam.
- `backend/src/admin/api/users.py`, `web/src/lib/admin/drill-in.ts`, `web/src/lib/admin/read-models.ts`, and current admin tests prove supervisor drill-in/read-side contracts are already mature.
- `backend/src/presentation_coach/services/interruption_detector.py` and `feedback_service.py` show PPT realtime interruption capability exists as a technical seam, but not yet as a proven user-facing training contract.
- `/support/runtime` plus support runtime tests already provide a base for operational smoke / release-health verification.

### Partial evidence / remaining gaps

1. **Supervisor action loop is still partial**
   - R017 remains deferred.
   - The system can show supervisors what happened, but it still does not fully own the assignment → learner visibility → completion → supervisor review loop.
2. **PPT coaching is still mostly post-hoc**
   - R016 remains deferred.
   - Presentation report/replay are strong, but real in-session interruption/correction is not yet proven as a user-safe core workflow.
3. **Growth planning surfaces are empty**
   - `.codex/roadmap/PROJECT_FUTURE.md`, `.codex/loop/GLM_AUDIT.md`, `.codex/loop/GROWTH_BACKLOG.md`, and `.codex/loop/PROJECT_GROWTH.md` are templates, not working guidance.
4. **Operational verification is still fragmented**
   - The repo has many focused tests and route proofs, but not one clear operator-grade release smoke spanning the main shipped flows.
5. **State/governance hygiene still has some rough edges**
   - The recent M007 close-out needed a workflow-DB metadata correction before generated state fully matched the milestone truth. This is documented, but still a signal that project governance needs one more layer of hardening.

---

## 4. Top Bottlenecks Ordered by Leverage

### 1. Supervisor loop stops at insight more often than action
**Why it matters:** the product can now diagnose and explain, but it still does not fully convert supervisor intent into a durable training assignment loop.

### 2. PPT mode is not yet a true realtime coach
**Why it matters:** PPT practice has good post-session evidence, but not yet the highest-value in-session correction behavior.

### 3. Release/operator confidence is lower than product capability maturity
**Why it matters:** as the system gets more complete, environment noise and verification fragmentation become a bigger drag on iteration speed.

### 4. Product-growth operating system is missing
**Why it matters:** the engineering core is ahead of the growth planning layer; without a real backlog/future profile, future work selection will drift.

---

## 5. Candidate Scoring

Scoring formula:

`user leverage + core-capability leverage + evidence strength + compounding value + validation ease - blast radius`

| Candidate | User | Core | Evidence | Compound | Validation | Blast | Total |
|---|---:|---:|---:|---:|---:|---:|---:|
| GROW-001 Supervisor assignment → completion → review loop (R017 minimal) | 5 | 4 | 5 | 5 | 4 | 2 | **21** |
| GROW-002 Operator/release smoke on shipped routes | 4 | 4 | 5 | 5 | 5 | 2 | **21** |
| GROW-003 PPT realtime interruption/correction milestone starter (R016) | 5 | 5 | 4 | 5 | 2 | 4 | **17** |
| GROW-004 Growth operating system backfill (`PROJECT_FUTURE` / backlog / audit) | 2 | 3 | 5 | 5 | 5 | 1 | **19** |
| GROW-005 Mobile / 企业微信 adaptation (R018) | 3 | 2 | 3 | 3 | 2 | 4 | **9** |
| GROW-006 External integration layer (R019) | 2 | 2 | 2 | 3 | 2 | 5 | **6** |

### Interpretation

- **GROW-001** and **GROW-002** are the best next moves.
- **GROW-003** is strategically important, but should follow after one smaller, safer growth cycle.
- **GROW-004** is not a user-facing feature, but it is a real enabling move that should happen alongside the roadmap handoff.

---

## 6. Recommended Horizons

## Horizon 1 — Turn the system into a true supervisor operating loop

### Recommended first milestone
## M008 — 主管训练重点闭环最小可用化

### User problem
Supervisors can already inspect reports, trends, interventions, and operating-pack signals, but they still rely heavily on offline follow-up to actually assign focus and confirm completion.

### Desired user outcome
A supervisor can:
1. pick a learner’s current issue
2. assign one clear training focus in-system
3. the learner can see that focus before practice
4. after one new completed session, the supervisor can immediately review whether the assigned focus improved

### System-capability outcome
The current intervention and admin drill-in seams become a real workflow loop instead of an observability-only layer.

### Evidence
- `backend/src/admin/services/manager_intervention_service.py`
- `backend/src/admin/api/interventions.py`
- `backend/src/admin/api/users.py`
- `web/src/lib/admin/drill-in.ts`
- `web/src/lib/admin/read-models.ts`
- `web/src/app/admin/users/[id]/page.tsx`
- `web/src/lib/api/client.ts` intervention APIs
- `.gsd/REQUIREMENTS.md` deferred `R017`

### Smallest credible slice
Do **not** build a new task system.

Build only:
- one persisted focus assignment path on existing admin user detail / manager-lite launchers
- one learner-visible “current assigned focus” surface on existing entry/practice/report family
- one supervisor read-back card that links latest evaluable completed session to the assigned focus

### Dependencies
- Reuse current manager intervention write service
- Reuse current admin user detail + report/replay drill-in
- Reuse latest-evaluable result semantics from M005/M006

### Validation plan
- backend integration tests for create/update/remind/result linkage
- web focused tests for admin user detail + learner focus visibility
- browser proof: supervisor assigns focus → learner sees focus → learner finishes one session → supervisor reviews outcome

### Success signal
A supervisor can complete a full “assign → learner trains → review result” loop without leaving the current product route family.

---

## Horizon 2 — Raise operator confidence to match product maturity

### Recommended second milestone
## M009 — 主链路 release-smoke / operator-smoke 收口

### User problem
The product can prove many flows in focused tests, but the operator/developer confidence layer is still fragmented. Runtime noise, stale process alerts, and environment-dependent failures can still blur “product regression” vs “verification environment issue”.

### Desired user outcome
A maintainer can run one trusted smoke command (or a very small set) and know whether the shipped user/admin route family is still healthy.

### System-capability outcome
The product gains a reproducible operational verification layer for:
- learner sales core loop
- PPT report/replay core loop
- supervisor/admin core loop
- support/runtime release-health loop

### Evidence
- current `/support/runtime` surface and tests
- existing `verify:*` / smoke patterns in repo tests and scripts
- recent stale process / config / decrypt noise seen during local verification
- `.gsd/KNOWLEDGE.md` already documents several environment-specific false-regression traps

### Likely files/modules
- `scripts/`
- backend/web verification shims
- support/runtime APIs and current smoke helpers
- admin analytics / user detail browser verification helpers

### Smallest credible slice
One operator-grade smoke chain that proves **the shipped route family**, not every subsystem.

### Validation plan
- clean-shell smoke run
- one localhost proof per route family
- explicit evidence/log export on failure

### Success signal
A failed smoke run tells the team *which* layer is broken (env / auth / runtime / canonical route), instead of just producing noisy crash alerts.

---

## Horizon 3 — Make PPT mode a true realtime coach

### Recommended third milestone
## M010 — PPT realtime interruption / correction contract

### User problem
PPT users can currently get strong post-session feedback, but not enough in-session correction to stop drift, over-talking, or missing critical points while presenting.

### Desired user outcome
During PPT practice, the system can safely and selectively interrupt when the user:
- goes off-topic
- misses required points
- exceeds acceptable coverage drift
- hits forbidden/critical mistakes

### System-capability outcome
Presentation mode becomes a real coach, not just a replay/report system.

### Evidence
- `backend/src/presentation_coach/services/interruption_detector.py`
- `backend/src/presentation_coach/services/feedback_service.py`
- performance tests for interruption latency
- current `presentation_review.page_summaries[*].issue_clusters` evidence already exists
- deferred requirement `R016`

### Smallest credible slice
Do **not** jump straight to “full live interruption everywhere”.

Start with:
- one explicit interruption contract on existing PPT route family
- one narrow set of interrupt reasons
- one learner-facing interruption UX rule
- one end-to-end live proof

### Validation plan
- backend performance/integration tests
- learner browser proof on real PPT session
- replay/report parity after interruption

### Success signal
A PPT learner gets one truthful in-session correction on the shipped route family and can still complete the session without semantic drift between live interruption and final report.

---

## 7. Immediate Next 5 Safe Execution Candidates

### GROW-001 (Recommended first item)
**标题：主管重点闭环最小化：分配重点 → 学员可见 → 结果复查**
- Type: usability / operability
- User problem: 主管知道问题，但系统内还不能完整追踪“布置了什么、学员是否按这个练、结果有没有变”。
- Desired user outcome: supervisor completes one in-system coaching loop on current routes.
- System outcome: intervention seam becomes a real operating loop.
- Smallest slice: add learner-visible assigned focus + result linkage on existing admin/user/practice/report surfaces.
- Validation: backend integration + web focused tests + one browser loop.

### GROW-002
**标题：主链路 operator smoke / release smoke**
- Type: diagnostics / reliability
- User problem: 团队仍可能把环境噪声误判成业务回归。
- Desired user outcome: one trusted smoke verdict for shipped routes.
- System outcome: lower iteration ambiguity.
- Smallest slice: one clean-shell smoke chain for sales report/replay + admin drill-in + support/runtime.
- Validation: repeatable local smoke with explicit artifact output.

### GROW-003
**标题：学员侧“当前被要求重点练什么”显式化**
- Type: usability
- User problem: intervention exists, but learner-side intent carry-forward is still too implicit.
- Desired user outcome: learner starts practice already knowing the assigned focus.
- System outcome: supervisor loop becomes behavior-shaping, not just reporting.
- Dependencies: pairs naturally with GROW-001, but can be executed as its first slice.

### GROW-004
**标题：PPT realtime interruption discovery slice**
- Type: core-capability
- User problem: PPT still relies too much on after-the-fact review.
- Desired user outcome: one safe, trustworthy live correction on current PPT route family.
- System outcome: foundation for R016 without overcommitting to a huge milestone.
- Validation: live PPT browser/runtime proof.

### GROW-005
**标题：增长 operating docs 回填 (`PROJECT_FUTURE` / backlog / audit)`**
- Type: diagnostics / planning-safety
- User problem: next-step selection is under-specified despite a mature codebase.
- Desired user outcome: future work selection becomes evidence-driven.
- System outcome: stronger single-item execution discipline.
- Validation: backlog + roadmap are no longer empty templates and point to one current top item.

---

## 8. Anti-Goals

Do **not** prioritize these now:

1. **New standalone consoles or route families** for supervisor workflow
   - current admin/user/practice/report/replay surfaces are already sufficient
2. **Mobile / 企业微信 adaptation before supervisor loop closure**
   - expands surface area without strengthening the core behavior loop
3. **CRM / SSO / external integration before internal loop is self-sustaining**
   - increases complexity without improving the core training outcome enough yet
4. **Broad architecture refactors across current learner/admin routes**
   - the project’s route-shaped seams are now a strength; preserve them
5. **Feature growth that weakens the evidence line**
   - any new behavior must stay on current `SessionEvidenceService` / projection / admin read-model authority seams

---

## 9. Recommendation

### Best next move
**Start with M008 / GROW-001: supervisor focus assignment loop on existing surfaces.**

Why:
- highest product leverage now
- strongest evidence base already exists in code
- smallest safe blast radius compared with PPT realtime interruption
- directly upgrades the product from “good training system” to “good training operating system”

### Planning handoff suggestion
If execution starts next, the first implementation slice should be:

**S01 — 把当前 intervention 变成 learner-visible assigned focus contract**

That is the narrowest credible move that changes real user behavior while preserving the current architecture.
