---
verdict: needs-remediation
remediation_round: 0
---

# Milestone Validation: M003

## Success Criteria Checklist
- [x] Criterion 1 — evidence: S02 moved Persona pressure into a canonical nested `customer_pressure` contract, froze it into `PracticeSession.voice_policy_snapshot`, and kept it on the current admin → `POST /api/v1/practice/sessions` → practice runtime authority chain; S05’s live same-session proof further showed `customer_pressure_source="explicit"` plus bound knowledge-base context on the accepted routes.
- [ ] Criterion 2 — gap: S01 locked the seven-status learner/admin vocabulary and S05 proved the same-session `knowledge-check.status="hit"` plus a readable canonical report with explicit fallback copy, but the accepted replay leg never completed on that same proof session. The session stayed `status="scoring"`, `/api/v1/sessions/{id}/replay` returned `[SESSION_NOT_COMPLETED]`, and `/practice/{sessionId}/replay` fell back to `统一训练证据不可用`, so the full practice → knowledge-check / report / replay surface proof is still incomplete.
- [x] Criterion 3 — evidence: S02 froze Persona pressure direction into the session snapshot, S03 persisted one unresolved objection ledger across topic drift and reconnect, and S05’s live runtime proof kept ROI / evidence pressure visible on the same session instead of reverting to generic prompt chat.
- [x] Criterion 4 — evidence: the slice summaries show product changes stayed on the accepted current-route backend/web directories (`backend/src/agent/`, `backend/src/sales_bot/`, `backend/src/common/knowledge/`, `backend/src/common/conversation/`, `backend/src/common/api/`, `web/src/app/admin/`, `web/src/app/(user)/practice/`) with supporting tests/docs only; no Silence / Conda / `.env` / lockfile work was promoted into the milestone.

## Slice Delivery Audit
| Slice | Claimed | Delivered | Status |
|-------|---------|-----------|--------|
| S01 | Lock the real admin Persona/knowledge → session create → practice → knowledge-check/report/replay chain and the live seven-status knowledge vocabulary. | Summary and verification show the current entry chain, replay ownership seam, seven public statuses, and inventory/spike blocker were all locked to current routes/modules. | pass |
| S02 | Freeze Persona pressure into `voice_policy_snapshot` and make current admin Persona surfaces edit/audit the model. | Summary and UAT show nested `customer_pressure` editing/audit on current admin pages plus per-session frozen snapshot fields and stable snapshot refs after later edits. | pass |
| S03 | Keep one unresolved objection alive across topic drift/reconnect and carry it onto report/replay conclusions. | Summary and UAT show ledger persistence in `transcript_metadata`, reconnect-safe restore, ledger-aware runtime coaching, and report/replay `main_issue` / `next_goal` preference for the latest open objection. | pass |
| S04 | Distinguish unsupported / pending / weak / verified claim truth on current realtime/report/replay surfaces without a second evaluator. | Summary and UAT show canonical `effectiveness_snapshot.claim_truth` across evaluator/session evidence, live StepFun diagnostics, knowledge-check, and learner report/replay cards while keeping kb-lock chain failures diagnostic-only. | pass |
| S05 | Prove one real admin → practice → report/replay run on current routes and capture degraded-state guardrails. | Delivered the real admin → practice → knowledge-check → canonical report proof and explicit degraded-state guardrails, but the same-session replay/highlights leg remained blocked behind `status="scoring"` and `[SESSION_NOT_COMPLETED]`. | gap |

## Cross-Slice Integration
- S01 → S02 aligned: the locked current entry chain and seven-status vocabulary were consumed by S02’s snapshot freeze work on the existing admin/session-create/runtime seam.
- S02 → S03 aligned: the frozen `voice_policy_snapshot.customer_pressure` contract became the stable pressure baseline for the unresolved-objection ledger and reconnect restore path.
- S03 → S04 aligned: the persisted objection ledger and closure states fed the canonical claim-truth classification without changing stable report/replay keys.
- The material boundary mismatch appears at S04 → S05 / final acceptance: S05 successfully consumed the shared claim-truth contract and objection ledger on one same-session proof, but post-end scoring finalization did not carry that same evidence into `/api/v1/sessions/{id}/replay` (and sibling highlights). Upstream integrations are working; the broken seam is the scoring-finalization / replay-completion handoff at the end of the accepted chain.

## Requirement Coverage
- R010 is the active requirement owned by M003, and it is addressed across S01-S05: route inventory/contract lock (S01), frozen Persona pressure (S02), reconnect-safe objection persistence (S03), claim-truth alignment (S04), and live same-session proof (S05).
- R010 is not yet validated because the accepted same-session chain still stops at replay/highlights when objection-heavy sessions remain `status="scoring"` after `report_generation_failed [NO_STAGE_RESULTS]` / `no_scoring_context_available`.
- Other active requirements (`R009`, `R011`, `R012`) remain owned by other milestones/slices (`M002`, `M004`, `M005`) and do not introduce a separate M003 coverage gap in this validation pass.

## Verdict Rationale
M003 cannot be sealed yet. S01-S04 substantiate the roadmap’s technical seams, and S05 provides a real same-session proof that the admin Persona/knowledge → practice → knowledge-check → canonical report chain now behaves like the intended objection-heavy customer. But the roadmap’s accepted chain explicitly includes replay, and the live proof shows that same-session replay is still blocked by post-end scoring finalization. That is a material milestone-level gap, not a minor note, because the replay route is part of both the success criteria and the acceptance boundary. The blocker is narrow and well evidenced, so remediation should focus on the scoring-finalization / replay-completion seam rather than reworking earlier slices.

## Remediation Plan
- **S06: scoring 收口与 replay/highlights 解锁** — fix the current post-end scoring/report finalization path so the same objection-heavy proof session transitions from `status="scoring"` to `status="completed"`, `/api/v1/sessions/{id}/replay` and `/api/v1/sessions/{id}/highlights` return same-session evidence instead of `[SESSION_NOT_COMPLETED]`, and `/practice/{sessionId}/replay` renders truthful replay content on the accepted chain. Re-run the live same-session admin Persona/knowledge → practice → knowledge-check → report → replay proof after the fix.
