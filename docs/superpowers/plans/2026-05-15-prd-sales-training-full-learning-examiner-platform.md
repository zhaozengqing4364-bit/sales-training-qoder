# PRD: 销售训练系统完整学习与 AI 考官闭环

来源设计稿：`~/.gstack/projects/zhaozengqing4364-bit-sales-training-qoder/zhaozengqing-main-design-20260515-095407.md`  
生成时间：2026-05-15  
状态：ready-for-agent  
背景：PRD #55 Phase 2 已交付 CurriculumPlan、Stage Snapshots、LearningPath、主管复核队列、课程分析看板、StepFun 增强、知识字典与 KB Grounding。本 PRD 在该底座上补齐 COO 要求的“课本 → 教案 → 实战对练 → 考核 → 报告”完整路径。

## Problem Statement

COO 在 2026-05-13 会议中明确要求销售训练系统必须形成完整学习路径：学员先看“课本/讲义”，再进入实战训练，再由 AI 考官进行主动提问式考核，最终形成报告并进入主管复核。当前系统已经具备课程化底座、实战对练、报告、主管复核与学习路径推荐，但仍存在三类关键断点：

1. 学员没有结构化前置学习内容，通常直接进入训练，缺少统一的产品知识与销售方法论输入。
2. 当前“实习专家”是学员问、AI 答的被动答疑模式，无法满足 COO 要求的“AI 主动提问、学员回答、AI 评分”的校招面试式考核。
3. 系统没有结构化试题库、案例库和评分维度模型，无法把 AB 卷、情景题、参考答案、考察逻辑稳定地喂给 AI 考官。

这导致“学→练→考→评”的闭环不完整：学习内容无法沉淀，考核标准无法复用，主管无法基于统一证据复核，COO 演示也无法呈现从学习到认证的完整路径。

## Solution

在现有 Phase 2 课程化底座上新增三个独立能力域：`LearningContent`、`TestBank`、`ExaminerAgent`，并扩展 `PracticeTemplate`、`CurriculumPlan Stage`、`RuntimeSnapshotService` 和前端 LearningPath，使平台形成“学习 → AI 考核 → 实战对练 → 报告 → 认证复核”的完整路径。

解决方案按 6 个 Slice 分批交付：

1. **LearningContent 结构化讲义系统**：管理员可维护讲义与章节，学员可阅读并记录学习进度，完成后解锁后续阶段。
2. **TestBank 试题库系统**：结构化管理试题分类、试题、参考答案、评分维度，支持 CSV/JSONL 导入与 AI 从讲义生成考题。
3. **ExaminerAgent AI 考官**：独立于 sales_bot 和实习专家，采用 server-driven WebSocket 模式，由 AI 主动出题、逐题评分、驱动考核完成。
4. **学员分层与模板绑定**：新增 LearnerProfile，扩展 PracticeTemplate 与 CurriculumPlan Stage，支持 study/exam/practice/report 阶段编排。
5. **前端学习与考核体验**：新增学员讲义阅读页、AI 考官考核页、管理员讲义/试题/考官管理页，并集成 Dashboard 与 LearningPath。
6. **端到端集成、性能验证与交付文档**：保证现有 1622 backend tests 不降级，新增约 89 个测试，完成 COO 演示脚本和部署说明。

本期以售前岗位为试点。`department` 字段在数据模型中预留，部门自治和严格部门 RBAC 强制执行延后到 Phase 3；但 IDOR、Prompt Injection、Markdown XSS 和批量分配权限校验必须在本期完成。

## User Stories

