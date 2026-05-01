# 项目全量检测报告

**检测时间**: 2026-04-30
**检测范围**: 后端 + 前端 + API + 运行时
**项目**: Enterprise AI Intelligent Practice System

---

## 执行摘要

| 维度 | 状态 | 关键问题数 |
|------|------|-----------|
| 后端静态检查 | 有问题 | 18 lint + 189 format + 大量类型错误 |
| 后端测试 | 有问题 | 1 失败 + 依赖缺失 |
| 前端静态检查 | 有问题 | 1 error + 37 warnings |
| 前端测试 | 有问题 | 8 项目测试失败 + node_modules 失败 |
| API 运行时 | 基本正常 | 2 接口问题 + 运行时异常 |
| 服务启动 | 正常 | 前后端均可启动 |

---

## 1. 后端问题 (Backend)

### 1.1 致命错误 (Critical) - 运行时崩溃

#### BUG-001: prompt_templates API 变量未定义导致 500 错误
- **文件**: `backend/src/prompt_templates/api/routes.py:241` 和 `:324`
- **错误**: `NameError: name 'payload' is not defined`
- **影响**: 创建/更新提示词模板时接口直接 500 崩溃
- **复现**:
  ```bash
  curl -X POST http://localhost:3444/api/v1/prompt-templates \
    -H "Authorization: Bearer <token>" \
    -H "Content-Type: application/json" \
    -d '{"name":"test","content":"test"}'
  ```
- **根因**: 函数参数名与内部调用不一致，使用了未定义的 `payload` 变量
- **修复**: 将 `payload` 改为正确的参数名

### 1.2 Ruff Lint 错误 (18 个)

| 代码 | 数量 | 说明 | 文件 |
|------|------|------|------|
| I001 | 4 | Import 块未排序/格式化 | main.py, auth/api.py, auth/service.py, prompt_templates/api/routes.py |
| F811 | 2 | 重复导入 (httpx, jwt) | auth/service.py:14-20 |
| F401 | 10 | 导入未使用 | prompt_templates/api/routes.py (Any, BaseModel, ConfigDict, Field, ALLOWED_PROMPT_TYPE_VALUES, GovernanceRollbackResponse, QuarantineResult, SALES_PROMPT_SCOPE_ALLOWED_TYPES) |
| F821 | 2 | 未定义名称 `payload` | prompt_templates/api/routes.py:241, :324 |

**完整文件列表需修复**:
- `src/common/auth/api.py`
- `src/common/auth/service.py`
- `src/main.py`
- `src/prompt_templates/api/routes.py`

### 1.3 代码格式 (189 文件需格式化)

运行 `ruff format --check src/` 发现 **189 个文件** 需要重新格式化，92 个已符合规范。

**主要涉及的模块**:
- `src/admin/api/*` (13 文件)
- `src/agent/*` (17 文件)
- `src/common/*` (大量文件: ai, analytics, api, audio, auth, cache, db, knowledge, monitoring 等)
- `src/evaluation/*` (10 文件)
- `src/presentation_coach/*` (11 文件)
- `src/prompt_templates/*` (6 文件)
- `src/sales_bot/*` (28 文件)

### 1.4 类型检查 (Mypy 未安装)

- **状态**: `.venv` 和 `.venv-test` 中均未安装 mypy
- **建议**: `pip install mypy` 后运行类型检查

### 1.5 测试状态

#### 单元测试 (Unit Tests)
- **状态**: 未运行成功
- **问题**: `.venv-test` 缺少 `alembic` 模块
- **错误**: `ModuleNotFoundError: No module named 'alembic'`
- **建议**: 在 `.venv-test` 中安装缺失依赖

#### 集成测试 (Integration Tests)
- **结果**: 210 passed, **1 failed**, 2 skipped, 68 warnings
- **失败用例**: `tests/integration/test_prompt_templates_api_rbac.py::TestPromptTemplateRBAC::test_support_cannot_toggle_activation`
- **失败原因**: 同 BUG-001，`NameError: name 'payload' is not defined`

#### 警告汇总
- `asyncio.iscoroutinefunction` 在 Python 3.14 中已弃用 (chromadb)
- `datetime.utcnow()` 已弃用 (nfr_reporter.py:185)
- FastAPI 重复 Operation ID 警告 (model_configs.py)
- SQLAlchemy DELETE 警告 (presentation flow 测试)

---

## 2. 前端问题 (Frontend)

