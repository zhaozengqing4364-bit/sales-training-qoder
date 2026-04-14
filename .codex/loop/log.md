- time: 2026-04-14T16:33:03+08:00
  mode: grow
  item id: M022-S04-T03
  files changed:
    - .gsd/plans/GSD_PLAN_post-M018-next-wave.md
    - .codex/roadmap/PROJECT_FUTURE.md
    - .gsd/DECISIONS.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Finished M022/S04/T03 by turning the org-boundary target-state into a concrete next-wave enterprise roadmap input instead of leaving it buried in the slice plan. The post-M018 plan now states the default stay-in-modular-monolith rule, the exact enterprise inputs to schedule next (`organization_member`, scope-aware readers, org rollout binding, organization metadata, and provisioning adapter contracts), the explicit service split triggers, and the out-of-scope guardrail against multi-tenant runtime, direct SSO/CRM integration, new org dashboards, or rewriting existing global rows into org-owned rows. `.codex/roadmap/PROJECT_FUTURE.md` is no longer a stub; it now records the same product promise, evidence snapshot, priority order, candidate scoring, service split test, and out-of-scope rules. Decision D250 locks the same execution path into the shared decision log.
  verification commands:
    - rg -n "organization|team|tenant|monolith|service split|out-of-scope|SSO|CRM" .gsd/plans/GSD_PLAN_post-M018-next-wave.md .codex/roadmap/PROJECT_FUTURE.md
    - rg -n "modular monolith|service split|SSO|CRM|org sync" .gsd/DECISIONS.md
  verification results: passed; the exact task-plan grep gate exited 0 and matched the roadmap handoff language in both durable planning artifacts, and the focused decision grep confirmed D250 wrote back the modular-monolith default, service-split triggers, and SSO/CRM/org-sync adapter boundary.
  success signal status: future enterprise work now has one durable entry rule — keep organization/team/member rollout inside the modular monolith until real scale/isolation/compliance pressure appears, and treat SSO/CRM/org sync as metadata/provisioning adapters rather than runtime authority.
  rollback note: if a later milestone introduces real org-scoped write isolation or external integration authority, update the M022/S04 section, PROJECT_FUTURE candidate scoring, and the recorded decision together so roadmap language does not drift from the actual execution contract.

- time: 2026-04-14T16:13:30+08:00
  mode: grow
  item id: M022-S03
  files changed:
    - web/src/app/admin/page.tsx
    - web/src/app/admin/page.test.tsx
    - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
    - .gsd/plans/GSD_PLAN_post-M018-next-wave.md
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .gsd/PROJECT.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Closed M022/S03 after fresh slice-level verification confirmed the manager/admin truth-surface boundary now holds end to end. The admin home no longer pretends to be a live operator dashboard beyond the single real effectiveness card; manager-lite, admin analytics, and admin user detail/interventions are the only currently productized manager/admin truth surfaces; the architecture scan and post-M018 plan now document the same product boundary; and the knowledge log records the guardrail against reintroducing homepage-only rollups or fake metrics.
  verification commands:
    - npm --prefix web test -- --run "src/app/admin/page.test.tsx" "src/components/admin/manager-lite-panel.test.tsx"
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_admin_analytics_service.py -x -q
    - rg -n "manager|calibration|truth surface|fake stats|placeholder|canonical evidence" .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md .gsd/plans/GSD_PLAN_post-M018-next-wave.md
    - lsp diagnostics web/src/app/admin/page.tsx web/src/app/admin/page.test.tsx web/src/components/admin/manager-lite-panel.tsx backend/src/admin/api/users.py backend/src/common/analytics/admin_analytics_service.py backend/tests/unit/common/test_admin_analytics_service.py
  verification results: passed; the exact web slice bundle finished 3/3 green, the backend admin analytics bundle finished 5/5 green, the architecture/plan grep gate matched the documented truth-surface boundary, and diagnostics were clean on the touched authority files.
  success signal status: M022/S03 is ready for slice completion and downstream roadmap reassessment; future organization/team/tenant planning can now treat manager-lite, admin analytics, and admin user detail/interventions as the real manager/admin evidence surfaces while keeping admin-home inventory cards and standalone calibration workspaces in future scope.
  rollback note: if later work productizes new manager/admin surfaces, update the admin-home read side, the focused web/backend proof bundle, the architecture scan, the post-M018 plan, and the knowledge/decision guardrails together so the product story never gets ahead of the shipped evidence line.

- time: 2026-04-14T16:08:22+08:00
  mode: grow
  item id: M022-S03-T03
  files changed:
    - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
    - .gsd/plans/GSD_PLAN_post-M018-next-wave.md
    - .gsd/DECISIONS.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Finished M022/S03/T03 by writing the manager/admin truth-surface product boundary back into the durable planning artifacts. The architecture scan now names the three real manager calibration/team coaching entry points (`manager-lite-panel`, `/admin/users/[id]`, `/admin/analytics`), distinguishes the already-productized canonical-evidence surfaces from the still-inventory admin-home and workflow shells, and locks the messaging guardrail against selling placeholder cards as live ops tooling. The post-M018 plan now mirrors that same boundary so downstream roadmap work cannot drift into broader commercial claims than the shipped evidence line supports, and decision D247 records that these are the only currently productized manager/admin truth surfaces.
  verification commands:
    - rg -n "manager|calibration|truth surface|fake stats|placeholder|canonical evidence" .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md .gsd/plans/GSD_PLAN_post-M018-next-wave.md
  verification results: passed; the exact task-plan grep gate exited 0 and matched the new entry-point, truth-surface, placeholder, fake-stats, and canonical-evidence boundary language in both target documents.
  success signal status: M022/S03 now has one durable product story for manager/admin truth surfaces — supervisors can rely on evidence-backed analytics, manager-lite, and user drill-in today, while admin-home inventory cards and independent calibration workspaces remain explicitly future work.
  rollback note: if later slices productize new manager/admin surfaces, update the architecture scan boundary section, the M022-S03 product-plan entry, and the corresponding UI/runtime proof in the same change so the docs never get ahead of the shipped evidence line.

- time: 2026-04-14T16:01:23+08:00
  mode: grow
  item id: M022-S03-T02
  files changed:
    - web/src/app/admin/page.tsx
    - web/src/app/admin/page.test.tsx
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Finished M022/S03/T02 by removing the remaining fake admin-home decision surfaces instead of trying to fake-connect them. `web/src/app/admin/page.tsx` now keeps only the one live effectiveness card on `api.internal.health + api.analyticsOpen.getDashboard`, replaces the old faux announcement/log/alert/activity/config blocks with an explicit “当前真实管理入口” section, and turns the rest of the home into inventory-only gap cards that point supervisors back to `/admin/users`, `/admin/analytics`, and `/admin/logs`. The focused admin page proof now also locks out the old fake strings (`GPT-4-Turbo`, quota alerts, backup activity rows, etc.), while manager-lite and backend admin analytics stay green on the same projection-backed evidence line.
  verification commands:
    - npm --prefix web test -- --run src/app/admin/page.test.tsx
    - npm --prefix web test -- --run "src/app/admin/page.test.tsx" "src/components/admin/manager-lite-panel.test.tsx" && backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_admin_analytics_service.py -x -q
    - browser_navigate http://127.0.0.1:3000/admin
  verification results: passed for the focused admin-page proof and the exact task-plan bundle (3 web tests + 5 backend tests). Browser automation itself is still blocked in this environment because the Playwright Chromium binary is missing, so the runtime UI attempt failed before navigation and is recorded as an environment limitation rather than a product regression.
  success signal status: M022/S03 manager/admin surfaces now present one honest home-page boundary: live authority lives in the effectiveness card and the existing user/analytics/log surfaces, while the remaining home sections are explicitly inventory-only instead of pretending to be operational tooling.
  rollback note: if later work restores homepage actions, alerts, or activity streams, reconnect them to a real backend authority first and update the focused admin page test in the same change so the home page cannot drift back into fake operator UI.

- time: 2026-04-14T15:47:30+08:00
  mode: grow
  item id: M022-S03-T01
  files changed:
    - web/src/app/admin/page.tsx
    - web/src/app/admin/page.test.tsx
    - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
    - .gsd/DECISIONS.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Finished M022/S03/T01 by turning the admin home into an honesty-first inventory instead of a mixed live/demo dashboard. `web/src/app/admin/page.tsx` now keeps only the top effectiveness card on real `internal.health + analyticsOpen.getDashboard` data, explicitly marks the rest of the admin-home ops cards as truth-surface inventory, removes the hardcoded fake user/session/resource/storage numbers, and rewrites those dialogs as gap descriptions plus links into existing real surfaces. The architecture scan now records the exact priority order for S03: admin analytics, manager-lite, and user detail/interventions are already projection-backed P0 truth surfaces; the remaining admin-home cards and draft action areas are not.
  verification commands:
    - npm --prefix web test -- --run src/app/admin/page.test.tsx
    - rg -n "2543|84|placeholder|demo|mock|dummy|manager-lite|analytics" web/src/app/admin web/src/components/admin backend/src/common/analytics backend/src/admin/api
    - rg -n "2,543|84|42%|68%|75%|450 GB" web/src/app/admin/page.tsx
  verification results: passed; the new fail-first admin page proof finished 1/1 green, the exact task-plan grep gate stayed green across the intended manager/admin/analytics surfaces, and the targeted old-literal grep exited 1 because the fake admin-home stats are gone.
  success signal status: M022/S03 now has one durable inventory showing which manager/admin surfaces already sit on canonical evidence and which admin-home cards must stay downgraded until T02 connects real stats.
  rollback note: if later work reconnects any admin-home card to real authority, update the page copy/dialogs, the focused admin page test, and the M022/S03 architecture inventory together so the home page never drifts back into mixed live/demo claims.

- time: 2026-04-14T14:45:15+08:00
  mode: grow
  item id: M022-S02-T03
  files changed:
    - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
    - .gsd/plans/GSD_PLAN_post-M018-next-wave.md
    - .gsd/milestones/M022/slices/S02/tasks/T03-SUMMARY.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Wrote the industry-pack operating rules back into the durable planning artifacts so the architecture scan and next-wave plan now agree on the honest control boundary: `industry pack` remains a composed asset over existing admin surfaces, `customer pressure` is a live runtime lever, `knowledge bundle` is the retrieval/report evidence lever, `scenario package` is only the entry/routing narrative lever, and future manager calibration must reuse `voice_policy_snapshot_ref.runtime_binding` instead of inventing a second asset taxonomy.
  verification commands:
    - rg -n "industry pack|customer pressure|scenario package|knowledge bundle" .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md .gsd/plans/GSD_PLAN_post-M018-next-wave.md
  verification results: passed; the exact task-plan grep gate exited 0 and matched the new operating-rule/manual-boundary language in both documents.
  success signal status: M022/S02 no longer relies on planner memory to explain which asset changes affect runtime, report evidence, manager calibration, or still require manual content operations.
  rollback note: if later slices promote a new asset authority or let `scenario package` influence runtime truth directly, update the M022/S02 architecture section, the next-wave plan entry, and the frozen runtime-binding/read-side wording together so docs do not drift from the shipped control boundary.

- time: 2026-04-14T13:43:55+08:00
  mode: grow
  item id: M022-S01
  files changed:
    - backend/src/common/effectiveness/methodology.py
    - backend/src/common/effectiveness/canonical.py
    - backend/src/agent/capabilities/realtime_scoring.py
    - backend/src/common/conversation/session_evidence.py
    - backend/src/common/services/practice_session_service.py
    - backend/src/common/api/practice.py
    - docs/api-contract/effectiveness.md
    - docs/api-contract/README.md
    - web/src/app/(user)/practice/[sessionId]/report/page.tsx
    - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .gsd/PROJECT.md
    - .gsd/milestones/M022/slices/S01/S01-SUMMARY.md
    - .gsd/milestones/M022/slices/S01/S01-UAT.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Closed M022/S01 after fresh slice-level verification confirmed the first methodology-aware sales rubric is now a real shared authority seam: `common.effectiveness.methodology` defines the five first-round rubrics, the canonical kernel and compatibility readers carry the same rubric status across realtime/report/replay/history/admin, learner-facing docs/report copy now explain the same contract honestly, and downstream M022 slices can reuse this seam instead of inventing their own sales taxonomy.
  verification commands:
    - rg -n "sales_stage|realtime_scoring|effectiveness|main_issue|next_goal|dimension_scores" backend/src/common backend/src/agent docs/api-contract
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests -k "sales and (report or replay or history or analytics)" -x -q
    - rg -n "qualification|discovery|value|objection|next-step|rubric" docs/api-contract .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md web/src/app/(user)/practice/[sessionId]/report/page.tsx
    - npm --prefix web test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'
  verification results: passed; both exact slice-plan grep gates exited 0, the backend sales report/replay/history/analytics bundle finished 24 selected tests green (plus 1 skipped), and the learner report page suite finished 24/24 green.
  success signal status: M022 can now build persona/scenario packs and manager truth surfaces on one explicit methodology contract instead of re-deriving what counts as good sales behavior in each subsystem.
  rollback note: if a later slice adds a standalone qualification stage or changes rubric exposure, update `common.effectiveness.methodology`, the canonical builder/compat reader wiring, docs/api-contract, learner report copy, and the focused backend/web proof together so the outward language and runtime truth do not drift.

- time: 2026-04-14T13:13:00+08:00
  mode: grow
  item id: M022-S01-T01
  files changed:
    - backend/src/common/effectiveness/methodology.py
    - backend/src/common/effectiveness/__init__.py
    - backend/tests/unit/test_sales_methodology_contract.py
    - docs/api-contract/effectiveness.md
    - docs/api-contract/README.md
    - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Defined the first methodology-aware sales rubric contract as a code-owned additive crosswalk instead of another score schema. `common.effectiveness.methodology.get_sales_methodology_contract()` now pins five first-round rubrics (`discovery_qualification`, `value_story`, `evidence_proof`, `objection_reframe`, `next_step_commitment`) to the shipped canonical kernel dimensions, sales_stage coverage, report `main_issue` / `next_goal` families, and realtime/report/history/admin evidence paths; docs/api-contract/effectiveness.md and the architecture scan now point downstream work at the same authority line, while the knowledge log records the non-obvious boundary that qualification is still merged into opening/discovery until the runtime stage contract changes.
  verification commands:
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_sales_methodology_contract.py -q
    - rg -n "sales_stage|realtime_scoring|effectiveness|main_issue|next_goal|dimension_scores" backend/src/common backend/src/agent docs/api-contract
    - lsp diagnostics backend/src/common/effectiveness/methodology.py
    - lsp diagnostics backend/src/common/effectiveness/__init__.py
    - lsp diagnostics backend/tests/unit/test_sales_methodology_contract.py
  verification results: passed; the fail-first focused contract suite finished 2/2 green, the exact task-plan grep gate now exposes the new methodology authority through both code and docs, and diagnostics stayed clean on every touched Python file.
  success signal status: future T02 work can wire realtime/report/manager read-side consumers onto one explicit methodology contract instead of re-deriving sales semantics from scattered dimension aliases and issue-family heuristics.
  rollback note: if later slices split qualification into its own stage or promote a new manager surface into authority, update `common.effectiveness.methodology`, docs/api-contract/effectiveness.md, the architecture scan note, and the focused unit proof together so the rubric crosswalk remains truthful.

- time: 2026-04-14T12:08:00+08:00
  mode: grow
  item id: M021-S04-T01
  files changed:
    - backend/src/common/ai/llm_service.py
    - backend/src/sales_bot/websocket/stepfun_realtime_handler.py
    - backend/tests/unit/test_ai_quality_event_inventory.py
    - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Finished M021/S04/T01 by turning the hidden AI fallback/default/cost behavior into a code-owned inventory instead of planner prose. `LLM_RUNTIME_EVENT_INVENTORY` now names the four shipped compat blind spots in `common.ai.llm_service` (filler fallback responses, parse-to-default 60 scores, coarse `[REPORT_GENERATION_FAILED]` surfaces, and session-only cost totals), `STEPFUN_RUNTIME_EVENT_INVENTORY` now names the live realtime degradations/mode seams in `stepfun_realtime_handler` (KB warmup degradation, capability pipeline failure, knowledge-answer rollout mode, browser TTS fallback, and transcription-timeout blocking), and the architecture scan/knowledge log write back the same authority line so T02 can add one explicit event schema instead of rediscovering these paths.
  verification commands:
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_ai_quality_event_inventory.py -q
    - rg -n "default|fallback|NO_STAGE_RESULTS|cost|report_generation_failed|knowledge_answer|degraded|claim_truth" backend/src/common backend/src/sales_bot backend/src/evaluation
    - rg -n "quality / cost / failure inventory baseline|LLM_RUNTIME_EVENT_INVENTORY|STEPFUN_RUNTIME_EVENT_INVENTORY|default score 不等于真实低分|knowledge-answer path truth 仍必须沿 compat seam 读取" .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md backend/src/common/ai/llm_service.py backend/src/sales_bot/websocket/stepfun_realtime_handler.py
    - lsp diagnostics backend/src/common/ai/llm_service.py
    - lsp diagnostics backend/src/sales_bot/websocket/stepfun_realtime_handler.py
    - lsp diagnostics backend/tests/unit/test_ai_quality_event_inventory.py
  verification results: passed; the fail-first focused inventory test finished 2/2 green, the exact task-plan grep gate stayed green after the write-back, the focused architecture grep proves the new inventory section and code constants are grep-discoverable, and LSP diagnostics stayed clean on every touched Python file.
  success signal status: future agents can now inspect explicit LLM/StepFun event inventories and the architecture note instead of reverse-engineering hidden AI failures from default scores, fallback copy, or scattered logs.
  rollback note: if T02 changes event ids or migrates any of these surfaces into a real unified event schema, keep `LLM_RUNTIME_EVENT_INVENTORY`, `STEPFUN_RUNTIME_EVENT_INVENTORY`, the focused unit test, and the architecture/knowledge write-back aligned so the discovery inventory remains truthful until the unified event line fully replaces it.

- time: 2026-04-14T11:46:58+08:00
  mode: grow
  item id: M021-S03-T03
  files changed:
    - web/src/lib/api/types.ts
    - web/src/lib/session-evidence.ts
    - web/src/app/(user)/practice/[sessionId]/report/page.tsx
    - web/src/app/(user)/practice/[sessionId]/replay/page.tsx
    - web/src/app/(dashboard)/history/page.tsx
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Finished M021/S03/T03 by wiring the front-end read side onto the shared canonical/compat score reader instead of letting each surface guess from legacy rollups. Report and replay now expose the resolved score source via data-contract-source while still falling back in the contract order canonical -> compatibility reader -> legacy, history applies the same helper for list cards and trend deltas, the shared web API types now declare canonical_evaluation_kernel plus compatibility_readers, and the accidental duplicated JSX tails from the previous failed attempt were removed so report/replay parse cleanly again.
  verification commands:
    - npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx" "src/app/(dashboard)/history/page.test.tsx"
    - rg -n "prefer `canonical_evaluation_kernel`|compatibility_readers|retire 阶段" .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md -S
  verification results: passed; the exact T03 web bundle finished 44/44 green, and the architecture scan still contains the canonical -> compat -> legacy retirement order note that the new read-side helper now matches at runtime.
  success signal status: done; report, replay, and history now explicitly consume the canonical/compat contract rather than silently trusting stale legacy rollups.
  rollback note: if later slices retire compatibility readers, keep web/src/lib/session-evidence.ts, web/src/lib/api/types.ts, the report/replay/history page surfaces, and the focused page tests aligned so the fallback order changes intentionally instead of drifting.

