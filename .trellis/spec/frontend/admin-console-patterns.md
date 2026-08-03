# Admin Console Patterns

> Interaction architecture for the operator console (`web/src/app/admin/`). Separates pages by **user intent**, not by technical CRUD verbs. Complements visual rules in `.kiro/steering/frontend-principles.md`.

Nav source of truth: `web/src/components/layout/admin-sidebar.tsx`.

---

## Core Principle: Intent-Based Surfaces

The first design question for an admin page is not “can we fit CRUD on one screen?” but **what is the operator trying to do right now**. Different intents belong on different routes or surfaces. Do not stack unrelated intents in one scroll flow.

| User intent | Typical actions | Where it belongs |
|-------------|-----------------|------------------|
| **Browse / search** | Search, filter, paginate, status overview | Index list page |
| **View** | Read-only summary, relationships, audit info | Detail hub (`/[id]`) or Overview tab |
| **Create** | Full form, pick related assets | Dedicated `/new` page or simple-entity modal |
| **Edit** | Change fields, save draft | Dedicated `/[id]/edit` page or Edit tab |
| **Bulk import** | Upload file, map fields, async job | **Dedicated `/import` route** — not inline on list or detail |
| **Bulk export** | Select scope, download | Secondary header action on list or analytics page |
| **Ops / diagnostics** | Upload docs, retry index, test retrieval | Sub-resource route or Ops tab — not on list page |
| **Global config** | Change policy, rules, defaults | Policy-center single-purpose page (thin shell + dedicated console) |

---

## Five Hard Rules

These are non-negotiable for new admin pages and refactors. `trellis-check` should reference them.

1. **List pages are Index only** — table/cards + search/filter + navigation to create/detail/import. No full create/edit forms on the list page.
2. **Import is separate from View** — import must not share the main surface with list browsing or detail viewing. Modals are not acceptable for import; import is its own task flow.
3. **Edit and Detail may merge, but must be separated by tab or route** — complex entities need at least `overview` (read-only) and `edit` (form). Simple entities may use `[id]` as the edit page, but the list page still must not embed edit forms.
4. **Sub-resources get sub-routes** — e.g. knowledge base documents, dictionary, retrieval diagnostics belong at `[id]/documents`, `[id]/dictionary`, `[id]/diagnostics`, not stacked on a single `[id]` god page.
5. **Policy center vs business assets** — global policies are edited in 策略中心 (Policy) pages. Asset pages only **bind/reference** policies, show read-only previews, and cross-link (see `retrieval-strategies` as the reference pattern).

---

## Intent Routing (Reference)

```mermaid
flowchart TB
  subgraph index [Index_ListPage]
    search[Search_Filter]
    table[Table_or_Cards]
    quickActions[Quick_Toggle_Delete]
  end

  subgraph mutations [Mutation_Entries]
    create["/new or CreateModal"]
    import["/import or ImportWizard"]
    edit["/[id]/edit or EditTab"]
  end

  subgraph detail [Detail_Hub]
    overview[Overview_ReadOnly]
    subResources[SubRoutes_Tabs]
  end

  index -->|"row click / 查看"| overview
  index -->|"新建"| create
  index -->|"批量导入"| import
  overview -->|"编辑"| edit
  overview --> subResources
```

---

## Standard Route Tree

Use `prompts` as the baseline; extend with import and sub-resources where needed.

```
/admin/{resource}                 → Index list (light)
/admin/{resource}/new             → Create (complex forms)
/admin/{resource}/import          → Bulk import (file + job status)
/admin/{resource}/[id]            → Detail hub (read-only summary + tab nav)
/admin/{resource}/[id]/edit       → Full edit (or merge into [id] as edit tab)
/admin/{resource}/[id]/{sub}      → Sub-resource (documents / chapters / bindings …)
```

Reference implementation: `web/src/app/admin/prompts/`.

---

## Modal vs Dedicated Page

| Condition | Use modal | Use dedicated page |
|-----------|-----------|-------------------|
| ≤ 4 fields, no asset pickers | Yes (e.g. create KB name only) | — |
| Multiple asset pickers, long text, multi-step validation | — | Yes |
| Bulk import / async job | — | Yes — must be `/import` or equivalent |
| Publish gate / gate error list | — | Yes — needs stable, shareable URL |

---

## In-Page Layout: Bento Box

Every admin page uses three layers, aligned with `.kiro/steering/frontend-principles.md`:

