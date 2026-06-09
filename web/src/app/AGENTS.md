# App Router Guide — `web/src/app/`

Scope: Next.js App Router pages and layouts. UI rules: `.kiro/steering/frontend-principles.md`.

## Route-Group Map

- `(auth)/` — `login/`, `forgot-password/`, `reset-password/`. No shell.
- `(dashboard)/` — Learner dashboard: `/`, `training/` (sales + presentation), `history/`, `leaderboard/`, `profile/`, `support/` (+ `support/runtime/`), `agents/[agentId]/`. `DashboardShell` + `requireServerSession`.
- `(user)/` — Dense learner flows:
  - `practice/[sessionId]/` — live practice, `replay/`, `report/` (route-local hooks/tests encouraged)
  - `exam/[sessionId]/` — examiner session + `report/`
  - `learning-path/` — curriculum path entry
  - `study/[learningContentId]/` — chapter study surface
  - `layout.tsx` — session gate only; `practice/layout.tsx` — practice chrome
- `admin/` — Operator console (`AdminShell`, `requiredRoles: ["admin"]`). Nav source of truth: `components/layout/admin-sidebar.tsx`.
  - **Assets**: `agents/`, `personas/`, `knowledge/`, `retrieval-strategies/`, `presentations/`, `curriculum-practice/` (`case-items/`, `role-profiles/`, `templates/`, `examiner-agents/` via shared `content-asset-index.tsx`), `learning-contents/`, `test-bank/`
  - **Sales trainer**: `sales-trainer/` (`units/`, `questions/`, `score-prompts/`, `score-standards/`, `materials/`, `paths/`, `audio-submissions/`, `quiz-attempts/`, `score-results/`, `training-records/`, `operation-logs/`, `settings/`). Read `admin/sales-trainer/AGENTS.md` first.
  - **Policy**: `prompts/`, `business-rules/` (sales-combinations, growth-achievements, ai-coach, next-practice-recommendations, objection-ledger), `scoring-rulesets/`, `governance/`, `voice-runtime/`, `presentation-ai/`, `rag-profiles/` (linked from knowledge, not sidebar)
  - **Analytics**: `records/`, `analytics/`, `analytics/curriculum/`, `supervisor-training/`
  - **Org & system**: `users/`, `settings/`, `logs/`
- `test-mic/` — dev mic check (outside groups)

## Admin Console Patterns

Before adding or refactoring admin pages, read [`.trellis/spec/frontend/admin-console-patterns.md`](../../.trellis/spec/frontend/admin-console-patterns.md). Five hard rules:

1. **List = Index only** — no full create/edit forms on list pages.
2. **Import ≠ View** — bulk import gets its own route (`/import`); no inline upload on list or detail.
3. **Detail vs Edit** — separate by tab or route; complex entities need read-only overview + edit surface.
4. **Sub-resources → sub-routes** — documents, diagnostics, bindings, etc. not stacked on one `[id]` page.
5. **Policy vs Assets** — edit global policy in 策略中心; asset pages bind/reference + read-only preview only (`retrieval-strategies` is the reference).

## Layout Boundaries

- Root `layout.tsx` — providers, `bg-slate-50`, metadata
- `(dashboard)/layout.tsx` — `DashboardShell`
- `admin/layout.tsx` — `AdminShell` + admin role
- `(user)/layout.tsx` — `requireServerSession` only
- `(user)/practice/layout.tsx` — practice-specific chrome

## Local Conventions

- Co-locate route hooks, tests, utilities (`page.test.tsx`, `use-*.ts`, `runtime-lock.ts`)
- No `route.ts`; call backend via `@/lib/api/client`
- Mirror sibling `error.tsx` / `loading.tsx` when adding segments
- Route tests: shell/render contracts, not full integration

## Where to Look

- Learner home: `(dashboard)/page.tsx`
- Practice session: `(user)/practice/[sessionId]/page.tsx`
- Exam: `(user)/exam/[sessionId]/page.tsx`
- Admin home: `admin/page.tsx`
- Shells: `web/src/components/layout/`
