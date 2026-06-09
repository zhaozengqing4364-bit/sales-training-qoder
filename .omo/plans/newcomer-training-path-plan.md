# Newcomer Training Path Implementation Plan

## TL;DR
> **Summary**: Reframe the current `sales_trainer` surface into a user-facing "新人训练路径" while keeping realtime AI robot roleplay (`sales_bot` / `practice_sessions`) as a separate future integration. Build a governed modular path with PPT/audio scoring, business-skills article + paper exam, elevator speech audio scoring, and a disabled realtime-practice placeholder.
> **Deliverables**:
> - Product/domain naming boundary: 新人训练路径 vs AI 实时对练.
> - Updated contracts/docs and compatibility strategy for existing `/sales-trainer` technical routes.
> - Module 1 PPT explanation + recording + ASR + AI score path.
> - Module 2 商务技巧 article + paper-managed exam path.
> - Module 3 电梯演讲 10/20/30 recording + scoring path.
> - Module 4 realtime practice placeholder only.
> - Admin management for path modules, articles, papers, questions, prompts, scoring standards, records, and audit.
> **Effort**: Large
> **Parallel**: YES - 5 waves
> **Critical Path**: Contract/naming decisions -> backend paper/article/path model -> admin configuration -> learner flows -> seed/migration -> full QA

## Context

### Original Request
The user clarified that the system currently has two sales-related concepts:

1. AI robot voice realtime conversation/practice.
2. The requested product, which should not be called a sales queue or sales trainer queue, but "新人训练路径".

The requested newcomer path includes:

- Module 1: latest newcomer training path PPT content and explanation points; learner studies and uploads a recording; system transcribes and AI-scores; admin configures scoring rules.
- Module 2: 商务技巧 / pre-client-visit business etiquette; learner reads Markdown article with images and takes a paper-based exam; admin configures article, question bank, papers, questions, and AI scoring prompts; supported question types are single choice, multiple choice, true/false, short answer; short answer is AI-scored; multiple choice also supports AI prompt judgment.
- Module 3: 电梯演讲, PPT speech 10/20/30 minutes, similar structure to the earlier modules.
- Module 4: realtime roleplay with existing robot system, explicitly not developed now.

### Interview Summary

No extra user interview was needed after exploration because the user supplied product intent and the repo exposes the main technical decisions:

- Keep `sales_bot` / `practice_sessions` as realtime AI voice practice.
- Treat current `sales_trainer` as the technical base for 新人训练路径, but change user-facing product language and admin navigation.
- Preserve existing `/sales-trainer` routes during the first release unless a later migration explicitly authorizes URL changes.
- Do not implement realtime roleplay in this plan; create only a disabled placeholder and integration contract.

### Research Findings

- `CONTEXT.md` distinguishes platform direct practice: `VoiceRuntimePolicyService` + `/practice/[sessionId]`, and course/learning flows: `PracticeTemplate` + learning/exam/practice/report.
- `docs/api-contract/sessions.md` and `backend/src/sales_bot/AGENTS.md` define realtime AI voice practice, WebSocket, StepFun, and `PracticeSession` runtime authority.
- `docs/api-contract/sales-trainer.md`, `backend/src/sales_trainer/`, and `web/src/app/(dashboard)/sales-trainer/` define the current non-realtime training base: `quiz`, `audio_scoring`, materials, audio submissions, ASR, Deucate scoring, records, operation logs, and paths.
- `web/src/app/(dashboard)/sales-trainer/page.tsx` still displays "销售训练"; `web/src/lib/sales-trainer/module-path.ts` uses `new_seller_modules_v1` and module labels `PPT演练`, `拜访前商务`, `金字塔演讲`.
- Existing MD article learning is supported through `LearningContent` / `LearningChapter`, `learnerStudy`, and `web/src/app/admin/learning-contents/[contentId]/page.tsx`.
- No first-class `ExamPaper`/`Paper` entity was found; current quiz exams are effectively `SalesTrainerUnit(unit_type="quiz")` plus `SalesTrainerUnitQuestion` bindings to `QuestionItem`.
- Current sales trainer question UI exposes AI scoring config for short-answer questions; multiple-choice AI judgment is not yet a first-class path.

### Metis Review (gaps addressed)

Metis review was requested. If asynchronous feedback returns after this plan is produced, incorporate any new critical findings before execution. The plan already includes guardrails for the likely risk areas: naming collision, paper vs loose question semantics, article content ownership, multi-choice AI scoring determinism, route compatibility, and module-4 scope control.

## Work Objectives

### Core Objective

Create a governed "新人训练路径" product experience on top of the existing `sales_trainer` base, clearly separated from realtime AI robot voice practice, with configurable modules, content, papers, scoring prompts, audit, and verifiable learner/admin flows.

