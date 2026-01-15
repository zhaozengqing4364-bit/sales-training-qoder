---
description: Execute the implementation planning workflow using the plan template to generate design artifacts.
handoffs:
  - label: Create Tasks
    agent: speckit.tasks
    prompt: Break the plan into tasks
    send: true
  - label: Create Checklist
    agent: speckit.checklist
    prompt: Create a checklist for the following domain...
scripts:
  sh: scripts/bash/setup-plan.sh --json
  ps: scripts/powershell/setup-plan.ps1 -Json
agent_scripts:
  sh: scripts/bash/update-agent-context.sh __AGENT__
  ps: scripts/powershell/update-agent-context.ps1 -AgentType __AGENT__
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Outline

1. **Setup**: Run `{SCRIPT}` from repo root and parse JSON for FEATURE_SPEC, IMPL_PLAN, SPECS_DIR, BRANCH. For single quotes in args like "I'm Groot", use escape syntax: e.g 'I'\''m Groot' (or double-quote if possible: "I'm Groot").

2. **Load context**: Read FEATURE_SPEC and `/memory/constitution.md`. Load IMPL_PLAN template (already copied).

2.5. **[AUTO - 遵循现有项目架构] 检查并加载项目架构分析**:
   - **检查是否存在项目架构分析**：
     ```bash
     if [ -f ".specify/memory/project-architecture.md" ]; then
         echo "✅ 发现现有项目架构分析"
         EXISTING_PROJECT=true
     else
         echo "ℹ️ 新项目或首次分析"
         EXISTING_PROJECT=false
     fi
     ```

   - **如果是现有项目**：
     a. **读取 `.specify/memory/project-architecture.md`**
     b. **在 Technical Context 中明确说明遵循现有架构**
     c. **新功能设计必须遵循现有规范**
     d. **在生成文件结构时基于现有架构**

   - **如果是新项目**：
     a. 进行技术选型
     b. 生成项目架构分析文档
     c. 后续功能将基于本次选择

3. **Execute plan workflow**: Follow the structure in IMPL_PLAN template to:
   - Fill Technical Context (mark unknowns as "NEEDS CLARIFICATION")
   - Fill Constitution Check section from constitution
   - Evaluate gates (ERROR if violations unjustified)
   - Phase 0: Generate research.md (resolve all NEEDS CLARIFICATION)
   - Phase 1: Generate data-model.md, contracts/, quickstart.md
   - Phase 1: Update agent context by running the agent script
   - Re-evaluate Constitution Check post-design

4. **Stop and report**: Command ends after Phase 2 planning. Report branch, IMPL_PLAN path, and generated artifacts.

## Phases

### Phase 0: Outline & Research

1. **Extract unknowns from Technical Context** above:
   - For each NEEDS CLARIFICATION → research task
   - For each dependency → best practices task
   - For each integration → patterns task

2. **Generate and dispatch research agents**:

   ```text
   For each unknown in Technical Context:
     Task: "Research {unknown} for {feature context}"
   For each technology choice:
     Task: "Find best practices for {tech} in {domain}"
   ```

3. **Consolidate findings** in `research.md` using format:
   - Decision: [what was chosen]
   - Rationale: [why chosen]
   - Alternatives considered: [what else evaluated]

**Output**: research.md with all NEEDS CLARIFICATION resolved

### Phase 1: Design & Contracts

**Prerequisites:** `research.md` complete

1. **[AUTO - Quality Enhancement] 获取通用编码规范并验证设计**:
   - 使用 Skill 工具调用 `coding_standards`
   - 获取技术栈相关的编码规范（SOLID、命名规范、测试标准等）
   - 保存到 `/memory/coding-standards.md` 供后续参考
   - **验证技术选型符合最佳实践**：
     * 检查架构决策是否符合 SOLID 原则
     * 验证测试策略是否符合测试金字塔（70% 单元、20% 集成、10% E2E）
     * 如不符合，生成警告并建议调整

2. **[AUTO - 前端 UI/UX 验证] 检测前端技术栈并获取设计规范**:
   - **检测前端技术栈**：检查 Technical Context 中是否包含前端技术
     * React / Next.js / Vue / Angular / Svelte / Solid.js
     * TypeScript / JavaScript
     * Tailwind CSS / CSS Modules / Styled Components
     * UI 库: shadcn/ui / Chakra UI / Material-UI / Ant Design
   - **如果是前端项目**：
     * 使用 Skill 工具调用 `ui-ux-pro-max`
     * 获取 UI/UX 设计规范（颜色、字体、布局、组件模式）
     * 保存到 `/memory/frontend-standards.md` 供后续参考
     * **验证设计符合 UX 最佳实践**：
       - 检查颜色对比度是否符合 WCAG 标准
       - 验证字体大小适合阅读（最小 16px 正文）
       - 检查组件设计符合 Material Design 或 Apple HIG 指南
       - 验证响应式设计原则
     * **生成前端设计系统文档**：
       - 颜色方案（主色、辅色、语义色）
       - 字体层级（标题、正文、辅助文字）
       - 间距系统（padding、margin 规范）
       - 组件库选择理由
   - **如果不是前端项目**：跳过此步骤

3. **Extract entities from feature spec** → `data-model.md`:
   - Entity name, fields, relationships
   - Validation rules from requirements
   - State transitions if applicable
   - **[AUTO] 验证数据模型符合 SOLID 原则**：
     * 单一职责：每个实体只负责一个概念
     * 开闭原则：实体设计支持扩展而非修改
     * 依赖倒置：依赖抽象而非具体实现

3. **Generate API contracts** from functional requirements:
   - For each user action → endpoint
   - Use standard REST/GraphQL patterns
   - Output OpenAPI/GraphQL schema to `/contracts/`

4. **Agent context update**:
   - Run `{AGENT_SCRIPT}`
   - These scripts detect which AI agent is in use
   - Update the appropriate agent-specific context file
   - Add only new technology from current plan
   - **[AUTO] 整合编码规范到 agent context**：
     * 将 constitution 原则和 coding_standards 合并
     * 确保生成的 CLAUDE.md 包含两者
   - Preserve manual additions between markers

**Output**: data-model.md, /contracts/*, quickstart.md, agent-specific file, /memory/coding-standards.md, /memory/frontend-standards.md (如果是前端项目)

## Key rules

- Use absolute paths
- ERROR on gate failures or unresolved clarifications
