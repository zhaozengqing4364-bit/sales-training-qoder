---
stepsCompleted: [1, 2, 3]
inputDocuments: []
session_topic: 'PPT演讲训练功能系统级评审与优化设计（面向销售内训）'
session_goals: '评估当前前后端实现合理性；围绕讲PPT、脱稿讲解、AI对练目标提出可落地优化方案；形成产品/技术/运营闭环改进清单'
selected_approach: 'ai-recommended'
techniques_used: ['Role Playing', 'Constraint Mapping', 'Solution Matrix']
ideas_generated:
  - '从对话助手转为训练镜像（实时听评而非聊天）'
  - '反馈密度分层：实时信号/阶段小结/结训复盘'
  - '评分从聊得通转为讲得赢（销售能力维度）'
  - '统一能力地图：PPT表达力 + 对练推进力'
  - '学习路径：PPT打底 -> 销售对练 -> 复盘回训'
  - '角色中心策略真源 + 运行时强校验'
  - 'AI主导零配置评分 + 轻治理底线'
context_file: ''
technique_execution_complete: false
facilitation_notes: '用户更关注训练价值闭环与产品结构，不希望复杂配置，倾向AI自动化与低认知负担。'
---

# Brainstorming Session Results

**Facilitator:** Zhaozengqing
**Date:** 2026-02-16

## Session Overview

**Topic:** PPT演讲训练功能系统级评审与优化设计（面向销售内训）
**Goals:** 评估当前前后端实现合理性；围绕讲PPT、脱稿讲解、AI对练目标提出可落地优化方案；形成产品/技术/运营闭环改进清单

### Session Setup

本次会话明确为“策略与产品优化”而非“修复 bug”。
我们将聚焦销售内训核心目标，按前端体验、后端治理、训练流程与结果闭环进行系统性发散与收敛。

## Technique Selection

**Approach:** AI-Recommended Techniques  
**Analysis Context:** PPT演讲训练功能系统级评审与优化设计（面向销售内训），重点是前后端合理性、配置治理收敛与训练效果闭环。

**Recommended Techniques:**

- **Role Playing:** 从销售学员、培训负责人、管理员、AI评审和研发视角拆解真实需求与断点，先对齐“谁的价值”。
- **Constraint Mapping:** 系统化识别入口过多、配置分散、权限边界和运行时一致性等约束，形成可治理问题图谱。
- **Solution Matrix:** 将候选改造方案按影响度、成本、风险排序，生成可执行迭代路线。

**AI Rationale:** 当前问题是典型“多角色系统 + 多入口配置 + 运行时一致性治理”复合问题。先做角色视角校准，再做约束识别，最后做决策矩阵，能够最大化从发散到落地的转化效率。

## Technique Execution Results

**Role Playing（部分完成后切换）:**

- **Interactive Focus:** 从销售学员、培训负责人、管理员与业务负责人多视角澄清“PPT训练 vs 销售对练”的关系与职责边界。
- **Key Breakthroughs:** 明确产品主形态采用“销售对练主入口，PPT为专项训练子模块”，底层统一能力模型与评分轴。
- **User Creative Strengths:** 能准确识别当前系统症结在“反馈价值不足、入口分散、配置复杂”而非单点bug。
- **Energy Level:** 高，用户持续推动落地取向并强调极简可执行。

**Transition Note:**
用户明确指令“下一个”，已从 Role Playing 切换至 Constraint Mapping 继续深挖。

**Constraint Mapping（部分完成后切换）:**

- **Interactive Focus:** 对“必须统一 / 必须区分 / 可延后”三层约束进行收敛，避免前后端入口膨胀与策略漂移。
- **Key Breakthroughs:** 确认“智能体页降级为运行编排页、策略写入只在角色中心、后端契约硬失败、前端能力投影、分阶段迁移”五项硬规则。
- **User Creative Strengths:** 明确接受“AI主导 + 极简治理”的方向，强调不做无谓复杂化。
- **Energy Level:** 稳定且高效，偏好快速进入可执行清单。

**Transition Note:**
用户明确指令“下一步”，已从 Constraint Mapping 切换至 Solution Matrix 进行优先级决策。

**Solution Matrix（进行中）:**

- **Priority Decision:** 确认三波次路线：Wave 1（锁与入口收敛）-> Wave 2（训练路径重排）-> Wave 3（评分与治理闭环）。
- **Wave 1 Focus:** 以“后端不可绕过 + 前端最小可见面”为第一目标，不做大规模视觉重构。
- **Implementation Principle:** 先硬约束、后体验优化；先兼容期，再清理期，避免大爆炸发布。

## Full Execution Baseline (All Waves)

**Wave 1（2周）- 锁与入口收敛：**
- 角色中心作为唯一策略写入源；智能体页降级为运行编排页；运行时必须知识库强校验；非法策略字段写入硬失败。
- 权限模型收敛为“admin可写、support只读（提示词仅可启停默认，不可改正文）、user不可进管理端”。
- 兼容期执行“可读不可写+告警日志”，并配置错误码引导到角色中心。

**Wave 2（2周）- 训练主链路重排：**
- 产品入口定为“销售对练主入口，PPT专项子模块”。
- 训练交互从“聊天”转为“训练镜像”：实时信号+阶段小结+结训复盘+单点改进行动。
- 不做全量视觉重做，优先改信息架构、页面职责和交互流。

**Wave 3（2周）- 评分与治理闭环：**
- AI零配置评分引擎：总分+子分+置信度+下一步动作。
- 三层看板（学员/组长/负责人）和低置信度抽检机制上线。
- 审计与巡检：策略变更可追溯、冲突自动检测、逐步删除旧入口旧字段。
