# PPT Flow Full Repair and Role Design

## TL;DR

> **Quick Summary**: Repair the PPT practice flow end-to-end by fixing frontend render bootstrap, implementing real thumbnail generation/storage/serving, hardening interruption cancellation parity, and wiring prompt-role runtime design into presentation coaching.
>
> **Deliverables**:
> - Stable PPT practice rendering from `/training/presentation` to `/practice/{sessionId}`
> - Working thumbnail pipeline (`upload -> generate -> persist -> serve -> display`)
> - Presentation interruption behavior aligned with robust sales cancellation semantics
> - Prompt-role runtime resolver for presentation scenario (hybrid baseline + template/persona overrides)
> - TDD test suite additions across backend/frontend with executable E2E QA scenarios
>
> **Estimated Effort**: Large
> **Parallel Execution**: YES - 4 waves
> **Critical Path**: Task 1 -> Task 2 -> Task 3 -> Task 5 -> Task 6 -> Task 8

---

## Context

### Original Request

User requested comprehensive implementation for PPT flow issues:
- frontend cannot display properly,
- backend thumbnails cannot display,
- AI interruption logic (like existing active interruption behavior) must be implemented fully,
- prompt-role design must be implemented comprehensively.

### Interview Summary

**Key Discussions**:
- PPT path is already structured in product flow, but broken at key integration points.
- Thumbnail failure is not a single UI bug; pipeline implementation gaps exist.
- Interruption logic exists in presentation handler, but parity and cancellation depth lag sales runtime.
- Prompt-template platform exists, but presentation runtime still contains hardcoded prompt/response paths.
- User confirmed test strategy: **TDD**.

**Research Findings**:
- Frontend depends on WS `slide_update` for initial PPT panel state; missing bootstrap can leave placeholder forever.
- `ppt_parser.generate_thumbnail()` is TODO and returns empty string.
- `Page.image_url` is never written in active presentation upload flow.
- Thumbnail serving contract is incomplete and storage conventions are fragmented.
- Sales runtime has proven interruption patterns (`stream_id`, task cancellation, stale stream filtering) reusable for PPT.
- Prompt-template scenario binding exists, but PPT runtime does not fully consume agent/persona/template composition.

### Metis Review

**Identified Gaps** (addressed in this plan):
- Missing explicit acceptance criteria for full chain from upload to rendering.
- Missing guardrails to prevent sales regression and scope explosion.
- Missing explicit cancellation state-machine requirements for interruption parity.
- Missing edge-case coverage (reconnection during interruption, partial generation, missing template fallback).

### Defaults Applied

- **Test strategy**: TDD (user confirmed).
- **Prompt role strategy**: Hybrid (baseline presentation coach + scenario/persona overrides).
- **Thumbnail access policy**: Authenticated backend thumbnail endpoint, frontend renders via fetched blob/object URL (no unauthenticated raw static exposure by default).
- **Legacy data policy**: Read compatibility + lazy/backfill strategy for existing presentations missing `image_url`.
- **Thumbnail format baseline**: PNG output as baseline contract (future optimization can add JPEG/WebP switch).

---

## Work Objectives

### Core Objective

Deliver a production-safe PPT practice flow where users can reliably start and run PPT sessions, see slide/thumbnails, receive robust interruption behavior, and experience configurable coach-role prompt behavior with deterministic fallbacks.

### Concrete Deliverables

- Repaired frontend PPT route bootstrap and right-panel rendering in practice session.
- Backend thumbnail generation and persistence wired into presentation ingestion.
- Thumbnail serving contract implemented and consumed by frontend.
- Presentation websocket interruption logic upgraded to cancellable, stream-aware behavior.
- Prompt-role runtime resolver integrated into presentation runtime using hybrid policy.
- TDD tests and E2E verification scenarios for all critical paths.

### Definition of Done

- [ ] New presentation upload produces page rows with non-empty thumbnail references.
- [ ] Admin PPT detail page renders real thumbnails (not only placeholders) for ready presentations.
- [ ] `/practice/{sessionId}` in presentation mode reliably shows initial slide context without manual workaround.
- [ ] User interruption during AI speaking cancels active playback/generation deterministically and returns to listening state.
- [ ] Presentation interruption feedback uses prompt-role resolver chain with documented fallback precedence.
- [ ] Added tests pass for backend + frontend + scenario-level QA commands listed below.

### Must Have

- Keep PPT and sales scenario behavior isolated (no breaking changes in sales runtime).
- Keep "no popup error" principle in all new failure paths.
- Ensure interruption and thumbnail states are observable with structured logs and trace context.
- Implement idempotent thumbnail generation behavior (re-run safe).
- Implement deterministic prompt-role fallback chain when bindings are missing.

### Must NOT Have (Guardrails)