```
┌─ PageHeader ─────────────────────────────────────┐
│ Title + one-line scope description               │
│ Primary: 新建 / 进入配置   Secondary: 导入 / 导出 │
└──────────────────────────────────────────────────┘
┌─ ContextBar (optional) ──────────────────────────┐
│ Governance banner / publish gate / page-specific │
│ context only — not cross-page setup wizards      │
└──────────────────────────────────────────────────┘
┌─ MainSurface ────────────────────────────────────┐
│ Single primary task for this page:               │
│ list OR form OR import OR console                │
└──────────────────────────────────────────────────┘
```

- **Header Primary** — only the main task entry for this page (list → 新建; import page → choose file).
- **Import button on list** — navigation only (`router.push('.../import')`); never expand inline upload on the list.
- **Row actions** — enable/disable, set default, delete confirm only; do not edit core fields inline.

---

## Application by Sidebar Category

From `admin-sidebar.tsx`:

### 业务资产 (Assets)

Entity resources: 智能体管理, 角色管理, 知识库管理, 训练案例库, 客户角色库, 课程训练模板, 学习内容管理, 题库管理, AI 考官管理, PPT 演练管理, etc.

- Index list + `[id]` hub + sub-routes where needed.
- Assembly resources (templates, case items): create/edit on dedicated pages; list shows cards and publish status only.
- `CurriculumConfigChecklist` is a **cross-page setup wizard** — show it only on the **课程训练模板** index (`/admin/curriculum-practice/templates`) or a future dedicated setup hub. Individual asset index pages (case items, role profiles, examiner agents, learning contents, test bank) are steps *inside* the checklist; do not render the full checklist on those routes. Strategy-center (Policy) pages must never include it.

### 策略中心 (Policy)

Rules, strategies, global defaults: 提示词管理, 业务规则, 评分规则集, 治理矩阵, 语音策略, PPT AI 策略, 检索策略, etc.

- Single-purpose config pages (reference: `retrieval-strategies` → `KnowledgeAnswerConsole`).
- List + `/new` + `/[id]/edit` (prompts pattern).
- Do not embed editable global policy inside asset detail pages — read-only preview + link only.

### 运营分析 (Analytics)

训练记录, 数据分析, 课程分析, 主管训练.

- Read-only first; export is a separate dialog or page, not mixed with detail browsing.
- Session snapshot detail in a dialog (e.g. records Eye icon) is acceptable; export stays a distinct header entry.
- When analytics pages depend on governed backend policy, display the effective policy diagnostics returned by the API and link to `management_entry`; do not duplicate thresholds, labels, or remediation rules in page code.

### 组织与权限 / 系统治理 (Org & System)

用户管理, 系统设置, 操作日志.

- Users: `/users` + `/users/[id]` (good existing split).
- Settings / Logs: single-page console, no CRUD list pattern.

---

## Current Page Compliance Gap Table

Snapshot for prioritizing refactors. **Compliance target** = follows five hard rules and route tree above.

| Module (sidebar label) | Route | Current pattern | Main gap | Target shape |
|------------------------|-------|-----------------|----------|--------------|
| **提示词管理** (Prompts) | `/admin/prompts` | Governance console + `/new` + `/[id]/edit` + `/bindings` | List includes governance health and read-only impact preview by design; bindings already separate | Keep list as policy cockpit; do not reintroduce inline binding wizard |
| **角色管理** (Personas) | `/admin/personas` | List modal + `[id]` large form | `[id]` aggregates too many config blocks | `[id]` overview + tabs/sub-routes |
| **智能体管理** (Agents) | `/admin/agents` | List modal + `[id]` large form | Same as personas | `[id]` overview + tabs/sub-routes |
| **知识库管理** (Knowledge) | `/admin/knowledge` | List modal + `[id]` god page | Documents, dictionary, diagnostics, strategy preview on one page | `[id]` hub + `documents` / `dictionary` / `diagnostics` |
| **学习内容管理** (Learning Contents) | `/admin/learning-contents` | Inline create form on list | Create mixed with list | `/new` + list index only |
| **课程训练模板** (Templates) | `/admin/curriculum-practice/templates` | Form + list same page | No deep link; edit scrolls to top | `/new`, `/[id]/edit` |
| **题库管理** (Test Bank) | `/admin/test-bank` | Categories + import + questions one page | Classic anti-pattern | Split `categories`, `import`, `questions` or tab routes |
| **检索策略** (Retrieval Strategies) | `/admin/retrieval-strategies` | Thin page + console | **Compliant** — keep as Policy template | Maintain; use as reference |
| **训练记录** (Records) | `/admin/records` | List + detail dialog + export dialog | Mostly compliant | Keep; do not conflate export with import |