- time: 2026-04-14T11:35:57+08:00
  mode: grow
  item id: M021-S03-T03
  files changed:
    - web/src/lib/api/types.ts
    - web/src/lib/session-evidence.ts
    - web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
    - web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx
    - web/src/app/(dashboard)/history/page.test.tsx
    - web/src/app/(user)/practice/[sessionId]/report/page.tsx
    - web/src/app/(user)/practice/[sessionId]/replay/page.tsx
    - web/src/app/(dashboard)/history/page.tsx
    - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Started M021/S03/T03 and completed the skill-required reads plus a fail-first web test pass for canonical-vs-compat consumption, then attempted a shared report/replay/history score-reader cutover. That runtime cutover did not converge inside the context budget: report/replay rendering regressed while trying to reuse a shared helper, so the risky path was backed out to leave the repo closer to the pre-task runtime baseline. The durable progress that remains is (1) explicit failing tests in report/replay/history that prove what T03 still needs, and (2) an architecture-scan note that fixes the intended retirement order as canonical -> compat -> legacy.
  verification commands:
    - npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx" "src/app/(dashboard)/history/page.test.tsx"
  verification results: failed; the new fail-first tests expose the intended canonical/compat cutover gaps, and the first runtime wiring attempt caused report/replay regressions before it was partially backed out. Resume from the stable baseline, then reintroduce the reader helper one surface at a time.
  success signal status: partial only; the task is not complete and should not be checked off yet.
  rollback note: before resuming, confirm report/replay/history pages are back on the legacy stable path, then use the new fail-first tests as the only acceptance target for the next incremental cutover.

  mode: grow
  item id: M021-S03-T02
  files changed:
    - backend/src/common/effectiveness/canonical.py
    - backend/src/common/effectiveness/__init__.py
    - backend/src/common/conversation/session_evidence.py
    - backend/src/common/analytics/history_service.py
    - backend/src/common/services/practice_report_service.py
    - backend/src/common/conversation/replay.py
    - backend/src/agent/capabilities/realtime_scoring.py
    - backend/src/sales_bot/websocket/components/stepfun_message_helpers.py
    - backend/src/common/db/schemas.py
    - backend/src/common/conversation/schemas.py
    - backend/tests/contract/test_practice_evidence_contract.py
    - backend/tests/unit/test_history_service_evidence_projection.py
    - backend/tests/unit/test_realtime_scoring.py
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Implemented the canonical evaluation kernel as a real runtime/read-side payload instead of a schema-only note: `common.effectiveness.canonical` now builds one scenario-aware kernel plus compatibility readers, realtime scoring emits and persists it, session-evidence/history/report/replay now expose the same kernel while still returning legacy rollup fields, and the focused contract/history/realtime tests lock the shared-kernel + compat-reader behavior in place.
  verification commands:
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_effectiveness_canonical_kernel.py backend/tests/unit/test_realtime_scoring.py backend/tests/unit/test_history_service_evidence_projection.py -q
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_conclusion_evidence_parity.py backend/tests/contract/test_practice_evidence_contract.py backend/tests/unit/common/test_admin_analytics_service.py backend/tests/unit/test_history_service_evidence_projection.py -x -q
    - lsp diagnostics backend/src/common/effectiveness/canonical.py backend/src/common/conversation/session_evidence.py backend/src/common/analytics/history_service.py backend/src/common/services/practice_report_service.py backend/src/common/conversation/replay.py backend/src/agent/capabilities/realtime_scoring.py backend/src/common/db/schemas.py backend/src/common/conversation/schemas.py backend/src/common/api/practice.py backend/src/common/services/practice_session_service.py
  verification results: passed; the new canonical-kernel focused unit bundle finished 16/16 green, the exact task-plan verification bundle finished 49/49 green, and LSP diagnostics stayed clean on every touched backend file.
  success signal status: downstream T03 web readers can now distinguish canonical truth from compatibility mirrors directly from API payloads instead of reverse-engineering sales/presentation score semantics from top-level legacy fields.
  rollback note: if later work changes the canonical payload shape, update `common.effectiveness.canonical`, StepFun score-snapshot normalization, session-evidence/report/replay/history projections, and the focused realtime/history/practice-contract tests together or persisted message snapshots will silently drop the new kernel view again.

- time: 2026-04-14T10:57:30+08:00
  mode: grow
  item id: M021-S03-T02
  files changed:
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Started M021/S03/T02 execution, completed skill-required reads plus local code/test audit, and confirmed the current slice verification bundle is still green before any edits. The missing work is not a broken existing contract but the absence of a shipped canonical evaluation kernel payload/compat-reader implementation across realtime score snapshots and report/replay/history/admin read models.
  verification commands:
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_conclusion_evidence_parity.py backend/tests/contract/test_practice_evidence_contract.py backend/tests/unit/common/test_admin_analytics_service.py backend/tests/unit/test_history_service_evidence_projection.py -x -q
    - rg -n "canonical|compatibility_reader|evaluation_kernel|dimension_scores|logic_score|accuracy_score|completeness_score|overall_score" backend/src/common backend/src/agent backend/src/presentation_coach -g '!**/__pycache__/**'
  verification results: partial-pass; the exact task-plan verification command finished 47/47 green before any code edits, and grep confirmed the current backend still centralizes read-side projection logic in session_evidence/history/admin while realtime snapshots and report/replay schemas do not yet surface a canonical evaluation kernel object.
  success signal status: durable handoff only; no implementation landed yet.
  rollback note: no product code changed in this unit, so resume directly from the saved CONTEXT-DRAFT and then add fail-first canonical-kernel tests before editing runtime/read-side code.

- time: 2026-04-14T10:32:06+08:00
  mode: grow
  item id: M021-S02-T03
  files changed:
    - docs/api-contract/prompt-templates.md
    - docs/api-contract/voice-runtime.md
    - docs/api-contract/personas.md
    - docs/api-contract/model-configs.md
    - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Wrote the post-T02 prompt authority line back into durable admin-facing docs so operators no longer have to infer runtime impact from code: prompt-templates now names the compiled legacy evaluation/report contract and its fail-closed diagnostics, personas + voice-runtime name the live StepFun instruction authority and frozen snapshot rule, model-configs owns the provider/base_url repair path, and the architecture scan now points S03 at the compiled prompt seam instead of the old fake-integration story.
  verification commands:
    - rg -n "compiled prompt|template source|guardrail|missing var|base_url" docs/api-contract .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md backend/src/prompt_templates -S
    - rg -n "Admin 变更路由|Authority boundary|canonical evaluation kernel authority entry|instruction_contract_hash|PROMPT_CONTRACT_BASE_URL_REQUIRED" docs/api-contract/prompt-templates.md docs/api-contract/voice-runtime.md docs/api-contract/personas.md docs/api-contract/model-configs.md .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md -S
  verification results: passed; the exact task-plan grep gate stayed green after the doc sync, and the focused routing grep proves the admin-facing surfaces now distinguish which changes affect legacy compiled prompt contracts versus live StepFun instruction contracts and which failures route to model-configs.
  success signal status: future S03 work can now start from one truthful compiled-prompt authority entry in both docs and architecture inventory instead of relying on stale template-bypass explanations or guessing which admin surface owns each runtime effect.
  rollback note: if later work changes the compiled-contract seam, base_url policy handling, or which admin surface owns a runtime prompt effect, update prompt-templates.md, voice-runtime.md, personas.md, model-configs.md, and the architecture scan together so operator guidance stays aligned with the shipped control plane.

- time: 2026-04-14T10:31:00+08:00
  mode: grow
  item id: M021-S02-T02
  files changed:
    - backend/src/prompt_templates/compiled_contract.py
    - backend/src/prompt_templates/service.py
    - backend/src/common/ai/config_manager.py
    - backend/src/common/ai/llm_service.py
    - backend/src/evaluation/services/staged_evaluation.py
    - backend/src/evaluation/services/comprehensive_report.py
    - backend/src/common/services/practice_report_service.py
    - backend/src/prompt_templates/taxonomy.py
    - backend/src/sales_bot/services/voice_instruction_compiler.py
    - backend/tests/unit/prompt_templates/test_compiled_prompt_contract.py
    - backend/tests/unit/prompt_templates/test_taxonomy.py
    - backend/tests/unit/evaluation/test_staged_evaluation_service.py
    - backend/tests/unit/evaluation/test_comprehensive_report_service.py
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Promoted PromptTemplateService from lookup-only governance helper into a real runtime authority for legacy evaluation/report flows: staged evaluation and comprehensive report now compile hashed prompt contracts with runtime consumer metadata, LLMService consumes those contracts with explicit missing-variable and base_url diagnostics plus fail-closed behavior, taxonomy now marks evaluation/report as compiled-contract consumers instead of template-bypass seams, and the only compatibility leftover is the raw dict hardcoded prompt fallback inside LLMService for untouched callers.
  verification commands:
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/prompt_templates/test_compiled_prompt_contract.py backend/tests/unit/prompt_templates/test_taxonomy.py backend/tests/unit/evaluation/test_staged_evaluation_service.py backend/tests/unit/evaluation/test_comprehensive_report_service.py backend/tests/unit/test_voice_instruction_compiler.py -q
    - lsp diagnostics backend/src/prompt_templates/compiled_contract.py backend/src/prompt_templates/service.py backend/src/common/ai/config_manager.py backend/src/common/ai/llm_service.py backend/src/evaluation/services/staged_evaluation.py backend/src/evaluation/services/comprehensive_report.py backend/src/prompt_templates/taxonomy.py backend/src/sales_bot/services/voice_instruction_compiler.py backend/src/common/services/practice_report_service.py
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests -k "prompt or knowledge_answer or report" -x -q
  verification results: passed; the focused compiled-contract suite finished 80/80 green, diagnostics stayed clean on every touched Python file, and the exact slice gate finished 274 passed / 6 skipped after one logger-formatting failure surfaced by the new fail-closed path was fixed in practice_report_service.
  success signal status: downstream prompt work can now rely on one truthful authority line — PromptTemplateService compiles evaluation/report contracts, LLMService records and enforces their runtime diagnostics, voice instructions share the same contract-versioned hashing scheme, and taxonomy no longer claims the staged-evaluation/report consumers are fake template integrations.
  rollback note: if T03 or later work removes the raw dict compatibility fallback or extends compiled contracts to more consumers, update prompt_templates/compiled_contract.py, PromptTemplateService.compile_runtime_prompt_contract, LLMService LEGACY_PROMPT_ENTRYPOINTS + contract logging, taxonomy tests, and the slice docs together so code/runtime/document truth stays aligned.

- time: 2026-04-14T10:04:33+08:00
  mode: grow
  item id: M021-S02-T01
  files changed:
    - backend/src/common/ai/llm_service.py
    - backend/src/prompt_templates/taxonomy.py
    - backend/tests/unit/prompt_templates/test_taxonomy.py
    - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Codified the prompt control-plane taxonomy into code-owned inventory so downstream runtime work stops guessing which prompt surfaces are live, compat, or fake integrations: llm_service now flags its legacy hardcoded prompt entrypoints explicitly, prompt_templates/taxonomy.py maps the current sources and runtime consumers, and the architecture scan/knowledge log now name the two real template-bypass seams where template lookup still does not drive the model call.
  verification commands:
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/prompt_templates/test_taxonomy.py backend/tests/unit/test_voice_instruction_compiler.py backend/tests/unit/evaluation/test_staged_evaluation_service.py backend/tests/unit/evaluation/test_comprehensive_report_service.py backend/tests/unit/test_report_generation_trigger.py -q
    - rg -n "PromptTemplateService|render\(|generate_report|evaluate\(|instructions|persona_policy|strict=|SilentUndefined|base_url" backend/src/prompt_templates backend/src/common/ai backend/src/sales_bot/services backend/src/presentation_coach/services backend/src/evaluation/services
    - lsp diagnostics backend/src/common/ai/llm_service.py
    - lsp diagnostics backend/src/prompt_templates/taxonomy.py
    - lsp diagnostics backend/tests/unit/prompt_templates/test_taxonomy.py
  verification results: passed; the focused prompt-taxonomy proof bundle finished 86/86 green, the exact slice grep gate now surfaces the live instruction/persona/guardrail seams plus the staged-evaluation/report template-bypass entrypoints, and LSP diagnostics were clean on all touched Python files.
  success signal status: future M021/S02 work can now start from one truthful prompt authority map instead of inferring it from call-site names — StepFun compiled instructions are clearly the live runtime contract, presentation interruption templates are real runtime helpers, and legacy evaluation/report still flow through hardcoded llm_service prompts despite resolving templates first.
  rollback note: if T02 rewires legacy evaluation/report to consume rendered templates or promotes another prompt surface into live runtime authority, update common.ai.llm_service LEGACY_PROMPT_ENTRYPOINTS, prompt_templates/taxonomy.py, the architecture scan prompt-control section, and the focused taxonomy tests together so code-owned inventory and runtime truth do not drift again.

- time: 2026-04-14T08:45:46+08:00
  mode: grow
  item id: M020-S04-T03
  files changed:
    - .sisyphus/deploy/ai-backend.service
    - .sisyphus/deploy/ai-frontend.service
    - .sisyphus/deploy/ai-practice.nginx.conf
    - .sisyphus/plans/cloud-full-redeploy-115-191-36-90.md
    - docs/backup-recovery-runbook.md
    - docs/api-contract/support-runtime.md
    - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Wrote the recovery-drill and deploy boundary back into the long-lived ops surfaces so the shipped systemd/nginx bundle, support runtime contract, runbook, and cloud redeploy plan all agree that the current deployment is single-node, future multi-instance rollout needs external drain orchestration, and release/recovery proof must pair node health with repo-local drill evidence instead of treating either one as sufficient alone.
  verification commands:
    - rg -n "single-node|multi-instance|drill|recovery|health" .sisyphus/deploy .sisyphus/plans docs/backup-recovery-runbook.md .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
    - rg -n "release-health|recovery drill|summary.json|process-local|redis snapshot|healthy" docs/api-contract/support-runtime.md docs/backup-recovery-runbook.md .sisyphus/plans/cloud-full-redeploy-115-191-36-90.md
  verification results: passed; the exact task-plan grep gate now surfaces the single-node/multi-instance/drill/health wording in every intended authority artifact, and the focused support/runtime grep proves release-health summaries are explicitly tied to recovery drill summary.json + log evidence rather than standing alone.
  success signal status: downstream deployment and recovery work can now start from one truthful boundary map — node-local `/health` proves one single-node bundle, recovery drills provide the db/auth/redis/oss/runtime evidence layer, and future multi-instance work is clearly marked as external-orchestrator territory instead of being implied by current systemd/nginx files.
  rollback note: if later work introduces cluster-aware drain automation, multi-instance websocket authority, or a new recovery evidence sink, update the .sisyphus/deploy comments, cloud redeploy plan, support runtime contract, runbook, and architecture scan together so deploy truth and recovery proof do not fork again.

- time: 2026-04-14T08:07:41+08:00
  mode: grow
  item id: M020-S04-T01
  files changed:
    - scripts/recovery_drill_baseline.py
    - backend/tests/unit/test_recovery_drill_baseline.py
    - docs/backup-recovery-runbook.md
    - docs/setup/backup-recovery-current-state.md
    - .gsd/DECISIONS.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Promoted the manual M018 recovery baseline into one executable repo-local drill inventory: scripts/recovery_drill_baseline.py now names the checked db/auth/redis/websocket/OSS/health drills plus the still-manual Redis restore, OSS export, and multi-instance drain boundaries, while the runbook/current-state docs point to that same inventory instead of carrying a parallel command list.
  verification commands:
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_recovery_drill_baseline.py -q
    - python3 scripts/recovery_drill_baseline.py check
    - rg -n "backup|restore|recovery|drill|auth|redis|oss|websocket" scripts docs/backup-recovery-runbook.md docs/setup/backup-recovery-current-state.md
    - lsp diagnostics scripts/recovery_drill_baseline.py
    - lsp diagnostics backend/tests/unit/test_recovery_drill_baseline.py
  verification results: passed; the fail-first recovery-drill unit suite finished 3/3 green after the new script landed, the inventory script validated all referenced authority paths and emitted the planned drill/manual-only split, the exact task-plan grep gate stayed green across scripts and docs, and diagnostics were clean on the touched Python files.
  success signal status: future S04 tasks no longer have to rediscover which recovery checks are real and which steps remain manual — one script now exposes the recovery drill authority line and the docs reuse it verbatim.
  rollback note: if later work changes the recovery command set, update scripts/recovery_drill_baseline.py, the focused unit test, and both recovery docs together; otherwise T02/T03 automation will drift from the documented drill baseline.

- time: 2026-04-13T23:07:58+0800
  mode: grow
  item id: M020-S02-T03
  files changed:
    - backend/src/admin/api/security_inventory.py
    - backend/src/common/monitoring/log_safety_inventory.py
    - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
    - .gsd/DECISIONS.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Codified the shipped admin/support redaction boundary into the durable inventory surfaces: security_inventory and log_safety_inventory now name the allowlist diagnostics, the backend-only detail classes, and the M021 quality-event prerequisite, while the architecture scan turns the same rule into a downstream observability contract instead of leaving it implicit in logger/API/UI code.
  verification commands:
    - rg -n "allowlist|redaction|trace_id|details|support|admin" backend/src/admin/api/security_inventory.py backend/src/common/monitoring/log_safety_inventory.py .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
    - backend/venv/bin/python -m py_compile backend/src/admin/api/security_inventory.py backend/src/common/monitoring/log_safety_inventory.py
    - lsp diagnostics backend/src/admin/api/security_inventory.py
    - lsp diagnostics backend/src/common/monitoring/log_safety_inventory.py
  verification results: passed; the exact task-plan grep gate now exposes the allowlist/redaction/support wording in all three authority artifacts, py_compile succeeded on the two touched Python inventories, and LSP diagnostics stayed clean.
  success signal status: future M021 quality/cost/failure event work no longer has to guess what support/admin may see — one code-owned inventory plus the architecture scan now say that only safe diagnostics like trace_id/error_code/phase/session_id/target_user_id may surface, while raw details/provider payloads/prompt/config secrets stay backend-only.
  rollback note: if later work expands admin/support observability fields, update the logger policy constants, both inventory modules, the architecture scan section 7.2.2, and the downstream M021 proof/docs together; otherwise runtime behavior and support guidance will drift again.

- time: 2026-04-13T18:04:04.426244+08:00
  mode: grow
  item id: M020-S01-T01
  files changed:
    - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - backend/src/common/auth/service.py
    - backend/src/sales_bot/websocket/router.py
    - backend/tests/unit/common/test_auth_transport_matrix.py
    - backend/tests/unit/test_sales_websocket_router.py
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Codified the real auth transport matrix for M020/S01 so downstream hardening stops guessing: common.auth now exposes one shipped HTTP/websocket/login-credential matrix, sales websocket exposes its compat policy explicitly, the architecture scan now distinguishes formal versus compatibility transports, and the focused proof bundle locks learner/admin cookie auth plus websocket query-token compatibility in place before T02 tightens anything.
  verification commands:
    - rg -n "AUTH_SHARED_PASSWORD|AUTH_USER_PASSWORDS_JSON|session cookie|resolve_websocket_token|token: str = Query|Authorization" backend/src/common/auth backend/src/sales_bot/websocket backend/src/presentation_coach/websocket web/src/lib/auth-handler.ts web/src/hooks/use-auth-protection.ts
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_auth_transport_matrix.py backend/tests/unit/test_sales_websocket_router.py backend/tests/unit/test_main_presentation_ws_runtime.py backend/tests/integration/test_auth_login_api.py -q
    - npm --prefix web test -- --run "src/hooks/use-practice-websocket.test.ts" "src/hooks/websocket/transport.test.ts" "src/lib/auth-handler.test.ts" "src/app/(auth)/login/page.test.tsx"
    - lsp diagnostics backend/src/common/auth/service.py
    - lsp diagnostics backend/src/sales_bot/websocket/router.py
    - lsp diagnostics backend/tests/unit/common/test_auth_transport_matrix.py
    - lsp diagnostics backend/tests/unit/test_sales_websocket_router.py
  verification results: passed; the grep gate exposes the intended auth surfaces, backend auth/websocket proofs finished 30/30 green, the focused frontend auth/websocket bundle finished 32/32 green, and diagnostics stayed clean on the touched backend files.
  success signal status: future M020 auth hardening work no longer has to rediscover whether bearer, cookie, query token, hashed_password, AUTH_USER_PASSWORDS_JSON, and AUTH_SHARED_PASSWORD are authoritative or compatibility-only — that matrix is now explicit in code, tests, and the architecture scan.
  rollback note: if T02 changes websocket resolution order, removes query-token compatibility, or retires shared-password fallbacks, update AUTH_TRANSPORT_MATRIX, SALES_WS_AUTH_POLICY, the architecture scan auth matrix section, and the focused backend/frontend proof bundle together so the documented authority line does not drift from runtime behavior.

