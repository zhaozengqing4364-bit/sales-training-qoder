# 修复音频与文章做题两条数据流的闭环断裂

## Goal

sales-training-qoder 的两条核心数据流存在闭环断裂：
1. **上传音频→判断**：regrade 不回写业务表（P0）、后台评分任务异常致状态卡死（P1）、轮询无总超时（P1）。
2. **文章阅读→出题做题→判断题目**：WS examiner 空题库伪完成（P1）、已答题目仅内存未逐题落库（P1）、completion_writer 失败仍发 completed（P1）、HTTP attempt 无幂等键（P2）、_score 静默跳过（P2）、越界静默（P2）。

目标：让两条流端到端真闭环——状态机终态可达、失败显眼不伪造成功、断线可恢复、重复提交幂等、权限对象级校验到位。全程遵守 AGENTS.md「失败必须显眼；禁止吞异常、静默跳过、伪造成功」。

## What I already know（已派生确认）

- **流①主链路已闭环**：上传→OSS 直传/multipart 兜底→register（status=uploaded）→BackgroundTasks 异步 process_submission→transcribe/score→终态 scored/transcription_failed/scoring_failed；前端 `isTerminalSubmissionStatus`（learner-presenter.ts:46）覆盖三种终态；结果页有错误映射+refresh。状态机定义见 models.py:487-488。
- **regrade 现状（P0 根因）**：`audio_regrade_service.py:69-123` 的 `run_audio_submission_regrade` 仅 `self._db.add(run)` 写 `SalesTrainerRegradeRun` 审计行 + `after_snapshot_json`，**不写回** `SalesTrainerAudioScoreResult`、**不改** `submission.status`。学员结果页轮询 submission，永远看不到重判结果。
- **后台任务异常（P1）**：`tasks/process_audio.py:37-44` 的 `except Exception` 仅 log+rollback，不把 submission 置 failed。若 `_transcribe` flush 后、`_score` 前崩，状态永留 `transcribing`/`scoring`。
- **轮询无总超时（P1）**：`use-sales-trainer-submission-poll.ts:9-10` 只有单次间隔上限 30s，无总 deadline/最大次数。配合上一条→前端无限轮询，用户永久 pending。
- **流② HTTP 主链路已闭环**：阅读进度真落库（learning_progress_service.py:127 `len(completed)==total`）；前置校验 `require_article_completed`（article_exam_prerequisite_service.py:33）在后端 submit_paper_attempt 真执行，前端门控仅 UX；出题来自题库+snapshot，空题库抛 `[SALES_TRAINER_QUIZ_HAS_NO_QUESTIONS]`；判题客观自动+主观 AI 失败返 Result.fail 置 submitted 显示"待判分"。
- **HTTP attempt 无幂等键（P2）**：models.py 的 SalesTrainerQuizAttempt 无 client_token/request_id 唯一键，重复 POST submit 生成多条 attempt 重复判分。（对照：SalesTrainerRoleplayObservation 表 models.py:852 已有 `uq_..._dedupe` + request_id models.py:881，有现成范式可复用。）
- **WS examiner 半闭环**：消息链完整、断线有 `_restore_session_state`；但空题库 connect 返回 `completed("empty_question_bank")` 伪完成（examiner_runtime.py:204-208）；已答题目仅在内存/runtime_state 快照，未逐题落库 `SalesTrainerQuizAnswer`，快照 disabled 时断线丢答（session_state_service.py:268）；completion_writer 抛异常只 log warning 仍发 exam.completed（examiner_runtime.py:486-492）→结果悬挂。

## Assumptions（自主对齐，ADR-lite 记录）

