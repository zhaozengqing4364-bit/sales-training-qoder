# 修复详情页 key 重复与重设计模块展示清晰度

## Goal

学员详情页 `/team/[learnerId]` 有两个问题：①React key 重复（business_skills 出现2次导致 console 报错）②模块展示不清晰，管理者看不出"谁学到哪、卡在哪、下一步做什么"。

## What I already know

### 问题1：key 重复根因
journey.modules 里 `business_skills` 出现两次：
- `order=2 key=business_skills kind=quiz_attempt type=article_exam title=第2关：商务技巧`
- `order=2 key=business_skills kind=ai_coach type=ai_coach title=第2关：商务技巧 AI Coach`

业务设计：商务技巧关包含「文章做题」+「AI教练」两部分，共享 module_key 但 kind 不同。
现详情页 `key={module.module_key}` → 两个 business_skills key 冲突。
看板页（team/page.tsx）用 learner_id 做 key 不受影响，只详情页有此 bug。

### 问题2：不清晰现状
现 ModuleCard（page.tsx:201-232）每个 module 一行 GlassCard：
- 标题 + "需关注"badge
- "下一步：xxx" 小字
- 右侧：stage_label（未开始/训练中等）+ passed_label（通过/未通过）
- 底部：成绩 数字

问题：
- 5 个模块平铺，无关卡分组，看不出第几关
- 同关卡的做题+AI教练分成两张独立卡，看不出它们属同一关
- 信息扁平，管理者要逐行读才知道状态
- 没有突出"卡关/待辅导"的视觉重点
- 成绩对未开始模块显示空，信息密度低

### 数据可用字段（每个 module）
module_key/title/display_name/kind(quiz_attempt|ai_coach|audio_submission|realtime_roleplay)/
module_type/article_exam/order_index/status/stage/passed(true|false|null)/
score/max_score/required/completion_satisfied/locked/block_reason/
next_action{action_key,label,target_path,disabled}/latest_outcome/outcome_history

## Requirements

- R1 修复 key 重复：用唯一字段组合做 React key（如 `${order_index}-${kind}` 或 `${module_key}-${kind}`）
- R2 重设计模块展示，让管理者一眼看懂：
  - 按关卡分组（第1关/第2关...），同关卡多部分归到一组
  - 每个模块状态用图标/颜色直观区分
  - 突出卡关/待辅导
  - 清晰展示"下一步该做什么"
- R3 不泄露工程字段（module_key/kind 等不进 UI 文本）
- R4 保持现有状态覆盖（loading/empty/error/无权限/未找到）

## Acceptance Criteria

- [ ] AC1 无 React key 重复 console 报错
- [ ] AC2 模块按关卡分组展示，同关卡的多部分视觉归组
- [ ] AC3 每个模块状态一目了然（图标/颜色区分未开始/进行中/已通过/未通过）
- [ ] AC4 管理者能在 3 秒内知道：学员学到第几关、卡在哪、下一步做什么
- [ ] AC5 不泄露工程字段

## Out of Scope

- 改后端 journey 数据结构（module_key 重复是业务设计，前端适配）
- 看板页（team/page.tsx）改动（本次只改详情页）

## Technical Approach

方案 A：关卡分组布局。

### 实现要点
1. **修 key 重复**：React key 改用 `${order_index}-${kind}`（同关内 kind 唯一），不再用 module_key
2. **按关卡分组**：modules 按 order_index 分组，每组渲染一个"关卡区块"
   - 关卡头：第N关 + 关卡标题 + 关卡整体状态（如"进行中"取该关所有模块里最靠前的状态）+ 该关下一步
   - 关卡体：同关的多部分（做题/AI教练）作为子项列出，每项显示 part 标题 + 状态图标 + 成绩 + 下一步
3. **状态图标/颜色**：用 lucide 图标 + 彩色左边框区分
   - ✅ 已通过（绿色 CheckCircle2）
   - ❌ 未通过（红色 XCircle）+ "需关注" 标记
   - 🔄 进行中（蓝色 Loader/RefreshCw）
   - ⏸ 未开始（灰色 Circle/Lock，locked 用 Lock）
4. **突出卡关**：未通过/进行中的关卡用强调色，已通过的低对比
5. **不泄露工程字段**：UI 文本只用 title/display_name + 中文状态，module_key/kind 不进展示
6. **整体进度**：保留顶部 ProgressCard（已有），关卡分组放下方

### 关卡整体状态判定（同关多模块取最靠前状态）
优先级：未通过 > 进行中 > 未开始 > 已通过（取最需关注的）
- 全部已通过 → 关卡"已通过"
- 有未通过 → 关卡"需关注"
- 有进行中无未通过 → 关卡"进行中"
- 全未开始 → 关卡"未开始"

### 现有代码复用
- view-models.ts 的 getStageLabel/getStageToneClass/detectJourneyRiskModules/formatRiskReasons 保留复用
- ModuleCard 改为"关卡区块"组件（含关卡头 + 子项列表）
- ProgressCard 保留不动

## Decision (ADR-lite)

**Context**：详情页 key 重复 + 展示不清晰，需选视觉方向。
**Decision**：方案 A 关卡分组。modules 按 order_index 分组，同关多部分归组，每关显示整体状态+子项，状态用图标/颜色直观区分，突出卡关。
**Consequences**：符合"按任务组织"+闯关业务设计；修复 key 重复（用 order_index-kind）；管理者一眼看懂学到第几关卡在哪。
