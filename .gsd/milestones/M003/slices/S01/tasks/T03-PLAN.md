---
estimated_steps: 4
estimated_files: 3
skills_used:
  - safe-grow
---

# T03: Bind proof and blocker rules to current routes only

**Slice:** S01 — 真实入口 inventory 与 current knowledge 真值线
**Milestone:** M003

## Description

Define the accepted proof surfaces for the rest of M003 using only current product routes and current authority modules. The proof line for this milestone must stay on admin Persona detail, admin knowledge detail, session creation, practice runtime, knowledge-check, report, and replay. If any required surface is missing, stale, or non-production, that is a blocker and the plan must stop at inventory/spike instead of continuing on placeholders.

## Steps

1. Confirm the current user/admin routes that will be accepted as proof surfaces for M003.
2. Confirm the backend authority route and read-side projection surfaces that those pages already depend on.
3. Rewrite the roadmap and slice plan to bind focused backend tests, focused web tests, and later live UAT to those current routes only.
4. Record the explicit blocker rule that missing entrypoints force inventory/spike before execution.

## Must-Haves

- [ ] The M003 docs name one accepted proof surface set on current routes: admin Persona detail, admin knowledge detail, practice page, knowledge-check, report, and replay.
- [ ] The blocker rule is explicit: if a required entrypoint cannot be located in runnable code, the work stops and becomes inventory/spike before implementation.

## Verification

- `test -f web/src/app/admin/personas/[id]/page.tsx && test -f web/src/app/admin/knowledge/[id]/page.tsx && test -f web/src/app/(user)/practice/[sessionId]/page.tsx && test -f web/src/app/(user)/practice/[sessionId]/report/page.tsx && test -f web/src/app/(user)/practice/[sessionId]/replay/page.tsx && test -f backend/src/common/api/practice.py && test -f backend/src/common/conversation/session_evidence.py`
- `rg -n "knowledge-check|report|replay|focused backend|focused web|live UAT|inventory/spike|blocking rule|current routes" .gsd/milestones/M003/M003-ROADMAP.md .gsd/milestones/M003/slices/S01/S01-PLAN.md .gsd/milestones/M003/slices/S01/tasks/T03-PLAN.md`

## Inputs

- `.gsd/OVERRIDES.md` — active override that narrows proof to real business code and user value chain
- `.gsd/milestones/M003/M003-ROADMAP.md` — milestone success criteria and slice boundaries being rewritten
- `.gsd/milestones/M003/slices/S01/S01-PLAN.md` — slice-level proof contract being tightened
- `web/src/app/admin/personas/[id]/page.tsx` — current admin Persona proof surface
- `web/src/app/admin/knowledge/[id]/page.tsx` — current admin knowledge proof surface
- `web/src/app/(user)/practice/[sessionId]/page.tsx` — current learner runtime proof surface
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx` — current learner post-session proof surface
- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx` — current learner replay proof surface
- `backend/src/common/api/practice.py` — current session creation / report / knowledge-check authority route
- `backend/src/common/conversation/session_evidence.py` — current shared read-side evidence surface

## Expected Output

- `.gsd/milestones/M003/M003-ROADMAP.md` — roadmap acceptance boundary rewritten around current proof surfaces only
- `.gsd/milestones/M003/slices/S01/S01-PLAN.md` — slice verification and blocker rule rewritten around current routes only
- `.gsd/milestones/M003/slices/S01/tasks/T03-PLAN.md` — task contract that keeps later M003 proof on real routes and forces inventory/spike when those routes are missing
