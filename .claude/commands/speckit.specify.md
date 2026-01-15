---
description: Create or update the feature specification from a natural language feature description.
handoffs:
  - label: Build Technical Plan
    agent: speckit.plan
    prompt: Create a plan for the spec. I am building with...
  - label: Clarify Spec Requirements
    agent: speckit.clarify
    prompt: Clarify specification requirements
    send: true
scripts:
  sh: scripts/bash/create-new-feature.sh --json "{ARGS}"
  ps: scripts/powershell/create-new-feature.ps1 -Json "{ARGS}"
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Outline

The text the user typed after `/speckit.specify` in the triggering message **is** the feature description. Assume you always have it available in this conversation even if `{ARGS}` appears literally below. Do not ask the user to repeat it unless they provided an empty command.

Given that feature description, do this:

1. **Generate a concise short name** (2-4 words) for the branch:
   - Analyze the feature description and extract the most meaningful keywords
   - Create a 2-4 word short name that captures the essence of the feature
   - Use action-noun format when possible (e.g., "add-user-auth", "fix-payment-bug")
   - Preserve technical terms and acronyms (OAuth2, API, JWT, etc.)
   - Keep it concise but descriptive enough to understand the feature at a glance
   - Examples:
     - "I want to add user authentication" → "user-auth"
     - "Implement OAuth2 integration for the API" → "oauth2-api-integration"
     - "Create a dashboard for analytics" → "analytics-dashboard"
     - "Fix payment processing timeout bug" → "fix-payment-timeout"

2. **Check for existing branches before creating new one**:

   a. First, fetch all remote branches to ensure we have the latest information:

      ```bash
      git fetch --all --prune
      ```

   b. Find the highest feature number across all sources for the short-name:
      - Remote branches: `git ls-remote --heads origin | grep -E 'refs/heads/[0-9]+-<short-name>$'`
      - Local branches: `git branch | grep -E '^[* ]*[0-9]+-<short-name>$'`
      - Specs directories: Check for directories matching `specs/[0-9]+-<short-name>`

   c. Determine the next available number:
      - Extract all numbers from all three sources
      - Find the highest number N
      - Use N+1 for the new branch number

   d. Run the script `{SCRIPT}` with the calculated number and short-name:
      - Pass `--number N+1` and `--short-name "your-short-name"` along with the feature description
      - Bash example: `{SCRIPT} --json --number 5 --short-name "user-auth" "Add user authentication"`
      - PowerShell example: `{SCRIPT} -Json -Number 5 -ShortName "user-auth" "Add user authentication"`

   **IMPORTANT**:
   - Check all three sources (remote branches, local branches, specs directories) to find the highest number
   - Only match branches/directories with the exact short-name pattern
   - If no existing branches/directories found with this short-name, start with number 1
   - You must only ever run this script once per feature
   - The JSON is provided in the terminal as output - always refer to it to get the actual content you're looking for
   - The JSON output will contain BRANCH_NAME and SPEC_FILE paths
   - For single quotes in args like "I'm Groot", use escape syntax: e.g 'I'\''m Groot' (or double-quote if possible: "I'm Groot")

3. Load `templates/spec-template.md` to understand required sections.

