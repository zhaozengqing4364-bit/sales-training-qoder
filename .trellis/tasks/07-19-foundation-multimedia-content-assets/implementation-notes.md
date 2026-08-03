# Implementation Notes

## Page contract

- 目标用户：拥有 `edit_content` 的内容编辑；执行端为已获得新人训练路径访问权的学员。
- 主要任务：在内容工作区创建七类来源资产，查看真实处理状态和受控预览，将 exact revision/anchor 编排成结构化学习单元，再由既有 ReleasePlan 发布。
- 主要对象：`LearningSourceDocument`、不可变的 `LearningSourceDocumentRevision`、`LearningSourceAnchor`、`LearningUnitRevision.content_blocks`、DurableTask。
- 主要操作：上传/创建来源、刷新或重试处理、查看原件/分页预览、保存结构化内容块、发布。
- 失败成本：不得把未解析、部分解析或媒体未解码伪装成 ready；失败保留原件和工作修订；学员访问必须同时通过组织、路径活动和冻结修订校验。

## Decisions

- 继续使用 Learning 作为唯一内容写权威；每页 manifest 写入来源修订，Task 只保存状态和结果摘要。
- 迁移只在 `20260717_1500_006` 后增加字段，不修改既有迁移；旧 `parse_status` 与新 `processing_state` 双写以兼容旧快照。
- 不复用 presentation coach 的文字卡片缩略图。PPTX 使用 python-pptx + Pillow 做受控分页栅格化；旧二进制 `.ppt` 在没有可信转换器时明确拒绝并给出转为 `.pptx` 的恢复动作。
- 文件先分块写入 staging 并完成 hash、签名/OOXML ZIP 与解压炸弹校验，数据库登记、原子落盘和任务入队分别使用短事务/补偿。
- 媒体只有在 ffprobe 解码探测成功且 codec 在 allowlist 内时才进入 ready；运行环境没有探测器时明确失败并可重试，不生成假元数据。
- 学员 DTO 只返回按活动和内容块签名的受控访问路径，不返回 artifact URI、存储路径、文件 hash、解析器或来源修订 ID。
- 新绑定拒绝 archived 来源；既有冻结 Attempt 仍允许读取 archived 学习单元及其 exact 来源。

## Deviations / environment

- 规范索引引用的 `.kiro/steering/backend-principles.md` 与 `.kiro/steering/frontend-principles.md` 在当前仓库不存在；已按 `.trellis/spec/`、根 `AGENTS.md` 和 `DESING.md` 执行，不阻塞当前任务。
- 当前开发容器没有 `ffprobe`/`ffmpeg`/LibreOffice。实现保留部署时探测能力；本地针对性测试使用真实签名样本或显式失败路径，绝不把工具缺失标记为成功。

## Verification evidence

待实现后补充命令、结果、浏览器证据和残余风险。
