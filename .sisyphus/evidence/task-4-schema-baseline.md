# T4 Schema Baseline — report/evaluation canonical truth

Date: 2026-04-15

## Scope

This artifact defines the **canonical schema baseline** for the highest-risk report/evaluation tables and their immediately coupled control-plane table:

- `practice_sessions` (**only** the report-generation control-plane columns)
- `staged_evaluation_results`
- `comprehensive_reports`

This is a **documentation-only** baseline for T6. It does **not** generate migrations and it does **not** change business logic.

## Evidence sources

- ORM truth: `backend/src/common/db/models.py:265-314`, `backend/src/common/db/models.py:559-595`
- Runtime write/read paths:
  - `backend/src/evaluation/services/staged_evaluation.py:156-179`
  - `backend/src/evaluation/services/staged_evaluation.py:250-277`
  - `backend/src/evaluation/services/staged_evaluation.py:330-347`
  - `backend/src/evaluation/services/comprehensive_report.py:53-67`
  - `backend/src/evaluation/services/comprehensive_report.py:294-317`
  - `backend/src/evaluation/services/comprehensive_report.py:616-653`
  - `backend/src/evaluation/api.py:148-180`
  - `backend/src/evaluation/services/report_generation_trigger.py:298-363`
  - `backend/src/presentation_coach/services/presentation_report_service.py:155-166`
- Alembic truth:
  - `backend/alembic/versions/20260204_0900_006_staged_evaluation.py:27-99`
  - `backend/alembic/versions/20260205_0100_009_add_report_columns.py:26-76`
  - `backend/alembic/versions/20260212_0000_013_add_report_generation_status.py:24-51`
- Runtime schema bootstrap / repair:
  - `backend/src/common/db/session.py:103-132`
  - `backend/src/common/db/session.py:137-188`
  - `backend/src/common/db/legacy_schema_repair.py:39-309`
  - `backend/alembic/versions/20260413_1040_029_explicit_legacy_startup_repairs.py:25-36`
- Drift evidence in tests:
  - `backend/tests/integration/test_staged_evaluation_db.py:50-106`
  - `backend/tests/integration/test_staged_evaluation_db.py:168-316`
  - `backend/tests/unit/evaluation/test_staged_evaluation_service.py:418-441`
  - `backend/tests/unit/evaluation/test_comprehensive_report_service.py:330-342`

## Canonical decision rules used here

1. **Runtime write/read path beats historical migration shape** when the code still actively persists or consumes a field today.
2. **Migration-only columns with no current runtime reader/writer are not canonical**, even if old tests still assert them.
3. **Runtime schema repair is evidence of inconsistency, not schema authority**. For these tables, there is no table-specific repair logic; the only live runtime authority is `Base.metadata.create_all`.
4. **PostgreSQL structured payload columns are canonically `JSONB`**, because migration `006` and the integration DB tests already assume PostgreSQL-native semi-structured storage; current ORM `JSON` usage is drift.

---

## 1) Immediately coupled control-plane table: `practice_sessions`

### Canonical scope for T4

Only the report-generation lifecycle columns are in scope here.

| Column | Canonical type | Null / default | Keys / indexes | Evidence / relevance |
|---|---|---|---|---|
| `session_id` | `VARCHAR(36)` | `PRIMARY KEY` | PK | Existing session identity in ORM (`models.py:268`) and the logical parent key for both report tables. |
| `report_status` | `VARCHAR(20)` | `NOT NULL DEFAULT 'pending'` | `CHECK (report_status IN ('pending','processing','completed','failed'))`, `idx_sessions_report_status` | ORM `models.py:296-314`, migration `013:24-51`, runtime updater `report_generation_trigger.py:298-333`. |
| `report_generated_at` | `TIMESTAMPTZ` | `NULL` | none | Set only on completed generation (`report_generation_trigger.py:327-328`). |
| `report_error` | `TEXT` | `NULL` | none | Set only on failures / cleared on non-failed transitions (`report_generation_trigger.py:329-332`). |

### Canonical decision

`practice_sessions` remains the **generation-status control plane**. The high-risk report tables store report/evaluation content only.

### Drift notes

- No drift was found between ORM and migration `013` for these three columns.
- There is still **no actual foreign-key linkage** from the content tables back to `practice_sessions`; the relationship is logical only.

---

## 2) Canonical table: `staged_evaluation_results`

### Canonical shape