1. As a sales trainee, I want to see a clear learning path before training, so that I know what to learn, what to practice, what to pass, and what report will be generated.
2. As a sales trainee, I want to read structured product learning materials before practice, so that I can build baseline knowledge instead of entering role-play unprepared.
3. As a sales trainee, I want chapters to be organized in an easy-to-navigate sequence, so that I can learn product knowledge step by step.
4. As a sales trainee, I want the system to remember which chapters I have completed, so that I can resume learning without losing progress.
5. As a sales trainee, I want to see a progress bar while reading learning materials, so that I understand how much content remains before I can proceed.
6. As a sales trainee, I want to mark a chapter complete after reading it, so that the system can unlock the next training stage when I finish the required material.
7. As a sales trainee, I want to return to previously completed chapters, so that I can review important product knowledge before the exam.
8. As a sales trainee, I want the study page to work on mobile, so that I can read learning materials from enterprise WeChat or a phone browser.
9. As a sales trainee, I want Markdown content to render cleanly and safely, so that learning materials are readable and do not expose me to unsafe content.
10. As a sales trainee, I want unavailable or empty learning content to show a clear empty state, so that I know to contact an administrator instead of assuming the system is broken.
11. As a sales trainee, I want partial loading failures to preserve readable chapters, so that one broken chapter does not block all learning.
12. As a sales trainee, I want the LearningPath card to show “continue learning” when I have not finished the study stage, so that I know the correct next action.
13. As a sales trainee, I want the LearningPath card to show “start exam” after I finish learning, so that the transition from learning to assessment is obvious.
14. As a sales trainee, I want the AI examiner to proactively ask the first question after connection, so that the exam feels like an interview rather than a chat tool.
15. As a sales trainee, I want the AI examiner to ask one question at a time, so that I can focus on answering without confusion.
16. As a sales trainee, I want to answer exam questions by voice or text, so that I can continue even if speech recognition is temporarily unavailable.
17. As a sales trainee, I want the system to show the current question index and total question count, so that I understand my exam progress.
18. As a sales trainee, I want to see the remaining time for each question and the whole exam, so that I can manage my answers under realistic pressure.
19. As a sales trainee, I want the system to warn me if I stay silent too long, so that I can respond before the question times out.
20. As a sales trainee, I want the AI examiner to score my answer after each question, so that I receive immediate feedback rather than waiting until the end.
21. As a sales trainee, I want per-question feedback to include dimension-level scores, so that I understand whether I missed product knowledge, customer communication, sales logic, or process planning.
22. As a sales trainee, I want the AI examiner to accept correct answers in my own words, so that I am not punished for not repeating the reference answer verbatim.
23. As a sales trainee, I want the AI examiner to ask follow-up questions when my answer is clearly off-track, so that the assessment can distinguish misunderstanding from incomplete expression.
24. As a sales trainee, I want duplicate submissions to be ignored safely, so that network retries or accidental clicks do not corrupt my exam state.
25. As a sales trainee, I want out-of-order answer messages to be ignored safely, so that reconnects or delayed packets do not advance the wrong question.
26. As a sales trainee, I want the exam to continue or recover when the network disconnects, so that I do not lose all progress because of a transient connection issue.
27. As a sales trainee, I want completed and scored questions not to be rescored after reconnecting, so that the exam remains fair and deterministic.
28. As a sales trainee, I want AI timeouts to retry once and then preserve progress, so that temporary model failures do not interrupt the full assessment.
29. As a sales trainee, I want the system to generate a final exam result after all questions or timeout, so that I know whether I passed and what to improve.
30. As a sales trainee, I want my exam result to flow into the broader training report, so that learning, exam, practice, and supervisor review form one coherent record.
31. As a sales trainee, I want the exam feature to show “coming soon” when disabled by feature flag, so that I understand why a stage is unavailable.
32. As a sales trainee, I want to set or update my learner background, so that the examiner can adjust question emphasis based on whether I am a fresh graduate, technical/non-sales transfer, or experienced sales person.
33. As a sales trainee, I want a simple first-entry self-assessment form, so that I can complete learner profiling quickly without slowing down the exam.
34. As a sales trainee, I want the default learner level to be conservative, so that missing profile data does not cause the examiner to ask overly advanced questions.
35. As a supervisor, I want exam reports to enter the supervisor review queue when relevant, so that I can calibrate certification decisions with evidence.
36. As a supervisor, I want to see dimension-level exam scores, so that I can identify whether a trainee needs product knowledge retraining, sales method coaching, or customer communication practice.
37. As a supervisor, I want to see the trainee’s full path status, so that I can distinguish incomplete learning, failed exam, unfinished practice, and pending certification.
38. As a supervisor, I want historical reports not to be recalculated, so that previously reviewed outcomes remain stable and auditable.
39. As a supervisor, I want trainees from other users not to be accessible through direct URL manipulation, so that privacy and assessment integrity are protected.
40. As an admin, I want to create and manage LearningContent, so that training teams can maintain official product learning materials.
41. As an admin, I want to create multiple chapters inside a learning content item, so that materials can map to product modules or the COO-approved course structure.
42. As an admin, I want to reorder chapters, so that the learning path matches the intended pedagogy.
43. As an admin, I want publish gates for learning materials, so that empty or invalid content cannot be assigned to learners.
44. As an admin, I want to archive obsolete learning materials, so that old content stops being used for new plans while existing snapshots remain stable.
45. As an admin, I want published learning content referenced by runtime snapshots, so that later edits do not change an already assigned learner’s session.
46. As an admin, I want to generate draft questions from a chapter using AI, so that I can bootstrap a question bank from structured materials faster.
47. As an admin, I want to preview and edit AI-generated questions before saving them, so that low-quality or inaccurate questions do not enter the bank automatically.
48. As an admin, I want to manage question categories as a tree, so that AB papers, scenario questions, and product knowledge areas can be organized consistently.
49. As an admin, I want to create and edit open-ended, scenario, and multi-step questions, so that the examiner can cover multiple assessment formats.
50. As an admin, I want to assign difficulty levels to questions, so that the examiner can adapt to trainee background.
51. As an admin, I want each question to include a reference answer, so that scoring can be grounded in an approved standard.
52. As an admin, I want each question to include scoring dimensions and weights, so that AI scoring reflects the intent behind each question.
53. As an admin, I want question tags and filters, so that I can quickly find relevant questions for a specific product, scenario, or competency.
54. As an admin, I want question status flow from draft to published to archived, so that incomplete questions cannot be used in exams.
55. As an admin, I want CSV import for single-line question content, so that existing spreadsheets can be imported efficiently.
56. As an admin, I want JSONL import for multi-line Markdown content, so that rich scenario questions can be imported without broken CSV escaping.
57. As an admin, I want import errors to show row number, field, and reason, so that I can fix only the bad rows.
58. As an admin, I want imports to run as background tasks, so that closing the page does not lose the import result.
59. As an admin, I want import file size and encoding validation, so that invalid or oversized files fail predictably.
60. As an admin, I want prompt injection scanning before publishing learning and question content, so that malicious content cannot override AI examiner instructions.
61. As an admin, I want Markdown XSS protection on all rendered learning and question content, so that admins and trainees are protected from unsafe HTML.
62. As an admin, I want to create ExaminerAgent configurations, so that different examiners can use different sources, levels, scoring policies, and timeouts.
63. As an admin, I want to test an examiner configuration before publishing it, so that I can validate question flow and scoring behavior.
64. As an admin, I want examiner publish gates to reject empty question sources, so that learners never enter a broken exam.
65. As an admin, I want PracticeTemplate to bind learning content and examiner agent, so that training templates can define the full study/exam/practice path.
66. As an admin, I want CurriculumPlan stages to distinguish study, exam, practice, and report, so that runtime behavior is driven by explicit stage type.
67. As an admin, I want stage publish gates to validate referenced assets are published, so that broken learning paths cannot be released.
68. As an admin, I want to batch assign training tasks by department and selected users, so that a pilot group can be launched quickly.
69. As an admin, I want batch assignment to skip users already assigned to the same template, so that repeated operations are idempotent.
70. As an admin, I want department scope checked when batch assigning, so that one admin cannot assign or view another department’s trainees without permission.
71. As a training designer, I want learner profiles to be manually overrideable, so that self-assessment mistakes can be corrected.
72. As a training designer, I want freshman, technical/non-sales, and experienced-sales profiles to change examiner emphasis, so that the same product topic can be assessed appropriately for different backgrounds.
73. As a training designer, I want the question bank to preserve the logic behind each question through scoring criteria, so that AI scoring reflects why the question was designed.
74. As a training designer, I want the first pilot to focus on the presales department, so that we can validate the model in the most familiar domain before generalizing.
75. As a COO, I want to see a demo of the complete path, so that I can verify the system matches the meeting requirement instead of only showing isolated features.
76. As a COO, I want the AI examiner to feel like a real interviewer, so that the product demonstrates “有来有回才叫对练”.
77. As a COO, I want structured reports after exam and practice, so that assessment results are explainable and actionable.
78. As a developer, I want ExaminerAgent isolated from sales_bot internals, so that new exam behavior does not destabilize sales practice.
79. As a developer, I want BaseWebSocketHandler to support an on_connect hook with no behavior change by default, so that server-driven exam can be added without breaking existing client-driven handlers.
80. As a developer, I want LearningProgress and ExaminerSessionState independent from PracticeSession.status, so that existing status enums do not need risky migration.
81. As a developer, I want all runtime reads to use frozen snapshots, so that historical sessions remain deterministic even after admins edit content.
82. As a developer, I want the implementation to reuse AssetRef patterns, so that LearningContentRef and TestBankRef do not duplicate existing reference/hash logic.
83. As a developer, I want baseline tests collected before model changes, so that we know whether implementation degraded existing behavior.
84. As a developer, I want exam websocket tests for reconnect, timeout, duplicate answer, and wrong question index, so that the most fragile interaction paths are protected.
85. As a developer, I want frontend tests for loading, empty, error, partial, mobile, and completion states, so that the new pages behave consistently with existing UI patterns.
86. As a developer, I want feature flag rollout, so that examiner capability can be piloted with the presales team before full release.
87. As a product owner, I want a known out-of-scope list, so that voice examiner mode, self-review dashboards, and self-test multiple-choice features do not creep into the current delivery.
88. As a product owner, I want open questions documented, so that COO demo timing, Yubo’s question logic, initial question data, and video course handling are resolved explicitly.
89. As a release owner, I want Swagger docs, screenshots/GIFs, deployment notes, and a COO demo script, so that delivery is verifiable beyond code completion.

