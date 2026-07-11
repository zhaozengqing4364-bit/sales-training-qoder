# Gate 1B Implementation Notes

## Assumptions

- Goal 已预先确认 Gate 1B 范围并要求不中途询问，因此 PRD 的推荐方案直接作为执行决策。
- `d96ec87f` 是 Gate 1B 开始前最后一个已闭环提交，作为首次 changed-line adoption anchor。
- 当前路径完成语义按 loader 的 latest-attempt-wins 保持不变；本 Gate 只证明持久化通过记录能解锁。

## Deviations

- 唯一门禁首次执行在全量 backend、mypy、lint 和 Vitest 均通过后，被 smoke seed 中已存在的
  金字塔演讲重复基线记录阻断。按保守策略暂停长门禁，先用真实数据库与完整新人 E2E 构造快速
  反馈环，修复种子幂等性和权限 fail-closed 漂移后再从头重跑唯一门禁。

## Evidence Ledger

- backend full unit + contract branch coverage：2617 passed / 1 skipped / 890.06s。
- frontend full coverage（20s 局部诊断参数）：209 files / 1327 passed / 6 skipped / 428.15s。
- frontend coverage：lines 69.82 / branches 62.87 / functions 66.03 / statements 68.27。
- 10s timeout 复现：`page-business-bindings.test.tsx` isolated coverage 14.86s；20s 下测试通过。

### Selector（Red → Green）

- Red：`backend/tests/unit/test_quality_test_selector.py` 首次运行因
  `scripts/select_quality_tests.py` 不存在而收集失败。
- Green：可信 base、PR/push/local dirty、direct tests、路径规则、CodeGraph 只加不减、
  malformed/empty、D/R、global/family fallback、排序、runner 路径拒绝与 runner-relative
  manifest 输出及非 production-root 合同 path policy 共 22 个用例通过。
- 复核修正：兼容 CodeGraph `pendingChanges` 对象结构；Playwright 递归 glob；转义
  `[sessionId]`；CI 无 CodeGraph 仅降级而不扩大；公共 API 触发 backend integration
  family fallback。

### Changed coverage guard（Red → Green）

- Red：`backend/tests/unit/test_changed_coverage_guard.py` 首次运行因
  `scripts/check_changed_coverage.py` 不存在而失败。
- Green：backend/frontend 报告、80% 边界、缺失文件、无 executable line、关键 branch、
  baseline regression、base N/A/full fallback、adoption expiry/一致性、PR/push diff 语义及
  Istanbul 多行 statement 和仓库真实 policy 一致性共 16 个用例通过；与 selector 合并运行
  结果为 `38 passed, 1 warning`。

### Full mypy（Red → Green）

- Red：`mypy src` 在 625 个源文件中发现 6 个真实错误：timeout 可空值、list 不变性及两处
  revision metadata 的 `Any | None` 收窄。
- Green：不新增 ignore，修正环境变量默认值、只读 `Sequence` 接口和显式 runtime metadata
  收窄；`mypy src` 输出 `Success: no issues found in 625 source files`，相关 backend 测试
  `108 passed, 1 warning`。

### Persisted path unlock（Red → Green）

- Red：新增真实 DB 跨 session 测试后，latest-attempt characterization fixture 首次因
  `SalesTrainerAudioScoreResult.prompt_id` 非空约束失败，证明 fixture 未绕过真实 schema。
- Green：补齐真实 published prompt 与 score provenance；两级路径发布、第一关音频评分持久化、
  新 session 重载解锁第二关，以及最新失败覆盖历史通过语义共 `2 passed, 1 warning`。

### Recording permission transition（Red → Green）

- Red：deferred permission Promise 下连续双击实际调用 `requestPermission` 2 次。
- Green：permission 分支进入 `requesting_permission`，覆盖请求与后续启动全生命周期并在 settle
  后释放；页面 pending 去重/settle 后重试与 hook 的 stop、permission-null、blocker priority、
  rerender、transition 生命周期合并结果为 `31 passed`。

### Review hardening

