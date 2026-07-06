# Research: Phase 4 新人训练内容资产 dead data 诊断

- Query: 找出 dead data 诊断最小可闭环范围，围绕 newcomer active/working path revision、material/material_version、audio prompt snapshot、article_exam learning_content/exam_paper、audio submissions/history replay。
- Scope: internal
- Date: 2026-06-27

## Findings

### 0. 调研边界

- 当前 `task.py current --source` 返回 `Current task: (none)`，但父任务明确指定 `.trellis/tasks/06-27-newcomer-training-closed-loop-optimization-plan`，本研究写入该任务的 `research/`。
- 仓库根目录没有 `.codegraph/`，无法使用 `codegraph explore` / `codegraph node`；本次改用定向文件读取和 `rg` 定位，不做全局 grep 代替结构分析。
- 本研究只读，未修改业务代码、未运行迁移、未提交。

### 1. 相关模型 / 服务 / API 文件与关键 symbol

#### 路径 revision 与 active/working 真源

- `backend/src/sales_trainer/models.py`
  - `SalesTrainerAssetRevision`：通用 revision 表，字段包括 `resource_type`、`logical_id`、`revision_no`、`status`、`payload_json`、`payload_hash`、`change_class`、`source_revision_id`，见 `models.py:149`。
  - `SalesTrainerAssetActiveRevision`：active pointer 表，`resource_type + logical_id` 唯一，见 `models.py:199`。
- `backend/src/sales_trainer/services/path_config_models.py`
  - `NEWCOMER_PATH_RESOURCE_TYPE = "newcomer_training_path"`、`NEWCOMER_PATH_LOGICAL_ID = "newcomer_training_path_v1"`，见 `path_config_models.py:29`。
  - `validate_path_payload_for_write()` 拒绝 legacy path key、顶层 disabled、重复 module/order 和非 canonical module，见 `path_config_models.py:78`。
  - `payload_from_revision()` 读取 active/working revision payload，见 `path_config_models.py:224`。
  - `_module_refs()` 把 module 的 `target_unit_id`、`learning_content_id`、`exam_paper_id`、`material_id`、`material_version_id`、`scoring_prompt_id` 和 duration options 作为 binding diff，见 `path_config_models.py:275`。
- `backend/src/sales_trainer/services/path_config_service.py`
  - `SalesTrainerPathConfigService.get_config()`：admin 配置面优先 active revision；无 active 时返回 `source="legacy_migration_snapshot"`、`legacy_snapshot_only=true`，见 `path_config_service.py:78`。
  - `active_projection()`：learner path / journey 的 active revision 投影；无 active 返回 `None`，不再生成正式 fallback，见 `path_config_service.py:117`。
  - `publish_preview()` 已有 future-only impact scope，明确历史 attempt/submission 不因发布改变，见 `path_config_service.py:230`。
- `backend/src/sales_trainer/services/path_service.py`
  - `SalesTrainerPathService.list_paths_for_user()` 无 active projection 直接返回空列表，见 `path_service.py:29`。
- `backend/src/sales_trainer/services/training_journey_service.py`
  - `TrainingJourneyService._build_journey()` 无 active revision 直接抛 `[NEWCOMER_PATH_ACTIVE_REVISION_MISSING]`，见 `training_journey_service.py:145`。
  - Journey outcome 只纳入当前 active `path_revision_id` 匹配的 audio/quiz/AI Coach 记录，见 `training_journey_service.py:354`、`training_journey_service.py:383`、`training_journey_service.py:461`。

#### Material / material version / history replay

- `backend/src/sales_trainer/models.py`
  - `SalesTrainerMaterial`：`material_key`、`material_type`、`purpose`、`status`、`current_version_id`，见 `models.py:509`。
  - `SalesTrainerMaterialVersion`：`material_id`、`version_label`、`storage_key`、`file_hash`、`status`、`published_at`，见 `models.py:545`。
  - `SalesTrainerAudioSubmission.confirmed_material_version_id`、`material_snapshot`、`score_scheme_snapshot`、`task_brief_snapshot` 是音频提交的历史快照字段，见 `models.py:444`。
