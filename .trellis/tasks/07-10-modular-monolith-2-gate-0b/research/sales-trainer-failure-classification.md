# Gate 0B Sales Trainer 失败分类

## 结论

- 诊断范围：5 个文件、65 个测试；稳定复现为 `13 failed, 52 passed`。
- 分类：**0 个生产 bug，10 个 fixture 漂移，3 个断言语义漂移**。
- 13 项都能在测试侧恢复当前合同；没有证据支持放松生产发布校验、active revision、对象级访问或 canonical module 约束。
- 当前合同的关键事实：
  - canonical path resource/logical id 均由
    `NEWCOMER_PATH_RESOURCE_TYPE="newcomer_training_path"`、
    `NEWCOMER_PATH_LOGICAL_ID="newcomer_training_path_v1"` 定义；
    `new_seller_modules_v1` 只是只读兼容 alias。
  - `ppt_explanation -> audio_scoring -> purpose=ppt_pitch`；
    `elevator_pitch -> audio_scoring_group -> purpose=elevator_pitch`。
  - active path 访问 fail-closed；`QuizService.submit_attempt` 与
    `AudioSubmissionService.create_submission` 都先通过 active revision / unit unlock 检查。
  - platform `admin` / `super_admin` 被明确允许进入 learner path 做开发、调试和产品验收，
    但仍使用自己的 learner journey 和进度隔离；`training_manager` 不因此获得 learner entry。
  - business skills 已成为 `newcomer_learning_topics_v1` 中非 required、非 blocking 的学习专题；
    其测验成绩不得推进 required-path `training_stage`。

## 复现证据

从 `backend/` 执行：

```bash
.venv/bin/pytest -q --no-cov --tb=short \
  tests/unit/test_newcomer_training_path_audio_lineage.py \
  tests/unit/test_newcomer_training_path_record_lineage.py \
  tests/unit/test_sales_trainer_phase2_projection.py \
  tests/unit/test_sales_trainer_realtime_roleplay_start.py \
  tests/unit/test_sales_trainer_services.py
```

结果：`65 collected, 13 failed, 52 passed, 1 warning in 32.35s`。分别重跑文件仍为
`5 + 1 + 1 + 1 + 5`，不是顺序或共享状态 flake。

相邻权威绿色证据：

```bash
.venv/bin/pytest -q --no-cov --tb=short \
  tests/unit/test_audio_evaluation_scenarios.py \
  tests/unit/test_newcomer_training_path_audio_lineage.py::test_should_use_path_audio_bindings_when_submitting_and_scoring \
  tests/unit/test_newcomer_training_path_permissions.py::test_admin_can_enter_learner_path_for_dev_and_acceptance \
  tests/unit/test_newcomer_learning_topic_config_service.py::test_learning_topic_is_projected_separately_and_not_path_blocking \
  tests/unit/test_sales_trainer_training_journey_service.py::test_should_ignore_legacy_business_skills_regrade_in_required_journey_history \
  tests/unit/test_sales_trainer_training_journey_service.py::test_training_record_detail_audit_logs_include_journey_level_context \
  tests/unit/test_business_etiquette_quiz_service.py::test_should_load_business_etiquette_unit_quiz_from_published_questions
```

结果：`12 passed, 1 warning in 3.63s`。

Git 语义也与现状一致：audio scenario 校验来自 `0e4f5ad0 feat: govern newcomer audio training tasks`；
admin learner-entry 与 learning-topic 解耦来自 `5e1428ea feat(newcomer-training): 学习专题独立治理与并行收口`。

## 生产调用链事实

### Audio / lineage

```text
test fixture
  -> SalesTrainerPathConfigService.save_config
  -> publish_config
  -> _prepare_publish_target
  -> _validate_publish_payload
  -> _validate_audio_module / _validate_audio_group_module
  -> _published_audio_unit_for_target
  -> _validate_audio_unit_scenario
  -> _validate_audio_prompt
  -> _validate_audio_materials
```