Other asset entries (case items, role profiles, examiner agents, presentations) should follow the same Assets rules when touched; audit them against this table in future issues.

---

## Anti-Patterns

Do not add or extend these patterns in new work:

| Anti-pattern | Why it fails | Fix |
|--------------|--------------|-----|
| **God page** | One `[id]` scrolls through unrelated ops, config, and diagnostics | Sub-routes or tabs per intent |
| **List + form same page** | Operator cannot bookmark, share, or reason about “create vs browse” | `/new` or modal (simple only) |
| **Inline import on list** | Import is a multi-step job flow, not a table accessory | `/import` route |
| **Fake filter dialog** | Filters that should persist in URL/state hidden behind a modal | ContextBar or inline filters on Index |
| **Editable global policy on asset detail** | Blurs Policy vs Assets boundary | Read-only preview + link to 策略中心 |
| **Row inline edit of core fields** | Breaks auditability and validation gates | Navigate to edit tab/page |

---

## Recommended Reusable Components

Prefer these over one-off UI when building admin surfaces:

| Component | Path | Use when |
|-----------|------|----------|
| `ConfirmDialog` | `components/ui/confirm-dialog.tsx` | Destructive or irreversible actions — never `window.confirm` |
| `ContentAssetStatusGuide` | `components/admin/curriculum-practice/content-asset-status-guide.tsx` | Published/draft/archived asset cards with immutability copy |
| `AssetGovernanceOverview` | `components/admin/asset-governance.tsx` | Publish/status summary on asset index pages |
| `AdminAssetRefPicker` | `components/admin/asset-ref-picker.tsx` | Picking linked assets in create/edit forms |
| `PersonaRefPicker` | `components/admin/persona-ref-picker.tsx` | Persona binding in templates and agents |
| `KbMultiRefPicker` | `components/admin/kb-multi-ref-picker.tsx` | Multi knowledge-base selection |
| `KnowledgeAnswerConsole` | `components/admin/knowledge-answer/knowledge-answer-console.tsx` | Policy-center tabbed console (retrieval strategies template) |
| `CurriculumConfigChecklist` | `components/admin/curriculum-config-checklist.tsx` | Curriculum setup readiness wizard — **templates index only** (not per-asset index pages) |
| `CurriculumConfigWizard` | `components/admin/curriculum-config-wizard.tsx` | Guided multi-step curriculum setup (does not replace per-route separation) |

---

## Verification (Documentation / PR)

When adding or refactoring an admin page:

1. Name the primary **intent** for each route segment.
2. Confirm list page has no full create/edit form and no inline import.
3. Confirm import (if any) has its own route or dedicated page.
4. Confirm Policy edits live under 策略中心, not asset detail.
5. Reference this spec in PR description; `trellis-check` may ask for compliance notes.

---

## Published Asset Change Workflow

Curriculum assets (`CaseItem`, `RoleProfile`, `ExaminerAgent`) and `PracticeTemplate` follow **publish immutability**: published records cannot be edited in place because runtime snapshots bind by ID + content hash.

| Operator intent | Preferred action | UI placement |
|-----------------|------------------|--------------|
| Change published content | **Duplicate → edit draft → update template bindings → republish template** | Primary button on published rows: 「复制为新草稿」 |
| Emergency revert | **Unpublish** (secondary, strong confirm) | Lists referencing published templates before acknowledge |
| Template binding change | Save template draft + **republish template** | Amber `AdminContextBar` on template edit when case/role refs change |

**Do not** encourage unpublish as the default change path. Duplicate preserves existing `curriculum_snapshot` references until the operator explicitly rebinds templates.

---

## In-Flow Create, Then Governed Follow-Up

When an asset page needs a governed policy that does not yet exist, follow the repository's in-flow completion rule:

1. Create the minimum valid object in the current drawer or inline surface.
2. Bind it to the current work object.
3. Persist the current work object's server-side draft and wait for the returned revision.
4. Offer a cross-link such as 「去完善提示词」 to the dedicated policy editor.