- 新持久化解锁测试加入 backend integration critical baseline，保证无 path 变更时也稳定执行。
- backend coverage 改为 unit+contract 建立 fresh data，selected integration/E2E 使用
  `--cov-append --cov-branch` 后才生成最终 JSON，避免集成证据不可见导致假红。
- Istanbul statement 由只认 start line 改为覆盖 start..end；多行 statement 回归先红（changed
  executable=0）后绿（2/2）。
- selection/coverage policy 的 adoption anchor 增加一致性 guard 和漂移回归，过期与漂移均
  fail closed。
- selector manifest 保留 repo path/reason；独立 CLI 只在 runner 边界输出经前缀校验的相对数组，
  避免 shell 手工裁剪或路径注入。

### Unique gate / CI wiring

- 删除固定 unit/contract/Vitest 清单与重复 newcomer coverage/mypy/smoke regression phase；
  唯一 gate 改为目录/配置自动发现、`mypy src` 与 selector 控制的慢测试。
- 四个关键 Playwright spec 继续使用各自 local provider 环境；full fallback 的额外 spec 进入
  通用 runner。
- backend 与 Vitest 各有 1200 秒 watchdog；CI checkout 使用 full history、稳定 event
  base/head/mode、90 分钟 job 上限并上传 selector 和两端 coverage artifacts。
- coverage append 机制另用两个独立 pytest 进程验证：unit selector 先写 fresh coverage data，
  persisted-path integration 再 append 并生成 4.7MB branch JSON；报告同时包含
  `config_manager.py` 与 `path_service.py`，证明两阶段证据合并生效。
- 聚焦验证：selector/coverage/path tests `40 passed, 1 warning`；frontend page/FSM/局部 20s
  工作流 `32 passed`；`tsc --noEmit`、聚焦 ESLint、聚焦 Ruff、`bash -n`、Python compile、
  workflow/policy YAML parse 均通过；`mypy src` 仍为 625 files 全绿。
- 未在本 slice 重跑约 15 分钟 backend full branch coverage、约 7 分钟 full Vitest coverage 或
  全栈 Playwright；它们保留为 Gate 1B 从 In verification 进入 Completed 的最终门禁证据。

### Independent Trellis check hardening

- 独立检查发现并修复 10 项：co-located Vitest 被误判为 production、CSS 等非 Istanbul 源文件
  假红、critical branch `0/0` 可绕过 floor、selection policy 非 list/no-op/收窄 glob 可静默缩测、
  workflow/smoke runner 改动未触发 full fallback、Playwright CodeGraph filter 把 helper 当 runner
  target、selector manifest 缺 schema/head 一致性校验、PR 使用 source head 而 coverage 来自 synthetic
  merge checkout、权限 prompt 期间 readiness 改变后仍会启动录音，以及两个 repo script 的 Ruff
  `collections.abc` 错误。
- 修复后 CodeGraph 1.2.0 实际 selector 为 `status=healthy`；本 Gate 自身因 runner/policy 变更按设计
  `full-fallback`，发现 94 个 backend integration、2 个 backend E2E、7 个 Playwright spec，且
  co-located test 不再产生 `unknown-production-path`。
- 独立聚焦证据：selector/coverage guard `46 passed, 1 warning`；persisted unlock
  `2 passed, 1 warning`；practice page/FSM `34 passed`；backend 自动发现 `2660 tests collected`，
  Vitest 自动发现 209 files；`mypy src` 625 files 全绿；target Ruff、TS、ESLint、Bash/Python/YAML
  syntax 与 `git diff --check` 全绿。
- backend full branch coverage、完整 Vitest coverage、全量 selected integration/E2E/Playwright 和
  自然退出的唯一门禁仍由主线程执行，不在独立 check 中重复长跑。

### 商务礼仪治理 fixture 闭环（7 failures → 15 passed）

- 确定性复现：四个商务礼仪 integration 文件共 `15` 个用例，初始结果为
  `7 failed, 8 passed, 1 warning`。失败集中在导入后可见性、学习单元、单元小测、部门隔离和
  自愿重练；错误分别落在旧模块端点的 `409`、`[SALES_TRAINER_UNIT_NOT_FOUND]` 和
  `[LEARNING_TOPIC_ACTIVE_REVISION_MISSING]`。