4. Follow this execution flow:

    1. Parse user description from Input
       If empty: ERROR "No feature description provided"

    1.5. **[AUTO - 项目架构分析] 检测并识别现有项目架构**:
       - **检查是否是现有项目**（有 .specify/specs/ 或已有代码）：

       a. **检测项目结构**：
          ```bash
          # 检查目录结构
          ls -la src/

          # 检查已有功能模块
          ls -la src/features/ 2>/dev/null || ls -la src/modules/ 2>/dev/null

          # 检查技术栈
          cat package.json 2>/dev/null | grep '"dependencies"'
          cat requirements.txt 2>/dev/null
          ```

       b. **识别架构模式**：
          - **按功能分模块** (Feature-based):
            ```
            src/
              features/
                auth/
                user/
                product/
            ```
          - **按层分架构** (Layered):
            ```
            src/
              controllers/
              services/
              models/
            ```
          - **混合架构**: 上述两种混合

       c. **识别代码规范**：
          - **命名规范**: 检查现有文件/函数的命名模式
          - **目录组织**: 识别项目的目录组织原则
          - **文件命名**: kebab-case / camelCase / PascalCase
          - **导入方式**: 相对路径 / 绝对路径 / 别名

       d. **识别现有组件库和工具**：
          - 检查已安装的 UI 库
          - 检查状态管理方案
          - 检查路由方案
          - 检查表单方案
          - 检查 API 调用方式

       e. **生成项目架构报告**：
          创建 `.specify/memory/project-architecture.md`：
          ```markdown
          # 项目架构分析

          ## 检测日期
          {{当前日期}}

          ## 项目结构模式
          - 架构类型: {{Feature-based / Layered / 混合}}
          - 目录组织: {{详细描述}}

          ## 技术栈
          - 前端框架: {{React/Vue/Angular}}
          - 状态管理: {{Redux/Zustand/Context}}
          - UI 组件库: {{shadcn/ui/Material-UI}}
          - 路由: {{React Router/Vue Router}}
          - 表单: {{React Hook Form/Formik}}
          - API: {{axios/fetch/tRPC}}

          ## 代码规范
          - 命名规范: {{描述}}
          - 文件命名: {{kebab-case/camelCase}}
          - 样式方案: {{Tailwind/CSS Modules}}
          - 目录命名: {{描述}}

          ## 现有功能模块
          {{列出所有 features/ 目录}}

          ## 设计系统
          - 颜色方案: {{从现有代码提取}}
          - 字体系统: {{从现有代码提取}}
          - 间距系统: {{从现有代码提取}}
          ```

       f. **如果是现有项目，遵循现有规范**：
          - ✅ 使用相同的目录结构
          - ✅ 使用相同的命名规范
          - ✅ 使用相同的组件库
          - ✅ 使用相同的状态管理
          - ✅ 使用相同的 API 调用方式
          - ❌ 不引入新的技术栈（除非用户明确要求）

       g. **如果是新项目，给出技术选型建议**：
          - 基于需求分析推荐技术栈
          - 使用 A/B/C 选项让用户选择

    2. **[AUTO - 需求澄清] 强制调用 requirement_analyzer skill 进行需求深挖**:

       **🚨 关键指令：必须执行以下步骤，不能跳过！**

       **步骤 A：调用 requirement_analyzer skill**
       ```bash
       # 必须使用 Skill 工具调用
       # 不能自己模拟，不能省略
       Skill: requirement_analyzer
       ```

       **步骤 B：等待 requirement_analyzer 完成所有维度的追问**
       - requirement_analyzer 会逐个维度进行追问
       - 必须等待用户回答每个问题
       - 必须等待 requirement_analyzer 完成（直到用户说"可以了"）
       - 不能提前结束，不能只问一次

       **步骤 C：收集所有澄清结果**
       - 从 requirement_analyzer 获取所有 8 个维度的答案
       - 如果是前端/全栈项目，确保包含前端维度（维度 7 和 8）
       - 将答案记录到内存中

       **步骤 D：验证是否完成**
       - 检查 requirement_analyzer 是否生成了 REQUIREMENTS.md
       - 如果没有，说明没有完成，需要重新调用
       - 如果有，读取该文件获取所有澄清结果

       **🎯 requirement_analyzer 追问的维度**：

       **后端/业务维度**（6 个）：
       - 维度 1: 业务规模与并发
       - 维度 2: 核心业务流程
       - 维度 3: 技术选型约束
       - 维度 4: 团队与开发方式
       - 维度 5: 代码规范与架构
       - 维度 6: 未来可拓展性

       **前端/UI/UX 维度**（2 个，仅前端/全栈项目）：
       - 维度 7: 界面风格与交互
       - 维度 8: 响应式与可访问性

       **前端维度的特殊处理**：
       - requirement_analyzer 会自动调用 ui-ux-pro-max skill
       - 给出 3 个专业方案（A/B/C）
       - 等待用户选择
       - 不是开放式提问

       **⚠️ 禁止行为**：
       - ❌ 不要自己模拟 requirement_analyzer 的问题
       - ❌ 不要只问一次就结束
       - ❌ 不要跳过任何一个维度
       - ❌ 不要自己想前端答案，必须等 requirement_analyzer

       **✅ 正确行为**：
       - ✅ 必须使用 Skill 工具调用 requirement_analyzer
       - ✅ 必须等待所有维度完成（8 个或 6 个）
       - ✅ 必须等待用户说"可以了"/"没问题了"
       - ✅ 必须读取生成的 REQUIREMENTS.md

    2.5. **[AUTO - 生成项目原则] 检查并自动生成 constitution.md**:
       - **关键原则**：不要让用户手动输入！
       - **检查是否已存在**：
         * 如果 `.specify/memory/constitution.md` 已存在：
           - 读取现有原则
           - 检查新需求是否与现有原则冲突
           - 如果冲突，提示用户确认是否更新原则
           - 如果不冲突，跳过生成，使用现有原则
         * 如果不存在：
           - 使用 Skill 工具调用 `coding_standards`
           - **基于需求特点自动生成原则**：
             需求特点 → 原则映射：
             - "高并发"/"多用户" → 添加性能原则、扩展性原则
             - "支付"/"金融"/"订单" → 添加安全原则、事务一致性原则
             - "用户界面"/"体验" → 添加 UX 原则、响应时间原则
             - "数据存储"/"数据库" → 添加数据一致性原则、备份原则
             - "API"/"接口" → 添加 API 设计原则、文档化原则
             - "实时"/"即时" → 添加低延迟原则、异步处理原则
           - **验证生成的原则**：
             * 检查原则是否具体可测量
             * 检查原则之间是否冲突
             * 检查原则是否符合最佳实践（SOLID/DRY/KISS/YAGNI）
           - **自动写入** `.specify/memory/constitution.md`
           - **通知用户**：
             ```
             ✅ 项目原则已自动生成！

             基于需求分析，系统生成了以下原则：
             - [原则 1]
             - [原则 2]
             - [原则 3]

             完整内容：.specify/memory/constitution.md

             💡 如需修改原则，运行：/speckit.constitution [修改内容]
             ```

    3. Extract key concepts from description
       Identify: actors, actions, data, constraints
    4. For unclear aspects:
       - Make informed guesses based on context and industry standards
       - Only mark with [NEEDS CLARIFICATION: specific question] if:
         - The choice significantly impacts feature scope or user experience
         - Multiple reasonable interpretations exist with different implications
         - No reasonable default exists
       - **LIMIT: Maximum 3 [NEEDS CLARIFICATION] markers total**
       - Prioritize clarifications by impact: scope > security/privacy > user experience > technical details
    4. Fill User Scenarios & Testing section
       If no clear user flow: ERROR "Cannot determine user scenarios"
    5. Generate Functional Requirements
       Each requirement must be testable
       Use reasonable defaults for unspecified details (document assumptions in Assumptions section)
    6. Define Success Criteria
       Create measurable, technology-agnostic outcomes
       Include both quantitative metrics (time, performance, volume) and qualitative measures (user satisfaction, task completion)
       Each criterion must be verifiable without implementation details
    7. Identify Key Entities (if data involved)
    8. Return: SUCCESS (spec ready for planning)

