# Newcomer Training Path Browser Acceptance Partial

## Scope

This is partial browser acceptance for the newcomer training path publish
governance work. It covers the current path configuration center, material
configuration entry, and business-skills learner flow. It does not cover all
required old/new revision, rollback, and regrade browser scenarios yet.

## Browser Target

- `http://localhost:3445/admin/sales-trainer/paths?module=business_skills`
- `http://localhost:3445/admin/sales-trainer/materials?module=ppt_explanation&purpose=ppt_pitch`
- `http://localhost:3445/sales-trainer/business-skills?unitId=dd365599-2674-4796-be76-d3e901baa41e`
- `http://localhost:3445/sales-trainer/business-skills/exam?unitId=dd365599-2674-4796-be76-d3e901baa41e`

## Observed Passes

- Path configuration center shows four stages, current binding status, missing
  configuration diagnostics, learner preview, operation-log/settings links, and
  publish-governance copy: "编辑将生成新修订，只影响后续学员".
- The business-skills module is selected without exposing `module_key`,
  `unit_id`, `paper_key`, or `sales_trainer` as the main admin task language.
- Business-skills binding controls are visible in the path center:
  learning article selector and exam paper selector.
- The "配置材料版本" target opens the material library configuration page, which
  includes "新建材料主档", "新增版本", "版本列表", and a link back to publish the
  path binding.
- Learner business-skills page loads the bound article as a chapter flow:
  two chapters are visible, progress starts at `0/2`, and the exam link is not
  shown until chapters are completed.
- Completing both chapters reveals "完成学习，进入考试".
- The exam page loads the bound paper with 4 questions covering single choice,
  multiple choice, true/false, and short answer.
- Editing a published business-skills paper from a first question to a second
  question keeps the old attempt detail on the first question while the learner
  exam page for the QA unit shows the second question.

## Screenshots

- `evidence/browser-path-config-center-business.png`
- `evidence/browser-materials-config-entry.png`
- `evidence/browser-business-skills-exam.png`
- `evidence/goal-paper-question-old-new-browser-acceptance.md`
- `evidence/goal-paper-old-attempt-keeps-old-question.png`
- `evidence/goal-paper-new-learner-sees-new-question.png`
- `evidence/goal-path-rollback-legacy-lineage-browser-acceptance.md`
- `evidence/goal-path-rollback-legacy-attempt-detail.png`
- `evidence/goal-path-rollback-learner-home-after-rollback.png`
- `evidence/goal-path-rollback-operation-log-expanded.png`
- `evidence/goal-ai-prompt-old-new-browser-acceptance.md`
- `evidence/goal-ai-prompt-old-new-regrade-preview.png`
- `evidence/goal-ai-prompt-old-new-preview.network-response`
- `evidence/goal-audio-regrade-browser-acceptance.md`
- `evidence/goal-audio-regrade-after-run.png`
- `evidence/goal-audio-regrade-operation-log-expanded.png`
- `evidence/goal-operation-log-governance-browser-acceptance.md`
- `evidence/goal-operation-log-governance-browser.png`

## Remaining Browser Acceptance

- No remaining browser acceptance item is listed in this partial file. The full
  goal still requires final requirement-by-requirement audit against
  `.omo/plans/published-governance-revision-acceptance-checklist.md`.