- 排序假设与探针：
  1. 首要假设是 fixture 仍只发布 active newcomer path、未发布 canonical
     `newcomer_learning_topics` revision；沿 `business_etiquette_api ->
     require_learner_learning_topic_access -> TrainingJourneyService ->
     LearningTopicProjectionService` 追踪后证实，缺 topic 会在业务服务前 fail closed。
  2. 次要假设是学习单元/小测仍从 path module 取配置；源码探针证伪，二者均从
     `active_business_etiquette_topic()` 读取 learning units，能力点则来自 active
     business-etiquette training-pack capability snapshot。
  3. 导入失败假设为生产发布状态回归；对比端点后证伪。测试仍调用 legacy
     `/modules/business_skills/article`，而治理合同已迁移到 topic-scoped article surface。
  4. 自愿重练假设为 AI session 创建回归；补齐 active topic 后 session shell、revision metadata
     和审计写入全部通过，确认原失败仅发生在 topic access gate。
- 根因分类：7 个失败均为治理迁移后的 fixture/expectation drift，不是生产逻辑回归。旧 fixture
  把 `business_skills` path module 当学习可见性真相；当前合同以 active learning-topic revision
  为唯一真相，并固定 `required=false`、`blocks_next=false`。
- 修复：仅更新四个 integration 测试文件。为对应成功/边界用例发布 canonical
  `business_etiquette` active topic revision；learning-unit 与 quiz fixture 继续使用 active
  training-pack 的 published capability snapshot；缺少 learning units 的用例在 canonical topic
  上显式发布空列表；导入用例改走 topic-scoped article endpoint，并在 active topic 绑定 draft
  后继续严格断言 `[LEARNING_CONTENT_NOT_PUBLISHED]`，未使用 skip 或放宽断言。
- 验证：
  - `.venv/bin/python -m pytest -c pyproject.toml
    tests/integration/test_business_etiquette_import_api.py
    tests/integration/test_business_etiquette_learning_units_api.py
    tests/integration/test_business_etiquette_quiz_api.py
    tests/integration/test_business_etiquette_release_api.py -q --no-cov`：
    `15 passed, 1 warning in 13.86s`。
  - `.venv/bin/ruff check` 同四个文件：`All checks passed!`。
  - `git diff --check` 同四个文件：通过。
- 范围与风险：未修改生产代码、门禁脚本、readiness 文档或 Git 状态；唯一警告为既有
  passlib `crypt` Python 3.13 deprecation，与本次 fixture 修复无关。

### Selected backend regression diagnosis

- 首轮自动选择的 integration/E2E 真实执行为 `619 collected / 579 passed / 21 skipped /
  19 failed`，证明 selector 能暴露历史 fixture 与已生效合同的漂移，没有通过缩减测试集制造绿色。
- 路径配置的 `business_skills.ai_coach` 旧必填断言与 2026-07-08 学习专题治理 ADR 冲突：
  商务礼仪 AI Coach 已由 `newcomer_learning_topics_v1` 独立治理且可选。回归改为证明兼容路径无旧
  AI Coach gate 也能发布，并明确 active path 不会隐式补入该配置。
- 材料对象级访问 fixture 把金字塔演讲单元错误标成 `ppt_pitch`，先被当前场景一致性门禁拒绝；
  fixture 改为显式 `ppt_explanation/ppt_pitch` 与 `elevator_pitch/elevator_pitch`。同一用例中的 admin
  learner-route 旧拒绝断言也已按现行“平台管理员可进入 learner path 做验收且仍受对象范围约束”
  权限合同改为只允许当前已解锁绑定版本，support、locked 与 unbound 拒绝断言保留。
- Presentation lifecycle 测试仍 patch 已移除的 common service 直接依赖；改为 patch 已注册的
  `presentation_coach` terminal contributor 依赖缝，保持 Presentation 结束直接 completed、无 Sales
  scoring 继承的合同。
