# AI Sales Training Market Patterns

## Sources

* Mindtickle AI Sales Role Play: https://www.mindtickle.com/platform/ai-sales-role-play/
* Second Nature product page: https://secondnature.ai/product/
* Gong sales training software / AI Trainer: https://www.gong.io/sales-training-software and https://help.gong.io/docs/how-to-create-and-manage-ai-trainer
* Hyperbound AI Sales Roleplay & Coaching Platform: https://www.hyperbound.ai/
* Business Insider, "How AI Sales Coaches Are Taking Over Training" (2026-03): https://www.businessinsider.com/ai-sales-coaching-tools-enterprise-training-2026-3

## Common Patterns

1. The strongest products do not sell "chatbot practice" alone. They combine content, scenarios, practice, scoring, certification, analytics, and manager coaching.
2. Roleplay generation from existing content or real sales calls is becoming a standard capability. This maps to our existing content/prompt/material governance rather than requiring a new runtime first.
3. Enterprise buyers care about measurable readiness: scorecards, progress tracking, certification, manager time saved, and skill-gap visibility.
4. AI practice is positioned as a supplement to human coaching, not a full replacement. Manager review and targeted intervention remain important.
5. The industry is moving from generic simulations toward buyer/context-specific practice: real calls, real objections, industry scenarios, region/customer context.
6. A credible platform needs governance: scenario authoring, rubric/version control, audit trail, safe AI output, and analytics. This is especially true for regulated or complex selling.

## Mapping To This Repo

1. This project already has a better governance foundation than a pure demo chatbot: training paths, article/exam/audio scoring, prompt templates, operation logs, config contracts, and admin surfaces.
2. The current weak point is not lack of AI interaction. It is proving repeatable training value through a polished end-to-end package: content import, capability points, reviewed AI question drafts, typed coach cards, scoring evidence, manager stuck-point view, and versioned rollout.
3. Realtime voice roleplay should remain a later stage for `sales_trainer`. The repo contract already says realtime belongs to `sales_bot` / `practice_sessions` / `training_runtime`, and newcomer training should not directly create realtime sessions.
4. The next commercially meaningful step is to turn "新人训练路径" into a content-package engine that can create and operate reusable training packs, starting with 商务礼仪 and later expanding to industry/role-specific packs.
5. Once content packs produce reliable learning records and skill gaps, realtime roleplay can consume those packs as scenario/rubric inputs rather than becoming a separate product island.

## Feasible Strategic Directions

### Direction A: Training Pack Engine

Turn the system into a governed training-pack platform: import content, define capability points, generate/review questions, run article/exam/audio/coach practice, and expose manager stuck-point analytics.

Pros:
* Best fit with current code and active tasks.
* Produces business value before realtime voice complexity.
* Creates reusable assets for later industry and realtime expansion.

Cons:
* Less visually impressive than live roleplay demos.
* Requires discipline in content/rubric quality and admin UX.

### Direction B: AI Coach Workbench First

Make the chat/card AI coach the primary product surface, focusing on adaptive drills, feedback, remediation, and learner engagement.

Pros:
* Strong learner experience.
* Differentiates from static LMS/training systems.

Cons:
* Without training-pack governance and manager analytics, it risks becoming a polished chatbot with weak operational proof.
* Higher prompt/schema/testing burden.

### Direction C: Realtime Roleplay Acceleration

Prioritize live buyer simulation and voice interaction, using existing `sales_bot`/runtime capabilities.

Pros:
* Strong demo value and closer to market's visible AI roleplay trend.
* Can support objection handling and consultative selling scenarios.

Cons:
* Conflicts with current `sales_trainer` contract if rushed.
* Depends on stable content, rubrics, scenario contracts, realtime reliability, and observability.
* Higher engineering and QA risk before the offline/coach loop proves value.

## Recommendation

Use Direction A as the 1-2 month anchor, with Direction B as the learner-facing interaction layer inside it. Keep Direction C as a 2-3 month gated expansion that consumes proven packs, capability points, rubrics, and manager insight data.