## Implementation Decisions

- Build **LearningContent** as a deep module for structured learning materials. Its public interface should cover content CRUD, chapter CRUD/reorder, publish/archive gates, and learner progress. The module must encapsulate chapter ordering and publish validation so callers do not duplicate these rules.
- Build **TestBank** as a deep module for categories, questions, scoring dimensions, import, and publish lifecycle. CSV and JSONL parsing should live behind one import interface that returns imported count, failed count, and structured row errors.
- Build **ExaminerAgent** as a separate interaction mode under the Agent platform, not as a sales_bot subfeature. ExaminerAgent is server-driven: the server sends the first question on connect, controls active question index, scores answers, and advances the exam.
- Add a default no-op `on_connect` hook to `BaseWebSocketHandler` and override it only in examiner handler. Existing sales_bot and presentation_coach handlers must not require behavior changes.
- Place examiner WebSocket handling in the Agent interaction layer rather than in sales_bot. This preserves scenario isolation: sales_bot remains customer role-play, presentation_coach remains PPT rehearsal, examiner remains AI assessment.
- Reuse `PracticeSession` for exam sessions. Do not introduce `SessionV2`.
- Do not extend `PracticeSession.status` or `TrainingTask.status`. Store study progress in `LearningProgress`; store exam progress in `ExaminerSessionState` and reference it through runtime state where needed.
- Extend `PracticeTemplate` to optionally bind learning content, examiner agent, target learner level, and timeout configuration.
- Extend `CurriculumPlan Stage` with explicit `stage_type`: `study`, `exam`, `practice`, `report`. `stage_type` drives runtime behavior and is orthogonal to existing stage keys.
- Extend `RuntimeSnapshotService` to freeze study and exam stage assets. Study snapshots include learning content and chapters. Exam snapshots include examiner config, question source, reference answers, scoring criteria, and target level.
- Preserve historical sessions and reports. Editing latest learning content, questions, or examiner configuration must not mutate already assigned or completed runtime snapshots.
- Use `LearnerProfile` for trainee background and level. First exam entry prompts a quick self-assessment; admins can override; default is the most conservative beginner/fresh-graduate strategy.
- TestBank supports `department` fields now but strict department-wide content isolation is deferred. Batch assignment must still validate assigner department scope.
- Defer `ExamPaper` as an extra abstraction. For this pilot, the examiner selects questions directly from the question bank using category, difficulty, and count parameters.
- Support CSV for single-line escaped content and JSONL for multi-line Markdown. Both share one import endpoint and are distinguished by content type.
- Run imports as background tasks and return `task_id`; frontend polls for task status and displays per-row errors.
- Add prompt injection scanning before publishing or using learning/question content. Suspicious content is marked `security_flagged=true` and rejected from publication.
- Render Markdown through the existing sanitizer pattern with DOMPurify. No new ad hoc Markdown rendering path should be introduced.
- Prewarm examiner prompts and load question snapshots at session creation to keep first-question latency under 300ms.
- Gate examiner capability behind feature flag `curriculum.examiner`; when disabled, LearningPath shows the exam stage as “即将上线”.
- Use the existing UI system for new pages: DashboardShell, GlassCard, Button, EmptyState, ChatBubble, AudioVisualizer, GlassSheet, ErrorBoundary, StatusIndicator, ResponsiveTableWrapper, MobileTableCard. Do not introduce a new component library or new design tokens.
- LearningContent pages must support desktop and mobile layouts. Desktop uses a fixed chapter sidebar; mobile uses a chapter selector.
- Exam page uses the existing practice two-column pattern: main chat area plus right-side progress/scoring panel; mobile collapses the panel into a bottom GlassSheet.
- Batch assignment endpoint accepts selected users, template, and plan; response reports assigned, skipped, and failed counts with reasons. Reassigning the same template is idempotent.
- Keep cost target below ¥1 per exam by constraining question count, using prompt prewarm, avoiding unnecessary LLM calls, and preserving retry limits.
- Delivery should be sliced into parallel lanes: Lane A LearningContent, Lane B TestBank, then merge for PracticeTemplate/RuntimeSnapshot binding, followed by ExaminerAgent, frontend integration, and E2E/performance validation.
- Coordinate migrations because LearningContent and TestBank both touch curriculum practice models. Lane A should establish base migration order before Lane B rebases.
- Required external dependency before serious TestBank finalization: Yubo must confirm the “大类 → 子类 → 考察维度” question logic so scoring dimensions reflect the intended business assessment.

