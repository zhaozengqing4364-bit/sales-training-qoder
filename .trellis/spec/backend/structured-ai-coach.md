# Structured AI Coach

> Executable contract for the first-launch newcomer Coach. The Coach is a bounded training activity with typed cards, durable AI work and human escalation; it is not a free-chat or readiness authority.

## 1. Scope / Trigger

Apply this contract when changing `backend/src/ai_coach/`, its Activity Runtime adapter, standard-pack Coach definitions, Coach durable tasks, learner/admin Coach APIs, or `FoundationCoachRunner`.

The authoritative write split is:

- `ai_coach`: ProfileRevision, Session, Cycle, Turn, TrainingCard, CardResponse, Assistance, CoachOutcome and append-only human intervention/audit;
- `newcomer_training`: generic ActivityAttempt, ActivityOutcome and Journey projection;
- `task_runtime`: durable task lifecycle only;
- the later competency module: the only formal CompetencyEvidence writer;
- the later readiness module: the only `foundation_ready` decision writer.

Realtime customer voice practice is outside this contract and must not become a Coach dependency.

## 2. Signatures

Published runtime configuration:

```python
class CoachProfileSnapshot(BaseModel):
    checkpoints: tuple[CoachCheckpointDefinition, CoachCheckpointDefinition, CoachCheckpointDefinition]
    card_type_whitelist: tuple[CoachCardType, ...]
    mastery_rule: CoachMasteryRule
    remediation_policy: CoachRemediationPolicy
    ai: CoachAIContracts

class StructuredCoachRuntime:
    async def start_or_resume(...) -> CoachRuntimeProjection: ...
    async def submit_answer(...) -> CoachRuntimeProjection: ...
    async def continue_training(...) -> CoachRuntimeProjection: ...
    async def retry_failed(...) -> CoachRuntimeProjection: ...
    async def request_assistance(...) -> CoachRuntimeProjection: ...
    async def cancel(...) -> CoachRuntimeProjection: ...
```

Canonical learner surface:

```http
GET  /api/v1/newcomer-training/activities/{activity_id}
POST /api/v1/newcomer-training/activities/{activity_id}/commands
```

Coach command union:

```text
start | submit_coach_answer | continue_coach | retry_coach |
request_coach_assistance | cancel
```

Governed human-help surface:

```http
GET  /api/v1/admin/newcomer-training/coach-sessions/help-queue
GET  /api/v1/admin/newcomer-training/coach-sessions/{session_id}/help-detail
POST /api/v1/admin/newcomer-training/coach-sessions/{session_id}/commands/intervene
```

Durable task types and result location:

```text
ai_coach.cards.generate
ai_coach.answer.evaluate
ai_coach.assistance.generate

TaskCompletion.location = /api/v1/newcomer-training/activities/{activity_id}
```

Database authority is the `coach_*` table family introduced by revision `20260717_0930_004`. `NEWCOMER_AI_COACH_ENABLED` gates creation/execution of new Coach work; disabling it retains all history.

## 3. Contracts

- A Session freezes `enrollment_id`, `path_revision_id`, `activity_id`, `attempt_id`, `profile_revision_id`, the full Profile snapshot, Context references/revisions and weakness inputs. A published Profile is immutable and a historical Session never follows a newer Profile, Prompt or model route.
- The standard Profile has exactly three ordered checkpoints: identify/understand, organize/express and transfer to a sales scenario. Each cycle accepts only 3–5 cards from the typed whitelist. Unknown types, extra fields, arbitrary HTML/script content, unknown sources and malformed payloads fail closed.
- Threshold, maximum uncertainty, card count and maximum automatic remediation cycles come only from the frozen Profile. The default standard pack uses 80% and two automatic remediation cycles; frontend code must not substitute either value.
- Learner answers are inserted and flushed with a client-token hash before an AI evaluation task is enqueued. Replaying the same token and answer returns the existing result; the same token with different input conflicts. Refresh/start resumes the existing Session and never creates duplicate work.
- Single/multiple/scenario choice and ordering cards use deterministic rules. Language cards invoke only `AIInvocationPort` with separate published contracts for card generation, answer evaluation and assistance. Each request freezes Prompt revision/hash, model routing revision, schemas, timeout/retry/budget policy and source scope.
- Model-reported `mastered` is evidence only. The application computes mastery from frozen score and uncertainty. High uncertainty, missing evidence or an exhausted two-cycle remediation budget routes to `needs_human_help`; it never fabricates completion.
- Assistance is a persisted, source-scoped side action. It may explain or give an example but does not change the formal Session state machine. Human interventions append guidance/action/audit and never overwrite learner answers or AI history.
- `CoachOutcome` and normalized `ActivityOutcome` are written only after all three checkpoints are mastered. The outcome carries response/card/content/Prompt/model lineage and cannot grant `foundation_ready`. Formal CompetencyEvidence is consumed through the later single-writer boundary.
- Durable handlers use short prepare transaction → external AI → fenced apply transaction. When converting one Pydantic result model to another, pass `result.model_dump(mode="json")`; `Target.model_validate(other_model)` is not a valid cross-model conversion in Pydantic v2.
- `FoundationCoachRunner` is a typed activity workspace, not chat. It shows checkpoint/progress, source labels, weakness summary, one current card, saved feedback, assistance and one dominant next action. It labels deterministic results as rule judgments and language results as AI inference; it never exposes Prompt, model, trace IDs or raw scores as verified facts.

