# 发布治理修订模型测试矩阵

关联主计划：`.omo/plans/published-governance-revision-plan.md`

## 命令真实性

本矩阵只使用仓库中存在的命令形态：

- `cd web && npx tsc --noEmit`
- `cd web && npm test`
- `cd web && npx vitest run 'src/app/admin/sales-trainer/paths/page.test.tsx' 'src/lib/sales-trainer/config-center.test.ts'`
- `cd backend && venv/bin/python -m pytest tests/unit/test_newcomer_training_path_papers.py tests/integration/test_newcomer_training_path_paper_api.py --no-cov`
- `cd backend && venv/bin/ruff check src/`
- `cd backend && venv/bin/mypy src/`
- `cd backend && venv/bin/alembic upgrade head`
- `bash scripts/critical-quality-gate.sh`

如果全量命令因既有失败无法通过，必须保存完整输出，说明失败是否与本次变更相关，并提供聚焦测试替代证据。不得写“已通过”。

## 后端单元测试矩阵

| 编号 | 场景 | 覆盖对象 | 推荐测试文件 | 命令 | 必须断言 |
|---|---|---|---|---|---|
| BE-U1 | revision 创建 | governance revision service | 新增 `backend/tests/unit/test_governance_revision_service.py` | `cd backend && venv/bin/python -m pytest tests/unit/test_governance_revision_service.py --no-cov` | `logical_id` 稳定、`revision_id` 唯一、payload hash 稳定 |
| BE-U2 | published revision 不可变 | governance revision service | 新增 `backend/tests/unit/test_governance_revision_service.py` | `cd backend && venv/bin/python -m pytest tests/unit/test_governance_revision_service.py --no-cov` | 已发布 payload update 被拒绝或只能创建新 revision |
| BE-U3 | active pointer 发布 | active pointer service | 新增 `backend/tests/unit/test_governance_active_pointer_service.py` | `cd backend && venv/bin/python -m pytest tests/unit/test_governance_active_pointer_service.py --no-cov` | publish 后 future lookup 命中新 revision |
| BE-U4 | active pointer 回滚 | active pointer service | 新增 `backend/tests/unit/test_governance_active_pointer_service.py` | `cd backend && venv/bin/python -m pytest tests/unit/test_governance_active_pointer_service.py --no-cov` | rollback 只移动 pointer，不复制或修改 revision payload |
| BE-U5 | 字段风险分类 | change classifier | 新增 `backend/tests/unit/test_governance_change_classifier.py` | `cd backend && venv/bin/python -m pytest tests/unit/test_governance_change_classifier.py --no-cov` | 题干、答案、分值、通过线、prompt 分类正确 |
| BE-U6 | 路径配置真源 | 新人训练路径 | `backend/tests/unit/test_newcomer_training_path_boundary.py` | `cd backend && venv/bin/python -m pytest tests/unit/test_newcomer_training_path_boundary.py --no-cov` | path active revision 是 learner 首页来源 |
| BE-U7 | 考卷修订 | 商务技巧考卷 | `backend/tests/unit/test_newcomer_training_path_papers.py` | `cd backend && venv/bin/python -m pytest tests/unit/test_newcomer_training_path_papers.py --no-cov` | 修改已发布 paper 生成 working revision，不改 active |
| BE-U8 | 文章绑定修订 | 商务技巧学习内容 | `backend/tests/unit/test_newcomer_training_path_articles.py` | `cd backend && venv/bin/python -m pytest tests/unit/test_newcomer_training_path_articles.py --no-cov` | 绑定变更生成 binding revision，写审计 |
| BE-U9 | 操作日志 | 审计事件 | `backend/tests/unit/test_newcomer_training_path_audit_logs.py` | `cd backend && venv/bin/python -m pytest tests/unit/test_newcomer_training_path_audit_logs.py --no-cov` | audit 包含 actor、action、target、before/after、reason、trace_id |
| BE-U10 | 权限 | RBAC | `backend/tests/unit/test_newcomer_training_path_permissions.py` | `cd backend && venv/bin/python -m pytest tests/unit/test_newcomer_training_path_permissions.py --no-cov` | 内容管理员、培训负责人、运维、学员权限边界正确 |
| BE-U11 | 录音快照 | material/score/prompt snapshot | `backend/tests/unit/test_sales_trainer_services.py` | `cd backend && venv/bin/python -m pytest tests/unit/test_sales_trainer_services.py --no-cov` | material_snapshot、score_scheme_snapshot、task_brief_snapshot 不被新发布污染 |
| BE-U12 | 课程闭环冻结引用 | published_asset_refs | `backend/tests/unit/test_practice_template_published_asset_refs.py` | `cd backend && venv/bin/python -m pytest tests/unit/test_practice_template_published_asset_refs.py --no-cov` | `published_asset_refs` 引用 revision/hash，旧 session snapshot 不变 |