- **regrade 产品定位**：默认假定为"真重判"——重判结果应回写业务表并让学员可见。若产品实际意图是"仅审计快照"，则改为去掉"重判"误导文案 + 管理后台展示 after_snapshot，不回写学员侧。**本任务采用前者（真回写）**，因为 AGENTS.md 要求"管理员操作留痕 + 用户可见结果"，且 audit-only 会让重判功能形同虚设。
- **轮询总超时默认值**：10 分钟（submission 通常 1-3 分钟完成；超时后提示"评分耗时较长，请稍后在结果页刷新或稍后重试"+保留手动 refresh）。可配置。
- **attempt 幂等键**：复用 roleplay_observation 的 `client_token` 范式——前端 submit 时生成 uuid，后端建唯一约束 `uq_quiz_attempt_client_token`，重复提交返回已存在 attempt 而非新建。
- **WS 已答题目落库**：每答一题 `_upsert_answer` 时同步 upsert `SalesTrainerQuizAnswer` 行（按 attempt_id+question_index 唯一），快照仍作加速恢复。属增量补全不重构。
- **修不破坏现有 terminal 状态**：所有失败兜底必须落到 models.py:487-488 已定义的 `*_failed` 终态，不引入新状态。

## Requirements

### R1 音频 regrade 回写（P0）
- R1.1 `run_audio_submission_regrade` 成功后，把 after_snapshot 的新分写回 `SalesTrainerAudioScoreResult`（upsert by submission_id）。
- R1.2 把 `submission.status` 置为 `scored`（若 regrade 失败置 `scoring_failed`，不卡在中间态）。
- R1.3 学员结果页轮询能拿到重判后的新分与新解析（无需改前端轮询逻辑，因 status 回到 scored）。
- R1.4 保留 `SalesTrainerRegradeRun` 审计行（before/after snapshot + actor + reason），审计不丢。
- R1.5 regrade 失败有用户可见错误 + 不污染原评分（事务回滚）。

### R2 后台评分任务异常兜底（P1）
- R2.1 `process_audio_submission_background` 的 `except Exception` 兜底：把 submission 置 `scoring_failed` + 写 error_code，再 log+rollback。
- R2.2 兜底只在「状态非终态」时执行，避免覆盖已 succeeded 的 submission。
- R2.3 兜底失败（如 DB 也挂）至少 log error 级别 + trace_id，不静默。

### R3 轮询总超时（P1）
- R3.1 `useSalesTrainerSubmissionPoll` 增加总超时（默认 10 分钟，可配置）。
- R3.2 超时后停止轮询，置 error 状态，显示"评分耗时较长，请稍后刷新或重试"+保留 manual refresh。
- R3.3 不影响已成功的终态停止逻辑。

### R4 WS examiner 空题库改错误（P1）
- R4.1 connect 时空题库不再返回 `completed("empty_question_bank")`，改为返回错误事件 + 关闭连接。
- R4.2 前端收到错误事件显示"该考核暂无题目，请联系管理员"，不显示"已完成"。

### R5 WS 已答题目逐题落库（P1）
- R5.1 `_upsert_answer` 时同步 upsert `SalesTrainerQuizAnswer`（by attempt_id+question_index 唯一）。
- R5.2 快照仍作恢复加速，但断线重连以 DB 为准恢复已答题目。
- R5.3 快照 disabled 时断线也能从 DB 恢复。

### R6 WS completion_writer 失败处理（P1）
- R6.1 `completion_writer` 抛异常时，不发 `exam.completed`，改发失败事件 + 置 report_status=failed。
- R6.2 用户看到"判分失败请重试"而非"已完成"，避免悬挂。

### R7 HTTP attempt 幂等（P2）
- R7.1 SalesTrainerQuizAttempt 增 `client_token` 列 + 唯一约束（migration）。
- R7.2 submit 时前端传 client_token，重复提交返回已存在 attempt。
- R7.3 旧数据 client_token 可空（向后兼容）。

### R8 静默跳过/越界可观测（P2）
- R8.1 `audio_submission_service.py:751` `_score` 的 `if status != "transcribed": return` 加 warning 日志 + trace_id。
- R8.2 `examiner_runtime.py:259` 答案索引越界 return `[]` 改为返回错误反馈给用户 + log。

## Acceptance Criteria