### Deliverables

- Product/domain contract that distinguishes:
  - 新人训练路径: async learning, exams, audio upload, ASR, AI scoring.
  - AI 实时对练: existing `sales_bot` / `practice_sessions` / WebSocket runtime.
- Compatibility-safe naming migration plan and implemented user-facing copy/navigation changes.
- Backend support for paper-managed exams and article binding.
- Admin surfaces for:
  - Path/module configuration.
  - PPT/elevator materials and scoring standards.
  - Business-skills article content.
  - Papers, questions, question ordering, scoring prompts.
  - Records, score results, audio submissions, operation logs.
- Learner surfaces for:
  - Module grid under 新人训练路径.
  - Module 1 PPT explanation recording.
  - Module 2 商务技巧 article reading and paper exam.
  - Module 3 elevator speech recordings.
  - Module 4 disabled realtime-practice placeholder.
- Seed/migration scripts for baseline modules and default content.
- Automated tests and manual QA evidence for every implemented behavior.

### Definition of Done

- `docs/api-contract/sales-trainer.md` or successor newcomer-path contract documents every endpoint, DTO, error code, configurable item, and compatibility alias.
- User-facing UI no longer presents this product as "销售训练" except in backwards-compatible technical names that are intentionally retained.
- Realtime practice remains routed through existing `/practice/[sessionId]`, `/api/v1/practice/sessions`, `sales_bot`, and `training_runtime`; no newcomer-path code calls realtime practice except the disabled placeholder.
- Admin can configure module labels/order/enabled state, article content, paper/question composition, scoring prompts, score standards, materials, and publish/archive lifecycle with audit.
- Learner can complete module 1, module 2, and module 3 flows through real pages.
- Module 4 is visible only as unavailable/coming-soon when enabled by config and cannot start a realtime session.
- Tests pass:
  - Backend focused tests: `cd backend && pytest tests/unit/test_sales_trainer_services.py tests/unit/test_newcomer_training_path*.py`
  - Frontend focused tests: `cd web && npx vitest run src/app/\\(dashboard\\)/sales-trainer src/app/admin/sales-trainer src/components/admin/sales-trainer src/components/sales-trainer src/lib/sales-trainer`
  - Type check: `cd web && npx tsc --noEmit`
- Browser QA artifacts exist for learner module flows and admin management flows under `evidence/`.

### Must Have

- Keep realtime AI robot practice semantically separate.
- Preserve existing technical routes for compatibility during first release unless explicitly changed in a later plan.
- All configurable business rules must have defaults, validation, permission boundary, audit/operation log, and missing/illegal handling.
- Paper/exam management must not be represented only as loose question selection in an unlabeled unit form.
- AI scoring for multi-choice must be opt-in and explain why/when it runs; deterministic fixed-answer grading remains default.

### Must NOT Have

- Do not implement realtime roleplay module 4 now.
- Do not rename `backend/src/sales_trainer` or mass-migrate code paths in the first implementation wave.
- Do not hardcode article text, scoring thresholds, prompt text, module labels, material URLs, paper composition, or enabled modules in page components.
- Do not reuse `/admin/presentations` semantics for newcomer training materials unless the contract explicitly maps the relationship.
- Do not let frontend pages hand-write API fetches; use `web/src/lib/api/client`.

## Verification Strategy

> ZERO HUMAN INTERVENTION - all verification is agent-executed.

- Test decision: TDD for production changes; docs-only updates use static/diff checks.
- Backend framework: pytest.
- Frontend framework: Vitest + React Testing Library + TypeScript.
- Browser QA: use Browser/Playwright against real local app pages after implementation.
- HTTP QA: use `curl -i` against live backend for API acceptance where browser does not cover the criterion.
- Evidence path convention: `evidence/task-{N}-{slug}.{log|png|json|txt}`.

## Execution Strategy

### Parallel Execution Waves

Wave 1: Contract, naming, and domain-model foundation.
Wave 2: Backend article/paper/module model and services.
Wave 3: Admin UI and API facade.
Wave 4: Learner UI flows and seed data.
Wave 5: Integration, compatibility, QA, and reviews.

### Dependency Matrix

| Task | Blocks | Blocked By |
|------|--------|------------|
| 1 Domain boundary docs | 2, 3, 4, 5, 6, 7, 8 | none |
| 2 Newcomer path config contract | 3, 4, 5, 6, 7 | 1 |
| 3 Paper/exam backend | 5, 6, 8, 9 | 1, 2 |
| 4 Article binding backend | 5, 7, 8 | 1, 2 |
| 5 Admin API facade/types | 6, 7, 8 | 2, 3, 4 |
| 6 Admin management UI | 9, 10 | 3, 5 |
| 7 Learner module flows | 10 | 4, 5 |
| 8 Seed/migrations | 9, 10 | 2, 3, 4 |
| 9 Backend integration tests | 10 | 3, 8 |
| 10 Browser/manual QA | Final | 6, 7, 8, 9 |

