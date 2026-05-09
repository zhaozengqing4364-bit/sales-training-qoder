# Type Debt Baseline

Generated: 2026-05-09

## Command

```bash
cd backend
PYTHONPATH=src .venv-test/bin/mypy src --show-error-codes || true
```

## Baseline Summary

- Current full mypy error count: 674
- Current full mypy error file count: 31
- Checked source files: 286
- Gate interpretation: full mypy is now a monitored debt ceiling for gray release, not a Phase 1.3 zero-error blocker.
- Gray-release rule: future full mypy runs during Phase 1 must not exceed 674 errors / 31 files unless the increase is explicitly recorded as a blocker in `DELIVERY_STATE.md`.

## Top 10 Error Files

| Rank | Errors | File |
| --- | ---: | --- |
| 1 | 77 | `src/admin/api/knowledge_answer_config.py` |
| 2 | 57 | `src/common/knowledge/api.py` |
| 3 | 54 | `src/common/api/analytics.py` |
| 4 | 38 | `src/sales_bot/websocket/base_sales_handler.py` |
| 5 | 38 | `src/agent/api/agents.py` |
| 6 | 32 | `src/presentation_coach/websocket/presentation_handler.py` |
| 7 | 32 | `src/admin/api/model_configs.py` |
| 8 | 28 | `src/presentation_coach/api/presentations.py` |
| 9 | 24 | `src/evaluation/services/comprehensive_report.py` |
| 10 | 23 | `src/common/api/users.py` |

## Error Types

| Error Code | Count | Primary Meaning |
| --- | ---: | --- |
| `no-untyped-def` | 177 | Missing function or parameter annotations. |
| `assignment` | 134 | SQLAlchemy runtime instance fields are being treated as class-level `Column[...]` descriptors or incompatible typed assignments. |
| `union-attr` | 109 | Optional values are accessed before success/None narrowing. |
| `arg-type` | 108 | Runtime ORM/JSON/LLM values are passed to narrower API contracts without coercion. |
| `return-value` | 89 | FastAPI/error-envelope return contracts or service returns do not match annotations. |
| `attr-defined` | 17 | Dynamic model/adapter attributes need explicit narrowing or protocol boundaries. |
| `index` | 10 | Dictionary/list index values are not narrowed to the expected runtime type. |
| `var-annotated` | 6 | Local variables need explicit annotations. |
| `misc` | 6 | Mixed structural issues, mostly generator/contextmanager or iterable typing. |
| `no-any-return` | 5 | Functions annotated narrowly still return dynamic `Any`. |
| `call-overload` | 3 | Third-party or SQLAlchemy overload selection is ambiguous. |
| `valid-type` | 2 | Invalid type expression usage. |
| `type-var` | 2 | Type variable bounds are not satisfied. |
| `operator` | 2 | Unsupported operation for inferred union/runtime types. |
| `override` | 1 | Subclass method signature does not match the base class. |
| `no-redef` | 1 | Duplicate definition. |
| `import-not-found` | 1 | Missing import stub/module in the current environment. |
| `call-arg` | 1 | Call signature mismatch. |

## Core Business Chain Impact

Core business chain for gray release:

员工训练 -> 系统报告 -> 主管评审 -> 要求复训 -> 员工复训 -> 前后对比 -> 主管给出上岗建议

Current impact assessment from the baseline:

- Auth access boundary: impacted by `src/common/auth/api.py` with 11 errors. This affects login/recovery API type confidence, but the existing auth service boundary and auth transport tests remain separately verified.
- Practice API: `src/common/api/practice.py` has 0 direct mypy errors in the current focused gate, so the main practice report/session API surface is acceptable for Phase 1 gray baseline.
- Scoring/effectiveness primitives: `src/common/effectiveness` has 0 direct mypy errors in the current focused gate. `src/evaluation` still has 57 errors across report generation and staged/comprehensive report services, which directly affects report-confidence work and must remain visible before Phase 3 evidence/calibration work.
- Sales training runtime: `src/sales_bot` has 46 focused mypy errors, mainly in `summary_service.py` and `websocket/base_sales_handler.py`. This affects type confidence around the sales WebSocket runtime and summary generation, but the change scope must remain bounded and avoid a StepFun rewrite.
- Presentation training runtime: `src/presentation_coach` has 70 focused mypy errors, mainly in report service, presentation API, and websocket handler. This affects type confidence around PPT training/reporting and should be handled as bounded boundary cleanup, not broad refactor.
- Admin/knowledge/analytics surfaces outside the Phase 1 core-domain gate account for several top error files and remain tracked debt for later phases. They are not allowed to block Phase 1 unless they raise the full mypy count above this baseline or break the gray-release commands.

## Phase 1 Gray Gate

The Phase 1 gray-release gate is:

- `ruff check src tests` passes.
- `npx eslint . --quiet` passes from `web/`.
- `npx tsc --noEmit` passes from `web/`.
- Core-domain mypy passes for:
  - `src/common/auth`
  - `src/common/api/practice.py`
  - `src/evaluation`
  - `src/sales_bot`
  - `src/presentation_coach`
  - `src/common/effectiveness`
- Full mypy remains at or below 674 errors / 31 files.
- `npx vitest run` runs only project tests and does not execute `node_modules` tests.

