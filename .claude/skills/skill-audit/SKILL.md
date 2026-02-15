---
name: skill-audit
description: "审核所有已安装的 Claude Code 技能，展示代码行数、功能重叠和改进机会。"
context: fork
version: 1.0.0
author: self
tags: [audit, skills, optimization, meta]
user-invocable: true
allowedTools: [Bash, Read, Grep, Glob]
argument-hint: []
complexity: low
---

# Skill Audit - 技能审核

扫描所有已安装的 Claude Code 技能，生成审核报告。

## 执行步骤

### Step 1: 收集技能列表

扫描以下目录中的所有技能：

```
~/.claude/skills/          # 全局技能
.claude/skills/            # 项目级技能（如果存在）
```

对每个技能目录，读取 `SKILL.md` 提取：
- name
- description
- tags
- version
- allowedTools

### Step 2: 统计代码行数

对每个技能目录，统计总代码行数：
```bash
find <skill_dir> -type f \( -name "*.md" -o -name "*.sh" -o -name "*.py" -o -name "*.ts" \) -exec wc -l {} + 2>/dev/null
```

### Step 3: 功能重叠检测

比较所有技能的 `tags` 和 `description`：
- 找出具有相似 tags 的技能对
- 找出 description 中有相同关键词的技能对
- 标记可能的重复或可合并技能

### Step 4: 生成审核报告

输出格式：

```
## 技能审核报告

### 已安装技能 (N 个)

| 技能名 | 版本 | 行数 | Tags | 说明 |
|--------|------|------|------|------|
| ...    | ...  | ...  | ...  | ...  |

### 功能重叠检测

- [技能A] 与 [技能B]: 共享标签 [tag1, tag2]
- ...

### 改进建议

1. 考虑合并: ...
2. 过大技能（>200行）: ...
3. 缺少版本号: ...
4. 未使用的技能（无 user-invocable）: ...
```

### Step 5: 输出总结

- 总技能数
- 总代码行数
- 潜在优化点数量
