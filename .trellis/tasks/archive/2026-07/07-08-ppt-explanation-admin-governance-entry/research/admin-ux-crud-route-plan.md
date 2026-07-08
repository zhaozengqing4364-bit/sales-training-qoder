# Research: admin-ux-crud-route-plan

- Query: 审查 `/admin/sales-trainer` 新人训练后台 IA/UX/CRUD 路由规划，重点区分“录音评测能力”和 PPT 讲解、公司产品 Demo 等具体训练场景；覆盖 module-nav、workbench、materials、paths、score-standards、articles、questions、papers、ai-coach、records/readiness/audio/score-results/settings/logs。
- Scope: internal
- Date: 2026-07-08

## Findings

### 结论先行

当前后台最大问题不是缺少 PPT 讲解入口，而是把“业务对象、能力配置、训练场景、运营记录、系统诊断”平铺成同一层导航。`/admin/sales-trainer` 的侧栏由 `SALES_TRAINER_ADMIN_ROUTES` 直接暴露 16 个入口，包括路径配置、AI 教练、题库、评分标准、材料库、训练记录、达标验收、录音记录、评分结果、分析、配置、日志（`web/src/lib/sales-trainer/routes.ts:46`-`143`），工作台又只取每个 context group 的第一个链接生成卡片（`web/src/lib/sales-trainer/routes.ts:450`-`452`），导致用户看见的是资源表和系统能力，而不是“我要治理新人训练任务”的任务结构。

“PPT 讲解录音”不应成为最高层级。它应是一个训练任务场景，和“公司产品 Demo”“电梯陈述”“商务礼仪/学习专题”并列；“录音评测能力”应是可复用能力层，负责音频上传、转写、评分标准、模型/Prompt 版本、重评、审计和服务健康。当前代码把 `ppt_explanation` 写在路径配置中心的模块定义里（`web/src/lib/sales-trainer/config-center-definitions.ts:3`-`37`），又把录音评分标准作为独立导航（`web/src/lib/sales-trainer/routes.ts:75`-`81`），但缺少“训练任务治理页”把场景、材料、评分标准、完成规则和发布状态组织在一起。

推荐导航从“资源平铺”改成五组：

1. **工作台**：风险、待处理发布、缺失配置、待复核记录，不再按资源表堆卡片。
2. **训练任务**：PPT 讲解、公司产品 Demo、商务礼仪学习、产品知识小测、电梯陈述、实时对练占位；每个任务页绑定材料、题目/考卷、评分标准、完成规则、发布版本。
3. **内容与能力库**：材料库、题库、考卷、学习专题、录音评测标准库、AI 教练策略库。这里管理可复用资产，不代表具体训练任务。
4. **学员记录与复核**：训练记录、达标验收、录音记录、评分结果、做题详情统一收束为记录中心的列表、详情、筛选、重评和复核动作。
5. **系统治理**：配置健康、路径高级编排、Journey 分析、操作日志。这里给管理员看健康、审计、发布和诊断，不应成为普通内容运营主路径。

### Files found