- `backend/src/sales_trainer/services/material_service.py`
  - `archive_material()` 会阻止仍被 active/working path 引用的 material 归档，见 `material_service.py:181`。
  - `resolve_unit_material_items()` 对 learner 要求 material 和 version 均 `published`，见 `material_service.py:339`。
  - `freeze_submission_snapshots()` 在录音提交时冻结 material/score scheme/task brief，见 `material_service.py:434`。
  - `resolve_file_access()` 只允许 published version 正常读取，见 `material_service.py:482`。
  - `resolve_historical_file_access()` 允许 audio submission 引用的 published/archived version 只读回放，见 `material_service.py:498`。
  - `_path_reference_blockers()` 扫 active/working path revision 中的 `material_id/material_version_id` 引用，见 `material_service.py:601`。
- `backend/src/sales_trainer/services/material_publish_workflow.py`
  - `publish_material_version()` 发布新版本时将同 material 的其他 published versions 归档，并写 `impact_scope="future_submissions_only"`，见 `material_publish_workflow.py:25`。
- `backend/src/sales_trainer/api.py`
  - admin 普通材料文件接口：`GET /api/v1/admin/sales-trainer/materials/versions/{version_id}/file`，见 `api.py:800`。
  - admin 历史记录材料回放接口：`GET /api/v1/admin/sales-trainer/training-records/detail/{record_type}/{record_id}/materials/{version_id}/file`，见 `api.py:819`。
- 测试锚点：
  - `backend/tests/integration/test_newcomer_training_path_material_api.py:426` 覆盖 archived material version 不能走普通文件接口，但可经 training record history replay 读取。
  - `backend/tests/unit/test_newcomer_training_path_material_governance.py:164` 覆盖 active path 引用 material 时禁止归档。

#### Audio prompt snapshot / regrade

- `backend/src/sales_trainer/models.py`
  - `SalesTrainerAudioScorePrompt` 是当前评分 prompt 行，含 `system_prompt`、`scoring_template`、`learner_rubric`、`version`、`status`，见 `models.py:621`。
  - `SalesTrainerAudioScoreResult` 保存 `prompt_id`、`prompt_version`、`prompt_hash`、`transcript_snapshot`、score outcome，见 `models.py:654`。
- `backend/src/sales_trainer/services/prompt_revision_payloads.py`
  - `PROMPT_RESOURCE_TYPE = "sales_trainer_audio_score_prompt"`，见 `prompt_revision_payloads.py:10`。
  - `prompt_lifecycle_snapshot()` 包含完整 prompt 内容和 rubric，见 `prompt_revision_payloads.py:22`。
- `backend/src/sales_trainer/services/prompt_revision_service.py`
  - `AudioScorePromptRevisionService` 支持 prompt working/published revision 和 initial published revision，见 `prompt_revision_service.py:34`。
- `backend/src/sales_trainer/services/audio_submission_service.py`
  - `_score()` 优先从 `submission.score_scheme_snapshot.prompt_snapshot` 重建历史 prompt；缺失才回退当前 prompt 行，见 `audio_submission_service.py:695`。
  - `_resolve_scoring_prompt_from_snapshot()` 需要 `prompt_id/system_prompt/scoring_template` 才能构造 snapshot prompt，见 `audio_submission_service.py:1015`。
  - `serialize_submission()` / `serialize_score_result()` 输出 lineage 与 `legacy_snapshot_only`，见 `audio_submission_service.py:536`、`audio_submission_service.py:611`。
- `backend/src/sales_trainer/services/audio_regrade_service.py`
  - `_require_latest_score()` 缺 score 或 `transcript_snapshot` 时不可重评，见 `audio_regrade_service.py:126`。
  - `_resolve_target_revision()` 要求 target prompt revision 存在、resource type 匹配、published、logical_id 等于历史 `score.prompt_id`，见 `audio_regrade_service.py:151`。
- `backend/src/sales_trainer/regrade_models.py`
  - `SalesTrainerRegradeRun` 是 append-only 重评记录，target_type 仅 `quiz_attempt/audio_submission`，见 `regrade_models.py:24`。

#### Article exam: learning_content / exam_paper

- `backend/src/curriculum_practice/models.py`
  - `LearningContent`：`learning_content_id`、`status`、`version`、`content_hash`，状态为 draft/published/archived，见 `models.py:220`。
  - `LearningChapter`：按 `learning_content_id + order_index` 绑定章节，见 `models.py:257`。
