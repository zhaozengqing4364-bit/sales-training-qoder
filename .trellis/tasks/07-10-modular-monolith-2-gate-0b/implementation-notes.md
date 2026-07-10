# Implementation Notes

## Deviations

- `test_should_use_effective_path_config_for_unit_brief_api` 的首轮 Green 断言把
  unit id 写成了 `data.unit_id`；实际稳定合同是 `data.unit.unit_id`。聚焦测试立即暴露，
  修正测试读取层级后 A 簇全绿，生产响应未变。
- 历史 unlock 集成测试同时伪造两个 `article_exam` required-path module，已无法表达现行
  canonical module 约束。按研究建议改到 `build_path_payload` 的纯 projection seam，使用
  `ppt_explanation/audio_scoring` 与 `elevator_pitch/audio_scoring_group` 验证 before/after
  unlock；不再为 projection 算法构造失真的 DB 资产。
- 主代理复验时直接执行 `.venv/bin/pytest`，在 importlib 模式下因 console script 未把
  backend 工作目录加入 `sys.path`，3 个 `from scripts...` 测试模块 collection error。
  仓库权威门禁使用 `.venv/bin/python -m pytest -c pyproject.toml`；改用该命令后正确收集
  2614 项。Gate 1B 应把唯一 runner 入口显式化，避免 shell 环境差异形成第二套事实。

## Verification Log

- 2026-07-10：全量 baseline：`2613 collected, 2598 passed, 15 failed, 1 skipped,
  74 warnings in 365.49s`。失败清单已写入 PRD，未使用 skip/xfail。
- 2026-07-10：两个只读诊断代理完成 CodeGraph + 聚焦复现。最终分类为 11 项 fixture
  漂移、3 项断言语义漂移、1 项生产 bug；研究分别落盘到
  `research/sales-trainer-failure-classification.md` 和
  `research/platform-api-failure-classification.md`。
- 2026-07-10：Sales Trainer 聚焦基线为 `13 failed, 52 passed`；相邻 audio scenario、
  admin learner-entry、learning-topic 解耦、journey 历史和 business-etiquette quiz 权威集
  为 `12 passed`。Secret scanner 生产合同正常；ForbiddenWord 500 发生在成功 commit 后
  的 FastAPI `TypeAdapter[Any]` ORM 序列化阶段。
- 2026-07-10 / 簇 A Red -> Green：audio/path/record lineage fixtures 统一到 canonical
  `ppt_explanation -> ppt_pitch` 与 `elevator_pitch` scenario，保留 active revision、prompt、
  material 和 lineage 校验。首轮 `36 passed, 1 failed` 只暴露上述 DTO 断言层级误差；修正后
  audio lineage + record lineage + scenario + permission 为 `37 passed, 1 warning`。
- 2026-07-10 / 簇 B Green：learning-topic record 的 required-path `training_stage` 收紧为
  精确 `not_started`；projection + learning-topic + journey 相邻集为
  `4 passed, 1 warning`。
- 2026-07-10 / 簇 C Green：Realtime entry 跟随 learner-path policy，user/learner/admin
  可进入、training_manager/inactive admin 不可进入；Realtime + permission 集为
  `22 passed, 1 warning`，未修改 production permission。
- 2026-07-10 / 簇 D Green：四个 QuizService 测试通过 test-local canonical active-path
  revision 获得授权；legacy unlock 测试迁到 pure projection seam。五个目标测试与
  business-etiquette quiz 相邻集为 `10 passed, 1 warning`，未绕过 QuizService gate。
- 2026-07-10 / secret Green：测试在 `tmp_path/.sisyphus/evidence` 创建普通 runtime
  evidence 与 secret report，并把 `module.DEFAULT_PATHS` 直接交给 `iter_files`；普通 evidence
  被纳入、report 被排除，scanner 生产代码未改。
- 2026-07-10 / ForbiddenWord Red -> Green：admin 与 presentation_coach 两个 POST 都复用
  `ForbiddenWordResponse`，显式 `response_model`，事务顺序为
  `add -> flush -> refresh -> DTO validate -> commit`，SQLAlchemyError 先 rollback 再映射。
  contract 使用真实 `Presentation` 并参数化验证两个 surface 的严格 201、DTO 和持久化。
  secret + PPT contract 为 `16 passed, 1 warning`；相邻 admin permission 为
  `7 passed, 1 warning`。
- 2026-07-10：七个原始失败文件复跑为 `81 passed, 1 warning in 35.86s`，无 skip/xfail。
- 2026-07-10：runtime generator 更新 committed OpenAPI；生成与 `--check` 均成功。
  changed-file Ruff 与 architecture dependency guard 通过。