| Column | Canonical type | Null / default | Keys / indexes | Why this is canonical |
|---|---|---|---|---|
| `id` | `VARCHAR(36)` | `PRIMARY KEY` | PK | Current runtime write path explicitly sends `id=str(uuid4())` (`staged_evaluation.py:332-343`). ORM also defines `String(36)` (`models.py:565`). |
| `session_id` | `VARCHAR(36)` | `NOT NULL` | `idx_staged_eval_session`, `idx_staged_eval_stage UNIQUE (session_id, stage_number)` | Every runtime read filters by `session_id` and orders by `stage_number` (`staged_evaluation.py:252-256`, `evaluation/api.py:160-163`). |
| `stage_number` | `INTEGER` | `NOT NULL` | part of unique composite index | Runtime uniqueness is per session/stage (`test_staged_evaluation_db.py:261-288`). |
| `start_turn` | `INTEGER` | `NOT NULL` | none | Written by runtime (`staged_evaluation.py:335-337`). |
| `end_turn` | `INTEGER` | `NOT NULL` | none | Written by runtime (`staged_evaluation.py:336-337`). |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT now()` | none | API feedback serializes `eval_item.created_at.isoformat()` without a null guard (`evaluation/api.py:170-176`). Runtime read path already prefers `created_at` over legacy `timestamp` (`staged_evaluation.py:265-269`). |
| `scores` | `JSONB` | `NOT NULL DEFAULT '{}'::jsonb` | none | Runtime requires dict semantics (`staged_evaluation.py:270`, tests exercise PostgreSQL JSON operators in `test_staged_evaluation_db.py:323-349`). |
| `strengths` | `JSONB` | `NOT NULL DEFAULT '[]'::jsonb` | none | Runtime requires list semantics (`staged_evaluation.py:271`). |
| `weaknesses` | `JSONB` | `NOT NULL DEFAULT '[]'::jsonb` | none | Generated at evaluation time (`staged_evaluation.py:156-177`) and consumed by report aggregation (`comprehensive_report.py:420-433`). |
| `suggestions` | `JSONB` | `NOT NULL DEFAULT '[]'::jsonb` | none | Runtime read/write field (`staged_evaluation.py:177`, `staged_evaluation.py:273`, `evaluation/api.py:175`). |
| `summary` | `TEXT` | `NULL` | none | Runtime read/write field (`staged_evaluation.py:178`, `staged_evaluation.py:274`, `evaluation/api.py:174`). |

### Explicit non-canonical / legacy-only columns

These are **not** part of the canonical target shape because there is no current runtime writer or reader that depends on them:

- `timestamp`
- `key_insights`
- `improvement_suggestions`
- `stage_summary`
- `comparison_with_previous`
- `is_fallback`
- `cost_tokens`
- `processing_time_ms`

### Truth comparison

| Surface | What it says today | Drift vs canonical |
|---|---|---|
| ORM (`models.py:559-576`) | `id/session_id/stage_number/start_turn/end_turn/scores/strengths/suggestions/summary/created_at`; no indexes; no `weaknesses`; generic `JSON`; `extend_existing=True` only | Missing `weaknesses`, missing canonical indexes/unique constraint, missing canonical Postgres `JSONB`, and no DB-level uniqueness declaration. |
| Migration `006` (`006_staged_evaluation.py:30-65`) | UUID PK with server default, `timestamp`, `scores/strengths/weaknesses/key_insights/improvement_suggestions/stage_summary/comparison_with_previous/is_fallback/cost_tokens/processing_time_ms`, plus session/stage indexes | Keeps legacy analytics metadata and legacy timestamp name; closest source for `weaknesses` and index intent. |
| Migration `009` (`009_add_report_columns.py:29-46`) | Adds `suggestions`, `summary`, `created_at` on top of the `006` shape | Introduces the fields current runtime needs, but does **not** remove the legacy `006` columns and still leaves `weaknesses` outside the ORM shape. |
| Runtime read/write (`staged_evaluation.py:156-179`, `250-277`, `330-347`) | Generates `weaknesses`, `suggestions`, `summary`; persists everything **except `weaknesses`** because the ORM has no mapped column; reads `created_at` first and falls back to `timestamp` | Active persistence loss: `weaknesses` is produced in memory, aggregated later, but not stored by current ORM write path. |

### Canonical decision for T6

- Keep `id` as an application-generated `VARCHAR(36)` primary key to match the current ORM and runtime writer.
- Keep the **unique** `(session_id, stage_number)` contract from migration `006`.
- Treat `created_at` as the canonical event timestamp; `timestamp` is legacy drift.
- Keep `weaknesses`; it is not optional drift — current report generation depends on it.
- Drop the legacy analytics-only `006` columns listed above unless a later task proves a real reader/writer still needs them.

---

## 3) Canonical table: `comprehensive_reports`

### Canonical shape

| Column | Canonical type | Null / default | Keys / indexes | Why this is canonical |
|---|---|---|---|---|
| `session_id` | `VARCHAR(36)` | `PRIMARY KEY` | PK only | Current runtime lookup/store key in all write/read paths (`comprehensive_report.py:297-317`, `616-653`, `presentation_report_service.py:155-166`), and current ORM already treats it as the PK (`models.py:585`). |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT now()` | none | Runtime stores `report.generated_at` into `created_at` (`comprehensive_report.py:652`) and reads it back as the persisted generation timestamp (`comprehensive_report.py:307`). |
| `overall_score` | `DOUBLE PRECISION` | `NOT NULL` (legacy NULL rows must be backfilled before tightening) | none | API contract requires `overall_score` (`evaluation/schemas.py:82-90`) and both report builders always provide it (`comprehensive_report.py:305-317`, `presentation_report_service.py:155-166`). |
| `dimension_scores` | `JSONB` | `NOT NULL DEFAULT '[]'::jsonb` | none | Current runtime stores list-of-object payloads (`comprehensive_report.py:637-647`). |
| `stage_summaries` | `JSONB` | `NOT NULL DEFAULT '[]'::jsonb` | none | Stored and returned by both sales and presentation report paths (`comprehensive_report.py:647`, `presentation_report_service.py:160`). |
| `key_strengths` | `JSONB` | `NOT NULL DEFAULT '[]'::jsonb` | none | Stored and read today (`comprehensive_report.py:648`, `313`). |
| `key_improvements` | `JSONB` | `NOT NULL DEFAULT '[]'::jsonb` | none | Stored and read today (`comprehensive_report.py:649`, `314`). |
| `recommendations` | `JSONB` | `NOT NULL DEFAULT '[]'::jsonb` | none | Stored and read today (`comprehensive_report.py:651`, `316`). |
| `detailed_feedback` | `TEXT` | `NULL` | none | Stored and read today (`comprehensive_report.py:650`, `315`). |