- `backend/src/sales_trainer/services/curriculum_practice_adapter.py`
  - `get_learning_content()` / `list_learning_chapters()` 是 sales_trainer 访问课程内容的窄适配，见 `curriculum_practice_adapter.py:64`、`curriculum_practice_adapter.py:81`。
- `backend/src/sales_trainer/services/article_binding_service.py`
  - `resolve_module_article()` 可按 active binding 校验 `learning_content_id`，并要求 content published、章节非空，见 `article_binding_service.py:42`。
  - `_active_learning_content_id()` 无 active projection 时抛 `[NEWCOMER_PATH_ACTIVE_REVISION_MISSING]`，见 `article_binding_service.py:225`。
  - `bind_module_article()` 保存 path working revision，不直接改 learner active，见 `article_binding_service.py:114`。
- `backend/src/sales_trainer/services/business_etiquette_learning_service.py`
  - `get_learning_units()` 当前读取 `get_config()` 后使用 path payload 和 article chapters 组装学习单元，见 `business_etiquette_learning_service.py:46`。
- `backend/src/sales_trainer/models.py`
  - `SalesTrainerExamPaper`：paper 到 backing `SalesTrainerUnit` 的关系，见 `models.py:101`。
  - `SalesTrainerQuizAttempt.paper_revision_id` 记录考卷 revision，见 `models.py:377`。
  - `SalesTrainerQuizAnswer.answer_payload` 可保存 question snapshot 与 attempt_context，见 `models.py:422`。
- `backend/src/sales_trainer/services/exam_paper_service.py`
  - `submit_paper_attempt()` 使用 paper active revision；若有 question snapshots 走 `PaperSnapshotAttemptService`，否则走 legacy `QuizService` 后补 attempt context，见 `exam_paper_service.py:161`。
- `backend/src/sales_trainer/services/paper_snapshot_attempt_service.py`
  - `submit_attempt()` 校验答案属于当前 paper revision，并写 `paper_revision_id` 与 answer snapshot，见 `paper_snapshot_attempt_service.py:46`。
- `backend/src/sales_trainer/services/path_attempt_context_service.py`
  - `resolve_for_paper()` / `resolve_for_unit()` 命中 active projection 时 `legacy_snapshot_only=false`；无 active 或未命中时返回 legacy context，见 `path_attempt_context_service.py:56`、`path_attempt_context_service.py:78`。
- `backend/src/sales_trainer/services/article_exam_prerequisite_service.py`
  - `_article_exam_binding_for_paper()` 先查 path config，再回看 legacy `unit.config.path`，见 `article_exam_prerequisite_service.py:80`。这是 dead data 诊断需要显式暴露的 legacy 入口。
- `backend/src/sales_trainer/services/exam_paper_serializers.py`
  - `serialize_paper_attempt()` 从 answer `attempt_context` 还原 path lineage；无 context 时 `legacy_snapshot_only=true`，见 `exam_paper_serializers.py:81`。

#### Training records / Journey 聚合

- `backend/src/sales_trainer/services/training_record_service.py`
  - `TrainingRecordService.list_records()` 已聚合 audio/quiz/AI Coach 三类记录，并可按 `material_version_id` 过滤 audio，见 `training_record_service.py:38`。
  - `_serialize_audio_record()` 输出 `material_snapshot`、`score_scheme_snapshot`、`task_brief_snapshot`，见 `training_record_service.py:274`。
  - `_serialize_quiz_record()` / `_serialize_ai_coach_record()` 使用 `training_record_lineage_fields()`，见 `training_record_service.py:388`。
- `backend/src/sales_trainer/services/training_record_lineage.py`
  - `training_record_lineage_fields()` 优先读 record 顶层 lineage，再读第一条 answer 的 `attempt_context`；仍缺失则 `legacy_snapshot_only=true`，见 `training_record_lineage.py:14`。
- `backend/src/sales_trainer/schemas.py`
  - `TrainingJourneySnapshotRef` 已有 `legacy_snapshot_only`、`regrade_unavailable`，见 `schemas.py:2513`。
  - `SalesTrainerTrainingRecordResponse` 已暴露 `legacy_snapshot_only` 和历史快照字段，见 `schemas.py:2597`。

### 2. 应诊断场景清单