## TODOs

- [x] 1. Define Domain Boundary And Naming Contract

  **What to do**: Update documentation first so every later implementer understands that 新人训练路径 is not realtime AI robot practice. Add/adjust a contract section in `docs/api-contract/sales-trainer.md` or a new `docs/api-contract/newcomer-training-path.md` that states: user-facing name is 新人训练路径; `sales_trainer` is a compatibility technical namespace for this release; realtime practice remains `practice_sessions` + `sales_bot` + `/practice/[sessionId]`; module 4 is placeholder only. Update `CONTEXT.md` with a concise glossary entry.

  **Must NOT do**: Do not rename source directories or API base paths in this task. Do not remove the existing sales trainer contract without adding compatibility references.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 2, 3, 4, 5, 6, 7, 8 | Blocked By: none

  **References**:
  - Pattern: `CONTEXT.md` - glossary style and "禁止" sections.
  - Pattern: `docs/api-contract/sessions.md` - realtime `PracticeSession` authority and `voice_policy_snapshot`.
  - Pattern: `docs/api-contract/sales-trainer.md` - current async training contract.
  - Pattern: `backend/src/sales_bot/AGENTS.md` - realtime sales practice domain definition.
  - Pattern: `backend/src/sales_trainer/AGENTS.md` - current async sales trainer/newcomer-path technical base.

  **Acceptance Criteria**:
  - [ ] Documentation states the two systems and their boundaries in Chinese.
  - [ ] Documentation explicitly records compatibility decision: keep `/sales-trainer` and `sales_trainer` technical names in first release.
  - [ ] Documentation explicitly marks realtime roleplay module 4 as "not developed now".
  - [ ] Command: `rg -n "新人训练路径|sales_bot|practice_sessions|sales_trainer|实时对练" CONTEXT.md docs/api-contract`.

  **QA Scenarios**:
  ```
  Scenario: Boundary docs can be discovered by an implementer
    Tool: bash
    Steps: rg -n "新人训练路径|AI 实时对练|sales_bot|practice_sessions|sales_trainer" CONTEXT.md docs/api-contract
    Expected: Output includes one glossary hit, one newcomer-path contract hit, and one realtime-practice contrast hit.
    Evidence: evidence/task-1-boundary-docs.txt

  Scenario: No accidental implementation change
    Tool: bash
    Steps: git diff --name-only | rg -v '^(CONTEXT.md|docs/api-contract/|plans/|\\.omo/drafts/|evidence/)'
    Expected: No output for this task.
    Evidence: evidence/task-1-docs-only.txt
  ```

  **Commit**: YES | Message: `docs(newcomer-path): define domain boundary` | Files: `CONTEXT.md`, `docs/api-contract/*`

- [x] 2. Specify Newcomer Path Module Configuration Contract

  **What to do**: Define a structured module configuration contract to replace implicit hardcoded labels in `web/src/lib/sales-trainer/module-path.ts`. The contract must include path key, module key, display name, description, order, enabled state, module type (`audio_scoring`, `article_exam`, `audio_scoring_group`, `realtime_placeholder`), completion rule, target unit/paper/content bindings, admin permissions, audit event names, defaults, validation, missing-config behavior, and illegal-config behavior.

  **Must NOT do**: Do not keep module labels as the only source of truth in frontend constants. Do not make module 4 start realtime sessions.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 3, 4, 5, 6, 7, 8 | Blocked By: 1

  **References**:
  - Pattern: `web/src/lib/sales-trainer/module-path.ts` - current hardcoded module labels and path key.
  - Pattern: `backend/src/sales_trainer/schemas.py` - `SalesTrainerPathConfig`, `SalesTrainerTaskBriefConfig`, validation style.
  - Pattern: `backend/src/sales_trainer/services/path_service.py` - current path aggregation.
  - Pattern: `docs/plans/2026-05-29-sales-trainer-three-modules.md` - existing three-module intent.

  **Acceptance Criteria**:
  - [ ] Contract defines all four modules and marks module 4 as disabled/coming soon by default.
  - [ ] Contract lists defaults, validators, permissions, audit action names, fallback behavior.
  - [ ] Contract says module labels come from backend/config, not frontend hardcoded strings.
  - [ ] Command: `rg -n "module_key|article_exam|realtime_placeholder|电梯演讲|商务技巧" docs/api-contract`.

  **QA Scenarios**:
  ```
  Scenario: Contract covers all configured module types
    Tool: bash
    Steps: rg -n '"audio_scoring"|"article_exam"|"audio_scoring_group"|"realtime_placeholder"' docs/api-contract
    Expected: All four module type strings appear in the newcomer path contract.
    Evidence: evidence/task-2-module-contract.txt

  Scenario: Config missing/illegal behavior is documented
    Tool: bash
    Steps: rg -n "缺失|非法|fallback|兜底|validation|校验" docs/api-contract
    Expected: Output includes newcomer path module config missing and illegal handling sections.
    Evidence: evidence/task-2-config-fallbacks.txt
  ```

  **Commit**: YES | Message: `docs(newcomer-path): specify module configuration` | Files: `docs/api-contract/*`

