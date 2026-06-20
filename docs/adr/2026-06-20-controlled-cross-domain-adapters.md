# ADR-2026-06-20：受控跨域 Adapter 边界策略

## 背景

当前存在两条显式跨域桥接：

- `sales_trainer/services/curriculum_practice_adapter.py`：新人训练路径需要读取课程文章、章节和题库写入 schema。
- `curriculum_practice/services/sales_trainer_revision_adapter.py`：课程实践发布链路需要调用新人训练路径的修订发布与操作日志能力。

这些桥接不是普通业务模块之间的自由 import。它们是历史迁移阶段的受控 Adapter，用来隔离对方域的 ORM 和实现细节。直接删除会破坏现有发布、题库和训练包链路；任由其扩大则会让 `sales_trainer` 与 `curriculum_practice` 形成隐式双向依赖。

## 决策

保留现有两个 Adapter，但将它们定义为受控桥：

- Adapter 文件是唯一允许跨 `sales_trainer` / `curriculum_practice` 边界的位置。
- Adapter 只能导出 DTO、Protocol、schema type 或窄服务 facade。
- Adapter 不得在 `__all__` 中导出对方域 ORM 模型。
- 新增导出必须先更新 `backend/tests/unit/test_runtime_dependency_contract.py` 的 allowed exports，再说明原因。
- 普通业务代码不得绕过 Adapter 直接 import 对方域模型或服务。

当前允许导出范围由 `test_should_keep_cross_domain_adapters_from_exporting_foreign_orm_models` 固定。

## 备选方案

1. 立即删除 Adapter，并改为全量 common port。
   - 放弃原因：影响发布链路和新人训练内容链路，风险高，超出本次治理任务。
2. 保留现状，只依赖开发者自觉。
   - 放弃原因：边界会继续漂移，测试无法阻止对方 ORM 被重新导出。
3. 保留受控 Adapter，并用契约测试固定允许导出面。
   - 采纳原因：改动小、可验证、保留现有用户路径，同时给后续 port 化留下清晰退役条件。

## 取舍

该决策接受短期存在跨域桥接，但要求桥接显式、窄口、可审计。它不把 Adapter 伪装成最终架构，也不在本轮重构里扩大为通用 port。后续只有当同一能力被两个以上域稳定消费，或 Adapter 开始承载业务规则时，才迁移到 common port。

## 影响

- 代码：现有 Adapter 文件继续存在；契约测试约束 `__all__`。
- 数据：不涉及 migration。
- 权限：不改变现有权限判断。
- 测试：`backend/tests/unit/test_runtime_dependency_contract.py` 成为 Adapter export guard。
- 运维：不改变部署方式。

## 退役条件

满足任一条件时，应将对应 Adapter 迁移为中立 port，并更新本 ADR：

- Adapter 需要导出对方域 ORM 才能继续演进。
- Adapter 内出现状态流转、权限判断、发布规则或评分规则。
- 同一读取/写入能力被第三个域复用。
- 新人训练路径和课程实践的内容资产模型完成统一，Adapter 只剩 pass-through。

## 回滚

如该策略阻塞紧急修复，可临时在 Adapter allowed exports 中加入最小必要导出，并在同一 PR 中记录退役 issue。不得直接删除契约测试，也不得让业务模块绕过 Adapter。