- `.trellis/workflow.md`：Trellis 工作流说明，确认本次只写 research 输出。
- `.trellis/spec/frontend/admin-console-patterns.md`：后台页面契约，明确 index/new/import/detail/edit/subresource 路由边界、modal/drawer/page 规则、策略中心与资产页边界。
- `.trellis/spec/frontend/component-guidelines.md`：后台组件状态和可访问性要求。
- `.trellis/spec/frontend/directory-structure.md`：前端目录、API facade、feature 边界要求。
- `.trellis/spec/frontend/state-management.md`：页面本地状态、服务端数据、副作用边界。
- `.trellis/spec/frontend/type-safety.md`：DTO -> Domain -> ViewModel -> UI 映射要求。
- `.trellis/spec/backend/sales-trainer-learning-topic-governance.md`：学习专题与必修路径解耦，修订只影响未来学员。
- `.trellis/spec/backend/prompt-template-governance.md`：Prompt、模型、版本和工具调用治理边界。
- `docs/api-contract/sales-trainer.md`：新人训练路径 API 契约，确认 PPT 演练是 `audio.purpose="ppt_pitch"` 的场景绑定，提交时冻结材料/任务/评分快照。
- `web/src/app/admin/sales-trainer/AGENTS.md`：局部前端治理规则。
- `web/src/lib/sales-trainer/routes.ts`：后台主导航、上下文导航和能力映射。
- `web/src/components/admin/sales-trainer/module-nav.tsx`：模块内横向导航。
- `web/src/app/admin/sales-trainer/page.tsx`：新人训练路径工作台。
- `web/src/app/admin/sales-trainer/units/**/page.tsx`：训练单元列表、新建、编辑。
- `web/src/app/admin/sales-trainer/paths/page.tsx` 与 `web/src/components/admin/sales-trainer/path-config-*.tsx`：路径配置中心和音频任务绑定。
- `web/src/app/admin/sales-trainer/materials/page.tsx`：材料库单页 CRUD、版本上传、发布。
- `web/src/app/admin/sales-trainer/score-standards/**/page.tsx`：录音评分标准库列表、新建、编辑。
- `web/src/app/admin/sales-trainer/score-prompts/**/page.tsx`：旧评分 Prompt 路由，当前重定向到 score-standards。
- `web/src/app/admin/sales-trainer/articles/**/page.tsx`：学习专题、商务礼仪、导入、能力点。
- `web/src/app/admin/sales-trainer/questions/**/page.tsx`：题库、AI 草稿、分类、预览、新建、编辑。
- `web/src/app/admin/sales-trainer/papers/**/page.tsx`：考卷列表、新建、编辑。
- `web/src/app/admin/sales-trainer/ai-coach/page.tsx`：AI 教练策略配置。
- `web/src/app/admin/sales-trainer/training-records/**/page.tsx`：统一训练记录列表和记录详情。
- `web/src/app/admin/sales-trainer/audio-submissions/**/page.tsx`：录音提交列表和详情。
- `web/src/app/admin/sales-trainer/score-results/page.tsx`：做题/录音评分结果。
- `web/src/app/admin/sales-trainer/quiz-attempts/[attemptId]/page.tsx`：做题结果详情。
- `web/src/app/admin/sales-trainer/readiness/**/page.tsx`：达标验收工作台和学员验收详情。
- `web/src/app/admin/sales-trainer/analytics/page.tsx`：Journey Analytics。
- `web/src/app/admin/sales-trainer/settings/page.tsx`：存储、ASR、评分服务、策略诊断。
- `web/src/app/admin/sales-trainer/operation-logs/page.tsx`：操作日志。

### Related specs

- 后台 index 页只能放浏览、筛选、批量、安全短动作；新建/编辑/导入/复杂发布应使用独立路由，不能塞进列表页。
- 策略中心管理全局规则；资产页只绑定或引用策略。录音评测标准、AI Coach Prompt、模型参数属于能力/策略层，不应被 PPT 场景页拥有。
- 业务页面按用户任务组织，不按数据库对象组织。普通后台不应默认展示 `module_key`、`training_stage`、`Prompt`、`traceId`、raw JSON、内部 ID 或后端枚举。
- 缺配置时应上下文内完成：当前任务页可选择已有对象、快速新建最小对象、自动关联、稍后补充，并保留权限、去重、审计和失败反馈。

### Code patterns

#### 导航与工作台