## API Contract Decisions

The implementation must expose explicit HTTP contracts for the new learning, question bank, examiner, learner progress, and batch assignment surfaces. Endpoint names should follow existing `/api/v1/...` conventions and be registered through the project’s central router pattern.

### LearningContent admin API

| Method | Endpoint | Purpose | Key contract notes |
|---|---|---|---|
| `GET` | `/api/v1/curriculum/learning-contents` | List learning contents | Supports department/status/search filters where existing list patterns allow. Returns summaries, not full chapter bodies. |
| `POST` | `/api/v1/curriculum/learning-contents` | Create learning content | Creates draft content. Requires title; description/department optional according to model validation. |
| `GET` | `/api/v1/curriculum/learning-contents/{id}` | Get learning content detail | Returns full metadata and chapter content for admin edit/detail view. |
| `PUT` | `/api/v1/curriculum/learning-contents/{id}` | Edit learning content | Edits draft or allowed mutable fields. Must not mutate frozen runtime snapshots. |
| `POST` | `/api/v1/curriculum/learning-contents/{id}/publish` | Publish learning content | Enforces publish gates: at least one chapter, non-empty chapter content, continuous chapter order, no security flags. |
| `POST` | `/api/v1/curriculum/learning-contents/{id}/archive` | Archive learning content | Must protect active plan references according to existing archive semantics. |
| `GET` | `/api/v1/curriculum/learning-contents/{id}/chapters` | List chapters | Returns ordered chapters for admin editing. |
| `POST` | `/api/v1/curriculum/learning-contents/{id}/chapters` | Create chapter | Supports Markdown first; `content_type=video/mixed` may be stored but video embedding is deferred. |
| `PUT` | `/api/v1/curriculum/learning-contents/{id}/chapters/{chapter_id}` | Edit chapter | Updates chapter title/content/order-related fields without affecting existing snapshots. |
| `DELETE` | `/api/v1/curriculum/learning-contents/{id}/chapters/{chapter_id}` | Delete chapter | Must preserve publish gate validity after deletion. |
| `POST` | `/api/v1/curriculum/learning-contents/{id}/chapters/reorder` | Reorder chapters | Validates complete, gap-free ordering. |

