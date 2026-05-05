# Delivery TODO

This file mirrors `DELIVERY_STATE.md` at task-list granularity. `DELIVERY_STATE.md` is the source of truth for phase status, verification evidence, commits, and blockers.

## Current Atomic Task

- [x] Phase 1.0: Create delivery state baseline.
- [x] Verify delivery state baseline.
- [x] Commit delivery state baseline.

## Phase 1: Baseline Falsification and Routing Audit

- [x] Generate `api_routing_audit.md` with OpenAPI paths, router sources, permission dependencies, and frontend call mapping.
- [x] Fix unmounted or wrongly mounted backend routes.
- [x] Fix frontend/backend API contract mismatches.
- [x] Fix frontend/backend lint errors.
- [x] Fix TypeScript type errors.
- [x] Normalize backend mypy invocation configuration.
- [x] Limit installed untyped third-party mypy noise.
- [x] Type backend entrypoint helpers.
- [x] Clean shared backoff helper mypy error.
- [x] Type retry focus page-number sanitation.
- [x] Type scoring ruleset schema literal constant.
- [x] Type document parse artifact loading contract.
- [x] Type OSS signing GET URL return contract.
- [x] Type admin permission dependency factory contract.
- [x] Type latency tracker constructor contract.
- [x] Type KB lock metric callback contract.
- [x] Type semantic cache hit payload contract.
- [x] Type Result generic helper contracts.
- [x] Type embedding service property contracts.
- [x] Type runtime event literal contracts.
- [x] Type assembler metadata contracts.
- [x] Type answerability metadata contracts.
- [x] Type evaluation harness payload contracts.
- [x] Type haystack adapter callback contracts.
- [x] Type HTML sanitizer URL callback contract.
- [x] Type auth middleware dispatch contract.
- [x] Type ingestion service lazy vector-store contract.
- [x] Type knowledge schema validator contracts.
- [x] Type RAG profile service sequence contract.
- [x] Type leaderboard success value contract.
- [x] Type admin training duration contract.
- [x] Type sales stage config read contract.
- [x] Type trigger context metadata contract.
- [x] Type point tracker state contract.
- [x] Type interruption detector constructor contract.
- [x] Type sales bot lazy chain contract.
- [x] Type TTS streaming callback contract.
- [x] Type persona prompt constructor contract.
- [x] Type growth safety policy resolver contract.
- [x] Type vagueness detector constructor and pattern compiler contracts.
- [x] Type context manager lifecycle helper contracts.
- [x] Type forbidden matcher pattern storage contract.
- [x] Type score processor websocket send callback contract.
- [x] Type message persistence saved message ID contract.
- [x] Type knowledge retrieval gather result contract.
- [x] Type support runtime JSONResponse return contract.
- [x] Type common TTS provider and stream contracts.
- [x] Type prompt renderer Jinja signature contracts.
- [x] Type point extraction result contracts.
- [x] Type realtime scoring feedback selector contract.
- [x] Type persona policy migration assignment contract.
- [x] Type agent persona default-clear contract.
- [x] Type evaluation realtime scoring result contract.
- [x] Type manager intervention timestamp contract.
- [x] Type history statistics payload contract.
- [x] Type AgentContext config-read contract.
- [x] Type BaseCapability result and enabled flag contract.
- [x] Type AI ConfigManager ORM field contract.
- [x] Type CapabilityProcessor pass-flag and action-card contracts.
- [x] Type RealtimeFeedbackArbiter stage and score context contracts.
- [x] Type AIScoringService dict and Result value contracts.
- [x] Type Aho matcher constructor, node, and queue contracts.
- [x] Type report trends datetime ORM field contracts.
- [x] Type error middleware return contracts.
- [x] Type sales scenario API return contracts.
- [x] Type presentation AI policy API return contracts.
- [x] Type user presentation progress update contract.
- [x] Type DB session startup guard signatures.
- [x] Type analytics service SQLAlchemy row boundary.
- [x] Type cross-encoder optional import boundary.
- [x] Type knowledge answer compatibility layer contracts.
- [x] Type ASR provider stream contracts.
- [x] Type semantic point tracker embedding contracts.
- [x] Type RAG profile API ORM contracts.
- [x] Type admin settings API return contracts.
- [x] Type admin analytics score rounding contract.
- [x] Type growth API return contracts.
- [x] Type log sanitizer container and processor contracts.
- [x] Type circuit breaker signature contracts.
- [x] Type support runtime status payload contracts.
- [x] Type PPT version manager filesystem contracts.
- [x] Type runtime diagnostics payload normalization contracts.
- [x] Type session state service lifecycle contracts.
- [x] Type API rate limiter decorator contracts.
- [x] Type session lifecycle ORM value contracts.
- [x] Type legacy schema repair SQLAlchemy boundary contracts.
- [x] Type PPT OCR processor optional dependency contracts.
- [x] Type response cache entry and decorator contracts.
- [x] Type presentation PPT parser optional dependency and page-context contracts.
- [x] Type password reset URL and delivery lifecycle ORM contracts.
- [ ] Resolve backend mypy baseline blocker.
- [ ] Configure Vitest to isolate `node_modules`.
- [ ] Raise overall coverage to at least 60%.
- [ ] Raise `scoring`, `auth`, and `practice` coverage to at least 70%.

