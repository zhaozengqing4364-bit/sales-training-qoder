# Codebase Surfaces for Presales CIO Closed Loop

## Summary

The project already has most of the infrastructure needed for a presales closed-loop sample. The recommended first implementation should use existing configuration/data surfaces rather than inventing a new training framework.

## Existing configuration surfaces

| Need | Existing surface | Notes |
|---|---|---|
| Training scenario shell | `Agent` / `/api/v1/admin/agents` | Agent is the scenario/capability shell, not the primary prompt authority. |
| Runtime role behavior | `Persona` / `persona_policy` / `/api/v1/admin/personas` | Persona policy is the live runtime source of truth for role prompt and knowledge bindings. |
| Agent-role association | `AgentPersona` / `/api/v1/admin/agents/{agent_id}/personas` | Allows persona ordering, default role, and override config. |
| Knowledge source | `KnowledgeBase`, `KnowledgeDocument` | Use for product/presales/company knowledge grounding. |
| Learning materials | `LearningContent`, `LearningChapter` | Good fit for pre-study content. |
| Question bank | `QuestionCategory`, `QuestionItem` | Good fit for examiner questions and scoring criteria. |
| Examiner | `ExaminerAgent` | Can bind question sources and scoring policy. |
| Customer case | `CaseItem` | Has industry, company profile, pain points, objections, hidden information, success criteria. |
| Customer profile | `RoleProfile` | Has role type, communication style, pressure level, knowledge boundary, behavior rules. |
| Scoring | `ScoringRuleset` and evaluation services | Supports weighted dimensions and reporting. |
| Path orchestration | `PracticeTemplate(mode="mixed_path")` + `curriculum_plan` | Supports study / exam / practice / report stages with completion and failure policies. |
| Learner path UI | `/learning-path`, `/study`, `/exam`, `/practice` pages | Existing learner-facing journey can host the closed loop. |

## Key implementation reference

`backend/scripts/seed_presales_mvp.py` already appears to provide a comprehensive presales seed pattern: learning content, questions, personas, curriculum plan, and verification. The manufacturing CIO sample should likely be a focused variant of this seed pattern unless inspection during implementation reveals a better data-loading path.

## MVP fit

The user's selected MVP is **first-visit discovery only**. That maps best to:

1. `LearningContent`: first-visit discovery basics and manufacturing CIO context.
2. `QuestionItem`: basic readiness and discovery-skill questions.
3. `ExaminerAgent`: active questioning before customer simulation.
4. `CaseItem`: manufacturing company and hidden needs.
5. `RoleProfile` + `Persona`: realistic CIO behavior.
6. `ScoringRuleset`: discovery-focused rubric.
7. `PracticeTemplate(mode="mixed_path")`: learning → exam → roleplay → report loop.

## Risks / constraints

* Do not put role prompt or knowledge bindings into Agent legacy fields; Persona policy is the source of truth.
* Avoid expanding MVP into objection handling, POC, quotation, or negotiation unless explicitly requested.
* Ensure hidden customer information is only disclosed when the learner asks relevant discovery questions.
* Ensure the scoring rubric rewards discovery behavior, not just product pitching.
