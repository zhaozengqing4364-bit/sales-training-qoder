# Gate 1B Runner 与覆盖率基线

## 总体结论

当前仓库已经有唯一主门禁：`.github/workflows/release-truth-gate.yml` 的 `release-truth`
job 只调用一次 `scripts/critical-quality-gate.sh`。问题不是缺少入口，而是入口内部仍使用手工
文件清单：Gate 0B/0C 已证明绿色的 backend unit+contract 与全量 Vitest，并没有进入该入口。

Gate 1B 最小兼容方案应当扩展现有脚本，而不是新增 workflow/第二套 gate：

1. 用目录/runner 自动发现取代 unit、contract、Vitest 固定清单；
2. 保留现有四条关键 Playwright E2E；integration/额外 E2E 再按 changed paths 选择；
3. CodeGraph 只作为本地 impact evidence，CI 不能依赖未安装、未提交的外部索引；
4. 同一次全量运行产出 branch-aware coverage，再由仓库内 checker 计算 changed executable lines；
5. 先清零现有 full mypy 的 6 个错误和当前 targeted invocation 的 2 个配置诱发错误；
6. 每个全量 phase 加明确 watchdog，并继续由 45 分钟 job timeout 作为最终上限。

## 1. 自动发现与主门禁的真实差距

### Backend

从 `backend/` 执行：

```bash
.venv/bin/python -m pytest --collect-only -q tests/unit tests/contract --no-cov
```

当前收集 `2617 items / 1 skipped`；文件层面为 300 个：273 unit、27 contract。Gate 0B 的
最终运行证据为 `2617 passed, 1 skipped, 74 warnings in 379.50s`。

`critical-quality-gate.sh` 当前清单情况：

| 集合 | 唯一文件 | 收集测试 | 说明 |
| --- | ---: | ---: | --- |
| `BACKEND_GATE_TARGETS` | 57 | 738 | 混合 unit/contract/integration，还有两个单 node id |
| `BACKEND_SMOKE_REGRESSION_TARGETS` | 4 | 58 | 4 个 unit 文件，和未来全量 unit 重复 |
| `BACKEND_NEWCOMER_COVERAGE_TARGETS` | 4 | 52 | 4 个文件都已包含在主清单，当前会重复运行 |
| 三者文件并集 | 61 | — | 40 unit、3 contract、18 integration |

因此主门禁只直接包含 43/300 个 unit+contract 文件，遗漏 257 个：

- unit：40/273 进入，233 未进入；
- contract：3/27 进入，24 未进入；
- integration：18/93 进入，75 未进入；
- backend performance 6、backend e2e 2、evaluation 2 均未进入。

### Frontend

从 `web/` 执行 `npx vitest list --filesOnly`，当前自动发现 209 个文件。Gate 0C 最终事实为
209 files、1327 passed、6 个既有 skipped，5:54.32 自然 exit 0。

`VITEST_GATE_TARGETS` 只有 29 个文件，遗漏 180 个。遗漏包含 `next.config.test.ts`、认证恢复、
history/profile/team/learning-path、customer FAQ、admin governance、hooks、API domain 等正常回归。

根目录 `npm test` 也不是完整权威：`scripts/run-vitest-root.mjs` 在无参数时强制添加 `src`，
只能发现 208 个文件，漏掉根级 `next.config.test.ts`。Gate 1B 应从 `web/` 运行无文件参数的
`npx vitest run` / `npm test`，不能复用这个收窄 wrapper 作为全量事实。

### Integration / E2E

- backend integration：93 files，当前固定清单覆盖 18；没有 changed-path 选择器；
- Playwright：7 specs，主门禁固定运行 smoke、newcomer closed-loop、presentation Phase 4、
  sales Phase 4 共 4 个；admin audit、learner audit、通用 audit 3 个未进入；
- schedule 触发时 `release-truth` 仍执行同一固定子集，没有切换到设计要求的“全量
  integration/E2E 定时层”。另外两个 scheduled jobs 只处理真实 Provider。

## 2. 唯一主门禁、CI 基线与 timeout

已满足的结构：