### Explicit non-canonical / legacy-only columns

These are **not** part of the canonical target shape because current runtime code neither persists nor reads them:

- surrogate `id`
- `generated_at` as a DB column name (API/output concept only; persisted column is `created_at`)
- `total_stages`
- `total_turns`
- `overall_assessment`
- `priority_improvements`
- `trend_summary`
- `personalized_advice`
- `practice_recommendations`
- `estimated_skill_level`
- `trend_analysis`
- `score_timeline`
- `is_fallback`
- `comparison_to_baseline`

### Truth comparison

| Surface | What it says today | Drift vs canonical |
|---|---|---|
| ORM (`models.py:579-595`) | `session_id` PK; `overall_score`, `dimension_scores`, `key_strengths`, `key_improvements`, `recommendations`, `detailed_feedback`, `stage_summaries`, `created_at`; generic `JSON`; `extend_existing=True` | Closest to canonical, but still uses generic `JSON` instead of canonical PostgreSQL `JSONB`, and it does not state any DB-level backfill/default intent. |
| Migration `006` (`006_staged_evaluation.py:67-98`) | UUID surrogate PK + unique `session_id`; `generated_at`; many analytics-summary columns; no `overall_score`, `dimension_scores`, `stage_summaries`, `key_improvements`, `detailed_feedback`, `recommendations` | Entirely different identity model and payload model from current runtime. |
| Migration `009` (`009_add_report_columns.py:48-76`) | Adds `overall_score`, `dimension_scores`, `stage_summaries`, `key_improvements`, `detailed_feedback`, `recommendations`, `comparison_to_baseline` on top of the `006` table | Bridges toward the current service contract, but leaves the legacy `006` columns and surrogate `id` intact. |
| Runtime dataclass + persistence (`comprehensive_report.py:53-67`, `616-653`) | Runtime object uses `generated_at`, current DB model persists that into `created_at`, and lookup is always by `session_id` | Confirms `session_id` is the real identity and `created_at` is the real persisted timestamp; no current persistence or retrieval path uses the `006` analytics columns or `comparison_to_baseline`. |
| Presentation report builder (`presentation_report_service.py:155-166`) | Builds exactly the current runtime report payload (`overall_score`, `dimension_scores`, `stage_summaries`, `key_strengths`, `key_improvements`, `detailed_feedback`, `recommendations`) | Reinforces that canonical shape must stay aligned with the shared runtime report object, not the old `006` table. |

### Canonical decision for T6

- `session_id` is the only canonical primary key; the legacy surrogate `id` and `idx_comprehensive_reports_session` are redundant once `session_id` is the PK.
- Persisted timestamp name is `created_at`; `generated_at` stays an API/runtime object field, not a DB column.
- The canonical content payload is the current runtime object shape plus Postgres-native `JSONB` storage.
- `comparison_to_baseline` is **not canonical today** because it is only a dormant dataclass field plus a migration-added column; there is no active store/read path.

---

## 4) Confirmed drift items that T6 must resolve explicitly

### A. `staged_evaluation_results`

