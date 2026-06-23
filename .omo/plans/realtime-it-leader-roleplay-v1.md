# realtime-it-leader-roleplay-v1 - Work Plan

## TL;DR (For humans)
<!-- Fill this LAST, after the detailed plan below is written, so it summarizes the REAL plan. -->
<!-- Plain English for a non-engineer: NO file paths, NO todo numbers, NO wave/agent/tool names. -->

**What you'll get:** 一个可运行的 15 分钟信息化负责人首访对练 v1 后端样板：固定角色合同、轻量状态卡、知识可见性边界、离线证据评分报告，以及 9 段回归样本结构。

**Why this approach:** 复用现有 StepFun 平台直练链路和 `VoiceRuntimePolicyService`，不新造实时运行时；把长流程稳定性放在冻结合同、状态卡和离线评分上，而不是让实时模型硬记 15 分钟上下文。

**What it will NOT do:** 不接入 `sales_trainer` realtime 占位，不做课程闭环 `PracticeTemplate` 开练，不做复杂后台、多行业自由配置、长期客户记忆、实时教练打断或模型微调。

**Effort:** Large
**Risk:** High - sales realtime WebSocket 是仓库复杂热点，且需要同时约束角色、知识、评分和权限边界。
**Decisions to sanity-check:** v1 只走平台直练；6 项业务评分作为 v1 report projection；4 个阶段只是 roleplay phase，不新增销售 stage。

Your next move: 已由 `$omo:start-work` 启动执行；实现按下面 TODO 由子代理分派，全部通过最终验证后再声明完成。Full execution detail follows below.

---

> TL;DR (machine): Large/high-risk backend-first v1 implementation using existing platform direct practice, voice policy snapshots, roleplay contract/state card samples, knowledge visibility guards, offline scoring, and regression fixtures.

## Scope
### Must have
- PRD/设计文档执行边界无冲突：平台直练入口、`sales_trainer` 禁入、6 项评分兼容、4 个 roleplay phase 非新 stage、权限/失败/回滚/观测/9 样本结构明确。
- 后端固定 v1 样板资产：roleplay contract、state card schema/default, knowledge visibility rules, scoring rubric, regression sample metadata.
- `VoiceRuntimePolicyService` / `VoiceInstructionCompiler` 复用现有 direct-practice `roleplay_contract` 编译路径，能把 v1 合同和短阶段锚点纳入 `voice_policy_snapshot` / instructions。
- 状态卡更新逻辑最小实现：version/sequence、防乱序、失败保留上一版、重连可从 persisted snapshot/runtime_state 恢复。
- 知识可见性守门：AI 客户只可见客户背景和有限产品事实；评分教练知识不进入实时客户上下文；检索超时/缺失记录 quality flag 并自然降级追问。
- 离线评分服务/投影：6 项 100 分 rubric，学员/管理员双视图，原话证据绑定，规则一致性校验，低置信度人工复核标记。
- 测试覆盖：unit/contract 为主，禁止真实 LLM/TTS/StepFun 调用；至少一个数据/CLI-shaped manual QA artifact。

### Must NOT have (guardrails, anti-slop, scope boundaries)
- 不创建新 WebSocket runtime，不恢复 legacy sales handler。
- 不修改 `sales_trainer` realtime 占位为可用，不通过 `PracticeTemplate` 课程闭环开练。
- 不新增复杂后台配置中心，不新增三套“客户背景 KB / 产品事实 KB / 评分教练 KB”平行库表。
- 不引入模型微调、实时教练打断、每轮强制检索或长期客户记忆。
- 不做大范围 UI；管理员质检视图 v1 只交付字段投影/API/报告数据结构，除非现有页面已有低成本挂载点。
- 不在单元测试中调用真实 LLM/TTS/StepFun/外部知识服务。

## Verification strategy
> Zero human intervention - all verification is agent-executed.
- Test decision: TDD where seams exist; otherwise baseline characterization before behavior changes and tests-after for pure fixtures/docs. Python tests run from `backend/` with pytest fakes/mocks.
- Evidence: `.omo/evidence/task-<N>-realtime-it-leader-roleplay-v1.{txt,json,md}` per TODO. Manual-QA may be data-shaped: exact pytest/script invocation, emitted JSON report, and grep/assert output are acceptable because this v1 surface is runtime/report data, not UI.

