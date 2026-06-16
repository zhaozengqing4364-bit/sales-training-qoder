# ADR-2026-06-15：学习内容归档受新人训练路径绑定保护

## 背景

学习内容由 `curriculum_practice` 负责正文、章节、发布修订和归档；新人训练路径由 `sales_trainer` 负责把已发布 `LearningContent` 绑定到 `article_exam` 模块并发布路径配置。运营在学习内容详情页归档文章时，可能不知道该文章仍被 active 或 working 新人训练路径引用，导致学员端文章不可用。

## 决策

`curriculum_practice` 的学习内容归档接口在执行归档前调用 `sales_trainer` 的学习内容绑定影响查询服务。若目标内容被 active 或 working 新人训练路径引用，服务端返回 409 `[LEARNING_CONTENT_BOUND_TO_NEWCOMER_PATH]`，要求管理员先替换文章绑定或路径配置并发布路径配置。

绑定影响的权威仍在 `sales_trainer`，因为路径 revision、模块配置、小单元章节序号和 learner 生效状态都属于新人训练路径域。`curriculum_practice` 只消费一个窄接口判断是否允许归档。

## 备选方案

1. 只在前端禁用归档按钮。放弃，因为绕过前端或旧页面仍可能破坏学员端。
2. 在 `curriculum_practice` 内复制新人训练路径绑定查询逻辑。放弃，因为会复制路径 revision 语义和小单元规则，长期容易分叉。
3. 将学习内容归档完全迁移到 `sales_trainer`。放弃，因为学习内容生命周期仍属于课程内容域，迁移会扩大边界。

## 取舍

选择跨域窄接口会让 `curriculum_practice` 对 `sales_trainer` 有一个明确依赖，但依赖点只限归档保护，不改变学习内容发布、章节编辑和修订存储的所有权。这样能用最小改动保证服务端硬约束，同时避免把新人训练路径规则复制到课程内容域。

## 影响

- 代码：新增 `LearningContentBindingImpactService`，学习内容归档前调用该服务。
- 数据：不新增表，不做迁移；读取 `sales_trainer_asset_revisions` active/working path revision。
- 权限：查询影响接口复用新人训练路径内容管理权限；归档接口继续复用学习内容管理权限。
- 测试：覆盖 binding impact、已绑定内容归档 409、未绑定内容原归档路径。
- 运维：如果路径 revision 数据非法，归档保护 fail-closed，返回服务错误而不是放行归档。

## 回滚

若该依赖造成不可接受的域耦合，可保留前端影响提示，撤回归档接口中的 guard 调用，并新增异步审计告警提示“已归档内容仍被路径引用”。在正式回滚前必须确认没有 active/working 路径仍引用目标学习内容。
