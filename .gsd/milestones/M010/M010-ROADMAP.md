# M010: 

## Vision
M010 closes the "fake-credible report" gap by attaching evidence provenance to key conclusions (main_issue, next_goal, claim_truth) and establishing a unified degradation taxonomy across report, replay, and knowledge-check routes. The user will see not just "what went wrong" but "why we believe this" — backed by retrieval, transcript, and audio evidence on the same authority seam that already powers the shipped product.

## Slice Overview
| ID | Slice | Risk | Depends | Done | After this |
|----|-------|------|---------|------|------------|
| S01 | 后端结论证据合同与跨路由一致性 | high | — | ✅ | After this slice, contract tests prove one completed session produces the same evidence_references (retrieval/transcript/audio sources for main_issue/next_goal/claim_truth) on report, replay, and knowledge-check. |
| S02 | 统一分层降级分类 | medium | S01 | ✅ | After this slice, sessions with partial evidence (missing retrieval, missing audio, or degraded transcript) produce explicit layered degradation tokens that are consistent across report, replay, and knowledge-check. |
| S03 | 前端出处渲染与端到端验证 | low | S01, S02 | ⬜ | After this slice, report and replay pages render conclusion provenance (which evidence sources support each conclusion) and degradation indicators (which layers are missing) using shared helpers from session-evidence.ts. |