下面是“最小可闭环”建议：只做只读诊断，不做自动修复、不做迁移、不改写历史。

#### A. active/working path revision 引用问题

1. `active_revision_missing`
   - 条件：`newcomer_training_path_v1` 没有 active revision。
   - 影响：learner `/paths` 返回空，journey 抛 `[NEWCOMER_PATH_ACTIVE_REVISION_MISSING]`；admin `get_config()` 仍可返回 legacy migration snapshot。
   - 分类：missing / legacy_snapshot_only。
2. `active_revision_payload_invalid`
   - 条件：active revision payload 无法 `NewcomerPathConfigPayload` validate。
   - 影响：learner/journey 不可构建。
   - 分类：missing / terminal config error。
3. `working_revision_payload_invalid`
   - 条件：working revision payload 非法。
   - 影响：发布不可用，但不影响当前 learner active。
   - 分类：working_only_error。
4. `path_module_binding_missing`
   - 条件：enabled module 缺 `target_unit_id`，article_exam 缺 `learning_content_id/exam_paper_id`，audio module 缺 material/scoring prompt 绑定。
   - 影响：journey module 进入 `error_terminal` 或 learner 入口不可用。
   - 分类：missing。
5. `path_module_binding_archived_or_missing_asset`
   - 条件：active/working module 引用的 `material_id/material_version_id/learning_content_id/exam_paper_id/scoring_prompt_id` 不存在或状态为 archived/draft。
   - 分类：missing / archived。
6. `legacy_unit_path_still_used_for_article_exam_prerequisite`
   - 条件：paper 没被 active path module 命中，但 `_article_exam_binding_for_paper()` 从 `unit.config.path` 解析出 article_exam binding。
   - 影响：可能继续由 legacy unit config 影响考试前置。
   - 分类：legacy_snapshot_only / legacy_path_dependency。

#### B. Material / material_version

1. `orphan_material`
   - 条件：material 不被 active/working path 引用，也没有任何 audio submission 的 `confirmed_material_version_id` 或 `material_snapshot` 引用。
   - 影响：可作为清理候选，但不自动归档。
   - 分类：orphan。
2. `orphan_material_version`
   - 条件：material_version 不等于 material.current_version_id，不被 active/working path 引用，不被历史 submission 引用。
   - 分类：orphan。
3. `material_current_version_missing`
   - 条件：published material 的 `current_version_id` 为空或指向不存在的 version。
   - 分类：missing。
4. `material_current_version_not_published`
   - 条件：published material.current_version status 不是 published。
   - 分类：archived / draft_leak。
5. `path_material_version_mismatch`
   - 条件：path module 同时写了 `material_id` 与 `material_version_id`，但 version.material_id 不等于 module.material_id。
   - 分类：missing / binding_mismatch。
6. `active_path_refs_archived_material_version`
   - 条件：active path module 引用 archived material_version。
   - 分类：archived。
7. `historical_material_replay_missing_reference`
   - 条件：audio submission 的 `material_snapshot.items[].current_version.version_id` 有值，但 `confirmed_material_version_id` 为空，历史回放接口无法授权确认。
   - 分类：legacy_snapshot_only。
8. `historical_material_replay_missing_file`
   - 条件：historical replay 所需 version 存在且 published/archived，但 `storage_key` 本地文件不存在且对象存储签名不可用。
   - 分类：missing。
9. `historical_material_replay_unavailable_for_non_audio`
   - 条件：quiz/AI Coach record 中出现 material snapshot 或引用，但正式回放接口只支持 `audio_submission`。
   - 分类：replay_unsupported。

#### C. Audio prompt snapshot / score / regrade

1. `audio_submission_score_scheme_missing`
   - 条件：audio submission 缺 `score_scheme_snapshot`。
   - 影响：评分或历史解释会回退 current prompt row；若 current row 变更，历史解释不稳定。
   - 分类：legacy_snapshot_only。
2. `audio_prompt_snapshot_incomplete`
   - 条件：`score_scheme_snapshot.prompt_snapshot` 缺 `prompt_id/system_prompt/scoring_template` 任一字段。
   - 分类：legacy_snapshot_only。
3. `audio_score_prompt_revision_missing`
   - 条件：score 的 `prompt_id` 无 active published `sales_trainer_audio_score_prompt` revision，或 revision 不存在。
   - 影响：不指定 target_revision_id 时重评不可用。
   - 分类：regrade_unavailable。
