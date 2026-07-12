# 新人训练活动编排 API 契约

> 状态：已冻结（2026-07-12）
> 权威模型：`TrainingPath → Phase → Module → Activity`

本文是新人训练路径的当前唯一契约。旧的固定模块键、学习专题矩阵、场景 slug、V1/V2 双轨及前端聚合约定均已废弃。

## 核心规则

- 路径配置只保存声明式业务数据，不得保存组件名、路由、URL、脚本或网络请求。
- 活动类型是封闭集合：`lesson`、`quiz`、`audio_assessment`、`realtime_roleplay`、`ai_coach`、`assignment`。
- 产品名、PPT、Demo、课程主题只是管理员录入的标题和资源，不是代码分支。
- 发布生成不可变 revision；学员首次读取 Journey 时创建 enrollment 并固定 `path_revision_id`。
- attempt 冻结活动、资源 revision、评分结果和外部会话绑定；后续发布不得改写历史。
- 所有写入以后端权限、对象范围、幂等键、并发版本、审计和明确错误为准。

## 管理端

基础前缀：`/api/v1/admin/newcomer-training/path`

| 方法 | 路径 | 语义 |
|---|---|---|
| GET | `/` | 返回工作草稿、当前发布 revision、校验结果和资源选项 |
| PUT | `/draft` | 保存完整声明式草稿；请求含 `payload`、`reason` |
| DELETE | `/draft` | 放弃工作草稿 |
| POST | `/validate` | 校验图结构、依赖、资源发布状态和闭环条件 |
| POST | `/publish` | 以不可变 revision 发布；请求含变更说明 |
| GET | `/revisions` | 查询历史 revision |
| POST | `/revisions/{revision_id}/restore` | 从历史快照生成新工作草稿 |
| GET | `/activity-types` | 返回六类活动的受信任描述符 |
| GET | `/coach-profiles` | 返回可绑定的已治理 AI Coach Profile |
| GET/POST | `/scoring-rubrics` | 查询或就地创建录音评分标准 |

团队投影前缀：`/api/v1/admin/newcomer-training`

| 方法 | 路径 | 语义 |
|---|---|---|
| GET | `/journeys` | 按对象权限和部门范围分页读取团队 Journey |
| GET | `/journeys/{learner_id}` | 读取指定学员固定 revision 的 Journey |
| GET | `/readiness/workbench` | 达标工作台 |
| GET | `/readiness/dossiers/{learner_id}` | 达标档案 |

资源快速新建复用现有 LearningContent、ExamPaper、材料版本和审计 API。创建后必须发布并自动绑定当前活动，不要求管理员离开编辑器。

## 学员端

基础前缀：`/api/v1/newcomer-training`

| 方法 | 路径 | 语义 |
|---|---|---|
| GET | `/journey` | 返回固定 revision 的阶段/模块/活动进度和唯一主要下一步 |
| GET | `/modules/{module_id}` | 返回模块详情 |
| GET | `/activities/{activity_id}` | 返回服务端可信活动详情和 Runner 描述符 |
| POST | `/activities/{activity_id}/start` | 以 `client_token` 幂等启动活动 |
| POST | `/activities/{activity_id}/lesson/confirm` | 确认学习章节完成 |
| POST | `/activities/{activity_id}/quiz/attempts` | 提交冻结试卷 revision 的答卷 |
| POST | `/activities/{activity_id}/audio/submissions` | 提交冻结材料与评分标准的录音 |
| POST | `/activities/{activity_id}/realtime/sessions` | 启动冻结 StepAudio/runtime binding 的会话 |
| POST | `/activities/{activity_id}/ai-coach/sessions` | 启动 AI Coach 会话 |
| POST | `/activities/{activity_id}/ai-coach/sessions/{session_id}/turns` | 提交幂等对话轮次 |
| POST | `/activities/{activity_id}/ai-coach/sessions/{session_id}/turns/stream` | SSE 流式返回对话轮次 |
| POST | `/activities/{activity_id}/assignments` | 提交文本或文件作业 |

## 错误与安全

错误使用统一 envelope 和稳定错误码。非法类型、缺失资源、资源未发布、依赖未满足、对象越权、revision 冲突及外部 Provider 不可用均 fail-closed；不得返回伪成功或从旧配置回填。

客户端只根据后端返回的活动类型进入本地封闭 Runner 注册表。配置中的未知字段由严格 schema 拒绝，敏感密钥不进入 payload、响应、日志或审计元数据。

## 兼容性

本次为未发布原型的直接替换。旧 learner/admin 路由、固定模块键和配置中心权威没有兼容期、重定向或适配层。成熟资源、评分、录音、AI Coach、StepAudio、训练记录和达标服务继续复用，但由 `activity_id + path_revision_id` 关联。