## Phase 2: Admin Governance Foundation and RBAC Loop

- [ ] Move scoring rulesets to `/api/v1/admin/scoring-rulesets`.
- [ ] Add scoring rulesets CRUD, publish, rollback, and dry-run.
- [ ] Sync frontend client and legacy path compatibility.
- [ ] Add RBAC schema, migrations, audit logs, and five seeded roles.
- [ ] Add action-level permission checks and audit persistence to high-risk admin APIs.
- [ ] Build RBAC admin UI.
- [ ] Enforce permission-based menus/buttons and direct-access 403 handling.

## Phase 3: User Dictionary Full Business Chain

- [ ] Add versioned and audited user dictionary model.
- [ ] Build user dictionary admin CRUD UI.
- [ ] Normalize ASR final transcripts through dictionary correction.
- [ ] Persist correction evidence to session messages.
- [ ] Use normalized text for knowledge retrieval grounding.
- [ ] Display correction traces in scoring evidence, six-dimensional reports, and Replay pages.

## Phase 4: Stable E2E for Both Training Flows

- [ ] Build auditable local mock provider for AI, ASR, and TTS.
- [ ] Add standard fixtures including corrupted PPT fixtures.
- [ ] Add sales training E2E success/degraded paths.
- [ ] Add presentation training E2E success path.
- [ ] Run both main E2E flows 3 consecutive times locally.
- [ ] Verify core API p95 latency below 500ms.

## Phase 5: Security Gate and Release Closure

- [ ] Extract frontend thresholds and operational copy into business configuration dictionaries.
- [ ] Validate defaults and fallback behavior for business configuration dictionaries.
- [ ] Run secret scan and reach 0 high-risk findings.
- [ ] Redact tokens and cookies from logs.
- [ ] Disable dev-login and default secrets in production.
- [ ] Create final `Release_Checklist.md`.

## Review

- 2026-05-06 Phase 1.3 password reset atom: `./.venv-test/bin/mypy src/common/services/password_reset.py` has no direct `src/common/services/password_reset.py` errors while import-chain errors remain, `ruff check src/common/services/password_reset.py` passed, and password reset/auth recovery regression tests passed with 15 assertions. Full backend `./.venv-test/bin/mypy src` now reports 2181 errors in 77 files. Token expiry, minimum password length, rate-limit constants, status/reason values, delivery error truncation, token hashing, supersede/consume/expire behavior, active-user guard, reset URL separator behavior, email transport fallback, generic user-facing response, runtime DDL prohibition, and log masking were not changed. No business rules, prompts, thresholds, permissions, admin management entries, audit semantics, or configurable items were added.