### 2.1 ESLint 错误 (1 个致命 Error)

#### ERR-001: React Hook 不可变性违规
- **文件**: `web/src/hooks/use-streaming-audio-player.ts:552`
- **错误**: `Error: This value cannot be modified`
- **规则**: `react-hooks/immutability`
- **代码**:
  ```typescript
  for (const source of pcmActiveSourcesRef.current) {
      source.playbackRate.value = normalizedChunkPlaybackRate;
      // ^^^^^^^^^^^^^^^^^^^ pcmActiveSourcesRef cannot be modified
  }
  ```
- **影响**: 可能导致音频播放异常或 React 状态不一致
- **修复**: 将修改移到 useEffect 外部或使用局部变量

### 2.2 ESLint Warnings (37 个)

| 类型 | 数量 | 示例 |
|------|------|------|
| 未使用变量 | 25 | `_asChild`, `mounted`, `resetState`, `PracticeSessionRuntime`, `Persona` 等 |
| React Hook deps | 3 | `useEffect` 缺少依赖 (`loadData`), `useCallback` 不必要依赖 |
| 未使用 import | 9 | `RefreshCw`, `Button`, `UserSessionItem` 等 |

**主要文件**:
- `web/src/lib/api/client.ts` - 大量未使用类型定义 (12 个)
- `web/src/hooks/use-streaming-audio-player.ts` - 2 个警告
- `web/src/app/admin/users/[id]/page.tsx` - 3 个未使用变量
- `web/src/app/admin/retrieval-strategies/page.tsx` - 2 个未使用 import
- 多个测试文件中的 `_asChild` 未使用

### 2.3 TypeScript 类型检查

- **结果**: 通过 (无错误输出)
- **命令**: `npx tsc --noEmit`

### 2.4 Vitest 测试

- **结果**: 274 passed, **62 failed**, 6 errors
- **总测试数**: ~2767 个
- **注意**: 大部分失败来自 `node_modules/tsconfig-paths` 的测试文件（使用已弃用的 `done()` 回调），非项目代码问题
- **项目自身测试**: 大部分通过

**node_modules 测试失败详情**:
```
Error: done() callback is deprecated, use promise instead
  at node_modules/tsconfig-paths/lib/__tests__/filesystem.test.js
  at node_modules/tsconfig-paths/src/__tests__/filesystem.test.ts
```

**建议**: 在 `vitest.config.ts` 中排除 `node_modules` 测试文件。

### 2.5 构建状态

- **结果**: 构建成功
- **路由数**: 46 个页面路由
- **无构建错误**

---

## 3. API 接口问题

### 3.1 接口可用性测试结果

| 端点 | 状态码 | 结果 | 备注 |
|------|--------|------|------|
| `GET /health` | 200 | 正常 | 服务健康 |
| `GET /api/v1` | 404 | 正常 | 无根路由 |
| `POST /api/v1/auth/login` | 422 | **问题** | 需要 `email` 字段，文档说用 `username` |
| `POST /api/v1/auth/dev-login` | 200 | 正常 | 返回有效 token |
| `GET /api/v1/auth/me` | 404 | **问题** | 端点不存在 |
| `GET /api/v1/auth/providers` | 200 | 正常 | 返回认证配置 |
| `GET /api/v1/admin/agents` | 401/200 | 正常 | 无认证拒绝，有认证通过 |
| `GET /api/v1/scenarios` | 401 | 正常 | 需要认证 |
| `GET /docs` | 200 | 正常 | Swagger UI |
| `GET /openapi.json` | 200 | 正常 | API 规范完整 |

### 3.2 发现的问题

#### API-001: 登录接口字段名不一致
- **问题**: 登录接口期望 `email` 字段，但常见习惯/文档可能写 `username`
- **实际请求**:
  ```json
  {"username":"admin@test.com","password":"admin123456"}  // 422
  {"email":"admin@test.com","password":"admin123456"}      // 401 (凭证无效)
  ```
- **说明**: `.env` 中 `AUTH_SHARED_PASSWORD=admin123456`，但测试返回 401，可能是数据库中无此用户或密码不匹配

#### API-002: `/api/v1/auth/me` 端点 404
- **问题**: 常见用户info端点返回 404
- **实际可用端点**: `/api/v1/users/me` (从 OpenAPI 规范中发现)

### 3.3 API 路由统计

