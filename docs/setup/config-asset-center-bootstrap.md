# Config Asset Center Import-First Bootstrap

本文档描述新环境如何用 Config Asset Center 导入包初始化 Presales CIO 首访闭环训练，替代历史 seed 脚本直接写库。

## 适用范围

- 导入包：`backend/config-assets/presales-cio-first-visit.export.json`
- API：`/api/v1/admin/config-assets/import`
- 权限：执行账号必须具备 `config_asset.import`；若启用 `publish_after_import=true`，还必须具备 ConfigBundle publish 与相关 native lifecycle publish/activate 权限。
- 审计：Import 写入 `SystemLog.action=config_asset_import`；SituationPack publish 写入 `ConfigBundleAuditLog`；native lifecycle 资产通过各自 service audit 或 domain audit 记录。

## 1. Dry Run

先用 dry run 验证 schema、topology、依赖解析与冲突策略。dry run 必须零写入，返回的 `id_mapping` 仅用于预览。

```bash
jq -n --slurpfile bundle backend/config-assets/presales-cio-first-visit.export.json '{
  bundle: $bundle[0],
  options: {
    dry_run: true,
    conflict_strategy: "new_version",
    publish_after_import: false,
    import_reason: "bootstrap dry_run: presales cio first visit"
  }
}' | curl -X POST "$BASE_URL/api/v1/admin/config-assets/import" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d @-
```

如果调用方没有 `jq`，请先把导出包作为 `bundle` 字段加载后再发送。验收标准：

- `failed == 0`
- `errors == []`
- `audit_recorded == false`
- `results[*].status` 只出现 `imported` 或 `skipped`

## 2. Apply Import

确认 dry run 后执行真实导入。默认冲突策略使用 `new_version`，避免覆盖目标环境已发布语义。

```bash
curl -X POST "$BASE_URL/api/v1/admin/config-assets/import" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d @payload.json
```

`payload.json` 结构：

```json
{
  "bundle": {},
  "options": {
    "dry_run": false,
    "conflict_strategy": "new_version",
    "publish_after_import": false,
    "import_reason": "bootstrap: presales cio first visit"
  }
}
```

将 `bundle` 替换为 `backend/config-assets/presales-cio-first-visit.export.json` 的完整 JSON 对象。

验收标准：

- `failed == 0`
- `audit_recorded == true`
- `id_mapping` 包含 `agent`、`voice_runtime_profile`、`scoring_ruleset`、`knowledge_base`、`learning_content`、`question_category`、`question_item`、`examiner_agent`、`situation_pack`、`persona`、`practice_template`
- `SystemLog.action=config_asset_import` 可查到本次 `import_reason`

## 3. Publish After Import

批量发布属于 HITL-Approve 操作。必须先保存 dry run 结果，并在 `import_reason` 中引用审批记录或 issue completion note。

```json
{
  "bundle": {},
  "options": {
    "dry_run": false,
    "conflict_strategy": "new_version",
    "publish_after_import": true,
    "import_reason": "bootstrap publish_after_import: presales cio first visit; hitl=C3,C4"
  }
}
```

发布语义：

- ConfigBundle-governed SituationPack 走 ConfigBundle validate/publish。
- PracticeTemplate 走 `PracticeTemplateService.publish_template()`，并冻结 `published_asset_refs`。
- Native lifecycle 资产必须由各自 service 创建或发布；禁止 importer 直接构造 ORM row 绕过 service。

验收标准：

- `report.errors` 不包含 `[PUBLISH_*]`
- `ConfigBundleAuditLog` 有 `bundle_key=roleplay.situation_packs.ruleset` 的 publish 记录
- Admin PracticeTemplate 页面可看到 `制造业 CIO 首次拜访闭环训练`
- 新建训练会话时 runtime snapshot 中可看到 `situation_pack_code=first_visit`

## 4. Rollback

Import 本身不是跨拓扑单事务回滚。回滚按资产类型处理：

- SituationPack：使用 ConfigBundle rollback 到上一 published snapshot。
- PracticeTemplate：归档误导入模板，或重新导入旧导出包创建 `new_version`。
- ScoringRuleset：通过 scoring ruleset rollback 或重新发布上一 active ruleset。
- Agent、Persona、KnowledgeBase、LearningContent、Question、ExaminerAgent：走对应 Admin/service 的 archive、unpublish 或 inactive/draft-equivalent 路径。

回滚必须记录 reason，并保留原始 ImportReport、`id_mapping` 和 audit trace id。

## 5. Seed 脚本策略

以下脚本已变成 deprecated wrapper，默认安全退出并提示使用 Import API：

- `backend/scripts/seed_presales_mvp.py`
- `backend/scripts/seed_presales_cio_first_visit.py`

仅允许本地救援或历史 fixture 重建时显式使用 `--legacy-seed-unsafe`。运行该参数必须在变更记录中说明原因、影响范围和回滚路径。

## 6. 双读观测启动

staging 启动 SituationPack 双读观测时，先保持 B1 authority 关闭：

```bash
export SITUATION_PACK_DUAL_READ=true
export SITUATION_PACK_READ_ORM=true
export SITUATION_PACK_B1_AUTHORITY=false
cd backend
PYTHONPATH=src python scripts/start_situation_pack_dual_read_observation.py --apply --reason p0-dual-read-start
```

脚本通过条件：

- `status` 为 `started` 或 `already_started`。
- `latest_projection_sync.status == "ok"`。
- `dual_read.lookup_count == dual_read.matched_count`。
- `dual_read.mismatch_count == 0`。
- `dual_read.authority == "phase_a"`。
- `observation_started_at` 非空。

脚本返回 `blocked` 或非 0 exit code 时，不得开启 `SITUATION_PACK_B1_AUTHORITY`。

## 7. B1 Authority 启动前检查

导入 Presales CIO 包不等于 B1 authority promotion。启用 `SITUATION_PACK_B1_AUTHORITY=true` 前必须满足：

- `SITUATION_PACK_DUAL_READ=true` 已开启观察。
- 最近 14 日 `SystemLog.action=situation_pack_dual_read_mismatch` 为 0。
- projection sync 无未恢复失败。
- `SITUATION_PACK_B1_APPROVAL_ID` 非空，并引用 HITL approval evidence。
- `GET /support/runtime/overview` 中 `config_asset_center.dual_read.promotion_ready == true`。

不满足上述条件时，运行时必须保持 Phase A authority。