- [ ] AC1 regrade 后学员结果页能看到新分（集成测试：regrade→轮询→result 显示新分）
- [ ] AC2 后台任务抛未预期异常时 submission 终态为 scoring_failed（单测模拟 flush 后崩溃）
- [ ] AC3 轮询 10 分钟后停止并显示超时提示（单测 mock 时间）
- [ ] AC4 WS 空题库 connect 返回错误而非 completed（WS 集成测试）
- [ ] AC5 WS 断线重连后已答题目从 DB 恢复（集成测试：答 2 题→断线→重连→看到 2 题）
- [ ] AC6 completion_writer 失败时用户看到失败提示而非 completed（单测 mock writer 抛异常）
- [ ] AC7 重复 submit 同一 client_token 返回同一 attempt（单测）
- [ ] AC8 _score 静默跳过有 warning 日志（单测断言日志）
- [ ] AC9 越界答案有用户反馈（单测）
- [ ] AC10 所有失败终态均为已定义状态（scored/transcription_failed/scoring_failed/completed/failed），无新状态
- [ ] AC11 权限：regrade/quiz submit/查结果对象级校验不退化（现有测试 + 新增 regrade 回写权限测试）
- [ ] AC12 全量回归：backend pytest + web vitest + lint + typecheck 绿

## Definition of Done

- 单测覆盖每个修复点（新增复现测试优先）
- 集成测试覆盖 regrade→可见、断线重连恢复、空题库错误三条关键路径
- migration 可重复执行 + 向后兼容（client_token 可空）
- lint/typecheck/CI 绿
- 无吞异常/静默跳过/伪造成功（grep 自查）
- 交付说明含影响、兼容性、回滚路径

## Technical Approach

### 分层修复（按 PR 切分，风险从低到高）

**PR1（P1 异常兜底，低风险先上）**：R2 + R3 + R8
- 后台任务 except 兜底置 scoring_failed
- 轮询总超时 10min
- _score 静默跳过加日志、越界加反馈
- 纯防御性，不改数据模型，先上保平安

**PR2（P2 幂等，含 migration）**：R7
- SalesTrainerQuizAttempt 加 client_token 列 + 唯一约束（可空，向后兼容）
- 复用 roleplay_observation 范式
- migration 单独评审

**PR3（P1 WS examiner，中等风险）**：R4 + R5 + R6
- 空题库改错误事件
- 已答题目逐题落库（新增 upsert 路径，快照保留）
- completion_writer 失败不发 completed
- WS 测试较重，单独 PR

**PR4（P0 regrade 回写，最高风险放最后）**：R1
- regrade 写回 SalesTrainerAudioScoreResult + submission.status
- 保留审计行
- 事务保护原评分
- 集成测试 regrade→轮询→可见

### 关键约束
- 所有失败终态用 models.py 已定义状态，不引入新状态枚举
- migration 必须 dry-run + 回滚脚本
- regrade 回写走事务，失败回滚不污染原分
- WS 改动需回归 examiner 全链路消息测试

## Decision (ADR-lite)

**Context**：两条数据流的闭环断裂涉及状态机、异步任务、WS 持久化、幂等、审计回写，修复需在"真闭环"与"最小侵入"间权衡。regrade 是核心歧义点——audit-only 还是真回写。

**Decision**：
1. regrade 采用"真回写"（写回业务表 + 学员可见），因 AGENTS.md 要求管理员操作留痕且用户可见结果，audit-only 会让功能形同虚设。
2. 轮询总超时 10 分钟（可配置），超时不伪造失败，提示用户稍后刷新。
3. attempt 幂等复用 client_token 范式（与 roleplay_observation 一致），不引入新机制。
4. WS 已答题目逐题落库（增量补全），不重构快照机制，快照保留作加速。
5. 修复按风险从低到高分 4 个 PR，P0 regrade 放最后。

**Consequences**：
- regrade 真回写增加事务复杂度，但符合产品语义；若后续要 audit-only 可 feature flag 切换。
- WS 逐题落库增加 DB 写入，但题目量小（通常 <20 题），可接受。
- client_token migration 需灰度，旧数据可空。
- 4 个 PR 串行评审，降低单 PR 风险。

## Out of Scope

- continuous-audio-uploader（练习会话审计段，不参与评分流，已知独立）
- 重构 WS examiner 为 HTTP（仅修闭环，不重构架构）
- 新增题目类型/评分模型（仅修闭环，不扩功能）
- AI 判分模型替换/调优（仅保降级链）
- 前端结果页 UI 改版（仅修错误状态展示）

