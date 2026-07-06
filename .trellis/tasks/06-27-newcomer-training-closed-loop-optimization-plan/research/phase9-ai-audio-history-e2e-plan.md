# Phase 9 AI Coach / 录音评分 / 历史回放 E2E 下一步建议

> 日期：2026-06-27
>
> 范围：只读复核与后续实现建议。未修改业务代码、测试代码或运行脚本。

## 结论摘要

- 当前 deterministic newcomer Playwright smoke 已覆盖 learner Journey active revision、商务技巧入口、admin analytics、realtime disabled 诊断；下一步可在同一 spec 上扩展 AI Coach、录音评分结果、历史回放。
- 最小实现不应让 Playwright 触发真实 LLM、真实 ASR、真实 Deucate 或真实 realtime provider。应在 smoke seed 阶段直接写入完成态 session/submission/score/history snapshot，再通过稳定 API 和少量 UI 表面验证。
- 最合适的 seed 落点是 `backend/scripts/seed_newcomer_training_path.py`，因为 `scripts/dev-smoke-up.sh` 已在启动后执行它，`scripts/critical-quality-gate.sh` 已复用该 smoke stack 跑 `web/tests/e2e/newcomer-training-closed-loop.spec.ts`。
- 历史回放当前已有后端正式接口，但 admin 训练记录详情页尚未提供回放链接；Phase 9 首批 Playwright 应先用 API 断言历史材料回放文件端点，UI 入口另列后续。

## 1. 可直接 seed / 查询的后端模型和 API

### AI Coach session

可直接 seed 的模型：

- `SalesTrainerAiCoachSession`
  - 字段已支持 `user_id`、`module_key`、`path_key`、`path_revision_id`、`path_revision_no`、`article_snapshot`、`path_config_snapshot`、`prompt_template_id`、`prompt_revision_id`、`prompt_contract_hash`、`config_snapshot`、`coach_state`、`status`、`mastery_state`、`total_score`、`max_score`、`trace_id`。
- `SalesTrainerAiCoachChatMessage`
  - 可 seed assistant/user 对话历史。
- `SalesTrainerAiCoachUiEvent`
  - 可 seed `quiz_card`、`quiz_result`、`summary_card` 等 UI event，含 `answer_payload` 和 `score_result`。
- `SalesTrainerOperationLog`
  - 可记录 `ai_coach_chat_session_created_v1` 或 deterministic e2e 专用 action。

可直接查询的 API：

- learner：
  - `POST /api/v1/newcomer-training/ai-coach/chat/sessions`
  - `POST /api/v1/newcomer-training/ai-coach/chat/sessions/stream`
  - `GET /api/v1/newcomer-training/ai-coach/chat/sessions/{session_id}`
  - `POST /api/v1/newcomer-training/ai-coach/chat/sessions/{session_id}/messages`
  - `POST /api/v1/newcomer-training/ai-coach/chat/sessions/{session_id}/events/{event_id}/answer`
- journey / record read-model：
  - `GET /api/v1/sales-trainer/journey`
  - `GET /api/v1/admin/sales-trainer/training-records/detail/ai_coach_session/{session_id}`
  - `GET /api/v1/admin/sales-trainer/journeys/analytics`

注意点：

- 真实 chat stream 会进入 `AiCoachChatStreamService` 和 generation/scoring runtime；首批 PR gate 不建议依赖它生成内容。
- 若只验证“已完成 AI Coach 进入 Journey / training record / admin analytics”，直接 seed `SalesTrainerAiCoachSession(status="completed")` 更稳。
- `TrainingRecordService._serialize_ai_coach_record()` 从 `path_config_snapshot` 读取 lineage；seed 时应写入 `path_key`、`path_revision_id`、`path_revision_no`、`module_key`、`legacy_snapshot_only=false`，避免记录详情被标记 legacy。

### Audio submission / score_result

可直接 seed 的模型：