`_validate_audio_unit_scenario` 先用 module 的 `scenario_key/module_key` 求 expected scenario，
再从 unit `config.audio.scenario_key`、`config.path.module_key` 或 `config.audio.purpose` 求 actual。
expected/actual 不同就返回 `[NEWCOMER_MODULE_CONFIG_INVALID]`。因此旧 fixture 的
`general_audio_scoring` 或空 config 必须先修正，不能把后续 prompt/material 断言当成生产回归。

发布后 submission 链路为：

```text
AudioSubmissionService.create_submission
  -> EffectiveAudioTrainingConfigResolver.resolve_for_unit(allow_legacy=False)
  -> require_learner_active_path_unit_access
  -> material policy / frozen snapshots
  -> freeze_submission_context(path revision/module lineage)
```

这条链说明 lineage 断言本身没有坏；失败全部发生在到达 lineage 冻结前的 fixture 发布阶段。

### Permission

```text
can_enter_sales_trainer_realtime
  -> can_enter_sales_trainer_learning_path
     -> active check
     -> admin/super_admin => True (dev/debug/acceptance)
     -> learner roles => True
```

`get_published_unit_brief`、units、paths、journey 最终也走相同 learner-entry 与 journey/object
检查。admin 不是绕过对象范围，而是以自身 user id 进入隔离的 journey。

### Quiz / topic / stage

```text
QuizService.submit_attempt
  -> load published quiz unit
  -> require_learner_active_path_unit_access
     -> TrainingJourneyService.get_learner_journey
        -> require active path revision
        -> active learning topics projection
        -> remove learning-topic source modules from required modules
        -> apply unlock
  -> validate answers / score / snapshot
```

`TrainingRecordService.list_records` 在序列化记录后调用
`_attach_journey_context -> TrainingJourneyService.get_admin_journey`，所以记录的
`training_stage` 是 required journey 的总体 stage，不是当前单条 business-etiquette 记录的 passed 状态。

## 逐项分类

| # | 失败 | 分类 | 直接证据 | 最小正确修复文件 |
|---|---|---|---|---|
| 1 | `test_should_reject_audio_submission_for_unit_outside_active_path` | fixture 漂移 | active `elevator_pitch` option 的 unit `config={}`，发布在 scenario 校验处失败，尚未进入 outside-unit access 断言。 | `backend/tests/unit/test_newcomer_training_path_audio_lineage.py` |
| 2 | `test_should_freeze_path_revision_lineage_when_submitting_audio` | fixture 漂移 | module 是 `ppt_explanation`，unit/prompt/request 却仍用 `general_audio_scoring`；邻近绿色测试使用 `ppt_pitch`。 | 同上 |
| 3 | `test_should_use_effective_path_config_for_unit_brief_api` | 断言语义漂移 | production 明确允许 platform admin；`test_admin_can_enter_learner_path_for_dev_and_acceptance` 绿色。实际返回 200，不是 403。 | 同上 |
| 4 | `test_should_reject_publishing_audio_path_without_effective_prompt` | fixture 漂移 | unit 的 generic purpose 先触发 scenario invalid，导致没走到 `_validate_audio_prompt` 的 `[NEWCOMER_MODULE_BINDING_MISSING]`。 | 同上 |
| 5 | `test_should_expose_audio_score_result_path_revision_lineage` | fixture 漂移 | 与 #2 相同，发布前 scenario mismatch；score-result lineage 代码尚未执行。 | 同上 |
| 6 | `test_should_expose_audio_training_record_path_revision_lineage` | fixture 漂移 | 与 #2 相同，发布前 scenario mismatch；record serializer 尚未执行。 | `backend/tests/unit/test_newcomer_training_path_record_lineage.py` |
| 7 | `test_training_records_filter_by_module_stage_and_levels` | 断言语义漂移 | business-etiquette attempt 是 learning-topic evidence，不推进 required journey；实际/相邻绿色权威断言均为 `training_stage="not_started"`。记录自身仍 `passed/scored`。 | `backend/tests/unit/test_sales_trainer_phase2_projection.py` |
| 8 | `test_realtime_roleplay_enter_permission_is_learner_only` | 断言语义漂移 | `can_enter_sales_trainer_realtime` 委托 learner-path entry；admin 合同是 True，training_manager 仍 False。 | `backend/tests/unit/test_sales_trainer_realtime_roleplay_start.py` |
| 9 | `test_should_publish_quiz_unit_and_score_choice_answer` | fixture 漂移 | unit 发布了，但没有 active path revision，gate fail-closed 为 unit not found，评分逻辑未执行。 | `backend/tests/unit/test_sales_trainer_services.py` |
| 10 | `test_should_reject_incomplete_quiz_attempt_before_creating_snapshot` | fixture 漂移 | 同 #9；访问校验先于 incomplete-answer 校验，故收到 `[SALES_TRAINER_UNIT_NOT_FOUND]`。 | 同上 |
| 11 | `test_should_score_short_answer_with_ai_and_store_feedback_snapshot` | fixture 漂移 | 同 #9；active path missing，AI short-answer scorer 未执行。 | 同上 |
| 12 | `test_should_submit_short_answer_attempt_when_ai_scoring_provider_fails` | fixture 漂移 | 同 #9；active path missing，provider-failure fallback 未执行。 | 同上 |
| 13 | `test_should_project_sales_trainer_path_with_unlock_progress` | fixture 漂移 | 把 canonical `elevator_pitch` 伪装成 `article_exam` + quiz unit；现行强制类型是 `audio_scoring_group`。同时旧“两级 article quiz required path”意图已与 learning-topic 解耦冲突。 | 同上；该测试需按现行 seam 重写，不能只换一个字符串。 |