- time: 2026-04-13T17:00:44.074256+08:00
  mode: grow
  item id: M019-S04-T03
  files changed:
    - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
    - .gsd/plans/GSD_PLAN_post-M018-next-wave.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Fixed the assembled release-gate handoff into durable repo-root rules instead of leaving it as local memory: the architecture scan now names the default downstream reuse bundle plus the router-backed doc-contract/live-route proof, the next-wave plan now tells M020-M022 to reuse that bundle unless they promote a new authority surface, and the admin home fake-stat mix stays explicitly parked as an M022-S03 truth-surface input rather than a release gate.
  verification commands:
    - rg -n "release gate|metrics|error reporting|doc contract|repo-root" .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md .gsd/plans/GSD_PLAN_post-M018-next-wave.md
    - rg -n "/practice/sessions|/admin/release-verification|/support/runtime" docs/api-contract backend/src/common/api/practice.py backend/src/admin/api/release_verification.py backend/src/support/api/runtime_status.py
    - rg -n "api.internal.health|api.analyticsOpen.getDashboard|2,543|84|42%|68%|75%|450 GB|legacy /api/v1/sessions|doc-contract drift gotcha" .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md .gsd/plans/GSD_PLAN_post-M018-next-wave.md .gsd/KNOWLEDGE.md web/src/app/admin/page.tsx backend/src/main.py
  verification results: passed; the exact task-plan grep gate stayed green, the new router-backed proof shows docs/api-contract still matches the live practice/release-verification/support-runtime route modules, and the known admin fake stats plus main.py inline route-summary drift are now explicit downstream facts instead of hidden release-surface ambiguity.
  success signal status: future M020-M022 work can now reuse one truthful release-gate contract without rediscovering it — workflow checks, observability sinks, router-backed doc-contract proof, legacy spec drift, and the admin home truthfulness gap are all written down in one place.
  rollback note: if later work promotes generated OpenAPI, adds new release authority routes, or truthifies the admin home metrics, update the workflow bundle, the router-backed proof, the architecture scan, the plan handoff, and the M022 carry-forward note together so the assembled release gate does not fork.

