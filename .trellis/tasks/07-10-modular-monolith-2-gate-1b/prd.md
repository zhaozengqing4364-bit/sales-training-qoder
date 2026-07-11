# 模块化单体 2.0 Gate 1B：自动测试选择与变更覆盖

## Goal

把已经恢复为绿色的 backend unit + contract 与完整 Vitest 纳入唯一发布真相门禁，建立
“稳定底座 + 保守影响选择 + 失败时扩大范围 + 变更覆盖率”的可执行合同，使新增测试无需登记、
慢测试选择可解释、关键状态机改动必须有分支证据，同时不让本地 CodeGraph 索引成为 CI 单点。

## Authority And Confirmed Scope

- 权威设计：`docs/superpowers/specs/2026-07-10-modular-monolith-2-design.md`。
- 权威决策：`docs/adr/2026-07-10-modular-monolith-2-ai-native-governance.md`。
- 路线图 Gate 1B 要求：backend unit + contract 自动发现、完整 Vitest、changed paths +
  CodeGraph affected、保留关键 E2E、changed-line 与关键状态机 branch coverage。
- Goal 已明确授权持续执行且禁止中途询问；因此本 PRD 将 Goal 中的 Gate 1B 条目视为已确认需求，
  对可推导选择采用最保守、兼容、可回滚的方案并在本文件记录。
- 风险等级：P1。修改发布门禁权威，但不改变 API、数据库 schema、权限或用户业务语义。

## Baseline Facts

- backend unit + contract 自动发现：300 files，`2617 passed, 1 skipped`；无 coverage 时
  379.50s，branch coverage 时 `2617 passed, 1 skipped`，890.06s，RSS 404036KB。
- backend branch coverage：81828 statements、22826 branches，综合 64%。
- 完整 Vitest：209 files，`1327 passed, 6 skipped`；无 coverage 354.32s；coverage 下使用
  20s 单测预算为 428.15s / wall 7:10.22 / RSS 792872KB，覆盖率 lines 69.82%、branches
  62.87%、functions 66.03%、statements 68.27%。
- `page-business-bindings.test.tsx` 在 10s 预算下可稳定复现 coverage timeout；隔离 coverage
  用时约 14.9–15.1s，20s 下通过。无 coverage 隔离约 6.1–6.6s。它是页面工作流测试，不能
  通过删除交互或断言缩短。
- 当前门禁只覆盖 43/300 个 backend unit + contract 文件和 29/209 个 Vitest 文件，并重复
  执行 smoke/newcomer unit 子集。
- full mypy 当前有 6 个真实类型错误；现有 `--follow-imports=skip` 还会制造 2 个假错误。
- 本地 CodeGraph 1.2.0 索引健康，但 CLI 与 114MB 数据库未进入干净 CI checkout。
- 当前长期分支比 `origin/main` 多 61 个提交。直接把整个历史差异作为 Gate 1B 首次增量分母，
  会把门禁引入前的遗留缺口误判为本 Gate 回归；需要一次有期限的 adoption anchor。

## Requirements

### R1. One Authority, Auto-discovered Fast Truth

- 保留 `scripts/critical-quality-gate.sh` 为唯一完整门禁入口，不新增竞争 workflow。
- 从 `backend/` 自动发现并一次运行 `tests/unit tests/contract`，生成 fresh branch-aware JSON；
  删除 unit/contract 固定清单及重复 newcomer coverage/smoke unit 运行。
- 从 `web/` 无目标参数运行完整 `npx vitest run --coverage`；不能使用根目录会强制 `src` 的
  wrapper，也不能维护 Vitest 文件清单。
- backend、Vitest 全量 phase 分别有 1200s suite watchdog；超时必须返回非零并显示分类，
  不能等待 job 被动终止。
- 对已测得 coverage instrumentation 正常耗时超过 10s 的单个页面工作流测试，使用局部 20s
  预算，不扩大全局单测 timeout。

### R2. Conservative Impact Selection

- 新增仓库内纯 Python selector 和版本化 YAML policy。
- 输入同时考虑可信 `base...head`、本地 staged、unstaged、untracked；保留 D/R 语义。
- 输出稳定排序 JSON manifest，记录 effective base、changed paths、每个测试的 reason、
  CodeGraph health/version、fallback reason 和选择模式。
