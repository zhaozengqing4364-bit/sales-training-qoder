# 新人训练路径全闭环：录音回放 / PPT 模板 / 反馈详情

## Goal

新人训练路径目前"讲完没反应"——学员上传录音后看不到完整反馈，管理者看不到学员具体录音内容，前端没有 PPT 模板/材料的统一展示。本任务把新人训练路径做成全闭环：学员讲完能看反馈、管理者能听录音看详情、材料/PPT 模板能统一展示。

## What I already know

### 现状盘点（代码调研）

**音频结果页 `audio/result/[submissionId]/page.tsx`（677 行，已有内容）**
- ✓ 有评分总分环（ScoreRing）+ 通过/未通过标签
- ✓ 有评分维度展示（dimension/label/score/comment 每项反馈）
- ✓ 有评分总结 summary
- ✓ 有改进建议 improvements 列表（带"查看全部 N 条"展开）— **仅 passed===false 时显示**
- ✓ 有转写全文（transcript_text）
- ✓ 有下载语音按钮 + "授权播放"按钮（跳新页放音频，授权端点读文件）
- ✗ **无页面内 `<audio>` 在线回放**（要听录音得点"授权播放"跳走，是 `<a target="_blank">`）
- ✗ 通过的学员看不到 strengths（showImprovements 仅 passed===false 触发；strengths 字段未渲染）
- ✗ 学员视角看一次后，没有"历史我的录音列表"可回看

**材料/学习页 `learn/[unitId]/page.tsx`（159 行）**
- 走 CooChapterReader（COO 图文章节阅读器）
- ✗ **章节阅读页无 PPT 模板/材料下载入口**——学员在"学习"阶段看不到材料

**材料展示现状（分散）**
- ✓ 录音上传页 `audio/[unitId]/page.tsx`（345-357 行）**已渲染 materials[] + 下载/预览**，含 `ppt_deck`/`script`/`example_audio`/`attachment` 全类型，走 `getMaterialVersionFileUrl` 授权下载
- ✗ learn 章节阅读页无材料入口
- 后端 material 体系完整：`material_type` 支持 `ppt_deck`/`script`/`example_audio`/`attachment`（models.py:525/544，schemas.py:13），`SalesTrainerMaterialVersion` 有 storage_key/version/published_at，`getUnitBrief` 返回 `materials[]`
- 真实缺口不是"无 PPT 模板类型"，而是"材料只挂在录音上传页，学员学习阶段看不到"——placement 问题

**管理者看板（/team）+ 详情页（/team/[learnerId]）**
- 详情页展示 journey 进度（关卡分组 + 状态）
- ✗ **无跳到学员录音详情的入口**——管理者看不到学员具体录音、分数、转写、回放
- 管理者无法判断"这个学员为什么没通过、讲得怎么样"

**数据已具备（后端）**
- SalesTrainerAudioSubmission：录音提交记录（含 file_url 等）
- SalesTrainerAudioTranscript：转写文本
- SalesTrainerAudioScoreResult：评分结果（含维度分、总分、passed）
- score_result JSON 含 total_score/passed/dimensions
- 已有授权播放端点（结果页"授权播放"按钮在用）

### 用户的真实诉求（从原话提炼）
1. "上传录音他的详细的录音经理也能听到" → 管理者要能在线听学员录音 + 看详情
2. "有一个详情页里面有录音详细的信息" → 录音详情页（含回放+转写+评分+反馈）
3. "学员应该也有一个详细的信息" → 学员侧也要有完整反馈详情（不只是结果页一次性看完）
4. "新人不可能讲完之后什么反应都没有" → 要有 AI 反馈/改进建议，不只是分数
5. "前端只有一个材料，并没有 PPT 模板" → 要放 PPT 模板/材料到前端
6. "上传录音，那个会分析的界面，弹窗或者界面" → 录音分析要有明确界面/弹窗

## Assumptions（待 brainstorm 验证）
- 录音回放用页面内 `<audio>` 控件 + 授权 URL，不跳走
- AI 反馈从现有 score_result.dimensions 扩展（或加 LLM 总结字段），不重做评分
- PPT 模板作为 material 的一种类型，复用现有材料体系
- 管理者录音详情复用学员结果页 + 权限隔离（training_manager 只能看本部门学员录音）

## Open Questions
- ~~[Blocking] 全闭环 MVP 范围~~ → **已定：B，5 个缺口全进 MVP**
- ~~[Preference] AI 反馈文案来源~~ → **已由代码澄清**：summary/dimensions.comment/improvements 已存在，只补 strengths 渲染
- ~~[Preference] 管理者录音详情：复用 vs 新建~~ → **已由代码澄清**：复用 admin 端点 + 部门权限已就绪
- ~~[Preference] PPT 模板：新类型 vs 独立下载区~~ → **已由代码澄清**：material_type 已支持，真实问题是 placement
- ~~[Preference] 材料入口 placement~~ → **已定：章节阅读页 learn/[unitId] 内联"本关训练材料"区块**
- ~~[Preference] 学员录音历史：放哪~~ → **已定：路径首页 /sales-trainer 加"我的录音"区**

所有 preference 已收敛，进入实现准备。

## Requirements（已收敛）
- R1 录音详情页支持页面内 `<audio>` 在线回放（不跳走，替换现有 `<a target="_blank">` 授权播放跳走）
- R2 补全 AI 反馈展示：**已存在** summary/dimensions.comment/improvements；补 strengths（通过学员也看得到"优点"），让"讲完有反馈"对所有结果都成立
- R3 学员在"学习/训练"阶段能拿到 PPT 模板与材料下载入口：在 learn/[unitId] 章节阅读页内联"本关训练材料"区块，复用录音上传页同款下载/预览组件，不新建 material 类型
- R4 管理者从 /team/[learnerId] 下钻能进学员录音详情页（含回放+评分+反馈），权限隔离本部门
- R5 学员在路径首页 /sales-trainer 能看到"我的录音"区（时间倒序，每次含分数+回看入口），后端补学员侧 list 端点
- R6 各页面覆盖 loading/empty/error/无权限，不泄露工程字段

