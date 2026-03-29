---
id: M008
title: "检索事实链收口"
status: complete
completed_at: 2026-03-29T19:34:16.169Z
key_decisions:
  - Persist a bounded, provider-neutral retrieval ledger in `voice_policy_snapshot.runtime_metrics.knowledge_retrieval.recent_attempts` via the existing runtime-metrics persistence seam.
  - Reject malformed persisted `recent_attempts` during snapshot merge and preserve copy-on-write snapshot semantics instead of half-writing invalid retrieval state.
  - Keep flat retrieval `last_*` fields backward-compatible and use the latest valid ledger entry only as a fallback for stale or missing flat fields.
  - Normalize completed-session retrieval truth through a single `build_retrieval_facts(voice_policy_snapshot)` pure function.
  - Attach `retrieval_facts` through a sales-gated projection overlay and diagnostics passthrough for completed sessions while leaving live-session truth with the live handler.
  - Render learner-facing retrieval truth from the canonical report payload and keep `/knowledge-check` supplemental-only on the report page.
key_files:
  - backend/src/common/conversation/runtime_diagnostics.py
  - backend/src/common/conversation/session_evidence.py
  - backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py
  - backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py
  - backend/src/sales_bot/websocket/components/stepfun_runtime_metrics_helpers.py
  - backend/src/sales_bot/websocket/stepfun_realtime_handler.py
  - backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py
  - backend/tests/unit/test_session_evidence_service.py
  - backend/tests/contract/test_practice_evidence_contract.py
  - backend/tests/integration/test_voice_runtime_session_snapshot.py
  - web/src/lib/api/types.ts
  - web/src/lib/session-evidence.ts
  - web/src/app/(user)/practice/[sessionId]/report/page.tsx
  - web/src/app/(user)/practice/[sessionId]/report/page.test.tsx
lessons_learned:
  - Backward-compatible projection overlays are a safer way to add new audit facts to shipped route families than widening live public contracts.
  - Retrieval occurrence and claim truth must stay orthogonal; tying a `hit` directly to `evidence_verified` would recreate the fake-credibility problem.
  - Canonical report payloads should own learner-visible report facts; optional supplemental fetches must never be allowed to hide core evidence sections.
  - Copy-on-write snapshot merges plus malformed-payload rejection prevent frozen snapshot references from drifting under runtime-metrics churn.
---

# M008: 检索事实链收口

**M008 closed the retrieval-truth gap by persisting auditable retrieval ledger facts, making report and knowledge-check share one normalized retrieval view, and surfacing that truth on the learner report page.**

## What Happened

M008 closed the gap between “knowledge base is configured” and “retrieval truth is auditable” on the shipped route family.

S01 persisted a bounded, provider-neutral retrieval ledger under `voice_policy_snapshot.runtime_metrics.knowledge_retrieval.recent_attempts`, kept the flat `last_*` fields backward-compatible, and added read-side fallback so current-session diagnostics can still explain hit/miss/search_failed truth when the flat fields are stale or missing.

S02 established `build_retrieval_facts(voice_policy_snapshot)` as the single normalizer for completed-session retrieval truth and wired it through a sales-gated, copy-on-write `SessionEvidenceService.build_projection()` overlay plus diagnostics passthrough. That made `/api/v1/practice/sessions/{id}/knowledge-check` and `/api/v1/practice/sessions/{id}/report` return the same retrieval facts for the same completed sales session without mutating persisted snapshots.

S03 surfaced those canonical retrieval facts on `web/src/app/(user)/practice/[sessionId]/report/page.tsx`, reading from `effectiveness_snapshot.retrieval_facts` instead of depending on the optional `/knowledge-check` supplemental fetch. The report page now shows KB binding, retrieval status, latest attempt, hit/miss/search_failed explanations, and weak-evidence notes while continuing to suppress the section for PPT sessions.

Fresh close-out verification reran the focused proof for the chain:
- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/test_runtime_diagnostics_knowledge_retrieval.py backend/tests/unit/test_session_evidence_service.py backend/tests/contract/test_practice_evidence_contract.py backend/tests/integration/test_voice_runtime_session_snapshot.py` → **60 passed**
- `pnpm --dir web exec vitest run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'` → **17 passed**
- `git diff --stat HEAD $(git merge-base HEAD 001-ai-practice-system) -- ':!.gsd/'` → non-`.gsd` implementation changes present, including the backend retrieval seams and learner report UI files.

## Decision Re-evaluation

| Decision | Re-evaluation | Status | Revisit next milestone? |
| --- | --- | --- | --- |
| D112 | Prioritizing the auditable training chain before wider workflow expansion still matches the product state. M008 retired the retrieval-truth gap and leaves a clean handoff to audio/provenance work. | Valid | No |
| D113 | Keeping proof on the current `knowledge-check` / report / replay route family was correct. M008 landed on those shipped surfaces instead of inventing a side audit console. | Valid | No |
| D114 / D116 | Not inferring `used_in_reasoning` remains correct. M008 can prove retrieval occurrence and returned evidence, but it still cannot prove model grounding honestly. | Valid | Yes — revisit in M010 only if provenance becomes strong enough |
| D115 / D117 | Persisting a bounded, provider-neutral retrieval ledger in `voice_policy_snapshot.runtime_metrics.knowledge_retrieval` proved durable and small enough for the current snapshot seam. | Valid | No |
| D118 | Reusing the existing runtime-metrics write path and rejecting malformed `recent_attempts` at merge time kept copy-on-write semantics intact and prevented half-written state. | Valid | No |
| D119 | Using the latest valid ledger entry only as a fallback for stale/missing flat `last_*` fields preserved backward compatibility while retiring snapshot drift. | Valid | No |
| D120 | A single `build_retrieval_facts()` normalizer did prevent vocabulary drift. Fresh contract and integration parity tests passed. | Valid | No |
| D121 | Sales-gated projection overlay plus diagnostics passthrough is still the right split: completed sessions share one projection truth; live sessions stay handler-owned. | Valid | No |
| D122 | Using canonical report payload data for the learner retrieval section was correct. Fresh web tests show retrieval truth survives supplemental `/knowledge-check` failure and PPT remains clean. | Valid | No |


