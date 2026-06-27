# PRD: 修复 release-verification bandit/safety CI 缺失

## 背景

当前 working tree 有一批发布门禁加固改动(2074 行),其中 `verification_runner.py` 把 bandit/safety 扫描从"工具未装则跳过(passed=True)"改成"工具未装则硬失败(passed=False, high_severity=1)"。改动意图正确——让工具缺失不再静默跳过。但 CI(`release-truth-gate.yml:77`)只 `pip install -r requirements.txt`,其中不含 bandit/safety,本地环境也未装。

结果:只要触发 release verification 端点,bandit/safety 两个 check 必然 `FileNotFoundError → passed=False` → 整个 release gate NO_GO。这是当前**唯一确定在咬人**的阻断点。

## 决策(已与用户 brainstorm 锁定)

采用 **甲 + optional-dependencies extras + 加契约测试** 方案:

1. **甲(装工具)**:不改回软失败。bandit/safety 必须真正可用,兑现硬门禁意图。
2. **optional-dependencies extras**:在 `backend/pyproject.toml` 的 `[project.optional-dependencies]` 新增 `release-gate`(或 `dev`)extras,放 `bandit` 和 `safety`;CI 安装 `.[release-gate]`。不进生产 `requirements.txt`,不进 Docker 镜像。
3. **加契约测试**:新增测试断言"当 bandit/safety 可用时,发现 HIGH 漏洞 → passed=False / NO_GO",守住硬门禁不被回退成软失败。

## 范围

### 必改
- `backend/pyproject.toml`:新增 `[project.optional-dependencies]` 的 `release-gate` extras,含 `bandit`、`safety`。
- `.github/workflows/release-truth-gate.yml`(或等价 CI 入口):安装步骤从 `pip install -r backend/requirements.txt` 扩展为同时装 `.[release-gate]`(或单独 `pip install bandit safety`)。
- `backend/tests/unit/test_verification_runner.py`(或 contract 测试):新增"工具可用 + HIGH 漏洞 → NO_GO"契约测试。

### 不改(明确边界)
- **不改** `verification_runner.py` 的硬失败逻辑——它是对的,只是工具没装。
- **不改** 生产 `backend/requirements.txt`——开发/CI 工具不进生产镜像。
- **不动** working tree 其他 2074 行改动——它们是连贯的发布门禁加固,本任务只补 P0 缺口。

## 验收标准

- [ ] `pip install -e ".[release-gate]"` 后,本地 `bandit` 和 `safety` 命令可用。
- [ ] CI 安装步骤包含 release-gate extras,bandit/safety 在 CI 环境可用。
- [ ] 新增契约测试通过:工具可用 + HIGH 漏洞样本 → `passed=False` 且 release gate NO_GO。
- [ ] `FileNotFoundError` 路径仍保持硬失败(不回退软失败),且有测试覆盖(已有 `test_verification_runner.py:388-432` 可复用)。
- [ ] 本地 `npm run release-check` 等价检查路径不再因 bandit/safety 缺失而误 NO_GO(因为工具已装)。

## 风险与回写

- **safety 联网依赖**:safety 默认查在线漏洞库,离线 CI 可能卡。若 CI 无外网,可用 `pip-audit` 替代 safety(离线友好)。brainstorm 不锁定具体工具,只锁定"必须有可用的依赖漏洞扫描且 HIGH → NO_GO"。实现时若选 pip-audit,需同步改 `verification_runner._run_safety_scan` 的调用——这属于**实现期可能触发的技术路径变化**,届时按 AGENTS.md 强制回写本 PRD。
- **契约边界**:本地开发若不装 extras,跑 release-check 仍会 NO_GO——这是预期的(本地可选跳过安全扫描,但 CI 必须装)。若需"本地可跳过、CI 必须硬",后续可演进为"条件硬失败"(brainstorm 的丙方案),当前不实现。

## 实现期回写(2026-06-27):subprocess 找不到 venv 内的 bandit/safety

**触发**:实现"甲"方案时发现,仅装工具不够。`verification_runner._run_bandit_scan` / `_run_safety_scan` 用 `subprocess.run(["bandit", ...], cwd=self.backend_root)`,依赖 **PATH** 能解析 `bandit`。但:
- 本地:`backend/venv/bin` 不在 `python -c` 继承的 PATH 中(实测 `venv/bin in PATH: False`)。
- CI:`backend/venv/bin/pip install bandit safety` 装到 `backend/venv/bin/`,但 CI `run:` step 的 shell PATH 同样不含 `backend/venv/bin`。

