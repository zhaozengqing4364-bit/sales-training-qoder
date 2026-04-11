# 依赖扫描与升级策略 baseline

最后更新：2026-04-12  
适用范围：`web/`、`backend/`

本基线的目标不是假装仓库已经有完整的依赖治理平台，而是把**现在真实可用的入口、缺失前置条件、升级门禁和同步规则**写清楚，让后续 agent 或维护者不用再重建一次同样的现场。

## 1. 当前权威文件（source of truth）

### Frontend

- 依赖声明：`web/package.json`
- 当前可审计锁文件：`web/package-lock.json`
- 当前真实漏洞扫描入口：`npm audit --prefix web`

### Backend

- 当前依赖治理权威：`backend/requirements.txt`
- `backend/pyproject.toml` 目前只覆盖极少量元数据/工具配置，**不是**当前依赖治理真相线
- `.github/workflows/nfr-performance-check.yml` 里的 `pip install -e .[test]` 目前也**不是**权威入口，因为 `backend/pyproject.toml` 还没有定义可复用的 `test` extra

> 结论：在 backend 包装元数据补齐之前，任何 backend 依赖新增、升级、移除，都必须以 `backend/requirements.txt` 为准。

## 2. 一键查看当前治理状态

先跑仓库内脚本：

```bash
bash scripts/dependency-governance.sh status
```

这个命令会直接告诉你：

- 现在该看哪几个权威文件；
- `npm audit` 是否可直接执行；
- backend 的 `pip_audit` 是否已经装进 venv；
- backend 的 `pip-licenses` 是否已经装进 venv；
- web license scan 是否具备 `npx` 前置条件；
- 当前为什么**不能**把 CI 的 `pip install -e .[test]` 当成治理权威入口。

## 3. 扫描节奏（cadence）

### A. 每次改动依赖的 PR / slice

至少执行：

```bash
bash scripts/dependency-governance.sh status
bash scripts/dependency-governance.sh web-audit
```

如果 PR/slice 改动了 backend 依赖，还要：

```bash
bash scripts/dependency-governance.sh backend-audit
```

如果 `backend-audit` 因为 `pip_audit` 未安装而被阻塞，**只能记录为 blocked prerequisite，不能写成已验证通过**。

### B. 每周一次人工治理检查

建议每周做一次完整人工检查：

```bash
bash scripts/dependency-governance.sh status
bash scripts/dependency-governance.sh web-audit
bash scripts/dependency-governance.sh backend-audit
bash scripts/dependency-governance.sh license-plan
```

说明：

- `license-plan` 会输出当前批准使用的 license scan 命令与缺失前置条件；
- 如果对应工具未安装，这次周检应明确写成“license proof blocked by prerequisites”，而不是跳过不记。

### C. 发布前 / 里程碑收口前

发布前至少满足：

1. 重新跑一遍 `status`；
2. 前端 `npm audit --prefix web` 结果被重新审阅；
3. backend 若改过依赖，则重新跑 `backend-audit` 或明确记录 why blocked；
4. license scan 的执行情况被明确记录为 **passed** 或 **blocked with prerequisite**；
5. 依赖升级带来的新增高风险问题不能静默带过。

## 4. 升级门禁（upgrade gate）

本仓库当前 baseline 不要求“所有 audit 输出为 0”才允许继续，因为前端 lockfile 里已经存在遗留漏洞；但是它要求**每次升级都必须诚实回答下面几个问题**：

1. 这次变更是否新增/升级/移除了依赖？
2. `npm audit --prefix web` 的结果相比变更前，是改善、持平，还是变差？
3. 如果出现新的 high / critical 风险，是否已经修复；若未修复，是否被明确记录为阻塞或例外？
4. backend 若改了依赖，是否真的跑过 `pip_audit`；如果没跑，是因为工具缺失还是环境不可用？
5. license scan 是否真的执行；如果没执行，缺的前置条件是什么？

### 合并前最低门槛

- **允许合并**：
  - 依赖变更已同步到权威文件；
  - 已运行可运行的扫描命令；
  - 所有未运行的 proof 都被明确记录为前置条件阻塞；
  - 没有把新增高风险问题伪装成“历史遗留”。

- **不允许合并**：
  - backend 依赖改了，但 `backend/requirements.txt` 没同步；
  - 依赖变更后完全不跑 `npm audit`；
  - 缺少 `pip_audit` / license tool 却仍宣称 backend/license proof 已通过；
  - 新增 high / critical 问题但没有明确处置结论。

## 5. Backend `requirements.txt` 同步规则

这是本任务最重要的治理规则之一。

### 规则

- 任何 backend 依赖新增、升级、移除，必须在**同一变更**里更新 `backend/requirements.txt`。
- 如果只改了 `backend/pyproject.toml`，但没有同步 `backend/requirements.txt`，这次变更视为**未完成**。
- 如果 workflow / CI 依赖安装方式与 `backend/requirements.txt` 不一致，优先修复文档和流程，不要把 CI 偶然能跑通误判成治理基线已经正确。
- 在 backend package extras（尤其 `test`）真正补齐前，不要把 `pip install -e .[test]` 当作升级是否完成的判断依据。

### 当前推荐操作顺序

1. 修改 `backend/requirements.txt` 中的目标依赖版本；
2. 若该改动还需要配套更新 `backend/pyproject.toml` 的最小元数据，可一并修改，但**不能只改它**；
3. 跑：

   ```bash
   bash scripts/dependency-governance.sh status
   bash scripts/dependency-governance.sh backend-audit
   ```

