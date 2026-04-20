---
verdict: needs-attention
remediation_round: 0
---

# Milestone Validation: M020

## Success Criteria Checklist
## Reviewer C — Assessment & Acceptance Criteria
Acceptance source: `.gsd/milestones/M020/M020-ROADMAP.md` (`M020-CONTEXT.md` not present, so the roadmap “After this” lines were used as the acceptance criteria source).

Assessment artifacts: no `*ASSESSMENT*.md` or validation files were found under `.gsd/milestones/M020/` or any `S01`-`S04` slice directory. The mappings below therefore rely on slice `SUMMARY` evidence.

- [x] Auth/cookie/websocket transport policy is real code plus focused tests, not compatibility-default guesswork | No `S01` assessment file; `.gsd/milestones/M020/slices/S01/S01-SUMMARY.md` has `verification_result: passed`, documents secure session+CSRF cookie enforcement, `resolve_websocket_auth(...)` precedence (`Authorization -> session cookie -> query token`), and passing backend/frontend auth proof.
- [x] Support/admin can see useful diagnostics without leaking sensitive fields in logs or admin UI | No `S02` assessment file; `.gsd/milestones/M020/slices/S02/S02-SUMMARY.md` has `verification_result: passed`, documents the shared allowlist-first redaction seam in logger/API/UI, masked identities, ordered diagnostics, and passing backend/frontend redaction tests.
- [x] Runtime connection visibility, session snapshot, reconnect, and drain semantics are explicit for single-instance and multi-instance reasoning | No `S03` assessment file; `.gsd/milestones/M020/slices/S03/S03-SUMMARY.md` has `verification_result: passed`, documents the `SessionManager` (instance-local) vs `SessionStateService` (shared Redis snapshot) authority split, reconnect-safe state persistence, and passing websocket/reconnect proof.
- [x] M018 backup/recovery baseline is upgraded into executable drills/scripts that can validate the hardened seams | No `S04` assessment file; `.gsd/milestones/M020/slices/S04/S04-SUMMARY.md` has `verification_result: passed`, documents `scripts/recovery_drill_baseline.py` + `scripts/recovery_drill_runner.py`, fresh evidence at `.dev/recovery-drills/20260414T010316Z/summary.json`, and real drill results. Caveat: the same summary also records an open `db_migration` blocker (`KeyError: '20260412_0315_028'`), but the criterion itself is still evidenced by the executable drill bundle and captured results.

**Reviewer C verdict: PASS**

## Slice Delivery Audit
| Slice | Planned outcome | Delivered evidence | Status |
| --- | --- | --- | --- |
| S01 | Harden auth/cookie/websocket transport policy with real code and focused tests | Summary records secure session+CSRF cookie posture, websocket auth precedence, compatibility diagnostics, passing backend/frontend auth tests, and updated docs/contracts | Delivered |
| S02 | Converge sensitive-log/admin observability redaction on one safe contract | Summary records backend-owned allowlist-first redaction policy across logger/API/UI, policy metadata, diagnostics contract, and passing backend/frontend redaction tests | Delivered |
| S03 | Make runtime/session snapshot/reconnect/drain semantics explicit across single and multi-instance reasoning | Summary records SessionManager vs SessionStateService authority split, reconnect-safe persistence rules, support/runtime contract, and passing websocket/reconnect proof | Delivered |
| S04 | Convert backup/recovery baseline into executable drills and recovery evidence | Summary records executable drill scripts and captured drill bundle evidence; delivery includes an open `db_migration` blocker in the drill results that still needs follow-up | Delivered with caveat |

## Cross-Slice Integration
## Reviewer B — Cross-Slice Integration
Roadmap note: `M020-ROADMAP.md` has no explicit slice `Depends` edges, so the cross-slice boundaries below come from the slice SUMMARY handoff metadata/narrative (`affects`, `requires`, and follow-up language).

| Boundary | Producer Summary | Consumer Summary | Status |
|---|---|---|---|
| **S01 → S02** auth transport authority / explicit auth compatibility signals | **Confirmed produced.** S01 says it provides “a concrete auth transport authority seam for all later M020 security/runtime slices,” affects `S02`, and explicitly says “M020/S02 should use the new explicit auth/compatibility signals to finish sensitive-log and admin-observability redaction.” | **Not confirmed consumed.** S02 confirms its own logger/API/UI redaction contract, but does not explicitly say it reused S01’s auth transport seam, CSRF/cookie boundary, or auth compatibility signals. | **Gap** |
| **S01 → S03** fixed auth boundary for reconnect/runtime work | **Confirmed produced.** S01 says it affects `S03` and explicitly says “M020/S03 should treat `resolve_websocket_auth(...)` plus the cookie/CSRF seam as the fixed auth boundary while it hardens multi-instance reconnect and session-state authority.” | **Not confirmed consumed.** S03 confirms runtime authority work (`SessionManager` / `SessionStateService`) but does not explicitly say it built on S01’s auth boundary or reused the hardened websocket auth contract. | **Gap** |
| **S01 → S04** auth transport/bootstrap authority for recovery drills | **Confirmed produced.** S01 says it affects `S04` and “M020/S04 should reuse the repo-root auth proof bundle as part of recovery-drill validation.” | **Confirmed consumed.** S04 `requires` S01 for “The hardened auth transport and bootstrap authority that S04 reuses for `auth_bootstrap` drill commands and recovery documentation,” and its body says recovery inventory covers hardened seams from `S01-S03`. | **Honored** |
| **S02 → S03** allowlist-first diagnostics contract as fixed observability boundary | **Confirmed produced.** S02 says it affects `S03` and “M020/S03 should treat this logger/API/UI diagnostics contract as fixed while it hardens reconnect/session-state authority.” | **Not confirmed consumed.** S03 confirms support/runtime and restart/drain semantics, but does not explicitly say it consumed S02’s diagnostics contract or built on the redaction/allowlist policy. | **Gap** |
| **S02 → S04** admin/support diagnostics contract for recovery evidence | **Confirmed produced.** S02 says it affects `S04` and “M020/S04 ... should reuse the same allowlist-first diagnostics seam for recovery/quality/failure events instead of inventing a second support payload.” | **Confirmed consumed.** S04 `requires` S02 for “The allowlist-first admin/support diagnostics contract that S04 reuses when pairing support runtime summaries with drill evidence.” | **Honored** |
| **S03 → S04** runtime authority split for redis/websocket recovery interpretation | **Confirmed produced.** S03 provides “a stable runtime authority split that S04 recovery drills can consume directly,” affects `S04`, and says “S04 should build recovery-drill automation and deployment guidance on top of the explicit SessionManager/SessionStateService authority split established here.” | **Confirmed consumed.** S04 `requires` S03 for “The process-local SessionManager vs shared Redis SessionStateService runtime split that S04 reuses for redis/websocket recovery interpretation,” and its body says the drill bundle covers hardened seams from `S01-S03`. | **Honored** |