4. `audio_score_transcript_snapshot_missing`
   - 条件：latest score 缺 `transcript_snapshot`。
   - 影响：`SalesTrainerAudioRegradeService._require_latest_score()` 会拒绝重评。
   - 分类：regrade_unavailable。
5. `audio_score_missing_for_scored_submission`
   - 条件：submission.status=`scored` 但找不到 score result。
   - 分类：missing。
6. `audio_submission_lineage_missing`
   - 条件：`task_brief_snapshot.submission_context` 缺失或无 `path_revision_id/module_key`。
   - 分类：legacy_snapshot_only。
7. `audio_submission_path_revision_not_found`
   - 条件：submission snapshot 中的 `path_revision_id` 不存在。
   - 分类：missing / legacy_snapshot_only。
8. `audio_submission_unit_missing_or_archived`
   - 条件：submission.unit_id 指向不存在或 archived unit。
   - 分类：missing / archived。

#### D. Article exam / learning_content / exam_paper

1. `article_exam_learning_content_missing`
   - 条件：active/working article_exam module 的 `learning_content_id` 不存在。
   - 分类：missing。
2. `article_exam_learning_content_not_published`
   - 条件：learning content 是 draft/archived。
   - 分类：archived / unpublished。
3. `article_exam_chapters_missing`
   - 条件：learning content published 但没有 chapters。
   - 分类：missing。
4. `article_exam_learning_unit_chapter_order_missing`
   - 条件：module.learning_units[].source_chapter_orders 引用不存在的 chapter order。
   - 分类：missing。
5. `article_exam_paper_missing_or_archived`
   - 条件：active/working article_exam module 的 `exam_paper_id` 不存在或非 published。
   - 分类：missing / archived。
6. `article_exam_paper_active_revision_missing`
   - 条件：published paper 没有 active `sales_trainer_exam_paper` revision。
   - 影响：新 attempt 可能走 legacy quiz path。
   - 分类：legacy_snapshot_only / regrade_unavailable。
7. `paper_attempt_revision_missing`
   - 条件：attempt.paper_revision_id 为空或指向不存在 revision。
   - 分类：legacy_snapshot_only / regrade_unavailable。
8. `paper_attempt_context_missing`
   - 条件：attempt answers 没有 `attempt_context`，无法还原 path/module。
   - 分类：legacy_snapshot_only。
9. `paper_attempt_question_snapshot_missing`
   - 条件：answer payload 或 paper revision 缺 question snapshot / question_revision_id / question_payload_hash。
   - 分类：legacy_snapshot_only / regrade_unavailable。

#### E. Audio submissions / history replay / journey 可见性

1. `outcome_not_in_active_journey`
   - 条件：audio/quiz/AI Coach record 的 path_revision_id 不等于当前 active revision。
   - 影响：不会出现在当前 journey，但仍应能在 training records 中解释为 historical outcome。
   - 分类：historical_not_active，不应误报为错误。
2. `legacy_record_only`
   - 条件：record lineage `legacy_snapshot_only=true`。
   - 影响：不伪造 active revision；仅历史记录/诊断可见。
   - 分类：legacy_snapshot_only。
3. `regrade_unavailable`
   - 条件：quiz/audio 任一满足 source revision 缺失、target active revision 缺失、transcript snapshot 缺失、question snapshot 不完整。
   - 分类：regrade_unavailable。
4. `history_replay_unavailable`
   - 条件：历史 record 引用了材料版本但无法通过正式 replay API 读取。
   - 分类：missing / archived / replay_unsupported。
5. `storage_dead_file`
   - 条件：audio submission.storage_key 或 material_version.storage_key 指向不可读本地路径；对象存储 key 无法在只读诊断里 HEAD 时，应返回 `unknown` 而不是失败。
   - 分类：missing / external_unknown。

### 3. 建议新增 service / API / schema / tests 的最小文件范围

#### 建议新增

