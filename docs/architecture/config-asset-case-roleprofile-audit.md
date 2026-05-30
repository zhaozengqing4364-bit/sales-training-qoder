# Config Asset Center — CaseItem / RoleProfile 前端审计

> **Issue**: [#100](https://github.com/zhaozengqing4364-bit/sales-training-qoder/issues/100) — Lane L6（仅前端）  
> **审计日期**: 2026-05-27  
> **结论**: **通过** — 主编辑面均为结构化表单，符合 `config-asset-center.md`「无 JSON 编辑」原则；无需结构性改造。

---

## 1. 审计范围

| 路由 | 页面职责 |
|------|----------|
| `/admin/curriculum-practice/case-items` | 训练案例库列表（Index） |
| `/admin/curriculum-practice/case-items/new` | 新建案例 |
| `/admin/curriculum-practice/case-items/[id]/edit` | 编辑草稿案例 |
| `/admin/curriculum-practice/case-items/import` | CSV 批量导入（独立入口） |
| `/admin/curriculum-practice/role-profiles` | 客户角色库列表（Index） |
| `/admin/curriculum-practice/role-profiles/new` | 新建角色画像 |
| `/admin/curriculum-practice/role-profiles/[id]/edit` | 编辑草稿角色画像 |
| `/admin/curriculum-practice/role-profiles/import` | CSV 批量导入（独立入口） |

**不在本次范围**: SituationPack、Persona 管理页（Issue 明确排除）。

---

## 2. 路由与 Admin 模式合规

两资产均遵循 [admin-console-patterns.md](../../.trellis/spec/frontend/admin-console-patterns.md)：

- **列表页**仅承载搜索、筛选、发布/归档/复制；无内嵌完整表单。
- **创建/编辑**在独立 `/new`、`/[id]/edit` 路由，由 `ContentAssetFormPage` 承载。
- **批量导入**在独立 `/import`，使用 CSV 文本区（运维批量场景），**不是**日常主编辑面。

对比：同目录下 `roleplay-situation-packs` 仍使用 `JsonEditorWithValidation`；CaseItem / RoleProfile **未**复用该模式。

---

## 3. 主编辑面：结构化表单

### 3.1 CaseItem（`CaseItemForm`）

实现：`web/src/components/admin/curriculum-practice/case-item-form.tsx`  
编排：`ContentAssetFormPage` → `api.admin.createCaseItem` / `updateCaseItem`

| API 字段 | 表单控件 | 说明 |
|----------|----------|------|
| `industry` | 单行文本 | |
| `customer_role` | 单行文本 | 标签注明「文本剧本，非角色库」 |
| `company_profile` | 多行文本 | |
| `hidden_information` | 多行文本 | |
| `pain_points` | 逗号分隔 → `string[]` | `refsFromText` |
| `objections` | 逗号分隔 → `string[]` | |
| `success_criteria` | 逗号分隔 → `string[]` | |
| `allowed_disclosure_policy.phases` | 逗号分隔阶段名 | **非** JSON 编辑器；提交时组装为 `{ phases: string[] }` |
| `content_hash` | 单行文本 | 治理哈希，运维可手填或由复制流程生成 |

与后端 `CaseItemBase`（`curriculum_practice/schemas.py`）字段一一对应，无遗漏必填项。

### 3.2 RoleProfile（`RoleProfileForm`）

实现：`web/src/components/admin/curriculum-practice/role-profile-form.tsx`

| API 字段 | 表单控件 | 说明 |
|----------|----------|------|
| `role_name` | 单行文本 | |
| `persona_ref` | `PersonaRefPicker` | 可选弱关联；保存前 `validateRoleProfilePersonaRef` |
| `pressure_level` | `<select>` low/medium/high | |
| `communication_style` | 多行文本 | |
| `knowledge_boundary` | 逗号分隔 → `string[]` | |
| `behavior_rules` | 逗号分隔 → `string[]` | |
| `voice_style_hint` | 单行文本 | |
| `content_hash` | 单行文本 | |
| `role_type` | （固定） | 表单层写死 `customer`，与 API `Literal["customer"]` 一致 |
| 声音克隆 | 仅编辑页展示 | `voice_name` / `voice_sample_url` / `voice_audio_base64` / `voice_content_type`；独立按钮调 `cloneRoleProfileVoice`，不混入主保存 payload |

与后端 `RoleProfileBase` 字段对齐。`voice_id` / `voice_sample_url` 为克隆结果回写，非主表单必填。

---

## 4. 未使用 JSON 主编辑器的证据

- `case-item-form.tsx`、`role-profile-form.tsx` 仅使用 `input` / `textarea` / `select` 与 `PersonaRefPicker`。
- `web/src/app/admin/curriculum-practice/case-items/**` 与 `role-profiles/**` 路由文件无 `JsonEditorWithValidation` 引用。
- 同模块内 JSON 编辑器仅出现在 `examiner-agents/`（考官策略块），与本案资产隔离。

---

## 5. 已知局限（非阻塞）

| 项 | 说明 | 建议 |
|----|------|------|
| 列表项逗号分隔 | 痛点/异议等以逗号输入，复杂条目可能需转义习惯 | 后续可加「逐条添加」chip UI，非 Issue #100 范围 |
| `allowed_disclosure_policy` | 仅编辑 `phases` 子字段；若后端扩展其它键需再加表单项 | 与当前 schema 校验一致 |
| `role_type` 不可选 | API 仅支持 `customer` | 符合领域模型 |
| CSV 导入 | 批量场景仍为平面 CSV，非 JSON | 符合「Import ≠ View」；非主编辑面 |
| 无只读 Detail 页 | 草稿走 `/edit`，已发布靠复制为新草稿 | 与现有 content-asset 模式一致 |

---

## 6. 测试覆盖

集中测试文件：`web/src/app/admin/curriculum-practice/content-assets-page.test.tsx`

- Index：CaseItem / RoleProfile 列表、发布/归档/复制、已发布不可直接编辑。
- Form：CaseItem 创建字段提交、RoleProfile Persona 校验、声音克隆。
- Import：CSV 行级错误与成功导入。

Issue #100 补充：断言创建页渲染结构化字段标签，且不存在 `(JSON)` 类 JsonEditor 标题。

验证命令：

```bash
cd web && npm test -- content-assets-page
```

---

## 7. 审计结论

| 检查项 | 结果 |
|--------|------|
| 主编辑面为结构化表单 | ✅ |
| 非 JSON 编辑器为主表面 | ✅ |
| 路由符合 Index / new / edit / import 分离 | ✅ |
| API 字段与表单映射完整 | ✅ |
| 需代码修复的缺口 | **无** |

**签署**: Lane L6 审计通过；可继续 Config Asset Center Phase 3.3 下游任务（PracticeTemplate 组装、Import/Export 等）。