- `SALES_TRAINER_ADMIN_ROUTES` 直接定义 16 个同级入口（`web/src/lib/sales-trainer/routes.ts:46`-`143`），其中内容、记录、设置、日志混在一层。
- 能力映射将 `manage_content` 同时赋给工作台、AI 教练、评分标准、文章、考卷、材料（`web/src/lib/sales-trainer/routes.ts:172`-`207`），权限可用，但信息架构没有区分“资产库”和“能力治理”。
- 上下文导航分组已经存在，但工作台只取每组第一个链接生成入口卡（`web/src/lib/sales-trainer/routes.ts:298`-`448`、`450`-`452`），所以用户看不到分组内完整任务边界。
- `SalesTrainerAdminModuleNav` 在少于 2 个可见项时直接返回 null（`web/src/components/admin/sales-trainer/module-nav.tsx:94`-`101`），单页区域缺少“我在哪个后台区域”的局部导航提示。
- 工作台页面标题是“新人训练路径工作台”，但卡片只展示图标和 label，没有说明每个入口解决什么治理任务（`web/src/app/admin/sales-trainer/page.tsx:117`-`123`、`267`-`278`）。

治理建议：

- 保留现有 capability fail-closed 逻辑，但 route metadata 增加 `section`、`intent`、`audience`、`primaryObject`、`riskLevel`、`showInSidebar`、`showInWorkbench`。
- 侧栏只放一级分组和核心入口；工作台卡片改为“待办/风险/配置缺口/近期发布/复核队列”，不要把每张资源表变成一个主入口。
- module-nav 支持分组说明和单页 breadcrumb；单页区域即使只有一个 tab，也可显示区域标题、返回上级分组和关联入口。

#### 录音评测能力 vs 训练场景

当前代码已经暴露出能力和场景的混合：

- `ppt_explanation` 被定义为路径模块，标题是“PPT 讲解录音”，描述直接绑定 PPT 材料和录音评分（`web/src/lib/sales-trainer/config-center-definitions.ts:3`-`37`）。
- 可编辑音频模块只有 `ppt_explanation` 和 `elevator_pitch`（`web/src/lib/sales-trainer/path-config-editing.ts:11`），说明“录音评测”本身不是单一场景。
- 音频绑定编辑器按 `ppt_explanation` 推导 `purpose="ppt_pitch"`，否则是 `elevator_pitch`（`web/src/components/admin/sales-trainer/path-config-audio-binding-editor.tsx:33`-`37`），这会让未来“公司产品 Demo”继续靠硬编码分支扩展。
- 缺材料或评分标准时，当前引导用户去材料库和评分标准页补资源（`web/src/components/admin/sales-trainer/path-config-audio-binding-editor.tsx:42`-`59`），没有在当前训练任务上下文里就地选择/快速新建/自动关联。

推荐模型：

- **录音评测能力**：共享能力，管理上传、ASR、转写、评分标准库、模型/Prompt 版本、重评、操作日志、服务健康。推荐入口名：`录音评测标准库` 或 `录音评测能力`。
- **PPT 讲解**：训练任务场景，绑定 PPT 材料、任务说明、评分标准、完成门槛、发布版本。推荐路由：`/admin/sales-trainer/training-tasks/ppt-explanation`。
- **公司产品 Demo**：训练任务场景，绑定产品资料、Demo 脚本/讲解要点、同一套或专门的录音评分标准、完成门槛。推荐路由：`/admin/sales-trainer/training-tasks/company-product-demo`。
- **电梯陈述/实时对练**：同属训练任务场景，可复用录音或对话评测能力。

场景页不能拥有通用评分引擎；它只引用能力层的评分标准、模型和服务健康。能力层不能被命名成 PPT，因为同一能力会服务多个训练场景。

### 每页意图边界与 CRUD 审查

