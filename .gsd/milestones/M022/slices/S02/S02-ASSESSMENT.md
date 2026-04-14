# M022 / S02 close-out wrap-up status

## Verdict

S02 implementation is **not yet ready for `gsd_complete_slice`**.

The slice-specific runtime/admin/doc work is landed and the primary S02-focused proofs are green, but the required broad backend verification gate from the slice plan still fails on collateral `knowledge` unit coverage outside the direct industry-pack/admin/runtime seam.

## What is already done

- Industry-pack / customer-pressure contract is now explicit and inspectable through existing entrypoints:
  - `GET /api/v1/admin/agents/industry-pack-contract`
  - `GET /api/v1/admin/personas/industry-pack-contract`
  - `GET /api/v1/scenarios/sales/runtime-contract`
- Frozen session provenance now includes compact `voice_policy_snapshot_ref.runtime_binding` for downstream report/replay/session-detail inspection.
- Admin persona and agent detail pages now surface the contract on existing pages instead of introducing a second content platform.
- Architecture scan and next-wave plan now document the operating rules and manual-ops boundary for `industry pack` / `customer pressure` / `knowledge bundle` / `scenario package`.

## Fresh verification evidence already collected

### Passed
- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_voice_runtime_session_snapshot.py backend/tests/contract/test_sessions.py backend/tests/unit/test_sales_scenarios_api.py -q`
- `npm --prefix web test -- --run "src/app/admin/personas/[id]/page.test.tsx"`
- `npm --prefix web test -- --run "src/app/admin/agents/[id]/page.test.tsx"`
- `rg -n "persona_policy|customer_pressure|scenario|knowledge_base|agent|industry" backend/src/agent backend/src/sales_bot backend/src/common/knowledge`
- `rg -n "industry pack|customer pressure|scenario package|knowledge bundle" .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md .gsd/plans/GSD_PLAN_post-M018-next-wave.md`

### Collateral verification fixes already applied
- App-mounted admin route families now expose expected public `ADMIN_REQUIRED` wording while preserving structured `[ROLE_REQUIRED]` dependency detail.
- Shared backend test harness now survives `common.db.session` reload tests by overriding all imported `get_db` callables and issuing a real fallback JWT for the canonical test user.
- Startup/bootstrap authority test now restores development baseline after reloading `common.db.session` under production env.
- `backend/tests/unit/common/test_knowledge_reranker.py` expectations were aligned to the current reranker pass/filter contract.
- `backend/tests/unit/common/test_knowledge_service_fallback.py` dummy collection fixtures were partially updated toward the current BM25 contract.

## Remaining blocker

The required broad gate still fails:

- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests -k "persona or knowledge or scenario or policy" -x -q`

Current remaining failure at wrap-up time:
- `backend/tests/unit/common/test_knowledge_service_fallback.py`
  - `test_search_multiple_falls_back_to_keywords_when_embedding_fails`
  - `test_search_multiple_merges_vector_and_keyword_into_hybrid`

This is in the generic knowledge fallback seam, not in the direct S02 industry-pack runtime/admin surface, but the slice plan still requires the broad gate to be green before close-out.

## Precise resume steps

1. Re-open:
   - `backend/tests/unit/common/test_knowledge_service_fallback.py`
   - `backend/src/common/knowledge/service.py`
2. Reconcile the unit test fixtures/expectations with the shipped fallback/hybrid retrieval contract in `KnowledgeService.search_multiple(...)`.
3. Re-run the exact slice-plan backend gate:
   - `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests -k "persona or knowledge or scenario or policy" -x -q`
4. If green, re-run the already-passing web/doc/grep gates and then proceed with:
   - `gsd_complete_slice(...)`

## Important note for next closer

Do **not** mark S02 complete from the current state. The honest state is: implementation landed, focused slice proofs green, broad required backend gate still red on collateral knowledge fallback tests.
