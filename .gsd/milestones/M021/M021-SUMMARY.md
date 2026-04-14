---
id: M021
title: "AI control plane / prompt / evaluation kernel 统一"
status: complete
completed_at: 2026-04-14T05:00:20.999Z
key_decisions:
  - D230 — keep using the live/compat/retire matrix as the execution authority for AI control-plane unification
  - D231 — keep StepFun realtime plus compiled voice policy/session snapshot as the live AI runtime authority
  - D232 — keep sessions/prompt-template/support-runtime docs as the durable consumer-facing authority bundle
  - D233 — keep the code-owned prompt taxonomy as the prompt control-plane authority map
  - D234 — keep compiling PromptTemplateService output into hashed CompiledPromptContract artifacts before legacy evaluation/report model calls
  - D235 — keep prompt authority split across prompt-templates, voice-runtime, personas, and model-config repair surfaces
  - D236 — keep one shared logic/accuracy/completeness rollup contract while allowing scenario-aware canonical dimension catalogs
  - D237 — keep canonical_evaluation_kernel plus compatibility_readers during migration instead of a flag-day field replacement
  - D238 — keep one shared frontend fallback order: canonical_evaluation_kernel -> compatibility_readers -> legacy rollups
key_files:
  - backend/src/prompt_templates/service.py
  - backend/src/common/ai/llm_service.py
  - backend/src/common/effectiveness/canonical.py
  - backend/src/common/conversation/session_evidence.py
  - backend/src/common/analytics/history_service.py
  - backend/src/common/conversation/replay.py
  - backend/src/common/knowledge_engine/runtime_events.py
  - backend/src/support/services/runtime_status_service.py
  - web/src/lib/session-evidence.ts
  - web/src/app/(user)/practice/[sessionId]/report/page.tsx
  - web/src/app/(user)/practice/[sessionId]/replay/page.tsx
  - web/src/app/(dashboard)/history/page.tsx
  - docs/api-contract/prompt-templates.md
  - docs/api-contract/support-runtime.md
lessons_learned:
  - Milestone close-out in this repo must verify against the real integration branch (`001-ai-practice-system` here), not `main`.
  - A summary-level evidence gap is not the same as a delivery failure; discharge it with fresh code/test proof across the actual seam before deciding milestone status.
  - Compiled prompt contracts, canonical evaluation kernels, and runtime events only stay trustworthy when docs, backend projection code, frontend readers, and focused proofs move together.
---

# M021: AI control plane / prompt / evaluation kernel 统一

**Unified the AI control plane around one live authority inventory, one compiled prompt contract seam, one canonical evaluation kernel, and one inspectable runtime-event truth line.**

## What Happened

M021 finished the four-part AI control-plane convergence that had been split across live StepFun runtime, legacy prompt/evaluation helpers, score read models, and quality/cost/degradation diagnostics.

- **S01** locked the live authority inventory so later work would stop targeting the wrong seam. The project now has an explicit live/compat/shadow/retire map for realtime runtime, prompt control, knowledge-answer rollout, and legacy evaluation/report surfaces.
- **S02** turned prompt-template governance into a real runtime-adjacent contract by compiling legacy evaluation/report prompts into hashed `CompiledPromptContract` artifacts before model calls, with fail-closed diagnostics for missing vars, empty renders, missing `base_url`, and generation failures.
- **S03** converged learner/admin score truth onto `canonical_evaluation_kernel` plus `compatibility_readers`, while keeping legacy rollups as migration mirrors rather than independent truth.
- **S04** unified AI quality/cost/failure/provenance onto one allowlist-safe `runtime_events` line so degraded/failure/compat state is inspectable instead of inferred from default scores or fallback copy.