| 当前路由 | 当前意图边界 | CRUD 清晰度 | 处理建议 | Modal / Drawer / Page 规则 |
| --- | --- | --- | --- | --- |
| `/admin/sales-trainer` | 指标、风险学员、弱项、建议、入口卡片（`page.tsx:151`-`278`） | 非 CRUD；导航意图弱 | 保留并改为“治理工作台”；入口按任务/待办组织 | 页面；卡片跳转到任务、记录、系统治理 |
| `module-nav` | 按当前路径显示局部横向导航（`module-nav.tsx:54`-`132`） | 非 CRUD | 保留，但从“链接列表”升级为分组导航/breadcrumb | 页面内导航；不要承载业务动作 |
| `/units` | 训练单元列表，发布/归档/历史在列表内（`units/page.tsx:185`-`371`） | 列表、新建、编辑清晰；历史略重 | 保留，改名“训练单元”；历史/回滚以后拆到详情或 revisions 子路由 | confirm modal 发布/归档；历史详情用 drawer/page |
| `/units/new`、`/units/[unitId]/edit` | 专用新建/编辑页（`units/new/page.tsx:116`-`155`、`units/[unitId]/edit/page.tsx:130`-`165`） | 清晰 | 保留 | 页面 |
| `/paths` | 路径配置中心，包含四阶段配置、发布、历史、诊断、预览（`paths/page.tsx:77`-`134`、`path-config-center.tsx:79`-`197`） | 不是普通 CRUD，是高级编排 | 改名“高级路径编排/发布中心”；从主工作台降级到系统治理或训练任务发布入口 | 页面；发布预览用 page/drawer；缺配置用当前任务 drawer 快速补 |
| `/materials` | 材料创建、列表、详情、版本上传、发布全在一页（`materials/page.tsx:105`-`175`、`207`-`233`） | 不清晰，CRUD 和版本发布混合 | 拆分：`/materials`、`/materials/new`、`/materials/[id]`、`/materials/[id]/versions/new`、`/publish-preview` | 快速创建材料 shell 可 modal；上传/发布必须 page；选择材料用 drawer |
| `/score-standards` | 录音评分标准列表、发布，默认展示 system prompt 摘要（`score-standards/page.tsx:105`-`204`） | 路由清晰，但默认信息过技术 | 保留并改名“录音评测标准库”；隐藏 Prompt 文本，展示评分维度/适用场景/版本 | confirm modal 发布；详情/编辑 page；技术字段 advanced drawer |
| `/score-standards/new`、`/[id]/edit` | 专用评分标准表单，保存生成待发布修订（`score-standards/[id]/edit/page.tsx:102`-`140`） | 清晰 | 保留；表单改成结构化 rubric 优先，Prompt/schema 后置 | 页面 |
| `/score-prompts/**` | 旧路由重定向到评分标准（`score-prompts/page.tsx:1`-`6`） | 已合并 | 保留兼容重定向，隐藏导航 | 无 |
| `/articles` | 学习专题/文章入口，同时可生成商务礼仪草稿并发布（`articles/page.tsx:114`-`168`、`190`-`260`） | 混合 topic、article、生成、发布 | 改名“学习专题”；列表只展示专题及状态，生成/发布进入专题详情 | 生成草稿 page/drawer；短确认 modal |
| `/articles/business-etiquette` | 商务礼仪专题管理，创建文章、绑定、生成、预览发布、历史、回滚全在一页（`articles/business-etiquette/page.tsx:101`-`178`、`265`-`435`） | 过重 | 拆成专题详情、内容绑定、AI 生成、发布历史；该专题不应借 active path 文案解释 | 选择/绑定已有内容 drawer；生成和发布 preview page；回滚 confirm modal |
| `/articles/import` | 训练包导入、影响预览、发布（`articles/import/page.tsx:132`-`198`、`244`-`580`） | 专用导入页清晰，但文案有 key/revision | 保留为“内容导入”；隐藏 training_pack_key、working revision 等内部名 | 页面；影响预览 page；发布 confirm modal |
| `/articles/capabilities` | 商务礼仪能力点、JSON 规则、章节绑定、发布/归档（`articles/capabilities/page.tsx:199`-`333`、`381`-`585`） | 能力点 CRUD 与规则 JSON、章节绑定混合 | 拆为“能力点库”“掌握规则”“章节绑定”tab/subroute；隐藏 capability_key 默认展示 | 小字段能力点 modal/drawer；规则编辑 page |
| `/questions` | 正式题库列表，去 AI 草稿、预览、新建（`questions/page.tsx:184`-`288`） | 较清晰 | 保留，改名“题库” | 列表 page；发布/归档 confirm modal |
| `/questions/new`、`/[questionId]/edit` | 专用题目表单；简答题含 AI 评分配置、模型、Prompt（`question-form.tsx:461`-`575`） | CRUD 清晰，策略配置过深 | 保留；AI 评分配置移入高级策略区或评分策略库 | 页面；高级配置 drawer/accordion，默认收起 |
| `/questions/drafts` | AI 出题生成、队列、审核、编辑、批准/拒绝（`questions/drafts/page.tsx:255`-`394`、`425`-`807`） | 生成、审核、题库入库混合 | 拆成“生成任务”和“草稿审核队列”；隐藏 Prompt 模板 ID、model JSON、hash | 生成 page；单条审核 drawer；批量批准 confirm modal |
| `/questions/categories` | 分类列表与新增（`questions/categories/page.tsx:106`-`175`） | 小型 CRUD 可接受 | 保留，可改为题库设置页或 modal | <=4 字段可 modal；列表 page |
| `/questions/quiz-preview` | 测验预览与诊断（`questions/quiz-preview/page.tsx:185`-`200`） | 非 CRUD，清晰 | 保留为“预览”；能力 key 显示名映射 | 页面 |
| `/papers` | 商务技巧考卷列表、发布、归档、历史/回滚（`papers/page.tsx:173`-`357`） | 列表、新建、编辑清晰；历史偏重 | 保留，改名“小测/考卷”；历史以后拆详情或 revisions | confirm modal；历史 drawer/page |
| `/papers/new`、`/[paperId]/edit` | 专用考卷表单和题目选择（`papers/new/page.tsx:137`-`193`、`papers/[paperId]/edit/page.tsx:159`-`227`） | 清晰 | 保留 | 页面 |
| `/ai-coach` | 单页管理 AI 教练模式、事件类型、恢复文案、模型/Prompt 绑定、发布（`ai-coach/page.tsx:760`-`807`、`941`-`1398`） | 过重，是策略 God page | 拆为“AI 教练策略总览/交互规则/恢复话术/模型与 Prompt/发布历史/诊断”；隐藏 prompt_contract_hash 等 | 高风险策略 page；短文案可 drawer；发布 preview page |
| `/training-records` | 统一训练记录；描述已说替代 audio/score results（`training-records/page.tsx:427`-`581`） | 作为记录 hub 清晰；筛选字段过内部 | 提升为记录中心主入口；`audio-submissions`、`score-results` 并入 tab/subroute | 页面；筛选用业务标签；详情 page |
| `/training-records/[recordType]/[recordId]` | 记录详情、快照、重评/补救、AI Coach 快照、raw record（`training-records/[recordType]/[recordId]/page.tsx:501`-`660`） | 详情清晰，但默认诊断过多 | 保留；raw JSON/trace/prompt 放高级诊断 | 页面；诊断 drawer 默认收起 |
| `/audio-submissions` | 录音提交运维列表（`audio-submissions/page.tsx:58`-`132`） | 和训练记录重复 | 合并/降级到 `/training-records/audio`；不做顶级导航 | 列表 page，作为记录中心 tab |
| `/audio-submissions/[submissionId]` | 录音详情、播放、转写/评分、快照、重评（`audio-submissions/[submissionId]/page.tsx:142`-`296`） | 详情有价值 | 保留为记录详情子类型，入口由记录中心进入 | 页面；重评 confirm/preview drawer |
| `/score-results` | 做题结果和录音评分结果两块列表（`score-results/page.tsx:201`-`435`） | 和训练记录重复；技术字段明显 | 合并/降级到 `/training-records/results`；默认隐藏 model/prompt/submission_id | 页面或记录中心 tab |
| `/quiz-attempts/[attemptId]` | 做题结果详情、答案、解析、重评（`quiz-attempts/[attemptId]/page.tsx:163`-`310`） | 清晰 | 保留为记录详情；backHref 应回记录中心/结果 tab | 页面 |
| `/readiness` | 达标验收队列和指标（`readiness/page.tsx:250`-`333`） | 清晰 | 保留为“达标复核”；归入学员记录与复核 | 页面 |
| `/readiness/[learnerId]` | 学员验收 dossier、证据、复核决策（`readiness/[learnerId]/page.tsx:394`-`820`） | 清晰，符合上下文内完成 | 保留；继续隐藏技术诊断 | 页面；复核表单可在详情页内完成 |
| `/analytics` | Journey Analytics，漏斗、模块、弱项、风险学员（`analytics/page.tsx:893`-`1297`） | 非 CRUD，诊断/业务混合 | 改名“训练路径分析”；默认用业务语言，诊断字段放 advanced | 页面；风险学员跳记录中心 |
| `/settings` | 存储、ASR、评分服务、上传限制、阶段策略、诊断（`settings/page.tsx:90`-`179`） | 非 CRUD，健康诊断清晰 | 改名“配置健康”；保留系统治理分组 | 页面；打开策略治理跳转对应策略页 |
| `/operation-logs` | 审计日志，原始数据可展开（`operation-logs/page.tsx:124`-`181`） | 清晰 | 保留；作为系统治理底层入口，从发布/回滚动作关联过去 | 页面；raw metadata 继续默认收起 |

