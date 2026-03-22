# AI智能演练系统 - 审计报告修复版

**修复日期**: 2026-02-24  
**文档版本**: v2（证据化修复版）  
**修复范围**: `backend/src` + 本报告文件  
**修复策略**: 保留 4xx `HTTPException` 语义；统一治理 5xx 响应出口

---

## 1. 执行摘要

本次对 `docs/audit-report-2026-02-24.md` 进行了“精准全面修复”，并同步完成代码侧治理闭环。

核心结果：

- `raise HTTPException(status_code=500, ...)`：**43 -> 0**
- 裸 `except:`：**1 -> 0**
- `TODO/FIXME`：**2（保留并标记为后续治理项）**
- 4xx 语义：**保持不变**

---

## 2. 原报告纠偏（事实修复）

### 2.1 误报修复

原报告将以下 `print(...)` 判定为运行时代码问题，实际为 **docstring 示例代码**，不参与运行：

- `backend/src/common/ai/encryption.py:31`
- `backend/src/agent/capabilities/registry.py:200`
- `backend/src/agent/capabilities/registry.py:252`

结论：上述项从“代码缺陷”下调为“文档示例观察项”。

### 2.2 路径口径修复

原报告大量路径省略 `backend/src/` 前缀，已统一为可直接定位的仓库相对路径。

### 2.3 统计口径修复

原报告存在“问题数量”和“风险汇总”口径不一致；本版改为命令可复核口径，所有结论都可通过命令复现。

---

## 3. 本次代码修复内容

### 3.1 新增统一 5xx 错误出口

- 新增 `backend/src/common/api/server_error.py`
- 扩展 `backend/src/common/api/response.py`：新增 `server_error_response(...)`

统一规则：

- 5xx 场景不再直接 `raise HTTPException(500, ...)`
- 统一返回结构：`success=false` + `error` + `message` + `trace_id`
- 保留日志记录与上下文（error_code、业务标识）

### 3.2 全量替换 5xx 直抛

已覆盖下列模块：

- `backend/src/admin/api/admin.py`
- `backend/src/admin/api/voice_runtime.py`
- `backend/src/agent/api/agents.py`
- `backend/src/agent/api/personas.py`
- `backend/src/agent/api/agent_personas.py`
- `backend/src/evaluation/api.py`
- `backend/src/sales_bot/api/scenarios.py`
- `backend/src/presentation_coach/api/presentations.py`
- `backend/src/common/knowledge/api.py`
- `backend/src/common/api/analytics.py`
- `backend/src/admin/api/presentation_ai.py`
- `backend/src/prompt_templates/api/routes.py`
- `backend/src/admin/api/model_configs.py`
- `backend/src/common/api/practice.py`

### 3.3 裸 except 修复

- `backend/src/common/ppt/version_manager.py`
- `_get_current_version(...)` 中 `except:` 已替换为 `except Exception as e` 并补充日志。

---

## 4. 证据矩阵（全量清单）

### 4.1 5xx 统一出口落点（当前代码）

以下为当前 `build_server_error(...)` 使用点：