- `SalesTrainerAudioSubmission`
  - 字段已支持 `unit_id`、`user_id`、`purpose`、`original_filename`、`content_type`、`size_bytes`、`storage_key`、`confirmed_material_version_id`、`material_snapshot`、`score_scheme_snapshot`、`task_brief_snapshot`、`status`。
- `SalesTrainerAudioTranscript`
  - 可 seed deterministic transcript，避免 ASR。
- `SalesTrainerAudioScoreResult`
  - 可 seed deterministic score，避免 Deucate。
- `SalesTrainerAudioScorePrompt`
  - seed 脚本已创建并发布 PPT 评分 prompt。

可直接查询的 API：

- learner：
  - `GET /api/v1/sales-trainer/audio-submissions/{submission_id}`
  - `GET /api/v1/sales-trainer/audio-submissions/{submission_id}/file`
- admin：
  - `GET /api/v1/admin/sales-trainer/audio-submissions`
  - `GET /api/v1/admin/sales-trainer/audio-submissions/{submission_id}`
  - `GET /api/v1/admin/sales-trainer/score-results`
  - `GET /api/v1/admin/sales-trainer/training-records/audio/{submission_id}`
  - `GET /api/v1/admin/sales-trainer/training-records/detail/audio_submission/{submission_id}`

注意点：

- `AudioSubmissionService.serialize_submission()` 会把 latest score_result、transcript、material snapshot、score scheme snapshot、task brief snapshot 一起投影给前端。
- `TrainingJourneyService._audio_outcome()` 以 submission `status="scored"` 和 score_result `passed` 决定 Journey 模块状态。
- `task_brief_snapshot.submission_context` 是 audio lineage 的关键来源；seed 时必须冻结 active revision 的 path context。

### Training record detail / history replay

可直接查询的 API：

- `GET /api/v1/admin/sales-trainer/training-records`
- `GET /api/v1/admin/sales-trainer/training-records/detail/{record_type}/{record_id}`
- `GET /api/v1/admin/sales-trainer/training-records/detail/{record_type}/{record_id}/materials/{version_id}/file`

可直接 seed 的历史回放条件：

- `SalesTrainerAudioSubmission.confirmed_material_version_id = <archived_or_published_version_id>`
- `SalesTrainerAudioSubmission.material_snapshot` 包含该 version 的冻结信息。
- 目标 `SalesTrainerMaterialVersion.status` 可以是 `archived`，普通 admin material file route 会拒绝 archived version，但 training-record historical file route 允许被记录引用的 archived version 只读回放。

注意点：

- 当前 historical replay 接口只支持 `record_type="audio_submission"`；其他 record type 会返回 `[TRAINING_RECORD_MATERIAL_REPLAY_UNSUPPORTED]`。
- 当前 admin detail 页只展示原始 payload，没有 material replay 链接；首批 E2E 用 API 断言更合适。

## 2. 最小 deterministic seed 落点

推荐直接扩展：

- `backend/scripts/seed_newcomer_training_path.py`

插入流程：

1. 继续保留现有 baseline seed：
   - owner/admin user
   - learner user
   - business etiquette article + chapters + training pack
   - AI Coach prompt/scoring prompt
   - PPT audio score prompt
   - PPT material/version
   - business skills paper
   - active path revision
2. 在 `_publish_seed_path_revision(...)` 之后、`await db.commit()` 和 `verify(...)` 之前，新增一个 idempotent helper，例如：
   - `_upsert_phase9_e2e_evidence(db, summary, actor=owner)`
3. helper 内部从 `SalesTrainerPathConfigService(db).get_config()` 读取 active revision id/no 和 module payload，避免手写 revision。
4. helper 直接 upsert 三类 deterministic evidence：
   - completed AI Coach session + chat messages + scored UI event
   - scored audio submission + transcript + score result + operation logs
   - archived historical material version referenced by that audio submission
5. `verify(...)` 增加只读校验：
   - learner Journey 出现 `ai_coach_session` outcome
   - learner Journey 出现 `audio_submission` passed outcome
   - admin score-results 可查到 seeded score
   - training record detail lineage 非 legacy
   - historical replay version 为 archived 且记录引用成立

