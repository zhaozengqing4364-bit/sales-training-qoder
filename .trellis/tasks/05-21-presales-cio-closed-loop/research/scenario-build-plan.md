# Scenario Build Plan — Manufacturing CIO First-Visit Discovery

## Default MVP decisions

* Scope: first-visit discovery only.
* Sales stage focus: opening + discovery + initial value mapping + next-step commitment.
* Explicitly excluded: quotation, POC execution, deep competitor battlecards, formal proposal presentation, procurement negotiation.
* Presales expert placement: mandatory learning-confirmation stage, because this sample must prove the full loop: learn → ask → exam → roleplay → report → remediate.
* Implementation style: reuse existing seed-data/configuration surfaces, likely by creating a focused seed script derived from `backend/scripts/seed_presales_mvp.py`.

## Data/config assets to create

### 1. Agent shell

Create or reuse a sales Agent named along the lines of:

* `制造业 CIO 首访训练教练`

Purpose:

* Hosts the learner-facing training entry.
* Provides sales/presales capability shell.
* Does not own live prompt truth; role prompts and knowledge bindings live in Persona policy.

### 2. Knowledge bases

Minimum recommended KB split:

1. `制造业 CIO 首访售前知识库`
   * Manufacturing digitalization context.
   * CIO concerns: integration, data security, ROI, system stability, project risk.
   * First-visit discovery playbook.
2. `产品与训练系统能力知识库`
   * Sales training system capabilities.
   * Learning content, roleplay, scoring, report, knowledge base, question bank, practice template concepts.

If implementation cost is high, combine into one KB for MVP but keep document sections clearly separated.

### 3. LearningContent and chapters

Create a published `LearningContent` titled:

* `制造业 CIO 首次拜访训练营`

Recommended 7 chapters:

1. `制造业 CIO 的角色与关注点`
   * CIO cares about IT/OT integration, reliability, security, governance, ROI, vendor risk.
2. `首次拜访的目标边界`
   * This visit is not for closing or quoting; it is for context, pain, decision line, and next step.
3. `客户背景与现状确认`
   * Ask about existing systems, factories/sites, users, integration points, current manual workarounds.
4. `痛点挖掘与影响量化`
   * Ask frequency, affected teams, cost, risk, urgency, current alternatives.
5. `初步价值匹配`
   * Connect product capabilities to discovered pain only after confirming the problem.
6. `风险/顾虑的基础承接`
   * Basic handling for data security, integration complexity, AI reliability, budget timing.
7. `下一步推进与复盘`
   * Secure a specific follow-up: stakeholders, materials, pilot scope, date, success criteria.

### 4. QuestionCategory and QuestionItem

Create a category:

* `制造业 CIO 首访需求挖掘题库`

Recommended dimensions:

* `manufacturing_context` — manufacturing/CIO context understanding.
* `discovery_depth` — current-state and pain discovery.
* `value_mapping` — mapping product capabilities to discovered pain.
* `risk_awareness` — basic risk/objection acknowledgement without over-selling.
* `next_step_commitment` — concrete follow-up plan.

Minimum question count:

* 15 for MVP, ideally 20 to match existing seed conventions.

Example question types:

* “制造业 CIO 首次见面时，你先确认哪三类背景信息？”
* “客户说现在已有培训/知识库/内部工具，你如何继续追问？”
* “客户担心系统集成复杂，你第一句话应该回应什么？”
* “客户只说‘我们效率低’，你如何把问题量化？”
* “一次首次拜访结束时，怎样约定下一步才算具体？”

### 5. ScoringRuleset

Create a published sales ruleset:

* Version suggestion: `presales-cio-first-visit-v1`.
* Passing score suggestion: `70`.

Recommended weighted dimensions:

| key | name | weight |
|---|---|---:|
| `opening_context` | 开场与背景确认 | 0.15 |
| `discovery_depth` | 需求挖掘深度 | 0.30 |
| `manufacturing_cio_fit` | 制造业/CIO 场景贴合 | 0.20 |
| `value_mapping` | 初步价值匹配 | 0.20 |
| `next_step_commitment` | 下一步推进 | 0.15 |

Rubric principle:

* High score requires asking relevant questions before presenting a solution.
* Penalize feature dumping, premature quotation, unsupported promises, and revealing ignorance of manufacturing/CIO context.

### 6. ExaminerAgent

Create an examiner:

* `制造业 CIO 首访测评官`

Configuration intent:

* Uses the above question source IDs.
* Default learner level: `beginner`.
* Question count: 8–10 for a short gate, or 15 for a full gate.
* Prompt style: concise, coach-like, asks one question at a time, gives targeted correction.
* Scoring policy: `presales-cio-first-visit-v1`.

Gate behavior:

* Pass: learner enters customer roleplay.
* Fail: learner gets top 2 missing knowledge points and returns to chapters/expert QA.