### Learner study progress API

| Method | Endpoint | Purpose | Key contract notes |
|---|---|---|---|
| `GET` | `/api/v1/learner/study/progress/{learning_content_id}` | Get my progress for one learning content | Scoped to authenticated user. Must not expose another user’s progress. |
| `POST` | `/api/v1/learner/study/progress/{learning_content_id}/complete-chapter` | Mark chapter complete | Idempotent for already completed chapter IDs. Updates status to completed when all required chapters are done. |
| `GET` | `/api/v1/learner/study/status` | Get my study statuses | Returns all relevant study-stage statuses for dashboard/LearningPath cards. |

### TestBank API

| Method | Endpoint | Purpose | Key contract notes |
|---|---|---|---|
| `GET` | `/api/v1/curriculum/test-bank/categories` | Get category tree | Returns parent/child category structure. |
| `POST` | `/api/v1/curriculum/test-bank/categories` | Create category | Supports department field reservation; strict department isolation deferred. |
| `PUT` | `/api/v1/curriculum/test-bank/categories/{id}` | Edit category | Must preserve tree integrity. |
| `DELETE` | `/api/v1/curriculum/test-bank/categories/{id}` | Delete category | Rejects unsafe deletion when children or questions depend on the category. |
| `GET` | `/api/v1/curriculum/test-bank/questions` | List questions | Supports category, difficulty, status, and tag filters. |
| `POST` | `/api/v1/curriculum/test-bank/questions` | Create question | Creates draft question with content, reference answer, scoring criteria, tags, and difficulty. |
| `GET` | `/api/v1/curriculum/test-bank/questions/{id}` | Get question detail | Returns full question content and scoring criteria for editing. |
| `PUT` | `/api/v1/curriculum/test-bank/questions/{id}` | Edit question | Updates mutable fields and version hash; must not mutate frozen snapshots. |
| `POST` | `/api/v1/curriculum/test-bank/questions/{id}/publish` | Publish question | Requires reference answer, scoring criteria validity, no security flags. |
| `POST` | `/api/v1/curriculum/test-bank/questions/{id}/archive` | Archive question | Existing exam snapshots remain unchanged. |
| `POST` | `/api/v1/curriculum/test-bank/import` | Import CSV/JSONL question data | Multipart/file upload. Enforces 10MB limit, encoding validation, background task creation, and structured row errors. |

