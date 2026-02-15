---
name: reflection
description: "对话复盘与学习提取 - 分析当前会话的任务模式、错误和改进点。"
context: fork
version: 2.0.0
author: self
tags: [reflection, learning, meta, improvement]
user-invocable: true
allowedTools: [Read, Bash, Grep, Glob, mcp__memory__search_nodes, mcp__memory__create_entities, mcp__memory__add_observations]
argument-hint: []
complexity: low
---

# Reflection - 对话反思与学习提取

分析当前会话中的工作模式，提取可复用的经验。

## 执行步骤

### Step 0: 读取会话数据（新增）

**0a. 读取最近会话统计**
- 读取 `.claude/memory/patterns.json` 获取最近 10 次会话统计
- 提取：工具调用次数、高频工具、重复模式

**0b. 如果有 transcript_path**
- 读取实际 transcript 分析任务和错误
- 从中识别：用户意图、实际完成的工作、遇到的问题

### Step 1: 回顾当前会话

回顾本次会话中完成的所有任务，整理：

1. **任务清单**: 列出本次会话中执行的所有任务
2. **工具使用**: 统计各类工具的使用频率
3. **错误与重试**: 识别失败的操作和重试次数

### Step 2: 模式分析

分析会话中的工作模式：

**2a. 效率模式**
- 哪些操作可以更高效？（如：多次 grep 可以合并）
- 是否有不必要的探索？（如：已知信息重复查找）

**2b. 错误模式**
- 重复出现的错误类型
- 错误的根本原因（假设错误、上下文缺失、工具误用）

**2c. 决策模式**
- 关键决策点及其结果
- 是否有更好的替代方案

### Step 3: 提取学习点

将发现整理为可行动的改进：

```
## 反思报告

### 最近 N 次会话趋势

| 日期 | 工具调用 | 高频工具 | 重复模式 |
| ... | ... | ... | ... |
| 2026-02-15 | 25 | Grep:8, read_file:6, Bash:5 | 连续 Grep 3次 |
| 2026-02-14 | 18 | read_file:7, Grep:5, Edit:4 | - |
| ... | ... | ... | ... |

### 当前会话概要
- 持续时间: ~N 分钟
- 任务数: N
- 工具调用: N 次
- 成功率: N%

### 可优化模式
1. **[具体模式]**: 出现 N 次，建议 [具体行动]
2. ...

### 做得好的
1. ...
2. ...

### 需要改进的
1. ...
2. ...

### 建议的 CLAUDE.md 更新

（直接给出可复制粘贴的文本）

```markdown
- **[日期] [模式名]**: [描述]
```
```

### Step 4: 持久化学习

如果用户确认，将学习点：
1. 追加到 `.claude/memory/patterns.json`
2. 建议更新到相关 CLAUDE.md 的自生长记录区

### Step 5: 输出总结

一句话总结本次会话的核心收获和下次改进方向。
