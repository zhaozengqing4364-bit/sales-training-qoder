# ADR：能力证据、达标档案与人工复核单一权威

- 状态：Accepted
- 日期：2026-07-17
- 风险等级：P1
- 相关 ADR：`2026-07-16-newcomer-foundation-domain-and-modules.md`、`2026-07-16-newcomer-foundation-product-boundary.md`

## 背景

Lesson、Quiz、录音、AI Coach 和异步客户场景录音已经各自产生正式 `ActivityOutcome`，但旧实现仍把达标信息拼成临时报表或操作日志。它无法可靠回答某条结论使用了哪一版路径、哪条证据和哪位复核人，也无法在重评、补练或申诉后安全重开复核。

## 决策

1. `competency_evidence` 是能力目录、Activity 映射和不可变能力证据的唯一写权威；`readiness` 是 Dossier、Snapshot、ReviewDecision、RetrainingAssignment、Appeal、Calibration 和 AI 辅助摘要的唯一写权威。旧 `sales_trainer` Readiness writer 退役，不双写。
2. 首发标准能力稳定为：`product_knowledge`、`customer_understanding`、`needs_discovery`、`value_expression`、`objection_handling`、`process_compliance`、`communication_structure`。名称和说明使用用户语言；定义变化创建新修订，不覆盖历史证据。
3. 每个 `ActivityOutcome` 按冻结 PathRevision 中的能力映射幂等追加 Evidence。重评结果通过 `supersedes_outcome_id` 和 `supersedes_evidence_id` 形成链；无法评分、处理中、低质量、已失效和被替代的证据不进入正式资格判断。
4. 每个 Enrollment 只有一个 Dossier。投影既支持 Outcome 到达后的增量更新，也支持按 Enrollment 全量 rebuild；两者复用同一 Evidence 和 policy 逻辑。正式复核使用冻结 Snapshot，新证据到达时旧 Snapshot 显式 `stale`，不静默改变材料。
5. `approve_foundation_ready` 只允许具备 `readiness.review`、位于 organization/Team 对象范围内且 `is_human=true` 的 Reviewer，在当前有效 Snapshot 上通过带 `If-Match` 和幂等键的命令记录。决定保存 Reviewer、能力与证据引用、理由、私密备注、版本、审计和 Outbox 事件。`exception_approved` 是不同的正式决定：必须先持久化冻结影响预览，再由同一 Reviewer 在短期有效期内携带相同 preview token、impact hash 和明确确认提交；档案版本、Snapshot、理由或引用变化都会拒绝原预览。
6. AI 摘要只保存结构化辅助草稿。事实必须引用当前 Snapshot 的 evidence id；无引用、越界引用、Schema 失败或 Provider 失败均不能阻塞确定性档案和人工复核。学员安全投影不返回原始 AI 草稿、内部风险、证据 lineage 或 Reviewer 私密备注。
7. Reviewer 在 Dossier 内选择已发布 Activity，或快速创建最小补练草稿。新终态 Outcome 必须晚于指派时间才算完成；完成后追加审计并重新投影。申诉不删除原结论，重评结果使相关 Snapshot stale，Reviewer 显式重开。
8. 对外使用 `EvidenceDossierV1` 和版本化复核队列。权限拒绝、跨组织/对象范围拒绝、导出和正式写命令均审计；导出带操作者、时间和“内部培训资料”水印。

## 结果

- 正式达标结论可以追溯到 PathRevision、policy revision、不可变 Evidence、Snapshot 和 Reviewer。
- 重评、失效、补练和申诉不会覆写历史，也不会让旧决定自动漂移。
- 同步 Outcome 投影保持当前事务闭环；幂等事件处理入口和 rebuild 提供恢复与对账路径。
- 管理队列读取聚合后的风险、缺口和等待时间，不要求运营人员查原始表或日志。

## 回滚与降级

- 可暂停新的复核写命令，训练活动和 Outcome 继续保留。
- 可从不可变 Outcome/Evidence rebuild Dossier；错误新 Snapshot 标记 stale，不删除旧 Snapshot 或 Decision。
- 代码回滚前先停用新复核入口；数据库 downgrade 仅用于尚未承载正式决定的开发/发布回滚环境。已有正式数据不得通过 downgrade 删除，应保留表并切换为只读。
- 实时客户语音对练不属于本决策或首发能力映射。
