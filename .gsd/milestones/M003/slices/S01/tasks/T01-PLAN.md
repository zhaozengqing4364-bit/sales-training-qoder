---
estimated_steps: 4
estimated_files: 3
skills_used:
  - safe-grow
---

# T01: Lock the current admin → runtime → learner entry chain

**Slice:** S01 — 真实入口 inventory 与 current knowledge 真值线
**Milestone:** M003

## Description

Inventory the current routes and modules that already move user value in M003: admin Persona detail, admin knowledge detail, session creation, voice policy freeze, runtime retrieval, and learner report / replay inspection. Rewrite the roadmap and slice plan so they name only those confirmed entrypoints and explicitly exclude environment/tooling-only scope. If any required surface cannot be located in runnable code, the work must stop and be re-scoped to inventory/spike instead of pretending the entrypoint exists.

## Steps

1. Confirm the current admin detail routes that own Persona and knowledge configuration.
2. Confirm the backend authority modules that freeze Persona / knowledge into `voice_policy_snapshot` and drive runtime retrieval.
3. Rewrite the M003 roadmap and S01 plan so they reference only confirmed business-code directories and current product routes.
4. Record the blocker rule and explicit out-of-scope note for Silence / Conda / `.env` / lockfile work.

## Must-Haves

- [ ] The M003 docs name one confirmed business chain from current admin pages to current learner-visible runtime/read surfaces.
- [ ] Tooling or environment artifacts are explicitly marked out of scope unless the milestone goal is later changed to environment migration.

## Verification

- `test -f backend/src/agent/services/persona_policy.py && test -f backend/src/sales_bot/services/voice_runtime_policy.py && test -f backend/src/sales_bot/services/voice_instruction_compiler.py && test -f backend/src/common/api/practice.py && test -f web/src/app/admin/personas/[id]/page.tsx && test -f web/src/app/admin/knowledge/[id]/page.tsx && test -f web/src/app/(user)/practice/[sessionId]/page.tsx && test -f web/src/app/(user)/practice/[sessionId]/report/page.tsx && test -f web/src/app/(user)/practice/[sessionId]/replay/page.tsx`
- `rg -n "persona_policy.py|voice_runtime_policy.py|voice_instruction_compiler.py|practice.py|web/src/app/admin/personas/\[id\]/page.tsx|web/src/app/admin/knowledge/\[id\]/page.tsx|web/src/app/\(user\)/practice/\[sessionId\]/report/page.tsx|Silence|Conda|\.env|lockfile|inventory/spike" .gsd/milestones/M003/M003-ROADMAP.md .gsd/milestones/M003/slices/S01/S01-PLAN.md .gsd/milestones/M003/slices/S01/tasks/T01-PLAN.md`

## Inputs

- `.gsd/OVERRIDES.md` — hard steer that narrows planning to real business code and user value chain
- `.gsd/milestones/M003/M003-CONTEXT.md` — milestone scope, constraints, and acceptance intent
- `backend/src/agent/services/persona_policy.py` — current Persona policy authority
- `backend/src/sales_bot/services/voice_runtime_policy.py` — current runtime policy resolution and snapshot authority
- `backend/src/sales_bot/services/voice_instruction_compiler.py` — current instruction contract compiler
- `backend/src/common/api/practice.py` — current session creation and learner report authority route
- `web/src/app/admin/personas/[id]/page.tsx` — current admin Persona detail entrypoint
- `web/src/app/admin/knowledge/[id]/page.tsx` — current admin knowledge detail entrypoint
- `web/src/app/(user)/practice/[sessionId]/page.tsx` — current learner practice entrypoint
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx` — current learner report entrypoint
- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx` — current learner replay entrypoint

## Expected Output

- `.gsd/milestones/M003/M003-ROADMAP.md` — roadmap rewritten around confirmed business chain, directories, and blocker rule
- `.gsd/milestones/M003/slices/S01/S01-PLAN.md` — slice goal/demo/verification rewritten around current routes only
- `.gsd/milestones/M003/slices/S01/tasks/T01-PLAN.md` — task contract aligned to the confirmed entry chain and out-of-scope guardrails