### ExaminerAgent API

| Method | Endpoint | Purpose | Key contract notes |
|---|---|---|---|
| `GET` | `/api/v1/agent/examiners` | List examiner agents | Returns examiner configs for admin list. |
| `POST` | `/api/v1/agent/examiners` | Create examiner agent | Creates draft `agent_type=examiner` config with question source, target level, scoring policy, and timeout policy. |
| `GET` | `/api/v1/agent/examiners/{id}` | Get examiner detail | Returns full examiner configuration. |
| `PUT` | `/api/v1/agent/examiners/{id}` | Edit examiner | Updates draft or mutable config; published snapshot semantics must be preserved. |
| `POST` | `/api/v1/agent/examiners/{id}/publish` | Publish examiner | Rejects empty question source, unpublished question references, invalid scoring policy, and security-flagged content. |
| `POST` | `/api/v1/agent/examiners/{id}/test` | Test examiner | Runs simulated examiner dialogue for admin validation without creating learner certification records. |

### Training task batch assignment API

| Method | Endpoint | Purpose | Key contract notes |
|---|---|---|---|
| `POST` | `/api/v1/training-tasks/batch-assign` | Batch assign learning/exam/practice tasks | Accepts `user_ids`, `template_id`, and `curriculum_plan_id`. Returns `assigned`, `skipped`, and `failed` counts with reasons. Must be idempotent for already assigned users and validate assigner department scope. |

### Import result contract

`POST /api/v1/curriculum/test-bank/import` must return a task identifier immediately. The completed task result must include structured counts and row-level errors:

```json
{
  "imported": 45,
  "failed": 3,
  "errors": [
    {"row": 12, "field": "difficulty", "message": "无效值: expert，合法值: beginner|intermediate|advanced"},
    {"row": 27, "field": "content", "message": "content 不能为空"},
    {"row": 41, "field": "category", "message": "分类 '财务报销' 不存在"}
  ]
}
```

## WebSocket Protocol Decisions

The AI examiner protocol is server-driven. The client opens the exam WebSocket for an exam `PracticeSession`; the server builds/fetches the frozen runtime snapshot, sends session initialization, and immediately sends the first question through `on_connect`.

### Exam connection flow

1. Learner enters exam page and creates or resumes a `PracticeSession` for an `exam` stage.
2. `RuntimeSnapshotService` freezes examiner config, question source, reference answers, scoring criteria, and target learner level.
3. WebSocket connects to the examiner handler.
4. Server sends `session.init` and the first `exam.question` without waiting for a learner message.
5. Learner sends `exam.answer` for the active question.
6. Server scores the answer, emits `exam.feedback`, then emits the next `exam.question`.
7. Server emits `exam.completed` when all questions are done or the session timeout is reached.
8. Result is persisted into the evaluation/reporting path and, when applicable, the supervisor review queue.

### Server → Client: `exam.question`

Sent by the server when a question becomes active.

```json
{
  "type": "exam.question",
  "question_index": 1,
  "total_questions": 10,
  "content": "请说明你会如何向客户解释实习产品的核心价值。",
  "per_question_timeout_s": 120
}
```

Required semantics:

- `question_index` is 1-based and must match the active question tracked by `ExaminerSessionState`.
- `total_questions` is frozen from the runtime snapshot.
- `per_question_timeout_s` defaults to 120 seconds unless overridden by examiner/template policy.

### Client → Server: `exam.answer`

Sent by the learner client for the currently active question.