- `release-truth-gate.yml:117-119` 只调用 `bash scripts/critical-quality-gate.sh`；
- 脚本 `set -euo pipefail`，未用 `|| true` 吞掉测试失败；
- architecture guard、OpenAPI parity、Ruff、TS、ESLint 和四个关键 E2E 都在同一入口。

当前 timeout：

- GitHub `release-truth` job：45 分钟；该上限包含依赖/浏览器安装和全部 gate phases；
- Vitest：单测 `testTimeout=10s`，未配置全量 run watchdog；
- pytest：未安装 `pytest-timeout`，也没有 per-test 或 suite timeout；
- Playwright：默认 test 90s、expect 15s、action 15s、navigation 30s；admin/learner audit
  可以覆盖为 480s；
- shell 脚本没有用 `timeout` 包裹 pytest/Vitest phases，挂住时只能等 45 分钟 job 被终止。

已知无 coverage 的两个完整快速层耗时：

```text
backend unit+contract  379.50s
frontend full Vitest   354.32s
combined               733.82s = 12:13.82
```

两者占 45 分钟约 27.2%，名义上剩约 32:46 给安装、静态检查、coverage 处理和现有 E2E；
但当前没有一次“全量 coverage + 现有 E2E”的完整 wall-clock 证据，因此不能直接宣称 45 分钟
必然足够。接线时必须以“替换重复运行”控制预算：

- 用全量 Vitest coverage 一次替换 29-file coverage，不要先跑全量再跑固定 coverage；
- 用全量 unit+contract 一次替换清单内 43 个 unit/contract、4 个 smoke unit 和 4 个重复
  coverage targets；
- 18 个既有 integration 留在关键/影响层，不重复其中已由 full unit+contract 覆盖的文件。

建议给 backend full 与 Vitest full 各加可配置 900 秒 watchdog（例如 GNU
`timeout -k 30s 900s`，或仓库内 Python subprocess wrapper），超时要显式返回 124/分类信息；
45 分钟仍是最后保护。覆盖率开启后的真实耗时必须在合入前重新测量，不能只扩大 timeout。

## 3. Coverage 现状

### Backend

权威配置是 `backend/pyproject.toml`：默认 `--cov=src`、line fail-under 48，当前没有
`--cov-branch`。根目录另有一份不同的 pytest 配置（`--cov=backend/src` 且无 fail-under），
所以 gate 必须继续 `cd backend && -c pyproject.toml`，不能从根目录裸跑 pytest。

主门禁实际绕开了全局 coverage：

- backend 主清单和 smoke 都使用 `--no-cov`；
- 只有 4 个 newcomer tests 对 `sales_trainer`、`common.business_rules` 做 45% 聚合阈值；
- 没有 backend JSON/XML coverage artifact，也没有 branch coverage；
- workflow 上传内容只有 gate 文本和 Playwright 报告，不含 backend/web coverage 原始文件。

仓库已跟踪的 `backend/coverage.json` 不能作为当前基线：文件内容是 coverage.py 7.13.3、
`branch_coverage=false`、146 files、48.659% line；当前 mypy 自动发现 625 个 source files，
该报告既陈旧又没有 branch arcs。

本轮针对“持久化学习进度 → 路径下一步/考试解锁”的小范围 branch probe（17 个相关
unit/integration/contract tests）得到以下下界；它不是 full-suite 最终基线：

| 关键模块 | statements covered/total | branches covered/total | coverage.py 综合值 |
| --- | ---: | ---: | ---: |
| `curriculum_practice/services/learning_path.py` | 432/553 | 167/266 | 73.14% |
| `curriculum_practice/services/learning_progress_service.py` | 66/112 | 10/30 | 53.52% |
| 合计 | 498/665 | 177/296 | 70.24% |

这个结果说明不能凭空设置 80% 全文件 branch floor；应以 full branch baseline 为准，并优先
约束“本次新增/修改的分支必须被覆盖”。相关行为测试至少包括：

- `tests/unit/test_learning_path_engine.py`；
- `tests/integration/test_learning_path_flow.py`；
- `tests/contract/test_learner_study_api_contract.py`；
- `tests/contract/test_learning_path_api_contract.py`。