- 2026-05-06 Phase 1.3 PPT parser atom: `./.venv-test/bin/mypy src/presentation_coach/services/ppt_parser.py`, `ruff check src/presentation_coach/services/ppt_parser.py`, an ad hoc missing-dependency fallback and page-context runtime check, and `PYTHONPATH=src ./.venv-test/bin/pytest tests/integration/test_presentation_thumbnail_api.py -q --no-cov` passed. Full backend `./.venv-test/bin/mypy src` now reports 2188 errors in 78 files. The broader thumbnail command including `tests/unit/test_presentation_thumbnail_pipeline.py` failed because `.venv-test` lacks Pillow despite `requirements.txt` declaring it; this was not counted as passing verification. PPT parser supported formats, missing-dependency fallbacks, parse/thumbnail fallback codes, thumbnail dimensions/copy/colors/path naming, page-context fields/defaults, validity checks, and singleton behavior were not changed. No business rules, prompts, thresholds, permissions, admin management entries, audit semantics, or configurable items were added.

- 2026-05-06 Phase 1.3 response cache atom: `./.venv-test/bin/mypy src/common/cache/response_cache.py`, `ruff check src/common/cache/response_cache.py`, an ad hoc `ResponseCache` hit/expire/invalidate/decorator runtime check, and `PYTHONPATH=src ./.venv-test/bin/pytest tests/unit/common/cache/test_redis_cache.py tests/unit/test_stepfun_internal_knowledge_searcher.py -q --no-cov` passed. Full backend `./.venv-test/bin/mypy src` now reports 2196 errors in 79 files. Response cache default TTL, key generation material/hash shape, expiration fallback, cache-miss sentinel, invalidation/cleanup semantics, global singleton, and async decorator behavior were not changed. No business rules, prompts, thresholds, permissions, admin management entries, audit semantics, or configurable items were added.