The follow-up link must not weaken persistence semantics:

- If navigation opens a new tab after an async save, synchronously reserve `about:blank` from the click event before awaiting; otherwise real browsers may block it.
- Navigate the reserved tab only after draft persistence succeeds. Close it on save failure, conflict, component close, or unmount.
- A toast is not sufficient evidence for an important cross-surface outcome. Keep an inline success or partial-failure record.
- For revisioned policies, distinguish “保存 working revision” from “发布为运行时生效版本”. If the user action promises both, call both APIs and report partial failure truthfully.

Reference flow: newcomer-training path scoring-standard quick-create → path draft save → recording scoring-standard editor → save and publish.

---

## Governed Policy Diagnostics

Domain settings pages may show read-only snapshots of backend-managed policies when the API returns a diagnostic payload such as `phase2_policy`.

Required behavior:

- Render values from the API payload (`source`, `config_version`, `fallback_applied`, `fallback_reason`, thresholds), never page-local constants.
- Show a navigation link to `management_entry` when provided.
- Keep edits in the policy-center/business-rule surface, not the domain settings or analytics page.
- Treat missing diagnostics as unknown/read-only, not as permission to invent defaults in the page.
- Add a page test that proves the values shown came from the mocked API payload.

**API surfaces** (admin):

- `POST /case-items|role-profiles|examiner-agents/{id}/duplicate`
- `POST .../unpublish` with optional `{ acknowledge: true }` when published templates still reference the asset
- `GET .../template-references` for preflight in confirm dialogs

## Scenario: Newcomer Foundation Admin Workspace

### 1. Scope / Trigger

- Trigger: changing `/admin/newcomer-training`, its navigation, Path editor, content/questions/cohorts/assessment/review/release/settings workspaces, or their shared DTO/ViewModel layer.
- The visual source of truth remains the existing project shell, tokens, forms, tables, Drawer, Inspector and status components. Do not create a parallel dashboard aesthetic or prototype chooser.

### 2. Signatures

```text
/admin/newcomer-training                 -> actionable overview
/admin/newcomer-training/paths           -> path index
/admin/newcomer-training/paths/[id]/edit -> three-pane editor
/admin/newcomer-training/content         -> Source / LearningUnit workspace
/admin/newcomer-training/questions       -> generation batches / candidate review
/admin/newcomer-training/audio           -> PPT/Demo 讲解材料与评分方案
/admin/newcomer-training/coaches         -> structured Coach Profile authoring
/admin/newcomer-training/scenarios       -> three-segment async customer scenarios
/admin/newcomer-training/cohorts         -> Cohort index and in-flow assignment
/admin/newcomer-training/cohorts/[id]    -> Enrollment/progress/import workspace
/admin/newcomer-training/assessments     -> durable task operations
/admin/newcomer-training/reviews         -> Readiness queue/dossier
/admin/newcomer-training/releases        -> ReleasePlan process/approval
/admin/newcomer-training/settings        -> governed configuration links/status
```

The frontend consumes `capabilities`, `workspace`, resource/path/cohort projections and typed domain methods. Permission/action availability must not be re-derived from a role string.

The single global entry is a product boundary, not a one-page boundary. Desktop uses a persistent local module navigation and narrow viewports use an accessible module selector. Authorized users must be able to discover 训练方案、内容中心、题库与测验、讲解与评分、AI 教练、客户场景、学员与班级、评测与复核、发布与治理 without relying on a horizontally clipped tab strip. Legacy `/admin/sales-trainer/*` pages never return to this navigation.

Target task capabilities are `view_content`, `edit_content`, `review_content`, `view_question_bank`, `edit_questions`, `review_questions`, `edit_quizzes`, `edit_audio_materials`, `edit_scoring_schemes`, `edit_coach_profiles`, `edit_async_scenarios`, `edit_paths`, `manage_cohorts`, `retry_assessments`, `regrade_results`, `review_readiness`, `publish_releases`, `rollback_releases`, and `view_sensitive_audit`. Existing coarse capabilities may remain during migration, but UI must consume the backend projection and must not infer these actions from role strings. Prompt/model/provider/secret governance stays behind separate high-risk authorization.

### 3. Contracts