- time: 2026-04-13T13:05:41.478296+08:00
  mode: grow
  item id: M019-S04-T01
  files changed:
    - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Wrote the first assembled release-truth inventory for M019/S04 so downstream work stops assuming that workflow files, metrics helpers, frontend beacons, and legacy specs are all equally live: the architecture scan now separates backend NFR workflow plus router-backed docs/api-contract surfaces from disconnected frontend analytics beacons, helper-only Prometheus export code, and drifting openapi/api-spec artifacts, and the knowledge log records the relative /api/v1/analytics/* beacon trap for future agents.
  verification commands:
    - rg -n "analytics/error|metrics|openapi|api-contract|pip install -e|requirements.txt|package-lock" .github/workflows web/src/components/ErrorBoundary.tsx backend/src/common/monitoring/metrics.py api-spec.md specs/001-ai-practice-system/contracts/openapi.yaml docs/api-contract
    - rg -n "analytics/error|analytics/performance|analytics/custom|MetricsMiddleware|initialize_metrics\(|get_metrics\(|/metrics|add_middleware\(|next.config" web/src/components/ErrorBoundary.tsx web/src/lib/performance.ts backend/src/common/api/analytics.py backend/src/common/monitoring/metrics.py backend/src/main.py backend/src/common/middleware/auth.py web/next.config.ts
    - rg -n "/auth/wechat|/practice/sessions|/api/v1/admin/release-verification|/api/v1/support/runtime|POST /api/v1/sessions|POST /api/v1/practice/sessions|M019/S04 assembled release truth inventory|M019/S04 release-truth gotcha" specs/001-ai-practice-system/contracts/openapi.yaml api-spec.md docs/api-contract .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md .gsd/KNOWLEDGE.md
  verification results: passed; the task-plan grep gate stayed green, repo-root grep proof showed the frontend analytics beacons and Prometheus helper file still lack a live backend/rewrite sink, and the new assembled inventory plus knowledge entry are themselves grep-discoverable for downstream slices.
  success signal status: future S04 work no longer has to rediscover which release surfaces are real — backend NFR workflow and router-backed docs/api-contract are the current truth line, while frontend analytics beacons, backend metrics export, and legacy spec files are now explicitly marked as disconnected or drifting.
  rollback note: if T02 wires a real metrics endpoint, adds frontend error/performance collection routes, or promotes a checked spec into release authority, update the architecture inventory, the beacon gotcha entry, and the repo-root proof commands together so the assembled truth line stays honest.

- time: 2026-04-13T12:38:12.165299+08:00
  mode: grow
  item id: M019-S03-T02
  files changed:
    - web/src/lib/api/client.ts
    - web/src/lib/api/client-domains.ts
    - web/src/hooks/use-practice-websocket.ts
    - web/src/hooks/websocket/transport.ts
    - web/src/lib/api/client-domains.test.ts
    - web/src/hooks/websocket/transport.test.ts
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Split the runtime-facing frontend seams behind dedicated helpers without changing page contracts: client.ts now delegates auth/practice/session/agent/presentation/report domains to client-domains.ts, usePracticeWebSocket now uses websocket/transport.ts for URL/queue/backoff helpers, and the login/practice/report/replay page bundle stayed green on the outward api façade plus usePracticeWebSocket hook.
  verification commands:
    - npm --prefix web test -- --run src/lib/api/client-domains.test.ts src/hooks/websocket/transport.test.ts src/hooks/use-practice-websocket.test.ts
    - npm --prefix web test -- --run "src/app/(auth)/login/page.test.tsx" "src/app/(user)/practice/[sessionId]/page.test.tsx" "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx"
    - lsp diagnostics web/src/lib/api/client.ts
    - lsp diagnostics web/src/lib/api/client-domains.ts
    - lsp diagnostics web/src/hooks/use-practice-websocket.ts
    - lsp diagnostics web/src/hooks/websocket/transport.ts
  verification results: passed; the new internal seam tests finished 23/23 green, the exact slice verification bundle finished 50/50 green across login/practice/report/replay pages, and diagnostics stayed clean on the touched TypeScript files.
  success signal status: the runtime-facing frontend seam is no longer locked inside two monoliths — pages still import api/usePracticeWebSocket, while the split between shared request/error/trace core, domain builders, and transport helpers is now explicit and re-runnable.
  rollback note: if later S03 work moves more domains out of client.ts or changes websocket queue/backoff semantics, keep client-domains.ts, websocket/transport.ts, the focused seam tests, and the page-level verification bundle aligned together so the outward contracts remain stable.

- time: 2026-04-13T12:17:51.050075+08:00
  mode: grow
  item id: M019-S03-T01
  files changed:
    - web/src/lib/api/client.ts
    - web/src/hooks/use-practice-websocket.ts
    - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Codified the frontend seam inventory for M019/S03 so downstream work can split internals without reopening page contracts: client.ts now names its cross-cutting transport/auth/error/trace seam plus domain/high-fan-out surfaces, usePracticeWebSocket now records the retained transport/orchestration boundary, and the architecture/knowledge artifacts point future work at the right layer before editing.
  verification commands:
    - rg -n "export const api|normalizeApiErrorPayload|usePracticeWebSocket|MAX_RECONNECT_ATTEMPTS|message-handlers" web/src/lib/api web/src/hooks
    - lsp diagnostics web/src/lib/api/client.ts
    - lsp diagnostics web/src/hooks/use-practice-websocket.ts
    - rg -n "M019/S03|api façade|transport contract inventory|usePracticeWebSocket\(\)|websocket lifecycle|domain client seam inventory" .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md web/src/lib/api/client.ts web/src/hooks/use-practice-websocket.ts .gsd/KNOWLEDGE.md
  verification results: passed; the task-plan grep gate is green, the new seam inventory is grep-discoverable across code and GSD artifacts, and diagnostics stayed clean on the touched TypeScript authority files.
  success signal status: future S03 work no longer needs to rediscover whether a change belongs in domain client internals, the shared auth/error/trace seam, transport orchestration, or inbound message handlers before refactoring.
  rollback note: if later S03 work changes outward imports or page-level websocket wiring, update the client/hook inventory comments, architecture scan section 4.5, and the knowledge entry together so the documented seam still matches the live contract.

- time: 2026-04-13T12:12:08+0800
  mode: grow
  item id: M019-S02
  files changed:
    - .gsd/KNOWLEDGE.md
    - .gsd/milestones/M019/slices/S02/S02-SUMMARY.md
    - .gsd/milestones/M019/slices/S02/S02-UAT.md
    - .gsd/PROJECT.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Closed M019/S02 after fresh slice-level verification confirmed the practice backend now has named session/report application seams behind a stable route-facing compatibility bundle, while replay/history/admin still consume SessionEvidenceService as the canonical completed-session read model instead of drifting back into practice.py.
  verification commands:
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_practice_evidence_contract.py backend/tests/integration/test_session_lifecycle_api.py -x -q
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_practice_evidence_contract.py backend/tests/integration/test_practice_evidence_flow.py backend/tests/integration/test_session_lifecycle_api.py -x -q
    - rg -n "practice_session_service|practice_report_service|SessionEvidenceService" .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md backend/src/common/api/practice.py backend/tests/contract/test_practice_evidence_contract.py
    - lsp diagnostics backend/src/common/api/practice.py
    - lsp diagnostics backend/src/common/services/practice_service.py
    - lsp diagnostics backend/src/common/services/practice_session_service.py
    - lsp diagnostics backend/src/common/services/practice_report_service.py
    - lsp diagnostics backend/tests/contract/test_practice_evidence_contract.py
    - lsp diagnostics backend/tests/integration/test_practice_evidence_flow.py
    - lsp diagnostics backend/tests/integration/test_session_lifecycle_api.py
  verification results: passed; the planned contract/lifecycle gate finished 44/44 green, the broader contract+evidence-flow+lifecycle gate finished 50/50 green, the seam grep proof exposed the new landing zones in the architecture scan and contract file, and LSP diagnostics were clean on all touched Python authority files. Only the pre-existing pytest-cov no-data warning and Python 3.14 async teardown warning remained.
  success signal status: future backend work no longer has to infer whether to extend practice.py, the route-facing compatibility bundle, or the canonical completed-session read model — S02 now documents and proves that split directly.
  rollback note: if later work pushes create/lifecycle/report/audio logic back into common/api/practice.py or lets replay/history/admin rebuild completed-session truth outside SessionEvidenceService, update the service split, architecture scan, knowledge note, and focused verification bundle together before claiming the seam still holds.

- time: 2026-04-13T12:02:21.064291+08:00
  mode: grow
  item id: M019-S02-T03
  files changed:
    - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
    - backend/tests/contract/test_practice_evidence_contract.py
    - backend/tests/integration/test_practice_evidence_flow.py
    - .gsd/DECISIONS.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Locked the extracted practice seam with durable proof and downstream rules: the architecture scan now names the practice_session_service/practice_report_service split plus the S03/M021 consumption rule, and focused backend proof now shows report/history/admin/replay still share SessionEvidenceService as the canonical completed-session read model instead of rebuilding truth in practice.py.
  verification commands:
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_practice_evidence_contract.py backend/tests/integration/test_practice_evidence_flow.py -x -q
    - rg -n "practice_session_service|practice_report_service|SessionEvidenceService" .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md backend/src/common/api/practice.py backend/tests/contract/test_practice_evidence_contract.py
    - lsp diagnostics backend/tests/contract/test_practice_evidence_contract.py
    - lsp diagnostics backend/tests/integration/test_practice_evidence_flow.py
  verification results: passed; the broader touched-file backend gate finished 37/37 green, the exact task-plan grep proof now surfaces the new seam docs and contract assertions, and diagnostics stayed clean on the touched Python proof files while markdown remained outside LSP coverage.
  success signal status: downstream slices no longer need to infer whether to extend practice.py, the extracted application services, or the completed-session read model — the boundary is now written down and re-runnable from one focused backend proof.
  rollback note: if later work moves report/replay/history/admin away from SessionEvidenceService or adds new practice route seams, update the architecture scan guidance, the focused contract/integration proof, and D214 together so the documented downstream rule stays aligned with the live call graph.

- time: 2026-04-13T11:09:36+08:00
  mode: grow
  item id: M019-S01-T03
  files changed:
    - docs/backup-recovery-runbook.md
    - docs/setup/backup-recovery-current-state.md
    - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
    - .github/workflows/nfr-performance-check.yml
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Wrote the post-T02 startup/migration/bootstrap authority line back into the recovery runbook, setup baseline, architecture scan, and CI migration entrypoint so future work can tell when to run Alembic, when to run the explicit repair/bootstrap scripts, and when startup must not be trusted to patch schema.
  verification commands:
    - rg -n "alembic upgrade head|bootstrap|init_db|migration" docs/backup-recovery-runbook.md .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md .github/workflows
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_startup_or_bootstrap_authority.py backend/tests/unit/common/test_db_session_compatibility.py -q
  verification results: passed; the exact task-plan grep gate is green across the long-lived doc and CI surfaces, and the focused startup/bootstrap authority suite still finishes 4/4 green with only the pre-existing pytest-cov and sqlite teardown warnings.
  success signal status: future M019 slices can now start from one durable, repo-root-verifiable authority map — Alembic owns forward migration, repair_legacy_schema owns explicit legacy repair, bootstrap_auth_admin owns account bootstrap, and startup init_db is documented as bootstrap-only with non-dev fail-fast semantics.
  rollback note: if later work changes startup bootstrap scope or adds a new migration/bootstrap entrypoint, update the setup baseline, recovery runbook, architecture scan, CI step wording, and the focused authority proof together so the verification commands in runbook section 6.6 keep matching the shipped behavior.

- time: 2026-04-13T10:38:53+0800
  mode: grow
  item id: M019-S01-T01
  files changed:
    - backend/src/common/db/session.py
    - backend/src/main.py
    - backend/tests/unit/common/test_db_session_compatibility.py
    - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
    - .gsd/KNOWLEDGE.md
    - .gsd/DECISIONS.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Wrote the first M019 startup-schema authority inventory by making the startup bootstrap seam explicit in code/logs, documenting the real migration/repair/bootstrap entrypoints in the architecture scan, and adding a focused unit proof for the new authority map.
  verification commands:
    - rg -n "create_all|alembic|bootstrap|repair_legacy_schema|init_db" backend/src/common/db/session.py backend/src/main.py backend/alembic/versions scripts
    - rg -n "M019/S01 数据库演进 / bootstrap authority inventory|scripts/dev-up.sh 当前只是拉起 infra|M019/S01/T01 database authority inventory exposed" .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md .gsd/KNOWLEDGE.md
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_db_session_compatibility.py -q
    - lsp diagnostics backend/src/common/db/session.py
    - lsp diagnostics backend/src/main.py
    - lsp diagnostics backend/tests/unit/common/test_db_session_compatibility.py
  verification results: passed; the planned rg gate now exposes the explicit startup/migration/bootstrap mapping, the new analysis and knowledge inventory entries are grep-discoverable, the focused db-session suite finished 2/2 green, and diagnostics stayed clean on the touched Python authority files.
  success signal status: downstream M019 work can now start from one truthful authority split — Alembic owns forward schema evolution, init_db owns startup bootstrap plus the currently-shipped compatibility guards, repair_legacy_schema is a one-off legacy repair/stamping entrypoint, and bootstrap_auth_admin is a one-off auth bootstrap script.
  rollback note: if later M019 tasks remove or relocate startup compatibility repair, update the session/main authority constants/logs, the architecture scan inventory, the knowledge note, and the focused authority test together so the documented split keeps matching the live startup surface.

- time: 2026-04-12T08:10:30+08:00
  mode: grow
  item id: M018-S03
  files changed:
    - docs/setup/backup-recovery-current-state.md
    - docs/backup-recovery-runbook.md
    - .gsd/analysis/BACKUP_RECOVERY_BASELINE.md
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .gsd/PROJECT.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Closed M018/S03 by turning the repository’s backup/recovery ambiguity into one truthful operational baseline: a current-state inventory, a manual runbook, and an analysis pointer that only cite revalidated repo-local commands and paths while isolating drill/improvement work under explicit non-baseline follow-up.
  verification commands:
    - find docs scripts -maxdepth 2 -type f | sort | head -n 20
    - test -f docs/backup-recovery-runbook.md || test -f .gsd/analysis/BACKUP_RECOVERY_BASELINE.md
    - grep -n "备份\|恢复\|演练" docs/backup-recovery-runbook.md .gsd/analysis/BACKUP_RECOVERY_BASELINE.md
  verification results: passed; all three slice-plan gates were rerun fresh from repo root, the runbook and baseline artifacts remain present, and the final docs are grep-discoverable for backup/recovery/drill surfaces without claiming unshipped automation.
  success signal status: future agents can now start from one durable, repository-grounded recovery baseline instead of re-auditing startup scripts, config drift, and repair commands before every ops-related slice.
  rollback note: if later work ships real backup automation, OSS export tooling, or named operational ownership, update the current-state inventory, runbook baseline, analysis pointer, and follow-up split together before promoting any new step into the executable baseline.

- time: 2026-04-12T08:05:35+08:00
  mode: grow
  item id: M018-S03-T03
  files changed:
    - docs/backup-recovery-runbook.md
    - .gsd/analysis/BACKUP_RECOVERY_BASELINE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Tightened the backup/recovery runbook against live repository paths so every cited repo-local seam now points at a real file, `/health` verification is anchored to the shipped backend route, and all drill/improvement guidance is clearly isolated as non-baseline follow-up instead of blending into the executable recovery steps.
  verification commands:
    - python3 repo-local reference existence check for the runbook/baseline path set
    - grep -n "备份\|恢复\|演练" docs/backup-recovery-runbook.md .gsd/analysis/BACKUP_RECOVERY_BASELINE.md
  verification results: passed; all revalidated repo-local references exist in the current repository, and the exact task-plan grep gate stays green while the follow-up split remains visible in the final documents.
  success signal status: future agents can now open the runbook or baseline pointer and immediately distinguish executable backup/recovery reality from not-yet-shipped drill/improvement work without re-auditing the repository.
  rollback note: if later slices add real backup automation, Redis restore flow, or OSS export tooling, update the repo-local reference list and the Follow-up split first, then promote only the actually shipped steps into the executable baseline.

- time: 2026-04-12T08:04:34+08:00
  mode: grow
  item id: M018-S03-T02
  files changed:
    - docs/backup-recovery-runbook.md
    - .gsd/analysis/BACKUP_RECOVERY_BASELINE.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Turned the backup/recovery current-state audit into a truthful manual runbook with explicit backup cadence, restore order, verification steps, evidence locations, quarterly drill guidance, and clearly separated uncovered gaps.
  verification commands:
    - test -f docs/backup-recovery-runbook.md || test -f .gsd/analysis/BACKUP_RECOVERY_BASELINE.md
    - rg -n "当前最小备份频率|pg_dump|pg_restore|redis-cli|alembic upgrade head|bootstrap_auth_admin|/health|季度演练建议|未来改进" docs/backup-recovery-runbook.md .gsd/analysis/BACKUP_RECOVERY_BASELINE.md
    - rg -n "postgresql\+asyncpg|CHROMADB_PERSIST_DIR|CHROMA_PERSIST_DIRECTORY" docs/backup-recovery-runbook.md .gsd/KNOWLEDGE.md
  verification results: passed; the task-plan file-existence gate is green, grep proof shows the shipped runbook contains backup cadence, restore commands, verification, and drill/follow-up sections, and the knowledge log now records the asyncpg/libpq plus Chroma-path drift that could otherwise derail future restore work.
  success signal status: future agents can now open one runbook and one analysis pointer to understand the current manual backup/recovery baseline, including what is executable today and what is still an explicit gap.
  rollback note: if later slices add real backup automation or unify storage paths, update docs/backup-recovery-runbook.md, .gsd/analysis/BACKUP_RECOVERY_BASELINE.md, and the related knowledge entry together so the manual baseline does not drift from the shipped recovery surface.

- time: 2026-04-12T07:57:15+08:00
  mode: grow
  item id: M018-S03-T01
  files changed:
    - docs/setup/backup-recovery-current-state.md
    - scripts/README.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Wrote the first backup/recovery current-state baseline so the next slice task can build a truthful runbook from real repository evidence: local startup is script-driven, runtime data spans PostgreSQL/Redis/local document+Chroma paths plus OSS audio, alembic/legacy-schema/admin-bootstrap commands are the only real recovery-side entrypoints, and repo-native backup automation is still absent.
  verification commands:
    - find docs scripts -maxdepth 2 -type f | sort | head -n 20
    - rg -n "DATABASE_URL|alembic upgrade head|repair_legacy_schema|bootstrap_auth_admin|pg_dump|OSS" docs/setup/backup-recovery-current-state.md scripts/README.md
  verification results: passed; the exact task-plan inventory command stayed green, and the focused grep proof confirmed the new baseline captures the real recovery commands, path drift, storage surfaces, and explicit backup gaps.
  success signal status: future agents no longer need to reverse-engineer backup/recovery assumptions from startup scripts, env defaults, and scattered backend modules before writing the runbook.
  rollback note: if later tasks add real backup or restore automation, update docs/setup/backup-recovery-current-state.md and the linked scripts/README baseline together so the inventory keeps distinguishing shipped capabilities from still-missing ops work.

- time: 2026-04-12T06:24:20+08:00
  mode: grow
  item id: M018-S01-T01
  files changed:
    - backend/src/common/analytics/admin_analytics_service.py
    - backend/src/common/analytics/history_service.py
    - backend/src/common/conversation/session_evidence.py
    - backend/src/admin/api/training_records.py
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Wrote the first code-adjacent DB performance discovery baseline so future agents can start from one durable inventory instead of re-auditing query hotspots: admin analytics repeats full projection-window loads, history/progress replays large session/message windows without classical DB N+1, session-evidence is the per-session message fan-in seam, and admin training records still has a confirmed row-level agent/persona N+1.
  verification commands:
    - rg -n "select|join|order_by|group_by|SessionEvidence|leaderboard|analytics" backend/src/common/analytics backend/src/common/conversation backend/src/admin/api
    - lsp diagnostics backend/src/common/analytics/admin_analytics_service.py
    - lsp diagnostics backend/src/common/analytics/history_service.py
    - lsp diagnostics backend/src/common/conversation/session_evidence.py
    - lsp diagnostics backend/src/admin/api/training_records.py
  verification results: passed; the exact task-plan rg gate now surfaces the code-adjacent analytics/history/projection/admin inventory facts, and diagnostics stayed clean on the touched authority files.
  success signal status: downstream M018/S01 work no longer needs to reconstruct the first performance baseline from grep output alone — the live authority files now distinguish confirmed query-shape/N+1 facts from index ideas that still need real Postgres/runtime evidence.
  rollback note: if later slices prove or retire any of these candidates, update the code-adjacent inventory constants, the matching decision/knowledge entries, and the focused analytics proof together so the baseline does not drift from live runtime facts.

- time: 2026-04-12T06:09:00+08:00
  mode: grow
  item id: M017-S03
  files changed:
    - backend/src/presentation_coach/api/presentations.py
    - backend/tests/contract/test_presentations.py
    - backend/tests/integration/test_presentation_flow.py
    - backend/tests/integration/test_presentation_delete_permissions.py
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .gsd/PROJECT.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Closed M017/S03 by converting presentation upload/replace/delete concurrency suspicion into a code-adjacent discovery baseline: replace is now a proved concurrent-writer race, delete is a proved live-session route-guard gap, and upload-new remains inventory-only until new evidence appears.
  verification commands:
    - rg -n "replace|upload|delete|active-session|lock" backend/src/presentation_coach/api/presentations.py backend/tests/contract/test_presentations.py backend/tests/integration/test_presentation_flow.py
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_presentations.py backend/tests/integration/test_presentation_flow.py backend/tests/integration/test_presentation_delete_permissions.py -x -q
    - lsp diagnostics backend/src/presentation_coach/api/presentations.py
    - lsp diagnostics backend/tests/contract/test_presentations.py
    - lsp diagnostics backend/tests/integration/test_presentation_flow.py
    - lsp diagnostics backend/tests/integration/test_presentation_delete_permissions.py
  verification results: passed; the exact slice-plan rg inventory exposed the discovery constants plus focused replace/delete proof lines, the full S03 backend gate finished 11/11 green, and diagnostics stayed clean on the touched backend authority/test files.
  success signal status: future agents no longer need to re-audit presentation mutation risk from scratch — they can start from one canonical discovery artifact and one focused proof bundle that already distinguishes real replace/delete problems from unproved upload suspicion.
  rollback note: if later work implements replace serialization or delete-policy changes, update the code-adjacent discovery artifact, the focused contract assertion, and the replace/delete integration proofs together so the discovery baseline stays aligned with the live route behavior.

- time: 2026-04-12T05:34:02+08:00
  mode: grow
  item id: M017-S02-T02
  files changed:
    - web/src/hooks/use-practice-websocket.ts
    - web/src/hooks/use-practice-websocket.test.ts
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Tightened the practice websocket outbound orchestration seam so reconnect now starts a fresh transport epoch, queued outbound messages no longer leak across reconnect, and interrupt clears both queued outbound work and local backpressure/slow-state flags.
  verification commands:
    - npm --prefix web test -- --run src/hooks/use-practice-websocket.test.ts
    - npm --prefix web test -- --run "src/hooks/use-practice-websocket.test.ts" "src/hooks/use-practice-websocket.presentation-flow.test.ts" "src/app/(user)/practice/[sessionId]/page.test.tsx"
    - lsp diagnostics web/src/hooks/use-practice-websocket.ts
    - lsp diagnostics web/src/hooks/use-practice-websocket.test.ts
    - lsp diagnostics web/src/hooks/use-practice-websocket.presentation-flow.test.ts
  verification results: passed; the new red-first websocket proofs finished green (17/17 on the focused hook suite), the exact task-plan web verification gate finished 30/30 green across hook/presentation/page surfaces, and diagnostics stayed clean on the touched hook/test files.
  success signal status: future agents can now tell reconnect/backpressure/interrupt regressions apart from downstream runtime problems because stale outbound intent no longer replays after reconnect and interrupt immediately resets the discarded local backlog state.
  rollback note: if later S02/T03 work extracts helpers, preserve the fresh-transport-epoch rule and keep interrupt responsible for clearing queued outbound work plus local backpressure flags; otherwise reconnect can silently replay stale intent against a restored session.

- time: 2026-04-12T05:25:37+08:00
  mode: grow
  item id: M017-S02-T01
  files changed:
    - web/src/hooks/use-practice-websocket.ts
    - web/src/hooks/use-practice-websocket.test.ts
    - web/src/hooks/use-practice-websocket.presentation-flow.test.ts
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Codified the real practice-websocket seam instead of doing a size-driven refactor: the hook now documents that it owns transport lifecycle, binary negotiation, outbound backpressure buffering/flush, and interrupt pre-cleanup, while focused tests prove runtime state changes still come back from inbound status/reconnected/interrupted/backpressure messages.
  verification commands:
    - rg -n "reconnect|backpressure|interrupt|binary" web/src/hooks/use-practice-websocket.ts web/src/hooks/use-practice-websocket*.test.ts
    - npm --prefix web test -- --run "src/hooks/use-practice-websocket.test.ts" "src/hooks/use-practice-websocket.presentation-flow.test.ts"
    - lsp diagnostics web/src/hooks/use-practice-websocket.ts
    - lsp diagnostics web/src/hooks/use-practice-websocket.test.ts
    - lsp diagnostics web/src/hooks/use-practice-websocket.presentation-flow.test.ts
  verification results: passed; the exact task-plan rg inventory now surfaces the explicit boundary map plus focused reconnect/backpressure/interrupt/binary proofs, the impacted websocket hook suites finished 18/18 green, and diagnostics stayed clean on the touched hook/test files.
  success signal status: future agents can now start S02/T02 from one explicit seam — outbound orchestration pressure lives in use-practice-websocket, while inbound runtime truth continues to flow through websocket/message-handlers; even presentation control:start is now proved to require backend status before sessionStatus flips to in_progress.
  rollback note: if later S02 work extracts helpers from use-practice-websocket, keep reconnect budget, binary negotiation, pending-outbound flush, backpressure buffer ownership, and interrupt pre-cleanup on the same coordinator seam; do not split start/pause/resume or interrupt state transitions into local optimistic state that bypasses backend status/reconnected confirmation.

- time: 2026-04-12T04:27:39+08:00
  mode: grow
  item id: M016-S03-T02
  files changed:
    - backend/src/common/monitoring/logger.py
    - backend/src/common/auth/api.py
    - backend/src/common/auth/service.py
    - backend/src/admin/api/admin.py
    - backend/src/admin/api/analytics.py
    - backend/src/admin/api/release_verification.py
    - backend/src/admin/api/system_logs.py
    - backend/src/admin/api/training_records.py
    - backend/src/admin/api/security_inventory.py
    - backend/src/common/monitoring/log_safety_inventory.py
    - backend/tests/integration/test_admin_users_api.py
    - backend/tests/unit/admin/test_admin_users_api_models.py
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Explicitly closed the M016/S03 fix-first admin and logging seams by moving five legacy admin router modules onto get_current_admin_user, centralizing token/password/cookie/email redaction in the shared structured logger, switching auth logging to structured masked fields, and refreshing the code-owned security inventories to reflect the now-green baseline.
  verification commands:
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_admin_users_api.py -k "admin_router_modules_require_admin_even_without_main_router_guard" -q
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/admin/test_admin_users_api_models.py -k "sanitize_log_kwargs" -q
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_admin_users_api.py backend/tests/unit/admin/test_admin_users_api_models.py -x -q
    - lsp diagnostics backend/src/common/monitoring/logger.py
    - lsp diagnostics backend/src/common/auth/api.py
    - lsp diagnostics backend/src/common/auth/service.py
    - lsp diagnostics backend/src/admin/api/admin.py
    - lsp diagnostics backend/src/admin/api/analytics.py
    - lsp diagnostics backend/src/admin/api/release_verification.py
    - lsp diagnostics backend/src/admin/api/system_logs.py
    - lsp diagnostics backend/src/admin/api/training_records.py
    - lsp diagnostics backend/src/admin/api/security_inventory.py
    - lsp diagnostics backend/src/common/monitoring/log_safety_inventory.py
    - lsp diagnostics backend/tests/integration/test_admin_users_api.py
    - lsp diagnostics backend/tests/unit/admin/test_admin_users_api_models.py
  verification results: passed; the isolated-router RBAC regression proof finished 5/5 green, the shared logger redaction unit proof finished 2/2 green, the exact task-plan pytest gate finished 33/33 green, and diagnostics stayed clean on the touched backend/runtime/test files.
  success signal status: future agents can now trust the admin security baseline from the code itself — the fix-first routers stay admin-only even when mounted without main.py wrapper dependencies, shared logging strips token/password/cookie/email fields before emission, auth logs preserve observability with masked structured fields, and the code-owned inventories no longer advertise unresolved fix-first surfaces.
  rollback note: if later work changes admin mounting or adds new structured log sinks, keep the router-local get_current_admin_user declarations, logger sanitizer, inventory files, and the isolated-router/log-redaction tests aligned together; otherwise main.py can hide a module-level RBAC gap and new sinks can bypass redaction by drift.

- time: 2026-04-12T04:14:30+08:00
  mode: grow
  item id: M016-S03-T01
  files changed:
    - backend/src/admin/api/security_inventory.py
    - backend/src/common/monitoring/log_safety_inventory.py
    - backend/src/common/auth/service.py
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Codified the M016/S03 security baseline into code-owned inventories so downstream work can stop re-scanning the backend: one admin permission matrix now names the five legacy /admin route families still gated only by generic authentication, one sensitive-log inventory names the shared logger/auth sinks most likely to leak token/password/cookie/email fields, and the auth service now points future agents at those baselines instead of the stale string-detail drift note.
  verification commands:
    - rg -n "token|password|cookie|email" backend/src/admin backend/src/common/monitoring backend/src/common/auth
    - python3 -m py_compile backend/src/admin/api/security_inventory.py backend/src/common/monitoring/log_safety_inventory.py backend/src/common/auth/service.py
    - backend/venv/bin/python -c 'import sys; sys.path.insert(0, "backend/src"); from admin.api.security_inventory import FIX_FIRST_ADMIN_ROUTE_FAMILIES; from common.monitoring.log_safety_inventory import FIX_FIRST_SENSITIVE_LOG_SURFACES; print(len(FIX_FIRST_ADMIN_ROUTE_FAMILIES), len(FIX_FIRST_SENSITIVE_LOG_SURFACES))'
    - lsp diagnostics backend/src/admin/api/security_inventory.py
    - lsp diagnostics backend/src/common/monitoring/log_safety_inventory.py
    - lsp diagnostics backend/src/common/auth/service.py
  verification results: passed; the task-plan grep gate finished cleanly with the new code-owned inventory surfaces present, py_compile succeeded on the new inventory/auth files, the backend venv imported the fix-first route/log lists successfully (5 route families, 4 log surfaces), and fresh diagnostics stayed clean on the touched Python files.
  success signal status: future S03 work now has one durable target list instead of a broad backend audit — fix-first RBAC work is narrowed to the five legacy get_current_user admin route families, and fix-first redaction work is narrowed to the shared logger/latency sinks plus auth logout/failure logging.
  rollback note: if later S03 tasks change which route families or sinks are first priority, update backend/src/admin/api/security_inventory.py, backend/src/common/monitoring/log_safety_inventory.py, the auth-service baseline note, and D194 together so the code-owned inventory does not drift from the actual repair plan.

- time: 2026-04-12T04:03:30+08:00
  mode: grow
  item id: M016-S02
  files changed:
    - backend/src/prompt_templates/api/routes.py
    - backend/src/presentation_coach/api/presentations.py
    - backend/src/common/auth/service.py
    - backend/src/common/api/practice.py
    - backend/tests/conftest.py
    - backend/tests/contract/test_presentations.py
    - web/src/lib/api/client.ts
    - web/src/lib/api/client.auth.test.ts
    - .gsd/DECISIONS.md
    - .gsd/PROJECT.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Closed M016/S02 after fresh slice-level verification confirmed the audited prompt-template, presentation, and auth dependency surfaces now share one stable error-contract seam, and the frontend API client keeps all of those failures on one ApiRequestError normalization path without page-local guessing.
  verification commands:
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_presentations.py backend/tests/contract/test_practice_evidence_contract.py backend/tests/integration/test_presentation_flow.py -x -q
    - npm --prefix web test -- --run src/lib/api/client.auth.test.ts
    - lsp diagnostics backend/src/prompt_templates/api/routes.py
    - lsp diagnostics backend/src/presentation_coach/api/presentations.py
    - lsp diagnostics backend/src/common/auth/service.py
    - lsp diagnostics backend/src/common/api/practice.py
    - lsp diagnostics backend/tests/conftest.py
    - lsp diagnostics backend/tests/contract/test_presentations.py
    - lsp diagnostics web/src/lib/api/client.ts
    - lsp diagnostics web/src/lib/api/client.auth.test.ts
  verification results: passed; the exact slice-plan backend gate finished 33/33 green, the focused frontend API-client auth suite finished 9/9 green, and diagnostics stayed clean on the touched backend/frontend authority files.
  success signal status: M016/S02 now gives downstream work one durable security/error-contract baseline — route-local audited 4xx failures expose top-level structured envelopes, dependency role/admin guards expose structured detail payloads, and frontend callers normalize both shapes through ApiRequestError.
  rollback note: if later admin-security work changes exception handling, keep `error_response(...)`/`build_server_error(...)`, `_raise_auth_http_error(...)`, `backend/tests/contract/test_presentations.py`, and `web/src/lib/api/client.auth.test.ts` aligned together; otherwise protected-route and not-found failures will drift back into mixed string-vs-envelope parsing.

- time: 2026-04-12T03:58:20+08:00
  mode: grow
  item id: M016-S02-T03
  files changed:
    - backend/src/common/auth/service.py
    - backend/tests/contract/test_presentations.py
    - web/src/lib/api/client.auth.test.ts
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Added cross-end proof for the unified API error seam by locking presentation/admin role-guard responses to structured auth detail payloads and proving the frontend API client still normalizes those dependency failures through ApiRequestError without page-local parsing.
  verification commands:
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_presentations.py -k "structured_detail_payload" -q
    - npm --prefix web test -- --run src/lib/api/client.auth.test.ts
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_presentations.py backend/tests/contract/test_practice_evidence_contract.py backend/tests/integration/test_presentation_flow.py -x -q
    - lsp diagnostics backend/src/common/auth/service.py
    - lsp diagnostics backend/tests/contract/test_presentations.py
    - lsp diagnostics web/src/lib/api/client.auth.test.ts
  verification results: passed; the new role-guard backend proof finished green, the focused frontend API-client auth suite finished 9/9 green including dependency-detail normalization, the slice verification command finished 33/33 green, and diagnostics stayed clean on the touched auth/test files.
  success signal status: backend dependency guards no longer leak raw-string 403 detail on presentation/admin routes, and frontend callers keep one stable ApiRequestError seam across dependency detail, route-local envelopes, and validation arrays.
  rollback note: if later auth or middleware work changes dependency-failure behavior, keep `get_current_user`/`get_current_admin_user`/`require_role(...)`, `backend/tests/contract/test_presentations.py`, and `web/src/lib/api/client.auth.test.ts` aligned together; otherwise admin/protected-route failures will silently fall back to generic HTTP_403 guessing.

- time: 2026-04-12T03:49:54+0800
  mode: grow
  item id: M016-S02-T02
  files changed:
    - backend/src/prompt_templates/api/routes.py
    - backend/src/presentation_coach/api/presentations.py
    - backend/src/common/auth/service.py
    - web/src/lib/api/client.ts
    - backend/tests/integration/test_prompt_templates_api_rbac.py
    - backend/tests/contract/test_presentations.py
    - backend/tests/integration/test_presentation_delete_permissions.py
    - web/src/lib/api/client.auth.test.ts
    - backend/tests/conftest.py
    - backend/src/common/api/practice.py
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Collapsed the audited backend/frontend error seam onto one stable contract by returning top-level error envelopes from prompt-template and presentation 4xx routes, structuring auth dependency failures, and teaching apiFetch plus segment-audio fetches to normalize route/detail/validation payloads into ApiRequestError.
  verification commands:
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_prompt_templates_api_rbac.py -q
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_presentations.py backend/tests/integration/test_presentation_delete_permissions.py -q
    - npm --prefix web test -- --run src/lib/api/client.auth.test.ts
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_practice_evidence_contract.py -k "kb_lock_chain_failures" -q
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_presentations.py backend/tests/contract/test_practice_evidence_contract.py backend/tests/integration/test_presentation_flow.py -x -q
    - lsp diagnostics backend/src/prompt_templates/api/routes.py
    - lsp diagnostics backend/src/presentation_coach/api/presentations.py
    - lsp diagnostics backend/src/common/auth/service.py
    - lsp diagnostics web/src/lib/api/client.ts
    - lsp diagnostics backend/src/common/api/practice.py
  verification results: passed; focused prompt-template/presentation/frontend client proof went green, the pre-existing knowledge-check NameError blocker in common/api/practice.py was fixed and re-proved, the slice verification command finished 31/31 green, and diagnostics stayed clean on the touched authority files.
  success signal status: frontend callers now get one stable ApiRequestError seam across top-level Result envelopes, auth dependency detail payloads, and FastAPI validation arrays, while audited prompt-template/presentation routes expose stable top-level error codes plus trace ids for support triage.
  rollback note: if later work changes the shared error helper or global HTTPException policy, keep route-local 4xx response envelopes, auth dependency structured detail, frontend normalization, and the focused contract tests aligned together; otherwise clients will fall back to stringified-dict guessing again.

- time: 2026-04-12T03:30:08+08:00
  mode: grow
  item id: M016-S02-T01
  files changed:
    - backend/src/prompt_templates/api/routes.py
    - backend/src/presentation_coach/api/presentations.py
    - backend/src/common/auth/service.py
    - web/src/lib/api/client.ts
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Codified the high-noise API error-contract drift map directly beside the live prompt-template, presentation, auth, and frontend client seams so downstream work can collapse the contract without re-inventorying the same surfaces.
  verification commands:
    - rg -n "HTTPException|except Exception" backend/src/prompt_templates backend/src/presentation_coach backend/src/common/auth
    - lsp diagnostics backend/src/prompt_templates/api/routes.py
    - lsp diagnostics backend/src/presentation_coach/api/presentations.py
    - lsp diagnostics backend/src/common/auth/service.py
    - lsp diagnostics web/src/lib/api/client.ts
  verification results: passed; the planned rg inventory still shows the intended drift surface, and fresh LSP diagnostics were clean on the four touched authority files after the seam writeback.
  success signal status: future M016/S02 work now has one explicit collapse map — prompt templates are the closest reusable backend seam, while presentations plain-string 403/404 branches, auth dependency HTTPExceptions, and the segment-audio client parser are the only hotspots that still leak error-shape drift.
  rollback note: if T02 chooses a different shared envelope, update the code-adjacent inventory notes, D191, and the knowledge entry together so the documented drift map still matches the real collapse target.

- time: 2026-04-12T03:19:18+08:00
  mode: grow
  item id: M016-S01-T03
  files changed:
    - backend/tests/integration/test_auth_login_api.py
    - backend/tests/integration/test_password_reset_api.py
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Expanded the focused auth recovery proof so the repo-root auth gate now covers reset success, expiry, reuse, same-IP rate limiting, and request-path DDL absence, while the dedicated reset suite also proves superseded-token rejection against the live lifecycle contract.
  verification commands:
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py -x -q
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_password_reset_api.py -x -q
    - lsp diagnostics backend/tests/integration/test_auth_login_api.py
    - lsp diagnostics backend/tests/integration/test_password_reset_api.py
  verification results: passed; the repo-root auth gate finished 17/17 green, the dedicated password-reset suite finished 8/8 green, and diagnostics were clean on both focused proof files.
  success signal status: future agents can now prove forgot/reset health from focused backend tests alone — including successful reset handoff into managed credentials, expired/reused/superseded token rejection, rate limiting, and the absence of request-path auth DDL.
  rollback note: if later auth-recovery work changes handler ownership or token lifecycle semantics, update both focused proof files together so the repo-root auth gate and the dedicated reset lifecycle suite keep describing the same contract.

- time: 2026-04-12T03:08:13+08:00
  mode: grow
  item id: M016-S01-T01
  files changed:
    - backend/src/common/auth/api.py
    - backend/src/common/auth/service.py
    - backend/src/common/db/models.py
    - .gsd/KNOWLEDGE.md
    - .gsd/DECISIONS.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Documented the narrow password-reset formalization boundary directly in the auth/model files and knowledge log so downstream work can target PasswordResetService + PasswordResetToken + Alembic 026/027 while keeping the current hashed_password-first login fallback stable.
  verification commands:
    - rg -n "CREATE TABLE IF NOT EXISTS|reset|forgot|token|email" backend/src/common/auth backend/src/common/db/models.py
    - lsp diagnostics backend/src/common/auth/api.py
    - lsp diagnostics backend/src/common/auth/service.py
    - lsp diagnostics backend/src/common/db/models.py
  verification results: passed; the planned rg inventory confirmed forgot/reset still lands on the existing auth/model seam without any auth-local CREATE TABLE path, and fresh LSP diagnostics were clean on backend/src/common/auth/api.py, backend/src/common/auth/service.py, and backend/src/common/db/models.py after the seam writeback.
  success signal status: M016/S01/T01 now has one explicit formalization boundary: future work can land on PasswordResetService + PasswordResetToken + Alembic 026/027 while preserving the hashed_password-first login compatibility rule instead of reopening JWT/session helpers or mistaking global startup create_all bootstrap for request-path auth DDL.
  rollback note: If later M016 work changes the auth recovery boundary, update the code-level seam notes in auth/api.py, auth/service.py, db/models.py, and the matching knowledge/decision entries together so migration authority and login fallback rules do not drift apart.


- time: 2026-04-12T02:52:25+08:00
  mode: grow
  item id: M015-S03
  files changed:
    - .gsd/DECISIONS.md
    - .gsd/milestones/M015/slices/S03/S03-SUMMARY.md
    - .gsd/milestones/M015/slices/S03/S03-UAT.md
    - .gsd/PROJECT.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Closed M015/S03 after fresh slice-level verification confirmed learner dashboard/auth/practice routes now share explicit route-level fallback shells, the durable learner route-error seam still reports correctly, and remaining responsive/timezone work is preserved as a focused deferred baseline instead of reopening shell scope.
  verification commands:
    - find web/src/app -type f \( -name 'error.tsx' -o -name 'loading.tsx' \) | sort && npm --prefix web test -- --run "src/app/(dashboard)/history/page.test.tsx" "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx"
    - npm --prefix web test -- --run "src/app/learner-shell-baseline.test.ts" "src/components/error-reporting.test.tsx" "src/app/(user)/practice/[sessionId]/error.test.tsx"
    - lsp diagnostics web/src/app/learner-shell-baseline.test.ts
  verification results: passed; the route-file inventory plus learner history/report/replay gate finished 41/41 green, the learner-shell baseline + route-error observability gate finished 8/8 green, and diagnostics were clean on the focused learner proof file.
  success signal status: M015/S03 is now closed on one durable learner-shell contract — group-level dashboard/auth loaders, live-practice fallback coverage, shared durable route-error reporting, and one proof file that future agents can rerun directly.
  rollback note: if later work changes learner route families or resolves the deferred responsive/timezone baseline, update web/src/app/learner-shell-baseline.test.ts, the matching knowledge entries, and this slice summary together so shell scope and proof do not drift.

- time: 2026-04-12T02:47:30+08:00
  mode: grow
  item id: M015-S03-T03
  files changed:
    - web/src/app/learner-shell-baseline.test.ts
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Added one focused learner-shell baseline proof that scopes route-shell closure to learner-core routes, locks the shared a11y seam, and records the remaining responsive/timezone work as explicit deferred source facts instead of reopening shell scope.
  verification commands:
    - npm --prefix web test -- --run "src/app/learner-shell-baseline.test.ts"
    - find web/src/app -type f \( -name 'error.tsx' -o -name 'loading.tsx' \) | sort && npm --prefix web test -- --run "src/app/learner-shell-baseline.test.ts" "src/app/(dashboard)/history/page.test.tsx" "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx"
    - lsp diagnostics web/src/app/learner-shell-baseline.test.ts
  verification results: passed; the new focused baseline proof finished 3/3 green, the slice inventory + learner regression gate finished 44/44 green, and diagnostics were clean on the new proof file.
  success signal status: learner fallback closure, route-shell a11y baseline, and deferred responsive/timezone facts are now all encoded in one focused learner test that future agents can rerun directly.
  rollback note: if later learner-shell work adds/removes route fallbacks or resolves the deferred responsive/timezone baseline, update web/src/app/learner-shell-baseline.test.ts and the matching knowledge entry together so the proof keeps matching the real scope.

- time: 2026-04-12T02:40:55+08:00
  mode: grow
  item id: M015-S03-T02
  files changed:
    - web/src/components/learner/learner-route-loading-state.tsx
    - web/src/components/learner/learner-route-loading-state.test.tsx
    - web/src/app/(auth)/loading.tsx
    - web/src/app/(auth)/error.tsx
    - web/src/app/(auth)/route-shells.test.tsx
    - web/src/app/(dashboard)/loading.tsx
    - web/src/app/(user)/practice/[sessionId]/loading.tsx
    - web/src/components/dashboard-skeleton.tsx
    - web/src/app/(user)/practice/[sessionId]/error.test.tsx
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Added shared learner route-level loading/error shells across dashboard, auth, and live practice, plus a narrow-screen-safe dashboard skeleton baseline, so learner-core routes now fail or wait on explicit fallback surfaces instead of blanking.
  verification commands:
    - find web/src/app -type f \( -name 'error.tsx' -o -name 'loading.tsx' \) | sort
    - npm --prefix web test -- --run "src/app/(auth)/route-shells.test.tsx" "src/components/learner/learner-route-loading-state.test.tsx"
    - npm --prefix web test -- --run "src/app/(dashboard)/history/page.test.tsx" "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx"
    - npm --prefix web test -- --run "src/components/error-reporting.test.tsx" "src/app/(user)/practice/[sessionId]/error.test.tsx"
  verification results: passed; the fallback inventory now shows the new dashboard/auth/practice route shells, the focused auth/loading seam tests finished 3/3 green, the task-plan learner regression command finished 41/41 green, and the route-error observability proof finished 5/5 green.
  success signal status: learner dashboard/auth/live-practice entry routes now have durable route-level fallback surfaces with accessible status semantics, and shared dashboard skeletons no longer force the previous edge-aligned header layout on narrow screens.
  rollback note: if later S03 work adds more learner page-local loaders, keep the default baseline on `(dashboard)/loading`, `(auth)/loading`, and `practice/[sessionId]/loading`; only introduce page-specific loaders when the route needs richer shape than the shared learner loading state.

- time: 2026-04-12T02:32:30+08:00
  mode: grow
  item id: M015-S03-T01
  files changed:
    - web/src/app/(dashboard)/history/loading.tsx
    - web/src/app/(user)/practice/[sessionId]/report/loading.tsx
    - web/src/app/(user)/practice/[sessionId]/replay/loading.tsx
    - web/src/app/(auth)/login/page.tsx
    - web/src/app/(auth)/forgot-password/page.tsx
    - web/src/app/(auth)/reset-password/page.tsx
    - web/src/app/(auth)/login/page.test.tsx
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Established the learner fallback/baseline matrix for M015/S03, recorded the real learner-core gap list in T01-RESEARCH, and shipped the low-risk a11y subset now: existing loading shells announce status and auth forms/errors expose explicit labels/alerts.
  verification commands:
    - find web/src/app -type f \( -name 'error.tsx' -o -name 'loading.tsx' \) | sort
    - npm --prefix web test -- --run "src/app/(auth)/login/page.test.tsx" "src/app/(auth)/forgot-password/login-recovery.test.tsx" "src/app/(auth)/reset-password/login-reset.test.tsx"
    - lsp diagnostics web/src/app/(auth)/login/page.tsx
    - lsp diagnostics web/src/app/(auth)/forgot-password/page.tsx
    - lsp diagnostics web/src/app/(auth)/reset-password/page.tsx
    - lsp diagnostics web/src/app/(dashboard)/history/loading.tsx
    - lsp diagnostics web/src/app/(auth)/login/page.test.tsx
  verification results: passed; the route-file scan confirmed the current fallback inventory used in the matrix, the focused auth suite finished 9/9 green after the label/alert updates, and diagnostics were clean on the touched auth/history files.
  success signal status: downstream S03 work now has one durable learner-core route matrix, one documented deferred responsive/timezone boundary, and one small shipped a11y baseline so T02 can focus on real fallback gaps instead of re-triaging scope.
  rollback note: if later S03 tasks add or remove learner-core routes, update the T01 research matrix and the learner-core scope rule in .gsd/KNOWLEDGE.md together; do not let `/support/runtime` or other role-gated dashboard pages drift into learner fallback closure by accident.

- time: 2026-04-12T02:17:45+08:00
  mode: grow
  item id: M015-S02
  files changed:
    - web/src/lib/auth-handler.ts
    - web/src/components/providers/app-providers.tsx
    - web/src/components/layout/dashboard-shell.tsx
    - web/src/components/layout/admin-shell.tsx
    - web/src/app/admin/records/page.tsx
    - web/src/app/admin/rag-profiles/page.tsx
    - web/src/app/admin/personas/[id]/page.tsx
    - web/src/lib/auth-handler.test.ts
    - web/src/app/admin/records/page.test.tsx
    - web/src/app/admin/rag-profiles/page.test.tsx
    - web/src/app/admin/personas/[id]/page.test.tsx
    - .gsd/PROJECT.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Closed M015/S02 after fresh slice-level verification confirmed native dialog and hard browser navigation are removed from the planned admin/learner business flows, with auth redirects, destructive confirms, and validation/save feedback all routed through shared authHandler/router/dialog/toast seams.
  verification commands:
    - rg -n "\b(alert|confirm)\s*\(|window\.location(\.assign|\.href)" web/src
    - node allowlist interruptive-ui grep check across web/src
    - npm --prefix web test -- --run "src/app/admin/personas/[id]/page.test.tsx" "src/app/(auth)/login/page.test.tsx"
    - npm --prefix web test -- --run src/app/admin/records/page.test.tsx src/lib/auth-handler.test.ts src/components/layout/dashboard-shell.test.tsx src/components/layout/admin-shell.test.tsx src/app/admin/rag-profiles/page.test.tsx
    - lsp diagnostics web/src/lib/auth-handler.ts
    - lsp diagnostics web/src/components/providers/app-providers.tsx
    - lsp diagnostics web/src/components/layout/dashboard-shell.tsx
    - lsp diagnostics web/src/components/layout/admin-shell.tsx
    - lsp diagnostics web/src/app/admin/records/page.tsx
    - lsp diagnostics web/src/app/admin/rag-profiles/page.tsx
    - lsp diagnostics web/src/app/admin/personas/*/page.tsx
  verification results: passed; the raw grep now reports only documented exceptions in ErrorBoundary/performance/admin-error, the stricter allowlist check confirmed no undisclosed native-dialog or hard-navigation hits remain, the focused persona/login suite finished 7/7 green, the expanded seam suite finished 14/14 green, and diagnostics were clean on the touched auth/router/admin authority files.
  success signal status: downstream learner-shell work now inherits one router-aware auth redirect seam, one reusable ConfirmDialog+toast destructive-action pattern, and one strict grep/test boundary for preventing regressions in native dialogs or hard redirects.
  rollback note: if a later slice changes the remaining exception set or adds new auth/destructive flows, update interruptiveUiInventory, its focused tests, and the grep allowlist together instead of letting page-local alert/confirm/location usage drift back into business code.