- No broad platform rewrite of all prompt usage in this scope.
- No redesign of admin IA/pages beyond minimal required integration touchpoints.
- No reliance on manual human verification as acceptance criteria.
- No coupling PPT runtime changes into unrelated sales runtime code paths.
- No silent fallback to wrong scenario mode (`presentation` must stay locked in PPT flow).

---

## Verification Strategy (MANDATORY)

> **UNIVERSAL RULE: ZERO HUMAN INTERVENTION**
>
> ALL tasks in this plan MUST be verifiable WITHOUT any human action.
>
> **FORBIDDEN**:
> - "User manually tests..."
> - "User visually confirms..."
> - "Ask user to verify..."

### Test Decision

- **Infrastructure exists**: YES
- **Automated tests**: TDD
- **Framework**:
  - Backend: `pytest` + `pytest-asyncio` + `pytest-cov`
  - Frontend: `vitest` + `jsdom`

### If TDD Enabled

Each TODO follows RED-GREEN-REFACTOR:
1. **RED**: Add failing test for target behavior.
2. **GREEN**: Implement minimum fix for test pass.
3. **REFACTOR**: Clean structure while all tests remain green.

### Agent-Executed QA Scenarios (MANDATORY — ALL tasks)

Use:
- **Playwright** for frontend/UI verification.
- **Bash/curl** for API and file-serving checks.
- **Python/pytest** for websocket and interruption state assertions.

Evidence output location:
- `.sisyphus/evidence/ppt-flow/` (screenshots, response dumps, command outputs)

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Foundation):
├── Task 1: Repro matrix + RED tests for frontend bootstrap and thumbnail contract
└── Task 4: RED tests for interruption cancellation parity (PPT)

Wave 2 (Core pipelines):
├── Task 2: Implement thumbnail generation + persistence
├── Task 3: Implement thumbnail serving contract + storage unification
└── Task 5: Implement frontend thumbnail consumption and bootstrap rendering fixes

Wave 3 (Behavioral runtime):
├── Task 6: Upgrade PPT interruption runtime cancellation and telemetry wiring
└── Task 7: Implement prompt-role resolver for PPT (hybrid policy)

