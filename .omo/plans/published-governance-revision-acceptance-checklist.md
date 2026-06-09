# 发布治理修订模型验收清单

关联主计划：`.omo/plans/published-governance-revision-plan.md`  
关联执行包：`.omo/plans/published-governance-revision-execution-pack.md`

## 使用规则

- 每个验收项必须有证据：测试输出、接口响应、数据库记录、截图、审计事件或浏览器验收记录。
- 前端隐藏按钮不能作为权限通过证据；必须有后端拒绝越权的测试或接口证据。
- 页面可打开不能作为业务闭环通过证据；必须证明历史快照不变、未来请求使用新修订、审计可追踪。
- 全量命令若因既有失败无法通过，必须附失败原文、影响判断和聚焦替代测试。

## A. 管理员自然编辑

- [ ] 已发布训练单元可进入编辑页，保存后生成 working revision，不直接覆盖 active revision。
- [ ] 已发布商务技巧考卷可进入编辑页，保存后生成 working revision。
- [ ] 已发布题目可编辑题干、选项、正确答案、分值、AI 评分 prompt，保存后生成题目 revision。
- [ ] 已发布录音评分标准可编辑，保存后生成评分标准 revision。
- [ ] 已发布商务技巧文章章节可编辑，保存后生成学习内容 revision。
- [ ] 管理员主流程显示“编辑 / 保存修改 / 发布并生效 / 查看历史 / 回滚到此版本 / 重新评分历史记录”。
- [ ] 管理员普通编辑不需要点击“复制为新草稿”。
- [ ] 管理员普通编辑不需要手动“换绑”才能让未来学员使用新内容。
- [ ] 发布确认明确说明“只影响后续学员，已提交记录不变”。

失败判定：

- 任何普通内容编辑仍以“复制草稿、重新发布、换绑”为主路径。
- 保存已发布对象直接更新 active published payload。

## B. 自动生成修订

- [ ] 每个业务对象有稳定 `logical_id`。
- [ ] 每次内容变更生成新的 `revision_id` 或等价不可变版本。
- [ ] revision payload 发布后不可原地修改。
- [ ] working revision 和 active revision 可同时存在。
- [ ] active pointer 更新必须写审计事件。
- [ ] 字段风险分类能区分非语义更正、语义修改、绑定修改、高风险评分规则修改。
- [ ] 正确答案、分值、通过线、AI prompt、评分规则不能被配置降级为低风险。
- [ ] 重复点击发布具备幂等语义。
- [ ] 并发编辑使用 `base_revision_id`、working revision version 或等价乐观锁。

失败判定：

- 修订只是状态字段，没有不可变 payload。
- 版本号可被后续编辑覆盖。

## C. 历史快照不变

- [ ] quiz attempt 创建时冻结 path/unit/paper/question revision refs 或 legacy snapshot 标记。
- [ ] quiz answer snapshot 继续保存学员当时看到的题干、选项、答案和评分依据。
- [ ] audio submission 创建时冻结 material、score scheme、task brief snapshot。
- [ ] audio score result 保留 transcript snapshot、prompt version、prompt hash 或 prompt revision。
- [ ] curriculum session 创建时冻结 `curriculum_snapshot` 和 revision lineage。
- [ ] 旧 attempt 在新题发布后仍显示旧题。
- [ ] 旧 audio result 在新 prompt 发布后仍能解释旧 prompt。
- [ ] 旧 session 在 CaseItem、RoleProfile、ExaminerAgent、LearningContent 变更后仍消费旧 snapshot。
- [ ] 历史记录只有 snapshot 无 revision lineage 时标记 `legacy_snapshot_only`，不伪造 revision id。

失败判定：

- 历史记录从 latest asset 重新拼装展示。
- 新题、新 prompt、新材料覆盖旧 attempt/submission/session/result。

## D. 未来生效

- [ ] 发布新 path revision 后，新学员首页使用新路径配置。
- [ ] 发布新 paper revision 后，新 attempt 使用新考卷。
- [ ] 发布新 question revision 后，新 attempt 使用新题。
- [ ] 发布新 prompt revision 后，新评分使用新 prompt。
- [ ] 发布新 material revision 后，新录音任务使用新材料。
- [ ] 发布新 learning content revision 后，新学习记录使用新章节内容。
- [ ] 正在考试中的学员继续使用 attempt 创建时冻结版本。
- [ ] 正在录音或评分的 submission 继续使用 submission 创建时冻结版本。

失败判定：

- 发布动作影响已创建 attempt 或 submission。
- 学员端仍主要依赖前端硬编码四模块。

## E. 路径配置中心是真源

- [ ] 存在路径级发布资产或等价模型，能表示 `newcomer_training_path_v1`。
- [ ] 路径配置中心可编辑四个关卡的启停、顺序、标题、说明、按钮、绑定、缺失配置和学员端预览。
- [ ] 路径配置中心可保存 working revision。
- [ ] 路径配置中心可发布 active revision。
- [ ] 路径配置中心可回滚到历史 revision。
- [ ] `SalesTrainerUnit.config.path` 只作为 legacy projection 或兼容 alias，不再是新写入真源。
- [ ] `new_seller_modules_v1` 只读兼容，并在诊断中标记迁移状态。
- [ ] 学员端首页从 path active revision 读取关卡配置。

失败判定：

- 路径配置中心仍只是从多个 Unit 聚合出来的只读状态页。
- 管理员仍需进模块单元编辑页填路径字段。

## F. 回滚未来生效