### CRUD 与页面拆分规则

建议按以下稳定路由约束治理：

- `/{resource}`：只做列表、筛选、批量安全动作、短确认动作。
- `/{resource}/new`：创建主对象。需要绑定多个资产、上传文件、AI 生成、发布预览时必须独立页面。
- `/{resource}/import`：导入必须独立页面，先解析/预览影响，再发布。
- `/{resource}/[id]`：详情/只读/关联资产/版本概览。
- `/{resource}/[id]/edit`：编辑主对象；发布后编辑生成待发布修订。
- `/{resource}/[id]/versions`、`/{resource}/[id]/history`：版本、回滚、发布历史。
- `/{resource}/[id]/diagnostics` 或 advanced drawer：Prompt、trace、raw JSON、内部 key、模型 hash、后端 fallback。

modal/drawer/page 使用规则：

- **Modal**：发布、归档、回滚、删除、重评确认；<=4 字段的快速新建壳对象；无复杂依赖的分类新增。
- **Drawer**：从当前训练任务选择材料/评分标准/题目；预览候选对象；展示当前场景缺失配置的就地修复动作；单条 AI 草稿审核。
- **Page**：材料上传、版本发布、训练包导入、AI 生成、评分标准编辑、AI Coach 策略、路径发布、考卷编辑、记录详情、重评预览、高风险操作。

