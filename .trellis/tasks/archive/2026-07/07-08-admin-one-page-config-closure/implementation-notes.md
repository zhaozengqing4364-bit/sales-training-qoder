# Implementation Notes

## Plan

1. 完成 Trellis task / PRD / 规范读取。
2. 使用 CodeGraph 和 3 个子 agent 审计录音、学习专题、权限/测试影响。
3. 抽取就地快速创建组件与结构化评分标准模型。
4. 改造录音管理和学习专题页面为一页式配置闭环。
5. 更新测试、文档、Trellis 记录。
6. 运行 trellis-check 对应质量门禁并提交归档。

## Impact Surface

- 前端管理后台页面、组件、导航、文档和测试。
- 不改数据库结构，不改后端权限、审计、发布、回滚或版本快照语义。
- 录音任务页复用现有单元、材料、评分标准和 path config API；学习专题页复用 learning content、paper 和 path config API。

## Deviations

- 未引入新的 backend `newcomer_learning_topics_v1.exam_paper_id` 字段；专题小测绑定复用现有 `business_skills.exam_paper_id` 的 path config working revision，页面文案和契约明确这是 v1 兼容持久化。
- 快速创建组件先放在目标页面内，避免过早抽象；后续第二个专题复用时再抽出共享 Drawer 组件更稳。

## Implementation Summary

- 录音任务详情页新增就地新建训练单元、材料和评分标准弹窗；成功后发布资源、刷新候选项并自动写回当前录音任务绑定。
- 评分标准表单改为普通结构化模式，高级模式折叠 `system_prompt`、`output_schema` 和原始学员评分 JSON；编辑旧数据时不因空结构化字段回写默认 rubric。
- 学习专题详情页聚合文章/章节、小单元、小测/考卷、AI 教练与得分展示；文章可带首章节就地创建发布并绑定，小测可从已发布题目快速组卷并保存绑定。
- 独立资源页保留为查看全部/高级管理/旧路由兼容，文档补充一页式配置原则和回滚边界。

## Verification

- `codegraph affected web/src/app/admin/sales-trainer/audio/[scenarioSlug]/page.tsx web/src/app/admin/sales-trainer/articles/business-etiquette/page.tsx web/src/components/admin/sales-trainer/score-prompt-form.tsx`：识别评分标准表单影响测试。
- `npx vitest run src/components/admin/sales-trainer/score-prompt-form.test.tsx 'src/app/admin/sales-trainer/audio/[scenarioSlug]/page.test.tsx' src/app/admin/sales-trainer/articles/business-etiquette/page.test.tsx src/app/admin/sales-trainer/articles/page.test.tsx src/lib/sales-trainer/routes.test.ts src/components/layout/admin-sidebar.test.tsx src/components/admin/sales-trainer/module-nav.test.tsx src/app/admin/sales-trainer/score-standards/new/page.test.tsx src/app/admin/sales-trainer/score-standards/[id]/edit/page.test.tsx`：9 files / 35 tests passed。
- `npx tsc --noEmit`：passed。
- `npm run lint`：passed，保留仓库既有 81 条 warning，未新增 error。
- `npm run build`：passed，Next.js 16.2.7 production build 成功。
