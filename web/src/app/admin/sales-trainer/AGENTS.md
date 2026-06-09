# admin/sales-trainer — Sales Trainer Admin Console

Admin pages for managing sales trainer units, question banks, score prompts/standards, materials, paths, submissions, results, training records, operation logs, and configuration health.

## Route Map

| Route | Purpose |
|-------|---------|
| `page.tsx` | Module overview |
| `units/` | Training unit list/create/edit |
| `questions/` | Question bank and categories |
| `score-prompts/`, `score-standards/` | Scoring prompt and standard governance |
| `materials/` | Training material library |
| `paths/` | Learner path configuration |
| `audio-submissions/`, `quiz-attempts/`, `score-results/` | Attempt/submission review |
| `training-records/`, `operation-logs/` | Audit and learning records |
| `settings/` | Configuration health |

## Where to Look

| Concern | Location |
|---------|----------|
| API client + DTOs | `web/src/lib/api/client-domains.ts`, `web/src/lib/api/types.ts` |
| Backend contract | `docs/api-contract/sales-trainer.md` |
| Admin navigation | `web/src/components/admin/sales-trainer/module-nav.tsx` |
| Unit form | `web/src/components/admin/sales-trainer/unit-form.tsx` |
| Question form | `web/src/components/admin/sales-trainer/question-form.tsx` |
| Score prompt form | `web/src/components/admin/sales-trainer/score-prompt-form.tsx` |
| Admin console patterns | `.trellis/spec/frontend/admin-console-patterns.md` |

## Local Conventions

- Pages compose data loading, empty/error states, and form/list components. Push validation, DTO shaping, and reusable UI into `components/admin/sales-trainer/` or `lib/api`.
- Use `module-nav.tsx` as the navigation source for this admin module. Do not duplicate module lists per page.
- Keep admin list, create, edit, detail, and import concerns on separate routes following the admin-console spec.
- Route tests stay co-located with pages for shell/render contracts; form tests stay beside form components.

## Configuration & Governance

- Score prompts, score standards, unit publish settings, material metadata, path rules, category labels, and filter options are managed business data. Read them from API responses/config endpoints; do not hardcode them into pages.
- Display copy that reflects business policy should come from contract-backed fields or centralized UI copy, not scattered strings inside each route.
- Missing config should render a clear admin remediation state. Illegal config should surface the backend validation reason without inventing client-only policy.
- Actions that publish, archive, score, upload, or manually correct records must expose audit/operation-log effects when the API provides them.

## Hard Rules

- NEVER add Next.js API routes here; call the Python backend through `@/lib/api/client`.
- NEVER bypass `web/src/lib/api` by hand-writing fetch calls in pages.
- NEVER store scoring dimensions, prompt text, material categories, or status transition policy in component-local constants.
- ALWAYS check `backend/src/sales_trainer/AGENTS.md` before changing request/response behavior.
- ALWAYS run the focused page/form tests when touching `page.test.tsx`, `unit-form.test.tsx`, `question-form.test.tsx`, or score/result pages.