- 2026-07-10：精确 mypy 命令检查两个 production route 时仍被既有
  `src/common/ai/config_manager.py:279` 的 `float(str | None)` arg-type 拦截；错误不在本任务
  修改文件，mypy 报告 `Found 1 error in 1 file (checked 2 source files)`。
- 2026-07-10：全量 `tests/unit tests/contract -q --no-cov` 最终为
  `2614 passed, 1 skipped, 74 warnings in 373.74s`；Gate 0B 的 15 个 baseline failure 清零。
- 2026-07-10：CodeGraph post-sync 后两个 route symbol 的静态 impact 均局限于自身 route；
  `affected` 返回 10 个相关测试文件。全量 unit+contract 已覆盖其中 unit/contract 范围，
  integration admin/release-gate/presentation 权限回归为
  `41 passed, 2 warnings in 23.82s`。
- 2026-07-10 / update-spec：在 `.trellis/spec/backend/error-handling.md` 增加
  “ORM-backed write responses” 七段式可执行合同，明确
  `flush -> refresh -> DTO validate -> commit`、数据库异常 rollback、精确 contract 测试与
  OpenAPI parity，防止同类“写入成功但响应 500”复发。
- 2026-07-10 / 主代理 trellis-check：changed-file Ruff 通过；Ruff format 首轮发现 3 个
  历史测试文件未规范化，执行 scoped format 后 `9 files already formatted`；architecture
  dependency policy、OpenAPI parity、Trellis context validate 与 `git diff --check` 均通过。
  精确 mypy 仍只报告既有 `src/common/ai/config_manager.py:279` 一项，未扩大本 Gate 范围。
- 2026-07-10 / 独立 check 首轮：发现两个 P1。其一是 ForbiddenWord 新规范尚缺
  permission/no-row、数据库失败 rollback 和 runtime OpenAPI `$ref` 回归；其二是四个
  QuizService 测试通过低层 revision API 构造了正式入口无法发布的 article-exam path。
  Gate 保持 in-progress，未提交、未归档。
- 2026-07-10 / P1 Red -> Green：Quiz helper 先切换到
  `SalesTrainerPathConfigService.save_config/publish_config`，在缺少学习内容绑定时精确 Red 为
  `[NEWCOMER_MODULE_BINDING_MISSING]`；补齐 published `LearningContent`、
  `SalesTrainerExamPaper` 与两项 binding 后四个目标测试 `4 passed, 1 warning`。不再绕过
  publish validation 写 active revision。
- 2026-07-10 / ForbiddenWord 分支闭环：两个 public POST 均新增 forced
  `SQLAlchemyError` 回归，断言 500、各自稳定错误码和 0 持久行；权限集覆盖两路 non-admin
  403 且 0 行；runtime `/openapi.json` 精确断言两路 201 DTO `$ref`。与正式 Quiz fixture
  合并聚焦为 `15 passed, 1 warning`，Ruff/format 通过。
- 2026-07-10 / 独立 check 复核：两个 P1 清零，无阻塞项。保留一个非阻塞增强建议：未来
  增加“持久化完成进度 → `SalesTrainerPathService.list_paths_for_user` → 下一关解锁”的
  单体跨层回归；现有 projection、正式 path 发布、Quiz gate、audio submission 和 Journey
  visibility 测试已分别覆盖当前合同，不影响 Gate 0B 真实性。该增强转入 Gate 1B 的关键
  状态机 branch coverage 设计，不在 Gate 0B 扩大业务夹具范围。
- 2026-07-10 / 最终全量复验：使用权威 runner
  `.venv/bin/python -m pytest -c pyproject.toml tests/unit tests/contract -q --no-cov`
  收集 2617 项，结果为 `2617 passed, 1 skipped, 74 warnings in 379.50s`。新增 rollback、
  OpenAPI schema 与正式 Quiz path fixture 均进入本轮全量。
- 2026-07-10 / 最终门禁复验：10 个 changed Python files 的 Ruff 与 format check 通过；
  architecture dependency policy、OpenAPI runtime parity、Trellis context validate、
  `git diff --check` 通过；admin/presentation permission 与 release-gate integration 为
  `41 passed, 2 warnings in 23.84s`。独立 trellis-check 确认 P1 阻塞清零。
- 2026-07-10 / 逻辑提交：`63a878db` 封装 ForbiddenWord 生产修复、public API
  成功/失败/权限合同和 OpenAPI；`0c418048` 封装 Sales Trainer canonical fixture 与
  Secret hygiene 隔离。Readiness 并行文档持续排除，未进入任一 staged set。