## 后端集成和契约测试矩阵

| 编号 | 场景 | 推荐测试文件 | 命令 | 必须断言 |
|---|---|---|---|---|
| BE-I1 | paper API 自然编辑 | `backend/tests/integration/test_newcomer_training_path_paper_api.py` | `cd backend && venv/bin/python -m pytest tests/integration/test_newcomer_training_path_paper_api.py --no-cov` | `PUT/PATCH` 已发布 paper 返回 working revision，不返回不可修改 |
| BE-I2 | article binding API | `backend/tests/integration/test_newcomer_training_path_article_api.py` | `cd backend && venv/bin/python -m pytest tests/integration/test_newcomer_training_path_article_api.py --no-cov` | 绑定已发布 LearningContent，草稿/归档被拒绝 |
| BE-I3 | RBAC API | `backend/tests/integration/test_newcomer_training_path_rbac_api.py` | `cd backend && venv/bin/python -m pytest tests/integration/test_newcomer_training_path_rbac_api.py --no-cov` | 越权发布、回滚、重评返回 `[GOVERNANCE_PERMISSION_DENIED]` 或契约定义错误 |
| BE-I4 | learner path | `backend/tests/integration/test_sales_trainer_api.py` | `cd backend && venv/bin/python -m pytest tests/integration/test_sales_trainer_api.py --no-cov` | learner 读取 path active revision；缺真源返回 `[PATH_CONFIG_SOURCE_MISSING]` |
| BE-I5 | ASR/AI 配置诊断 | `backend/tests/integration/test_sales_trainer_real_providers.py` | `cd backend && venv/bin/python -m pytest tests/integration/test_sales_trainer_real_providers.py --no-cov` | 诊断区分配置缺失、请求失败、响应非法 |
| BE-I6 | 数据迁移 | Alembic | 新增迁移测试或手工证据 | `cd backend && venv/bin/alembic upgrade head` | migration 可 apply；backfill 不伪造历史 lineage |

## 前端单元和页面测试矩阵

| 编号 | 场景 | 文件 | 命令 | 必须断言 |
|---|---|---|---|---|
| FE-U1 | 类型检查 | 全 web | 全局 | `cd web && npx tsc --noEmit` | API DTO、revision 字段、权限字段类型正确 |
| FE-U2 | 路径配置中心 | `web/src/app/admin/sales-trainer/paths/page.test.tsx` | `cd web && npx vitest run 'src/app/admin/sales-trainer/paths/page.test.tsx'` | 页面可编辑、保存、发布、回滚，不是只读诊断 |
| FE-U3 | 配置中心模型 | `web/src/lib/sales-trainer/config-center.test.ts` | `cd web && npx vitest run 'src/lib/sales-trainer/config-center.test.ts'` | 缺绑定、草稿绑定、归档引用、legacy alias 诊断正确 |
| FE-U4 | 模块路径 | `web/src/lib/sales-trainer/module-path.test.ts` | `cd web && npx vitest run 'src/lib/sales-trainer/module-path.test.ts'` | 学员端从后端配置映射，不以硬编码为唯一真源 |
| FE-U5 | 管理显示文案 | `web/src/lib/sales-trainer/admin-display.test.ts` | `cd web && npx vitest run 'src/lib/sales-trainer/admin-display.test.ts'` | 普通管理员默认不看到技术字段 |
| FE-U6 | 考卷列表 | `web/src/app/admin/sales-trainer/papers/page.test.tsx` | `cd web && npx vitest run 'src/app/admin/sales-trainer/papers/page.test.tsx'` | 已发布 paper 主操作为编辑/历史/发布修订，不是复制草稿 |
| FE-U7 | 考卷编辑 | `web/src/app/admin/sales-trainer/papers/[paperId]/edit/page.test.tsx` | `cd web && npx vitest run 'src/app/admin/sales-trainer/papers/[paperId]/edit/page.test.tsx'` | 已发布考卷可保存 working revision，高风险字段提示 |
| FE-U8 | 评分标准 | `web/src/app/admin/sales-trainer/score-standards/page.test.tsx` | `cd web && npx vitest run 'src/app/admin/sales-trainer/score-standards/page.test.tsx'` | 已发布评分标准可编辑为新修订 |
| FE-U9 | 题目表单 | `web/src/components/admin/sales-trainer/question-form.test.tsx` | `cd web && npx vitest run 'src/components/admin/sales-trainer/question-form.test.tsx'` | 题干、选项、正确答案、分值、AI prompt 风险提示 |
| FE-U10 | prompt 表单 | `web/src/components/admin/sales-trainer/score-prompt-form.test.tsx` | `cd web && npx vitest run 'src/components/admin/sales-trainer/score-prompt-form.test.tsx'` | prompt 修改提示未来生效；重评为独立入口 |
| FE-U11 | 运维诊断 | `web/src/app/admin/sales-trainer/settings/page.test.tsx` | `cd web && npx vitest run 'src/app/admin/sales-trainer/settings/page.test.tsx'` | active revision、缺失配置、服务配置、错误码展示 |
| FE-U12 | 操作日志 | `web/src/app/admin/sales-trainer/operation-logs/page.test.tsx` | `cd web && npx vitest run 'src/app/admin/sales-trainer/operation-logs/page.test.tsx'` | before/after revision、reason、trace_id、影响范围展示 |
| FE-U13 | 学员首页 | `web/src/app/(dashboard)/sales-trainer/page.test.tsx` | `cd web && npx vitest run 'src/app/(dashboard)/sales-trainer/page.test.tsx'` | 学员知道当前关卡、下一步、解锁状态 |
| FE-U14 | 商务技巧学习页 | `web/src/app/(dashboard)/sales-trainer/business-skills/page.test.tsx` | `cd web && npx vitest run 'src/app/(dashboard)/sales-trainer/business-skills/page.test.tsx'` | 先学习章节，支持 Markdown 和图片，再进入考试 |
| FE-U15 | 考试页 | `web/src/app/(dashboard)/sales-trainer/business-skills/exam/page.test.tsx` | `cd web && npx vitest run 'src/app/(dashboard)/sales-trainer/business-skills/exam/page.test.tsx'` | attempt 使用 paper revision；提交后状态清楚 |
| FE-U16 | 答题记录详情 | `web/src/app/admin/sales-trainer/quiz-attempts/[attemptId]/page.test.tsx` | `cd web && npx vitest run 'src/app/admin/sales-trainer/quiz-attempts/[attemptId]/page.test.tsx'` | 展示 answer snapshots 和 revision lineage |
| FE-U17 | 录音记录详情 | `web/src/app/admin/sales-trainer/audio-submissions/page.test.tsx` | `cd web && npx vitest run 'src/app/admin/sales-trainer/audio-submissions/page.test.tsx'` | 展示 material/score/task snapshots |
| FE-U18 | 全量前端测试 | 全 web | 全局 | `cd web && npm test` | 若失败，保存既有失败证据并提供聚焦测试 |