推荐 idempotent key：

- 用固定 `original_filename = "phase9-deterministic-ppt.wav"` + seed learner + PPT unit 查找 audio submission。
- 用固定 `trace_id = "phase9-ai-coach-deterministic"` 或 `session_id` 查找 AI Coach session。
- 用固定 material key / version label，例如 `phase9-history-ppt-material` / `phase9-history-v1`。

为什么不新增独立 seed 脚本：

- 当前 `dev-smoke-up.sh` 已把 `seed_newcomer_training_path.py --apply` 接入 smoke bootstrap。
- 当前 `critical-quality-gate.sh` 已先拉 smoke stack，再跑 newcomer Playwright。
- 扩展同一 seed 能保证本地、CI、重跑、verify 使用同一 active revision 真源，避免新脚本漏调用。

为什么不走真实 provider：

- AI Coach stream 会触发 LLM generation/scoring runtime。
- 录音 `auto_process=true` 会进入 ASR + Deucate 链路。
- Phase 9 PR gate 目标是 deterministic closed-loop，不是 provider 兼容性测试；真实 provider 应放 nightly/release。

## 3. Playwright 应断言的页面和接口

### API 断言优先

1. learner Journey：
   - `GET /api/v1/sales-trainer/journey`
   - 断言：
     - `path_revision_id` 非空
     - `source === "active_revision"`
     - `modules[*].source.path_revision_id` 与 journey 一致
     - `business_skills` 下存在 `record_type="ai_coach_session"` 的 outcome
     - `ppt_explanation` 下存在 `record_type="audio_submission"` 的 outcome
     - outcome `snapshot_ref.legacy_snapshot_only === false`

2. AI Coach record detail：
   - `GET /api/v1/admin/sales-trainer/training-records/detail/ai_coach_session/{session_id}`
   - 断言：
     - `record_type === "ai_coach_session"`
     - `module_key === "business_skills"`
     - `status === "completed"`
     - `passed` 与 `mastery_state` 一致
     - `path_revision_id` / `path_revision_no` 非空
     - `ai_coach_session.trace_id` 为 deterministic seed trace

3. audio score result：
   - `GET /api/v1/admin/sales-trainer/score-results?submission_id={submission_id}`
   - 断言：
     - `total === 1`
     - `items[0].passed === true`
     - `items[0].prompt_version` 为数字
     - `items[0].deucate_model === "deterministic-e2e"` 或同类固定值

4. learner audio result：
   - `GET /api/v1/sales-trainer/audio-submissions/{submission_id}`
   - 断言：
     - `status === "scored"`
     - `transcript.transcript_text` 非空
     - `score_result.total_score` 为固定分
     - `score_scheme_snapshot.name/version/learner_rubric` 存在
     - `material_snapshot.items[0].current_version.version_label` 为固定历史版本
     - `task_brief_snapshot.submission_context.legacy_snapshot_only === false`

5. historical replay：
   - `GET /api/v1/admin/sales-trainer/training-records/detail/audio_submission/{submission_id}/materials/{version_id}/file?disposition=inline`
   - 断言：
     - HTTP 200
     - body 包含 seeded markdown 的稳定 token，例如 `PHASE9_HISTORY_REPLAY_MARKER`
   - 反向断言：
     - `GET /api/v1/admin/sales-trainer/materials/versions/{version_id}/file` 对 archived version 返回 404 和 `[MATERIAL_VERSION_NOT_PUBLISHED]`

### UI 断言只覆盖稳定结构

建议断言：

- `/sales-trainer`
  - 继续断言 active revision、核心模块存在。
  - 新增断言可基于模块卡状态或 record type，不要只依赖长文案。
- `/sales-trainer/audio/result/{submission_id}`
  - 断言页面主标题“语音作业反馈”。
  - 断言评分区显示固定总分、模型值、授权播放/下载链接路径包含 `/sales-trainer/audio-submissions/{submission_id}/file`。
  - 断言不出现 storage key 原文。