## Execution strategy
### Parallel execution waves
> Target 5-8 todos per wave. Fewer than 3 (except the final) means you under-split.
- Wave 0: documentation boundary cleanup and codebase targeting. No product behavior change.
- Wave 1: independent foundations: v1 sample contracts/fixtures, state card model helpers, offline scoring schema/rubric.
- Wave 2: integration seams: voice policy/instruction injection, knowledge visibility/tool-policy guard, scoring report projection.
- Wave 3: runtime resilience and observability: state card restore/sequence handling, quality flags, permission fail-closed projection.
- Wave 4: regression harness and end-to-end data-shaped QA.

### Dependency matrix
| Todo | Depends on | Blocks | Can parallelize with |
| --- | --- | --- | --- |
| 0 | none | 1,2,3,4,5,6,7,8 | none |
| 1 | 0 | 4,5,8 | 2,3 |
| 2 | 0 | 4,6,8 | 1,3 |
| 3 | 0 | 6,7,8 | 1,2 |
| 4 | 1,2 | 7,8 | 5,6 |
| 5 | 1,3 | 7,8 | 4,6 |
| 6 | 2,3 | 7,8 | 4,5 |
| 7 | 4,5,6 | 8 | none |
| 8 | 7 | Final verification | none |

## Todos
> Implementation + Test = ONE todo. Never separate.
<!-- APPEND TASK BATCHES BELOW THIS LINE WITH edit/apply_patch - never rewrite the headers above. -->
- [x] 0. Boundary patch and implementation targeting gate
  What to do / Must NOT do: Verify `.trellis/tasks/06-23-15-v1/prd.md` and `docs/plans/2026-06-23-realtime-it-leader-roleplay-v1-design.md` no longer contain implementation-blocking contradictions. If the sentence “本次任务仍只补文档边界，不修改产品代码” remains, replace it with “后续实现按本 PRD/设计拆分最小任务推进”. Do not touch product code. Also write `.omo/evidence/task-0-realtime-it-leader-roleplay-v1.md` summarizing exact backend target files/symbols discovered for later workers.
  Parallelization: Wave 0 | Blocked by: none | Blocks: all product-code todos
  References (executor has NO interview context - be exhaustive): `.trellis/tasks/06-23-15-v1/prd.md`; `docs/plans/2026-06-23-realtime-it-leader-roleplay-v1-design.md`; `CONTEXT.md`; `backend/src/sales_bot/AGENTS.md`; CodeGraph findings for `VoiceRuntimePolicyService`, `_compile_direct_practice_roleplay_contract`, `VoiceInstructionCompiler`, `StepFunRealtimeHandler`, `search_internal_knowledge`.
  Acceptance criteria (agent-executable): `grep -R "本次任务仍只补文档边界" .trellis/tasks/06-23-15-v1/prd.md docs/plans/2026-06-23-realtime-it-leader-roleplay-v1-design.md` exits non-zero; `grep -n "平台直练\\|sales_trainer\\|PracticeTemplate\\|roleplay_contract_hash\\|state_card_version\\|9 段" ...` finds the expected boundaries; evidence file lists exact implementation targets.
  QA scenarios (name the exact tool + invocation): happy: `grep -n` commands above plus `sed -n '15,60p' .trellis/tasks/06-23-15-v1/prd.md`; failure: intentionally search the forbidden phrase and capture non-zero exit via `bash -lc 'grep -R "本次任务仍只补文档边界" ...; test $? -ne 0'`. Evidence `.omo/evidence/task-0-realtime-it-leader-roleplay-v1.md`.
  Commit: N | docs(plan): align realtime roleplay v1 execution boundary

- [x] 1. Add v1 sample asset contracts and regression fixture metadata
  What to do / Must NOT do: Add the smallest backend-owned sample asset module and tests for fixed v1 roleplay contract, state card default/schema, knowledge visibility rules, scoring rubric, and 9 regression sample metadata. Prefer `backend/src/sales_bot/services/it_leader_roleplay_v1.py` or an existing nearby services/config file if one already exists. Do not add DB tables or migrations. Do not create three new KB asset tables.
  Parallelization: Wave 1 | Blocked by: 0 | Blocks: 4,5,8
  References: `.trellis/tasks/06-23-15-v1/prd.md` Requirements; `docs/plans/2026-06-23-realtime-it-leader-roleplay-v1-design.md` sections 3.1, 4, 5, 6, 8, 11; `CONTEXT.md` Roleplay Contract and Roleplay Asset Layers; `backend/AGENTS.md`; `backend/src/sales_bot/AGENTS.md`; `backend/tests/AGENTS.md` if editing tests.
  Acceptance criteria: pytest unit test proves contract contains visible/hidden knowledge boundaries, forbidden behaviors, 4 phase ids as roleplay phases not sales stages, scoring rubric totals 100, and 9 sample metadata entries split excellent/average/poor = 3/3/3 with required coverage tags.
  QA scenarios: happy: `cd backend && pytest tests/unit/test_it_leader_roleplay_v1_assets.py -q`; failure: test mutates/constructs a bad rubric total or missing hidden scope and asserts validation rejects it. Evidence `.omo/evidence/task-1-realtime-it-leader-roleplay-v1.txt`.
  Commit: Y | feat(sales-bot): add it leader roleplay v1 assets