Wave 4 (Integration and hardening):
└── Task 8: End-to-end verification, regression suite, contract/docs updates
```

### Dependency Matrix

| Task | Depends On | Blocks | Can Parallelize With |
|------|------------|--------|----------------------|
| 1 | None | 2, 3, 5 | 4 |
| 2 | 1 | 3, 5, 8 | 5 |
| 3 | 1, 2 | 5, 8 | 6 |
| 4 | None | 6 | 1 |
| 5 | 1, 2, 3 | 8 | 6 |
| 6 | 4, 3 | 8 | 7 |
| 7 | 1 | 8 | 6 |
| 8 | 2, 3, 5, 6, 7 | None | None |

### Agent Dispatch Summary

| Wave | Tasks | Recommended Agents |
|------|-------|--------------------|
| 1 | 1, 4 | `task(category="unspecified-high", load_skills=["test-driven-development","systematic-debugging"], run_in_background=false)` |
| 2 | 2, 3, 5 | parallel dispatch after Wave 1 |
| 3 | 6, 7 | parallel dispatch after Wave 2 |
| 4 | 8 | final integration and verification |

---

## TODOs

- [ ] 1. Build failing test matrix for PPT bootstrap and thumbnail contract (TDD RED)

  **What to do**:
  - Add backend RED tests that assert thumbnail path is generated and persisted per page.
  - Add frontend RED tests for presentation practice bootstrap state requiring initial `slide_update` (or equivalent initial context hydration).
  - Add API contract RED tests for `image_url`/thumbnail availability in presentation detail pages.

  **Must NOT do**:
  - Must not implement fixes in this task (RED only).
  - Must not alter sales behavior tests except regression assertions.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: cross-layer failing test design and contract alignment.
  - **Skills**: `test-driven-development`, `systematic-debugging`
    - `test-driven-development`: required for RED-GREEN-REFACTOR structure.
    - `systematic-debugging`: required to encode current failure signatures into tests.
  - **Skills Evaluated but Omitted**:
    - `frontend-ui-ux`: visual polish not needed for RED test stage.

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Task 4)
  - **Blocks**: 2, 3, 5
  - **Blocked By**: None

  **References**:
  - `web/src/app/(dashboard)/training/presentation/page.tsx` - PPT entry load/error states to codify.
  - `web/src/app/(dashboard)/agents/[agentId]/page.tsx` - presentation session creation and ready-presentation guard.
  - `web/src/app/(user)/practice/[sessionId]/page.tsx` - runtime lock and initial render behavior.
  - `web/src/hooks/websocket/message-handlers.ts` - slide/point/forbidden WS event reducers.
  - `backend/src/presentation_coach/api/presentations.py` - upload and page persistence behavior.
  - `backend/src/presentation_coach/services/ppt_parser.py` - thumbnail generation stub and expected insertion point.
  - `backend/src/common/db/models.py` - `Page.image_url` persistence field.
  - `backend/tests/contract/test_presentations.py` - baseline contract test style.
  - `web/src/hooks/websocket/message-handlers.test.ts` - frontend websocket reducer test style.

  **Acceptance Criteria**:
  - [ ] New backend RED tests fail with current implementation for thumbnail generation/persistence expectations.
  - [ ] New frontend RED tests fail with current implementation for initial PPT slide bootstrap expectations.
  - [ ] Existing unrelated tests remain unchanged in outcome.

  **Agent-Executed QA Scenarios**:

  ```bash
  Scenario: Backend RED tests fail for thumbnail contract
    Tool: Bash (pytest)
    Preconditions: backend venv and test DB fixtures available
    Steps:
      1. Run: pytest backend/tests/unit/presentation/test_thumbnail_pipeline.py -q
      2. Assert: non-zero exit code
      3. Assert: failure message references missing thumbnail generation/persistence expectations
      4. Save output: .sisyphus/evidence/ppt-flow/task-1-backend-red.txt
    Expected Result: RED failure is reproducible and specific
    Evidence: .sisyphus/evidence/ppt-flow/task-1-backend-red.txt

  Scenario: Frontend RED tests fail for initial slide bootstrap
    Tool: Bash (vitest)
    Preconditions: web deps installed
    Steps:
      1. Run: npm --prefix web run test -- web/src/hooks/websocket/message-handlers.test.ts
      2. Run: npm --prefix web run test -- web/src/app/(user)/practice/[sessionId]/__tests__/bootstrap.test.tsx
      3. Assert: bootstrap test fails and points to missing initial context behavior
      4. Save output: .sisyphus/evidence/ppt-flow/task-1-frontend-red.txt
    Expected Result: RED failure captures frontend non-display condition
    Evidence: .sisyphus/evidence/ppt-flow/task-1-frontend-red.txt
  ```

  **Commit**: NO

---

- [ ] 2. Implement thumbnail generation and persistence in upload pipeline (TDD GREEN)

  **What to do**:
  - Implement real thumbnail generation for each page during presentation processing.
  - Persist `Page.image_url` (or equivalent thumbnail reference) for every generated page.
  - Make generation idempotent and resilient to partial failures.
  - Ensure presentation status progression correctly reflects thumbnail readiness policy.

  **Must NOT do**:
  - Must not block the entire presentation if one page thumbnail fails; mark per-page fallback and continue.
  - Must not introduce path traversal or insecure file write behavior.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: backend ingestion pipeline and storage correctness are high risk.
  - **Skills**: `test-driven-development`, `systematic-debugging`
    - `test-driven-development`: convert RED to GREEN with deterministic behavior.
    - `systematic-debugging`: handle conversion edge cases and failures.
  - **Skills Evaluated but Omitted**:
    - `playwright`: not needed for backend generation logic.

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Task 5)
  - **Blocks**: 3, 5, 8
  - **Blocked By**: Task 1

  **References**:
  - `backend/src/presentation_coach/services/ppt_parser.py` - current parser + thumbnail TODO.
  - `backend/src/presentation_coach/api/presentations.py` - active upload and page insert path.
  - `backend/src/common/storage/presentation.py` - storage helper and path safety checks.
  - `backend/src/common/db/models.py` - `Presentation` status and `Page.image_url` field semantics.
  - `backend/src/common/db/schemas.py` - API exposure of page image URL.
  - `backend/tests/contract/test_ppt_upload.py` - contract expectations around upload processing.

  **Acceptance Criteria**:
  - [ ] Uploading a valid PPT creates page rows with non-empty `image_url` values.
  - [ ] Thumbnail files exist at expected storage location for all successfully generated pages.
  - [ ] Idempotent reprocessing does not duplicate page thumbnail references.
  - [ ] Tests from Task 1 backend RED now pass.

  **Agent-Executed QA Scenarios**:

  ```bash
  Scenario: Upload PPT produces page thumbnail references
    Tool: Bash (pytest)
    Preconditions: backend test fixtures include sample PPT
    Steps:
      1. Run: pytest backend/tests/integration/presentation/test_upload_sets_page_image_url.py -q
      2. Assert: status PASS
      3. Assert: test verifies each page has non-empty image_url
      4. Save output: .sisyphus/evidence/ppt-flow/task-2-upload-pass.txt
    Expected Result: Upload pipeline persists thumbnail references
    Evidence: .sisyphus/evidence/ppt-flow/task-2-upload-pass.txt

  Scenario: Corrupt PPT does not crash whole processing pipeline
    Tool: Bash (pytest)
    Preconditions: fixture includes corrupt PPT file
    Steps:
      1. Run: pytest backend/tests/integration/presentation/test_upload_corrupt_ppt_resilience.py -q
      2. Assert: request handled gracefully; no uncaught exception
      3. Assert: failure status and error metadata are persisted predictably
      4. Save output: .sisyphus/evidence/ppt-flow/task-2-corrupt-pass.txt
    Expected Result: Graceful degradation without service crash
    Evidence: .sisyphus/evidence/ppt-flow/task-2-corrupt-pass.txt
  ```

  **Commit**: YES
  - Message: `fix(presentation): generate and persist page thumbnails during upload`
  - Files: `backend/src/presentation_coach/services/ppt_parser.py`, `backend/src/presentation_coach/api/presentations.py`, related tests
  - Pre-commit: `pytest backend/tests/unit/presentation/test_thumbnail_pipeline.py -q`

---

- [ ] 3. Implement thumbnail serving contract and storage path normalization

  **What to do**:
  - Define one canonical serving contract for thumbnails and apply consistently.
  - Add backend authenticated thumbnail endpoint so stored thumbnail references are retrievable (`200`, correct MIME).
  - Ensure legacy records with missing thumbnail references are handled by controlled fallback/backfill path.
  - Normalize storage path conventions to avoid split roots and mismatched URL mapping.
  - Add regression checks for auth/access policy behavior chosen in implementation.

  **Must NOT do**:
  - Must not leave mixed old/new path logic without compatibility mapping.
  - Must not break existing presentation file upload locations without migration/read compatibility.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: API serving contract and storage semantics affect all consumers.
  - **Skills**: `systematic-debugging`, `test-driven-development`
    - `systematic-debugging`: path and URL mapping errors are subtle and environment-dependent.
    - `test-driven-development`: enforce serving behavior via tests first.
  - **Skills Evaluated but Omitted**:
    - `frontend-ui-ux`: no UI design change required in this backend contract task.

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential in Wave 2
  - **Blocks**: 5, 6, 8
  - **Blocked By**: Task 1, Task 2

  **References**:
  - `backend/src/main.py` - route/static mount surface and global router wiring.
  - `backend/src/presentation_coach/api/presentations.py` - page/detail API responses.
  - `backend/src/common/storage/presentation.py` - canonical storage abstraction.
  - `backend/src/common/db/models.py` - persisted URL/reference fields.
  - `web/src/lib/api/client.ts` - `normalizePresentationPage` and image URL consumption.

  **Acceptance Criteria**:
  - [ ] `image_url` returned by presentations API is retrievable and returns valid image content type.
  - [ ] Storage path is deterministic and consistent across upload/retrieval/reprocess operations.
  - [ ] Old-path compatibility is preserved for existing presentations.
  - [ ] Legacy presentations with missing thumbnail refs no longer break page rendering (fallback/backfill path works).

  **Agent-Executed QA Scenarios**:

  ```bash
  Scenario: Thumbnail URL retrieval returns image payload
    Tool: Bash (curl)
    Preconditions: at least one presentation with generated thumbnails exists
    Steps:
      1. curl -s -H "Authorization: Bearer $TOKEN" http://localhost:3444/api/v1/presentations/$PRESENTATION_ID/pages > /tmp/pages.json
      2. Parse first non-empty image_url from /tmp/pages.json
      3. curl -s -H "Authorization: Bearer $TOKEN" -D /tmp/thumb.headers -o /tmp/thumb.bin "$IMAGE_URL"
      4. Assert: /tmp/thumb.headers contains "200" and "Content-Type: image/"
      5. Save evidence: .sisyphus/evidence/ppt-flow/task-3-thumbnail-headers.txt
    Expected Result: Thumbnail URL is directly retrievable with valid MIME
    Evidence: .sisyphus/evidence/ppt-flow/task-3-thumbnail-headers.txt

  Scenario: Missing thumbnail returns graceful fallback response
    Tool: Bash (curl)
    Preconditions: query a page known to have no thumbnail
    Steps:
      1. curl -s -o /tmp/missing-thumb -w "%{http_code}" "$MISSING_THUMB_URL"
      2. Assert: returns controlled fallback status (e.g., 404/204) without server error stack
      3. Save evidence: .sisyphus/evidence/ppt-flow/task-3-missing-thumb.txt
    Expected Result: No 500 crash path for missing assets
    Evidence: .sisyphus/evidence/ppt-flow/task-3-missing-thumb.txt
  ```

  **Commit**: YES
  - Message: `fix(presentation): stabilize thumbnail serving contract and storage mapping`
  - Files: `backend/src/main.py`, `backend/src/presentation_coach/api/presentations.py`, storage helpers, tests
  - Pre-commit: `pytest backend/tests/integration/presentation/test_thumbnail_serving.py -q`

---

- [ ] 4. Add RED tests for PPT interruption cancellation parity and telemetry

  **What to do**:
  - Add failing tests for presentation interruption parity targets:
    - cancellation of active output tasks,
    - stream-aware interruption event consistency,
    - interruption persistence event write.
  - Add contract tests for `interrupted` event shape and stale-stream safety assumptions.

  **Must NOT do**:
  - Must not modify runtime logic in this task (RED only).

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: websocket cancellation race conditions require careful test design.
  - **Skills**: `test-driven-development`, `systematic-debugging`
    - `test-driven-development`: define parity expectations before changing handler.
    - `systematic-debugging`: detect race/rerequest edge cases.
  - **Skills Evaluated but Omitted**:
    - `playwright`: backend websocket logic better tested by unit/integration first.

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Task 1)
  - **Blocks**: 6
  - **Blocked By**: None

  **References**:
  - `backend/src/presentation_coach/websocket/presentation_handler.py` - current interruption handling.
  - `backend/src/presentation_coach/services/feedback_service.py` - interruption decision source.
  - `backend/src/presentation_coach/services/interruption_detector.py` - semantic/rule decision fallback.
  - `backend/src/presentation_coach/services/coach_service.py` - interruption persistence API.
  - `backend/tests/unit/test_presentation_handler_persistence.py` - existing presentation handler tests.
  - `backend/src/sales_bot/websocket/enhanced_handler.py` - parity target for cancellation semantics.

  **Acceptance Criteria**:
  - [ ] New RED tests fail on current PPT handler where parity requirements are unmet.
  - [ ] Test failures clearly indicate missing cancellation/persistence semantics.

  **Agent-Executed QA Scenarios**:

  ```bash
  Scenario: RED failure for interruption persistence wiring
    Tool: Bash (pytest)
    Preconditions: backend test environment available
    Steps:
      1. Run: pytest backend/tests/unit/presentation/test_interruption_parity.py -q
      2. Assert: fails on missing persistence invocation and/or stream metadata assertions
      3. Save output: .sisyphus/evidence/ppt-flow/task-4-red-interrupt.txt
    Expected Result: RED state captures parity gaps
    Evidence: .sisyphus/evidence/ppt-flow/task-4-red-interrupt.txt
  ```

  **Commit**: NO

---

- [ ] 5. Fix frontend PPT rendering bootstrap and thumbnail display chain

  **What to do**:
  - Ensure presentation practice view gets initial slide context deterministically on connect (not only after manual page change).
  - Ensure `scenario_type` lock remains `presentation` throughout runtime sync and reconnect paths.
  - Consume thumbnail URLs/references robustly in admin presentation detail and practice panel, including authenticated fetch-to-blob rendering path.
  - Keep placeholder behavior non-blocking while data loads.

  **Must NOT do**:
  - Must not regress sales practice UI states.
  - Must not introduce popup-style blocking errors.

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: frontend rendering state, route/runtime lock, and component data hydration.
  - **Skills**: `frontend-ui-ux`, `test-driven-development`
    - `frontend-ui-ux`: maintain UX quality while fixing render chain.
    - `test-driven-development`: close RED tests and guard regressions.
  - **Skills Evaluated but Omitted**:
    - `playwright`: kept for QA stage instead of implementation stage.

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Task 2)
  - **Blocks**: 8
  - **Blocked By**: Task 1, Task 2, Task 3

  **References**:
  - `web/src/app/(user)/practice/[sessionId]/page.tsx` - runtime lock and initial lifecycle behavior.
  - `web/src/hooks/use-practice-websocket.ts` - websocket URL/session state transitions.
  - `web/src/hooks/websocket/message-handlers.ts` - slide/point event reducers.
  - `web/src/components/practice/RightPanelContent.tsx` - presentation panel branching.
  - `web/src/components/practice/presentation/SlideViewer.tsx` - visual loading/content state.
  - `web/src/app/admin/presentations/[id]/page.tsx` - thumbnail rendering for page cards.
  - `web/src/lib/api/client.ts` - presentation page normalization contract.
  - `backend/src/presentation_coach/websocket/presentation_handler.py` - slide update event producer.

  **Acceptance Criteria**:
  - [ ] Presentation practice page shows initial slide context without requiring manual page switch.
  - [ ] `scenario_type` mismatch path is prevented/recovered; presentation sessions do not connect to sales websocket path.
  - [ ] Admin presentation page renders generated thumbnails for ready pages.
  - [ ] Thumbnail rendering works under authenticated API mode (no token-in-query dependency).
  - [ ] Frontend RED tests from Task 1 pass.

  **Agent-Executed QA Scenarios**:

  ```
  Scenario: PPT practice page renders initial slide context
    Tool: Playwright (playwright skill)
    Preconditions: frontend on localhost:3445, backend on localhost:3444, valid auth state, ready presentation exists
    Steps:
      1. Navigate to: http://localhost:3445/training/presentation
      2. Click first available presentation agent card
      3. On agent page, ensure a PPT is selected in selector
      4. Click "开始练习"
      5. Wait for URL pattern: /practice/{sessionId}
      6. Assert right panel title contains "幻灯片"
      7. Assert slide panel is not permanently stuck at placeholder text after 10s
      8. Screenshot: .sisyphus/evidence/ppt-flow/task-5-practice-initial-slide.png
    Expected Result: Initial slide context is visible in presentation mode
    Evidence: .sisyphus/evidence/ppt-flow/task-5-practice-initial-slide.png

  Scenario: Admin PPT detail shows thumbnails for ready pages
    Tool: Playwright (playwright skill)
    Preconditions: at least one ready presentation with generated thumbnails
    Steps:
      1. Navigate to: http://localhost:3445/admin/presentations
      2. Click first presentation row "编辑"
      3. Wait for page grid in "页面管理"
      4. Assert at least one page card contains `<img>` element (not only icon placeholder)
      5. Screenshot: .sisyphus/evidence/ppt-flow/task-5-admin-thumbnails.png
    Expected Result: Real page thumbnails are displayed
    Evidence: .sisyphus/evidence/ppt-flow/task-5-admin-thumbnails.png
  ```

  **Commit**: YES
  - Message: `fix(web): stabilize ppt practice bootstrap and thumbnail rendering`
  - Files: `web/src/app/(user)/practice/[sessionId]/page.tsx`, websocket handlers/components, admin presentation detail
  - Pre-commit: `npm --prefix web run test -- web/src/hooks/websocket/message-handlers.test.ts`

---

- [ ] 6. Implement PPT interruption cancellation parity and persistence wiring (GREEN)

  **What to do**:
  - Upgrade presentation websocket interrupt flow to cancellable task model consistent with sales behavior quality.
  - Add stream-aware interruption metadata where applicable for stale-event safety.
  - Wire interruption event persistence through `PresentationCoachService.record_interruption`.
  - Replace hardcoded latency value with measured timing capture.

  **Must NOT do**:
  - Must not alter sales websocket payload contracts.
  - Must not block message loop with long-running cancellation work.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: concurrent websocket/task cancellation logic is high complexity.
  - **Skills**: `systematic-debugging`, `test-driven-development`
    - `systematic-debugging`: race/cancellation correctness.
    - `test-driven-development`: close RED parity tests from Task 4.
  - **Skills Evaluated but Omitted**:
    - `frontend-ui-ux`: backend runtime correctness task.

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Task 7)
  - **Blocks**: 8
  - **Blocked By**: Task 3, Task 4

  **References**:
  - `backend/src/presentation_coach/websocket/presentation_handler.py` - target runtime logic.
  - `backend/src/presentation_coach/services/feedback_service.py` - interruption decision + dedup.
  - `backend/src/presentation_coach/services/interruption_detector.py` - semantic decision path.
  - `backend/src/presentation_coach/services/coach_service.py` - persistence API for interruption events.
  - `backend/src/sales_bot/websocket/enhanced_handler.py` - parity pattern for cancellable task pipeline.
  - `backend/src/sales_bot/websocket/components/tts_component.py` - cooperative interruption checks.
  - `backend/tests/unit/test_presentation_handler_persistence.py` - base test suite extension target.

  **Acceptance Criteria**:
  - [ ] Interrupt during AI speaking cancels active generation/playback path deterministically.
  - [ ] `interrupted` confirmation payload remains contract-compatible and stream-safe.
  - [ ] Partial interrupted assistant output is handled consistently (no duplicate persistence / explicit interrupted state path).
  - [ ] Interruption persistence entries are written for reportability.
  - [ ] RED tests from Task 4 pass.

  **Agent-Executed QA Scenarios**:

  ```bash
  Scenario: Interrupt during active AI output cancels pipeline
    Tool: Bash (pytest)
    Preconditions: websocket test fixtures available
    Steps:
      1. Run: pytest backend/tests/unit/presentation/test_interruption_parity.py::test_interrupt_cancels_active_output -q
      2. Assert: PASS
      3. Save output: .sisyphus/evidence/ppt-flow/task-6-cancel-pass.txt
    Expected Result: active output is cancelled and handler state returns to listening
    Evidence: .sisyphus/evidence/ppt-flow/task-6-cancel-pass.txt

  Scenario: Interruption persistence is recorded
    Tool: Bash (pytest)
    Preconditions: DB fixture with session and interruption trigger input
    Steps:
      1. Run: pytest backend/tests/integration/presentation/test_interruption_event_persistence.py -q
      2. Assert: PASS
      3. Assert: interruption_event row includes reason, trigger, latency fields
      4. Save output: .sisyphus/evidence/ppt-flow/task-6-persistence-pass.txt
    Expected Result: interruption telemetry is persisted and queryable
    Evidence: .sisyphus/evidence/ppt-flow/task-6-persistence-pass.txt
  ```

  **Commit**: YES
  - Message: `fix(presentation): harden interruption cancellation and telemetry`
  - Files: `backend/src/presentation_coach/websocket/presentation_handler.py`, coach service wiring, tests
  - Pre-commit: `pytest backend/tests/unit/test_presentation_handler_persistence.py -q`

---

- [ ] 7. Implement prompt-role resolver for presentation runtime (hybrid design)

  **What to do**:
  - Implement hybrid role resolution chain for presentation runtime:
    1) scenario-specific template binding,
    2) scenario-type template default,
    3) curated baseline presentation coach role.
  - Inject session `agent_id/persona_id` context into presentation prompt-role composition where available.
  - Replace hardcoded interruption/feedback role text paths with resolver-backed rendering.
  - Keep safe fallback when template variables are missing.

  **Must NOT do**:
  - Must not require admin UI completion before runtime works (runtime fallback must be self-sufficient).
  - Must not remove existing behavior without equivalent fallback.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: runtime prompt composition touches AI behavior and scenario correctness.
  - **Skills**: `test-driven-development`, `Requirement Analyzer`
    - `test-driven-development`: enforce precedence/fallback matrix correctness.
    - `Requirement Analyzer`: keep role policy constraints explicit and deterministic.
  - **Skills Evaluated but Omitted**:
    - `frontend-ui-ux`: role resolver is backend runtime concern.

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Task 6)
  - **Blocks**: 8
  - **Blocked By**: Task 1

  **References**:
  - `backend/src/prompt_templates/service.py` - `get_template_for_scenario` resolution order.
  - `backend/src/prompt_templates/models.py` - prompt types and variable schema.
  - `backend/src/prompt_templates/renderer.py` - rendering behavior for missing/extra variables.
  - `backend/src/presentation_coach/services/interruption_detector.py` - hardcoded prompt path to replace.
  - `backend/src/presentation_coach/websocket/presentation_handler.py` - interruption/feedback response generation integration point.
  - `backend/src/common/api/practice.py` - session includes `agent_id/persona_id` for presentation.
  - `backend/src/sales_bot/services/voice_runtime_policy.py` - proven composition approach reference.
  - `backend/src/prompt_templates/api/routes.py` - scenario assignment admin/API plumbing.

  **Acceptance Criteria**:
  - [ ] Presentation runtime resolves prompt-role chain deterministically with documented precedence.
  - [ ] Missing template binding falls back to baseline role behavior without runtime error.
  - [ ] Agent/persona context is used when available for presentation role rendering.
  - [ ] New role-resolution matrix tests pass.

  **Agent-Executed QA Scenarios**:

  ```bash
  Scenario: Role resolver precedence matrix
    Tool: Bash (pytest)
    Preconditions: test fixtures for scenario-specific and scenario-default bindings
    Steps:
      1. Run: pytest backend/tests/unit/presentation/test_prompt_role_resolution.py -q
      2. Assert: PASS for cases (specific binding, type default, baseline fallback)
      3. Save output: .sisyphus/evidence/ppt-flow/task-7-role-matrix-pass.txt
    Expected Result: deterministic precedence chain
    Evidence: .sisyphus/evidence/ppt-flow/task-7-role-matrix-pass.txt

  Scenario: Missing template variable does not break runtime
    Tool: Bash (pytest)
    Preconditions: template fixture missing optional variable
    Steps:
      1. Run: pytest backend/tests/unit/presentation/test_prompt_role_resolution.py::test_missing_variable_fallback -q
      2. Assert: PASS
      3. Save output: .sisyphus/evidence/ppt-flow/task-7-missing-var-pass.txt
    Expected Result: runtime degrades gracefully to fallback prompt text
    Evidence: .sisyphus/evidence/ppt-flow/task-7-missing-var-pass.txt
  ```

  **Commit**: YES
  - Message: `feat(presentation): add hybrid prompt-role resolver for runtime coaching`
  - Files: presentation services/handler + prompt integration + tests
  - Pre-commit: `pytest backend/tests/unit/presentation/test_prompt_role_resolution.py -q`

---

- [ ] 8. Final integration, regression verification, and contract updates

  **What to do**:
  - Run full verification matrix for backend/frontend and targeted scenario regression.
  - Validate no regression in sales interruption flow.
  - Update API contract docs for presentation thumbnail and interruption payload semantics if changed.
  - Capture evidence artifacts for sign-off.

  **Must NOT do**:
  - Must not declare complete without command evidence.
  - Must not skip failing checks.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: cross-layer verification and contract consistency.
  - **Skills**: `verification-before-completion`, `requesting-code-review`
    - `verification-before-completion`: evidence-first completion gate.
    - `requesting-code-review`: final quality review before merge/start-work.
  - **Skills Evaluated but Omitted**:
    - `frontend-ui-ux`: verification task, not UI implementation.

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 4 (final)
  - **Blocks**: None
  - **Blocked By**: Tasks 2, 3, 5, 6, 7

  **References**:
  - `docs/api-contract/websocket.md` - interruption event contract documentation.
  - `docs/api-contract/sessions.md` - session flow and scenario semantics.
  - `docs/api-contract/README.md` - response/contract consistency guidance.
  - `backend/tests/unit/test_presentation_handler_persistence.py` - presentation websocket behavior coverage.
  - `backend/tests/integration/test_presentation_flow.py` - scenario flow integration baseline.
  - `web/src/hooks/websocket/message-handlers.test.ts` - frontend event reducer regression checks.

  **Acceptance Criteria**:
  - [ ] Backend targeted tests pass for thumbnail, interruption, prompt-role modules.
  - [ ] Frontend targeted tests pass for presentation rendering and websocket state.
  - [ ] Playwright E2E scenarios pass for presentation start, render, and interruption.
  - [ ] Sales interruption regression checks pass unchanged.
  - [ ] Contract docs updated where runtime payload/fields changed.

  **Agent-Executed QA Scenarios**:

  ```bash
  Scenario: Backend verification matrix
    Tool: Bash
    Preconditions: backend dependencies and test DB ready
    Steps:
      1. pytest backend/tests/unit/presentation -q
      2. pytest backend/tests/integration/presentation -q
      3. pytest backend/tests/unit/test_presentation_handler_persistence.py -q
      4. Save output: .sisyphus/evidence/ppt-flow/task-8-backend-matrix.txt
    Expected Result: all targeted backend checks pass
    Evidence: .sisyphus/evidence/ppt-flow/task-8-backend-matrix.txt

  Scenario: Frontend and E2E matrix
    Tool: Bash + Playwright
    Preconditions: web and backend running locally
    Steps:
      1. npm --prefix web run test -- web/src/hooks/websocket/message-handlers.test.ts
      2. npx playwright test web/e2e/ppt-practice-flow.spec.ts --project=chromium
      3. Save output: .sisyphus/evidence/ppt-flow/task-8-frontend-e2e.txt
    Expected Result: presentation UI flow and event handling validated
    Evidence: .sisyphus/evidence/ppt-flow/task-8-frontend-e2e.txt

  Scenario: Sales interruption regression
    Tool: Bash
    Preconditions: backend test environment ready
    Steps:
      1. pytest backend/tests/unit/sales_bot/websocket -k interrupt -q
      2. Assert: PASS
      3. Save output: .sisyphus/evidence/ppt-flow/task-8-sales-regression.txt
    Expected Result: sales interruption behavior unaffected
    Evidence: .sisyphus/evidence/ppt-flow/task-8-sales-regression.txt
  ```

  **Commit**: YES
  - Message: `chore(presentation): finalize verification and contract alignment`
  - Files: tests + contract docs + minor glue
  - Pre-commit: full matrix commands above

---

## Commit Strategy

| After Task | Message | Files | Verification |
|------------|---------|-------|--------------|
| 2 | `fix(presentation): generate and persist page thumbnails during upload` | parser/api/tests | `pytest backend/tests/unit/presentation/test_thumbnail_pipeline.py -q` |
| 3 | `fix(presentation): stabilize thumbnail serving contract and storage mapping` | main/api/storage/tests | `pytest backend/tests/integration/presentation/test_thumbnail_serving.py -q` |
| 5 | `fix(web): stabilize ppt practice bootstrap and thumbnail rendering` | web practice/admin/api normalization/tests | `npm --prefix web run test -- web/src/hooks/websocket/message-handlers.test.ts` |
| 6 | `fix(presentation): harden interruption cancellation and telemetry` | presentation handler/services/tests | `pytest backend/tests/unit/test_presentation_handler_persistence.py -q` |
| 7 | `feat(presentation): add hybrid prompt-role resolver for runtime coaching` | prompt integration/tests | `pytest backend/tests/unit/presentation/test_prompt_role_resolution.py -q` |
| 8 | `chore(presentation): finalize verification and contract alignment` | docs/tests/glue | full matrix |

---

## Success Criteria

### Verification Commands

```bash
# Backend PPT targeted
pytest backend/tests/unit/presentation -q
pytest backend/tests/integration/presentation -q
pytest backend/tests/unit/test_presentation_handler_persistence.py -q

# Frontend targeted
npm --prefix web run test -- web/src/hooks/websocket/message-handlers.test.ts

# E2E
npx playwright test web/e2e/ppt-practice-flow.spec.ts --project=chromium

# Sales regression guard
pytest backend/tests/unit/sales_bot/websocket -k interrupt -q
```

### Final Checklist

- [ ] All Must Have items present.
- [ ] All Must NOT Have violations absent.
- [ ] All TDD RED tests converted to GREEN and refactor-safe.
- [ ] All agent-executed QA scenarios captured evidence under `.sisyphus/evidence/ppt-flow/`.
- [ ] No manual verification step required for completion.