## Fresh verification
- `git diff --stat HEAD $(git merge-base HEAD 001-ai-practice-system) -- ':!.gsd/'` confirmed real non-`.gsd` implementation work exists on this branch.
- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/integration/test_voice_runtime_session_snapshot.py backend/tests/unit/common/test_knowledge_answer_feature_flag.py backend/tests/unit/test_report_generation_trigger.py backend/tests/unit/prompt_templates/test_compiled_prompt_contract.py backend/tests/unit/test_effectiveness_canonical_kernel.py backend/tests/unit/test_history_service_evidence_projection.py backend/tests/unit/test_replay_service.py backend/tests/unit/test_ai_quality_event_inventory.py backend/tests/unit/test_support_runtime_service.py backend/tests/contract/test_support_runtime.py backend/tests/integration/test_support_runtime_api.py -q` passed **86/86**.
- `rg -n "compile_runtime_prompt_contract|CompiledPromptContract|canonical_evaluation_kernel|compatibility_readers|runtime_events|path_mode" backend/src web/src docs/api-contract -S` confirmed the assembled authority seams are still present across backend, web, and contract docs.
- LSP diagnostics were clean on the key authority files for prompt control, canonical evaluation, and support-runtime read models.

## Decision Re-evaluation
| Decision | Re-evaluation | Next milestone? |
|---|---|---|
| D230 | Still valid. S02-S04 all honored the keep/compat/retire matrix instead of promoting compat surfaces back to live authority. | No |
| D231 | Still valid. Live runtime authority remains StepFun realtime plus compiled voice runtime policy/session snapshots. | No |
| D232 | Still valid. Consumer-facing docs remain aligned to the real seams and were useful during close-out verification. | No |
| D233 | Still valid. The prompt taxonomy remains the clearest authority map for live vs legacy prompt surfaces. | No |
| D234 | Still valid. Compiled prompt contracts are now the real legacy evaluation/report handoff seam and stayed green in focused verification. | No |
| D235 | Still valid. Distinguishing prompt-template, voice-runtime, persona, and model-config authority prevented operator confusion during convergence. | No |
| D236 | Still valid. Shared logic/accuracy/completeness rollups plus scenario-aware dimension catalogs held up in canonical-kernel tests. | No |
| D237 | Valid now, but should be revisited when future work is ready to retire compatibility readers. | Yes |
| D238 | Valid now, but should be revisited when every frontend consumer can stop reading compat/legacy fallback fields. | Yes |

## Success Criteria Results

- [x] **AI authority inventory is explicit.** S01 established and preserved the live / compat / shadow / retire-candidate map; the milestone-close 86-test bundle re-passed the StepFun session snapshot, knowledge rollout, and report-trigger proofs, and the authority grep still shows the intended seam vocabulary across backend, web, and docs.
- [x] **Compiled prompt control really drives a shipped path.** `PromptTemplateService.compile_runtime_prompt_contract(...)` still feeds staged evaluation and comprehensive report execution; the focused compiled-prompt tests passed and the docs continue to route operators to prompt templates vs voice runtime vs model-config repair correctly.
- [x] **Canonical evaluation kernel is shared across realtime/report/replay/history/admin.** `canonical_evaluation_kernel` and `compatibility_readers` remain present in realtime scoring, evidence projection, replay, history, and frontend readers; kernel/projection/replay tests all passed.
- [x] **Quality/cost/failure/provenance are explicit on one runtime-event line.** `runtime_events` and `path_mode=live|compat` remain wired through knowledge diagnostics, `LLMService`, support-runtime surfaces, and frontend/read-side proofs; runtime/support tests all passed.
- [x] **Cross-slice assembly holds together.** Fresh milestone-close verification covered the S01->S04 seams in one test bundle and resolved the earlier summary-only handoff concern on S02 -> S03 with current code/test evidence.
- [x] **No planning-only close-out.** The branch contains substantial non-`.gsd` implementation work relative to the real integration branch (`001-ai-practice-system`).

## Definition of Done Results

- [x] **All slices complete:** `gsd_milestone_status` reports S01-S04 all `complete`, each with 3/3 tasks done.
- [x] **Slice summaries exist:** `find .gsd/milestones/M021 -maxdepth 3 \( -name 'M021-SUMMARY.md' -o -name 'S*-SUMMARY.md' -o -name '*UAT.md' -o -name '*VALIDATION.md' \) | sort` confirmed `S01-SUMMARY.md`, `S02-SUMMARY.md`, `S03-SUMMARY.md`, `S04-SUMMARY.md`, all four `S##-UAT.md` files, and `M021-VALIDATION.md`.
- [x] **Real code shipped:** `git diff --stat HEAD $(git merge-base HEAD 001-ai-practice-system) -- ':!.gsd/'` returned substantial non-`.gsd` backend/web/docs/test changes, so this milestone was not planning-only.
- [x] **Cross-slice integration works:** the assembled milestone-close pytest bundle passed **86/86** across S01 authority proofs, S02 compiled prompt contracts, S03 canonical evaluation kernel/read-side projections, and S04 runtime/support diagnostics.
- [x] **Key authority files are clean:** LSP diagnostics reported `No diagnostics` for `backend/src/prompt_templates/service.py`, `backend/src/common/effectiveness/canonical.py`, and `backend/src/support/services/runtime_status_service.py`.
- [x] **Horizontal checklist:** none was present in the roadmap/validation packet; close-out explicitly verified the slice-overview outcomes instead of inventing extra checklist items.

## Requirement Outcomes

No requirement status transitions were made during M021 close-out. The system event for this unit listed Requirements Advanced / Validated / Invalidated as `None`, milestone verification found no requirement IDs needing status changes, and no `gsd_requirement_update` calls were required.

## Deviations

None. The milestone shipped the planned four-slice convergence without changing scope; the only mid-closeout adjustment was revalidating the milestone after replacing an earlier summary-level evidence gap with fresh code/test proof.

## Follow-ups

1. Start the post-M021 retirement plan for remaining compatibility readers and legacy evaluation/report surfaces only after every learner/admin/support consumer proves it no longer depends on compat fallback.
2. Add a dedicated operator-facing surface for compiled prompt diagnostics / contract-hash drift if prompt-control failures need faster triage than logs + support/runtime allow today.
3. Keep the M020 recovery drill follow-up active: repair the Alembic graph drift around revision `20260412_0315_028`, then rerun the same repo-local recovery drills until `db_migration` turns green as well.