5. Write the specification to SPEC_FILE using the template structure, replacing placeholders with concrete details derived from the feature description (arguments) while preserving section order and headings.

6. **Specification Quality Validation**: After writing the initial spec, validate it against quality criteria:

   a. **Create Spec Quality Checklist**: Generate a checklist file at `FEATURE_DIR/checklists/requirements.md` using the checklist template structure with these validation items:

      ```markdown
      # Specification Quality Checklist: [FEATURE NAME]

      **Purpose**: Validate specification completeness and quality before proceeding to planning
      **Created**: [DATE]
      **Feature**: [Link to spec.md]

      ## Content Quality

      - [ ] No implementation details (languages, frameworks, APIs)
      - [ ] Focused on user value and business needs
      - [ ] Written for non-technical stakeholders
      - [ ] All mandatory sections completed

      ## Requirement Completeness

      - [ ] No [NEEDS CLARIFICATION] markers remain
      - [ ] Requirements are testable and unambiguous
      - [ ] Success criteria are measurable
      - [ ] Success criteria are technology-agnostic (no implementation details)
      - [ ] All acceptance scenarios are defined
      - [ ] Edge cases are identified
      - [ ] Scope is clearly bounded
      - [ ] Dependencies and assumptions identified

      ## Feature Readiness

      - [ ] All functional requirements have clear acceptance criteria
      - [ ] User scenarios cover primary flows
      - [ ] Feature meets measurable outcomes defined in Success Criteria
      - [ ] No implementation details leak into specification

      ## Notes

      - Items marked incomplete require spec updates before `/speckit.clarify` or `/speckit.plan`
      ```

   b. **Run Validation Check**: Review the spec against each checklist item:
      - For each item, determine if it passes or fails
      - Document specific issues found (quote relevant spec sections)

   c. **Handle Validation Results**:

      - **If all items pass**: Mark checklist complete and proceed to step 6

      - **If items fail (excluding [NEEDS CLARIFICATION])**:
        1. List the failing items and specific issues
        2. Update the spec to address each issue
        3. Re-run validation until all items pass (max 3 iterations)
        4. If still failing after 3 iterations, document remaining issues in checklist notes and warn user

      - **If [NEEDS CLARIFICATION] markers remain**:
        1. Extract all [NEEDS CLARIFICATION: ...] markers from the spec
        2. **LIMIT CHECK**: If more than 3 markers exist, keep only the 3 most critical (by scope/security/UX impact) and make informed guesses for the rest
        3. For each clarification needed (max 3), present options to user in this format:

           ```markdown
           ## Question [N]: [Topic]

           **Context**: [Quote relevant spec section]

           **What we need to know**: [Specific question from NEEDS CLARIFICATION marker]

           **Suggested Answers**:

           | Option | Answer | Implications |
           |--------|--------|--------------|
           | A      | [First suggested answer] | [What this means for the feature] |
           | B      | [Second suggested answer] | [What this means for the feature] |
           | C      | [Third suggested answer] | [What this means for the feature] |
           | Custom | Provide your own answer | [Explain how to provide custom input] |

           **Your choice**: _[Wait for user response]_
           ```

        4. **CRITICAL - Table Formatting**: Ensure markdown tables are properly formatted:
           - Use consistent spacing with pipes aligned
           - Each cell should have spaces around content: `| Content |` not `|Content|`
           - Header separator must have at least 3 dashes: `|--------|`
           - Test that the table renders correctly in markdown preview
        5. Number questions sequentially (Q1, Q2, Q3 - max 3 total)
        6. Present all questions together before waiting for responses
        7. Wait for user to respond with their choices for all questions (e.g., "Q1: A, Q2: Custom - [details], Q3: B")
        8. Update the spec by replacing each [NEEDS CLARIFICATION] marker with the user's selected or provided answer
        9. Re-run validation after all clarifications are resolved

   d. **Update Checklist**: After each validation iteration, update the checklist file with current pass/fail status