1. `backend/src/sales_trainer/services/dead_data_diagnostic_service.py`
   - 只读服务，最小职责：
     - 加载 active/working path revisions。
     - 扫描 path module refs。
     - 扫描 material/material_version 引用与 orphan。
     - 扫描 audio submission / score / prompt snapshot / regrade availability。
     - 扫描 article_exam learning_content / exam_paper / paper attempt lineage。
     - 返回 typed diagnostic items，不修改数据。
   - 不建议放进 `TrainingJourneyService`，因为 journey 是 learner/admin 单人读模型，dead data 是 ops/admin 全局诊断。
2. `backend/src/sales_trainer/dead_data_api.py`
   - 建议 endpoint：
     - `GET /api/v1/admin/newcomer-training/dead-data/summary`
     - `GET /api/v1/admin/newcomer-training/dead-data/issues?category=&severity=&limit=&offset=`
   - 权限建议复用 `can_view_sales_trainer_settings()` 或更严格的 `can_view_sales_trainer_logs()`；不要给 `content_admin`。
3. `backend/src/sales_trainer/dead_data_schemas.py` 或直接追加到 `schemas.py`
   - 若新增 DTO 较多，建议独立文件，减少 `schemas.py` 继续膨胀。
   - 最小 DTO：
     - `DeadDataIssueCategory = path_revision | material | audio_prompt | article_exam | history_replay | regrade`
     - `DeadDataIssueType`
     - `DeadDataSeverity = info | warning | error`
     - `DeadDataIssueResponse`
     - `DeadDataSummaryResponse`
   - 每条 issue 至少包含：
     - `issue_id` 稳定可去重。
     - `category`、`type`、`severity`。
     - `resource_type`、`resource_id`、`resource_label`。
     - `module_key`、`path_revision_id`、`path_revision_no`。
     - `status`：`orphan` / `missing` / `archived` / `legacy_snapshot_only` / `regrade_unavailable` / `replay_unavailable` / `external_unknown`。
     - `message`、`recommended_action`、`auto_fix_supported=false`。
     - `evidence`：只放 id/status/hash/refs，不放 prompt 正文、答案正文或敏感日志。
4. `backend/src/sales_trainer/router_registration.py`
   - include `dead_data_api` admin router。

#### 建议新增/补充测试

1. `backend/tests/unit/test_newcomer_training_path_dead_data_diagnostics.py`
   - 服务层最小覆盖：
     - active revision missing。
     - active path 引用 missing/archived material_version。
     - orphan material/material_version。
     - audio prompt snapshot missing / incomplete。
     - audio score transcript_snapshot missing -> `regrade_unavailable`。
     - article_exam learning_content missing/archived/no chapters。
     - paper attempt paper_revision_id missing -> `legacy_snapshot_only` + `regrade_unavailable`。
2. `backend/tests/integration/test_newcomer_training_dead_data_api.py`
   - API envelope、权限、分页/过滤：
     - ops/admin 可读。
     - content_admin、support、learner fail-closed。
     - summary counts 与 issue list 一致。
3. 可复用现有测试 fixture 和锚点：
   - `test_newcomer_training_path_material_api.py` 的 archived replay 场景。
   - `test_newcomer_training_path_audio_lineage.py` 的 prompt/material/path lineage 场景。
   - `test_newcomer_training_path_attempt_lineage.py` / `test_newcomer_training_path_record_lineage.py` 的 paper/record lineage 场景。
   - `test_sales_trainer_training_journey_service.py` 的 journey active revision 过滤场景。

#### 暂不建议新增

- 暂不新增 migration：最小闭环可以基于现有表和 JSON snapshots 做只读扫描。
- 暂不新增 backfill 脚本：历史回填需要业务 owner 决策，不能由诊断任务自动写。
- 暂不把 dead data 写入持久表：首版可实时扫描；如果性能不足，再考虑快照表或后台任务。
- 暂不扩展 learner API：dead data 是 admin/ops 诊断面，learner 只消费已 fail-closed 的 journey/path。

### 4. 验证命令建议

从 `backend/` 执行：

```bash
pytest tests/unit/test_newcomer_training_path_dead_data_diagnostics.py -q
pytest tests/integration/test_newcomer_training_dead_data_api.py -q
pytest tests/unit/test_newcomer_training_path_material_governance.py tests/integration/test_newcomer_training_path_material_api.py -q
pytest tests/unit/test_newcomer_training_path_audio_lineage.py tests/unit/test_newcomer_training_path_attempt_lineage.py tests/unit/test_newcomer_training_path_record_lineage.py -q
pytest tests/unit/test_sales_trainer_training_journey_service.py tests/integration/test_newcomer_training_journey_api.py -q
ruff check src/sales_trainer tests/unit/test_newcomer_training_path_dead_data_diagnostics.py tests/integration/test_newcomer_training_dead_data_api.py
```