- time: 2026-04-12T01:36:20+08:00
  mode: grow
  item id: M015-S01
  files changed:
    - web/src/lib/debug.ts
    - web/src/lib/console-boundary.test.ts
    - web/src/components/ErrorBoundary.tsx
    - web/src/components/learner/learner-route-error-state.tsx
    - web/src/app/(dashboard)/error.tsx
    - web/src/app/admin/error.tsx
    - .gsd/PROJECT.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Closed M015/S01 after fresh slice-level verification confirmed the shared frontend debug seam, durable route-error reporting, and raw-console exception boundary are all in place for downstream dialog/router and learner-shell cleanup work.
  verification commands:
    - npm --prefix web test -- --run src/lib/console-boundary.test.ts src/lib/debug.test.ts src/components/error-reporting.test.tsx "src/app/(user)/practice/[sessionId]/page.test.tsx" "src/hooks/use-practice-websocket.test.ts"
    - rg -n "console\.(log|error|warn|info)" web/src
    - lsp diagnostics web/src/lib/debug.ts
    - lsp diagnostics web/src/components/ErrorBoundary.tsx
    - lsp diagnostics web/src/components/learner/learner-route-error-state.tsx
    - lsp diagnostics web/src/app/(dashboard)/error.tsx
    - lsp diagnostics web/src/app/admin/error.tsx
    - lsp diagnostics web/src/lib/console-boundary.test.ts
  verification results: passed; the focused frontend seam gate finished 27/27 green, the repo-root raw-console grep returned only web/src/lib/debug.ts plus web/src/instrumentation*.ts, and fresh diagnostics were clean on the shared seam, route-error surfaces, and boundary proof file.
  success signal status: frontend business pages, hooks, and route-error surfaces now share one explicit debug/observability seam, so later M015 slices can distinguish intentional instrumentation exceptions from product/runtime logging with one test and one grep.
  rollback note: if a later slice needs to change the raw-console exception set, update the inventory in web/src/lib/debug.ts, the allowlist in web/src/lib/console-boundary.test.ts, and the matching decision/knowledge entries together rather than letting page-local console usage redefine policy by drift.

- time: 2026-04-12T01:30:30+08:00
  mode: grow
  item id: M015-S01-T03
  files changed:
    - web/src/lib/console-boundary.test.ts
    - web/src/app/(dashboard)/agents/[agentId]/page.tsx
    - web/src/app/(dashboard)/training/presentation/page.tsx
    - web/src/app/(dashboard)/training/sales/page.tsx
    - web/src/app/(user)/practice/[sessionId]/page.tsx
    - web/src/app/admin/**/*.tsx
    - web/src/app/test-mic/page.tsx
    - web/src/components/admin/knowledge-answer/tabs/intent-rules-tab.tsx
    - web/src/components/highlights/HighlightCard.tsx
    - web/src/components/highlights/HighlightDetailModal.tsx
    - web/src/components/training/ScenarioList.tsx
    - web/src/components/ui/audio-visualizer.tsx
    - web/src/hooks/use-audio-recorder.ts
    - web/src/hooks/use-debounce-request.ts
    - web/src/hooks/use-practice-websocket.ts
    - web/src/hooks/use-streaming-audio-player.ts
    - web/src/hooks/websocket/message-handlers.ts
    - web/src/hooks/websocket/use-audio-playback.ts
    - web/src/lib/auth-handler.ts
    - web/src/lib/performance.ts
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
  summary: Migrated the remaining business-page, hook, and developer/support raw-console callers onto the shared debug seam and added a filesystem-backed console-boundary test that fails whenever raw console leaks outside instrumentation/bootstrap and web/src/lib/debug.ts.
  verification commands:
    - npm --prefix web test -- --run src/lib/console-boundary.test.ts src/lib/debug.test.ts src/components/error-reporting.test.tsx "src/app/(user)/practice/[sessionId]/page.test.tsx" "src/hooks/use-practice-websocket.test.ts"
    - rg -n "console\.(log|error|warn|info)" web/src
    - ./web/node_modules/.bin/tsc --noEmit -p web/tsconfig.json
    - lsp diagnostics web/src/app/(dashboard)/**/*.tsx
    - lsp diagnostics web/src/app/admin/**/*.tsx
    - lsp diagnostics web/src/components/**/*.tsx
    - lsp diagnostics web/src/hooks/**/*.ts
    - lsp diagnostics web/src/lib/*.ts
  verification results: passed for the focused Vitest seam gate (27/27 green), repo-root raw-console grep (only instrumentation/debug seam remain), and sampled LSP diagnostics across the touched frontend surface. The direct tsconfig typecheck still reports unrelated pre-existing errors in dashboard page, replay/error-reporting tests, chat-bubble tests, and admin linked-assets tests; no new errors were reported on the migrated console-cleanup files.
  success signal status: future agents can now prove the frontend console boundary with one grep plus one focused test, and page/hook logging policy no longer depends on scattered raw console calls.
  rollback note: if later slices intentionally add or remove raw-console exceptions, update web/src/lib/debug.ts inventory, web/src/lib/console-boundary.test.ts, and the corresponding decision/knowledge entries together rather than letting page-local callers redefine the boundary by drift.


- time: 2026-04-12T00:32:00+08:00
  mode: grow
  item id: M014-S04-T02
  files changed:
    - web/src/app/(user)/practice/[sessionId]/page.tsx
    - web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.ts
    - web/src/app/(user)/practice/[sessionId]/page.test.tsx
    - web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts
    - web/src/app/test-mic/page.tsx
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
  summary: Added a truthful preflight brief to the practice page for ordinary learners, upgraded pause/resume/end failures into learner-facing retry guidance with explicit next steps, and relabeled /app/test-mic as a developer-only debug tool without reintroducing it into the learner route map.
  verification commands:
    - npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/page.test.tsx" "src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts"
    - browser smoke attempt: npm --prefix web run dev -> http://localhost:3445/practice/session-current?scenario_type=sales&voice_mode=legacy
  verification results: passed for the focused Vitest gate (13/13 green, clean output). Browser smoke was environment-blocked because local Next dev never served the page and stayed stuck on `Compiling instrumentation Node.js ...`; the managed bg_shell process was killed to keep auto-mode health clean.
  success signal status: learners now see what they are about to practice, how it will be judged, and what to do when pause/resume/end actions fail, while the standalone mic page now clearly reads as a debug-only utility.
  rollback note: if later slices enrich preflight data further, keep learner-readable names/titles hydrated from the existing agent/presentation detail APIs and keep lifecycle failures on the same page-level banner/retry seam instead of moving them back into console-only logs or a separate route.

- time: 2026-04-12T00:04:00+08:00
  mode: grow
  item id: M014-S04-T01
  files changed:
    - .gsd/KNOWLEDGE.md
    - .gsd/DECISIONS.md
    - .codex/loop/state.json
  summary: Inventoried the live practice preflight and interruption surfaces so downstream work can reuse the real seams: ordinary sessions only show thin shell state, retry focus and right-panel live summary already carry goal/evidence context, pause/resume failures are still silent, end failures already expose retry/reconnect affordances, the mic test tool lives off the learner path at /app/test-mic, and the seam choice was recorded as D178.
  verification commands:
    - rg -n "pause|resume|end|test-mic|persona|scenario|goal" 'web/src/app/(user)/practice/[sessionId]/page.tsx' 'web/src/hooks/use-practice-websocket.ts'
    - npm --prefix web test -- --run 'src/app/(user)/practice/[sessionId]/page.test.tsx' 'src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts' 'src/app/(user)/practice/layout.test.tsx'
  verification results: passed; the planned rg scan confirmed the existing scenario/persona/focus/interruption seams, and the focused practice page/lifecycle/layout Vitest suite finished 11/11 green after the knowledge-only writeback.
  success signal status: future agents can now add S04 UX copy on the existing practice page/right-panel/help seams without reintroducing a learner-facing test-mic path or duplicating retry/live-summary data.
  rollback note: if later practice UX work changes the entrypoints, keep preflight/interruption guidance on the real practice shell and right-panel seams, and keep the standalone /app/test-mic tool off the learner route map unless a deliberate product decision restores it.

- time: 2026-04-11T23:47:30+08:00
  mode: grow
  item id: M014-S03-T03
  files changed:
    - web/src/app/(dashboard)/page.test.tsx
    - web/src/app/(dashboard)/profile/page.test.tsx
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
  summary: Added focused learner-help proof on dashboard home and profile so the shared sidebar/mobile-drawer help guidance is now regression-locked across home, profile, and history instead of only on one page.
  verification commands:
    - npm --prefix web test -- --run "src/app/(dashboard)/history/page.test.tsx" "src/app/(dashboard)/**/*.test.tsx"
    - npm --prefix web test -- --run "src/app/(dashboard)/page.test.tsx" "src/app/(dashboard)/profile/page.test.tsx" "src/app/(dashboard)/history/page.test.tsx"
    - npm --prefix web test -- --run "src/components/layout/dashboard-shell.test.tsx"
  verification results: passed; the plan command stayed green but only exercised history under local Vitest glob semantics, so an explicit dashboard page suite was run and finished 22/22 green across home/profile/history, and the focused DashboardShell seam suite finished 2/2 green for the shared desktop/mobile help entry.
  success signal status: future agents can now verify learner help discoverability from the three main dashboard entry pages and separately prove the shared learner shell seam still exists.
  rollback note: if future support UX changes the copy, update the shared learner-help guidance expectations together across the dashboard page suites and the DashboardShell seam proof instead of reintroducing page-local support buttons.

