---
estimated_steps: 1
estimated_files: 3
skills_used: []
---

# T02: 增加控制面与审计数据模型

新增 Alembic migration 与 SQLAlchemy models：query profiles、intent rules、entity aliases、ranking profiles、answerability profiles、config versions、answer runs、run steps。先只做最小字段，确保可版本化与可审计。

## Inputs

- `backend/src/common/db/models.py`
- `docs/plans/2026-03-31-haystack-knowledge-answering-engine.md`

## Expected Output

- `backend/alembic/versions/*_knowledge_answer_control_plane.py`
- `backend/src/common/db/models.py`
- `backend/tests/unit/common/test_knowledge_answer_control_plane_models.py`

## Verification

backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_answer_control_plane_models.py -q

## Observability Impact

answer run / step 表为后续完整执行轨迹提供存储。