- The overview contains deduplicated actionable work with reason, affected object and next action; it is not a grid of decorative metrics.
- The Path editor is Structure → typed editor → preview/validation/impact. One selected work object and one dominant save/validate/release action are visible at a time; raw JSON is never the ordinary editor.
- Missing resources are completed in the current Drawer/Inspector: search, preview, quick-create minimum working object, auto-bind and preserve the Path draft. This applies to LearningUnit、Quiz、AudioMaterial、ScoringScheme、CoachProfile and Scenario. Source/Unit/Quiz and other legal working references are permitted for composition; formal effect still requires ReleasePlan. A backend `quick_create_supported=true` without a frontend renderer is a visible contract error, not a reason to hide the action.
- Source file upload shows durable parse status, permits leaving the page and keeps a result location. Failure preserves the resource/input and offers an explicit recovery path.
- Question generation submits only safe Source/Unit/prompt-policy/model-policy selections. Prompt text, Provider payload, internal task type, contract hash and opaque IDs are never rendered as user explanations. Candidates remain draft until human review.
- Seed resources, list options and routes are runtime prerequisites only. Completion evidence for an Authoring workspace requires create, save working revision, validate, compare/reference impact, archive, permission denial and ReleasePlan hand-off through the actual rendered flow.
- Cohort import and candidate bulk review always preview first and persist per-item success/failure. Partial success is never displayed as complete success.
- Release UI never calls Path/resource direct publish. It shows dependency graph, blockers, impact and stable rollback target before confirm.
- Every navigation item and command is gated by the backend projection; denied workspaces show an explicit permission state and help route without fetching sensitive detail.

### 4. Validation & Error Matrix

| Condition | Required UI behavior |
|---|---|
| Capability absent | hide unavailable navigation/action; direct URL shows permission state, not empty data |
| Initial loading or filtered no-result | stable skeleton or explanatory no-result with filter reset |
| Save conflict/stale projection | preserve edits, show conflict details and reload/compare action |
| Source parsing/generation task pending | persistent status/result link; page may be left safely |
| Recoverable task failure | preserve input/object and offer authorized retry/cancel path |
| Bulk items partly rejected | durable per-item result grouped by success/failure |
| Release blocker | locate object/Stage/Activity/field; publish remains disabled |
| Publish/rollback succeeds | persistent plan record and result location, not toast-only |
| Long labels/file names/values | wrap or truncate with accessible full value; primary action remains reachable |

### 5. Good / Base / Bad Cases

- **Good**: an editor uploads a Source, follows its persistent parse task, creates an Anchor and Unit in-flow, binds it to a Path, reviews blockers and publishes one ReleasePlan without leaving the work context.
- **Base**: a manager imports learner emails, previews valid/invalid rows, confirms valid rows, and sees a persistent partial-result table with reasons for rejected rows.
- **Bad**: role strings drive buttons, a quick-create forces navigation and loses dirty Path edits, the browser submits raw Prompt/hash, or a success toast hides failed bulk items.

### 6. Tests Required

- Navigation/capability tests prove allowed, denied and direct-route permission behavior.
- Path editor tests cover keyboard selection, reorder controls, dirty/submitting/conflict, typed field errors, resource quick-create/bind and no direct publish action.
- Content/question tests cover durable task pending/recovery, safe policy options, candidate batch filtering, source references and no internal-term leakage.
- Cohort/assessment/release tests cover preview-confirm, partial results, frozen Enrollment copy, task result locations, blockers and rollback.
- Rendered verification covers desktop/narrow viewport, 200% zoom, keyboard/focus return, long Chinese/English text and realistic large lists; final release evidence is produced by the newcomer admin/learner Playwright suites and `.sisyphus/evidence/task-9-playwright-report.html`.

### 7. Wrong vs Correct

#### Wrong

```tsx
{user.role === "admin" && <Button onClick={() => publishResource(id)}>发布</Button>}
```

This duplicates authorization and bypasses ReleasePlan, dependency preview and audit.

#### Correct

```tsx
{capabilities.publish_release ? (
  <Link href="/admin/newcomer-training/releases">校验发布计划</Link>
) : (
  <PermissionState help={capabilities.permission_help} />
)}
```

The backend projection owns capability truth and the user enters the persistent ReleasePlan workflow.

---

## Related Docs

- Visual / glass UI: `.kiro/steering/frontend-principles.md`
- App Router map: `web/src/app/AGENTS.md` (Admin Console Patterns summary)
- Components: `.trellis/spec/frontend/component-guidelines.md`
- Nav labels: `web/src/components/layout/admin-sidebar.tsx`