## 4. Validation & Error Matrix

| Condition | Required result |
|---|---|
| Profile is draft/missing or Activity references a different revision | 409/404 typed failure; no latest-version fallback |
| Context has no authorized published references | `[COACH_CONTEXT_UNAVAILABLE]`; no model call |
| Checkpoint count is not exactly three | Profile validation failure; cannot publish/start |
| Card count outside frozen 3–5 range | `[COACH_CARD_GENERATION_OUTPUT_INVALID]`; Session `failed_recoverable` |
| Unknown card type, extra field, HTML/script, unknown source or malformed model payload | fail closed; no card/score write; retry or human path |
| Duplicate answer client token with identical payload | return existing response/task; no extra Turn, budget or score |
| Duplicate token with different payload | idempotency conflict; preserve original answer |
| Provider timeout or invalid evaluation schema | preserve raw answer; Session `failed_recoverable`; no formal score completion |
| Deterministic card reaches AI evaluation processor | state conflict; no invocation |
| AI uncertainty exceeds frozen maximum | cycle and Session `needs_human_help` after valid cycle reconciliation |
| Remediation would exceed frozen maximum | no new task; enter the human-help queue |
| Cross-organization Coach review | hidden 404 plus denied audit |
| Reviewer lacks `newcomer.coach.review` | 403 plus denied audit |
| Feature flag disabled | no new Coach start/command; stored history remains intact |
| Task succeeds | result location uses Activity ID, never Session ID |

## 5. Good / Base / Bad Cases

- **Good**: a language answer is flushed, an evaluation task times out, refresh restores the saved answer, retry uses the same response, the eventual structured feedback is marked as AI inference and all lineage is persisted.
- **Base**: a choice card is evaluated locally, the checkpoint passes using the frozen threshold, the learner advances, and no AI invocation or budget row exists for that card.
- **Bad**: a message endpoint calls a Provider inside a database transaction, trusts model `mastered`, accepts an arbitrary component/HTML payload, retries without an idempotency token, or treats Coach completion as formal readiness.

## 6. Tests Required

- Contract: every whitelisted card type validates through the backend union and matching TypeScript renderer; unknown type/extra field fails.
- Runtime: exact three-checkpoint progression, 3–5 card policy, save-before-AI, same-token replay/conflict, deterministic no-AI path, provider/schema/source failure recovery, cancel and resume.
- Remediation: maximum two automatic cycles, high uncertainty and exhausted cycles enter `needs_human_help`; no additional task/budget is created.
- Persistence: Assistance and formal feedback survive projection reload; CoachOutcome is absent before checkpoint three and contains response/card/source/Prompt/model lineage after completion.
- Handler: prepare/apply uses fenced sessions and `TaskCompletion.location` points to the activity workspace.
- Governance: capability, organization scope, append-only interventions, denied audit and unchanged answer/history.
- Frontend: all card renderers use semantic controls; preparing/evaluating/offline/recoverable/cancelled/human-help/completed states preserve one primary action and identify AI inference.
- Migration: targeted upgrade/downgrade verifies all `coach_*` tables, constraints and indexes.

## 7. Wrong vs Correct

### Wrong

```python
answer = await llm.generate(user_message)
session.messages.append({"role": "assistant", "content": answer})
session.status = "completed"
```

This loses save-before-AI recovery, typed schemas, source scope, idempotency, durable execution and application-owned mastery.

### Correct

```python
response = CoachCardResponse(raw_answer_json=answer, client_token_hash=token_hash)
session.add(response)
await session.flush([response])  # durable save boundary

if card.evaluation_mode == "deterministic":
    await finalize_response(...)
else:
    await tasks.enqueue(CoachAnswerEvaluationTaskInput(response_id=response.response_id))
```

The worker later validates the governed result, the application computes mastery from the frozen Profile, and the learner resumes from persisted Session truth.
