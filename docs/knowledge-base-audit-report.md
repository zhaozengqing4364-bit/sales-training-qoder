# AI 知识库问答问题审计报告

**生成日期**: 2026-02-16
**分析团队**: knowledge-base-audit
**分析目标**: 为什么 AI 无法完全按照知识库来回答问题

---

## 执行摘要

经过深入分析，发现系统存在 **3 个关键问题** 导致 AI 无法完全按照知识库回答问题：

1. **工具配置方式错误** - 使用自定义函数而非原生 retrieval 工具
2. **知识库绑定流程问题** - 知识库 ID 可能未正确传递
3. **指令引导不足** - system prompt 未明确强制使用知识库

---

## 详细分析

### 问题 1: 工具配置方式错误（严重）

**位置**: `backend/src/sales_bot/websocket/components/stepfun_tool_helpers.py:64-91`

**问题描述**:
当前系统使用**自定义函数** `search_internal_knowledge` 来实现知识检索，而不是使用 StepFun Realtime API 原生的 `retrieval` 工具类型。

**当前实现**:
```python
# stepfun_tool_helpers.py:64-91
if enable_internal_retrieval:
    tools.append(
        {
            "type": "function",
            "function": {
                "name": "search_internal_knowledge",
                "description": "检索企业内部知识库，用于回答产品、流程和策略问题。",
                "parameters": {...}
            }
        }
    )
```

**正确的 StepFun retrieval 工具配置方式**（根据实时语音识别.md）:
```python
{
    "type": "retrieval",
    "function": {
        "description": "触发条件描述",
        "options": {
            "vector_store_id": "知识库ID",
            "prompt_template": "从文档{{knowledge}}中找到问题{{query}}的答案..."
        }
    }
}
```

**影响**:
- 自定义函数需要 AI 模型主动识别并调用，存在调用失败风险
- 原生 `retrieval` 工具由 StepFun 服务器直接处理，稳定性更高
- prompt_template 无法直接传递给自定义函数，导致知识检索的提示不够精确

---

### 问题 2: 知识库绑定流程问题（中等）

**位置**: `backend/src/sales_bot/services/voice_runtime_policy.py:818-825`

**问题描述**:
知识库 ID 的绑定依赖 Agent 和 Persona 的配置。如果配置不当，可能导致 `knowledge_base_ids` 为空列表。

**绑定逻辑**:
```python
# voice_runtime_policy.py:818-825
def _merge_knowledge_base_ids(self, agent, persona):
    merged = []
    merged.extend(_as_list(agent.default_knowledge_base_ids))
    merged.extend(_as_list(persona.knowledge_base_ids))
    return merged
```

**潜在问题点**:
1. Agent 的 `default_knowledge_base_ids` 可能未配置
2. Persona 的 `knowledge_base_ids` 可能未配置
3. 数据库中的知识库 ID 可能已失效

**验证方式**:
检查日志中 `kb_bound` 字段和 `knowledge_base_ids` 列表是否正确填充。

---

### 问题 3: 指令引导不足（中等）

**位置**: `backend/src/sales_bot/services/voice_instruction_compiler.py:119-138`

**问题描述**:
虽然 `VoiceInstructionCompiler` 中包含了知识库检索相关的指令引导，但引导强度可能不足。

**当前指令**:
```python
# voice_instruction_compiler.py:128-131
if retrieval_priority == "kb_first":
    directives.append(
        "遇到业务、产品、流程、报价问题时优先调用内部知识库检索。"
    )
```

**问题**:
- 指令使用 "优先" 而非 "必须"，AI 可能选择不调用
- 缺少强制性的错误处理指导（如：当检索结果为空时明确告知用户）
- 没有明确指导 AI 如何使用检索到的知识片段

---

### 问题 4: 函数调用结果传递问题（需验证）

**位置**: `backend/src/sales_bot/websocket/stepfun_realtime_handler.py:1967-1972`

**代码逻辑**:
```python
# stepfun_realtime_handler.py:1967-1972
await self._send_upstream(
    build_function_call_output_event(
        call_id=call_id,
        output_payload=output_payload,
    )
)

if trigger_followup_response:
    if self._active_response is not None:
        self._pending_tool_followup_response = True
    else:
        await self._create_response()
```

**潜在问题**:
- 当 `trigger_followup_response=False` 时，可能不会触发 AI 使用检索结果
- 需要检查调用点的 `trigger_followup_response` 参数值

---

## 架构分析图

```
用户问题 → StepFun Realtime API
                    ↓
            session.update (tools配置)
                    ↓
        ┌───────────┴───────────┐
        ↓                       ↓
   自定义函数               原生retrieval
   search_internal_knowledge   (未使用)
        ↓
   本地知识检索服务
   (KnowledgeService)
        ↓
   ChromaDB 向量存储
```

---

## 根因总结

| 优先级 | 问题 | 根因 | 影响 |
|--------|------|------|------|
| **P0** | 工具类型错误 | 使用自定义函数而非原生 retrieval 工具 | AI 可能不触发知识检索 |
| **P1** | 知识库未绑定 | Agent/Persona 配置缺失 | 检索结果为空 |
| **P2** | 指令引导弱 | prompt 中 "优先" 非 "必须" | AI 可跳过知识库 |
| **P3** | 调用时序问题 | trigger_followup_response 参数 | 检索结果未使用 |

---

## 建议修复方案

### 方案 A: 改用原生 retrieval 工具（推荐）

将 `stepfun_tool_helpers.py` 中的工具配置改为使用 StepFun 原生的 `retrieval` 类型：

```python
if enable_internal_retrieval:
    # 获取知识库 ID
    kb_ids = effective_policy.get("knowledge_base_ids", [])
    for kb_id in kb_ids:
        tools.append({
            "type": "retrieval",
            "function": {
                "description": "当用户询问产品、流程、政策等问题时使用此工具检索企业内部知识库",
                "options": {
                    "vector_store_id": kb_id,
                    "prompt_template": "根据以下知识库内容回答用户问题：{{knowledge}}。用户问题：{{query}}。如果知识库中没有相关信息，请明确告知用户。"
                }
            }
        })
```

### 方案 B: 增强指令引导

修改 `voice_instruction_compiler.py` 中的指令：

```python
directives.append("当用户询问业务、产品、流程、政策等问题时，**必须**先调用内部知识库检索工具获取相关信息，再基于检索结果回答。如果检索结果为空，明确告知用户知识库中无相关信息。")
```

### 方案 C: 验证知识库绑定

在管理后台添加知识库绑定状态检查，确保 Agent 和 Persona 正确配置了知识库 ID。

---

## 验证清单

- [ ] 检查 Agent 的 `default_knowledge_base_ids` 是否配置
- [ ] 检查 Persona 的 `knowledge_base_ids` 是否配置
- [ ] 检查日志中 `kb_bound` 是否为 true
- [ ] 检查日志中 `knowledge_base_ids` 列表长度 > 0
- [ ] 检查工具配置中是否有 `search_internal_knowledge` 函数
- [ ] 使用调试模式验证检索结果是否正确返回

---

## 结论

AI 无法完全按照知识库回答问题的**根本原因**是：

1. **主要问题**: 使用了自定义函数而非 StepFun 原生 retrieval 工具，导致知识检索依赖 AI 模型主动识别调用
2. **次要问题**: 知识库可能未正确绑定到会话，或 system prompt 引导不够强制

建议优先实施 **方案 A（改用原生 retrieval 工具）**，这是最直接有效的解决方案。

---

*报告生成工具: Agent Teams 并行分析*