- [x] 3. Add Paper-Managed Exam Backend Contract And Tests

  **What to do**: Introduce a paper/exam management layer for module 2. Preferred implementation: add `NewcomerExamPaper` or `SalesTrainerExamPaper` model plus paper-question binding model, while preserving existing `QuestionItem` as the question source. Provide services and API endpoints for list/create/update/publish/archive papers, bind/reorder questions, and submit paper attempts. If a smaller implementation wraps existing `SalesTrainerUnit(unit_type="quiz")`, it must still expose paper semantics in DTOs and admin UI and must not look like loose unit question binding.

  **Must NOT do**: Do not force admins to manage the exam only by editing a generic quiz training unit. Do not duplicate question data instead of referencing `QuestionItem`.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: 5, 6, 8, 9 | Blocked By: 1, 2

  **References**:
  - Pattern: `backend/src/sales_trainer/models.py` - `SalesTrainerUnit`, `SalesTrainerUnitQuestion`, `SalesTrainerQuizAttempt`.
  - Pattern: `backend/src/sales_trainer/services/quiz_service.py` - current attempt scoring and answer snapshots.
  - Pattern: `backend/src/sales_trainer/services/question_service.py` - sales trainer question bank wrapper over `QuestionItem`.
  - Pattern: `docs/api-contract/test-bank.md` - `QuestionItem` contract.
  - API: `backend/src/sales_trainer/api.py` - admin router and learner router style.

  **Acceptance Criteria**:
  - [ ] Test-first: add failing backend tests for paper create/publish, question ordering, learner submission, missing paper, archived paper.
  - [ ] Admin API supports paper lifecycle and question composition.
  - [ ] Learner API can fetch a published paper and submit answers.
  - [ ] Existing quiz attempt behavior remains compatible.
  - [ ] Commands: `cd backend && pytest tests/unit/test_newcomer_training_path_papers.py tests/unit/test_sales_trainer_services.py`.

  **QA Scenarios**:
  ```
  Scenario: Admin creates and publishes 商务技巧 paper
    Tool: HTTP call
    Steps: curl -i -X POST http://localhost:8000/api/v1/admin/newcomer-training/papers ... then publish endpoint with a payload binding one single choice and one short answer question.
    Expected: HTTP 200/201, response status published, ordered questions preserved.
    Evidence: evidence/task-3-admin-paper-http.txt

  Scenario: Learner cannot fetch draft paper
    Tool: HTTP call
    Steps: curl -i http://localhost:8000/api/v1/newcomer-training/papers/{draftPaperId}
    Expected: HTTP 404 or explicit [PAPER_NOT_FOUND]/[PAPER_NOT_PUBLISHED], no draft content leaked.
    Evidence: evidence/task-3-draft-paper-http.txt
  ```

  **Commit**: YES | Message: `feat(newcomer-path): add paper exam backend` | Files: `backend/src/sales_trainer/*`, `backend/alembic/versions/*`, `backend/tests/unit/*`, `docs/api-contract/*`