- time: 2026-04-12T07:25:00+08:00
  mode: grow
  item id: M018-S02
  files changed:
    - backend/requirements.txt
    - backend/src/common/auth/service.py
    - backend/src/common/websocket/base_handler.py
    - backend/src/sales_bot/websocket/router.py
    - backend/src/sales_bot/websocket/stepfun_realtime_handler.py
    - backend/src/presentation_coach/websocket/presentation_handler.py
    - backend/src/main.py
    - backend/tests/unit/test_main_presentation_ws_runtime.py
    - web/package.json
    - web/package-lock.json
    - docs/setup/dependency-governance-baseline.md
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .gsd/PROJECT.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Closed M018/S02 by turning dependency governance into a fully green executable baseline: web audit stayed 0-vuln, backend exact pip_audit now also returns clean after requirements sync + venv rebuild, piplicenses now emits a real inventory, and auth/runtime JWT handling was migrated from python-jose to PyJWT to remove the audited ecdsa risk chain without changing the HS256 contract.
  verification commands:
    - test -f web/package.json && test -f backend/requirements.txt
    - npm audit --prefix web
    - backend/venv/bin/python -m pip_audit
    - backend/venv/bin/python -m piplicenses --from=mixed --format=json
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py -x -q
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_main_presentation_ws_runtime.py backend/tests/unit/test_websocket_handler.py -x -q
    - bash scripts/dependency-governance.sh status
  verification results: passed; all planned slice gates are now green, license inventory is runnable, and focused backend auth/websocket suites stayed green after the dependency/JWT seam hardening.
  success signal status: future agents no longer need to treat backend dependency governance as a blocked-or-open-risk-only baseline — the repo now exposes one runnable, green dependency-governance path from doc/script entrypoint through exact audit commands.
  rollback note: if later dependency updates or JWT changes reopen audit failures, keep backend/requirements.txt, docs/setup/dependency-governance-baseline.md, the shared auth JWTError seam, and the focused auth/websocket proofs aligned together; otherwise exact pip_audit can regress while the docs still claim green.

- time: 2026-04-11T23:32:52+0800
  mode: grow
  item id: M014-S03-T01
  files changed:
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Inventoried learner shell help/navigation entrypoints and confirmed the real authority seam is DashboardShell + LearnerHelpEntry, so downstream work should close discoverability/proof gaps on that shared shell instead of adding page-local help buttons.
  verification commands:
    - rg -n "反馈|帮助|管理员|support|history" web/src/components/layout web/src/app/\(dashboard\)
    - npm --prefix web test -- --run "src/components/layout/sidebar.test.tsx" "src/components/layout/dashboard-shell.test.tsx"
  verification results: passed; the rg scan showed help copy only on the shared layout seam while home/profile/history tests still focus on other learner flows, and the focused sidebar/dashboard-shell Vitest suite finished 6/6 green for desktop/mobile help mounts.
  success signal status: M014/S03 can now build on the existing shared learner help seam instead of re-researching or scattering temporary buttons across dashboard pages.
  rollback note: if later slices need richer support UX, extend DashboardShell/LearnerHelpEntry and its focused shell tests rather than reintroducing page-local help affordances on home/profile/history.

- time: 2026-04-11T23:12:00+08:00
  mode: grow
  item id: M014-S02
  files changed:
    - .gsd/milestones/M014/slices/S02/tasks/T03-SUMMARY.md
    - .gsd/milestones/M014/slices/S02/S02-SUMMARY.md
    - .gsd/milestones/M014/slices/S02/S02-UAT.md
    - .gsd/PROJECT.md
    - .codex/loop/state.json
  summary: Closed M014/S02 by formalizing password-reset lifecycle and delivery observability, preserving the truthful profile → forgot-password handoff, proving forgot/reset page closure, and locking voice-speed refresh persistence to the shared browser-local seam.
  verification commands:
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_auth_login_api.py -x -q
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_password_reset_api.py -x -q
    - npm --prefix web test -- --run "src/app/(auth)/login/page.test.tsx"
    - npm --prefix web test -- --run "src/app/(auth)/forgot-password/login-recovery.test.tsx" "src/app/(auth)/reset-password/login-reset.test.tsx" "src/app/(dashboard)/profile/page.test.tsx" "src/hooks/use-voice-speed-preference.test.ts"
  verification results: passed; backend auth/password-reset gates finished 20/20 green, focused web auth/profile/voice-speed gates finished 17/17 green, and diagnostics stayed clean on the profile/password-reset authority files.
  success signal status: learner profile now hands off to the real forgot/reset path, reset tokens keep explicit invalidation + delivery state for recovery/debugging, and voice-speed preference survives refresh truthfully through the shared localStorage seam.
  rollback note: if future account-settings work adds a true authenticated change-password or backend preference contract, extend the existing auth/profile authority seams instead of reintroducing fake profile PATCH persistence, window.location redirects, or split reset-token lifecycle semantics.

- time: 2026-03-31T11:06:08+08:00
  mode: grow
  item id: M011-S02-T03
  files changed:
    - backend/src/common/knowledge_engine/haystack_adapter.py
    - backend/src/common/knowledge_engine/reranker.py
    - backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py
    - backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py
    - backend/src/common/knowledge_engine/__init__.py
    - backend/tests/unit/common/test_haystack_adapter.py
    - backend/tests/unit/common/test_knowledge_reranker.py
    - backend/tests/unit/test_stepfun_internal_knowledge_searcher.py
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
  summary: Added a config-driven knowledge-engine execution seam to StepFun internal retrieval, including entity resolution + intent classification + retrieval planning, a Haystack-style step executor with early-stop tracing, and a business reranker that returns explainable score breakdowns on final candidates.
  verification commands:
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_haystack_adapter.py backend/tests/unit/common/test_knowledge_reranker.py backend/tests/unit/test_stepfun_internal_knowledge_searcher.py -q
  verification results: passed; focused backend pytest finished 16/16 green after the red-to-green TDD cycle, and fresh LSP diagnostics reported no issues on the touched runtime or test files.
  success signal status: StepFun internal knowledge search can now turn queries like '请介绍一下世袭科技' into canonical entity resolution, intent classification, retrieval planning, executed query-step traces, and reranked results with per-document score breakdowns while preserving legacy fallback behavior when no active config snapshot is present.
  rollback note: if downstream slices reshape the answerability flow, keep the StepFun runtime on the new project-owned seam (config snapshot -> resolver -> classifier -> planner -> adapter -> reranker) and preserve the actual-executed query trace contract instead of falling back to ad hoc rewritten-query logic.

- time: 2026-03-31T11:52:40+08:00
  mode: grow
  item id: M011-S02-T02
  files changed:
    - backend/src/common/knowledge_engine/intent_classifier.py
    - backend/src/common/knowledge_engine/retrieval_planner.py
    - backend/src/common/knowledge_engine/__init__.py
    - backend/tests/unit/common/test_knowledge_intent_classifier.py
    - backend/tests/unit/common/test_knowledge_retrieval_planner.py
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
  summary: Added a project-owned intent classifier plus progressive retrieval planner that consume DB-normalized config and entity-resolution output, support regex/keyword/entity+keyword rules, and emit auditable rewritten query steps for downstream Haystack execution.
  verification commands:
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_intent_classifier.py backend/tests/unit/common/test_knowledge_retrieval_planner.py -q
  verification results: passed; focused backend pytest finished 4/4 green after confirming the initial red state was missing classifier/planner modules, and fresh LSP diagnostics reported no issues on the new modules, exports, or focused tests.
  success signal status: normalized entity-aware queries can now be classified into DB-backed profiles and turned into deterministic progressive retrieval plans that preserve existing product-overview rewrite behavior while exposing trace/audit metadata.
  rollback note: if later control-plane work changes rule syntax or rewrite expansion vocabulary, keep the classifier/planner seam on project-owned DTOs and update the focused rule/plan tests in lockstep rather than bypassing the new modules from the Haystack adapter.

- time: 2026-03-23T02:10:18+08:00
  mode: stabilize
  item id: M001-S01-T02
  files changed:
    - backend/src/sales_bot/websocket/stepfun_realtime_handler.py
    - .gsd/DECISIONS.md
    - .gsd/milestones/M001/slices/S01/S01-PLAN.md
    - .gsd/milestones/M001/slices/S01/tasks/T02-SUMMARY.md
    - .gsd/STATE.md
    - .codex/loop/state.json
  summary: Hooked Sales StepFun back into snapshot recovery, restored turn/session runtime continuity on reconnect, and deleted dirty snapshots on timeout/terminal exits.
  verification commands:
    - cd backend && pytest tests/unit/test_stepfun_realtime_persistence.py tests/integration/test_sales_realtime_reconnect_flow.py tests/integration/test_websocket_status_contract.py
    - cd backend && pytest tests/integration/test_session_lifecycle_api.py tests/contract/test_sessions.py tests/integration/test_session_flow.py -k "lifecycle or end"
    - cd web && npx vitest --run 'src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts' src/hooks/use-practice-websocket.test.ts src/hooks/websocket/message-handlers.test.ts
  verification results: passed; exact npm test slice command still fails before execution because the package script duplicates --run
  success signal status: reconnected payloads now restore minimal runtime state and reconnect flow reaches end with session_status=scoring while snapshots are cleared
  rollback note: revert StepFun handler snapshot integration if future work changes reconnect protocol; keep D010 boundary unless replacing it with a broader tested contract

- time: 2026-03-25T15:03:33+0800
  mode: stabilize
  item id: M003-S04-T03
  files changed:
    - web/src/lib/session-evidence.ts
    - web/src/app/(user)/practice/[sessionId]/report/page.tsx
    - web/src/app/(user)/practice/[sessionId]/replay/page.tsx
    - web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
    - web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
  summary: Learner report and replay now render the canonical claim-truth line from the completed-session evidence snapshot, with shared labels/explanations for unsupported, weak, pending, and verified sales claims.
  verification commands:
    - cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx' 'src/app/(user)/practice/[sessionId]/replay/page.test.tsx'
    - cd web && npx tsc --noEmit
  verification results: focused report/replay Vitest passed; repo-wide web typecheck still reports the pre-existing admin knowledge page error `api.reprocessKnowledgeDocument` missing in `src/app/admin/knowledge/[id]/page.tsx`, and no new type errors remained in the S04 files after the claim-truth parser fix
  success signal status: report and replay now expose the same canonical claim-truth vocabulary already used by realtime diagnostics without leaking kb-lock chain-failure copy into completed-session coaching surfaces
  rollback note: if a future contract version promotes claim-truth to a top-level field, keep report/replay on the completed-session projection line and migrate the shared frontend helper rather than reintroducing knowledge-check as the primary read surface

- time: 2026-03-23T02:35:20+08:00
  mode: stabilize
  item id: M001-S01-T03
  files changed:
    - web/package.json
    - web/src/app/(user)/practice/[sessionId]/page.tsx
    - web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.ts
    - web/src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts
    - web/src/hooks/use-practice-websocket.ts
    - web/src/hooks/use-practice-websocket.test.ts
    - web/src/hooks/websocket/message-handlers.ts
    - web/src/hooks/websocket/message-handlers.test.ts
    - .gsd/DECISIONS.md
    - .gsd/completed-units.json
    - .gsd/milestones/M001/slices/S01/S01-PLAN.md
    - .gsd/milestones/M001/slices/S01/tasks/T03-SUMMARY.md
    - .gsd/STATE.md
    - .codex/loop/state.json
  summary: Practice page lifecycle now follows server status/reconnected/session_ended, end failures stay visible on the training page with retry/reconnect affordances, and report navigation waits for confirmed terminal status.
  verification commands:
    - cd backend && pytest tests/integration/test_session_lifecycle_api.py tests/contract/test_sessions.py tests/integration/test_session_flow.py -k "lifecycle or end"
    - cd backend && pytest tests/unit/test_stepfun_realtime_persistence.py tests/integration/test_sales_realtime_reconnect_flow.py tests/integration/test_websocket_status_contract.py
    - cd web && npm test -- --run 'src/app/(user)/practice/[sessionId]/use-practice-session-lifecycle.test.ts' src/hooks/use-practice-websocket.test.ts src/hooks/websocket/message-handlers.test.ts
    - browser verification: legacy sales session + backend-down failure injection confirmed end stays on /practice with retry UI; fresh legacy session confirmed end routes to /report after terminal transition
  verification results: passed
  success signal status: training-page end failures are no longer masked by report redirects, and lifecycle UI state is driven by server events instead of optimistic local writes
  rollback note: revert the T03 frontend lifecycle changes together if future work redefines websocket lifecycle contracts; keep D011 unless a new server-authoritative contract replaces it

- time: 2026-03-30T15:49:00+08:00
  mode: grow
  item id: M010-S03-T01
  files changed:
    - web/src/lib/api/types.ts
    - web/src/lib/session-evidence.ts
    - web/src/app/(user)/practice/[sessionId]/report/page.tsx
    - web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
    - .gsd/DECISIONS.md
    - .codex/loop/state.json
  summary: Added shared frontend conclusion-evidence types and helper-owned provenance/degradation formatters, then wired the learner report page to render canonical report-driven conclusion provenance plus four-layer degradation without parsing raw contract fragments in the page.
  verification commands:
    - npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/report/page.test.tsx"
  verification results: passed; focused report-page Vitest finished 21/21 green, including happy-path sales provenance/degradation, malformed payload omission, rejected supplemental knowledge-check, and presentation-null suppression.
  success signal status: the learner report now exposes a visible helper-driven authority seam for conclusion provenance and degradation distinct from optional knowledge-check diagnostics.
  rollback note: if T02 replay parity reopens this path, keep token-to-copy mapping and malformed-fragment filtering in session-evidence.ts rather than duplicating page-local parsing.

- time: 2026-03-30T16:09:30+0800
  mode: grow
  item id: M010-S03
  files changed:
    - web/src/lib/api/types.ts
    - web/src/lib/session-evidence.ts
    - web/src/app/(user)/practice/[sessionId]/report/page.tsx
    - web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
    - web/src/app/(user)/practice/[sessionId]/replay/page.tsx
    - web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx
    - .gsd/KNOWLEDGE.md
    - .gsd/PROJECT.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Closed M010/S03 after fresh slice-level verification confirmed learner report and replay both render helper-owned conclusion provenance and four-layer degradation from canonical payload fields, while replay keeps report snapshots retry-metadata-only.
  verification commands:
    - npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx"
  verification results: passed; focused report+replay Vitest finished 33/33 green, covering shared provenance/degradation vocabulary, malformed helper inputs, supplemental knowledge-check failure isolation, stale report-snapshot non-authority, replay completion-gate behavior, retry CTA behavior, highlight/deep-link anchors, and presentation-null suppression.
  success signal status: learner-facing report and replay now show the same explanation of why each conclusion is believed and which evidence layers are degraded, without page-local truth derivation.
  rollback note: if future work changes conclusion provenance/degradation fields, keep report and replay on the shared session-evidence helper seam and preserve replay payload authority over any cached report snapshot.

- time: 2026-03-31T14:06:08+08:00
  mode: grow
  item id: M011-S04-T01
  files changed:
    - backend/src/common/knowledge_engine/evaluation.py
    - backend/tests/evaluation/test_knowledge_answer_engine_eval.py
    - backend/tests/fixtures/knowledge_answer_eval_cases.json
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
  summary: Added a fixture-driven knowledge-answer evaluation harness plus an initial deterministic case set that runs the real engine seam through product intro, pricing, version comparison, coaching guidance, and blocked-timeout degradation behaviors.
  verification commands:
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/evaluation/test_knowledge_answer_engine_eval.py -q
    - backend/venv/bin/python -m py_compile backend/src/common/knowledge_engine/evaluation.py backend/tests/evaluation/test_knowledge_answer_engine_eval.py
  verification results: passed; fresh repo-root pytest finished 6/6 green for the new harness and fixture cases, and a follow-up py_compile check passed on the new evaluation module and focused test file.
  success signal status: the backend can now replay a stable eval fixture suite against the project-owned knowledge-answer engine without a live knowledge base, while preserving exact multiline answer formatting and blocked-timeout degradation expectations.
  rollback note: if later slices evolve answer copy or retrieval-summary fields, keep the eval harness on the real engine seam and update fixture expectations in lockstep instead of moving assertions into runtime-handler-specific tests.

  files changed:
    - backend/alembic/versions/20260331_1100_023_knowledge_answer_control_plane.py
    - backend/tests/unit/common/test_knowledge_answer_control_plane_models.py
    - .gsd/KNOWLEDGE.md
  summary: Added the missing Alembic control-plane revision for knowledge config and answer run/step audit tables, and extended the focused backend model test to fail when the migration file is absent or stops declaring the expected schema.
  verification commands:
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_answer_control_plane_models.py -q
  verification results: passed; focused backend pytest finished 10/10 green, and the new migration-presence assertions verified the revision exists, points to 20260328_1000_022, and names all expected control-plane/audit tables.
  success signal status: knowledge answer control-plane schema history now contains the versioned config plus answer run/step audit tables needed for future DB-backed config reads and execution-trace persistence.
  rollback note: if a future migration reshapes these tables, update the focused regression test in lockstep so ORM definitions and Alembic history cannot drift again.

