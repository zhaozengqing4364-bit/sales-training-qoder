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

### B. 每周一次人工治理检查

建议每周做一次完整人工检查：

```bash
bash scripts/dependency-governance.sh status
bash scripts/dependency-governance.sh web-audit
bash scripts/dependency-governance.sh backend-audit
bash scripts/dependency-governance.sh license-plan
```

说明：

- `license-plan` 会输出当前批准使用的 license scan 命令与前置条件；
- 如果某个 proof 因环境被阻塞，应明确记为 blocked，不要跳过不记。

### C. 发布前 / 里程碑收口前

发布前至少满足：

1. 重新跑一遍 `status`；
2. 前端 `npm audit --prefix web` 结果被重新审阅；
3. backend 若改过依赖，则重新跑 `backend-audit`；
4. license scan 的执行情况被明确记录为 **passed** 或 **blocked with prerequisite**；
5. 依赖升级带来的新增高风险问题不能静默带过。

## 4. 升级门禁（upgrade gate）

当前 baseline 的门槛不是“只有 0 风险才允许继续”，而是**每次依赖改动都必须留下真实证明**：

1. 这次变更是否新增/升级/移除了依赖？
2. `npm audit --prefix web` 的结果相比变更前，是改善、持平，还是变差？
3. 如果出现新的 high / critical 风险，是否已经修复；若未修复，是否被明确记录为阻塞或例外？
4. backend 若改了依赖，是否真的跑过 `pip_audit`？
5. license scan 是否真的执行？

### 合并前最低门槛

- **允许合并**：
  - 依赖变更已同步到权威文件；
  - 已运行可运行的扫描命令；
  - 没有把新增高风险问题伪装成“历史遗留”；
  - 未通过项被诚实记录为 open risk 或 blocked。

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

截至本次 slice closeout：

- `npm audit --prefix web` 已可直接执行并返回 **0 vulnerabilities**；
- backend `pip_audit` 与 `pip-licenses` 已安装到 `backend/venv`，`bash scripts/dependency-governance.sh status` 会把它们标记为 ready；
- 依赖治理权威仍然是 `web/package-lock.json` + `backend/requirements.txt`，`backend/pyproject.toml` extras / `pip install -e .[test]` 仍然只是 drift context，不是权威入口；
- backend license scan 现在可以实际执行，不再是“只有命令、没有 proof”；
- future agents 仍应先看这份文档和 `scripts/dependency-governance.sh status`，不要从零猜测哪份文件才是当前依赖治理权威。

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

当前 baseline 已满足：

```bash
backend/venv/bin/python -m pip_audit --version
backend/venv/bin/python -m piplicenses --version
```

如果后续本地环境缺工具，可补装：

```bash
backend/venv/bin/python -m pip install pip-audit pip-licenses
```

### 9.2 backend vulnerability proof

本次 closeout 同时跑了两条 proof：

```bash
PIP_AUDIT_VULNERABILITY_SERVICE=osv backend/venv/bin/python -m pip_audit -r backend/requirements.txt
backend/venv/bin/python -m pip_audit
```

结果：两条命令现在都返回 **No known vulnerabilities found**。

之所以能让 exact gate 也回绿，不是因为把风险“改口径”了，而是因为这次实际完成了下面这些治理动作：

- 在 `backend/requirements.txt` 里补齐 security floors（`aiohttp`、`cryptography`、`langchain-core`、`onnx`、`orjson`、`Pillow`、`pypdf`、`protobuf`、`pyasn1`、`Pygments`、`urllib3` 等）；
- 把 JWT 依赖从 `python-jose[cryptography]` 切到 `PyJWT[crypto]`，并同步更新代码引用，移除 `ecdsa` 风险链；
- clean rebuild `backend/venv`，避免旧环境里重复/残留 dist-info 继续污染 `pip_audit` 结果。

### 9.3 为什么 requirements-scoped proof 仍然有意义

即使 exact gate 现在已绿，repo-level backend proof 仍建议保留 requirements-scoped 命令：

```bash
PIP_AUDIT_VULNERABILITY_SERVICE=osv backend/venv/bin/python -m pip_audit -r backend/requirements.txt
```

原因：它更直接表达“仓库声明的依赖面”而不是“当前这个本地 venv 里碰巧装了什么”。但由于 auto verification 当前确实执行裸 `backend/venv/bin/python -m pip_audit`，这次 slice 也必须把 exact gate 一起拉到绿色。

### 9.4 本次 backend license proof 结果

已实际执行：

```bash
backend/venv/bin/python -m piplicenses --from=mixed --format=json
```

结果：**通过**。

本次执行生成了完整 JSON 输出（227 个已安装分发包），说明此前 `TypeError: expected string or bytes-like object, got 'NoneType'` 不是仓库天然 blocker，而是旧本地环境/包元数据污染导致的扫描器运行时问题。当前结论应写成：

- 工具前置条件：已满足；
- 扫描命令：已执行成功；
- 状态：**green**；
- 后续若再出现同类 `piplicenses` 元数据崩溃，优先检查并必要时 clean rebuild `backend/venv`，不要直接把 license proof 退回成“长期 blocked”。
