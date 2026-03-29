---
depends_on: [M008, M009]
---

# M010: 报告证据链收口

**Gathered:** 2026-03-28
**Status:** Ready for planning

## Project Description

M010 要解决的是用户明确指出的“报告有问题”中最危险的那一类：报告会下结论，但说不清这个结论到底根据哪段事实来的。M010 不是重新做 report page，也不是只优化 wording，而是要在现有 `SessionEvidenceService`、canonical report API、replay API、knowledge-check 这些已经成熟的 authority seam 上，给关键结论补齐 evidence reference model，并建立 retrieval / transcript / audio / enhanced-report 多层降级的统一归因模型，最终消除“假可信报告”。

## Why This Milestone

M008 和 M009 分别把 retrieval truth 与 audio audit 做硬，但如果 report 仍然只会输出“像真的”结论，这条事实链对用户仍然不可见。M010 之所以必须单列，是因为 report/replay/knowledge-check 已经很成熟，任何 evidence reference 新增都必须非常克制：不能发明第二条 report truth source，不能破坏兼容 payload，也不能让 report/replay/knowledge-check 再次 semantic drift。

## User-Visible Outcome

### When this milestone is complete, the user can:

- 在现有 report/replay 路径里看到关键结论的出处，而不是只看到一个抽象主问题或建议。
- 当 retrieval、音频、转写或增强报告链路降级时，知道是哪一层出了问题，以及这会如何影响当前结论可信度。

### Entry point / environment

- Entry point: `/practice/{sessionId}/report`, `/practice/{sessionId}/replay`, `/api/v1/practice/sessions/{id}/knowledge-check`
- Environment: browser + current FastAPI / Next.js shipped route family
- Live dependencies involved: `SessionEvidenceService`, canonical report API, replay API, retrieval ledger, audio audit chain

## Completion Class

- Contract complete means: report/replay/knowledge-check payload 都有稳定 evidence reference / degraded reason contract，并保持兼容。
- Integration complete means: 同一条 session 的 retrieval、transcript、audio evidence 能在 report/replay/knowledge-check 上形成一条可对照的出处链。
- Operational complete means: 任何一层缺证据时，系统不会静默继续装作完整，而是明确降级并说明影响范围。

## Final Integrated Acceptance

To call this milestone complete, we must prove:

- 一条真实 session 的 report 关键结论能回到 retrieval / transcript / audio evidence。
- 同一条 session 的 replay 和 knowledge-check 与 report 的证据出处和降级说明一致。
- 不能靠新增 report-only heuristics 或 UI 本地推导来宣称完成；必须继续站在现有 authority seam 上完成 proof。

## Risks and Unknowns

- `SessionEvidenceService` 已经承担大量 authority；如果 evidence reference 建模不慎，容易让 payload 复杂化或破坏既有 consumers。
- retrieval/audio 两条上游事实链在 M008/M009 真正落地前都可能继续变化 —— 这意味着 M010 需要吸纳 upstream shape，而不是提前写死。
- 如果 degraded taxonomy 不统一，系统会再次出现“knowledge-check 一种说法、report 一种说法、replay 第三种说法”的 drift。

## Existing Codebase / Prior Art

- `backend/src/common/conversation/session_evidence.py` — 当前 report/replay authority seam，M010 必须继续复用它而不是绕开。
- `backend/src/common/api/practice.py` — canonical report route，当前用户最终可见结论的 API 出口。
- `backend/src/common/conversation/replay.py` — replay authority seam，已经承载 `learning_evidence` 与 `replay_anchor`。
- `web/src/lib/session-evidence.ts` — 前端当前 report/replay/knowledge-check wording 的共享 helper。
- `backend/tests/contract/test_practice_evidence_contract.py` — 当前最关键的 contract lock file。

> See `.gsd/DECISIONS.md` for all architectural and pattern decisions — it is an append-only register; read it during planning, append to it during execution.

## Relevant Requirements

- R023 — knowledge-check/report retrieval parity (carry-forward)
- R026 — 学员可查音频证据（carry-forward)
- R027 — 报告关键结论必须有出处
- R028 — retrieval/audio/transcript/enhanced-report 分层降级说明

## Scope

### In Scope

- report 关键结论的 evidence reference model。
- replay / report / knowledge-check 的共享 degraded taxonomy。
- retrieval / transcript / audio evidence 在当前 route family 下的出处对齐。
- 一条真实 session 的 final evidence-consistency proof。

### Out of Scope / Non-Goals

- 不重写现有 report/replay 页面整体结构。
- 不新增独立 evidence explorer / investigation console。
- 不重新定义 M008/M009 的上游事实源；M010 只消费和统一它们。

## Technical Constraints

- 继续以 `SessionEvidenceService` 作为 report authority，不新增第二条 report truth source。
- evidence references 必须兼容现有 report/replay/knowledge-check consumers，避免无意义 breaking changes。
- degraded reason 必须跨 route family 统一，而不是页面各自翻译。

## Integration Points

- `SessionEvidenceService`
- canonical report API
- replay API / `learning_evidence` / `replay_anchor`
- `knowledge-check` diagnostics
- M008 retrieval ledger
- M009 audio audit chain

## Open Questions

- 关键结论的“出处粒度”第一阶段是结论级（主问题/下一步/claim truth）还是逐条建议级 —— 当前倾向先做关键结论级，避免一次拉太大。 