- 三项聚焦 Red 为 `2 failed / 1 passed`（先暴露 response snapshot 层级和 admin 权限旧断言），
  修正后 Green 为 `3 passed, 1 warning`；目标 Ruff 同步通过。
- `_validate_required_ai_coach_module` 当前无调用者，保留为 Gate 6 删除无消费者兼容层的审计候选，
  本 Gate 不扩大为无关生产重构。
- 主线程复核唯一 gate 的进程生命周期后，在 Playwright 与 selected backend coverage 之间显式关闭
  smoke stack，避免后台服务在 9 分钟级 pytest 覆盖收集期间占用 CPU/内存或意外共享全局依赖；
  最终 trap 仍保留失败路径清理。
- 19 个失败所在的 13 个 integration 文件在三组修复合并后全文件回归为
  `74 passed, 1 warning in 40.16s`，证明修复不只让原失败 node 通过，也覆盖了同文件后续断言与
  contributor registry 隔离。
- selector 重新生成后，full-fallback 的 94 个 integration + 2 个 backend E2E 全量无覆盖快跑为
  `598 passed / 21 skipped / 70 warnings in 294.74s`；首轮 19 个失败全部消失，收集规模仍为
  619，未通过移除目标缩测。

### PracticeTemplate actor / publish fixture diagnosis

- Red：6 个 integration 文件稳定复现 `21 collected / 9 failed / 12 passed`。其中 7 项在
  `PracticeTemplateService._actor` 失败：fixture 传 `actor_id=None` 或未持久化的 `admin-1`；
  另外 2 项手写 parent `customer_roleplay` template 只有 child 引用 CaseItem，违反当前
  Roleplay Contract 对 parent 自身 published CaseItem 的发布合同。
- 修复仅更新 fixture：为每条发布链持久化真实 admin `User` 并传其 `actor_id`；为
  customer-roleplay child/parent 建立并发布真实 CaseItem，保留 `first_visit` situation pack。
  未修改 `PracticeTemplateService`、未放宽对象级权限、未新增 skip/xfail。
- actor/publish 修正继续暴露 2 个陈旧期望：publish-time `PublishedAssetRef.version` 的权威 schema
  是 string，因此 examiner/question frozen ref 精确期望改为 `"1"`；已冻结 ruleset 被改成 draft
  时首先命中 hash integrity，精确错误码更新为
  `[RUNTIME_SNAPSHOT_ASSET_HASH_MISMATCH]`，没有弱化异常断言。
- Green：同一 6 文件完整回归 `21 passed, 1 warning`（13.76s）；目标 Ruff
  `All checks passed!`。

### 唯一门禁首轮与 newcomer smoke 闭环

- 首次完整执行 `QUALITY_GATE_SELECTION_MODE=local QUALITY_GATE_HEAD_SHA=HEAD bash
  scripts/critical-quality-gate.sh` 的前置证据：backend unit+contract branch coverage
  `2663 passed / 1 skipped`（791.97s）；`mypy src` 625 files 全绿；frontend lint 0 error；
  full Vitest coverage 209 files / `1335 passed / 6 skipped`（435.03s）并自然退出。随后 smoke seed
  以 `e2e journey pyramid speech outcome mismatch` fail closed，未进入 Playwright。
- 数据库探针证实同一 seed learner、unit、source_page、filename 下遗留两条演讲提交。无排序的
  `_first` 与按 `created_at desc` 的 Journey projection 会在每次 seed 刷新时间后选择不同 ID；
  操作日志显示两条记录自 2026-07-08 起交替被重评分，排除事务缓存、路径 revision 和时长聚合
  假设，根因是 seed 自有记录缺少 deterministic canonicalization。
- Red：在第一次 seed 后注入同一业务键的未来时间重复提交，第二次 seed 稳定复现相同 Journey
  outcome ID mismatch。Green：normalize 后按 `created_at, submission_id` 选最早 canonical，删除
  仅限 seed 自有业务键的重复行，并由数据库级 cascade 清理其 transcript/score；回归保持原 ID，
  canonical count=1。聚焦单测 `1 passed`，本地真实 Postgres `--apply` 为
  `created=0 / updated=36 / verified=True`，真实重复记录由 2 条收敛到 1 条。
