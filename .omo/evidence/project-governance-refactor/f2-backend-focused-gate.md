# F2 Backend Focused Gate

Date: 2026-06-20

## Commands and Results

- `cd backend && alembic heads`
  - Result: passed.
  - Output head: `20260616_086 (head)`.

- `cd backend && venv/bin/python -m pytest tests/unit/test_runtime_dependency_contract.py --no-cov -q`
  - Result: passed.
  - Summary: `8 passed, 1 warning in 1.03s`.

- `cd backend && venv/bin/python -m pytest tests/unit/test_voice_runtime_policy_service.py tests/unit/test_domain_contributor_bootstrap.py tests/unit/test_session_runtime_repair_service.py tests/unit/test_roleplay_contracts.py tests/unit/test_config_bundle_inventory_facade.py tests/unit/test_sales_trainer_ai_coach.py tests/unit/test_sales_trainer_ai_coach_chat.py tests/unit/test_sales_trainer_phase2_projection.py tests/unit/test_sales_trainer_path_projection_ai_coach.py tests/unit/test_sales_trainer_unit_public_payloads.py tests/unit/test_seed_newcomer_training_path.py tests/unit/test_verification_runner.py tests/integration/test_release_gate.py tests/contract/test_release_verification_contract.py tests/integration/test_prompt_templates_api_rbac.py tests/unit/test_newcomer_training_path_permissions.py tests/unit/test_presentation_stepfun_realtime_handler.py tests/unit/test_stepfun_realtime_handler.py --no-cov -q`
  - Result: passed.
  - Summary: `363 passed, 3 warnings in 23.93s`.

## Warning Classification

- `chromadb` deprecation warning from dependency code.
- `PytestCollectionWarning` for `TestExecutionResult` dataclass naming in `src/common/analytics/verification_runner.py`; this does not prevent the selected tests from collecting and passing.