**Reviewer B verdict: NEEDS-ATTENTION**

## Requirement Coverage
## Reviewer A — Requirements Coverage
The review treated **M020-relevant requirements** as the ones the M020 slice summaries explicitly advanced, because `.gsd/REQUIREMENTS.md` has **no requirements with M020 as primary/supporting owner** and the slice summaries only name **R001** and **R002**.

| Requirement | Status | Evidence |
|---|---|---|
| R001 — 桌面端销售客户演练必须能稳定完成多轮来回，不能在第二轮录音、第二轮响应、会话结束或重连时频繁失效。 | PARTIAL | `.gsd/REQUIREMENTS.md` defines R001 as broad end-to-end multi-round stability. In `.gsd/milestones/M020/slices/S03/S03-SUMMARY.md`, M020 explicitly lists **R001 under “Requirements Advanced”**, not validated. S03 adds concrete reconnect/runtime authority work: `SessionManager` vs `SessionStateService`, reconnect snapshot persistence, request-epoch continuity, pacing-state persistence, and fresh focused proof (`backend/tests/integration/test_websocket_status_contract.py`, `test_sales_realtime_reconnect_flow.py`, 11/11 passed). That is clear evidence for the **reconnect/runtime** part of R001, but M020 does **not** demonstrate the full requirement scope (second-round recording/response/session-end stability across the full learner loop), and no M020 slice marks R001 as validated. |
| R002 — 当 ASR、LLM、TTS、WebSocket、会话状态或知识检索出现失败时，系统必须提供恢复、降级或可诊断路径，而不是直接终止训练或依赖人工猜测问题。 | PARTIAL | M020 materially improves failure visibility and recovery tooling, but only for part of R002’s scope. `.gsd/milestones/M020/slices/S01/S01-SUMMARY.md` adds auth/CSRF/websocket compatibility diagnostics (`X-Auth-Authority`, `X-Auth-Compatibility-Mode`, `403 [CSRF_VALIDATION_FAILED]`). `.gsd/milestones/M020/slices/S03/S03-SUMMARY.md` explicitly lists **R002 under “Requirements Advanced”** and adds reconnect/restart/drain diagnostics plus docs for websocket/session-state recovery. `.gsd/milestones/M020/slices/S04/S04-SUMMARY.md` adds executable recovery drills and fresh evidence at `.dev/recovery-drills/.../summary.json`, but also records an open blocker: `db_migration` still fails with `KeyError: '20260412_0315_028'`. No M020 slice lists any requirement under “Requirements Validated”, and the milestone evidence does not fully demonstrate recovery/degradation coverage across the whole R002 surface (ASR/LLM/TTS/knowledge retrieval). |

**Reviewer A verdict: NEEDS-ATTENTION**

## Verification Class Compliance
- **Contract:** Present. Evidence spans backend auth/login/reset tests, websocket status/reconnect tests, admin log redaction tests, frontend auth/admin-log tests, and recovery drill script outputs across S01-S04.
- **Integration:** Present. Slice summaries show login/reset, websocket connect/reconnect, admin logs page/system-log API, session snapshot/reconnect, and recovery drill execution all exercised.
- **Operational:** Partial. S03 and S04 provide restart/drain/reconnect and drill evidence plus runbook alignment, but S04 still records an open `db_migration` drill blocker that should be closed or explicitly dispositioned before milestone completion.
- **UAT:** Partial evidence only in this validation pass. Slice UAT artifacts exist for S01-S04, but this validation synthesized from SUMMARY evidence and did not re-audit those UAT files line-by-line.


## Verdict Rationale
Reviewer C found that all roadmap acceptance criteria map to clear slice-summary evidence, but Reviewer A found milestone-level requirement coverage is only partial for the broader R001/R002 requirements, and Reviewer B found several S01/S02 producer-to-consumer handoffs into later slices are implied rather than explicitly evidenced in consumer summaries. The milestone therefore demonstrates substantial shipped value, but the requirement mapping, cross-slice consumption trail, and the remaining S04 drill caveat warrant a needs-attention verdict rather than pass.