- 完整 newcomer E2E 随后暴露第二个真实合同差异：`training_manager` 具备
  `manage_questions=true` 但 `manage_content=false` 时，前端 route map 错把 papers inventory
  授权给 manage_questions，导致先显示“新建考卷”并请求后端受限资源，再退化为通用 403 加载失败。
  保留 E2E 的 fail-closed 断言，新增 route/page Red（2 failed），从 manage_questions roots 移除
  两个 papers 路径；manage_content 仍授权，题目管理仍可用。Green：route/page `13 passed`，
  restricted-manager Playwright `1 passed`。
- 完整 `newcomer-training-closed-loop.spec.ts` 快速门禁最终为 `10 passed / 2 skipped`（1.3m），
  覆盖 active revision、学习专题、quiz、fresh lineage、admin analytics、移动端治理筛选、对象级权限、
  回放、真实本地 sales WebSocket 与 path/topic 解耦。两个 skip 仅为需显式开启的真实收费 Provider
  门禁，不属于本 Goal 授权范围。
- 唯一门禁第二轮的 full backend (`2663 passed / 1 skipped`, 776.84s)、mypy、lint 与 full Vitest
  (`1335 passed / 6 skipped`, 431.25s) 再次通过；随后 policy-selected learner audit 暴露旧审计仍从
  Journey modules 构造 L-04/05/06，而学习专题已由 `learning_topics` 独立治理。审计未被删除或 skip：
  L-04/05/06 改为按 active topic 的 `learning_content_id`、`unit_key` 与 latest attempt 校验同页
  in-flow 阅读、小测与结果状态，desktop/mobile route 数量保持不变。
- 审计迁移后又发现两个生产风险并保持 fail-closed：旧 `/business-skills/exam` 页面把
  `active path revision` 工程术语直接显示给 learner；topic attempt ID 送入旧
  `/sales-trainer/quiz-attempts/{id}` 会 404。未扩展旧模型兼容层，而是将旧考试书签以 Next redirect
  汇入 `/sales-trainer/business-skills` 单一工作台，并让 L-06 审计 topic workbench 的内联结果。
  Redirect Red 为旧页面仍调用 `useRouter`，Green 与 canonical workbench 合并为 `20 passed`；learner
  desktop/mobile 专项审计最终 `1 passed`（1.4m），无 setup gap、内部字段、404 或水平溢出。
- 唯一门禁第三轮在 selector 启动即暴露 direct-change 边界缺口：
  `web/tests/e2e/newcomer-training-route-manifest.ts` 位于 Playwright family prefix 下，但不是
  `.spec.ts` runner target，旧逻辑仍把它传给 `runner_paths` 并 fail。新增 Red 精确复现该异常；
  Green 将 family 内非 runner 文件归类为 `test-support-change`，触发该 family 全量 fallback，且
  helper 永不进入命令参数。selector 全套 `26 passed`；真实 local preflight 为 `full-fallback`、
  Playwright 7 个 spec，并显式记录 support-file fallback reason。
- 唯一门禁第四轮通过 selector、full backend (`2664 passed / 1 skipped`, 773.99s)、mypy、lint、
  full Vitest (`1329 passed / 6 skipped`, 425.07s) 及前两组 generic Playwright，learner audit 最终
  仅被 fresh audio file 的 `ERR_BLOCKED_BY_ORB` 阻断。数据库与文件探针证明 fresh submission
  把 `storage_key` 指向 `/tmp/newcomer-*.wav`，但 seed 从未创建该文件；且 `/tmp` 不在授权的
  `SALES_TRAINER_AUDIO_STORAGE_PATH` 下。独立审计未设置 fresh run ID，因而此前偶然使用可播放基线。