## Acceptance Criteria（已收敛）
- [ ] AC1 学员上传录音后，结果页能页面内 `<audio>` 播放录音（不跳走）+ 看到完整反馈（总分+维度+comment+strengths+improvements+转写）
- [ ] AC2 通过的学员也能看到 strengths（"优点"区），不再因 passed===true 隐藏反馈
- [ ] AC3 管理者从 /team/[learnerId] 下钻能进学员录音详情页，页面内听录音+看反馈；跨部门学员录音返回 404/无权限
- [ ] AC4 学员在 learn/[unitId] 章节阅读页底部能看到"本关训练材料"区块，可下载/预览 PPT 模板等
- [ ] AC5 学员在 /sales-trainer 路径首页能看到"我的录音"区，按时间倒序列出每次提交+分数+回看入口
- [ ] AC6 各页面覆盖 loading/empty/error/无权限，不泄露工程字段（error_code/trace_id/module_key 原始值等）

## 实现计划（small PRs）

**PR1：录音详情页页面内回放 + 反馈补全（R1+R2）**
- 前端 `audio/result/[submissionId]/page.tsx`：`<a target="_blank">授权播放` 改为页面内 `<audio controls>` + 授权 URL
- 补 strengths 渲染（通过学员也显示"优点"区），showImprovements 不再仅 passed===false
- 单测：回放控件渲染、strengths 渲染、improvements 展开

**PR2：管理者下钻学员录音详情（R4）**
- 前端 `/team/[learnerId]` 详情页：journey 里 audio 模块加"听录音"下钻入口 → 跳学员结果页（带 admin 端点）
- 学员结果页支持 admin 上下文（走 `api.admin.salesTrainer.getAudioSubmission` + admin 文件 URL），复用同页
- 后端权限已就绪（`_team_scope` 部门隔离），只补测试：跨部门 404
- 单测：下钻入口、admin 上下文渲染、跨部门无权限

**PR3：章节阅读页内联训练材料（R3）**
- 前端 `learn/[unitId]/page.tsx`：底部加"本关训练材料"区块，复用 `audio/[unitId]` 同款下载/预览组件
- 拉 `getUnitBrief(unitId).materials`，渲染 ppt_deck/attachment 等
- 单测：材料区块渲染、下载/预览、空态

**PR4：路径首页"我的录音"区 + 后端学员侧 list 端点（R5）**
- 后端：新增学员侧 `GET /sales-trainer/audio-submissions`（按 current_user 过滤，分页）
- 前端 `lib/api/domains/sales-trainer.ts`：加 `listMyAudioSubmissions`
- 前端 `/sales-trainer` 路径首页：加"我的录音"区（时间倒序，分数+回看入口）
- 后端测试：学员只看自己、admin 端不受影响
- 前端单测：录音列表渲染、空态、回看入口

## Definition of Done
- 前端单测覆盖各状态 + 下钻 + 回放
- 后端权限测试覆盖管理者只看本部门学员录音
- lint/typecheck/CI 绿
- 无吞异常/伪造成功

## Out of Scope（暂定，待确认）
- 重新设计评分算法（复用现有 score_result）
- AI 教练对话式反馈（用一次性总结文案，不做多轮对话）
- 重新做材料管理体系（复用现有 material）

## Technical Notes
- 音频结果页：`web/src/app/(dashboard)/sales-trainer/audio/result/[submissionId]/page.tsx`（677 行）
- 材料已渲染处：`web/src/app/(dashboard)/sales-trainer/audio/[unitId]/page.tsx`（345-357 行，下载/预览全类型 material）
- 章节阅读页：`web/src/app/(dashboard)/sales-trainer/learn/[unitId]/page.tsx`（159 行，仅 CooChapterReader）
- 管理者详情页：`web/src/app/(dashboard)/team/[learnerId]/page.tsx`
- 后端模型：SalesTrainerAudioSubmission/Transcript/ScoreResult（models.py:454/611/665）
- 授权播放端点已存在（结果页"授权播放"按钮在用，是 `<a target="_blank">` 跳走）
- score_result JSON 含 summary/dimensions.comment/improvements/strengths/total_score/passed
- 后端 admin 录音端点：`admin_list_audio_submissions`/`admin_get_audio_submission`/`admin_get_audio_submission_file`（api.py:1336/1362/1389），已带 `_require_records_viewer` + `_team_scope` 部门隔离
- 后端学员侧端点：`get_my_audio_submission`（按 submission_id 单条，api.py:738），**无"我的录音列表"端点**——R5 需补 list 端点（学员侧或复用 admin + 当前用户过滤）
- material 体系：`material_type` = `ppt_deck`/`script`/`example_audio`/`attachment`（models.py:525/544，schemas.py:13），`getUnitBrief` 返回 `materials[]`
- 前端 admin 录音 API：`api.admin.salesTrainer.listAudioSubmissions`/`getAudioSubmission`/`getAudioSubmissionFileUrl`（sales-trainer.ts:527/542/562）

## 待 brainstorm 聚焦的问题
4 个缺口（录音回放 / AI反馈 / PPT模板 / 管理者录音详情）+ 学员历史回看，哪个进 MVP？哪个延后？