这些文件目前都不在固定 backend gate 清单；接入全量 unit+contract 后仍需由影响/关键层
保证 `test_learning_path_flow.py` 的持久化跨层路径。

### Frontend

`web/vitest.config.ts` 当前 thresholds 为 lines/functions/statements 30%、branches 25%，并输出
text/json/json-summary/html。问题是没有 `coverage.include`，所以未被 29 个目标文件 import 的
生产文件不会进入分母；`assert_non_empty_vitest_coverage_summary` 只检查总计非零，不能证明
全量源码或 changed lines 被覆盖。

Gate 1B 运行全量 coverage 时应显式 include `src/**/*.{ts,tsx}`，再排除测试文件、声明文件和
明确生成物；否则新增但未被任何测试 import 的生产文件可能完全消失在报告中。启用 include 后
现有 30/25 阈值是否通过必须先实测，不能通过排除业务目录维持旧百分比。

## 4. 当前 mypy 事实

现有脚本不是 full mypy，而是 11 个 source targets 加 `--follow-imports=skip`。精确复现当前
gate invocation：

```text
training_journey_service.py:2794 no-any-return
training_journey_service.py:2795 no-any-return
Found 2 errors in 1 file (checked 11 source files)
```

根因是 `follow-imports=skip` 把已正确标注为 `list[str]` 的 `unique_non_empty()` 和
`module_capability_keys()` 当成 `Any`，继而制造 return Any；同时 `warn_unused_configs` 报出
多组 override 未使用。改成 `--follow-imports=silent` 时 11 targets 可以通过，但这只能修正
配置诱发的假红，不能替代设计要求的 full mypy。

真正执行 `.venv/bin/python -m mypy --config-file pyproject.toml src` 会发现 625 个 source files，
当前有 6 个错误：

1. `common/ai/config_manager.py:279`：`float(str | None)`；
2. `article_exam_prerequisite_service.py:62`：`list[LearningChapterSummary]` 传给不变的
   `list[object]`；
3. `ai_coach_session_service.py:535-536`：`Any | None` 赋给 `str` / `int`；
4. `ai_coach_chat_session_creator.py:82-83`：同类 `Any | None` 赋值。

因此 Gate 1B 在把 mypy 改为 `mypy src` 前必须先以类型收窄/协变接口修复这 6 个真实错误；
不要通过扩大 ignore、关闭 `disallow_untyped_defs` 或长期保留手工 target 清单制造绿色。

## 5. Changed paths、CodeGraph 与 CI 可行性

本地 CodeGraph 1.2.0 和 110MB `.codegraph/codegraph.db` 可运行 `codegraph affected`；但仓库只
跟踪 `.codegraph/.gitignore`，CLI 也不在 npm/pip/CI 安装步骤中。干净 GitHub checkout 既没有
索引也没有命令。按 ADR“CI 不依赖外部索引状态”的约束，CodeGraph 不能成为 CI 唯一选择器。

建议双轨：

- 本地/开发 evidence：存在 CLI + DB 时运行 `codegraph affected --json <changed files>`，保存
  affected 列表用于复核和额外测试；
- CI 权威：仓库内 changed-path manifest/selector 保守选择 integration/E2E；CodeGraph 缺失
  不得减少 CI 应跑集合；
- 无法分类的 backend/src、router、auth、DB model/migration、shared config、runner/selector
  改动必须回退为全量 integration/E2E，而不是空集合；
- 现有四个关键 Playwright specs 无条件保留，impact 选择只做加法。

CI 当前 `actions/checkout@v4` 未配置 `fetch-depth`，默认浅克隆不保证 base commit 可用。
Gate 1B 必须先设置 `fetch-depth: 0`（或显式 fetch base），并传入稳定 base/head：PR 使用
`pull_request.base.sha`，push 使用 `event.before`；全零 before、schedule、workflow_dispatch
没有有效 base 时，changed coverage 标记为 N/A 并回退保守全量，禁止伪报 100%。

Vitest 4 已提供 `--changed <base>` 和 `coverage.changed`，可作为前端 impact 加速信号；它仍不
替代无参数全量 Vitest。pytest 没有同等内建选择，backend integration 需要仓库内 path manifest
和可选 CodeGraph affected 合并去重。