- backend unit + contract 与完整 Vitest 永远不能被 selector 缩小。
- 现有 18 个关键 backend integration 与四个关键 Playwright spec 永久作为 critical baseline。
- 直接变更的 integration/backend e2e/Playwright 测试必须被选择。
- 确定性 changed-path policy 是 CI 权威；可用且健康的 CodeGraph `affected` 只能向集合加测试，
  不能移除 policy/critical 选择。
- CodeGraph 缺失、命令 exit 0 但 JSON 无效、索引未初始化或 worktree mismatch 都写入证据；
  其缺失不得缩小确定性集合。
- base/head 不可信、D/R、测试基础设施/依赖/共享 auth/DB/app factory/runner 改动、未知生产路径
  或 source 非空却慢测试集合为空时，按受影响测试族 full fallback。
- schedule 和显式 full 模式运行所有 backend integration/backend e2e/Playwright。
- 路径只通过参数数组交给 runner，拒绝未知前缀，禁止 shell 字符串执行。

### R3. Changed-line And Critical Branch Guard

- 新增仓库内纯 Python coverage guard 和版本化 YAML policy；不引入 `diff-cover`。
- backend 输入必须是 `branch_coverage=true` 的 coverage.py JSON；frontend 输入必须是 Istanbul
  `coverage-final.json`。
- 只统计 production roots 中新增/修改且报告认定为 executable 的行；删除、注释、空行、
  tests 和声明文件不进入分母。
- changed production file 不在 fresh report 中时失败，不能记为 100% 或 N/A。
- 普通 changed executable lines 聚合阈值为 80%。
- 关键状态机文件的 changed branch source line 必须 100% 覆盖；历史关键文件 branch 比例按
  本 Gate fresh baseline 设 no-regression floor，不要求一次性清偿全部历史缺口。
- base 不可信时 changed-line 报 N/A 仅在 selector manifest 已证明 full fallback 时允许；
  关键 branch baseline 仍执行。
- 首次迁移 anchor 使用 Gate 1B 开始前的 `d96ec87f`。仅当 CI base 尚未包含该 commit 时使用；
  owner=`architecture-governance`，retire_when=`target base contains adoption commit`，
  expires_on=`2026-08-10`。过期未退役必须失败。

### R4. State-machine Scenario Evidence

- 新增真实 DB 跨层测试：发布两级路径，持久化第一关通过记录，清理 session identity map 后用新
  session 调用 `SalesTrainerPathService.list_paths_for_user`，证明 progress loader → path
  projector → journey visibility 后下一关解锁。
- 将“最新失败是否覆盖历史通过”按当前实现记录为 latest-attempt-wins 语义；本 Gate 不静默改变
  产品规则。测试至少锁定通过记录解锁主路径，后续规则变更必须另做 ADR/产品决定。
- 修复页面权限请求分支未进入 `requesting_permission` transition 的真实缝隙。
- 用 deferred Promise 证明待决权限请求期间双击只请求一次，settle 后可重试；hook 测试补齐
  stop、blocker priority、rerender 和 transition 生命周期关键分支。

### R5. Full Static Truth And CI Wiring

- 将门禁 mypy 改为 `mypy src`，通过类型收窄和协变只读接口修复 6 个真实错误；禁止新增 ignore。
- workflow checkout 使用 `fetch-depth: 0`；按事件传稳定 base/head/mode。
- release-truth timeout 根据实测 coverage 底座从 45 分钟提高到 90 分钟；内部 suite watchdog
  仍负责更快、可分类地失败。
- 上传 selector manifest、backend coverage JSON、frontend coverage-final/summary 和现有 E2E
  evidence；artifact 缺失不能让 gate 假绿。

### R6. Documentation And Operability

- `scripts/README.md` 记录本地/CI 调用、base/head、full fallback、artifact 与排障方式。
- 设计文档、ADR、路线图和 Trellis spec 同步为实现事实；不修改并行 Readiness 文档。
- 所有临时例外具有 owner、reason、retire_when、expires_on。

## Acceptance Criteria

- [ ] selector 单测覆盖可信 base、PR/push、本地 dirty、direct tests、path rule、CodeGraph 加法、
      malformed/empty graph、D/R、unknown/global full fallback、稳定排序和路径拒绝。
- [ ] coverage guard 单测覆盖 backend/frontend 报告、80% 边界、缺失文件、无 executable line、
      changed critical branch、baseline regression、base N/A/full fallback 与 adoption expiry。
