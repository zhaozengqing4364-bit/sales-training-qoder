# Current State Code Inventory

## Correction

The project is significantly further along than a "needs AI coach / exam boundary" planning stage. Many items previously framed as recommendations are already implemented in code, contracts, or tests.

## Implemented Or Substantially Implemented

### Newcomer Training Path / Sales Trainer Core

* Dedicated `sales_trainer` backend domain with units, question binding, papers, audio submissions, transcripts, scoring prompts, score results, materials, AI coach sessions, operation logs, and business etiquette assets.
* Learner and admin API surfaces are split across `api.py`, `unit_api.py`, `paper_api.py`, `material_upload_api.py`, `path_config_api.py`, `business_etiquette_api.py`, `ai_coach_api.py`, and `ai_coach_admin_api.py`.
* The domain contract explicitly keeps `sales_trainer` as an async learning/training path, not a realtime WebSocket runtime.

### PPT / Audio Scoring

* Audio upload, direct object-store registration, transcription, Deucate scoring, scoring prompt governance, result retention, regrade, and operation logs are represented by services and tests.
* The design doc states the MVP audio scoring path is implemented and has real-provider smoke evidence.

### Article / Exam / Question Governance

* Traditional exam capability exists: single choice, multiple choice, true/false, short answer, paper revisions, active/working revisions, AI short-answer scoring fallback semantics, and attempt snapshots.
* Business etiquette unit quiz computes capability scores, weak capability keys, pass status, recommended chapters, and freezes question/capability snapshots.
* AI question draft workflow exists: generate drafts from source chapters, record prompt contract hash/version, edit/reject/approve drafts, and convert into formal question drafts.

### Business Etiquette Training Pack

* Markdown import parses business etiquette material into training-pack draft assets with chapters, micro chapters, knowledge points, hashes, revision metadata, and operation logs.
* Capability snapshot model exists: capability configs, mastery levels, evidence rules, chapter bindings, publish/archive, and default seed fallback.
* Release impact and retraining strategy exist: preview impact, publish with strategy, voluntary retraining, assigned retraining, operation logs, and new AI coach session creation for retraining.

### AI Coach

* Two generations of AI Coach APIs coexist:
  * Legacy turn/session API.
  * Chat-first AI coach API with messages, white-listed UI events, SSE streaming, quiz-card answers, scoring, next-action generation, and public projection.
* AI coach configuration is extensive: enabled flags, chat/streaming, resume policy, generation timeout, coach mode, allowed interaction types, allowed training-card types, allowed UI event types, proactive start, auto advance, streak thresholds, remediation strategy, summary behavior, allowed next actions, prompt binding, scoring prompt binding, retry policy, recovery prompts, min/max turns, and mastery threshold.
* Backend has typed UI event and action persistence: `sales_trainer_ai_coach_chat_messages`, `sales_trainer_ai_coach_ui_events`, and `sales_trainer_ai_coach_coach_actions`.
* Runtime prompt compilation uses `PromptTemplateService.compile_runtime_prompt_contract` for AI question generation, coach card generation, next action, and short-answer scoring.
* The learner AI Coach workbench is already a structured training surface, not just a chat page: context panel, card rendering, active quiz card, followup prompts, command bar, streaming preview, progress state, summary/guidance panel.
* Admin AI Coach config UI exists and validates high-risk settings on the client before save.

### Capability Progress / Stuck Point Signals

* Business etiquette AI coach progress service calculates unit-level pass, ready-for-field, manual-review-required, block-next, weak capability keys, recommended chapters, recommended card types, and next-step code.
* Admin dashboard already has intervention suggestion plumbing, and learner surfaces display weak capability/progress states.

### Test Surface

* There is substantial unit and integration coverage around sales trainer, business etiquette import/capabilities/question drafts/quiz/release/AI coach progress, path config, RBAC, materials, papers, revisions, score prompts, and AI coach chat.

## Important Nuance

Some plan documents still show unchecked acceptance criteria or "draft" status, but the codebase already contains many corresponding implementations. The next discussion should not assume those capabilities are absent. The productive analysis is:

1. Which implemented capabilities are cohesive enough to become the product's main user journey?
2. Which capabilities are present but not yet proven end-to-end by a demo/seed/browser validation path?
3. Which outputs from the current async training pack should become formal inputs to future realtime roleplay?
4. What is still missing to bridge from training pack assets to realtime roleplay contracts?

## Next-Level Development Question

The project should be understood as having already built a "training asset and evidence layer." The next strategic layer is a "roleplay readiness layer":

* Convert training-pack assets into roleplay-ready scenario packs.
* Convert capability weaknesses into targeted roleplay objectives.
* Convert article/quiz/AI coach evidence into persona/role constraints and evaluation rubrics.
* Gate realtime roleplay creation on knowledge, role, prompt, and scoring readiness.
* Run realtime roleplay only after the required asset contracts are complete.