### 7. CaseItem — real virtual customer

Create a manufacturing customer case:

* Industry: `manufacturing`.
* Company: fictional but realistic, e.g. `华东精密装备集团`.
* Customer role: CIO / IT director.

Recommended dossier:

* Company size: multi-site equipment manufacturer, 5,000–8,000 employees, 3–5 factories.
* Current systems: ERP, MES, CRM, OA, knowledge base/wiki, manual sales enablement docs.
* Business pressure: intelligent manufacturing upgrade, inconsistent presales enablement, slow newcomer ramp-up, inconsistent solution quality across regions.
* CIO concerns: integration, access control, data leakage, model hallucination, auditability, rollout cost, business department adoption.
* Hidden information:
  * Sales enablement is currently owned jointly by sales operations and presales leads.
  * CIO is under pressure after a failed knowledge-base project with low adoption.
  * Budget may exist if a pilot proves reduced training cycle or manager coaching workload.
  * Final decision also involves sales VP and HR training lead.
* Objections:
  * “我们已经有内部知识库。”
  * “AI 回答不稳定会不会误导新人？”
  * “和现有系统怎么集成？”
  * “没有明确 ROI 我很难推动。”
* Success criteria:
  * Learner identifies current training workflow, affected users, decision chain, risk concerns, and proposes a concrete pilot next step.

### 8. RoleProfile — CIO behavior

Create a role profile:

* Role type: `customer`.
* Communication style: rigorous, concise, evidence-oriented, skeptical of vague product claims.
* Pressure level: medium-high.
* Knowledge boundary: only knows his company context; does not reveal hidden details unless asked relevant discovery questions.
* Behavior rules:
  * If learner pitches too early, ask “你还没了解我们现状，为什么认为这个适合？”
  * If learner asks specific discovery questions, reveal one relevant hidden detail.
  * If learner asks vague questions, answer vaguely and wait for follow-up.
  * If learner promises unsupported outcomes, challenge evidence and implementation boundary.

### 9. Persona — live runtime role

Create a Persona:

* Name: `制造业 CIO（首次拜访）`.
* Category: `customer`.
* Difficulty: `medium` or `hard` (recommend medium for first sample; pressure can be medium-high in RoleProfile).
* `persona_policy.system_prompt`: embeds role identity, first-visit scope, disclosure rules, hidden-info behavior, and no-score-leak rule.
* `persona_policy.knowledge_base_ids`: bind relevant KB(s).
* `persona_policy.tool_policy`: require grounding if KB is available; no web search for MVP.
* `behavior_config`: challenge frequency, follow-up style, response length.

### 10. PracticeTemplate and curriculum_plan

Create or seed a template:

* Name: `制造业 CIO 首次拜访闭环训练`.
* Scenario type: `sales`.
* Mode: prefer existing viable mode from code; `customer_roleplay` is proven in existing seed, while `mixed_path` is conceptually ideal if accepted by schema/runtime.
* Binds: Agent, Persona, RuntimeProfile, ScoringRuleset, KB refs, LearningContent, ExaminerAgent, CaseItem/RoleProfile if model fields support them.

Recommended stage graph:

1. `study`: `制造业 CIO 首次拜访训练营`
2. `expert_qa` / learning-confirmation: if stage type cannot represent expert QA directly, encode as a study/practice pre-step in template metadata or use the Agent/Persona expert role as a required linked practice.
3. `exam`: `制造业 CIO 首访测评官`
4. `practice`: `制造业 CIO（首次拜访）` customer roleplay.
5. `report`: report and remediation suggestions.

If current `CurriculumPlanSchema` only supports `study`, `exam`, `practice`, `report`, represent expert QA as a required part of the study stage for MVP and keep a future note to promote it to a first-class stage.

## Acceptance checklist

* Verify seed script is idempotent: second run updates, not duplicates.
* Verify `--verify-only` confirms all assets exist and are published.
* Verify learning content has at least 7 chapters and all are safe/published.
* Verify question bank has at least 15–20 published questions across all scoring dimensions.
* Verify examiner binds the intended question IDs and scoring policy.
* Verify customer Persona has non-empty `persona_policy.system_prompt` and KB binding.
* Verify practice template has a curriculum plan in correct stage order.
* Verify learner task points to the practice template / curriculum plan.
* Manual smoke path: learner can see path → study → start exam → start practice → get report/remediation.

## Open implementation checks

* Confirm whether `PracticeTemplate.mode="mixed_path"` is accepted everywhere or whether to keep the existing seed's `customer_roleplay` mode with `curriculum_plan` attached.
* Confirm whether `CaseItem` and `RoleProfile` have direct fields on `PracticeTemplate`; if not, bind through metadata/config fields or keep them as published admin assets referenced by template config.
* Confirm how expert QA is represented at runtime; if no first-class `expert_qa` stage exists in curriculum plan validation, include expert QA inside study stage for MVP.