如实现新增 API router，还应跑：

```bash
pytest tests/integration/test_newcomer_training_path_rbac_api.py tests/integration/test_newcomer_training_dead_data_api.py -q
```

### 5. 暂停条件 / 需要人工决策的历史回填问题

1. 不可自动回填 active path lineage
   - 对 `legacy_snapshot_only=true` 的旧 audio/quiz/AI Coach 记录，若没有 frozen `path_revision_id/module_key`，不要用当前 active revision 反推。
   - 需要人工确认是否按时间窗口、发布记录、用户 cohort 或 unit legacy config 分批回填。
2. 不可自动恢复 material replay
   - 若 `material_snapshot` 有 version id 但 `confirmed_material_version_id` 为空，是否允许基于 snapshot 写回确认字段，需要业务 owner 确认。
   - 若 storage_key 本地文件缺失或对象存储不可达，诊断只能标记 missing/external_unknown，不能自动替换文件。
3. 不可自动重评旧成绩
   - 缺 `transcript_snapshot`、缺 paper revision、缺 question snapshot/hash 的记录，应标记 `regrade_unavailable`，不要自动用 current prompt/paper 重算。
4. 不可自动清理 orphan
   - orphan material/material_version 可能是运营预备资产、待发布素材或外部导入中间态；首版只报，不自动归档或删除。
5. Legacy article_exam prerequisite 是行为风险，不应在 dead data 诊断中直接修
   - `ArticleExamPrerequisiteService` 仍回看 legacy `unit.config.path`。诊断应暴露影响范围；是否改为 strict active-only 需要实现任务评估兼容影响。
6. 对象存储 HEAD/签名能力需要策略
   - 只读诊断若尝试检查 OSS/COS 文件存在性，可能引入外部调用成本、权限和超时。首版建议默认只检查本地 storage path；对象存储返回 `external_unknown`，除非运维明确开启 deep check。

### 6. 相关 specs / 文档

- `AGENTS.md`：要求中文输出；强调 active/runtime path 不得用 legacy fallback 伪成功，失败要分类、可诊断。
- `CLAUDE.md`：`sales_trainer` 是新人训练路径异步学习/录音/考卷域，和 realtime runtime 分离。
- `.trellis/workflow.md`：研究和决策必须持久化到文件。
- `.trellis/spec/backend/index.md`：后端改动需遵守 service/API 分层、错误处理、日志、测试和契约要求。
- `docs/api-contract/sales-trainer.md`：
  - active revision 是 learner 路径、TrainingJourney、模块入口和训练记录上下文唯一真源。
  - 旧 unit backfill 仅迁移/诊断/历史兼容可见，必须标记 `legacy_snapshot_only=true`。
  - TrainingJourney outcome snapshot ref 已包含 `legacy_snapshot_only` 和 `regrade_unavailable`。
  - 音频、考卷、AI Coach、历史回放都要求 snapshot-first。
- `.trellis/tasks/06-27-newcomer-training-closed-loop-optimization-plan/prd.md`：R8 要求历史结果 snapshot-first，无法回填显式标记 legacy/regrade unavailable；Phase 3/4 包含 dead data dashboard/report。
- `.trellis/tasks/06-27-newcomer-training-closed-loop-optimization-plan/research/audit-synthesis.md`：已把 orphan material、未绑定 paper/question、active config 引用 archived/missing asset、legacy_snapshot_only 记录列为 dead data dashboard 范围。

## Caveats / Not Found

- 未发现现有 `dead_data_service.py`、dead data API 或 config health/dependency graph 的后端权威实现；当前只有局部 lineage 标记、history replay 和 journey 投影。
- 未发现可直接复用的 dead data DTO；`TrainingJourneySnapshotRef` 有 `legacy_snapshot_only/regrade_unavailable` 字段，但它服务于单个 learner journey，不适合作为全局诊断 issue schema。
- 未发现持久化 dead data 表；首版建议实时扫描，不新增 migration。
- 未执行测试；本任务为只读研究。
