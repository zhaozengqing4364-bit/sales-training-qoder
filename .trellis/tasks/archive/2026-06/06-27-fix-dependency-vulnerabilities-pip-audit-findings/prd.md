# PRD: 修复 pip-audit 发现的 28 个依赖漏洞

## 背景

P0 任务(`06-27-fix-release-verification-bandit-safety-ci-gap`)把 pip-audit 接入 release gate 后,扫描出 28 个依赖漏洞分布在 11 个包。这导致 safety check 永远 `passed=False` → release gate NO_GO。P0 保证了"扫描器能正确运行和解析",本任务负责"让扫描结果能通过"——即修复漏洞使 safety check 转为 passed。

## 漏洞分布(核查实据)

11 个包 / 28 漏洞:
- **aiohttp 3.13.5**(11 漏洞)→ 3.14.1
- **pip 26.0**(3)→ 26.1.2(传递,venv 自带)
- **pypdf 6.12.2**(3)→ 6.13.3
- **python-multipart 0.0.29**(3)→ 0.0.31
- **starlette 1.1.0**(2)→ 1.3.1
- **cryptography 48.0.0**(1)→ 48.0.1
- **langchain 1.3.2**(1)→ 1.3.9
- **langsmith 0.8.5**(1)→ 0.8.18(传递,随 langchain)
- **msgpack 1.1.2**(1)→ 1.2.1(传递)
- **pydantic-settings 2.14.1**(1)→ 2.14.2
- **torch 2.12.0**(1)→ 无修复版本

## 决策(已 brainstorm 锁定)

采用 **乙(一批全升)+ 卸载 torch + 三层验证**:

### 一批全升(非分级)
brainstorm 原计划分级(低风险先升、高风险后升),但 dry-run 核查证伪了高风险假设:
- `pip install --dry-run aiohttp==3.14.1` → `Would install`,**无冲突**
- `pip install --dry-run starlette==1.3.1` → `Would install`,**无冲突**
- dashscope 对 aiohttp **无版本上限约束**(裸 `aiohttp` 依赖)
- aiohttp 在 `src/` **零直接使用**(只被 dashscope SDK 间接依赖)
- starlette 仅 3 个 middleware 文件直接使用(auth/base_handler/error_handling)
- fastapi 0.136.3 未锁 starlette 上限

结论:无依赖冲突 → 分级无技术必要,一批全升 + 统一验证更快定位问题。

### 卸载 torch —— 实现期回写:改为保留 + ignore

原计划卸载 torch(`Required-by: 空`)。实现期核查发现 **`funasr`(ASR 核心)运行时需要 torch**:
- `pip show funasr` 的 `Requires` 未直接列 torch,但 `funasr` 是 ASR 推理库,运行时 `import torch`(静态 metadata 的 `Required-by` 不反映 runtime import)。
- 卸载 torch → funasr ASR 断裂 → 违背宪法 §I"用户体验永不中断"。

**修正决策**:保留 torch(无修复版本,无法升级),在 `_run_safety_scan` 的 `pip-audit` 调用加 `--ignore-vuln` 跳过 torch 的漏洞 id。这是"无修复版本 + 运行时必需"的唯一合法处理。

torch 的漏洞不阻断 release(显式 ignore + 注释说明原因),其余 27 个漏洞通过升级修复。

### 升级清单(一批全升)
直接依赖 requirements.txt 升版本下限:
- `aiohttp>=3.13.4` → `aiohttp>=3.14.1`
- `python-multipart>=0.0.6` → `python-multipart>=0.0.31`
- `pypdf>=6.10.0` → `pypdf>=6.13.3`
- `cryptography>=48.0.1` → `cryptography>=48.0.1`(已达标,确认即可)
- `langchain>=0.1.0` → `langchain>=1.3.9`
- `pydantic-settings>=2.1.0` → `pydantic-settings>=2.14.2`
- starlette(传递,由 fastapi 拉,不直接锁但验证升到 1.3.x)

传递依赖(langsmith/msgpack/pip)随父升级或 venv 重装自动解决。

## 范围

### 必改
- `backend/requirements.txt`:
  - 升级 7 个直接依赖版本下限:aiohttp、python-multipart、pypdf、cryptography、langchain、pydantic-settings(starlette 由 fastapi 传递,不直接锁但需确认 fastapi 拉到 1.3.x)
  - 删除 `torch>=2.0.0`
- `backend/uv.lock`:重新生成同步
- 传递依赖(langsmith/msgpack/starlette/pip)随父升级或 venv 重装自动解决,不单独锁

### 不改(明确边界)
- 不改业务代码(aiohttp/src 零使用,starlette 3 文件仅升级不改逻辑)
- 不处理 bandit 的 8 MEDIUM/75 LOW(非阻断,另一条线)
- torch 若卸载导致某测试依赖断裂,回写本 PRD 决定保留+ignore

## 验收标准(三层验证)

- [ ] **L1 依赖层**:`pip-audit -f json` 重新扫描,漏洞归零(torch 已卸载,无残留)
- [ ] **L2 单测层**:`pytest tests/unit/ tests/integration/ tests/contract/` 全过(无新失败)
- [ ] **L3 运行时层**:后端可 import + `app_factory.create_app()` 构造成功 + WebSocket 路由注册成功(starlette/middleware 不破)
- [ ] `requirements.txt` / `uv.lock` 一致(本地 `pip install -r requirements.txt` 干净)
- [ ] `_run_safety_scan` 端到端返回 `passed=True`(safety check 转绿,release gate 不再因漏洞 NO_GO)

## 风险与回写

- **starlette 1.1→1.3 可能有 middleware API 变更**:3 个 middleware 文件(auth.py/base_handler.py/error_handling/middleware.py)若测试 L3 失败,需回写本 PRD 记录具体断裂点,决定回退 starlette 还是适配代码。
- **aiohttp 3.14 对 dashscope SDK 的影响**:虽然 dashscope 不约束版本,但 SDK 运行时行为可能依赖 aiohttp 3.13 特性。L3 验证若涉及真实 ASR 调用失败(需 API key),记为已知限制,不阻断本任务(本任务验证到"import + app 构造"层)。
- **torch 卸载后若 ChromaDB 等隐式依赖断裂**:`Required-by: 空` 是当前状态,但 ChromaDB 可能在运行时按需 import torch。若 L2/L3 失败,回写决定保留 torch + `--ignore-vuln`。

## 不属于本任务

- bandit MEDIUM/LOW 清理(另一条线)
- dual-read 审计开关(P2)
- WebSocket 深查(P3)
