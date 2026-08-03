# 设计产物审计

审计日期：2026-07-19  
范围：父 PRD、十个子任务 PRD、执行策略、执行顺序与当前事实研究。

## 总体结论

架构方向与当前 Foundation 单一权威一致；审计发现 3 个必须修正项，已全部修正。第二轮按类型、依赖、事务、调用方语义、测试和内部一致性复核后，无剩余硬错误。尚有两项实施期技术选择（PPT 转换实现、外部视频托管策略），已经被限制在内容资产子任务内，不能在合同阶段臆造依赖。

## 第一轮发现与修复

### 🔴 1. Wave 1 依赖描述自相矛盾

- 证据：父任务依赖表明确 1C 依赖 1A、1E 依赖 1C，正文却写“1A～1E 独立推进”。
- 后果：实施时可能在 Source/Scoring 接口未冻结前并行造出不兼容字段。
- 修复：改为 1A/1B 独立，1C/1D 等待 1A 引用接口，1E 等待 1C 评分接口；执行顺序保持 Wave gate。

### 🔴 2. 慢 IO 与事务边界未显式冻结

- 证据：内容任务要求 PPT/媒体处理和外链探测，题库任务要求文件导入/AI，但初稿未说明数据库事务边界。
- 后果：实现可能把转换或 Provider 调用放进 API 事务，长期占用连接并放大失败补偿难度。
- 修复：父/内容/题库 PRD 明确“短事务记录意图与 Outbox → DurableTask 执行慢 IO → 短事务回写结果”。

### 🔴 3. 新题型兼容边界不够明确

- 代码事实：`learning.contracts.QuestionCandidateContent` 当前只允许 single/multiple/true_false/short_answer。
- 后果：若直接改变旧快照或让前端先出现排序/匹配，会造成 Runtime/回放不一致。
- 修复：明确排序/匹配为 additive discriminator，仅新修订使用，旧 Question/Quiz/Attempt 不迁移；Schema、判分、DTO、ViewModel、Runtime 和测试同一子任务完成。

## 七维复核

### 1. 参照对象真实性

- `SourceDocumentRevisionDraft` 确有 file/url/manual，但无 `content_kind`；PRD 将其标为新增扩展，没有冒充现成功能。
- `AudioActivityResourceRevision` 确有 `audio_material/scoring_scheme/scenario` 三类。
- `CoachProfileRevision` 确有版本表；生产创建点主要在 Standard Pack，Authoring 缺口成立。
- 路径封闭联合确为 lesson/quiz/audio_assessment/ai_coach/assignment。
- 前端 Drawer 当前主要快建 LearningUnit/Quiz，后端 options/能力与 UI 支持不完全一致，路径任务目标成立。

### 2. 依赖方向

- 路径只保存其他领域 exact revision ID，Authoring 由 learning/audio_assessment/ai_coach 领域应用服务负责。
- ReleasePlan 继续通过公开资源适配器协调，不允许管理 API 跨域 ORM 写入。
- Legacy 迁移使用只读 adapter，不让 Foundation 业务模块反向依赖 Legacy service。

### 3. 类型字段

- `content_kind`、内容块联合、排序/匹配题型、Profile/Scenario Authoring DTO 均明确为新增合同，要求同切片完成全层对齐。
- 录音资源类型沿用现有表约束；路径资源字段沿用现有 exact revision ID，不发明可执行配置。

### 4. 事务与 IO

- 上传/转换、导入、AI 和外链探测均已明确移出长事务。
- ReleasePlan preview 外部健康检查与最终短事务发布保持分离；失败不移动 active pointer。
- 迁移 apply 使用计划/impact hash/幂等，逐项短写并在 verify 后单独发布。

### 5. 调用方语义

- Source 是原始资料，LearningUnit 是精编呈现，Path 只编排，不把上传等同课程完成。
- AI/Import 产物先进入 Candidate，人工批准只形成 working revision，ReleasePlan 才正式生效。
- 新发布只影响未来 Enrollment，旧 Attempt/Session/Submission 冻结修订。

### 6. 测试即时影响

- 每个子任务包含相关静态、单元、集成和最小浏览器验证；排序/匹配、资源联合与 capability 等签名变化均要求同步调用者测试。
- 只有路径发布闭包、迁移和最终 E2E 允许扩大到完整 Foundation 相关套件；不运行全仓无关测试。

### 7. 产物内部一致性

- 父任务十个子任务与 `task.json.children` 一致。
- 所有子任务包含依赖、可测验收、最小验证、范围外、风险/回滚和统一执行约束。
- 十一个任务的 implement/check context 均已去除示例行并通过 `task.py validate`。
- 现有 `07-16-material-upload-bind-ux` 重叠项已记录为 Wave 0 必须处理的任务治理项，未擅自归档或修改。

## 建议级未决项

- PPT/PPTX 转换优先复用仓库现有 presentation/common-ppt 能力；若无法满足分页预览，再在 1A 内做依赖评估，不在 PRD 预选库。
- 大视频上传与转码是否首批走项目现有对象存储，需在 1A 代码探索中确认；无论实现如何，URL/文件安全、持久任务和失败回退合同不变。

## 审计结论

设计产物可以进入实施准备。当前仅创建任务并保持 `planning`，未启动任何实现任务；建议严格从 Wave 0 开始。

