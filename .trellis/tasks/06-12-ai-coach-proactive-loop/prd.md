# 商务技巧 AI 教练主动训练闭环继续实施

## 背景

当前工作区已经存在商务技巧 AI Coach 的一批后端、前端、迁移和测试改动。本任务接续实施附件计划中的主动训练闭环，把 `/sales-trainer/business-skills/coach` 从用户主动要求出题升级为后端教练主导训练局。

## 目标

1. 核对现有实现覆盖度，找出缺口。
2. 继续完成后端 `next_coach_action`、`coach_state`、主动开局、答后自动推进、审计和 public projection。
3. 继续完成 learner chat surface、卡片 renderer、状态展示和 admin 配置入口。
4. 补齐契约、seed、测试和验证证据。

## 配置化判断

- 稳定代码逻辑：动作类型白名单、状态机边界、评分后事务顺序、重复提交防护、public DTO 脱敏、LLM 输出校验和错误分类。
- 可配置业务规则：主动教练开关、进入后行为、答后自动推进开关、每轮自动推进步数、连续答对/答错阈值、补救策略、总结策略、允许动作白名单。
- 配置来源：复用新人训练路径 `modules[].ai_coach`，不新增孤立配置体系。
- 管理入口：`/admin/sales-trainer/ai-coach`，发布/回滚/审计沿用路径配置 revision 和 operation log。
- 缺失处理：后端使用安全默认值，learner 入口依据 availability 隐藏或显示明确不可用状态。
- 非法处理：保存/运行时返回 typed error，前端只展示后端错误，不自造业务规则。

## 非目标

- 不新增 Next API route。
- 不接入 SSE/WebSocket 作为 v1 必需项。
- 不复用正式考试 attempt 流程。
- 不让前端决定下一步教练动作。

## 验收

1. 相关后端单测覆盖默认配置、规则决策、主动开局、答后自动推进、重复提交和 public projection。
2. 相关前端测试覆盖入口、状态展示、卡片渲染、followup prompt 和 admin 配置字段。
3. `docs/api-contract/sales-trainer.md` 与实现一致。
4. 相关 focused tests 通过；如存在既有失败，需要明确说明。