- `backend/src/presentation_coach/api/presentations.py:202`
- `backend/src/evaluation/api.py:114`
- `backend/src/evaluation/api.py:139`
- `backend/src/agent/api/agents.py:54`
- `backend/src/sales_bot/api/scenarios.py:174`
- `backend/src/agent/api/agent_personas.py:45`
- `backend/src/admin/api/presentation_ai.py:104`
- `backend/src/prompt_templates/api/routes.py:90`
- `backend/src/admin/api/model_configs.py:1004`
- `backend/src/admin/api/voice_runtime.py:115`
- `backend/src/admin/api/voice_runtime.py:144`
- `backend/src/admin/api/voice_runtime.py:170`
- `backend/src/admin/api/voice_runtime.py:209`
- `backend/src/agent/api/personas.py:46`
- `backend/src/common/knowledge/api.py:75`
- `backend/src/common/knowledge/api.py:361`
- `backend/src/common/knowledge/api.py:392`
- `backend/src/admin/api/admin.py:87`
- `backend/src/admin/api/admin.py:192`
- `backend/src/admin/api/admin.py:217`
- `backend/src/admin/api/admin.py:245`
- `backend/src/admin/api/admin.py:282`
- `backend/src/admin/api/admin.py:309`
- `backend/src/admin/api/admin.py:359`
- `backend/src/admin/api/admin.py:395`
- `backend/src/admin/api/admin.py:424`
- `backend/src/admin/api/admin.py:459`
- `backend/src/admin/api/admin.py:499`
- `backend/src/admin/api/admin.py:525`
- `backend/src/admin/api/admin.py:559`
- `backend/src/common/api/analytics.py:59`（通过 `_server_error(...)` 转发）
- `backend/src/common/api/practice.py:448`
- `backend/src/common/api/practice.py:518`
- `backend/src/common/api/practice.py:730`
- `backend/src/common/api/practice.py:779`
- `backend/src/common/api/practice.py:1628`

### 4.2 当前“print / TODO / 异常模式”真实状态

`print(`（docstring示例，非运行时）:

- `backend/src/common/ai/encryption.py:31`
- `backend/src/agent/capabilities/registry.py:200`
- `backend/src/agent/capabilities/registry.py:252`

`TODO`（保留项）:

- `backend/src/common/auth/service.py:129`（企业微信 SSO 接入）
- `backend/src/evaluation/services/staged_evaluation.py:112`（scenario_type 参数化）

裸 `except:`：

- 当前扫描结果：**0**

---

## 5. 量化结果（修复后）

### 5.1 指标统计

- `raise HTTPException(status_code=500, ...)`: **0**
- `status_code=500` 语句总量（全仓字面量）: **0**
- `except:`（裸捕获）: **0**
- `TODO/FIXME`: **2**
- `HTTPException` 总量（含 4xx 与导入）: **173**
- `Result.fail(...)` 总量: **270**

### 5.2 HTTPException 分布（按顶层目录）

- `common`: 56
- `admin`: 49
- `agent`: 33
- `prompt_templates`: 15
- `presentation_coach`: 6
- `evaluation`: 5
- `main.py`: 4
- `sales_bot`: 3
- `support`: 2

说明：当前分布主要由 4xx 语义和历史代码结构决定，本轮未改动 4xx 语义。

---

## 6. 复核命令（可复现）

```bash
# 1) 500 直抛应为 0（跨行匹配）
rg -nU "raise\s+HTTPException\([\s\S]{0,200}?status_code\s*=\s*500" backend/src -S

# 2) 裸 except 应为 0
rg -n "^\s*except\s*:\s*$" backend/src -S

# 3) TODO/FIXME 全量
rg -n "TODO|FIXME" backend/src -S

# 4) print( 全量（用于区分示例代码与运行时代码）
rg -n "^\s*print\(" backend/src -S

# 5) HTTPException 分布
rg -n "\bHTTPException\b" backend/src -S | awk -F: '{print $1}' | sed 's#backend/src/##' | cut -d/ -f1 | sort | uniq -c | sort -nr
```

---

## 7. 风险与后续治理建议

### 7.1 已收敛风险

- 5xx 错误出口分散且不一致：已统一
- 裸 `except` 吞错：已消除

### 7.2 待治理项（非阻塞）

- 企业微信 SSO 正式接入（`common/auth/service.py`）
- `staged_evaluation` 场景类型参数化（`evaluation/services/staged_evaluation.py`）
- `HTTPException` 与 `Result` 双范式长期并存问题（当前保留，建议后续分模块治理）

---

## 8. 结论

本报告已从“描述性审计”修复为“证据化审计”，并完成对应代码整改闭环。当前代码基线满足：

- 5xx 不再直接 `raise HTTPException(500)`
- 异常处理具备统一返回结构与 `trace_id` 可观测性
- 审计结论可通过命令逐条复核
