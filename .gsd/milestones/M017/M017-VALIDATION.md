---
verdict: needs-attention
remediation_round: 0
---

# Milestone Validation: M017

## Success Criteria Checklist
## Reviewer C — Assessment & Acceptance Criteria

Note: `.gsd/M017/CONTEXT.md` was not present, and no slice-level `ASSESSMENT` artifacts were found under `.gsd/milestones/M017/slices/`; acceptance was therefore validated against the roadmap “After this” outcomes plus slice SUMMARY evidence.

- [x] **S01:** `pause/resume/end` 并发行为有可重复证明，状态收敛策略清晰。  
  **Evidence:** `S01-SUMMARY.md` documents stale-writer race reproduction, compare-and-swap convergence in `SessionLifecycleService`, preserved sales=`scoring` / presentation=`completed` terminal split, and focused verification via `backend/tests/unit/test_session_lifecycle_service.py` + `backend/tests/integration/test_session_lifecycle_api.py` (**27 passed**).
- [x] **S02:** practice websocket 的 `reconnect/backpressure/interrupt` contract 更清晰，测试保持通过。  
  **Evidence:** `S02-SUMMARY.md` documents reconnect as a fresh transport epoch, interrupt-owned local cleanup, reconnect-vs-failed learner UX split, and focused verification across `use-practice-websocket` / presentation-flow / practice page tests (**33/33 passed**).
- [x] **S03:** presentation `upload / replace` 等并发风险点被列成可证据化清单，并给出下一步建议。  
  **Evidence:** `S03-SUMMARY.md` documents the code-adjacent discovery inventory, proved concurrent replace as a real writer race, distinguished delete as a route/policy gap, kept upload-new as inventory-only, and recorded the next-step boundary with focused verification (**11/11 passed**).
- [ ] **Formal acceptance artifact package is complete.**  
  **Evidence:** Requested milestone context/assessment artifacts were not present at the paths named in the reviewer protocol, so acceptance is provable from roadmap + summary evidence but not from a complete CONTEXT/ASSESSMENT package.

**Reviewer verdict:** NEEDS-ATTENTION

## Slice Delivery Audit
| Slice | Planned delivery | Delivered evidence | Status |
|---|---|---|---|
| S01 | `pause/resume/end` 并发 proof + clear state convergence strategy | `S01-SUMMARY.md` shows durable lifecycle concurrency contract, stale-writer harness, compare-and-swap convergence seam, explicit sales=`scoring` vs presentation=`completed` split, and 27-passing focused lifecycle tests. | Delivered |
| S02 | Practice websocket reconnect/backpressure/interrupt contract clearer and tests still passing | `S02-SUMMARY.md` shows transport-epoch reconnect contract, interrupt cleanup ownership, learner reconnect UX boundary, and 33/33 passing focused hook/page tests. | Delivered |
| S03 | Presentation upload/replace concurrency risks inventoried with evidence and next-step guidance | `S03-SUMMARY.md` shows code-adjacent race inventory, proven replace race, delete policy gap proof, next-step mitigation boundary, and 11/11 passing focused presentation tests. | Delivered |

Milestone status check via `gsd_milestone_status`: S01, S02, and S03 are all `complete` with task counts 3/3 done.

## Cross-Slice Integration
## Reviewer B — Cross-Slice Integration

Note: no rendered boundary map was present in the roadmap, so integration was audited from the explicit slice handoff language in the roadmap and summaries.