## 变更簇与依赖

### 簇 A：Audio canonical scenario + lineage（可与其他簇并行）

修改两个 lineage 测试文件，生产文件不动：

1. PPT fixture 统一使用：
   - module `module_key="ppt_explanation"`、`module_type="audio_scoring"`、
     `scenario_key="ppt_explanation"`；
   - unit `config.audio.scenario_key="ppt_explanation"`、`purpose="ppt_pitch"`；
   - prompt `purpose="ppt_pitch"`；
   - submission request `purpose="ppt_pitch"`；
   - material/version 保持已发布且 path binding 指向当前 version。
2. Outside-path 测试的 active option unit 使用
   `scenario_key/purpose="elevator_pitch"`，module 也显式带该 scenario；outside unit 仍不进入 active path。
3. Missing-prompt 测试只补 canonical PPT scenario/purpose，**仍故意不提供 prompt id**，从而验证
   `[NEWCOMER_MODULE_BINDING_MISSING]` 和 working revision 保留。
4. Brief 测试把第二个 admin 改名为 acceptance/admin viewer；brief、units、paths、journey 均应断言 200，
   并至少断言返回 journey/record 绑定该 admin 自己的 user id，防止把 admin-entry 误解成跨用户越权。

聚焦命令：

```bash
.venv/bin/pytest -q --no-cov --tb=short \
  tests/unit/test_newcomer_training_path_audio_lineage.py \
  tests/unit/test_newcomer_training_path_record_lineage.py \
  tests/unit/test_audio_evaluation_scenarios.py \
  tests/unit/test_newcomer_training_path_permissions.py
```

### 簇 B：Projection / topic stage（可并行）

`test_training_records_filter_by_module_stage_and_levels` 的两处宽松
`{"in_progress", "passed"}` 改为精确 `"not_started"`。保留 record 的
`module_key="business_skills"`、`status="scored"`、filter round-trip 断言；增加注释说明
learning-topic record 不推进 required path。不要把 `attempt.passed=True` 映射成 journey passed。

聚焦命令：

```bash
.venv/bin/pytest -q --no-cov --tb=short \
  tests/unit/test_sales_trainer_phase2_projection.py::test_training_records_filter_by_module_stage_and_levels \
  tests/unit/test_newcomer_learning_topic_config_service.py::test_learning_topic_is_projected_separately_and_not_path_blocking \
  tests/unit/test_sales_trainer_training_journey_service.py::test_should_ignore_legacy_business_skills_regrade_in_required_journey_history \
  tests/unit/test_sales_trainer_training_journey_service.py::test_training_record_detail_audit_logs_include_journey_level_context
```

