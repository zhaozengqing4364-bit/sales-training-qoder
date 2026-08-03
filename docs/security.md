# 安全、权限与隐私合同

> 状态：新人销售基础训练首发安全合同已实现并通过最终权限、安全、Secret Scan 与跨组织门禁（2026-07-18）。

## 权限矩阵

| 能力 | 学员 | 培训负责人 | 内容编辑 | 训练管理员 | 系统管理员 |
|---|---:|---:|---:|---:|---:|
| 查看/执行本人 Enrollment、Attempt | ✓ | 负责 Team 只读 | — | 组织内运营只读 | 仅显式诊断范围，不默认读取内容 |
| 查看本人 Dossier / 申诉 | ✓ | 负责 Team | — | 组织内只读 | — |
| 作出复核、例外、补练 | — | 负责 Team | — | 可配置规则，不替代负责人决定 | — |
| 编辑 Source/Learning/Question working revision | — | — | ✓ | ✓ | — |
| 审核普通候选题 | — | — | ✓ | ✓ | — |
| 确认红线题/AI 简答题 | — | — | — | ✓ | — |
| 提交本人 Transcript 更正申请 | ✓（本人 Submission） | ✓（负责 Team） | — | ✓（组织范围） | — |
| 批准 Transcript 更正并追加 Revision | — | ✓（负责 Team，`newcomer.audio.transcript.correct`） | — | ✓（组织范围） | — |
| 预览/执行录音重评并追加 ScoreOutcomeVersion | — | ✓（负责 Team，`newcomer.audio.regrade`） | — | ✓（组织范围） | — |
| 编辑 Path/Cohort/ReleasePlan | — | — | — | ✓ | — |
| 发布 Path/内容/题目/评分方案 | — | — | 准备但不可最终发布 | ✓（组织范围） | — |
| Prompt working revision / 预览 | — | — | 仅内容用途且被授权 | ✓（训练用途） | ✓ |
| 高风险 Prompt/模型/Provider 发布 | — | — | — | 仅已授权训练 Prompt | ✓（平台配置） |
| Task/Provider 诊断、密钥与全局策略 | — | — | — | 只读 capability health | ✓ |

角色只是默认能力集合；后端策略必须同时校验 `organization_id`、Team/对象关系、对象状态和具体 capability。System Admin 不因角色自动获得跨组织训练内容；跨组织默认 403/404，Support/诊断必须是显式、限时、审计的授权范围。前端只消费 capability projection，隐藏按钮不是授权。

Transcript 更正拆为 request/approve：学员只能在活动策略允许时发起申请，不能写正式 TranscriptRevision；批准者必须具备 `newcomer.audio.transcript.correct`、命中 Submission 对象范围并引用未过期 preview/impact hash。重评需要 `newcomer.audio.regrade`，修复/队列需要 `newcomer.audio.review`，试听需要 `newcomer.audio.listen` 或本人对象权限；内容编辑、Provider、Task Worker 或 System Admin 角色本身都不隐式获得这些能力。Worker 只执行已经授权并审计的 Regrade command。

## 高风险命令

| 命令 | Preview | Confirm | Audit | Rollback / Compensation |
|---|---|---|---|---|
| ReleasePlan publish | 依赖闭包、diff、影响 Enrollment | impact hash + reason | actor、版本、前后引用 | 恢复上一修订为新 Release；不改历史 Attempt |
| Enrollment revision migration | 活动差异、进行中 Attempt、人数 | preview token + If-Match + reason | from/to revision、影响 | 显式反向迁移；仍保留全部历史 |
| Review exception/decision | 证据、缺口、既有决定 | dossier version + reason | 决定、依据、Actor | 新决定 supersede；不覆盖旧决定 |
| Regrade/transcript correction | 旧新合同、影响档案 | exact revision + reason | 新版本与 lineage | 追加版本；必要时重新打开复核 |
| Prompt/model publication | diff、消费者、校准/预算 | expected revision + reason | 模型/Prompt hash，不记录正文输入 | 回滚已发布修订；正式评分不静默换模 |
| Bulk review/export | 对象数、范围、字段与失败策略 | 二次确认 | 每个对象结果 + 汇总 | 幂等重试失败项；导出短时下载 |

## 数据与 AI 安全

- 所有业务对象、事件和任务携带 `organization_id`；查询必须先施加组织/Team scope。
- 音频、完整转写、评分、申诉属于敏感员工训练数据；读取、下载、导出、重评和人工决定留审计。
- 对象存储只返回短时签名 URL；API 不暴露 storage key。上传校验魔数、解码、时长、大小、静音/削波和恶意内容。
- Provider 输入采用允许清单和最小上下文；Prompt injection 内容作为不可信数据隔离，输出经 Schema/策略校验。
- 日志、事件、任务 payload 不含密钥、token、完整音频/转写、Prompt 正文、Raw AI Response 或敏感个人信息。
- 高风险 AI 建议不自动执行；正式员工结论必须人工确认并保留申诉路径。

## 录音保留与删除

- 浏览器未完成草稿默认保留 7 天，退出登录或超期后在本地删除；服务端确认上传前的可恢复失败不得自动清除草稿。
- 服务端 UploadSession 默认 24 小时；过期/取消会话的 part 由有界、可重试、带 fenced claim 的部署级清理任务删除，会话状态和清理审计保留。
- `finalized` 原始音频、标准化派生音频、TranscriptRevision、QualityReport、ScoreOutcomeVersion、更正/重评/失效历史是正式员工训练证据。首发安全默认是不做无策略的自动物理删除；它们不进入“未完成上传”清理器。
- 组织级归档、法定删除和 erasure 必须由正式 retention policy + 有租约的任务执行，先校验组织/对象范围、申诉与审计保留义务，再以可补偿方式处理引用；策略未发布前禁止临时脚本、单表删除或对象存储生命周期规则单独清除正式 Artifact。
- 具体调度、告警和回滚见 [`setup/foundation-audio-assessment-runbook.md`](setup/foundation-audio-assessment-runbook.md)。