| Boundary | Producer Summary | Consumer Summary | Status |
|---|---|---|---|
| **S01 → S02:** lifecycle terminal-state / concurrency contract | **Confirmed.** `S01-SUMMARY.md` says it produced “a durable backend concurrency contract for pause/resume/end races” and notes that S02 can rely on one stable terminal-state seam. | **Not explicitly confirmed.** `S02-SUMMARY.md` proves websocket reconnect/backpressure/interrupt behavior, but does not explicitly state that it consumed S01’s lifecycle contract. | Gap |
| **S01 → S03:** proof-first concurrency/race-discovery pattern | **Confirmed.** `S01-SUMMARY.md` says it established the proof-first pattern for downstream resource-contention work. | **Partially aligned but not explicitly acknowledged.** `S03-SUMMARY.md` uses a proof-first approach, but does not explicitly state that it consumed the S01 handoff. | Gap |
| **S02 → S03:** websocket reconnect / transport-epoch contract | **Confirmed.** `S02-SUMMARY.md` says S03 can assume stale interrupt/control intent no longer replays across reconnects. | **Not explicitly confirmed.** `S03-SUMMARY.md` stays focused on presentation mutation discovery and does not explicitly mention consumption of S02’s transport-epoch contract. | Gap |

**Reviewer verdict:** NEEDS-ATTENTION

## Requirement Coverage
## Reviewer A — Requirements Coverage

Note: no dedicated `.gsd/M017/REQUIREMENTS.md` was present, so the milestone roadmap “After this” commitments were used as the equivalent requirement source.

| Requirement | Status | Evidence |
|---|---|---|
| **S01:** `pause/resume/end` 并发行为有可重复证明，状态收敛策略清晰。 | **COVERED** | `S01-SUMMARY.md` shows the slice turned lifecycle concurrency into a mechanically provable backend contract, added stale-writer race proofs, implemented optimistic compare-and-swap convergence in `SessionLifecycleService`, preserved the intentional terminal split, and verified with focused lifecycle pytest coverage (**27 passed**). |
| **S02:** practice websocket 的 `reconnect/backpressure/interrupt` contract 更清晰，测试保持通过。 | **COVERED** | `S02-SUMMARY.md` says it locked the websocket seam, documented reconnect as a fresh transport epoch, made interrupt own local cleanup, added learner reconnect UX proof, and reran the focused hook/page bundle (**33/33 passed**). |
| **S03:** presentation `upload / replace` 等并发风险点被列成可证据化清单，并给出下一步建议。 | **COVERED** | `S03-SUMMARY.md` says it built the code-adjacent race inventory, proved replace as a real concurrent-writer race, separated delete guard/policy gaps from writer races, kept upload suspicion as inventory-only, and recorded concrete next-step guidance with focused presentation verification (**11/11 passed**). |

**Reviewer verdict:** PASS

## Verification Class Compliance
- **Contract:** Satisfied by focused proof bundles across all three slices: S01 lifecycle pytest bundle (**27 passed**), S02 websocket/page bundle (**33/33 passed**), and S03 presentation contract/integration bundle (**11/11 passed**).
- **Integration:** Satisfied at the slice level: S01 covers `SessionLifecycleService` + lifecycle API, S02 covers `use-practice-websocket` + learner practice page, and S03 covers presentation flow/delete permissions on shared DB concurrency proofs.
- **Operational:** Mostly satisfied. S01 explicitly preserved sales/report/replay semantics and terminal split; S02 preserved truthful reconnect UX without adding a second client-side state machine; S03 stayed discovery-only and did not introduce new runtime processes. No evidence of extra background processes or broken unlock semantics surfaced in the summaries.
- **UAT:** Partial. The slice summaries provide clear evidence for practice interrupt/recovery behavior and upload/replace risk conclusions, but no standalone milestone CONTEXT/UAT/ASSESSMENT artifact was present at the expected reviewer paths. This keeps the milestone in `needs-attention` rather than `pass`.


## Verdict Rationale
M017’s substantive milestone goals are delivered: all three planned slices are complete, each roadmap commitment is covered by focused passing proof, and the verification classes are largely satisfied. The milestone still needs attention because the reviewer protocol could not find the expected acceptance/context artifact package, and the cross-slice consumption boundaries are only inferable from producer summaries rather than explicitly confirmed by downstream slice summaries.