```json
{
  "type": "exam.answer",
  "question_index": 1,
  "content": "我会先确认客户当前培训痛点，再说明系统如何通过 AI 对练、报告和主管复核形成闭环。"
}
```

Required semantics:

- Server only accepts answers where `question_index` equals the current active question.
- Wrong-index answers are logged as warnings and ignored; they must not advance exam state.
- Duplicate answers for the same accepted `question_index` are ignored after the first accepted answer.
- Empty or unusable content follows validation/error handling but must not crash or interrupt the exam UI.

### Server → Client: `exam.feedback`

Sent after the active answer is scored.

```json
{
  "type": "exam.feedback",
  "question_index": 1,
  "score": 8,
  "max_score": 10,
  "dimension_scores": [
    {"name": "知识准确性", "score": 4, "max_score": 5},
    {"name": "客户沟通", "score": 4, "max_score": 5}
  ],
  "comment": "回答覆盖了客户痛点和训练闭环，但可以补充更多产品功能证据。"
}
```

Required semantics:

- Scores must be derived from frozen reference answer and scoring criteria.
- Reference answer is not an exact-match string; semantically correct answers in the learner’s own words can receive high scores.
- Malformed LLM scoring output falls back safely according to examiner scoring error policy and is logged.

### Server → Client: `exam.completed`

Sent when the exam ends normally or by session timeout.

```json
{
  "type": "exam.completed",
  "total_score": 82,
  "max_score": 100,
  "passed": true,
  "dimension_summary": [
    {"name": "知识准确性", "score": 38, "max_score": 45},
    {"name": "客户沟通", "score": 28, "max_score": 35},
    {"name": "流程规划", "score": 16, "max_score": 20}
  ],
  "summary": "产品价值表达较完整，客户追问处理仍需加强。",
  "next_action": "进入实战对练"
}
```

Required semantics:

- Completion writes the final evaluation/reporting records once.
- Reconnect after completion must not create duplicate reports.
- Certification-oriented exams route to supervisor review according to existing review queue rules.

### Timeout and recovery parameters

| Parameter | Default | Purpose |
|---|---:|---|
| `per_question_timeout_s` | 120 | Maximum answer time per question. Timeout skips the question, assigns zero for that question, and advances to the next question. |
| `session_timeout_minutes` | 30 | Maximum exam duration. Timeout ends the current question, summarizes already scored answers, and emits `exam.completed`. |

Recovery rules:

- Speech recognition failure degrades to text input without interrupting the exam.
- AI response timeout retries once; if retry fails, current progress is saved and the learner can resume later.
- Network reconnect restores the current question position from `ExaminerSessionState`.
- Already scored questions are never rescored during reconnect.
- If the learner is silent for half of `per_question_timeout_s`, the server prompts the client to show a remaining-time warning.

## Testing Decisions