1. **ORM is missing `weaknesses`**, but runtime evaluation generates it and report aggregation consumes it.
2. ORM declares **no unique/index metadata** for `session_id` / `(session_id, stage_number)`.
3. ORM uses generic `JSON`; migration intent and Postgres tests assume PostgreSQL semi-structured storage.
4. Existing migration path leaves both **`timestamp` and `created_at` semantics** in play; runtime already prefers `created_at`.
5. `006` legacy columns still exist in migration truth but are unused by current runtime.

### B. `comprehensive_reports`

1. Migration truth still has a **surrogate UUID `id` + unique `session_id`**, while ORM/runtime already use **`session_id` as the actual PK**.
2. Migration truth still has the **legacy analytics-summary columns** from `006`; runtime never reads/writes them.
3. ORM/runtime persist **`created_at`**, while migration `006` introduced **`generated_at`**.
4. ORM uses generic `JSON`; canonical Postgres target should be `JSONB` for report payload columns.
5. `comparison_to_baseline` exists only as dormant schema/runtime residue; no current store/read path uses it.

### C. Test suite drift

1. `backend/tests/integration/test_staged_evaluation_db.py:50-106` and `168-316` still assert the **old `006`/`009` schema**, not the current runtime contract.
2. `backend/tests/unit/evaluation/test_staged_evaluation_service.py:418-441` assumes DB rows expose `weaknesses`; current ORM does not.
3. `backend/tests/unit/evaluation/test_comprehensive_report_service.py:330-342` still mocks `generated_at` / `comparison_to_baseline` on the DB row even though runtime DB access uses `created_at` and ignores `comparison_to_baseline`.

---

## 5) Runtime schema-repair dependency inventory (exact relevance)

| Surface | Exact relevance to target tables |
|---|---|
| `backend/src/common/db/session.py:103-132` | **High relevance.** Startup always runs `Base.metadata.create_all`, so fresh or partially missing report/evaluation tables can be created from the **current ORM shape**, not from Alembic history. This is the main runtime drift amplifier for the target tables. |
| `backend/src/common/db/session.py:137-188` | **Low / none for target tables.** Startup compatibility guards cover only `personas.persona_policy` and `knowledge_documents`. No report/evaluation table-specific repair exists here. |
| `backend/src/common/db/legacy_schema_repair.py:39-309` | **No direct relevance.** Only persona and knowledge-document repair logic exists. There is no staged-evaluation or comprehensive-report repair function. |
| `backend/alembic/versions/20260413_1040_029_explicit_legacy_startup_repairs.py:25-36` | **No direct relevance.** Replays only persona/knowledge repairs under Alembic authority. Nothing here reconciles the report/evaluation tables. |
| Broad test/bootstrap use of `Base.metadata.create_all` (e.g. `backend/tests/conftest.py:48`, `backend/reset_db.py:27`) | **Medium relevance.** Local/test databases can reflect ORM truth even when Alembic truth differs, which explains why schema assumptions drifted across runtime and tests. |

### Practical implication

For the report/evaluation tables, there is **no runtime auto-healing path** beyond `create_all`. If a database already has the legacy Alembic shape, startup will not reconcile it. If a database is created from the ORM, it will not inherit the migration-era indexes/legacy columns. T6 must therefore treat these tables as a true ORM↔migration reconciliation problem, not a startup-repair problem.

---

## 6) T6 no-guess checklist

T6 should use this artifact as the single source of truth and make the following explicit in the migration plan:

1. Reconcile `staged_evaluation_results` to the canonical column set above.
2. Preserve / recreate the canonical staged-evaluation indexes:
   - `idx_staged_eval_session(session_id)`
   - `idx_staged_eval_stage(session_id, stage_number)` unique
3. Reconcile `comprehensive_reports` to a `session_id` primary-key model and remove the redundant unique-index-only identity strategy.
4. Choose one timestamp name per table:
   - staged evaluation: `created_at`
   - comprehensive report: `created_at`
5. Backfill or rewrite legacy rows before tightening any `NOT NULL` rules for canonical columns such as `overall_score` and JSON collections.
6. Update drifted tests so they assert the canonical schema rather than the original `006` table shape.
7. Remove the dependency on runtime `create_all` as an implicit schema authority for these tables once Alembic and ORM agree.

## Bottom line

The canonical report/evaluation storage model is the **current runtime object shape**, not the original `006` analytics table design. The highest-risk drift is:

- `staged_evaluation_results`: missing `weaknesses` + missing canonical unique/index metadata in ORM
- `comprehensive_reports`: migration-era surrogate-key/legacy-column model vs runtime `session_id`-primary-key model
- startup/test `create_all`: keeps re-materializing ORM truth even while Alembic still describes older truth

That is the exact ambiguity T6 must remove.