### 推荐导航方案

#### 一级导航

1. **新人训练工作台**
   - `/admin/sales-trainer`
   - 展示：待发布、缺失材料、缺失评分标准、待复核、失败重试、风险学员。

2. **训练任务**
   - `/admin/sales-trainer/training-tasks`
   - `/admin/sales-trainer/training-tasks/ppt-explanation`：PPT 讲解。
   - `/admin/sales-trainer/training-tasks/company-product-demo`：公司产品 Demo。
   - `/admin/sales-trainer/training-tasks/elevator-pitch`：电梯陈述。
   - `/admin/sales-trainer/training-tasks/business-etiquette`：商务礼仪学习。
   - 任务页内展示：目标人群、任务说明、绑定材料、评分/考核方式、完成规则、发布版本、缺失项修复。

3. **内容与能力库**
   - `/admin/sales-trainer/materials`：材料库。
   - `/admin/sales-trainer/questions`：题库。
   - `/admin/sales-trainer/papers`：小测/考卷。
   - `/admin/sales-trainer/articles`：学习专题。
   - `/admin/sales-trainer/audio-assessment` 或继续 `/score-standards`：录音评测标准库。
   - `/admin/sales-trainer/ai-coach`：AI 教练策略库。

4. **学员记录与复核**
   - `/admin/sales-trainer/training-records`：记录中心。
   - `/admin/sales-trainer/training-records/audio`：录音记录 tab/subroute。
   - `/admin/sales-trainer/training-records/results`：评分结果 tab/subroute。
   - `/admin/sales-trainer/readiness`：达标复核。