- time: 2026-03-31T11:31:56+0800
  mode: grow
  item id: M011-S01
  files changed:
    - backend/src/common/knowledge_engine/__init__.py
    - backend/src/common/knowledge_engine/engine.py
    - backend/src/common/knowledge_engine/schemas.py
    - backend/src/common/knowledge_engine/config_repo.py
    - backend/alembic/versions/20260331_1100_023_knowledge_answer_control_plane.py
    - .gsd/DECISIONS.md
    - .gsd/PROJECT.md
    - .codex/loop/state.json
  summary: Closed M011/S01 after fresh slice-level verification confirmed the constructable KnowledgeAnswerEngine seam, control-plane Alembic schema history, and DB-backed normalized active-config repository are all in place for downstream Haystack execution work.
  verification commands:
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_answer_engine.py -q
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_answer_control_plane_models.py -q
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_answer_config_repo.py -q
  verification results: passed; focused backend slice-close gate finished 14/14 tests green and LSP diagnostics reported no issues on the engine, schemas, repository, migration, and focused test files
  success signal status: downstream slices can now instantiate a project-owned knowledge-answer engine and read one latest enabled active query/ranking/answerability configuration snapshot from the database without leaking Haystack types, ORM rows, or raw JSON control-plane shapes
  rollback note: if S02/S03 reshape the control-plane schema or repository snapshot, keep the project-owned engine/repository seam intact and update migration-presence plus repository-normalization regressions in lockstep rather than bypassing them in runtime handlers

- time: 2026-03-31T13:55:34+0800
  mode: grow
  item id: M011-S04-T02
  files changed:
    - backend/src/common/api/knowledge_debug.py
    - backend/src/main.py
    - backend/tests/integration/test_knowledge_debug_api.py
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
  summary: Added a read-only knowledge debug API for admin/support users that lists recent answer runs, returns one run’s persisted audit payload, and exposes ordered step breakdowns directly from KnowledgeAnswerRun and KnowledgeAnswerRunStep rows.
  verification commands:
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_knowledge_debug_api.py -q
    - backend/venv/bin/python -m py_compile backend/src/common/api/knowledge_debug.py backend/tests/integration/test_knowledge_debug_api.py
  verification results: passed; fresh repo-root focused integration pytest finished 5/5 green for list/detail/steps/RBAC/not-found coverage, py_compile passed on the new router and focused test module, and fresh LSP diagnostics reported no issues on backend/src/common/api/knowledge_debug.py or backend/src/main.py.
  success signal status: admin/support can now inspect recent persisted knowledge-answer runs and their ordered step traces from one stable /api/v1/knowledge-debug surface without reconstructing runtime-local traces.
  rollback note: if T03 or later slices extend report/debug inspection, keep this surface read-only and backed by the persisted audit rows plus compat payload fields rather than teaching runtime handlers to rebuild traces for API consumers.

- time: 2026-04-11T22:18:19+08:00
  mode: grow
  item id: M014-S02-T01
  files changed:
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
  summary: Inventoried the live auth/profile seams and recorded that backend forgot/reset is already persisted and tested, while profile password change remains a truthful forgot-password handoff and voice-speed preference still lives only in localStorage.
  verification commands:
    - rg -n "forgot|reset|password|speech|rate|window.location" web/src/app/\(auth\) web/src/app/\(dashboard\)/profile backend/src/common/auth
    - rg -n "forgot|reset|PasswordReset|AUTH_SHARED_PASSWORD|AUTH_USER_PASSWORDS|hashed_password" backend/tests -g "!**/__pycache__/**"
  verification results: passed; repo-root rg verification found the live auth/profile entrypoints and silent-fallback surfaces, and the focused backend test scan confirmed dedicated forgot/reset integration coverage already exists in backend/tests/integration/test_password_reset_api.py rather than only in test_auth_login_api.py.
  success signal status: downstream M014/S02 tasks can now build from the real seams instead of re-researching—PasswordResetService + PasswordResetToken are already the backend authority, the profile password CTA is intentionally a `/forgot-password` link, and voice speed is still frontend-local persistence.
  rollback note: if later slices change these seams, keep one authoritative reset-token lifecycle and one authoritative voice-speed persistence seam instead of reintroducing fake profile password APIs or split storage paths.

- time: 2026-04-12T01:04:39+08:00
  mode: grow
  item id: M015-S01-T01
  files changed:
    - web/src/lib/debug.ts
    - web/src/components/ErrorBoundary.tsx
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
  summary: Inventoried the live frontend console surfaces and encoded one canonical boundary in web/src/lib/debug.ts so downstream migration work can distinguish instrumentation exceptions from durable business errors and debug-only noise without rerunning a repo-wide search.
  verification commands:
    - rg -n "console\.(log|error|warn|info)" web/src
    - lsp diagnostics web/src/lib/debug.ts
    - lsp diagnostics web/src/components/ErrorBoundary.tsx
  verification results: passed; the repo-root rg gate produced the expected raw-console inventory for classification, and fresh LSP diagnostics reported no issues after adding the inventory map to web/src/lib/debug.ts and tagging ErrorBoundary as a durable route-error surface.
  success signal status: future M015/S01 tasks now have an explicit migration contract—only instrumentation bootstrap and the shared debug seam itself are allowed raw-console exceptions, while route errors, business faults, and dev/support debug output have named categories and seam destinations.
  rollback note: if later slices narrow or expand the exception set, update the shared inventory in web/src/lib/debug.ts and the corresponding knowledge/decision entries together instead of letting page-local console calls define policy by drift.

