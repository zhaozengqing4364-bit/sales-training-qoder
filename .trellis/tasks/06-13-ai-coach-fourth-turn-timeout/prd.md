# AI Coach Fourth-Turn Timeout Recovery

## Context

Learner reports that `/sales-trainer/business-skills/coach` consistently times out around the fourth generated step. Browser evidence shows the learner has completed multiple challenge cards, then the stream renders `AI 教练生成超时，请重试下一步训练。`

Backend logs show a single next-action step can make multiple LLM calls because `retry_policy.max_retries + 1` attempts are allowed. Each successful DeepSeek call near the failure took roughly 10-13 seconds. The stream layer currently wraps the full next-action workflow with `generation_timeout_seconds=25`; once the timeout fires, it cancels the domain workflow before `AiCoachChatAutoAdvance` can persist its configured fallback response/action.

The user also linked CopilotKit. We will not add CopilotKit as a dependency in this task. The relevant design lesson is durable agent/UI action streaming: the UI should render step status immediately, and backend failures should resolve into a typed, persisted, recoverable action instead of a dead red error.

## Goal

Make multi-turn AI Coach training resilient enough that a fourth-turn next-card timeout does not strand the learner. After an answer is scored, the learner must either receive the next generated card/summary, or receive a persisted fallback assistant response with follow-up prompts and an auditable failed action.

## Stable Code Logic

- Stream order: score answer -> emit scored snapshot -> decide next action -> generate next card/summary -> emit completed/fallback snapshot.
- Answer scoring must commit before next-action generation.
- Timeout/failure after scoring is a typed generation failure, not a scoring failure.
- Fallback persistence belongs in the AI Coach service/auto-advance layer, not in the React page.
- Learner UI must consume SSE events through the API facade and render backend snapshots.

## Configurable Business Rules

- `generation_timeout_seconds`
- `retry_policy.max_retries` and `retry_policy.retry_backoff`
- `failure_behavior`
- `allowed_next_actions`
- `empty_response_recovery_message`
- `empty_response_recovery_prompts`
- mastery/turn thresholds already managed by `AiCoachConfig`

No new config table is needed; these rules remain under the existing AI Coach module config and admin management page.

## Requirements

1. Increase the bundled AI Coach generation budget to match multi-attempt generation without relying on page-local constants.
2. On stream timeout after a scored answer, roll back any cancelled transaction state and persist a fallback assistant response/action through the service layer.
3. The fallback must preserve the current session, set `can_auto_advance=false`, set a stopped reason/error code, and expose follow-up prompts so the learner can retry/switch/summarize.
4. The stream should emit a fresh `session_snapshot` after the persisted fallback so the frontend can recover without a full reload.
5. Keep create/send-message timeout behavior typed; do not hide terminal configuration errors behind infinite retries.
6. Update the API contract and admin defaults if default timeout semantics change.
7. Add focused backend tests for timeout recovery after a scored answer.

## Non-Goals

- No realtime WebSocket voice practice.
- No CopilotKit dependency migration.
- No new business-rule table.
- No unbounded LLM wait or infinite retry.

## Acceptance

- Unit test proves `_stream_submit_answer` emits `answer_scored` before generation and emits a recoverable completed/fallback snapshot when `advance_after_scored_event` exceeds `generation_timeout_seconds`.
- Unit/service test proves timeout fallback records a failed next action and fallback assistant message through the auto-advance pathway.
- Admin AI Coach default/config contract uses the new default timeout consistently.
- Focused backend tests pass.
- Browser validation on the learner coach page shows the chat shell remains viewport-bound and timeout recovery leaves visible follow-up actions instead of only a red error.