- [ ] `pytest --collect-only tests/unit tests/contract` 与实际 gate 都是目录自动发现，不含静态清单。
- [ ] backend full branch coverage：`2617 passed, 1 skipped` 或因本 Gate 新增测试而只增加通过数。
- [ ] 完整 Vitest coverage：209 files 或更多，全部通过、6 个既有 skip、不挂住。
- [ ] `mypy src`、ruff、architecture guard、OpenAPI parity、tsc、ESLint 全部通过。
- [ ] 持久化进度跨 session 解锁测试通过；权限 pending 双击回归测试先红后绿。
- [ ] selector manifest 和两份 coverage artifact 非空、schema 可验证、guard 通过。
- [ ] `bash scripts/critical-quality-gate.sh` 对不依赖真实凭证的全部 phase 自然 exit 0。
- [ ] CodeGraph affected/impact 复核没有遗漏必须追加的测试族。
- [ ] 无永久 skip/xfail/`|| true`/吞异常/降低断言制造绿色。

## Definition Of Done

- 实现、测试、CI、policy、文档和 Trellis 状态一致。
- 至少一个独立 Trellis check finding=0。
- 逻辑化本地提交；只暂存 Gate 1B 文件，明确排除
  `docs/superpowers/plans/2026-07-10-readiness-decision-integrity.md`。
- Trellis spec 更新、任务归档、journal 提交完成。
- 路线图 Gate 1B 标为完成，Gate 2 前置事实可复现。

## Technical Approach

采用三层测试真相：

1. **不可缩小底座**：full unit + contract、full Vitest、静态与合同门禁。
2. **可解释影响层**：critical baseline ∪ direct test ∪ path policy ∪ healthy CodeGraph affected。
3. **失败扩大层**：不可信输入、全局横切或未知影响触发对应慢测试族 full fallback。

覆盖率使用 fresh runner artifact，由独立 guard 解释 Git diff；测试选择与覆盖率共用同一个
effective-base 决策和 manifest，避免两个工具对“本次变更”给出不同答案。

## Decision (ADR-lite)

**Context**：CodeGraph 本地有效但 CI 不具备索引；固定清单会衰减；全量慢测试每 PR 成本过高；
历史分支在门禁引入前已有大量低覆盖变更。

**Options**：

1. 全测试每次运行：最安全但超时与资源成本不可控。
2. CodeGraph 单独决定：快但 CI 不可复现且空结果可能假绿。
3. 稳定底座 + policy 权威 + CodeGraph 只加不减 + fail-closed fallback（选择）。

**Decision**：采用选项 3；使用一次有期限 adoption anchor 对首次迁移做增量切线，之后始终使用
已包含 Gate 1B 的 PR base。

**Consequences**：普通 PR 获得可解释的风险测试集合；横切和未知改动仍可能运行全套；首次门禁
耗时会增加，因此 CI 上限提高到 90 分钟但每个核心 suite 仍有 20 分钟 watchdog。

## Out Of Scope

- 不接入真实收费 Provider，不 push、不创建 PR、不部署。
- 不在 Gate 1B 重写产品的“latest attempt wins”完成规则。
- 不一次性把所有历史文件覆盖率提升到统一 80% 全文件阈值。
- 不拆分微服务、不改变数据库表/迁移/API/权限。
- 不让 selector 缩小 unit + contract 或 Vitest。

## Research References

- [`research/impact-selection-and-state-machine-coverage.md`](research/impact-selection-and-state-machine-coverage.md)
  — fail-closed 选择、CodeGraph 限制和关键状态机缺口。
- [`research/runner-and-coverage-baseline.md`](research/runner-and-coverage-baseline.md)
  — runner 清单差距、full mypy、coverage/CI 时间预算基线。

## Implementation Slices

1. Red tests：selector/coverage guard、持久化路径解锁、权限 pending 双击、full mypy 失败证据。
2. 实现 policy + selector + coverage guard，并单测纯逻辑和 Git/报告边界。
3. 修复类型收窄与录音 transition；补关键状态机 branch tests。
4. 重构唯一门禁为自动发现，接线 workflow/artifacts/watchdog。
5. focused → full suites → critical gate；CodeGraph affected；文档/spec/ADR/路线图闭环。