- [x] 4. Add Article Binding And Learning Content Adapter

  **What to do**: Reuse the existing `LearningContent` / `LearningChapter` system for Markdown article content, but expose newcomer-path-specific binding and validation. Add service methods that resolve a module's `learning_content_id`, verify the content is published, expose a learner article DTO, and let admin bind/rebind article content to the 商务技巧 module. Use existing admin learning-content editor for actual article editing unless this task adds a thin newcomer-path shortcut route.

  **Must NOT do**: Do not create a second markdown article table unless the existing learning content system cannot satisfy image/MD publishing. Do not hardcode "见客户前商务礼仪" article body in seed or component source without admin-manageable content.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 5, 7, 8 | Blocked By: 1, 2

  **References**:
  - Pattern: `backend/src/curriculum_practice/services/learning_progress_service.py` - published content and chapters.
  - Pattern: `web/src/app/admin/learning-contents/[contentId]/page.tsx` - admin MD chapter editing.
  - Pattern: `web/src/app/(dashboard)/sales-trainer/learn/[unitId]/page.tsx` - current learner article reader.
  - Pattern: `web/src/components/sales-trainer/coo-chapter-reader.tsx` - Markdown rendering with `ReactMarkdown`.

  **Acceptance Criteria**:
  - [ ] Test-first: backend test fails then passes for resolving published content and rejecting draft/missing content.
  - [ ] Admin can bind a published learning content to the 商务技巧 module.
  - [ ] Learner receives article/chapter content through newcomer-path flow.
  - [ ] Markdown image syntax renders in browser QA without unsafe custom HTML.
  - [ ] Commands: `cd backend && pytest tests/unit/test_newcomer_training_path_articles.py`; `cd web && npx vitest run src/app/\\(dashboard\\)/sales-trainer/learn src/components/sales-trainer/coo-chapter-reader.test.tsx`.

  **QA Scenarios**:
  ```
  Scenario: Learner opens 商务技巧 article
    Tool: Browser use
    Steps: Open http://localhost:3445/sales-trainer/learn/hub, click 商务技巧 article/chapter, assert title "见客户前商务礼仪" and an image alt text render.
    Expected: Article page renders Markdown text and image; no console error.
    Evidence: evidence/task-4-article-browser.png

  Scenario: Draft article is not available to learner
    Tool: HTTP call
    Steps: curl -i http://localhost:8000/api/v1/newcomer-training/modules/business-skills/article with module bound to draft content.
    Expected: HTTP 404 or [LEARNING_CONTENT_NOT_PUBLISHED].
    Evidence: evidence/task-4-draft-article-http.txt
  ```

  **Commit**: YES | Message: `feat(newcomer-path): bind business skills article content` | Files: `backend/src/sales_trainer/*`, `web/src/app/(dashboard)/sales-trainer/*`, `web/src/components/sales-trainer/*`, tests

- [x] 5. Extend API Facade And Shared Types For Newcomer Path

  **What to do**: Add typed frontend API methods for newcomer path modules, papers, article bindings, paper attempts, and module status. Keep existing `api.salesTrainer` methods as compatibility aliases if they remain in use. Add TypeScript DTOs for module config, paper, paper question, paper attempt, article binding, module status, and realtime placeholder.

  **Must NOT do**: Do not hand-code fetches in page components. Do not silently change existing `api.salesTrainer` return shapes without updating all consumers and tests.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: 6, 7 | Blocked By: 2, 3, 4

  **References**:
  - Pattern: `web/src/lib/api/client-domains.ts` - current domain builder structure.
  - Pattern: `web/src/lib/api/types.ts` - DTO type definitions.
  - Pattern: `web/src/lib/api/sales-trainer.test.ts` - API facade tests if present.
  - Pattern: `web/src/lib/AGENTS.md` - pages import `api` from `client.ts` only.

  **Acceptance Criteria**:
  - [ ] Test-first: API facade tests fail for missing newcomer paper/article methods before implementation.
  - [ ] `api.newcomerTraining` exists, or `api.salesTrainer.newcomerPath` exists with explicit compatibility rationale.
  - [ ] Existing sales trainer tests still pass.
  - [ ] Command: `cd web && npx vitest run src/lib/api`.

  **QA Scenarios**:
  ```
  Scenario: API facade exposes newcomer path methods
    Tool: bash
    Steps: cd web && npx vitest run src/lib/api/sales-trainer.test.ts src/lib/api/newcomer-training.test.ts
    Expected: Tests pass and assert request URLs for modules, papers, article bindings, and attempts.
    Evidence: evidence/task-5-api-facade-vitest.txt

  Scenario: No page-level raw fetch introduced
    Tool: bash
    Steps: rg -n "fetch\\(" web/src/app/\\(dashboard\\)/sales-trainer web/src/app/admin/sales-trainer
    Expected: No raw fetch calls in newcomer/sales-trainer pages.
    Evidence: evidence/task-5-no-raw-fetch.txt
  ```

  **Commit**: YES | Message: `feat(newcomer-path): add typed api facade` | Files: `web/src/lib/api/*`, tests