- [x] 2. Add session state card helper with versioned update semantics
  What to do / Must NOT do: Implement a minimal helper for `session_state_card` validation/update/serialization, using sequence/version to reject stale updates and preserving prior state on invalid or failed updates. Prefer `backend/src/sales_bot/services/roleplay_state_card.py` unless an existing state-card helper is discovered. Do not wire into live WebSocket yet.
  Parallelization: Wave 1 | Blocked by: 0 | Blocks: 4,6,8
  References: `docs/plans/2026-06-23-realtime-it-leader-roleplay-v1-design.md` section 5; `CONTEXT.md` Roleplay Compliance observability fields; `backend/src/sales_bot/AGENTS.md` realtime state cautions.
  Acceptance criteria: unit tests cover default state, valid update increments version, stale update is ignored, invalid update keeps previous state, serialization includes `state_card_version`, current phase, customer attitude, learner actions, objections, quality flags.
  QA scenarios: happy: `cd backend && pytest tests/unit/test_roleplay_state_card.py -q`; failure: stale sequence update after newer state returns unchanged state and records/returns stale outcome. Evidence `.omo/evidence/task-2-realtime-it-leader-roleplay-v1.txt`.
  Commit: Y | feat(sales-bot): add versioned roleplay state card helper

- [x] 3. Add offline scoring rubric/report schemas and consistency validator
  What to do / Must NOT do: Add minimal offline scoring data structures and validator for the v1 6-item rubric, learner/admin report projections, evidence binding, score-total consistency, confidence, and manual-review flag. Prefer a new small service under `backend/src/sales_bot/services/it_leader_roleplay_scoring.py` or reuse an existing evaluation service if clearly suitable. Do not call a live LLM; tests use deterministic/fake inputs.
  Parallelization: Wave 1 | Blocked by: 0 | Blocks: 5,6,8
  References: `.trellis/tasks/06-23-15-v1/prd.md` scoring requirements; `docs/plans/...` sections 8 and 9; `docs/architecture.md` existing 5-dimension evaluation caution; backend quality rules forbidding real LLM calls in unit tests.
  Acceptance criteria: unit tests validate six scores sum to total, each displayed score has learner evidence from learner turns only, admin projection includes scoring JSON/state/contract hash fields, learner projection excludes hidden/admin-only fields, low confidence triggers review flag.
  QA scenarios: happy: `cd backend && pytest tests/unit/test_it_leader_roleplay_scoring.py -q`; failure: report with AI-customer evidence or mismatched total is rejected. Evidence `.omo/evidence/task-3-realtime-it-leader-roleplay-v1.txt`.
  Commit: Y | feat(sales-bot): add it leader roleplay scoring report contract

- [x] 4. Wire v1 contract/state anchors into existing voice policy and instruction compiler
  What to do / Must NOT do: Reuse `VoiceRuntimePolicyService._compile_direct_practice_roleplay_contract`, `VoiceInstructionCompiler`, and existing `voice_policy_snapshot` flow to include the v1 sample contract and short state-card/phase anchors when the v1 feature/config is enabled. Do not add a new realtime handler, do not alter `sales_trainer`, and do not fallback to latest assets at runtime.
  Parallelization: Wave 2 | Blocked by: 1,2 | Blocks: 7,8
  References: `backend/src/sales_bot/services/voice_runtime_policy.py` `_compile_direct_practice_roleplay_contract`; `backend/src/sales_bot/services/voice_instruction_compiler.py` roleplay contract sections; `backend/src/sales_bot/websocket/stepfun_realtime_policy.py` snapshot resolution; tests `backend/tests/unit/test_voice_runtime_policy_service.py`, `backend/tests/unit/test_voice_instruction_compiler.py`, `backend/tests/unit/test_stepfun_realtime_handler.py`.
  Acceptance criteria: baseline test pins existing effective policy without v1 flag; failing-first test for v1 flag expects `roleplay_contract_hash`, v1 roleplay contract, phase anchor, and state card summary in compiled instructions/snapshot; implementation makes tests pass without breaking existing policy tests.
  QA scenarios: happy: `cd backend && pytest tests/unit/test_voice_runtime_policy_service.py tests/unit/test_voice_instruction_compiler.py -q`; failure: v1 disabled path does not include v1-specific phase/state anchor. Evidence `.omo/evidence/task-4-realtime-it-leader-roleplay-v1.txt`.
  Commit: Y | feat(realtime): inject it leader roleplay contract anchors