结果:工具装了仍 `FileNotFoundError → tool_missing → passed=False`。**"甲"方案单独不足以达成验收**。

**修正(扩范围,仍属本任务)**:`verification_runner` 解析 bandit/safety 可执行文件时,优先用 `sys.executable` 同目录(`Path(sys.executable).parent / "bandit"`),回退到 `shutil.which("bandit")`。这样 venv 内安装的工具无论 PATH 如何都能被 subprocess 找到。safety 同构。

这把任务从"纯配置(加 extras + CI + 测试)"扩展为"配置 + 一处代码修复(PATH 解析)"。决策点未变(仍是甲+extras+契约测试),只是甲需要这处代码支撑才能真生效。

## 实现期回写(2026-06-27,b):bandit/safety 输出解析逻辑缺陷

**触发**:PATH 解析修好后,bandit 真正执行了,但 `_run_bandit_scan` 仍返回 `passed=False`。深查发现两个独立缺陷:

1. **bandit stdout 污染**:不带 `-q` 时 stdout 开头有进度条 `Working... ━━━`,导致 `json.loads(result.stdout)` 在首字符就失败 → 走 else 分支 → "Bandit scan failed to complete"。修法:调用加 `-q`,且 JSON 解析用容错(跳过非 JSON 前缀)。
2. **bandit returncode 语义误判**:runner 用 `if returncode == 0` 判断成功,但 bandit 默认"发现任何 issue(含 LOW)就 returncode≠0"。即使 HIGH=0 也会被判 failed。修法:不依赖 returncode 判断成功,改为"成功解析 JSON = 扫描完成",HIGH 数量决定 passed。
3. **safety 3.x 输出格式不兼容**:runner 的 `--json` 解析假设旧格式,但 safety 3.8 输出是人类可读表格或不同 JSON schema。需核对新版 safety 的 JSON 输出格式并适配。

**修正(再扩范围)**:`_run_bandit_scan` 加 `-q`、改 returncode 判断逻辑、JSON 解析容错;`_run_safety_scan` 适配 safety 3.x 输出。这是 P0 验收"工具可用→门禁真生效"的最后一块,不修则 bandit/safety 永远 passed=False,等于门禁形同虚设。

**边界**:本任务只修到"bandit/safety 能正确解析、HIGH→NO_GO、无 HIGH→passed"。不修 bandit 报的 8 个 MEDIUM / 75 个 LOW(非阻断,后续单独处理)。

## 实现期回写(2026-06-27,c):safety 废弃,改用 pip-audit

**触发**:探测 safety 3.8 时发现 `safety check --json` 已 **DEPRECATED**(2024-06 后不支持,returncode=64),`safety scan --json` 新命令**需要登录注册**(免费但 CI 要配 token,违反 KISS)。runner 的 safety 调用根本无法在 CI 无登录态下工作。

**决策**:用 **pip-audit**(PyPA 官方维护)替代 safety 做依赖漏洞扫描。理由:
- 无需登录,CI 直接可用
- JSON 输出稳定:`{"dependencies":[{"name","version","vulns":[{"id","fix_versions","description"}]}]}`
- returncode 语义清晰:0=无漏洞,1=有漏洞
- prd 风险节早已预案此替代("可用 pip-audit 替代 safety")

**改动**:
- `pyproject.toml` extras:`safety` → `pip-audit`
- CI 工作流:装 `pip-audit` 替代 `safety`
- `_run_safety_scan`:重写为调用 `pip-audit -f json`,解析 `dependencies[].vulns`,有漏洞→passed=False。check_type 仍叫 "safety"(保留语义名,底层工具是实现细节),details 标 `scanner: pip-audit`
- 测试:`test_safety_json_vulnerabilities_fail_security_check` 适配 pip-audit JSON 格式;`test_missing_safety_scanner_fails_security_check` 保留(FileNotFoundError 契约不变,只是工具名换)

**已知**:pip-audit 当前在本地环境扫到 28 漏洞/11 包(含 aiohttp CVE-2026-34993)。这些是**真实的依赖漏洞**,会让 safety check passed=False → release NO_GO。但修复依赖漏洞超出本任务范围(边界已声明);本任务只保证"扫描器能正确运行和解析"。修依赖漏洞是 P0 之后的独立工作。

## 不属于本任务

- dual-read 审计开关默认关(P2 记债)
- WebSocket 层深查(P3)
- working tree 其余改动收尾提交(P1,依赖本任务完成)