### 簇 C：Realtime entry permission（可并行）

把测试语义改为“跟随 learning-path entry policy”：user/learner/admin=True，training_manager=False；建议补
inactive admin=False，或者复用已有 permission suite，不改 production permission。

```bash
.venv/bin/pytest -q --no-cov --tb=short \
  tests/unit/test_sales_trainer_realtime_roleplay_start.py \
  tests/unit/test_newcomer_training_path_permissions.py
```

### 簇 D：Legacy Sales Trainer service fixtures（簇内有依赖）

先解决 #9-#12，再重写 #13：

1. #9-#12 在 `QuizService.submit_attempt` 前提供 active revision，unit 必须是 active
   `business_skills/article_exam` 的 target；使用 canonical path resource/logical id 和 module key/type。
   这些测试的目标是 choice/empty/short-answer/provider-failure，所以不要 mock 掉 QuizService 自身，
   也不要改变 production gate。若用 test-local helper，应明确它只提供最小 active-path authorization fixture。
2. #13 不可把 `elevator_pitch` 改成另一个伪 article module。两种正确方案中优先前者：
   - 把 unlock 算法测试移到/改为 `build_path_payload` 的正确 seam，用两个 canonical audio path items
     （PPT 单项 + elevator duration option）和 `UnitProgress` 做 before/after；或
   - 做完整 service 集成 fixture：published PPT/elevator audio units、prompts/materials、active path，
     完成第一项音频后验证第二项解锁。
   business skills 的多小单元解锁应由 active `newcomer_learning_topics_v1`、
   `learning_units[].unlock_after_unit_keys` 和 `BusinessEtiquetteQuizService` 覆盖，不能再伪装成 required path levels。

聚焦命令：

```bash
.venv/bin/pytest -q --no-cov --tb=short \
  tests/unit/test_sales_trainer_services.py::test_should_publish_quiz_unit_and_score_choice_answer \
  tests/unit/test_sales_trainer_services.py::test_should_reject_incomplete_quiz_attempt_before_creating_snapshot \
  tests/unit/test_sales_trainer_services.py::test_should_score_short_answer_with_ai_and_store_feedback_snapshot \
  tests/unit/test_sales_trainer_services.py::test_should_submit_short_answer_attempt_when_ai_scoring_provider_fails \
  tests/unit/test_sales_trainer_services.py::test_should_project_sales_trainer_path_with_unlock_progress \
  tests/unit/test_business_etiquette_quiz_service.py
```

## 不可采用的伪修复

- 不得删除/放松 `_validate_audio_unit_scenario`，也不得让 `general_audio_scoring` 自动冒充 PPT 或 elevator scenario。
- 不得为了 missing-prompt 旧断言调换生产校验顺序；正确做法是先让 fixture 满足 scenario，再验证 prompt 缺失。
- 不得恢复 `new_seller_modules_v1` 写入、`ppt_explain`、`pyramid_speech`、错误 module type 或新增只读 alias。
- 不得绕过 active revision、locked unit、learner level 或对象级 unit access；不得让 QuizService 无路径提交。
- 不得把 admin 从 learner entry 移除；该能力已有显式生产注释、提交语义和独立绿色测试。也不得因此让
  training manager/content admin 获得 learner entry。
- 不得让 business-etiquette quiz pass 推进 required-path stage；topic 必须保持 `required=false`、
  `blocks_next=false`。
- 不得把 `elevator_pitch` 的 canonical type 从 `audio_scoring_group` 改回 `article_exam`，或为了旧测试新增第二个
  article-exam alias。
- 不得使用 skip/xfail、删除失败断言、扩大允许错误码或吞异常制造绿色。

## 实施后验证顺序

1. 先按簇运行上述精确命令；每簇 Red -> Green。
2. 运行五个原始文件：预期 `65 passed`。
3. 运行相关领域集：audio scenarios、permissions、learning-topic config、training journey、business-etiquette quiz。
4. 最后再进入 Gate 0B 全量 `tests/unit tests/contract -q --no-cov`；本研究不支持任何生产代码改动。
