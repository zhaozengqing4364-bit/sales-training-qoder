# ADR：新人训练管理工作台与 ReleasePlan 单一发布权威

- 状态：Accepted
- 日期：2026-07-17
- 风险等级：P1
- 相关 ADR：`2026-07-16-newcomer-foundation-domain-and-modules.md`、`2026-07-16-enrollment-revision-freeze.md`、`2026-07-17-competency-evidence-readiness-review.md`

## 背景

前置切片已经分别建立 Path、学习资源、录音、Coach、持久任务和 Readiness 的领域写权威，但运营入口和发布动作仍然分散。Slice 2 为独立验收留下的 Path/资源直发命令无法表达完整依赖闭包，也无法让管理员在一次可审计操作中确认阻塞、影响和回滚目标。来源文件解析与题目生成还是长耗时工作，不能退回同步请求或把内部 Prompt/模型合同交给浏览器组装。

## 决策

1. `/admin/newcomer-training` 是新人基础训练唯一管理入口。总览、路径、内容、题目、班级、评测、复核、发布和设置按运营任务组织；可见区域和动作来自后端 capability + organization/object scope 投影，而不是前端角色名判断。
2. 管理工作台只组合各领域公开查询和应用命令。`newcomer_training`、`learning`、`audio_assessment`、`ai_coach`、`task_runtime` 与 `readiness` 继续拥有各自状态机和写入；工作台不得跨域 ORM 写入、复制规则或建立第二份业务状态。
3. `ReleasePlanService` 是 Path 及其可发布训练资源正式生效的唯一协调者。预览冻结 exact Path working revision、依赖图、目标修订、校验报告、影响摘要、合同 hash 和短期 preview token；发布必须提交同一 impact hash、`If-Match` 和幂等键。
4. 当前原子闭包按 Source、Question、LearningUnit、Quiz、Path 的依赖顺序发布；已经发布且由其他领域治理的评分、Coach、Prompt 和模型合同只作为 exact dependency 被校验，不在浏览器或 Path route 中改写。任何阻塞都会使事务失败，原 active ReleasePlan 和已发布指针继续有效，不出现半发布。
5. 新发布只改变 Path 的 published/active 发布指针，不自动迁移活跃 Enrollment。Enrollment 继续冻结原 PathRevision；迁移必须使用独立的 preview/confirm、影响 hash、版本、理由、权限与审计命令。
6. 回滚不是覆写或删除修订，而是经过 preview/confirm 后重新激活同一 Path 的已知稳定 ReleasePlan。历史计划、目标修订、发布/回滚操作者和审计记录永久保留。
7. Slice 2 的 Path/资源直发 HTTP 路由曾作为固定返回 409 `[NEWCOMER_RELEASE_PLAN_REQUIRED]` 的有期限墓碑；Slice 8 在消费者与 OpenAPI inventory 通过后已删除。它们不得转发、双写或恢复直发。
8. Source 文件上传创建 pending working revision，先校验 allowlist、文件签名与 hash，再保存受组织隔离的 artifact 并排入持久解析任务。解析结果回写同一修订的可恢复状态；API 请求不等待解析完成，失败清理只处理本次新建的未正式 artifact。
9. 题目生成页面只提交已发布 Source/Unit、数量和已发布策略修订的安全选择。服务端验证 Source–Unit Anchor 关系，使用与 Worker 相同的输入上下文严格编译 Prompt，并冻结 `prompt_contract_hash`；普通 UI 不接收 Prompt 正文、Provider/model payload 或客户端可伪造的 hash。候选题仍须人工审核，批量审核必须 preview/confirm 并逐项报告结果。
10. 当前题目生成仅接受 published Source 和 LearningUnit。直接从 mutable working revision 生成会在任务排队期间发生输入漂移；若未来需要支持，必须先增加冻结内容快照/hash 和相应血缘合同，不能读取“当前 working”作为异步任务输入。
11. Realtime 客户语音对练不进入本工作台、发布闭包、设置、导航或首发依赖。

## 结果

- 管理员从一个任务型工作台完成配置、审核、运营、发布和回滚，但领域边界与权限边界不被 UI 聚合破坏。
- 正式生效动作可以追溯到完整依赖图、精确修订、影响预览、操作者、理由和审计；失败时旧版本继续服务。
- Source 解析和题目生成具备持久任务位置、恢复语义和受治理 AI 合同，不依赖浏览器在线或进程内临时任务。
- 已冻结 Enrollment 不会因内容发布发生隐式漂移。

## 回滚与降级

- 发布失败无需数据补偿：事务回滚，旧 active ReleasePlan 和 published pointers 保持不变。
- 已发布错误版本通过 ReleasePlan 回滚命令重新激活已知稳定计划；不得手工改表或恢复旧直发入口。
- 可按 capability/feature flag 隐藏管理入口或暂停新发布；现有学员继续读取已冻结 Enrollment 和已发布资源。
- Source 解析或题目生成能力不可用时保留 working revision、批次、候选和 Task 结果位置，允许授权人员重试或取消，不伪造成功。
- 数据库 downgrade 仅用于尚未承载正式发布计划的开发/发布回滚环境；已有正式历史时保留表并将新命令置为只读。
