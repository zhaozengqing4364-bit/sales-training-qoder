# M010 — Research

**Date:** 2026-03-28

## Summary

M010 should be planned as a **contract-hardening milestone on the existing evidence authority seam**, not as a report-page redesign. The strongest existing pattern in this repo is already clear: completed-session truth flows through `SessionEvidenceService`, report stays on `backend/src/common/api/practice.py`, replay stays on `backend/src/common/conversation/replay.py`, and frontend wording is supposed to stay in `web/src/lib/session-evidence.ts`. Retrieval truth (M008) and audio audit (M009) are already additive overlays on that seam; M010 should extend the same pattern for **key-conclusion provenance** and **cross-route degradation semantics**.

The first thing to prove is not a UI card. It is that **the same completed sales session can expose one identical conclusion-evidence contract on report, replay, and knowledge-check** for the key conclusion family: `main_issue`, `next_goal`, and `claim_truth`. Today the code already proves parity for `retrieval_facts` between report and knowledge-check, parity for `claim_truth` between report and replay, and parity for `audio_audit` between report and replay. What is missing is the bridge between them: a stable reference model that says which retrieval/transcript/audio facts support the conclusion, plus a single degraded taxonomy that explains where the chain is incomplete.

The natural slice order is therefore: **(1) backend contract and parity tests first, (2) degradation taxonomy second, (3) minimal frontend rendering and live proof last**. If the order is reversed, the milestone will almost certainly drift into page-local heuristics and “looks traceable” UI without actually hardening the authority seam.

## Recommendation

Take a **conclusion-level, additive contract approach**.

Do **not** try to make every suggestion or every highlight individually provenance-complete in M010. The codebase and milestone context both point toward a narrower first step: attach provenance for the canonical conclusion family (`main_issue`, `next_goal`, `claim_truth`) and let replay/highlight-specific metadata stay where it already belongs (`learning_evidence`, `replay_anchor`). This keeps scope aligned with the milestone context’s “关键结论级” leaning and avoids turning M010 into a second replay/highlight redesign.

Implementation-wise, prefer one shared backend normalizer that builds a compact **conclusion evidence bundle** from the existing sources already on the seam:
- retrieval facts from `build_retrieval_facts(...)`
- transcript/message references from normalized `ConversationMessage` / `transcript_metadata`
- audio evidence from `build_session_audio_audit(...)` (summary + segment/session references only; do not pretend exact utterance-to-audio alignment if the data is not there)
- enhanced-report degradation as an explicitly optional layer, not a blocker for canonical evidence

That bundle should be produced inside `SessionEvidenceService.build_projection()` for completed sessions and mirrored into `build_session_runtime_diagnostics(...)` for knowledge-check, so all three route families reuse the same vocabulary. Keep it additive: do not rename existing fields, do not create a second report-only endpoint, and do not infer facts like “used_in_reasoning” that M008 explicitly avoided.

## Implementation Landscape

### Key Files