- [ ] 每个可发布对象都有历史版本入口。
- [ ] 回滚 API 接收目标 revision 和 reason。
- [ ] 回滚前执行依赖门禁。
- [ ] 回滚移动 active pointer，不修改历史 revision payload。
- [ ] 回滚写 audit event，包含 before_revision_id、after_revision_id、reason、trace_id。
- [ ] 回滚只影响未来学员、未来考试、未来录音、未来 session。
- [ ] 回滚到非法旧版本时返回可操作错误和修复入口。
- [ ] 归档资产被当前 active 配置引用时禁止归档或要求先解除引用。

失败判定：

- 回滚只是 UI 文案或复制一份旧数据。
- 回滚会改写历史 attempt/session/result。

## G. 高风险重评审计

- [ ] 重评历史成绩不是发布 prompt 或评分规则时的自动副作用。
- [ ] 重评入口仅超级管理员或授权运维可见。
- [ ] 后端强制检查重评权限。
- [ ] 重评前必须预览影响范围。
- [ ] 重评必须填写 reason。
- [ ] 重评记录 before/after、范围、操作者、trace_id、created_at。
- [ ] 默认追加 regrade result，不覆盖原始结果。
- [ ] 如需切换展示结果，必须有额外高风险确认和审计。

失败判定：

- 重评可无原因执行。
- 重评直接覆盖原始成绩且无 before/after。

## H. 权限拦截

- [ ] 超级管理员可配置、发布、回滚、归档、重评、查看诊断和审计。
- [ ] 内容管理员可编辑内容、题库、考卷，但不能查看全量学员敏感记录或执行重评。
- [ ] 培训负责人只能查看授权部门学员记录和结果。
- [ ] 运维人员可看诊断、日志、重试任务，可按授权执行应急回滚或重评。
- [ ] 学员只能学习、考试、上传录音、查看自己的结果。
- [ ] 后端拒绝越权编辑。
- [ ] 后端拒绝越权发布。
- [ ] 后端拒绝越权回滚。
- [ ] 后端拒绝越权重评。
- [ ] 前端按钮隐藏只是辅助，不是权限真源。

失败判定：

- 权限仍只有 `admin/support` 粗粒度。
- 后端没有集中权限判断。

## I. 运维诊断

- [ ] 诊断页显示当前 path active revision。
- [ ] 诊断页显示四个关卡绑定的 content/paper/material/prompt revision。
- [ ] 诊断页能指出商务技巧文章未发布、未绑定或绑定草稿。
- [ ] 诊断页能指出商务技巧考卷未发布、未绑定或绑定草稿。
- [ ] 诊断页能指出 PPT 材料缺 current published revision。
- [ ] 诊断页能指出录音评分标准缺 active revision。
- [ ] 诊断页能显示 ASR 配置状态。
- [ ] 诊断页能显示 AI 评分服务配置状态。
- [ ] 诊断页能显示最近错误码 Top N。
- [ ] 诊断页能显示 legacy snapshot only 数量。
- [ ] 每个错误给出对象、原因、处理角色、后台入口。

失败判定：

- 学员端只显示“未绑定已发布内容”且不给原因。
- 运维看不到缺哪个绑定、哪个 revision、哪个服务配置。

## J. 技术字段默认隐藏

- [ ] 普通管理员主流程默认不显示 `sales_trainer`。
- [ ] 普通管理员主流程默认不显示 `module_key`。
- [ ] 普通管理员主流程默认不显示 `unit_id`。
- [ ] 普通管理员主流程默认不显示 `paper_key`。
- [ ] 普通管理员主流程默认不显示 `path_key`。
- [ ] 普通管理员主流程默认不显示 raw JSON config。
- [ ] 技术字段只在诊断展开区或运维视图出现。
- [ ] 用户可见文案使用“新人训练路径”。

失败判定：

- 普通管理员必须靠技术字段完成配置。
- 用户可见区域仍出现“销售队列”或把 `sales_trainer` 当产品名。

## K. 浏览器验收路径

- [ ] 管理员配置路径，发布商务技巧学习文章和考卷。
- [ ] 学员进入新人训练路径首页，看到当前关卡、下一步和解锁状态。
- [ ] 学员先学习商务技巧章节，再进入考试。
- [ ] 管理员编辑已发布商务技巧考卷题目并发布。
- [ ] 旧学员考试记录仍显示旧题。
- [ ] 新学员考试显示新题。
- [ ] 管理员编辑 AI prompt 并发布。
- [ ] 旧评分仍显示旧 prompt 版本或 hash。
- [ ] 新评分使用新 prompt。
- [ ] 管理员回滚路径配置。
- [ ] 新学员看到回滚后的路径。
- [ ] 旧 attempt/session/result 不变。
- [ ] 操作日志能查到发布、回滚、绑定变更和重评事件。

## L. 质量门

- [ ] 执行 `cd web && npx tsc --noEmit`。
- [ ] 执行 `cd web && npm test` 或聚焦 `cd web && npx vitest run 'src/app/admin/sales-trainer/paths/page.test.tsx' 'src/lib/sales-trainer/config-center.test.ts' 'src/lib/sales-trainer/admin-display.test.ts'`。
- [ ] 执行 `cd backend && venv/bin/python -m pytest tests/unit/test_newcomer_training_path_papers.py tests/unit/test_newcomer_training_path_audit_logs.py tests/integration/test_newcomer_training_path_paper_api.py --no-cov`。
- [ ] 必要时执行 `cd backend && venv/bin/ruff check src/`。
- [ ] 必要时执行 `cd backend && venv/bin/mypy src/`。
- [ ] 执行 `cd backend && venv/bin/alembic upgrade head`。
- [ ] 最终执行 `bash scripts/critical-quality-gate.sh`。
- [ ] 全量失败时记录既有失败证据和聚焦替代证据。

失败判定：

- 未执行验证却声称通过。
- 只提供页面快照，不提供业务闭环证据。
