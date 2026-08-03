# Legacy → Foundation 内容生产迁移清单

> 状态：Accepted mapping contract（2026-07-20）。本文件只定义 inspect/dry-run 输入输出，不授权迁移或业务数据修改。

## 对象与字段映射

| Legacy 输入 | Foundation 目标 | Stable migration key | 必须保留 | 自动映射条件 | 阻塞条件 |
|---|---|---|---|---|---|
| `SalesTrainerMaterial` + 有效 published `SalesTrainerMaterialVersion` | `SourceDocument` + `SourceDocumentRevision`；PPT/PPTX 的 `content_kind=slide_deck` | `sales_trainer + org + material + material_id + version_id/file_hash` | legacy ID、版本、文件名、可信 MIME、大小、hash、purpose、来源血缘 | 同组织目标中同 hash 唯一；同名同 hash 可复用 | 目标组织未确定、文件/版本/hash 缺失、同名不同 hash、同 hash 多目标、签名/解码失败 |
| active `newcomer_training_path_orchestration` revision | 从当前 Foundation published Path 克隆的新 working `PathRevision` | `sales_trainer + org + path + logical_id + revision_id/payload_hash` | revision_no、payload_hash、活动顺序/依赖/必修语义 | v2 stable activity key 唯一且无语义冲突 | 无 Foundation 基线 Path、重复 key、前置条件不可表达、依赖未完成 |
| `石犀ppt讲解` | `audio_material` + `scoring_scheme` + v2 `audio_assessment` Activity | path migration key + legacy activity ID | 标题、目标、材料引用、时长/尝试语义、评分引用 | PPT source、材料和评分均通过新 Schema/ReleasePlan 校验 | PPT 缺失、评分不可验证、能力映射缺失、跨组织引用 |
| `demo讲解` | Demo Source/脚本 + 独立 `audio_material` + `scoring_scheme` + v2 `audio_assessment` Activity | path migration key + legacy activity ID | 标题、目标、Demo/脚本引用、评分引用 | Demo 来源可验证且评分合同完整 | Demo 文件/链接/脚本缺失、评分不可验证、能力映射缺失 |
| `SalesTrainerAudioScorePrompt` 及路径引用 | governed Prompt/Model/Schema exact refs + `scoring_scheme` | `sales_trainer + org + score_prompt + prompt_id + contract_hash/version` | 名称、purpose、状态、版本、安全 contract hash、引用活动 | 新 Prompt/Model/Schema 已发布，变量/输出/维度可通过新评分 Schema 校验 | Prompt 正文无法验证、任意输出、缺模型/Schema、维度或阈值不闭合 |

## 生命周期与发布边界

1. Inventory 只输出安全元数据、hash、引用、冲突和预计对象数；不输出 storage key、Source URI、Prompt 正文、文件内容、转写或个人数据。
2. Dry-run 冻结目标组织、输入 hash、目标候选、冲突决策和预计写入，产生 plan/impact hash；仍然零写入业务对象。
3. Apply 只能由后续迁移任务提供，必须显式组织、计划 ID、impact hash、操作者、理由和幂等键。
4. 新对象先成为 working revision；解析、预览、评分/AI 合同和 Path compile 均通过后，才进入 ReleasePlan。
5. ReleasePlan 发布只影响未来 Enrollment；已有 Enrollment、Attempt、Outcome、Evidence 不迁移、不重评。
6. Verify 失败保留旧 active ReleasePlan；不得把部分迁移描述为已切换。

## 权限映射

| 操作 | Capability | 对象范围 |
|---|---|---|
| 查看只读 inventory | `view_sensitive_audit` 或迁移专用受控权限 | 明确目标组织；Legacy 行仍标记 `global_unscoped` |
| 选择/重传来源 | `edit_content` | organization + SourceDocument |
| 审核旧评分合同 | `edit_scoring_schemes` + 高级 AI 合同权限 | organization + ScoringScheme；Prompt 正文单独授权 |
| 合并 Path working revision | `edit_paths` | organization + Path |
| 发布/回滚 | `publish_releases` / `rollback_releases` | organization + ReleasePlan；preview/impact hash + If-Match |

## Inventory 输出真值

标准工具：

```bash
cd backend
PYTHONPATH=src .venv/bin/python scripts/inventory_newcomer_foundation_authoring.py \
  --organization-id <organization_id> \
  --json-output <inventory.json> \
  --markdown-output <inventory.md>
```

命令没有 `apply`/`migrate` 参数；PostgreSQL 使用只读事务，其他测试数据库只执行 `SELECT` 并最终 rollback。结构化输出 Schema 为 `foundation_authoring_inventory_v1`，同一输入和固定生成时间下排序稳定。