7. Report completion with branch name, spec file path, checklist results, and readiness for the next phase (`/speckit.clarify` or `/speckit.plan`).

**NOTE:** The script creates and checks out the new branch and initializes the spec file before writing.

## General Guidelines

## Quick Guidelines

- Focus on **WHAT** users need and **WHY**.
- Avoid HOW to implement (no tech stack, APIs, code structure).
- Written for business stakeholders, not developers.
- DO NOT create any checklists that are embedded in the spec. That will be a separate command.

### Section Requirements

- **Mandatory sections**: Must be completed for every feature
- **Optional sections**: Include only when relevant to the feature
- When a section doesn't apply, remove it entirely (don't leave as "N/A")

### For AI Generation

When creating this spec from a user prompt:

1. **Make informed guesses**: Use context, industry standards, and common patterns to fill gaps
2. **Document assumptions**: Record reasonable defaults in the Assumptions section
3. **Limit clarifications**: Maximum 3 [NEEDS CLARIFICATION] markers - use only for critical decisions that:
   - Significantly impact feature scope or user experience
   - Have multiple reasonable interpretations with different implications
   - Lack any reasonable default
4. **Prioritize clarifications**: scope > security/privacy > user experience > technical details
5. **Think like a tester**: Every vague requirement should fail the "testable and unambiguous" checklist item
6. **Common areas needing clarification** (only if no reasonable default exists):
   - Feature scope and boundaries (include/exclude specific use cases)
   - User types and permissions (if multiple conflicting interpretations possible)
   - Security/compliance requirements (when legally/financially significant)

**Examples of reasonable defaults** (don't ask about these):

- Data retention: Industry-standard practices for the domain
- Performance targets: Standard web/mobile app expectations unless specified
- Error handling: User-friendly messages with appropriate fallbacks
- Authentication method: Standard session-based or OAuth2 for web apps
- Integration patterns: RESTful APIs unless specified otherwise

### Success Criteria Guidelines

Success criteria must be:

1. **Measurable**: Include specific metrics (time, percentage, count, rate)
2. **Technology-agnostic**: No mention of frameworks, languages, databases, or tools
3. **User-focused**: Describe outcomes from user/business perspective, not system internals
4. **Verifiable**: Can be tested/validated without knowing implementation details

**Good examples**:

- "Users can complete checkout in under 3 minutes"
- "System supports 10,000 concurrent users"
- "95% of searches return results in under 1 second"
- "Task completion rate improves by 40%"

**Bad examples** (implementation-focused):

- "API response time is under 200ms" (too technical, use "Users see results instantly")
- "Database can handle 1000 TPS" (implementation detail, use user-facing metric)
- "React components render efficiently" (framework-specific)
- "Redis cache hit rate above 80%" (technology-specific)
