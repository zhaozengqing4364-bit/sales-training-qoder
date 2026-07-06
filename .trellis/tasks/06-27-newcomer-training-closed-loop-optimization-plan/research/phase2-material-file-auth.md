# Phase 2 材料文件对象级授权实现记录

> 日期：2026-06-27  
> 范围：`/api/v1/sales-trainer/materials/versions/{version_id}/file`、`SalesTrainerMaterialService.resolve_file_access()`。

## 2026-06-29 闭环复核附录

本文件记录的是 Phase 2 当时的材料文件授权切片。后续 Phase 4/Phase 9 已补齐当时明确延期的历史材料只读回放：

- archived material version 被训练记录冻结引用时，可通过历史回放授权只读访问；不会把任意 archived version 暴露给 learner。
- 文件访问对象级授权下沉到后端 service，并经 `TrainingRecordService.get_record_for_viewer()` 复查 viewer/team department scope。
- dead data diagnostics 已输出 legacy 标记、候选动作和 no-mutation rollback plan；生产 apply 仍需人工审批。
- 最新证据：`audit-closure-matrix.md` P1 内容资产与历史回放、`final-verification-report.md` 历史回放三快照契约补强、2026-06-29 06:12 full gate passed。

## 本轮决策

- 保持“文件访问授权权威”在后端 service，不把对象级判断散落到前端或调用方。
- learner 文件访问基于当前 **active path revision + 学员当前可进入模块** 收敛：
  - 先读 `SalesTrainerPathService.list_paths_for_user()` 产出的 learner path；
  - 只接受当前 active revision 中 `locked=false` 的 level；
  - 再把对应 unit/path binding 解析成当前 learner 可见材料版本；
  - 请求版本不在这个集合里时 fail-closed 返回 404。
- `admin` / `content_admin` / `ops` 继续保留已发布材料版本读取能力，不要求命中 learner path。
- `support` / `training_lead` / `training_manager` 不因为“可看部门记录”自动获得材料文件访问权；本轮统一返回 403。

## 为什么这样收口

- 当前仓库里已有可复用真源：
  - active path revision projection；
  - learner path 锁定态计算；
  - path material binding 到 unit 有效配置的合成。
- learner-level 来源在 `sales_trainer` 域内尚未落地；本轮如果硬加 learner-level 判断，只能凭空创造规则，不符合“最小正确修复”。
- manager 的材料访问需求如果未来需要开放，必须绑定到“部门内某条历史记录引用的材料”或明确的新权限模型，不能继续走任意 published version。

## 本轮未覆盖 / 延期

- **archived material version 历史只读回放仍延期到 Phase 4。**
  - 当前实现仍要求 `SalesTrainerMaterialVersion.status == "published"`。
  - 历史 submission 的 `material_snapshot` 虽已冻结，但本轮没有新增正式“历史材料回放”接口，也没有把 archived version 通过 learner 文件接口伪装成可读。
  - 这样做是刻意 fail-closed，避免在未定义回放策略前把历史访问做成伪成功。
- learner-level scope 仍未闭环。
  - 原因：当前 `sales_trainer` 后端没有稳定 learner-level 真源或模块过滤输入。
  - 风险：后续如果 path/module 开始按 learner-level 分层，本轮 material file policy 需要再补一层过滤。

## 验证关注点

- learner 可下载当前 active path 中自己可进入模块绑定的 published material version。
- learner 不能下载锁定模块材料、未绑定 published 材料。
- manager 403。
- content_admin / ops 仍可读取 published 材料。
- draft / archived version 继续 404，不做历史回放伪成功。
