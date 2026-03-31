---
estimated_steps: 1
estimated_files: 2
skills_used: []
---

# T03: 实现数据库配置仓储

实现 DB-backed config repository。先只支持 active config version 读取 query profile、intent rules、entity aliases、ranking profile、answerability profile，返回归一化 DTO，不把 ORM 泄漏到 engine。

## Inputs

- `backend/src/common/db/models.py`
- `backend/src/common/knowledge_engine/schemas.py`

## Expected Output

- `backend/src/common/knowledge_engine/config_repo.py`
- `backend/tests/unit/common/test_knowledge_answer_config_repo.py`

## Verification

backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_answer_config_repo.py -q

## Observability Impact

为后续 debug API 暴露 config_version 与 profile source 奠定基础。