5. **系统治理**
   - `/admin/sales-trainer/paths`：高级路径编排/发布中心。
   - `/admin/sales-trainer/analytics`：训练路径分析。
   - `/admin/sales-trainer/settings`：配置健康。
   - `/admin/sales-trainer/operation-logs`：操作日志。

#### 二级页面命名建议

- `PPT 讲解录音` 改为 `PPT 讲解`。录音只是完成方式，不是业务任务名。
- `公司产品 Demo` 新增为训练任务场景，和 PPT 讲解同级。
- `录音评分标准` 改为 `录音评测标准库`，强调能力库和复用。
- `路径配置` 改为 `高级路径编排` 或 `发布中心`，避免普通运营误以为所有配置都必须从这里开始。
- `学习文章` 改为 `学习专题`，文章是专题下内容资产。
- `商务技巧考卷管理` 改为 `小测/考卷`，按学员体验命名。
- `学员录音`、`评分结果` 从一级导航移除，进入记录中心。
- `Journey Analytics` 改为 `训练路径分析`，内部 Journey 名称放诊断说明。

### 页面级优先级

第一阶段应先改 IA，不急着改业务模型：

1. 新增“训练任务”分组和任务详情信息架构，把 `ppt_explanation` 从路径配置中心提升为任务页，把 `company-product-demo` 预留为同级任务页。
2. 将 `audio-submissions`、`score-results` 从一级导航降级到记录中心 tab/subroute，保留老路由重定向或兼容入口。
3. 将 `materials` 拆出专用新建、详情、版本上传、发布预览路由；这是当前最明显的 CRUD 混杂页。
4. 将 `score-standards` 命名和默认展示改成“评分维度/适用场景/版本状态”，Prompt 仅 advanced。
5. 将 `ai-coach` 拆分或至少按 tab 分区，避免一个页面承载模式、事件、话术、Prompt、发布全部治理。
6. 将 `articles/business-etiquette` 和 `articles/capabilities` 从“全量治理单页”拆成专题详情、能力点库、规则/章节绑定。

第二阶段再做深层策略：

1. 统一任务场景 schema：task key、display name、task type、required assets、assessment capability、completion rule、publish revision。
2. 把 `purpose` 从 `ppt_pitch`/`elevator_pitch` 硬编码分支扩展为可配置场景绑定。
3. 把材料、评分标准、考卷、学习专题的选择和快速新建嵌入任务页 drawer，满足上下文内完成原则。
4. 建立高级诊断权限层：raw JSON、trace、Prompt hash、module_key、fallback_reason 不在默认运营视图中出现。

### External references

- 未使用外部资料。本审查依据仓库 CodeGraph 输出、Trellis/项目规范、API 契约和本地源码。

## Caveats / Not Found

- 本次只读源码并写研究文档，没有修改产品代码、没有运行前端页面、没有做浏览器视觉验证。
- `python3 ./.trellis/scripts/task.py current --source` 返回当前任务为空；用户明确给出了任务目录，因此研究文件写入用户指定的 task research 目录。
- 未发现现有 `/admin/sales-trainer/training-tasks` 或 `/admin/sales-trainer/company-product-demo` 路由；“公司产品 Demo”目前只能作为推荐场景入口规划。
- 未发现专门的“录音评测能力”顶层路由；现有能力分散在 `score-standards`、`settings`、`audio-submissions`、`score-results`、`paths` 的音频绑定中。
- `score-prompts` 旧路由已重定向到 `score-standards`，不应再作为信息架构入口。
