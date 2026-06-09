# 发布治理修订模型风险登记

关联主计划：`.omo/plans/published-governance-revision-plan.md`

## 风险分级

- P0：会导致历史数据污染、权限绕过、无法回滚或生产不可恢复。
- P1：会导致管理员无法自然编辑、运维无法定位、路径配置仍混乱。
- P2：会导致迁移成本增加、测试不稳定、局部体验退化。

## 风险清单

| ID | 等级 | 风险 | 触发原因 | 早期信号 | 影响 | 预防动作 | 降级或恢复 |
|---|---:|---|---|---|---|---|---|
| R1 | P0 | `ConfigVersion` 不可变性不能直接照搬 | 现有 ConfigBundle 版本同步可能更新已有 snapshot | 代码中出现 update existing snapshot 或 sync 覆盖历史 payload | revision 语义被破坏，历史版本无法审计 | 新增 immutable revision 存储；只复用 lifecycle 体验 | 停止复用 ConfigVersion 写入路径，改为单独 revision table |
| R2 | P0 | 路径配置仍由 Unit 反推 | 继续使用 `SalesTrainerUnit.config.path` 作为 source of truth | 路径配置中心 API 仍聚合 units；无 path active revision | 管理员仍需理解模块单元字段，回滚无法路径级执行 | 阶段 2 先建立 path logical id 和 active pointer | 保留 Unit projection 只读 fallback；禁止新写入 Unit path 真源 |
| R3 | P0 | quiz attempt 缺 revision lineage | 旧 answer snapshot 有内容但没有 path/paper/question revision refs | 新旧题对比只能靠当前 paper 查 latest | 新题污染旧记录，无法解释历史成绩 | attempt 创建时写 path/unit/paper/question revision refs；旧数据 `legacy_snapshot_only` | 不伪造历史 revision；以 snapshot 展示旧记录 |
| R4 | P1 | paper 与 backing unit 耦合 | ExamPaper 仍绑定兼容 quiz unit 复用评分和答题快照 | 管理员页面或日志要求理解 unit_id | 考卷治理和路径绑定混乱 | adapter 层保留兼容，paper 成为 admin/API 语义权威 | 分阶段解耦；短期写审计记录 paper_id 与 unit_id 映射 |
| R5 | P0 | 回滚到非法旧版本 | 旧 revision 引用已归档、删除或未发布资产 | rollback preview 出现 missing dependency | 未来学员路径不可用 | rollback 前执行 publish gate，显示修复入口 | 拒绝回滚；允许先恢复依赖或选择另一个 revision |
| R6 | P0 | 并发编辑覆盖 | 多管理员同时编辑同一 working revision | 无 `base_revision_id`，最后保存覆盖前者 | 管理员修改丢失，审计不可信 | 乐观锁、takeover 审计、diff 冲突提示 | 返回 `[REVISION_CONFLICT]`，要求重新拉取或分支 |
| R7 | P0 | 高风险重评误操作 | prompt/答案/分值修改后自动重评或无范围重评 | 发布 prompt 时触发历史结果变化 | 历史成绩被误改，责任无法追踪 | 重评必须单独 API、预览、reason、trace_id、权限 | 默认 append-only regrade result；展示指针可回退到原始结果 |
| R8 | P1 | 技术字段泄露给普通管理员 | UI 为了方便调试直接展示 `module_key`、`unit_id`、`paper_key`、`sales_trainer` | 页面主卡片或按钮文案出现技术字段 | 管理员被迫理解底层状态机 | 技术字段集中在 diagnostics disclosure；Vitest 断言默认隐藏 | 紧急隐藏技术字段，保留运维展开区 |
| R9 | P2 | 全量测试存在既有失败 | 仓库当前已有大量改动，质量门覆盖广 | `bash scripts/critical-quality-gate.sh` 在无关用例失败 | 无法证明本次改动质量 | 先跑聚焦测试；记录全量失败原文和归因 | 不谎称通过；用聚焦测试和失败证据替代 |
| R10 | P0 | 历史 snapshot 被服务层重新拼 latest | 展示或评分服务为“补全信息”重新读 active asset | 旧 attempt 页面随题目编辑变化 | 历史记录失真 | 历史读取优先 snapshot/revision refs，禁止 fallback latest | 检测污染后从 audit 和 snapshot 恢复展示 |
| R11 | P1 | 归档资产被 active 配置引用 | 归档未检查 binding refs | 归档后 learner 报未发布或文件缺失 | 新学员路径中断 | 归档前查询 active bindings，阻断或要求先换 active ref | 通过 active pointer 回滚或恢复资产 |
| R12 | P1 | 文件物理删除破坏旧材料 revision | 材料版本文件被清理，旧 revision 仍引用 | 旧录音记录材料下载失败 | 历史解释和审计不完整 | 文件删除前检查 revision refs；使用冷存储策略 | 恢复对象存储文件或标记不可恢复并记录审计 |
| R13 | P1 | 权限映射仍然粗粒度 | 继续沿用 admin/support 二分 | 内容管理员可看学员敏感记录，培训负责人可改题 | 管理者无法管控，隐私风险 | 权限集中在 `backend/src/sales_trainer/permissions.py` | 紧急收紧后端权限；前端提示权限变化 |
| R14 | P1 | 业务规则硬编码在页面 | 文案、按钮、流程、阈值散落在 TSX | rg 出现多个同义业务文案和状态判断 | 后续管理仍需改代码 | 文案和规则来自 API/config 或集中 UI copy | 收敛到 `web/src/lib/sales-trainer/*` 和后端配置 |
| R15 | P0 | 路由直接改 ORM 绕过审计 | 快速实现 save/publish/rollback 时在 api.py 修改 model | 审计缺失，权限和门禁绕过 | 数据不一致、无法追责 | route 只调用 service；service 内统一审计和门禁 | 回滚 route 直写，补审计迁移或人工核对 |
| R16 | P1 | 草稿资产被 learner 使用 | 兼容接口未校验 active/published revision | learner 打开草稿文章或草稿考卷 | 学员看到未审核内容 | learner lookup 只读 active published revision | 返回 `[REVISION_DEPENDENCY_INVALID]` 并给管理员入口 |
| R17 | P1 | 回滚语义被理解成历史改写 | UI 或 API 使用“恢复所有记录”文案 | 管理员以为能撤销历史成绩 | 业务误用、审计争议 | UI 明确“只影响未来”；历史重评单独入口 | 文案热修，撤回错误操作需走 regrade 审计 |
| R18 | P2 | 旧数据 backfill 过度自信 | 历史对象无法可靠匹配 revision 却强行回填 | revision refs 与 snapshot hash 不一致 | 历史追溯错误 | 只在 hash/ID 可证明时回填；否则 legacy 标记 | 清除错误 lineage，恢复 snapshot-only 展示 |
| R19 | P1 | 课程闭环对齐破坏现有 `published_asset_refs` | 新 revision id 接入时不兼容旧 refs | 旧 PracticeTemplate 无法创建 session | 课程训练中断 | 解析器兼容旧 refs 和新 refs；发布时写新 refs | 回退到旧 refs 解析路径，保留 runtime snapshot |
| R20 | P2 | 浏览器验收只看单页面 | 验收没有旧学员/新学员对照数据 | 截图显示页面可打开但无业务证据 | 问题进入试运行才暴露 | 必须构造旧 attempt、新 attempt、回滚后新 learner 三组证据 | 补跑端到端手册，记录缺口 |

## 风险审查门

每个阶段结束前必须回答：

1. 本阶段是否引入新的 source of truth？
2. 旧 source of truth 是否保留为只读兼容或 projection？
3. 历史记录是否只读 snapshot/revision refs？
4. active pointer 变更是否只影响未来？
5. 所有高风险动作是否有 reason、trace_id 和 before/after？
6. 普通管理员是否仍需要理解技术字段？
7. 是否有聚焦测试证明本阶段最关键不变量？

任一答案为“否”时，不进入下一阶段。