- [x] 6. Build Admin Newcomer Path Management Surfaces

  **What to do**: Update admin UI so business users manage 新人训练路径 rather than a generic sales trainer unit list. Required surfaces: module overview, module config edit, PPT/elevator material bindings, scoring standards, 商务技巧 article binding shortcut, paper list/create/edit/publish/archive, paper question ordering, AI scoring prompt configuration for short answer and AI-assisted multiple choice, records/logs. Existing sales-trainer admin pages may be reused but labels/navigation must reflect 新人训练路径.

  **Must NOT do**: Do not require admins to edit raw JSON for normal module, paper, article, or prompt operations. Do not duplicate navigation lists outside `module-nav.tsx` or the chosen source of truth.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: 10 | Blocked By: 3, 5

  **References**:
  - Pattern: `web/src/app/admin/sales-trainer/AGENTS.md` - admin sales trainer/newcomer path local rules.
  - Pattern: `web/src/app/admin/sales-trainer/units/page.tsx` and `units/new/page.tsx` - existing unit admin.
  - Pattern: `web/src/components/admin/sales-trainer/module-nav.tsx` - local navigation source.
  - Pattern: `web/src/components/admin/sales-trainer/question-form.tsx` - current question and AI short-answer form.
  - Pattern: `.trellis/spec/frontend/admin-console-patterns.md` - list/detail/edit/import separation.

  **Acceptance Criteria**:
  - [ ] Test-first: admin page tests fail for missing 新人训练路径 labels and paper management routes before implementation.
  - [ ] Admin nav and headings use 新人训练路径 / 商务技巧 / 电梯演讲 labels.
  - [ ] Paper create/edit supports question order, points, deterministic grading, optional AI judgment prompt for multiple choice.
  - [ ] Article binding shows current published article and links to learning content editor or inline shortcut.
  - [ ] Commands: `cd web && npx vitest run src/app/admin/sales-trainer src/components/admin/sales-trainer && npx tsc --noEmit`.

  **QA Scenarios**:
  ```
  Scenario: Admin creates 商务技巧 paper
    Tool: Browser use
    Steps: Open http://localhost:3445/admin/sales-trainer/papers/new, fill paper title "商务礼仪入门考卷", add two questions, set AI multi-choice judging prompt, save, publish.
    Expected: Browser shows published status and ordered question list.
    Evidence: evidence/task-6-admin-paper-browser.png

  Scenario: Admin sees module naming not sales queue
    Tool: Browser use
    Steps: Open http://localhost:3445/admin/sales-trainer and inspect nav/headings.
    Expected: Page uses 新人训练路径; no "销售队列" text; module labels include 商务技巧 and 电梯演讲.
    Evidence: evidence/task-6-admin-naming-browser.png
  ```

  **Commit**: YES | Message: `feat(newcomer-path): add admin management surfaces` | Files: `web/src/app/admin/sales-trainer/*`, `web/src/components/admin/sales-trainer/*`, tests

- [x] 7. Update Learner Newcomer Path Experience

  **What to do**: Update learner pages to present 新人训练路径 as the product. Module grid should include module 1 PPT讲解录音, module 2 商务技巧 article + paper exam, module 3 电梯演讲 10/20/30, module 4 realtime placeholder disabled. Use backend/config labels and module DTOs rather than hardcoded frontend copy. Preserve existing route compatibility initially.

  **Must NOT do**: Do not start realtime sessions from module 4. Do not hide missing config with fake success. Do not block audio upload by fixed duration.

  **Parallelization**: Can Parallel: YES | Wave 4 | Blocks: 10 | Blocked By: 4, 5

  **References**:
  - Pattern: `web/src/app/(dashboard)/sales-trainer/page.tsx` - current learner home.
  - Pattern: `web/src/components/sales-trainer/sales-trainer-module-grid.tsx` - current module cards.
  - Pattern: `web/src/app/(dashboard)/sales-trainer/audio/[unitId]/page.tsx` - audio upload flow.
  - Pattern: `web/src/app/(dashboard)/sales-trainer/quiz/[unitId]/page.tsx` - current quiz flow.
  - Pattern: `web/src/app/(dashboard)/sales-trainer/learn/[unitId]/page.tsx` - current MD article learner flow.

  **Acceptance Criteria**:
  - [ ] Test-first: learner page tests fail for expected 新人训练路径 labels and module 4 disabled state before implementation.
  - [ ] Module 1 opens audio upload with material/brief/score standard.
  - [ ] Module 2 opens article then paper exam.
  - [ ] Module 3 offers 10/20/30 or configured options.
  - [ ] Module 4 renders disabled/coming-soon and does not call `api.practice.createSession`.
  - [ ] Commands: `cd web && npx vitest run src/app/\\(dashboard\\)/sales-trainer src/components/sales-trainer src/lib/sales-trainer && npx tsc --noEmit`.

  **QA Scenarios**:
  ```
  Scenario: Learner completes module 2 happy path
    Tool: Browser use
    Steps: Open http://localhost:3445/sales-trainer, click 商务技巧, read article, click start exam, answer one single choice and one short answer, submit.
    Expected: Result page shows submitted/scored state and feedback; URL remains compatible.
    Evidence: evidence/task-7-learner-module2-browser.png

  Scenario: Module 4 is unavailable
    Tool: Browser use
    Steps: Open http://localhost:3445/sales-trainer and click realtime practice placeholder.
    Expected: No navigation to /practice; page displays 暂不开放/敬请期待 or configured disabled reason.
    Evidence: evidence/task-7-module4-disabled-browser.png
  ```

  **Commit**: YES | Message: `feat(newcomer-path): update learner module flows` | Files: `web/src/app/(dashboard)/sales-trainer/*`, `web/src/components/sales-trainer/*`, `web/src/lib/sales-trainer/*`, tests