## 6. Changed-line 与关键 branch coverage 的最小机制

当前没有 `diff-cover` 依赖。无需立即引入第三方：coverage.py 7.15 与 Vitest/Istanbul JSON
已经包含足够事实，可新增一个仓库内 checker 并由唯一主脚本调用。

### 输入

- `git diff --unified=0 BASE...HEAD -- backend/src web/src` 得到新增/修改行；删除行不进入分母；
- backend：用 `pytest --cov=src --cov-branch` 生成 fresh JSON，强制
  `meta.branch_coverage=true`；
- frontend：全量 Vitest coverage 的 `coverage-final.json`；`coverage-summary.json` 只有聚合值，
  不能计算 changed lines；
- 两份报告和 selector manifest 都上传 CI artifact，不能只保留终端文本。

### 判定

- 只统计 coverage 报告认定为 executable 的 changed lines；注释/空行不进入分母；
- changed production file 没出现在 coverage 报告中必须失败，不能当作“无可执行行”；
- 普通生产改动建议先以 changed-line 80% 为初始门槛，但应在本 Gate 的 fresh full baseline
  dry-run 后锁定；
- 对 `learning_progress_service.py`、`learning_path.py` 等关键状态机，不用低全局百分比替代：
  changed branch source line 若仍存在 missing arc 即失败；无关键模块变更时报告 N/A；
- 旧代码全文件 branch 比例先记录 baseline/no-regression；新增/修改分支要求覆盖，而不是要求
  Gate 1B 一次性把历史 33%/63% branch 提高到任意拍脑袋目标；
- BASE 不可用时不执行 changed percentage，但全量测试和全量报告仍必须成功。

## 7. 推荐的最小接线顺序

仍然只有 `scripts/critical-quality-gate.sh` 一个权威入口：

1. 修复 full mypy 的 6 个错误；删除 `BACKEND_NEWCOMER_MYPY_TARGETS`，改为 `mypy src`；
2. workflow checkout 提供完整 base history，并向脚本传 base/head/事件模式；
3. `BACKEND_GATE_TARGETS` 拆出 18 个 integration；unit+contract 改为目录自动发现，一次运行；
4. 删除已被 full unit 覆盖的 4 个 smoke unit 和重复 newcomer coverage run；
5. `VITEST_GATE_TARGETS` 改为无文件参数的 full Vitest coverage，一次运行；
6. 生成 backend branch JSON、frontend Istanbul JSON，运行 changed coverage checker；
7. changed-path selector 选择额外 integration/E2E；未知影响回退全量；
8. 无条件保留现有四个关键 Playwright specs；schedule 模式扩展到全部 integration/backend E2E/
   7 个 Playwright specs；
9. 每个 full phase 记录收集数、通过/跳过数、coverage、wall time、RSS、退出码和 timeout 分类；
10. 上传 coverage JSON、selection manifest、JUnit/JSON summary 与现有 Playwright evidence。

验收时至少执行并留证：

```bash
cd backend
.venv/bin/python -m mypy --config-file pyproject.toml src
.venv/bin/python -m pytest -c pyproject.toml tests/unit tests/contract --cov=src --cov-branch

cd ../web
npx tsc --noEmit
npx vitest run --coverage

cd ..
bash scripts/critical-quality-gate.sh
```

最后一条必须在 45 分钟 job 预算模型下自然 exit 0；任何 coverage threshold 调整都需要 fresh
报告证据，禁止复用当前 tracked `backend/coverage.json` 或通过永久 exclude/skip 降低分母。

## 8. 风险与边界

- 风险等级：P1。改动的是发布门禁权威，错误选择会产生假绿或阻塞所有 PR；
- 不修改生产业务行为、API、数据库和用户路径；
- 不把 integration/E2E 全部塞入每个 PR 的快速层；changed selector 只能选择附加风险层；
- 不让 CodeGraph 索引成为 CI 单点；
- 不硬编码当前 209/300 个文件数作为永久断言，数量仅是日期化审计证据；
- 用户并行 Readiness 文档不属于本任务，保持未触碰、未暂存。
