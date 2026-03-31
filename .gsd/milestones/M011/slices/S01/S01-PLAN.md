# S01: 引擎 seam 与数据库控制面骨架

**Goal:** 建立 KnowledgeAnswerEngine seam、DB control plane schema、配置仓储与基础契约，先把系统能力边界立住。
**Demo:** After this: 可以在代码里实例化新的 KnowledgeAnswerEngine，并从数据库读取一套 active query/ranking/answerability 配置。

## Tasks
- [x] **T01: Added the initial KnowledgeAnswerEngine seam, project-owned request/result schemas, and Haystack dependency entrypoints behind a constructable placeholder engine.** — 先写 engine seam 的失败测试，再创建 `common/knowledge_engine` 包、基础 request/result contract 和 Haystack dependency 接入点。保持只有最小构造能力，不提前引入复杂逻辑。
  - Estimate: 20-30m
  - Files: backend/pyproject.toml, backend/src/common/knowledge_engine/__init__.py, backend/src/common/knowledge_engine/engine.py, backend/src/common/knowledge_engine/schemas.py, backend/tests/unit/common/test_knowledge_answer_engine.py
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_answer_engine.py -q
- [ ] **T02: 增加控制面与审计数据模型** — 新增 Alembic migration 与 SQLAlchemy models：query profiles、intent rules、entity aliases、ranking profiles、answerability profiles、config versions、answer runs、run steps。先只做最小字段，确保可版本化与可审计。
  - Estimate: 30-45m
  - Files: backend/alembic/versions, backend/src/common/db/models.py, backend/tests/unit/common/test_knowledge_answer_control_plane_models.py
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_answer_control_plane_models.py -q
- [ ] **T03: 实现数据库配置仓储** — 实现 DB-backed config repository。先只支持 active config version 读取 query profile、intent rules、entity aliases、ranking profile、answerability profile，返回归一化 DTO，不把 ORM 泄漏到 engine。
  - Estimate: 25-35m
  - Files: backend/src/common/knowledge_engine/config_repo.py, backend/tests/unit/common/test_knowledge_answer_config_repo.py
  - Verify: backend/venv/bin/python -m pytest -c backend/pyproject.toml backend/tests/unit/common/test_knowledge_answer_config_repo.py -q