- [x] 8. Add Seed And Migration Path For Baseline Newcomer Modules

  **What to do**: Add or update backend scripts to seed baseline 新人训练路径 modules: module 1 PPT explanation, module 2 商务技巧 article/paper, module 3 电梯演讲 10/20/30, module 4 disabled realtime placeholder. Seed should upsert by stable keys, publish required materials/content/papers where appropriate, and provide `--verify-only`.

  **Must NOT do**: Do not delete existing `new_seller_modules_v1` data. Do not hardcode final article content in code except as seed fixture content that admins can later edit. Do not store secrets or provider credentials in seed.

  **Parallelization**: Can Parallel: YES | Wave 4 | Blocks: 9, 10 | Blocked By: 2, 3, 4

  **References**:
  - Pattern: `docs/plans/2026-05-29-sales-trainer-three-modules.md` - current seed steps.
  - Pattern: `backend/scripts/seed_sales_trainer_three_modules.py` if present - existing upsert/verify script.
  - Pattern: `backend/scripts/import_coo_learning_content.py` and `backend/scripts/seed_coo_questions.py` if present - learning content/question seed style.
  - Pattern: `backend/src/sales_trainer/services/operation_log_service.py` - audit action expectations.

  **Acceptance Criteria**:
  - [ ] Test-first or script dry-run test covers idempotent upsert and verify-only.
  - [ ] Seed creates no duplicate modules/papers/questions on repeated run.
  - [ ] Seed creates admin-editable content records, not frontend constants.
  - [ ] Command: `cd backend && PYTHONPATH=src python scripts/seed_newcomer_training_path.py --verify-only`.

  **QA Scenarios**:
  ```
  Scenario: Seed verify confirms baseline modules
    Tool: tmux
    Steps: tmux new-session -d -s ulw-qa-seed 'cd backend && PYTHONPATH=src python scripts/seed_newcomer_training_path.py --verify-only'; tmux capture-pane -pt ulw-qa-seed
    Expected: Transcript includes PASS for modules 1-4, article binding, paper binding, audio scoring configs.
    Evidence: evidence/task-8-seed-tmux.txt

  Scenario: Repeated seed is idempotent
    Tool: bash
    Steps: cd backend && PYTHONPATH=src python scripts/seed_newcomer_training_path.py && PYTHONPATH=src python scripts/seed_newcomer_training_path.py --verify-only
    Expected: Second run reports updated/existing resources, not duplicate creation errors.
    Evidence: evidence/task-8-seed-idempotent.txt
  ```

  **Commit**: YES | Message: `feat(newcomer-path): seed baseline modules` | Files: `backend/scripts/*`, `backend/tests/*`, docs

- [x] 9. Implement Backend Integration And Regression Tests

  **What to do**: Add focused backend tests that prove the full newcomer path backend works and does not regress existing sales trainer or realtime practice boundaries. Cover module config validation, paper lifecycle, article binding, audio scoring config, multi-choice AI config behavior, module-4 disabled behavior, audit logs, and compatibility aliases.

  **Must NOT do**: Do not skip existing sales trainer service tests. Do not mock away all service boundaries in integration tests; at least one test must exercise API/service wiring.

  **Parallelization**: Can Parallel: YES | Wave 5 | Blocks: 10 | Blocked By: 3, 8

  **References**:
  - Pattern: `backend/tests/unit/test_sales_trainer_services.py` - current service coverage.
  - Pattern: `backend/tests/unit/test_curriculum_plan_schema.py` - schema/path style tests.
  - Pattern: `backend/tests/unit/test_runtime_dependency_contract.py` - boundary regression style.
  - Pattern: `backend/tests/unit/test_runtime_preflight_service.py` - terminal failure tests.

  **Acceptance Criteria**:
  - [ ] Tests verify newcomer path cannot use realtime `sales_bot` runtime except placeholder metadata.
  - [ ] Tests verify missing article/paper/scoring config gives typed errors.
  - [ ] Tests verify invalid module config is rejected.
  - [ ] Tests verify audit logs for publish/archive/retry/manual correction.
  - [ ] Command: `cd backend && pytest tests/unit/test_newcomer_training_path*.py tests/unit/test_sales_trainer_services.py tests/unit/test_runtime_dependency_contract.py`.

  **QA Scenarios**:
  ```
  Scenario: Backend boundary regression
    Tool: bash
    Steps: cd backend && pytest tests/unit/test_newcomer_training_path_boundary.py -q
    Expected: Test asserts newcomer path module 4 config does not create PracticeSession or import sales_bot runtime.
    Evidence: evidence/task-9-boundary-tests.txt

  Scenario: Backend typed config failure
    Tool: HTTP call
    Steps: curl -i -X POST http://localhost:8000/api/v1/admin/newcomer-training/modules with malformed module type "sales_queue".
    Expected: HTTP 422 or [NEWCOMER_MODULE_CONFIG_INVALID] with trace_id.
    Evidence: evidence/task-9-invalid-config-http.txt
  ```

  **Commit**: YES | Message: `test(newcomer-path): cover backend contracts` | Files: `backend/tests/*`, possible small fixes in backend source