- time: 2026-04-12T01:52:30+08:00
  mode: grow
  item id: M015-S02-T01
  files changed:
    - web/src/lib/auth-handler.ts
    - web/src/lib/auth-handler.test.ts
    - web/src/app/admin/records/page.tsx
    - web/src/app/admin/rag-profiles/page.tsx
    - web/src/app/admin/personas/[id]/page.tsx
    - .gsd/KNOWLEDGE.md
    - .gsd/DECISIONS.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Centralized the remaining native-dialog and hard-navigation inventory into web/src/lib/auth-handler.ts, annotated the hottest admin touchpoints with their target seams, and locked the inventory with a focused auth-handler unit test so later cleanup work can distinguish true cleanup points from explained grep exceptions.
  verification commands:
    - npm --prefix web test -- --run src/lib/auth-handler.test.ts
    - rg -n "\b(alert|confirm)\s*\(|window\.location(\.assign|\.href)" web/src
    - lsp diagnostics web/src/lib/auth-handler.ts
    - lsp diagnostics web/src/app/admin/records/page.tsx
    - lsp diagnostics web/src/app/admin/rag-profiles/page.tsx
    - lsp diagnostics web/src/app/admin/personas/*/page.tsx
    - lsp diagnostics web/src/lib/auth-handler.test.ts
  verification results: passed; the focused auth-handler test finished 4/4 green, the slice grep gate now reports only the real remaining cleanup points plus the documented ErrorBoundary/performance/admin-error exceptions, and the touched authority files were diagnostics-clean.
  success signal status: downstream S02 tasks can now migrate dialog/toast/router/auth-handler seams from one shared inventory instead of re-scanning admin/learner pages or accidentally treating grep exceptions as product regressions.
  rollback note: if T02/T03 changes the remaining exception set, update interruptiveUiInventory, its focused unit test, and the matching knowledge/decision entries together; do not add literal grep-target strings into the inventory/comments or the grep gate will start matching the documentation itself.

- time: 2026-04-12T04:35:21+08:00
  mode: grow
  item id: M016-S03-T03
  files changed:
    - backend/tests/integration/test_admin_users_api.py
    - backend/tests/unit/admin/test_admin_users_api_models.py
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Added focused admin-security baseline proof that locks the repaired router RBAC seam, proves sink-level log redaction, and encodes the current covered-vs-follow-up inventory scope directly in tests.
  verification commands:
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_admin_users_api.py -k "admin_security_baseline_inventory_is_closed_and_scoped or admin_router_modules_require_admin_even_without_main_router_guard" -q
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/admin/test_admin_users_api_models.py -k "structured_logger_masks_sensitive_fields_before_sink_emission or sensitive_log_security_baseline_inventory_is_closed_and_scoped" -q
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_admin_users_api.py backend/tests/unit/admin/test_admin_users_api_models.py -x -q
    - lsp diagnostics backend/tests/integration/test_admin_users_api.py
    - lsp diagnostics backend/tests/unit/admin/test_admin_users_api_models.py
  verification results: passed; the focused admin baseline subset finished 6/6 green, the focused logger/inventory subset finished 2/2 green, the exact task-plan pytest gate finished 36/36 green, and diagnostics were clean on the two touched proof files.
  success signal status: future agents can now rerun one focused backend bundle to tell whether a regression is in module-level admin RBAC, sink-level redaction, or inventory drift about what this baseline currently covers.
  rollback note: if later admin route families or sensitive-log surfaces are added, update the code-owned inventories and these focused proof subsets together so the watch/baseline split does not drift from runtime reality.

- time: 2026-04-12T05:53:19+08:00
  mode: grow
  item id: M017-S03-T01
  files changed:
    - backend/src/presentation_coach/api/presentations.py
    - backend/tests/contract/test_presentations.py
    - backend/tests/integration/test_presentation_flow.py
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Added a code-adjacent presentation upload/resource race inventory, locked replace as the first concurrent-writer proof target, and proved in the focused integration harness that delete currently succeeds without a route-level live-session blocker and detaches the session from its presentation.
  verification commands:
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_presentations.py backend/tests/integration/test_presentation_flow.py -q
    - rg -n "replace|upload|delete|active-session|lock" backend/src/presentation_coach/api/presentations.py backend/tests/contract/test_presentations.py backend/tests/integration/test_presentation_flow.py
    - lsp diagnostics backend/src/presentation_coach/api/presentations.py
    - lsp diagnostics backend/tests/contract/test_presentations.py
    - lsp diagnostics backend/tests/integration/test_presentation_flow.py
  verification results: passed; the focused presentation contract/integration suite finished 9/9 green, the exact task-plan rg inventory now surfaces the code-adjacent discovery seam plus the new delete guard-gap proof, and diagnostics stayed clean on the touched backend authority/test files.
  success signal status: future agents can now tell which presentation race surfaces are already covered, which one is already proved as a guard gap, and which one still needs concurrent reproduction before any locking work is justified.
  rollback note: if later S03 work changes presentation mutation rules, keep the runtime inventory in backend/src/presentation_coach/api/presentations.py and the focused proofs in backend/tests/contract/test_presentations.py + backend/tests/integration/test_presentation_flow.py aligned together; otherwise discovery conclusions will drift back into audit guesses.

- time: 2026-04-12T06:45:20+08:00
  mode: grow
  item id: M018-S01-T03
  files changed:
    - backend/tests/contract/test_analytics.py
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Added a layered query/index discovery backlog to the analytics contract so future agents can start from explicit confirmed gaps versus Postgres-only hypotheses instead of rebuilding M018 DB findings from scattered inventories.
  verification commands:
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_analytics.py -k "db_performance_baseline or query_index_discovery_conclusions" -q
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_analytics.py backend/tests/unit/common/test_admin_analytics_service.py backend/tests/unit/common/test_leaderboard_service.py -x -q
    - lsp diagnostics backend/tests/contract/test_analytics.py
    - lsp diagnostics backend/tests/unit/common/test_admin_analytics_service.py
    - lsp diagnostics backend/tests/unit/common/test_leaderboard_service.py
  verification results: passed; the red-green contract proof finished green, the full task-plan pytest gate finished 23/23 green, and diagnostics stayed clean on the touched/focused proof files.
  success signal status: downstream M018 work no longer needs to infer priority from baseline inventory strings alone — the contract now names which query-shape gaps are already confirmed and which index/search ideas still require real Postgres/runtime evidence before implementation.
  rollback note: if a future slice proves or retires any query/index candidate, update backend/tests/contract/test_analytics.py together with the code-adjacent inventory constant that supplied the evidence so the backlog does not drift from the live baseline.

- time: 2026-04-12T06:53:04+08:00
  mode: grow
  item id: M018-S01
  files changed:
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .gsd/PROJECT.md
    - .gsd/milestones/M018/slices/S01/S01-SUMMARY.md
    - .gsd/milestones/M018/slices/S01/S01-UAT.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Closed M018/S01 after fresh slice-level verification confirmed the query/index discovery baseline is now code-adjacent, executable, and layered by proof strength, with one reusable backlog for future performance work instead of audit-era guesswork.
  verification commands:
    - rg -n "select|join|order_by|group_by|SessionEvidence|leaderboard|analytics" backend/src/common/analytics backend/src/common/conversation backend/src/admin/api
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_analytics.py backend/tests/unit/common/test_admin_analytics_service.py backend/tests/unit/common/test_leaderboard_service.py -x -q
    - lsp diagnostics backend/tests/contract/test_analytics.py
    - lsp diagnostics backend/tests/unit/common/test_admin_analytics_service.py
    - lsp diagnostics backend/tests/unit/common/test_leaderboard_service.py
  verification results: passed; the slice-close rg inventory stayed present, the full analytics/leaderboard/query-index gate finished 23/23 green, and diagnostics stayed clean on the proof files.
  success signal status: downstream M018 work can now start from one durable discovery artifact that distinguishes focused-proof-confirmed projection costs, code-path-confirmed gaps, and index ideas that still need real Postgres evidence.
  rollback note: if later performance slices implement or disprove any listed gap, update the code-adjacent baseline inventories, QUERY_INDEX_DISCOVERY_CONCLUSIONS, and focused analytics proof together so the discovery backlog does not drift from runtime facts.

- time: 2026-04-12T07:03:27+0800
  mode: grow
  item id: M018-S02-T02
  files changed:
    - docs/setup/dependency-governance-baseline.md
    - scripts/dependency-governance.sh
    - scripts/README.md
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Landed the first repo-local dependency-governance baseline by writing one authority doc plus one wrapper script that exposes the real dependency truth lines, scan cadence, upgrade gates, backend requirements.txt sync rule, approved license-scan commands, and the current missing pip_audit/pip-licenses prerequisites without pretending CI already proves them.
  verification commands:
    - bash -n scripts/dependency-governance.sh
    - bash scripts/dependency-governance.sh status
    - bash scripts/dependency-governance.sh license-plan
    - bash scripts/dependency-governance.sh backend-audit
    - npm audit --prefix web
  verification results: passed with honest blockers; the wrapper stayed shell-valid, status/license-plan surfaced the real authority files plus missing backend/license prerequisites, backend-audit failed in the expected blocked-prerequisite mode (exit 2 with install guidance), and the required npm audit gate still reports the inherited 8 web vulnerabilities instead of being papered over.
  success signal status: future agents can now determine the current dependency-governance state from one repo-local doc/script pair, know that backend dependency sync is anchored to requirements.txt, and see exactly which proofs are runnable versus blocked by missing tools.
  rollback note: if a later slice pins different license tooling or repairs backend pyproject extras, update docs/setup/dependency-governance-baseline.md, scripts/dependency-governance.sh, scripts/README.md, and the matching decision/knowledge entries together so the governance baseline does not drift from the actual runnable commands.

- time: 2026-04-12T07:18:54+0800
  mode: grow
  item id: M018-S02-T03
  files changed:
    - web/package.json
    - web/package-lock.json
    - docs/setup/dependency-governance-baseline.md
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Closed M018/S02/T03 by turning dependency-governance proof into a truthful executed-vs-blocked record: the web lockfile was refreshed until npm audit returned green, the baseline doc now records the exact proof commands and prerequisites, and backend security/license proof now explicitly distinguishes requirements-scoped open risk from scanner/runtime blockers instead of treating them as the same kind of failure.
  verification commands:
    - npm audit --prefix web
    - npm --prefix web test -- --run src/lib/api/client.auth.test.ts
    - PIP_AUDIT_VULNERABILITY_SERVICE=osv backend/venv/bin/python -m pip_audit -r backend/requirements.txt
    - backend/venv/bin/python -m piplicenses --from=mixed --format=json
  verification results: web governance is now green end-to-end (`npm audit` exits 0 and the focused client-auth suite stayed 9/9 green). Backend requirements-scoped pip_audit now executes and truthfully reports one open ecdsa CVE with no newer pip release available, while pip-licenses still crashes on missing package Name metadata and therefore remains an explicit blocked scanner/runtime issue rather than a silent pass.
  success signal status: future agents can now open the baseline doc and immediately tell which proofs were executed, which one is a real open dependency risk, and which one is still blocked by tooling/runtime rather than product code drift.
  rollback note: if later dependency work changes the backend scanner or resolves the ecdsa/open-license blockers, update web/package-lock.json, docs/setup/dependency-governance-baseline.md, D207, and the matching knowledge entry together so the repo keeps one truthful proof ledger instead of drifting back to command-name-only guidance.

- time: 2026-04-13T10:56:08+08:00
  mode: grow
  item id: M019-S01-T02
  files changed:
    - backend/src/common/db/session.py
    - backend/src/common/db/legacy_schema_repair.py
    - backend/scripts/repair_legacy_schema.py
    - backend/alembic/versions/20260413_1040_029_explicit_legacy_startup_repairs.py
    - backend/tests/integration/test_startup_or_bootstrap_authority.py
    - backend/tests/unit/common/test_db_session_compatibility.py
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Moved the remaining startup schema repair out of production-like service startup by restricting compatibility guards to development/test bootstrap, routing the same persona/knowledge legacy repair through an explicit shared helper used by the repair script and a new Alembic revision, and proving prod-like startup now fails loudly on missing migration drift.
  verification commands:
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_startup_or_bootstrap_authority.py backend/tests/unit/common/test_db_session_compatibility.py -q
    - lsp diagnostics backend/src/common/db/session.py
    - lsp diagnostics backend/src/common/db/legacy_schema_repair.py
    - lsp diagnostics backend/scripts/repair_legacy_schema.py
    - lsp diagnostics backend/alembic/versions/20260413_1040_029_explicit_legacy_startup_repairs.py
    - lsp diagnostics backend/tests/integration/test_startup_or_bootstrap_authority.py
    - lsp diagnostics backend/tests/unit/common/test_db_session_compatibility.py
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration -k "startup or bootstrap or migration" -x -q
  verification results: passed; focused proof is green for explicit production-like startup failure and explicit repair-script handoff, the touched Python/revision/test files are diagnostics-clean, and the exact slice gate passes without relying on implicit startup schema patching outside development/test.
  success signal status: production-like startup no longer silently repairs legacy persona/knowledge schema drift, while operators still have two explicit recovery paths — `alembic upgrade head` (now including revision 20260413_1040_029) and `python scripts/repair_legacy_schema.py`.
  rollback note: if later tasks remove `Base.metadata.create_all()` or further narrow local bootstrap, keep `backend/src/common/db/session.py`, `backend/src/common/db/legacy_schema_repair.py`, `backend/scripts/repair_legacy_schema.py`, the explicit Alembic repair revision, and the focused startup authority tests aligned together so startup/bootstrap authority does not drift again.

- time: 2026-04-13T22:20:00+08:00
  mode: grow
  item id: M020-S02-T02
  files changed:
    - .gsd/DECISIONS.md
    - backend/src/common/monitoring/logger.py
    - backend/src/admin/api/system_logs.py
    - backend/tests/integration/test_admin_users_api.py
    - backend/tests/unit/admin/test_system_logs_redaction.py
    - web/src/app/admin/logs/page.tsx
    - web/src/app/admin/logs/page.test.tsx
    - web/src/lib/api/types.ts
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Unified the admin/support log redaction contract across logger, API, and UI by making logger.py the source of truth for safe diagnostic field order, teaching the system log API to emit ordered diagnostics plus policy metadata, and switching the admin logs page to render that server-supplied diagnostics list instead of reconstructing visibility client-side.
  verification commands:
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/admin/test_system_logs_redaction.py backend/tests/integration/test_admin_users_api.py -k "system_logs_api_returns_shared_redaction_policy_and_safe_diagnostics or test_log_to_response_applies_admin_support_exposure_policy" -q
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_admin_users_api.py backend/tests/unit/admin/test_admin_users_api_models.py -x -q && npm --prefix web test -- --run "src/app/admin/logs/page.test.tsx"
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/admin/test_system_logs_redaction.py -q
    - lsp diagnostics backend/src/common/monitoring/logger.py
    - lsp diagnostics backend/src/admin/api/system_logs.py
    - lsp diagnostics web/src/app/admin/logs/page.tsx
    - lsp diagnostics web/src/lib/api/types.ts
    - lsp diagnostics backend/tests/unit/admin/test_system_logs_redaction.py
    - lsp diagnostics web/src/app/admin/logs/page.test.tsx
  verification results: passed; the new backend unit + integration proofs finished green, the exact task-plan backend/web verification command passed end-to-end, and diagnostics stayed clean on the touched runtime/test files.
  success signal status: future M020/M021 observability work no longer has to guess whether trace_id/error_code/phase/session_id/target_user_id are safe to show or rebuild that selection in the UI — one ordered diagnostics contract now flows from backend policy to admin display.
  rollback note: if later work changes which admin/support diagnostics are safe to expose, update logger.py diagnostic-field constants, the system-log API policy payload, the focused backend serializer/API proofs, and the admin logs page test together so backend/API/UI do not drift.

- time: 2026-04-13T23:30:30+08:00
  mode: grow
  item id: M020-S02
  files changed:
    - .gsd/milestones/M020/slices/S02/S02-SUMMARY.md
    - .gsd/milestones/M020/slices/S02/S02-UAT.md
    - .gsd/PROJECT.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Closed M020/S02 after fresh slice-level verification confirmed that the shared logger, admin system-log API, and admin logs page now expose one backend-owned allowlist-first diagnostics contract; support/admin keep masked identifiers plus safe diagnostics while raw details, precise identity/IP data, and provider/request/prompt/secret-adjacent payloads remain backend-only.
  verification commands:
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_admin_users_api.py backend/tests/unit/admin/test_admin_users_api_models.py -x -q && npm --prefix web test -- --run "src/app/admin/logs/page.test.tsx"
    - rg -n "token|password|cookie|email|user_identifier|ip_address|details" backend/src/common/monitoring backend/src/admin/api web/src/app/admin/logs/page.tsx
    - rg -n "allowlist|redaction|trace_id|details|support|admin" backend/src/admin/api/security_inventory.py backend/src/common/monitoring/log_safety_inventory.py .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/admin/test_system_logs_redaction.py -q
    - lsp diagnostics backend/src/common/monitoring/logger.py
    - lsp diagnostics backend/src/admin/api/system_logs.py
    - lsp diagnostics backend/src/admin/api/security_inventory.py
    - lsp diagnostics backend/src/common/monitoring/log_safety_inventory.py
    - lsp diagnostics web/src/app/admin/logs/page.tsx
    - lsp diagnostics web/src/lib/api/types.ts
    - lsp diagnostics backend/tests/unit/admin/test_system_logs_redaction.py
    - lsp diagnostics web/src/app/admin/logs/page.test.tsx
  verification results: passed; the slice-plan backend+frontend gate finished 37 backend tests plus 1 web admin-logs test green, both grep gates were rerun fresh, the focused system-log redaction proof passed, and diagnostics stayed clean on the touched authority/test files.
  success signal status: downstream M020/M021 work no longer has to guess what admin/support may see in failure logs — the logger, route, UI, inventory, and architecture scan all now agree on the same safe diagnostics boundary.
  rollback note: if later work expands admin/support observability fields, update the shared logger policy constants, system-log API contract, admin logs UI renderer, both inventory modules, and the architecture scan together; otherwise route/UI behavior and support guidance will drift again.

- time: 2026-04-14T07:42:19+08:00
  mode: grow
  item id: M020-S03-T03
  files changed:
    - docs/api-contract/support-runtime.md
    - docs/backup-recovery-runbook.md
    - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Wrote the runtime state authority split back into the durable support/operator surfaces: support-runtime now documents the real overview/fault contract plus the companion SessionManager and SessionStateService inspection surfaces, the backup/recovery runbook now explains what restart and drain really preserve, and the architecture scan turns the same rule into a downstream boundary instead of leaving it implicit in websocket code.
  verification commands:
    - rg -n "reconnect|epoch|snapshot|active connection|drain|restart" docs/api-contract/support-runtime.md docs/backup-recovery-runbook.md .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
  verification results: passed; the exact task-plan grep gate was rerun fresh and now exposes reconnect, epoch, snapshot, active connection, drain, and restart wording across all three durable surfaces.
  success signal status: future support/runtime, recovery, and multi-instance hardening work no longer has to guess whether /api/v1/support/runtime is a websocket truth surface or whether restart empties cluster state — the docs now say release-health summary lives in the API, live connections are process-local, Redis snapshots are the restart-safe authority, and drain still depends on external traffic steering.
  rollback note: if later work adds a real websocket drain endpoint, cluster-wide live-connection authority, or new support/runtime inspection payloads, update docs/api-contract/support-runtime.md, docs/backup-recovery-runbook.md, and section 7.2.3 of the architecture scan together so operator guidance does not drift again.

- time: 2026-04-14T07:50:41+08:00
  mode: grow
  item id: M020-S03
  files changed:
    - backend/src/common/websocket/session_manager.py
    - backend/src/common/websocket/session_state_service.py
    - backend/src/sales_bot/websocket/stepfun_realtime_handler.py
    - backend/tests/unit/test_session_runtime_authority.py
    - backend/tests/integration/test_websocket_status_contract.py
    - backend/tests/integration/test_sales_realtime_reconnect_flow.py
    - docs/api-contract/support-runtime.md
    - docs/backup-recovery-runbook.md
    - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
    - .gsd/DECISIONS.md
    - .gsd/KNOWLEDGE.md
    - .gsd/PROJECT.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Closed M020/S03 after fresh slice-level verification confirmed the runtime authority split is now explicit and durable: SessionManager is the instance-local live-connection surface, SessionStateService is the shared Redis reconnect authority, StepFun reconnect snapshots preserve request/pacing continuity without replaying stale action-card UI, and support/runbook surfaces now explain restart/drain semantics without pretending /support/runtime is a cluster-state API.
  verification commands:
    - rg -n "SessionManager|SessionStateService|snapshot|reconnect|active_connections|runtime_state" backend/src/common/websocket backend/src/sales_bot/websocket backend/src/presentation_coach/websocket
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_websocket_status_contract.py backend/tests/integration/test_sales_realtime_reconnect_flow.py -x -q
    - rg -n "reconnect|epoch|snapshot|active connection|drain|restart" docs/api-contract/support-runtime.md docs/backup-recovery-runbook.md .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
    - lsp diagnostics backend/src/common/websocket/session_manager.py
    - lsp diagnostics backend/src/common/websocket/session_state_service.py
    - lsp diagnostics backend/src/sales_bot/websocket/stepfun_realtime_handler.py
    - lsp diagnostics backend/tests/integration/test_websocket_status_contract.py
    - lsp diagnostics backend/tests/integration/test_sales_realtime_reconnect_flow.py
  verification results: passed; the websocket authority grep gate stayed green, the exact slice-plan pytest bundle finished 11/11 green, the support-runtime/runbook/architecture grep gate stayed green, and LSP diagnostics were clean on the touched runtime/test files. Only the pre-existing pytest-cov no-data warning remained.
  success signal status: future S04 recovery drill work can start from one truthful runtime contract instead of rediscovering it — live connection visibility is explicitly process-local, Redis snapshots are explicitly restart-safe shared authority, request epoch and pacing state survive reconnect, stale action-card UI does not, and the operator docs now say that restart/drain still lacks repo-native cluster controls.
  rollback note: if later work adds cluster drain controls, widens /support/runtime, or changes reconnect snapshot contents, update SessionManager.get_stats(), SessionStateService.get_stats(), the StepFun reconnect snapshot contract, the support-runtime/runbook docs, and the focused status-contract/reconnect proof together so the authority split does not drift again.

- time: 2026-04-14T08:27:27.661185+08:00
  mode: grow
  item id: M020-S04-T02
  files changed:
    - scripts/recovery_drill_baseline.py
    - scripts/recovery_drill_runner.py
    - scripts/recovery-drill-baseline.py
    - scripts/recovery-drill-runner.py
    - backend/scripts/bootstrap_auth_admin.py
    - backend/tests/unit/test_recovery_drill_runner.py
    - backend/tests/unit/test_bootstrap_auth_admin.py
    - docs/backup-recovery-runbook.md
    - docs/setup/backup-recovery-current-state.md
    - .gsd/KNOWLEDGE.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Turned the recovery inventory into a minimal executable drill runner: the baseline now carries command templates, preconditions, and failure signals; the new runner executes those commands, writes per-drill logs plus summary.json under .dev/recovery-drills, and the auth bootstrap entrypoint now imports agent.models so recovery no longer dies on unresolved Agent/Persona mappers.
  verification commands:
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_bootstrap_auth_admin.py backend/tests/unit/test_recovery_drill_baseline.py backend/tests/unit/test_recovery_drill_runner.py -q
    - RECOVERY_ADMIN_EMAIL=admin@qoder.ai RECOVERY_ADMIN_NAME=管理员 python3 scripts/recovery-drill-runner.py run --continue-on-failure --drill db_migration --drill auth_bootstrap --drill redis_session_state --drill oss_signing_playback --drill health_check
    - bash scripts/dependency-governance.sh status && rg -n "health|alembic|bootstrap|redis|oss|recovery" scripts/recovery-* docs/backup-recovery-runbook.md
    - lsp diagnostics scripts/recovery_drill_baseline.py
    - lsp diagnostics scripts/recovery_drill_runner.py
    - lsp diagnostics backend/scripts/bootstrap_auth_admin.py
    - lsp diagnostics backend/tests/unit/test_recovery_drill_runner.py
    - lsp diagnostics backend/tests/unit/test_bootstrap_auth_admin.py
  verification results: passed with one truthful environment blocker; the focused unit proof finished 7/7 green, the real drill run produced logs + summary.json, auth/runtime/OSS/health drills passed, the grep gate stayed green, diagnostics were clean, and db_migration surfaced the existing Alembic revision gap (`20260412_0315_028`) as explicit recovery evidence instead of a silent script failure.
  success signal status: downstream recovery/deploy work can now consume one executable authority surface instead of markdown-only guidance — scripts, docs, and evidence all point at the same baseline + runner seam, and the current local migration blocker is already captured in machine-readable output.
  rollback note: if later work changes any drill command, update scripts/recovery_drill_baseline.py, scripts/recovery_drill_runner.py, both hyphenated CLI entrypoints, the focused runner/bootstrap tests, and the runbook/current-state docs together; otherwise the executable recovery surface and the written guidance will drift again.

- time: 2026-04-14T09:36:59.952541+08:00
  mode: grow
  item id: M021-S01-T01
  files changed:
    - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
    - .gsd/milestones/M021/M021-CONTEXT-DRAFT.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Wrote the first M021 live AI authority inventory into the architecture scan and milestone context draft so downstream slices stop guessing which AI seams are truly live. The new map distinguishes the StepFun/session-snapshot runtime authority, the compat-owned knowledge-answer rollout seam, PromptTemplateService governance helpers, and the still-shipped compatibility scoring/comprehensive-report stack.
  verification commands:
    - rg -n "PromptTemplateService|generate_report|evaluate\(|stepfun|knowledge_answer|voice_instruction|compiled" backend/src/sales_bot backend/src/evaluation backend/src/prompt_templates backend/src/common backend/src/presentation_coach
    - rg -n "M021/S01 live AI authority inventory|live rollout seam|compat enhancement / retire candidate|shadow by default; live only when enabled" .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md && test -f .gsd/milestones/M021/M021-CONTEXT-DRAFT.md
  verification results: passed; the exact task-plan grep gate stayed green across the intended source trees, the architecture scan now exposes the concrete M021/S01 live/compat/shadow labels, and the milestone context content is persisted as CONTEXT-DRAFT because the final CONTEXT artifact is depth-gated rather than safely writable in auto-mode.
  success signal status: future M021 work can now cite one truthful AI authority map instead of rediscovering whether StepFun, PromptTemplateService, knowledge-answer engine rollout, classic scoring, or comprehensive-report paths are live, compat, or shadow.
  rollback note: if later slices promote the engine to always-live, retire classic voice mode, or replace comprehensive-report/report_status consumers, update the architecture scan AI inventory and the M021 context artifact together so the authority map does not drift.

- time: 2026-04-14T09:44:43+08:00
  mode: grow
  item id: M021-S01-T02
  files changed:
    - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
    - docs/api-contract/sessions.md
    - docs/api-contract/prompt-templates.md
    - backend/tests/integration/test_voice_runtime_session_snapshot.py
    - backend/tests/unit/common/test_knowledge_answer_feature_flag.py
    - backend/tests/unit/test_report_generation_trigger.py
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Turned the T01 AI authority inventory into durable proof and contract language: the live StepFun/session-snapshot path, the compat-owned knowledge-answer rollout seam, and the compat report-generation sidecar are now named directly in focused tests, while sessions/prompt-templates/support-runtime docs and the architecture scan now say which consumers belong to the live runtime line versus compat helper/report surfaces.
  verification commands:
    - backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_voice_runtime_session_snapshot.py::test_start_session_persists_voice_policy_snapshot backend/tests/integration/test_voice_runtime_session_snapshot.py::test_snapshot_baseline_is_immutable_and_report_replay_refer_same_baseline backend/tests/unit/common/test_knowledge_answer_feature_flag.py backend/tests/unit/test_report_generation_trigger.py -q
    - rg -n "live|compat|shadow|retire|authority" .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md docs/api-contract backend/tests
    - lsp diagnostics backend/tests/integration/test_voice_runtime_session_snapshot.py
    - lsp diagnostics backend/tests/unit/common/test_knowledge_answer_feature_flag.py
    - lsp diagnostics backend/tests/unit/test_report_generation_trigger.py
  verification results: passed after one syntax-only fix to the touched knowledge-rollout test file; the focused pytest bundle finished 15/15 green, the exact task-plan grep gate exposes live/compat/shadow/authority wording across analysis/docs/tests, and LSP diagnostics were clean on all touched Python proof files.
  success signal status: downstream M021 work no longer has to infer consumer ownership from the raw inventory table alone — the live runtime/read-side contract is now documented in sessions/support-runtime, the governance-vs-runtime prompt boundary is explicit in prompt-templates, and the focused proof files explain which authority path each assertion is locking.
  rollback note: if later slices promote PromptTemplateService into the live runtime contract, retire the legacy evaluation/report sidecar, or change which read-side surfaces consume the frozen session snapshot, update the focused proof docstrings/comments, the two api-contract docs, and the architecture scan consumer-sync bullets together so proof language and shipped authority stay aligned.

- time: 2026-04-14T12:41:43.712765+08:00
  mode: grow
  item id: M021-S04-T03
  files changed:
    - docs/api-contract/support-runtime.md
    - web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
    - web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx
    - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Wrote the S04 runtime-event read-side back into durable support/runtime and architecture docs, and strengthened report/replay proof so compat-reader score fallbacks and retrieval failure states stay explicit instead of being misread as canonical or low-quality success.
  verification commands:
    - npm --prefix web test -- --run "src/app/(user)/practice/[sessionId]/report/page.test.tsx" "src/app/(user)/practice/[sessionId]/replay/page.test.tsx"
    - rg -n "quality|cost|failure|degraded|compat" docs/api-contract/support-runtime.md .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
  verification results: passed; the exact T03 web bundle finished 39/39 green, the new tests prove report/replay explicitly label compatibility-reader rollups and keep retrieval search_failed copy from collapsing into hit/miss success text, and the grep gate now exposes the runtime-event read rules directly in the intended long-lived docs.
  success signal status: future agents no longer need to infer support/runtime event semantics or UI fallback meaning from scattered code — the docs say how to read mode/degraded/failure/cost events, and the front-end proof locks compat/failure presentation in place.
  rollback note: if later slices change runtime_event fields, compat score source handling, or the learner-facing degradation copy, update support-runtime.md, the architecture scan read-side bullets, and the focused report/replay assertions together so documentation and proof keep matching the shipped UI/runtime semantics.

- time: 2026-04-14T16:31:10+08:00
  mode: grow
  item id: M022-S04-T02
  files changed:
    - .gsd/plans/GSD_PLAN_post-M018-next-wave.md
    - .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
    - .gsd/DECISIONS.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Finished M022/S04/T02 by turning the org/team/tenant target-state matrix into a concrete modular-monolith migration contract. The post-M018 plan and next-wave architecture scan now both say the same thing: keep the runtime inside the monolith, add organization/team compatibility readers to session/report/replay/history/admin truth surfaces first, move authz onto membership + scope readers before changing global-role semantics, keep agent/persona/knowledge/prompt/runtime assets on global-template plus org-rollout-binding seams instead of cloning org-owned rows, and treat future SSO/CRM/org sync integrations as metadata/provisioning adapters rather than new runtime authorities.
  verification commands:
    - rg -n "migration path|organization|team|tenant|SSO|CRM|org sync|compatibility reader" .gsd/plans/GSD_PLAN_post-M018-next-wave.md .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
  verification results: passed; the exact task-plan grep gate exited 0 and matched the new migration path, compatibility-reader surfaces, service-split trigger, and future integration-slot language in both durable planning artifacts.
  success signal status: future enterprise/org-boundary work can now start from one explicit ordering rule — scope readers first, authz seam second, rollout binding third, external integration automation last — without reinterpreting the T01 matrix or accidentally promoting SSO/CRM/org sync into present-tense product scope.
  rollback note: if later slices change the migration order or promote org-owned assets/service split sooner, update the M022/S04 sections in both durable docs and the architectural decision together so downstream roadmap work does not fork the org-boundary story.


- time: 2026-04-14T16:44:24+08:00
  mode: grow
  item id: M022-S04
  files changed:
    - .gsd/milestones/M022/slices/S04/S04-SUMMARY.md
    - .gsd/milestones/M022/slices/S04/S04-UAT.md
    - .gsd/PROJECT.md
    - .codex/loop/state.json
    - .codex/loop/log.md
  summary: Closed M022/S04 by compressing T01-T03 into the canonical slice summary/UAT artifacts and refreshing project state. The slice now gives downstream milestone and roadmap work one durable enterprise contract: organization is the account/authz/analytics boundary, team is the coaching cohort boundary, member is the membership seam, tenant remains a future heavier isolation slot, org/team rollout stays reader-first inside the modular monolith, and SSO/CRM/org-sync remain provisioning adapters until real internal org/member/team seams exist.
  verification commands:
    - rg -n "user_id|role|owner|agent_id|persona_id|knowledge_base|organization|tenant|team" backend/src/common backend/src/admin web/src/app/admin .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
    - rg -n "migration path|organization|team|tenant|SSO|CRM|org sync|compatibility reader" .gsd/plans/GSD_PLAN_post-M018-next-wave.md .gsd/analysis/ARCHITECTURE_SCAN_2026-04-13_next-wave.md
    - rg -n "organization|team|tenant|monolith|service split|out-of-scope|SSO|CRM" .gsd/plans/GSD_PLAN_post-M018-next-wave.md .codex/roadmap/PROJECT_FUTURE.md
  verification results: passed; all three slice-plan grep gates exited 0 and confirmed the current global-user seams, the reader-first migration path, and the downstream roadmap/service-split guardrails in the durable planning artifacts before slice completion.
  success signal status: M022 now has all four slices complete, and future enterprise planning can start directly from the S04 contract instead of rerunning a repository-wide org-boundary investigation.
  rollback note: if later work changes organization/member/team ownership, service-split pressure, or integration authority, update the architecture scan, post-M018 plan, future roadmap, decisions, knowledge note, and focused verification bundle together so the enterprise contract does not drift.