## 浏览器验收矩阵

浏览器验收建议在本地服务 `http://localhost:3445` 和后端 `http://localhost:3444` 上执行。

| 编号 | 路径 | 操作 | 必须证据 |
|---|---|---|---|
| BR-1 | `/admin/sales-trainer/paths` | 配置并发布新人训练路径 | 路径 active revision、四关卡配置、学员端预览、审计事件截图 |
| BR-2 | `/sales-trainer` | 学员打开首页 | 当前关卡、先学习/先考试、结果入口、下一关解锁状态截图 |
| BR-3 | `/sales-trainer/business-skills` | 学习商务技巧章节 | Markdown、图片、章节列表、学习后考试入口截图 |
| BR-4 | `/admin/sales-trainer/papers` | 编辑已发布商务技巧考卷题目并发布 | 发布确认、影响范围、history drawer、audit 截图 |
| BR-5 | `/admin/sales-trainer/quiz-attempts/{attemptId}` | 查看旧学员考试记录 | 旧题干、旧选项、旧分值、旧 revision 或 legacy snapshot 截图 |
| BR-6 | `/sales-trainer/business-skills/exam` | 新学员考试 | 新题干、新选项、新 paper revision 证据 |
| BR-7 | `/admin/sales-trainer/score-standards` | 编辑 AI prompt 并发布 | 新评分使用新 prompt；旧评分仍解释旧 prompt hash |
| BR-8 | `/admin/sales-trainer/paths` | 回滚路径配置 | 回滚确认、active pointer before/after、future-only 说明、审计截图 |
| BR-9 | `/admin/sales-trainer/settings` | 查看运维诊断 | 缺绑定、非法引用、ASR/AI 配置、错误码 Top N、legacy 数量 |
| BR-10 | `/admin/sales-trainer/operation-logs` | 查看操作日志 | publish、rollback、binding_changed、regrade 事件含 trace_id |

## 完整质量门

最终执行：

```bash
bash scripts/critical-quality-gate.sh
```

质量门脚本会执行 secret scan、web typecheck、覆盖率 Vitest、Playwright smoke、presentation/sales E2E、后端集成与 smoke regression。若该命令失败：

1. 保存 `.sisyphus/evidence/task-9-quality-gate.txt` 或等价输出。
2. 标注失败来自既有用例、环境依赖还是本次发布治理改造。
3. 提供本矩阵中的聚焦测试通过证据。
4. 最终汇报中禁止写“完整质量门通过”。