- 2026-05-06 Phase 1.3: backend `ruff check src tests`, frontend `npx eslint . --quiet`, frontend `npx tsc --noEmit`, and targeted touched-file tests passed. Backend mypy invocation is now normalized in `pyproject.toml`; direct `./.venv-test/bin/mypy src` reaches real checking and reports 2204 errors in 80 files after limiting installed untyped third-party library noise, typing backend entrypoint helpers, cleaning the shared backoff helper, typing retry focus page-number sanitation, typing the scoring ruleset schema literal constant, typing the document parse artifact loading contract, typing the OSS signing GET URL return contract, typing the admin permission dependency factory contract, typing the latency tracker constructor contract, typing the KB lock metric callback contract, typing the semantic cache hit payload contract, typing the Result generic helper contracts, typing the embedding service property contracts, typing the runtime event literal contracts, typing the assembler metadata contracts, typing the answerability metadata contracts, typing the evaluation harness payload contracts, typing the haystack adapter callback contracts, typing the HTML sanitizer URL callback contract, typing the auth middleware dispatch contract, typing the ingestion service lazy vector-store contract, typing the knowledge schema validator contracts, typing the RAG profile service sequence contract, typing the leaderboard success value contract, typing the admin training duration contract, typing the sales stage config read contract, typing the trigger context metadata contract, typing the point tracker state contract, typing the interruption detector constructor contract, typing the sales bot lazy chain contract, typing the TTS streaming callback contract, typing the persona prompt constructor contract, typing the growth safety policy resolver contract, typing the vagueness detector constructor and pattern compiler contracts, typing the context manager lifecycle helper contracts, typing the forbidden matcher pattern storage contract, typing the score processor websocket send callback contract, typing the message persistence saved message ID contract, typing the knowledge retrieval gather result contract, typing the support runtime JSONResponse return contract, typing the common TTS provider and stream contracts, typing the prompt renderer Jinja signature contracts, typing the point extraction result contracts, typing the realtime scoring feedback selector contract, typing the persona policy migration assignment contract, typing the agent persona default-clear contract, typing the evaluation realtime scoring result contract, typing the manager intervention timestamp contract, typing the history statistics payload contract, typing the AgentContext config-read contract, typing the BaseCapability result and enabled flag contract, typing the AI ConfigManager ORM field contract, typing the CapabilityProcessor pass-flag and action-card contracts, typing the RealtimeFeedbackArbiter stage and score context contracts, typing the AIScoringService dict and Result value contracts, typing the Aho matcher constructor/node/queue contracts, typing the report trends datetime ORM field contracts, typing the error middleware return contracts, typing the sales scenario API return contracts, typing the presentation AI policy API return contracts, typing the user presentation progress update contract, typing the DB session startup guard signatures, typing the analytics service SQLAlchemy row boundary, typing the cross-encoder optional import boundary, typing the knowledge answer compatibility layer contracts, typing the ASR provider stream contracts, typing the semantic point tracker embedding contracts, typing the RAG profile API ORM contracts, typing the admin settings API return contracts, typing the admin analytics score rounding contract, typing the growth API return contracts, typing the log sanitizer container/processor contracts, typing the circuit breaker signature contracts, typing the support runtime status payload contracts, typing the PPT version manager filesystem contracts, typing the runtime diagnostics payload normalization contracts, typing the session state service lifecycle contracts, typing the API rate limiter decorator contracts, typing the session lifecycle ORM value contracts, typing the legacy schema repair SQLAlchemy boundary contracts, and typing the PPT OCR processor optional dependency contracts. AI ConfigManager environment variable names/defaults, provider/model defaults, API key/base URL policies, database-first precedence, decryption flow, active/default selection, and environment fallback behavior were not changed. CapabilityProcessor realtime feedback thresholds, action-card copy, feedback priority, duplicate suppression, score update payload semantics, and websocket message types were not changed. RealtimeFeedbackArbiter primary-source selection, severity priority, score priority, action-card inputs, duplicate suppression, action signature construction, and preserved context payloads were not changed. AIScoringService scoring dimensions, weights, prompt text, system message, JSON extraction, default score values, fallback copy, strengths/improvements defaults, and error codes were not changed. Aho matcher forbidden-word sources, exact/regex matching strategy, failure-link traversal, match ordering, unique-match deduplication, default suggestion copy, severity values, and emitted match fields were not changed. Report trends same-user/same-scenario filtering, completed/evaluable inclusion rules, score basis, scan limit, request limit bounds, trend sort order, delta calculation, no-history explanation copy, and response payload fields were not changed. Error middleware trace header names, traceparent/tracestate propagation, HTTP status codes, fallback codes, exception payload fields, user-facing fallback copy, and logging fields were not changed. Sales scenario route paths, active-scenario filters, scenario-type query semantics, scenario ordering, response field names, runtime-contract payload, persona discovery filters, persona ordering/deduplication, persona characteristic formatting, runtime binding summary, HTTP 404 behavior, error codes, and error messages were not changed. Presentation AI policy route paths, admin dependency, scope validation, scope-id normalization, preview input limits, payload fields, upsert field selection, effective-policy resolution order, commit/rollback behavior, HTTP 400/404 behavior, error code, and user-facing error message were not changed. User presentation progress source marker, user/presentation isolation query, minimum page rule, presentation existence check, total-page upper bound, saved fields, commit/refresh flow, rollback behavior, error codes, and fallback messages were not changed. DB session database URL default, SQLite engine branching, pool options, startup repair environment allowlist, guarded table names, schema guard table/column/index sets, Alembic/repair entrypoint copy, schema-drift errors, and session rollback/close semantics were not changed. Session lifecycle action set, terminal status mapping, race scenarios, optimistic status guard, invalid transition errors, start/pause/resume/end status transitions, duration calculation formula, report-generation trigger condition, fire-and-forget behavior, and scoring-context save behavior were not changed. Legacy schema repair personas `persona_policy` repair detection/payload, knowledge document content-hash repair, spreadsheet file-type constraint repair, SQLite table rebuild SQL, index names, startup repair authority, production refusal semantics, and repair log fields were not changed. PPT OCR optional `python-pptx`, Tesseract, and PIL lazy import behavior, missing-dependency fallback markers, OCR failure fallback markers, slide title heuristic, image-count detection, page numbering, result payload shape, and singleton processor behavior were not changed. Analytics service time window default, completed-session filters, scenario filters, scoring weights, effectiveness pass-flag names, evaluability filter, retry window, percentage rounding, zero defaults, dashboard stat fields, and fallback codes were not changed. Cross-encoder env variable names, model defaults, max length, top-k bounds, score normalization, strategy labels, Cohere request payload, model-load failure flagging, and original-order passthrough fallback were not changed. Knowledge answer env flags, rollout mode resolution, compat/live/dual-run payload fields, answerability diagnostics, retrieval-mode derivation, citation/result payload shape, snippet fallback, audit step names/order, audit final status selection, and transcript metadata keys were not changed. ASR browser handoff code, fallback-provider unavailable code, retry/delay/timeout constructor defaults, circuit breaker thresholds, provider fallback order, browser handoff settings, provider attempt payloads, retry/backoff handling, timeout handling, degraded payload shape, and stream text joining behavior were not changed. Semantic point similarity threshold, cooldown default, required point IDs, stop-word list, keyword overlap formula, semantic fallback keyword threshold, embedding-failure keyword threshold, covered-point persistence, matched-text truncation, stats payload shape, and feedback deduplication behavior were not changed. RAG profile route paths, admin dependency, schema defaults, field range validation, response redaction, cross-encoder API key encrypt/clear semantics, system-default unset/set flow, applied-KB count lookup, delete protection, knowledge-base listing fields, and response payload shape were not changed. Admin settings route paths, BusinessRuleConfig lifecycle, surface keys, default definitions, validators, permission dependency, validation failure mapping, publish/rollback behavior, audit log listing, and response payload shape were not changed. Admin analytics projection-backed score basis, overview growth calculation, score rounding digits, completion/evaluable filters, issue-family grouping, agent/persona aggregation, leaderboard grouping/sorting/ranking, duration conversion, and response fields were not changed. Growth API route paths, dashboard/adaptive-difficulty dry-run/notification/goal flows, Pydantic goal validation, growth service delegation, error codes, user-facing fallback messages, and response payload shape were not changed. Log sanitizer sensitive-field names, sensitive regex patterns, masking algorithm, database URL masking, recursive dict/list traversal, and structlog processor sanitization behavior were not changed. Circuit breaker failure threshold, success threshold, timeout, half-open max-call defaults, can-execute behavior, success/failure recording, state transition rules, callback invocation, global registry behavior, and stats payload fields were not changed. Support runtime overview/fault payload fields, release-health status resolution, active/scoring status filters, stuck-scoring window, asset governance indexes, asset change labels, seven-day change counting semantics, admin paths, and supplemental log handling were not changed. PPT version storage path, current-presentation path, max retained versions, version directory naming, version history sorting, current-version comparison, rollback copy flow, cleanup deletion order, fallback error codes, and existing async current-version lookup behavior were not changed. Runtime diagnostics claim truth status/source/evidence-score normalization, main-issue and next-goal required fields, coach-health status/message fallback copy, KB lock timeout/pass-score defaults, retrieval ledger bounds, retrieval status derivation, runtime event merge behavior, and diagnostics response payload fields were not changed. Session-state TTL default, cleanup interval default, Redis URL/key-prefix environment names, Redis key prefix default, snapshot fields, reconnect-state summary fields, operation metric names, save/get/delete behavior, healthcheck loop behavior, and lifecycle log/error semantics were not changed. API rate limiter default call limit, default period, cleanup interval, storage key format, IP/user identifier resolution, blocked-window behavior, rate-limit response code, retry-after message copy, response headers, and global limiter singleton behavior were not changed.