- Good tests should verify externally observable behavior: API responses, state transitions, published/unpublished gates, WebSocket message flows, import results, rendered UI states, and persisted reports. Tests should not assert private helper implementation details unless the helper is a deep module interface.
- Before implementation, run `pytest backend/tests/ --co -q` to record the backend baseline count. Current expected baseline from the design document is 1622 backend tests. Existing curriculum_practice tests must remain green before any Slice is marked complete.
- Test **LearningContent** lifecycle: create, edit, publish, archive, publish rejection for no chapters, publish rejection for empty chapter content, publish rejection for non-contiguous chapter order, archive rejection when active plan references content, deterministic snapshot hash.
- Test **Chapter** ordering: valid reorder, gaps, duplicates, missing IDs, idempotent reorder.
- Test **LearningProgress**: complete chapter, complete already-completed chapter idempotently, complete chapters out of order, concurrent completion conflict behavior, transition from reading to completed.
- Test **TestBank QuestionItem** lifecycle: CRUD, publish gate for missing reference answer, publish/archive behavior, filtering by category/difficulty/status/tag, version hash changes.
- Test **QuestionCategory**: parent/child tree, duplicate name handling where applicable, deletion rules when questions or children exist.
- Test **CSV import**: valid rows, RFC 4180 escaped commas/quotes, invalid difficulty, empty content, unknown category, mixed valid/error rows, structured row error output.
- Test **JSONL import**: multi-line Markdown content, malformed JSON line, missing required field, mixed valid/error lines.
- Test **import safety**: file >10MB returns rejection, illegal encoding rejects, UTF-8/GBK accepted when supported, background task returns task_id and final result.
- Test **AI generated questions**: valid LLM output creates draft QuestionItems, malformed output returns actionable error, generated questions remain preview/editable before save, prompt injection content is rejected.
- Test **ExaminerAgent prompt generation** across learner levels: beginner/fresh graduate emphasizes basics and learning potential; technical/non-sales emphasizes sales conversion and customer communication; experienced sales emphasizes advanced tactics and complex scenarios.
- Test **ExaminerAgent scoring**: valid LLM JSON parses dimension scores, malformed JSON falls back safely with logging, reference answers are used as criteria not exact strings.
- Test **Examiner WebSocket**: on_connect sends first question, snapshot build failure returns graceful error, empty question bank is blocked, normal full flow asks all questions and emits completion, wrong question_index is ignored, duplicate answer is ignored after first, answer after completion is ignored, per-question timeout skips and scores zero.
- Test **reconnect behavior** as critical integration coverage: reconnect mid-exam restores active question and does not rescore completed questions.
- Test **batch assignment**: assign to new users, skip already assigned users idempotently, reject cross-department assignment, reject invalid template/plan references.
- Test **frontend StudyPage**: chapter list renders, chapter content switches, final chapter shows CTA, mobile dropdown switches content, empty/error/partial states render correctly.
- Test **frontend ExamPage**: WebSocket connection transitions from loading to first question, idle timeout warning renders, disconnect/reconnect banner renders, progress panel updates, exam completed view renders final report.
- Test **frontend ImportPage**: valid CSV shows success count, failed rows show error table with line numbers and fields, invalid file type or oversize displays clear error.
- Add E2E tests for: study → exam transition; full exam → report → dashboard update; import question bank → bind examiner → learner takes exam.
- Add performance checks for examiner first-question latency <300ms after prewarm, per-question scoring latency <2s, and 100 concurrent imports within the 10MB file limit without resource exhaustion.
- Prior art in this codebase: backend unit/integration/contract/performance/e2e test directories, frontend Vitest tests in `web/tests/`, existing curriculum_practice tests, existing WebSocket handler tests, and existing LearningPath/dashboard patterns should be followed rather than inventing a new testing style.

## Out of Scope

- Voice-first examiner mode with StepFun voice channel switching and interruption handling. The current phase supports voice/text answer input with graceful fallback, but full voice examiner behavior is deferred.
- Examiner self-review analytics dashboard. Data can be collected now, but the dedicated analytics frontend is deferred.
- Chapter self-test multiple-choice quizzes. This requires separate question/option/answer models and UI components and is deferred.
- Strict department-wide RBAC for all learning content and question bank operations. Department fields are reserved now; full department autonomy is Phase 3. Security-critical batch assignment scope checks remain in scope.
- ExamPaper template abstraction. The pilot selects questions directly from TestBank by category, difficulty, and count.
- Video embed implementation for learning chapters. The model reserves `content_type` and `media_url`; Phase 2 focuses on Markdown content.
- CSV/JSONL import preview-confirm wizard. Current import page is upload → background task → result/error details in one page.
- Recalculating historical reports. Existing reports remain immutable.
- Changing `User.role` DB constraints. Learner/profile/department fields are introduced without altering role constraints.
- Replacing the current CurriculumPlan architecture. This PRD extends the existing architecture rather than rebuilding it.

## Further Notes

- The most urgent business dependency is confirming Yubo’s question taxonomy: “大类 → 子类 → 考察维度”. Without this, TestBank can be built technically but may encode the wrong assessment model.
- The COO originally requested a demo next Tuesday/Wednesday, while the full plan is a 4-5 week delivery. If a near-term demo is mandatory, build a 2-week MVP path: LearningContent + basic TestBank seed + prompt-based ExaminerAgent + minimal exam page, behind `curriculum.examiner` feature flag.
- Initial data is needed: at least 20 presales pilot questions covering 3+ scoring dimensions, plus the initial 7-chapter learning content derived from existing materials.
- Success should be demonstrated with a COO script: learner opens dashboard, completes learning, starts AI exam, answers several questions, receives dimension feedback, enters practice/report/review path.
- Security hardening is not optional because user-generated/imported content is fed into prompts and rendered as Markdown. IDOR, prompt injection scanning, RBAC checks for batch assignment, and Markdown sanitization are all part of the MVP-quality baseline.
- The implementation should remain intentionally simple: no SessionV2, no new component library, no unnecessary ExamPaper abstraction, and no broad refactor of existing sales_bot or presentation_coach flows.