- `/admin/sales-trainer/score-results`
  - 通过 API 先拿 `submission_id`，页面只断言表格出现该 id、固定分数、prompt version。
- `/admin/sales-trainer/training-records/detail/audio_submission/{submission_id}`
  - 断言有效分、原始记录、path lineage 相关字段在 raw payload 中存在。
- `/admin/sales-trainer/training-records/detail/ai_coach_session/{session_id}`
  - 断言 record type 对应页面能加载、有效分/状态可见、raw payload 含 deterministic trace。

避免断言：

- AI Coach 生成的长文案、stream status 文案、按钮中文细节。
- 日期本地化字符串的完整格式。
- CSS class、卡片顺序、图表视觉细节。
- LLM/ASR/provider 原始错误文案。

## 4. 建议延期或需人工决策的内容

建议延期到 nightly/release 或单独任务：

- 真实 AI Coach 流式生成 happy path：
  - 需要 deterministic LLM generation/scoring seam 或正式 provider fixture。
  - 当前可先验证已完成 session 的 read-model 闭环。
- 真实录音 ASR + Deucate 评分：
  - PR gate 不应依赖 DashScope/Deucate。
  - 当前可直接 seed transcript + score_result。
- realtime 真 WebSocket：
  - 现阶段 newcomer smoke 只覆盖 disabled 诊断。
  - 真 WS 应等 runtime binding、provider readiness、outcome projection、failure taxonomy 全部稳定后进入 nightly/release。
- admin 历史材料回放 UI 入口：
  - 后端 API 已有，页面尚未提供专门链接。
  - 先 API 断言；后续若产品确认需要操作员从详情页点击回放，再补 UI。
- AI Coach 是否必须在 learner UI 中打开 seeded session：
  - 当前 coach 页面默认走 stream create/resume，可能触发 runtime。
  - 若要 UI 直接回放 seeded session，需要新增稳定入口或 query 参数，这属于业务/前端实现决策，本轮不建议偷改。
- `SalesTrainerTrainingRecordType` 前端类型当前不含 `realtime_roleplay_session`，但后端 detail API 已接受该类型；这不是本轮 AI/audio/history 的阻塞项，建议随 realtime 真 E2E 单独收口。

## 5. 推荐实施顺序

1. 扩展 `backend/scripts/seed_newcomer_training_path.py`：
   - 新增 `_upsert_phase9_e2e_evidence(...)`。
   - 新增 verify 覆盖 AI/audio/history evidence。
   - 更新 `backend/tests/unit/test_seed_newcomer_training_path.py` 断言 idempotent evidence。
2. 扩展 `web/tests/e2e/newcomer-training-closed-loop.spec.ts`：
   - 先通过 API 登录拿 token。
   - API 查 journey，发现 seeded outcome ids。
   - UI 只访问稳定页面并做结构断言。
3. 扩展 `scripts/critical-quality-gate.sh` 目标：
   - 若 seed unit test 未在 gate targets 中，加入 `tests/unit/test_seed_newcomer_training_path.py`。
   - Playwright 仍保持 newcomer spec 单文件、`--workers=1`。
4. 后续独立补 UI：
   - admin training record detail 增加历史材料回放链接。
   - AI Coach 页面增加不触发 stream 的 session resume/detail 稳定入口，前提是产品确认需要。

## 6. 验证建议

后续实现完成后建议跑：

```bash
cd backend
pytest -c pyproject.toml tests/unit/test_seed_newcomer_training_path.py --no-cov -q
pytest -c pyproject.toml tests/integration/test_newcomer_training_journey_api.py tests/integration/test_newcomer_training_path_material_api.py --no-cov -q
```

```bash
bash scripts/dev-smoke-up.sh
cd web
SMOKE_REUSE_EXISTING_STACK=1 npx playwright test tests/e2e/newcomer-training-closed-loop.spec.ts --workers=1
```

本研究未执行上述验证，因为本轮范围是只读复核和研究文件。