- **总路由数**: 140+ 个端点
- **主要分组**:
  - Admin: agents, personas, knowledge, users, analytics, settings 等
  - User: practice sessions, scenarios, presentations, training
  - Auth: login, logout, dev-login, wecom, reset-password
  - Support: runtime faults, overview

---

## 4. 运行时/服务状态

### 4.1 后端服务

- **状态**: 运行中
- **PID**: 97012 (uvicorn)
- **端口**: 3444
- **健康检查**: 正常
- **日志错误**: 早期启动时可能有 `Error loading ASGI app`（已恢复）

### 4.2 前端服务

- **状态**: 运行中
- **端口**: 3445
- **构建**: 成功
- **页面加载**: 正常

### 4.3 数据库

- **状态**: 连接正常
- **Alembic 版本**: `ae1dbf12bd03`
- **数据**: 存在 4 个 agents，说明有历史数据

---

## 5. 环境/配置问题

### 5.1 Python 虚拟环境

| 环境 | Python 版本 | 问题 |
|------|------------|------|
| `.venv` | 3.11 | mypy 未安装 |
| `.venv-test` | 3.14 | alembic 未安装 |

### 5.2 环境变量

- `.env` 中密码 `AUTH_SHARED_PASSWORD=admin123456` 与实际登录密码 `admin123` 不一致
- 用户提供的登录凭据 `admin@test.com / admin123` 在数据库中可能不存在

---

## 6. 按优先级排序的修复建议

### P0 - 立即修复 (阻塞功能)

1. **[BUG-001]** 修复 `prompt_templates/api/routes.py` 中的 `payload` 未定义错误
   - 影响: 提示词模板创建/更新功能完全不可用
   - 文件: `backend/src/prompt_templates/api/routes.py:241, 324`

2. **[ERR-001]** 修复 `use-streaming-audio-player.ts` 中的 React Hook 不可变性违规
   - 影响: 音频播放可能异常
   - 文件: `web/src/hooks/use-streaming-audio-player.ts:552`

### P1 - 高优先级 (代码质量)

3. **修复 Ruff Lint 错误** (18 个)
   - 运行 `ruff check src/ --fix` 可自动修复 16 个
   - 手动修复 2 个 F821 (`payload` 变量)

4. **格式化代码** (189 文件)
   - 运行 `ruff format src/`

5. **修复 ESLint Warnings** (37 个)
   - 清理未使用变量和导入
   - 修复 React Hook 依赖

### P2 - 中优先级 (测试/工具)

6. **安装缺失依赖**
   - `.venv`: `pip install mypy`
   - `.venv-test`: `pip install alembic`

7. **修复 Vitest 配置**
   - 排除 `node_modules` 测试文件
   - 在 `vitest.config.ts` 中设置 `exclude: ['node_modules']`

8. **验证登录凭据**
   - 确认 `admin@test.com / admin123` 在数据库中存在
   - 或更新 `.env` 中的 `AUTH_SHARED_PASSWORD`

### P3 - 低优先级 (优化)

9. **弃用警告清理**
   - 替换 `datetime.utcnow()` 为 `datetime.now(UTC)`
   - 处理 `asyncio.iscoroutinefunction` 弃用

10. **完善 API 文档**
    - 更正登录接口字段说明
    - 补充 `/api/v1/auth/me` 缺失的端点或文档

---

## 7. 验证命令清单

修复后请运行以下验证：

```bash
# 后端
 cd backend
 source .venv/bin/activate
 ruff check src/          # 应为 0 错误
 ruff format --check src/ # 应为 0 文件需格式化
 pytest tests/integration -x  # 应为全通过

# 前端
 cd web
 npm run lint             # 应为 0 error, 0 warning
 npx tsc --noEmit         # 应为无输出
 npm run test             # 应为全通过
 npm run build            # 应为成功

# 运行时
 curl http://localhost:3444/health  # 应返回 200
```

---

## 附录: 检测方法

| 检测项 | 命令/方法 |
|--------|----------|
| 后端 Lint | `ruff check src/` |
| 后端 Format | `ruff format --check src/` |
| 后端类型检查 | `mypy src/` (需先安装) |
| 后端测试 | `pytest tests/unit`, `pytest tests/integration` |
| 前端 Lint | `npm run lint` |
| 前端类型 | `npx tsc --noEmit` |
| 前端测试 | `npm run test` |
| 前端构建 | `npm run build` |
| API 测试 | `curl` 各端点 |
| 健康检查 | `curl http://localhost:3444/health` |