- Red：设置 `NEWCOMER_E2E_FRESH_RUN_ID` 后要求 fresh submission 的文件存在、size 一致并可经
  `resolve_audio_file_access` 返回 local/audio-wav，旧实现稳定失败于 `Path.is_file()`。Green：fresh
  与 baseline 统一复用 `_ensure_seed_audio_file`，同时生成合法 WAV、hash、size 和受控 storage key；
  seed 单测全文件 `13 passed`。带 fresh run ID 的完整 learner desktop/mobile audit 为 `1 passed`
  （1.4m），证明组合门禁场景不再触发 ORB/404/越权。

### 唯一门禁第五轮与 Presentation fixture 真相闭环

- 第五轮从头通过 secret scan、selector full-fallback、Ruff、dependency guard、OpenAPI parity、
  backend mypy、backend unit+contract branch coverage（`2665 passed / 1 skipped`, 738.38s）、web
  typecheck、lint（0 error）、full Vitest（209 files / `1329 passed / 6 skipped`, 428.77s）、generic
  Playwright（`3 passed`, 3.3m）、smoke（`9 passed`）和 newcomer closed loop（`11 passed / 1 skipped`）。
  Presentation Phase 4 随后在读取两个不存在的 `.pptx` fixture 时 fail closed。
- Git tree、全仓库和历史提交证明两个 PPTX 从未提交；根 `.gitignore` 又全局忽略 `*.pptx`，历史审计
  仅记录了开发机上的 29,382/52 字节文件。这不是路径层级问题，而是 E2E 依赖未版本化的本地残留，
  CI 从设计上不可复现。
- 保留原 Presentation E2E 作为 Red seam。新增可追踪的 Base64 fixture：正常 OpenXML 为 29,309
  字节、2 页（“客户业务目标”“实施路径”）；损坏 fixture 为固定 44 字节。测试只在内存解码，上传
  filename 仍为 `.pptx`，未新增依赖、未放宽 validator、未依赖开发机二进制。
- 第一次 Green 运行中，正常 PPT 与真实 `/ws/presentation`、provider transcript、evaluation/report
  evidence 全链通过；损坏路径暴露旧期望漂移：当前 validator 已在写文件/建库记录之前返回结构化
  400，而旧测试仍期待先创建 `failed` asset。按 fail-closed 合同更新 E2E：精确断言 400、错误消息和
  `trace_id`，并比较上传前后 Presentation ID 集合完全相同，证明无伪资产、会话或成功报告证据。
- 聚焦最终结果：`presentation-phase4.spec.ts` 为 `2 passed`（4.4s）；`npx tsc --noEmit` 通过；目标
  ESLint 0 error/0 warning；CodeGraph impact 仅该 E2E 文件，索引同步且 healthy。

### 最终唯一门禁与独立复核

- 第六轮从头执行最终自然 exit 0：secret scan 556 files；selector 为 full-fallback 且 CodeGraph
  1.2.0 healthy；Ruff、architecture guard、OpenAPI parity、`mypy src` 625 files、web typecheck 和
  lint（0 error）通过。
- 全量测试证据：backend unit+contract `2665 passed / 1 skipped`（795.55s）；Vitest 209 files /
  `1329 passed / 6 skipped`（430.31s）；generic Playwright `3 passed`、smoke `9 passed`、newcomer
  `11 passed / 1 real-provider skip`、Presentation `2 passed`、Sales `1 passed`；selected backend
  integration/E2E `598 passed / 21 skipped`（522.09s）。
- changed coverage artifact 为 41/50 changed executable lines（82% ≥ 80%），关键 backend/frontend
  branch `changed_missing_source_lines=[]` 且全部不低于 adoption floor；最终日志明确输出
  `Changed coverage satisfied` 与 `Critical quality gate passed`。
- 独立 Trellis check 找到 1 项跨 runner 影响缝：仅修改
  `backend/tests/e2e/fixtures/**` 原先只会 fallback backend E2E，Presentation 恰因 critical baseline
  被选中但政策没有显式表达依赖。将该路径加入 global fallback，并新增 repo-policy Red/Green，证明
  fixture-only 变更 full-fallback 且包含 Presentation spec。主线程独立复验 selector+coverage guard
  `48 passed`、目标 Ruff、YAML、CodeGraph impact/status 全绿；最终阻塞 finding=0。
