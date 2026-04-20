# S02: 审计相关验证基线补齐 — UAT

**Milestone:** M013  
**Written:** 2026-04-09T17:32:19.129Z

# S02: 审计相关验证基线补齐 — UAT

**Milestone:** M013  
**Slice goal:** 为后续所有 repair/discovery slices 锁定可复用的 web/backend focused 验证命令集合，避免执行时重新发明 proof 或被 stale/错误命令误导。

## Preconditions
- 仓库根目录存在最新的 `docs/plans/2026-04-08-system-audit-remediation-plan.md`、`.gsd/plans/GSD_PLAN_system-audit-repair.md`、`.gsd/milestones/M013/M013-ROADMAP.md`。
- 评审者可从仓库根目录运行 `rg`、`python3`、`zsh`。
- 允许读取 `.gsd/DECISIONS.md`、`.gsd/KNOWLEDGE.md`、`.gsd/PROJECT.md` 以确认 closeout 元信息已同步。

## Case 1 — Focused verification inventory must exist for the real audit surfaces
1. 打开 `docs/plans/2026-04-08-system-audit-remediation-plan.md`，定位到 `Focused Verification Command Inventory (repo-root runnable)`。
2. 运行 `rg -n "npm --prefix web test|backend/venv/bin/python -m pytest" docs/plans/2026-04-08-system-audit-remediation-plan.md`。
3. 预期：能看到 auth、dashboard、history、profile、practice、lifecycle、websocket、admin 八个 surface 的 focused baseline 行。
4. 抽查 `auth` / `practice` 与 `dashboard` / `profile` 两组 surface。
5. 预期：前者同时存在 web + backend focused command；后者只有 focused web command，没有伪造的 backend-only baseline。

## Case 2 — Backend pytest contract must be explicit in both execution handoff and GSD authority plan
1. 在 `docs/plans/2026-04-08-system-audit-remediation-plan.md` 中定位 `Backend pytest contract for auto-mode`。
2. 在 `.gsd/plans/GSD_PLAN_system-audit-repair.md` 中定位对应的 repo-root backend pytest / 串行约束段落。
3. 运行 `rg -n "串行|coverage|backend/venv/bin/python -m pytest -c backend/pyproject.toml" docs/plans/2026-04-08-system-audit-remediation-plan.md .gsd/plans/GSD_PLAN_system-audit-repair.md`。
4. 预期：两个文档都明确写出 repo-root runnable 形式、禁止退回 `cd backend && pytest ...`、多条 backend proof 需串行运行，以及 `.coverage` / pytest-cov 竞争原因。

## Case 3 — Every downstream slice in M014-M018 must have a reusable baseline or an explicit exception
1. 运行 `zsh -c 'setopt extended_glob; rg -n "npm --prefix web test|backend/venv/bin/python -m pytest" .gsd/milestones/M01{4,5,6,7,8}*/**/*.md docs/plans/2026-04-08-system-audit-remediation-plan.md'`。
2. 预期：M014-S01..S04、M015-S01..S03、M016-S01..S03、M017-S01..S03、M018-S01 都能在 slice/task plans 或 remediation handoff 中看到 focused baseline command。
3. 再运行一个 structured scan，逐个检查 `M014`-`M018` 的 roadmap 和 slice plans。
4. 预期：16 个 downstream slices 全部被覆盖，其中 14 个具备 focused reusable baseline，`M018/S02` 与 `M018/S03` 被识别为显式 documented exceptions，而不是缺失项。

## Case 4 — Governance/runbook slices must stay honest exceptions
1. 在 `docs/plans/2026-04-08-system-audit-remediation-plan.md` 的 downstream baseline map 中定位 `M018 / S02` 与 `M018 / S03`。
2. 打开 `.gsd/DECISIONS.md`，查找 `M013/S02/T03` 对应决策。
3. 预期：
   - `M018/S02` 使用 `npm audit --prefix web` / `backend/venv/bin/python -m pip_audit` 之类 governance proof；
   - `M018/S03` 使用 runbook file-presence / content grep proof；
   - 文档与决策都明确这些是刻意保留的 honest exceptions，而不是 feature-surface test。

## Case 5 — Closeout metadata must teach future executors how to use the baseline correctly
1. 打开 `.gsd/DECISIONS.md`。
2. 预期：存在 M013/S02 相关 verification decisions，至少覆盖：
   - 复用最小 focused suite；
   - backend pytest 必须 repo-root runnable + 串行；
   - M018/S02 与 M018/S03 是例外而不是缺口。
3. 打开 `.gsd/KNOWLEDGE.md`。
4. 预期：存在两条非显然使用约束：
   - dashboard / profile 当前是 web-led verification surfaces；
   - 这个 shell harness 对 `**` 不可靠，milestone-plan grep 需要显式目录或支持 globstar 的 shell。
5. 打开 `.gsd/PROJECT.md`。
6. 预期：Current State 与 Milestone Sequence 已反映 M013/S02 完成，且后续 slices 被指向这份 verification crosswalk。

## Edge Checks
- **Web-led surface guard:** 如果后续 agent 试图给 dashboard/profile 硬配一条并不存在的 backend-only suite，应视为错误；正确做法是从 web baseline 起步，只在真实改动跨到 server seam 时再加 backend proof。
- **Serial backend proof guard:** 如果有人把多个 repo-root backend pytest 命令并行跑，导致 `.coverage` / `coverage_schema` 竞争，应视为错误执行方式，而不是产品回归。
- **Exception honesty guard:** 如果后续规划把 M018/S02 或 M018/S03 改写成伪造的页面测试，只是为了“统一格式”，应视为违反 S02 established pattern；正确做法是保留 governance/runbook proof。