## Technical Notes

### 关键文件
- 流①：`backend/src/sales_trainer/services/audio_submission_service.py`、`tasks/process_audio.py`、`services/audio_regrade_service.py`、`regrade_api.py`、`web/src/hooks/use-sales-trainer-submission-poll.ts`、`web/src/app/(dashboard)/sales-trainer/audio/result/[submissionId]/page.tsx`
- 流②：`backend/src/sales_trainer/services/examiner_runtime.py`、`examiner_report_service.py`、`examiner_session_assembler.py`、`session_state_service.py`、`services/quiz_service.py`、`exam_paper_service.py`、`models.py`（SalesTrainerQuizAttempt/QuizAnswer）
- 范式参考：`models.py:852` roleplay_observation 幂等 + request_id

### 状态机定义（不新增）
- submission（models.py:487-488）：uploaded→transcribing→transcribed→scoring→scored，或→transcription_failed/scoring_failed
- quiz_attempt：submitted→scored（HTTP）/ in_progress→completed（WS）

### 风险等级
- P0：regrade 回写（事务复杂、影响学员可见结果）
- P1：异常兜底、轮询超时、WS 三项（影响数据完整性）
- P2：幂等、日志、越界（可观测性与防重复）

### 验证命令
- backend：`cd backend && pytest tests/ -x`
- web：`cd web && pnpm vitest && pnpm tsc --noEmit && pnpm lint`
- migration dry-run：`alembic upgrade --sql head`（新增 migration 时）

## Deviations（实现期发现，ADR-lite 增补）

### R5.1 持久化载体的架构修正

**原 PRD 描述**：R5.1「`_upsert_answer` 时同步 upsert `SalesTrainerQuizAnswer`（by attempt_id+question_index 唯一）」。

**实现期发现**：此字面要求违背两条架构约束，不可执行，需修正载体：
1. **领域隔离原则**（.claude/rules/L2 §10）：curriculum_practice 与 sales_trainer 禁止直接引用。`SalesTrainerQuizAnswer` 是 sales_trainer 域表（models.py:432），仅由 HTTP 路径写入（quiz_service.py:186、paper_snapshot_attempt_service.py:159）。
2. **WS examiner 无 quiz_attempt**：WS examiner 属 curriculum_practice 域，基于 `PracticeSession`（runtime_gate_contributor.py:143），无 `SalesTrainerQuizAttempt` 行可外键，不存在 attempt_id。

**真实意图与已实现的等价方案**：R5 的真实意图是「断线重连从持久化存储恢复已答题目」。该意图已由 PR3 的 R5 实现完整满足，载体为 Redis 快照而非跨域表：
- **逐题持久化**：`ExaminerWebSocketHandler.handle_message` 在每条 `exam.answer` 后调用 `_save_session_state()`（examiner_runtime.py:570-571），把含 `answers` 的 runtime 序列化写入 `SessionStateSnapshot`。
- **持久化后端**：`SessionStateService.save_state` 把快照写入 Redis（session_state_service.py:387-391，TTL 30 分钟），非纯内存。
- **断线恢复**：`get_state` 从 Redis 读快照 → `_restore_session_state` → `ExaminerRuntime.from_state` 恢复 answers（examiner_runtime.py:583-592）。
- **快照 disabled 时**：`startup_policy="required"`（默认）下 Redis 不可用直接 fail-closed 拒连接，不出现「断线丢答」中间态。

**结论**：R5.1/R5.2/R5.3 的用户可见行为（断线重连已答题目恢复）已达成。trellis-check 报告的「R5.1 未实现」基于 PRD 字面表名，未识别领域边界。本任务不跨域写 `SalesTrainerQuizAnswer`，避免破坏场景隔离。原 PRD 文案保留以体现决策轨迹，以此偏差记录为准。

**AC5 调整**：AC5「断线重连后已答题目从 DB 恢复」的「DB」实指 Redis 持久化快照。已由 `test_should_preserve_completion_writer_when_handler_restores_mid_exam`（test_examiner_runtime.py:473）覆盖 mid-exam 断线恢复链路。
