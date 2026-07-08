# 新人训练专项 Playwright Route Manifest

运行规格：

- `web/tests/e2e/newcomer-training-learner.spec.ts`
- `web/tests/e2e/newcomer-training-admin.spec.ts`
- 代码清单：`web/tests/e2e/newcomer-training-route-manifest.ts`

截图目录：

- `.trellis/tasks/07-08-newcomer-path-playwright-audit-governance/playwright-audit/screenshots/`

报告文件：

- `.trellis/tasks/07-08-newcomer-path-playwright-audit-governance/playwright-audit/newcomer-training-learner-report.json`
- `.trellis/tasks/07-08-newcomer-path-playwright-audit-governance/playwright-audit/newcomer-training-admin-report.json`

## 前台

- `L-01` `/sales-trainer`
- `L-02` `/sales-trainer/learn/hub`
- `L-03` `/sales-trainer/learning-topics/business-etiquette`
- `L-04` `/sales-trainer/learn/[unitId]`
- `L-05` `/sales-trainer/quiz/[unitId]`
- `L-06` `/sales-trainer/quiz/result/[attemptId]`
- `L-07` `/sales-trainer/audio/[unitId]`
- `L-08` `/sales-trainer/audio/result/[submissionId]`
- `L-09` `/sales-trainer/business-skills`
- `L-10` `/sales-trainer/business-skills/exam`
- `L-11` `/sales-trainer/business-skills/coach`

## 后台

- `A-01` `/admin/sales-trainer`
- `A-02` `/admin/sales-trainer/audio`
- `A-03` `/admin/sales-trainer/audio/ppt-explanation`
- `A-03B` `/admin/sales-trainer/audio/company-product-demo`
- `A-04` `/admin/sales-trainer/audio/materials`
- `A-05` `/admin/sales-trainer/audio/score-standards`
- `A-06` `/admin/sales-trainer/audio/submissions`
- `A-07` `/admin/sales-trainer/audio/results`
- `A-08` `/admin/sales-trainer/learning-topics`
- `A-09` `/admin/sales-trainer/learning-topics/business-etiquette`
- `A-10` `/admin/sales-trainer/learning-topics/import`
- `A-11` `/admin/sales-trainer/learning-topics/capabilities`
- `A-12` `/admin/sales-trainer/learning-topics/questions`
- `A-13` `/admin/sales-trainer/learning-topics/questions/new`
- `A-14` `/admin/sales-trainer/learning-topics/questions/drafts`
- `A-15` `/admin/sales-trainer/learning-topics/questions/quiz-preview`
- `A-16` `/admin/sales-trainer/learning-topics/papers`
- `A-17` `/admin/sales-trainer/learning-topics/papers/new`
- `A-18` `/admin/sales-trainer/paths`
- `A-19` `/admin/sales-trainer/units`
- `A-20` `/admin/sales-trainer/ai-coach`
- `A-21` `/admin/sales-trainer/readiness`
- `A-22` `/admin/sales-trainer/training-records`
- `A-23` `/admin/sales-trainer/analytics`
- `A-24` `/admin/sales-trainer/settings`
- `A-25` `/admin/sales-trainer/operation-logs`

## 旧入口兼容

- `C-01` `/admin/sales-trainer/articles`
- `C-02` `/admin/sales-trainer/materials`
- `C-03` `/admin/sales-trainer/score-standards`
- `C-04` `/admin/sales-trainer/papers`
- `C-05` `/admin/sales-trainer/questions`
- `C-06` `/admin/sales-trainer/audio-submissions`
- `C-07` `/admin/sales-trainer/score-results`
- `C-08` `/admin/sales-trainer/training-tasks`

## 排除范围

- `/training/sales`
- `/practice/*`
- `/admin/business-rules/sales-trainer-phase2`
- 其他非新人训练路径页面