## Success Criteria Results

## Success criteria audit

The rendered roadmap for M008 contains no standalone `Success Criteria` section, so verification was performed against the milestone vision and the three acceptance outcomes encoded in the slice overview.

- **Persisted session snapshot can explain whether retrieval happened, what was searched, what came back, and why miss/failure occurred.** Met. S01 delivered a bounded provider-neutral ledger in `voice_policy_snapshot.runtime_metrics.knowledge_retrieval.recent_attempts`, preserved backward-compatible flat metrics, and added diagnostics fallback. Fresh evidence: the close-out backend pack passed 60 tests, including `test_build_session_runtime_diagnostics_uses_latest_valid_ledger_entry_for_search_failures_when_flat_fields_missing`, `test_build_session_runtime_diagnostics_ignores_malformed_recent_attempts_and_uses_latest_valid_event`, `test_knowledge_check_reads_latest_valid_ledger_entry_when_flat_last_fields_are_missing`, and `test_knowledge_check_reports_kb_not_ready_status`.
- **Completed-session `knowledge-check` and canonical report return the same retrieval truth.** Met. S02 wired `build_retrieval_facts()` through projection overlay and diagnostics passthrough. Fresh evidence: the close-out backend pack passed contract/integration parity checks `test_report_and_knowledge_check_return_identical_retrieval_facts_for_completed_sales_session`, `test_retrieval_facts_parity_with_miss_status`, and `test_completed_sales_session_returns_identical_retrieval_facts_through_report_and_knowledge_check`.
- **Learner report page shows retrieval truth directly on the current report surface.** Met. S03 rendered retrieval facts from `effectiveness_snapshot.retrieval_facts`, kept `/knowledge-check` supplemental-only, and continued to suppress the section for PPT sessions. Fresh evidence: `pnpm --dir web exec vitest run 'src/app/(user)/practice/[sessionId]/report/page.test.tsx'` passed 17/17, covering retrieval `hit`, `miss`, `search_failed`, malformed guards, coexistence with weak-evidence claim truth, and PPT suppression.


## Definition of Done Results

## Definition of done audit

- **All slices complete.** Met. `M008-ROADMAP.md` shows S01, S02, and S03 as `✅`.
- **All slice artifacts exist.** Met. Filesystem audit found `S01/S02/S03` `PLAN`, `SUMMARY`, and `UAT` artifacts, plus all task summaries (`T01-T03` for S01, `T01-T04` for S02, `T01-T02` for S03).
- **Cross-slice integration works.** Met. Fresh verification proved the end-to-end chain: S01 ledger persistence and fallback → S02 projection parity between report and knowledge-check → S03 report-page rendering from canonical report payload. Evidence: backend close-out pack **60 passed** and web close-out pack **17 passed**.
- **Real implementation code exists outside `.gsd/`.** Met. `git diff --stat HEAD $(git merge-base HEAD 001-ai-practice-system) -- ':!.gsd/'` returned non-`.gsd` backend and web changes, including `backend/src/common/conversation/runtime_diagnostics.py`, `backend/src/common/conversation/session_evidence.py`, `backend/src/sales_bot/websocket/components/stepfun_knowledge_helpers.py`, `backend/src/sales_bot/websocket/components/stepfun_internal_knowledge_searcher.py`, `backend/src/sales_bot/websocket/stepfun_runtime_metrics_helpers.py`, `backend/src/sales_bot/websocket/stepfun_realtime_handler.py`, `web/src/lib/api/types.ts`, `web/src/lib/session-evidence.ts`, and `web/src/app/(user)/practice/[sessionId]/report/page.tsx`.
- **Horizontal checklist.** None present in the rendered roadmap, so there was no additional horizontal checklist to audit.


## Requirement Outcomes

## Requirement status audit

No requirement status transitions were made in M008, so no `gsd_requirement_update` calls are required.

- **R005** remained `validated`. M008 added supporting proof by rendering canonical `effectiveness_snapshot.retrieval_facts` on the learner report page; fresh web verification passed 17/17.
- **R010** remained `validated`. M008 added supporting proof by making `GET /api/v1/practice/sessions/{id}/knowledge-check` and `GET /api/v1/practice/sessions/{id}/report` share identical `retrieval_facts` for completed sales sessions; fresh contract and integration parity tests passed.
- **R011** remained `validated`. M008 added supporting proof by persisting provider-neutral retrieval ledger entries in `voice_policy_snapshot.runtime_metrics.knowledge_retrieval.recent_attempts` and overlaying `retrieval_facts` into the completed-session projection without mutating the persisted snapshot; fresh backend verification passed.


## Deviations

One slice-local deviation occurred inside S01: T02 absorbed the unfinished T01 helper/searcher normalization work because the persistence seam needed normalized `ledger_event` payloads before ledger persistence could be proved. No milestone-level scope change followed from that deviation.

## Follow-ups

M009 should extend the same auditable-chain discipline to raw audio evidence and keep the proof on existing replay/report surfaces. M010 can revisit whether any stronger provenance seam justifies exposing a truthful `used_in_reasoning`-style contract; M008 evidence is still insufficient for that claim.