- `backend/src/common/conversation/session_evidence.py` — The core authority seam. `build_projection()` already overlays `claim_truth` and `retrieval_facts` onto `effectiveness_snapshot`; `serialize_message()` already carries `transcript_metadata`, `audio_url`, `sales_stage`, highlights, and score snapshots. This is the right place to add a shared conclusion-evidence bundle and broader evidence-chain completeness/degradation logic.
- `backend/src/common/conversation/runtime_diagnostics.py` — Already owns `build_retrieval_facts(...)` and the knowledge-check diagnostics payload. This should share the same conclusion-evidence/degradation vocabulary as projection, rather than inventing a knowledge-check-only explanation model.
- `backend/src/common/api/practice.py` — Owns canonical report and knowledge-check routes. `get_session_report()` is already a thin projection passthrough; `get_session_knowledge_check()` already mixes live handler state and completed-session projection. This is the right route layer to expose the shared backend contract, but not to derive it.
- `backend/src/common/conversation/replay.py` — Already follows the additive-metadata pattern (`learning_evidence`, `replay_anchor`, `audio_audit`). Replay should consume the new conclusion evidence contract from projection and only add replay-specific decoration where needed.
- `backend/src/common/db/schemas.py` — `SessionReport` is still mostly `dict[str, Any]` for conclusion payloads, which lowers backend migration cost, but any new nested payload still needs to be reflected here or FastAPI/OpenAPI drift will be hidden.
- `backend/src/common/conversation/schemas.py` — Replay response models are stricter than the service code. Any nested provenance/degradation fields added in replay must be declared here or they will be silently filtered.
- `web/src/lib/api/types.ts` — Current web contract seam. `SessionMainIssue`, `SessionNextGoal`, `SessionClaimTruthPayload`, `ReplayAnchor`, `AudioAuditPayload`, and `PracticeSessionReport`/`ReplayData` live here. This file already shows one important drift: `KnowledgeCheckDiagnostics` is narrower than the backend payload actually returned.
- `web/src/lib/session-evidence.ts` — The right frontend place to parse and format shared evidence semantics. It already centralizes `claim_truth`, `retrieval_facts`, `evidence_completeness`, and presentation degraded copy. M010 should extend this file rather than adding new page-local wording logic.
- `web/src/app/(user)/practice/[sessionId]/report/page.tsx` — Already renders claim-truth, retrieval truth, evidence completeness, and audio audit as separate cards. This page can adopt a new shared provenance/degradation helper with relatively small UI changes.
- `web/src/app/(user)/practice/[sessionId]/replay/page.tsx` — Already renders claim-truth, evidence completeness, replay anchors, learning evidence, and audio audit, but does not currently surface retrieval truth the way report does. If user-visible parity is desired, this page likely needs a minimal read-side addition rather than a structural rewrite.
- `backend/tests/contract/test_practice_evidence_contract.py` — The lock file that matters most. It already proves report↔knowledge-check retrieval parity, report↔replay claim-truth parity, and report↔replay audio-audit parity. M010 should extend this file first before UI work.

### Build Order

1. **Prove one completed-session parity contract first.**
   Add failing contract tests that assert the same session exposes the same conclusion evidence/degradation payload on:
   - `GET /api/v1/practice/sessions/{id}/report`
   - `GET /api/v1/sessions/{id}/replay`
   - `GET /api/v1/practice/sessions/{id}/knowledge-check`
   This is the main risk retirement step. If the payload cannot be made identical here, frontend work should not start.

2. **Add one shared backend conclusion-evidence builder.**
   Implement the evidence-reference model in shared backend code (`session_evidence.py` + `runtime_diagnostics.py`), sourcing only from existing persisted facts: retrieval ledger, normalized messages/transcript metadata, and audio audit summary/segments. Keep it additive and conclusion-level.

3. **Unify degradation taxonomy before page wording.**
   Introduce one taxonomy that distinguishes at least these layers:
   - retrieval degradation
   - transcript/message-reference degradation
   - audio-evidence degradation
   - enhanced-report degradation
   The key requirement is that optional enhanced-report failures remain explicitly optional and do not overwrite the canonical evidence line.

4. **Update response models and frontend shared types/helpers in the same step.**
   This codebase has already been burned by FastAPI response-model trimming. Backend service changes without `schemas.py` / `types.ts` updates are not real changes.

5. **Only then add minimal report/replay rendering and one live consistency proof.**
   The frontend should read the new shared contract through `web/src/lib/session-evidence.ts`, not derive provenance from local state, stage names, or highlight copy.

### Verification Approach

Backend contract-first verification:
- `backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/contract/test_practice_evidence_contract.py backend/tests/integration/test_replay_api.py -v`

Frontend focused verification:
- `npm test -- --run "web/src/app/(user)/practice/[sessionId]/report/page.test.tsx" "web/src/app/(user)/practice/[sessionId]/replay/page.test.tsx"`

Key proof points:
- one session’s `main_issue` / `next_goal` / `claim_truth` can each point back to retrieval/transcript/audio references without inventing a new truth source
- knowledge-check uses the same degraded vocabulary as report/replay for the same missing layer
- optional enhanced-report failure remains visibly degraded but does not erase canonical evidence references
- replay remains completion-gated; do not weaken lifecycle truth to make proof easier

For live/UAT proof, the success condition is not “nice UI”. It is: **the same session lets a reviewer compare report, replay, and knowledge-check and see the same conclusion provenance and the same explanation of what is missing.**