- [x] 5. Enforce knowledge visibility and grounded degradation for v1 realtime tools
  What to do / Must NOT do: Add/adjust tool-policy assembly so realtime customer context can use customer-visible and limited product facts but never scoring-coach/internal answer keys. On KB missing/timeout, return a natural customer challenge and quality flag instead of hallucinating product facts. Reuse `search_internal_knowledge` and existing policy fields; do not create a new retrieval engine.
  Parallelization: Wave 2 | Blocked by: 1,3 | Blocks: 7,8
  References: `backend/src/common/knowledge/internal_searcher.py`; `VoiceRuntimePolicyService.build_stepfun_tools`; `.trellis/tasks/06-23-15-v1/prd.md` knowledge failure strategy; `CONTEXT.md` Visible/Hidden Information Scope; tests `backend/tests/unit/test_stepfun_internal_knowledge_searcher.py`, `backend/tests/unit/test_stepfun_realtime_handler.py`.
  Acceptance criteria: tests prove scorer-only knowledge keys are not present in realtime tool policy/instructions, KB timeout/missing produces quality flag (`knowledge_timeout_count` or equivalent) and no unsupported product assertion, normal product fact retrieval remains available when KB is ready.
  QA scenarios: happy: `cd backend && pytest tests/unit/test_stepfun_internal_knowledge_searcher.py tests/unit/test_stepfun_realtime_handler.py -q -k "knowledge or kb or roleplay"`; failure: fake scorer-only KB binding is rejected/omitted from realtime customer context. Evidence `.omo/evidence/task-5-realtime-it-leader-roleplay-v1.txt`.
  Commit: Y | feat(realtime): guard it leader knowledge visibility

- [x] 6. Add permission-safe learner/admin report projection
  What to do / Must NOT do: Expose or generate v1 scoring report projections with fail-closed field filtering: learner sees total/dimensions/suggestions/learner evidence; admin/supervisor sees transcript/scoring JSON/state card/contract hash/AI quality; ops sees only redacted logs/metrics. Prefer service-level projection first; only add API fields if an existing report endpoint already supports equivalent extension. No new large UI.
  Parallelization: Wave 2 | Blocked by: 2,3 | Blocks: 7,8
  References: `.trellis/tasks/06-23-15-v1/prd.md` permissions; docs design section 9; existing evaluation/report services discovered by worker; backend error/permission rules.
  Acceptance criteria: tests cover learner projection excludes hidden/admin fields, admin projection includes required quality fields, unknown role fails closed, evidence source is learner-only.
  QA scenarios: happy: `cd backend && pytest tests/unit/test_it_leader_roleplay_report_projection.py -q`; failure: unknown role or learner requesting raw scoring JSON returns denied/filtered result. Evidence `.omo/evidence/task-6-realtime-it-leader-roleplay-v1.txt`.
  Commit: Y | feat(sales-bot): add permission-safe roleplay report projection

