# [PROJECT NAME] Development Guidelines

Auto-generated from all feature plans. Last updated: [DATE]

## Project Overview

**项目名称**: [PROJECT NAME]
**项目描述**: [从 spec.md 提取核心功能描述]
**开发模式**: Spec-Driven Development
**技术栈**: [从 plan.md 提取主要技术]

## Project Principles (Constitution)

[从 .specify/memory/constitution.md 提取项目原则]

这些原则指导所有技术决策和实现细节。

## Coding Standards (通用规范 + 项目特点)

### 通用原则

从 `coding_standards` skill 获取的通用编码原则：

- **SOLID 原则**
  - 单一职责原则 (SRP): 每个类/函数只负责一个功能
  - 开闭原则 (OCP): 对扩展开放，对修改封闭
  - 里氏替换原则 (LSP): 子类可以替换父类
  - 接口隔离原则 (ISP): 客户端不应依赖它不需要的接口
  - 依赖倒置原则 (DIP): 依赖抽象而非具体实现

- **DRY** (Don't Repeat Yourself): 避免代码重复
- **KISS** (Keep It Simple, Stupid): 保持简单
- **YAGNI** (You Aren't Gonna Need It): 不要添加不需要的功能

### 语言特定规范

[根据技术栈从 coding_standards skill 获取]

[从 plan.md 的 Technical Context 提取]

### 测试规范

- **测试金字塔**: 70% 单元测试, 20% 集成测试, 10% E2E 测试
- **TDD 方法**: 先写测试，再写实现
- **测试命名**: `test_函数名_场景` 或 `should_预期行为_when_条件`

## Frontend UI/UX Standards (前端项目专用)

[从 /memory/frontend-standards.md 提取 - 仅当项目包含前端技术时]

### 设计系统

- **颜色方案**: [主色、辅色、语义色定义]
- **字体层级**: [标题、正文、辅助文字规范]
- **间距系统**: [padding、margin 规范]
- **组件库**: [选用的 UI 库及理由]

### UI/UX 最佳实践

- **可访问性**: WCAG 2.1 AA 标准，颜色对比度 >= 4.5:1
- **响应式设计**: 移动优先，断点定义（sm: 640px, md: 768px, lg: 1024px, xl: 1280px）
- **性能优化**: 懒加载、代码分割、图片优化
- **用户反馈**: 加载状态、错误提示、成功确认

### 组件设计原则

- **一致性**: 遵循 Material Design 或 Apple HIG 指南
- **可复用性**: 组件单一职责，属性清晰
- **可测试性**: 组件可独立测试，避免过度耦合

### 前端代码规范

- **命名规范**: 组件使用 PascalCase，文件名使用 kebab-case
- **样式组织**: CSS Modules / Tailwind / Styled Components 规范
- **状态管理**: [选用的状态管理方案及使用规范]
- **路由设计**: [路由结构规范]

## Active Technologies

[EXTRACTED FROM ALL PLAN.MD FILES]

## Project Structure

```text
[ACTUAL STRUCTURE FROM PLANS]

.specify/
  memory/
    constitution.md      # 项目原则
    coding-standards.md  # 通用编码规范（自动生成）
  specs/                 # 功能规范目录
specs/                   # 符号链接到 .specify/specs/
```

## Commands

[ONLY COMMANDS FOR ACTIVE TECHNOLOGIES]

## Code Style

[LANGUAGE-SPECIFIC, ONLY FOR LANGUAGES IN USE]

## Spec-Driven Development Workflow

1. **Constitution** (`/speckit.constitution`) - 建立项目原则
2. **Specify** (`/speckit.specify`) - 定义需求（自动调用 requirement_analyzer）
3. **Clarify** (`/speckit.clarify`) - 澄清需求（可选）
4. **Plan** (`/speckit.plan`) - 技术规划（自动调用 coding_standards 验证）
5. **Tasks** (`/speckit.tasks`) - 任务分解
6. **Implement** (`/speckit.implement`) - 执行实现（自动调用 code_reviewer）

## Automated Quality Checks

本项目已配置自动化质量检查，在每个关键阶段自动触发：

- **Constitution 阶段**: 验证原则符合 SOLID/DRY/KISS/YAGNI
- **Specify 阶段**: 自动调用 requirement_analyzer 进行需求澄清
- **Plan 阶段**: 自动调用 coding_standards 验证技术选型和架构
- **Plan 阶段 (前端)**: 自动调用 ui-ux-pro-max 验证设计系统和 UX 规范
- **Implement 阶段**: 每个任务完成后自动调用 code_reviewer
- **Implement 阶段 (前端)**: 前端代码自动验证 UI/UX 规范

### 手动检查命令

| 命令 | 何时使用 |
|------|----------|
| `/review` | 深度代码审查 |
| `/impact-analyze` | 修改前影响分析 |
| `/complete-check` | 完整性检查 |
| `/refactor` | 智能重构 |
| `/test` | 测试生成与执行 |

## Recent Changes

[LAST 3 FEATURES AND WHAT THEY ADDED]

<!-- MANUAL ADDITIONS START -->
<!-- 手动添加的内容放在这里，不会被自动更新覆盖 -->
<!-- MANUAL ADDITIONS END -->