## Don't Hand-Roll

| Problem | Existing Solution | Why Use It |
|---------|------------------|------------|
| Retrieval truth normalization | `build_retrieval_facts(...)` in `backend/src/common/conversation/runtime_diagnostics.py` | Already locked by M008 contract tests; re-deriving retrieval semantics elsewhere will recreate drift. |
| Completed-session authority | `SessionEvidenceService.build_projection()` | This is already the canonical report/replay/history seam; M010 should extend it, not route around it. |
| Learner-facing audio evidence | `build_session_audio_audit(...)` in `backend/src/common/api/practice.py` | Already gives shared report/replay audio truth and degraded reasons; no need for a second audio summary model. |
| Additive replay metadata | `learning_evidence` and `replay_anchor` patterns | This repo already uses nested additive metadata without replacing top-level conclusion fields. M010 should follow the same pattern. |
| Frontend evidence wording | `web/src/lib/session-evidence.ts` | Centralizing wording there is the existing anti-drift seam. |

## Constraints

- `SessionEvidenceService` must remain the report authority; do not add a second report truth source.
- M008 decisions explicitly rejected inferred `used_in_reasoning`; M010 must not reintroduce that claim through provenance wording.
- Replay must stay completion-gated. Do not loosen the gate just to make route-family parity easier.
- Knowledge-check uses live handler state when runtime is active and projection fallback only for completed sessions. Any new contract must preserve that split.
- Audio audit currently proves segment/session-level evidence, not exact utterance-to-waveform alignment. First-version provenance should be honest about that granularity.
- Response-model filtering is a known local failure mode: backend service changes are incomplete until `backend/src/common/db/schemas.py`, `backend/src/common/conversation/schemas.py`, and `web/src/lib/api/types.ts` are updated too.

## Common Pitfalls

- **Re-deriving truth in pages** — The report/replay pages already consume shared helpers. If M010 computes provenance from local `stage_name`, highlight text, or ad hoc route state, it will drift from the backend seam.
- **Treating claim truth as equivalent to retrieval truth** — Existing contract tests already prove they are orthogonal. Retrieval can hit while claim truth remains `weak_evidence`.
- **Overloading `evidence_completeness` with all degradation semantics** — Current `evidence_completeness` is broad and coarse. M010 likely needs a more explicit layered taxonomy rather than burying all reasons in `missing_fields`.
- **Trying to make audio provenance too precise** — The current system can truthfully reference uploaded segments and playback paths, but not necessarily exact sentence offsets. Pretending otherwise will recreate fake credibility.
- **Forgetting frontend contract drift on knowledge-check** — `web/src/lib/api/types.ts` currently understates the backend knowledge-check payload. M010 should not pile more raw fields on top of an already stale TS type.

## Open Risks

- Transcript provenance may require a new normalized reference shape (message ID / turn / snippet / transcript_metadata path) because the current payload has transcript metadata but not a first-class conclusion-reference object.
- If planners try to make replay show every provenance layer exactly the way report does, scope could grow into a replay-page redesign. The safer first step is parity of contract and vocabulary, with minimal UI surfacing.
- Knowledge-check may need only compact audio provenance/degradation signals, not the full `audio_audit.segments` payload. That is a likely slice decision, not yet proven.

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| FastAPI | `fastapi-python` | preinstalled |
| React / Next.js | `react-best-practices` | preinstalled |
| SQLAlchemy | `bobmatnyc/claude-mpm-skills@sqlalchemy-orm` | installed globally for later units |

## Candidate Requirement Clarifications

- **Likely table-stakes within existing R027/R028:** provenance for `main_issue`, `next_goal`, and `claim_truth`; explicit layered degradation across retrieval/transcript/audio/enhanced-report; no silent “complete-looking” fallback.
- **Likely optional, not first-wave requirements:** per-suggestion provenance, a standalone evidence explorer, exact audio-to-utterance alignment, or replay-only bespoke provenance workflows.
- **Candidate requirement if the user wants stronger learner parity:** replay should surface retrieval provenance with the same vocabulary as report, not just carry it silently in backend payloads.