4. 在任务总结 / PR 描述里写清：
   - 改了哪些依赖；
   - backend audit 是否已跑；
   - 若未跑，缺什么前置条件。

## 6. License scan 的当前建议做法

仓库里目前**没有 repo-pinned 的 license scanner**，所以 baseline 先把“批准使用的命令 + 前置条件”写清楚，而不是假装已经自动化。

### Frontend license scan（建议命令）

```bash
npx --yes license-checker --start ./web --production --summary
```

前置条件：

- 本机有 `npm` / `npx`；
- 若本地没有缓存 `license-checker`，第一次执行可能需要网络访问 npm registry。

### Backend license scan（建议命令）

```bash
backend/venv/bin/python -m piplicenses --from=mixed --format=json
```

前置条件：

- backend venv 可用；
- venv 内已安装 `pip-licenses`。

### 审核规则

- 没跑成功就写 blocked，不写 green；
- 发现非宽松许可证（或 unknown）时，先审阅再合并依赖更新；
- 后续如果仓库决定 pin 某个 license tool，应更新本文件和 `scripts/dependency-governance.sh`，而不是只在某次 PR 描述里临时说明。

## 7. 当前 baseline 的诚实状态

截至这次基线落地时：

- `npm audit --prefix web` 是可直接执行的；
- backend 的 `pip_audit` / `pip-licenses` 仍然需要本地或 CI 先把对应工具装进 `backend/venv`；
- license scan 仍依赖额外 CLI 前置条件，目前先以“可执行命令 + blocker 说明”作为 baseline；
- future agents 应优先看这份文档和 `scripts/dependency-governance.sh status`，不要从零猜测哪份文件才是当前依赖治理权威。

## 8. 本次已执行 proof（2026-04-12）

### Frontend vulnerability proof

已实际执行：

```bash
npm audit --prefix web
```

结果：**通过（0 vulnerabilities）**。

本次修复路径不是只跑 `npm audit fix` 就结束，而是：

```bash
npm install --prefix web next@16.2.3 eslint-config-next@16.2.3
npm update --prefix web
npm audit --prefix web
```

原因：单独执行 `npm audit fix` 在本仓库里没有把部分已可修复的传递依赖（如 `vite` / `rollup` / `minimatch` / `flatted`）真正抬到安全版本；只有在锁文件允许的前提下再执行一次 `npm update --prefix web`，audit 才会回到绿色。

因此，后续如果 web audit 仍报告“fix available”但 `npm audit fix` 没有实际改动，不要立刻把它记成“仍有未解漏洞”，先补跑一次：

```bash
npm update --prefix web
```

### Frontend smoke proof

依赖刷新后还执行了一个最小 smoke test：

```bash
npm --prefix web test -- --run src/lib/api/client.auth.test.ts
```

结果：**通过（9/9）**。

## 9. Backend proof 与执行前置说明

### 9.1 工具前置条件

若本地 `backend/venv` 里缺工具，先安装：

```bash
backend/venv/bin/pip install pip-audit pip-licenses
```

这一步只是让 proof 可运行，不代表 proof 自动通过。

### 9.2 为什么不要把裸 `backend/venv/bin/python -m pip_audit` 当成唯一 repo proof

本次实际执行中，裸命令出现了两个问题：

1. 在未安装 `pip_audit` 时，它直接失败，说明工具前置条件必须先记录；
2. 安装后，默认 PyPI 后端会因网络/代理超时而失败；即使改用可用服务，它默认审计的是**整个 venv**，会把 `pip-audit`、`pip-licenses` 等治理工具本身也算进结果里，不能准确代表仓库声明的 `backend/requirements.txt` 风险面。

因此，repo-level backend proof 应优先使用**requirements-scoped**命令：

```bash
PIP_AUDIT_VULNERABILITY_SERVICE=osv backend/venv/bin/python -m pip_audit -r backend/requirements.txt
```

### 9.3 本次 backend vulnerability proof 结果

已实际执行：

```bash
PIP_AUDIT_VULNERABILITY_SERVICE=osv backend/venv/bin/python -m pip_audit -r backend/requirements.txt
```

结果：当前命中了一个仍需人工跟踪的已知问题：

- `ecdsa 0.19.2` — `CVE-2024-23342`

补充核查：

```bash
backend/venv/bin/pip index versions ecdsa
```

执行时显示 `0.19.2` 已是最新可用版本，没有更高的已知修复版本可直接升级。因此，这一项目前应被记录为：

- **proof 已执行**；
- **存在 open risk**；
- **不是“没跑 proof”**；
- **也不是“可以直接升一个版本就绿”**。

### 9.4 本次 backend license proof 结果

已尝试执行：

```bash
backend/venv/bin/python -m piplicenses --from=mixed --format=json
```

结果：**未通过，不是因为命令不存在，而是因为当前环境里有部分已安装分发包缺少 `Name` 元数据，`pip-licenses` 会以 `TypeError: expected string or bytes-like object, got 'NoneType'` 直接崩溃。**

因此，当前 backend license 结论应写成：

- 工具前置条件：已满足；
- 扫描命令：已尝试执行；
- 当前 blocker：扫描器被环境内异常元数据包打断；
- 状态：**blocked by scanner/runtime issue**，不是 green。

后续如果要把 backend license proof 变成稳定绿色，需要二选一：

1. 清理/隔离这些缺失 `Name` 元数据的安装包后继续使用 `pip-licenses`；
2. 为仓库 pin 一个更稳定的 backend license scanner，并同步更新本文档与 `scripts/dependency-governance.sh`。