- [x] 10. Run Full Manual QA And Compatibility Review

  **What to do**: Start the local stack, run browser QA for admin and learner surfaces, run HTTP QA for backend endpoints, capture evidence, and ensure no leftover QA state. Verify compatibility pages still load under existing `/sales-trainer` route and no existing realtime practice route was changed.

  **Must NOT do**: Do not declare done from tests alone. Do not leave servers/tmux sessions running without cleanup receipt.

  **Parallelization**: Can Parallel: NO | Wave 5 | Blocks: Final | Blocked By: 6, 7, 8, 9

  **References**:
  - Pattern: `scripts/README.md` - dev stack and smoke commands.
  - Pattern: `web/playwright.config.ts` - browser QA setup.
  - Pattern: `docs/api-contract/sessions.md` - realtime practice compatibility endpoints.
  - Pattern: `docs/api-contract/sales-trainer.md` or newcomer path contract - async training endpoints.

  **Acceptance Criteria**:
  - [ ] Admin browser QA passes for module config, article binding, paper management, scoring prompt, audit/log pages.
  - [ ] Learner browser QA passes for module 1, module 2, module 3, and module 4 disabled placeholder.
  - [ ] HTTP QA passes for key admin and learner endpoints.
  - [ ] Compatibility check: `/sales-trainer` still loads or redirects intentionally; `/practice/[sessionId]` and `/api/v1/practice/sessions` semantics are unchanged.
  - [ ] Cleanup receipts captured: tmux sessions closed, dev servers stopped if started by QA.

  **QA Scenarios**:
  ```
  Scenario: Full learner path smoke
    Tool: Browser use
    Steps: Open http://localhost:3445/sales-trainer, verify 新人训练路径 title, run module 1 upload test fixture, module 2 article+paper, module 3 elevator option, module 4 disabled.
    Expected: All four module surfaces match configured behavior and screenshots captured.
    Evidence: evidence/task-10-learner-full-smoke.png

  Scenario: Realtime practice untouched
    Tool: HTTP call
    Steps: curl -i http://localhost:8000/api/v1/practice/history and optionally POST /api/v1/practice/sessions with existing valid fixture payload.
    Expected: Response schema still matches `docs/api-contract/sessions.md`; no newcomer path fields leak into practice session response.
    Evidence: evidence/task-10-realtime-compat-http.txt

  Scenario: QA cleanup
    Tool: bash
    Steps: tmux ls || true; lsof -i :3445 -i :8000 || true
    Expected: Only intentional user/dev processes remain; any QA-started sessions are stopped and recorded.
    Evidence: evidence/task-10-cleanup.txt
  ```

  **Commit**: NO | Message: n/a | Files: `evidence/*`


## Final Verification Wave (MANDATORY - after ALL implementation tasks)

> ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.

- [x] F1. Plan Compliance Audit
- [x] F2. Code Quality Review
- [x] F3. Real Manual QA
- [x] F4. Scope Fidelity Check

## Commit Strategy

- Use atomic Conventional Commits.
- Suggested sequence:
  - `docs(newcomer-path): define domain boundary and contract`
  - `feat(newcomer-path): add paper and article configuration backend`
  - `feat(newcomer-path): add admin management surfaces`
  - `feat(newcomer-path): update learner module flows`
  - `test(newcomer-path): cover module, paper, and scoring flows`
- Do not auto-commit without user approval.

## Success Criteria

- Newcomer training path is visible and understandable to learners/admins without the misleading "销售训练队列" language.
- Existing realtime AI practice remains untouched and clearly separate.
- Module 1/2/3 are configurable, test-covered, and browser-QA verified.
- Module 4 is explicitly out of scope except for a safe placeholder.
- Paper-based exam management and article management are first-class enough that business users are not forced to edit raw JSON or loose question bindings.