- [x] 7. Runtime resilience and observability integration
  What to do / Must NOT do: Integrate state-card version, contract hash, quality flags, violation counts, knowledge timeout count, and scoring confidence into existing runtime metrics/snapshot persistence. Ensure reconnect restore reads persisted contract/state, stale state updates are ignored, and blocking violations can mark report for review. Keep hot audio path short; do not block on scoring or retrieval.
  Parallelization: Wave 3 | Blocked by: 4,5,6 | Blocks: 8
  References: `backend/src/sales_bot/websocket/components/stepfun_runtime_metrics_helpers.py`; `backend/src/sales_bot/websocket/stepfun_realtime_policy.py`; `backend/src/sales_bot/websocket/stepfun_realtime_upstream.py`; `CONTEXT.md` Roleplay Compliance observability fields.
  Acceptance criteria: tests simulate reconnect with existing snapshot/runtime_state, stale state-card update, knowledge timeout quality flag, and blocking violation marker; persisted snapshot includes required observability fields and does not lose previous state on update failure.
  QA scenarios: happy: `cd backend && pytest tests/unit/test_stepfun_realtime_handler.py tests/unit/test_roleplay_state_card.py -q -k "roleplay or runtime_state or reconnect or quality"`; failure: out-of-order state update after reconnect is ignored and evidence shows prior state preserved. Evidence `.omo/evidence/task-7-realtime-it-leader-roleplay-v1.txt`.
  Commit: Y | feat(realtime): persist roleplay v1 quality state

- [x] 8. End-to-end regression harness and data-shaped manual QA
  What to do / Must NOT do: Add a small regression harness or pytest module that runs the 9 metadata samples through the v1 scoring/report validator and compiles a representative v1 voice policy/instruction payload. Do not use live StepFun or live LLM. Produce a JSON/MD evidence artifact showing no hidden leakage, scoring evidence binding, and quality flags.
  Parallelization: Wave 4 | Blocked by: 7 | Blocks: Final verification
  References: all files changed by 1-7; `.omo/evidence/task-*`; PRD Acceptance Criteria.
  Acceptance criteria: `cd backend && pytest tests/unit/test_it_leader_roleplay_v1_regression.py -q` passes; generated artifact records sample ids, expected quality tier, covered tags, report validity, leakage checks, and compiled instruction checks.
  QA scenarios: happy: exact pytest above plus `python` or pytest artifact generation if implemented; failure: one fixture containing hidden scoring answer in customer-visible context is caught. Evidence `.omo/evidence/task-8-realtime-it-leader-roleplay-v1.json`.
  Commit: Y | test(sales-bot): add it leader roleplay v1 regression harness

## Final verification wave
> Runs in parallel after ALL todos. ALL must APPROVE. Surface results and wait for the user's explicit okay before declaring complete.
- [ ] F1. Plan compliance audit: independent reviewer checks every TODO acceptance criterion, PRD boundary, and Must NOT Have against final diff and evidence. Evidence `.omo/evidence/f1-realtime-it-leader-roleplay-v1-plan-compliance.md`.
- [ ] F2. Code quality review: independent reviewer checks minimality, existing-pattern reuse, test quality, no live external calls in unit tests, no `sales_trainer` realtime activation, and no new parallel runtime. Evidence `.omo/evidence/f2-realtime-it-leader-roleplay-v1-code-review.md`.
- [ ] F3. Real manual QA: QA executor runs the data-shaped manual scenario from TODO 8 and captures generated report/instruction artifacts. Evidence `.omo/evidence/f3-realtime-it-leader-roleplay-v1-manual-qa.md`.
- [ ] F4. Scope fidelity: reviewer verifies no multi-industry config center, long-term memory, realtime coaching, model fine-tuning, or UI expansion slipped in. Evidence `.omo/evidence/f4-realtime-it-leader-roleplay-v1-scope.md`.

## Commit strategy
- Commit per completed implementation TODO where practical; documentation/plan-only state can remain unstaged unless user asks.
- Suggested commit sequence:
  1. `feat(sales-bot): add it leader roleplay v1 assets`
  2. `feat(realtime): inject it leader roleplay contract anchors`
  3. `feat(sales-bot): add it leader roleplay scoring report`
  4. `test(sales-bot): add it leader roleplay v1 regression harness`
- Do not commit unrelated dirty worktree changes. Do not amend existing commits.

## Success criteria
- Platform direct practice can compile a v1 information-leader roleplay contract and short stage/state anchor without creating a new realtime runtime.
- Roleplay contract is frozen/hashable; runtime does not fallback to latest assets for active sessions.
- State card updates are versioned; stale/failed updates do not wipe state; reconnect can restore persisted state.
- Knowledge visibility keeps scorer-only/internal training content out of realtime customer context and degrades safely on missing/timeout.
- Offline scoring report uses 6-item rubric, learner/admin projections, learner evidence only, total consistency checks, confidence, and manual-review flags.
- 9 regression sample metadata and harness prove drift/leakage/scoring evidence checks at a data surface.
- Tests and manual QA artifacts are recorded under `.omo/evidence/`.
