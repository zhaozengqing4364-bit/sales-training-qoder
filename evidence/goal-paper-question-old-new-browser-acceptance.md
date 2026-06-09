# 新人训练路径考卷题目旧新版本浏览器验收

时间：2026-06-04 12:26 CST

## 验收目标

覆盖目标中的浏览器验收项：

- 编辑已发布商务技巧考卷题目后，旧学员考试记录仍显示旧题。
- 新学员进入考试页时看到新题。
- 考卷发布操作写入 revision 和操作日志，且标记为只影响后续学员。

## QA 数据

- 标记：`QA旧新题-mpyzp2aehrag7`
- 考卷：`b30a262b-ec73-4acf-aeab-3b8cedbc1381`
- QA 单元：`448a1958-bdc4-4ab9-808c-85d67351272b`
- 旧提交：`03a61446-f714-4822-8803-c09913a4066c`
- 第一版题目：`cd251827-9a1f-4b4b-af3e-f0aa0f021832`
- 第二版题目：`2a9c4010-2eaa-41f4-a7c3-5ca76e9e4457`
- 第一版考卷 revision：`f3c56af6-d53a-42ec-b5e5-86f5629803c4`
- 第二版 active revision：`433b8e51-5f03-4ae5-93e7-4e0b9146a861`
- QA 学习文章：`cca43799-63e5-4749-ba61-cbe1bd86c454`

## 浏览器证据

- `evidence/goal-paper-old-attempt-keeps-old-question.png`
- `evidence/goal-paper-new-learner-sees-new-question.png`

旧提交详情页：

- URL：`/admin/sales-trainer/quiz-attempts/03a61446-f714-4822-8803-c09913a4066c`
- 可见 `QA旧新题-mpyzp2aehrag7 第一版题干：见客户前先确认客户背景。`
- 不包含 `QA旧新题-mpyzp2aehrag7 第二版题干`

新学员考试页：

- URL：`/sales-trainer/business-skills/exam?unitId=448a1958-bdc4-4ab9-808c-85d67351272b`
- 可见 `QA旧新题-mpyzp2aehrag7 第二版题干：见客户前先准备议程和确认参会人。`
- 不包含 `QA旧新题-mpyzp2aehrag7 第一版题干`

## API / 审计证据

旧提交详情 API：

```json
{
  "attempt_id": "03a61446-f714-4822-8803-c09913a4066c",
  "total_score": 10,
  "question_id": "cd251827-9a1f-4b4b-af3e-f0aa0f021832",
  "question_title": "QA旧新题-mpyzp2aehrag7 第一版题目",
  "question_stem": "QA旧新题-mpyzp2aehrag7 第一版题干：见客户前先确认客户背景。",
  "paper_revision_id": "f3c56af6-d53a-42ec-b5e5-86f5629803c4"
}
```

当前学员考卷 API：

```json
{
  "paper_id": "b30a262b-ec73-4acf-aeab-3b8cedbc1381",
  "active_revision_id": "433b8e51-5f03-4ae5-93e7-4e0b9146a861",
  "active_revision_no": 2,
  "question_id": "2a9c4010-2eaa-41f4-a7c3-5ca76e9e4457",
  "question_title": "QA旧新题-mpyzp2aehrag7 第二版题目",
  "question_stem": "QA旧新题-mpyzp2aehrag7 第二版题干：见客户前先准备议程和确认参会人。"
}
```

考卷 revision 列表：

```json
[
  {
    "revision_id": "433b8e51-5f03-4ae5-93e7-4e0b9146a861",
    "revision_no": 2,
    "status": "published",
    "is_active": true,
    "change_class": "scoring_high_risk"
  },
  {
    "revision_id": "f3c56af6-d53a-42ec-b5e5-86f5629803c4",
    "revision_no": 1,
    "status": "published",
    "is_active": false,
    "change_class": "scoring_high_risk"
  }
]
```

操作日志：

- `exam_paper_revision_saved` 包含 `before_revision_id=f3c56af6-d53a-42ec-b5e5-86f5629803c4`、`working_revision_id=433b8e51-5f03-4ae5-93e7-4e0b9146a861`、`changed_fields=["description","questions"]`、`future_only=true`。
- `exam_paper_revision_published` 包含 `before_revision_id=f3c56af6-d53a-42ec-b5e5-86f5629803c4`、`after_revision_id=433b8e51-5f03-4ae5-93e7-4e0b9146a861`、`future_only=true`。

## 注意

该 QA attempt 的 `path_revision_id` 为空且 `legacy_snapshot_only=true`，因为本场景专门验证考卷 revision 对历史 answer snapshot 的隔离，不声明覆盖路径级 lineage 验收。路径配置回滚和路径 revision 的浏览器验收仍是独立未完成项。
