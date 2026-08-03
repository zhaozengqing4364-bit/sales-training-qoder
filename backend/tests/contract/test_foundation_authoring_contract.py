from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
ADR = (
    REPO_ROOT
    / "docs/adr/2026-07-20-foundation-authoring-and-legacy-migration-authority.md"
)
ARCHITECTURE = REPO_ROOT / "docs/architecture/newcomer-foundation-contract.md"
MAPPING = (
    REPO_ROOT / "docs/architecture/newcomer-foundation-legacy-authoring-mapping.md"
)
API = REPO_ROOT / "docs/api-contract/newcomer-training-v2.md"
GLOSSARY = REPO_ROOT / "docs/domain-glossary.md"
ADMIN_SPEC = REPO_ROOT / ".trellis/spec/frontend/admin-console-patterns.md"
ACCEPTANCE = (
    REPO_ROOT
    / ".trellis/tasks/archive/2026-07/07-16-newcomer-sales-foundation-platform"
    / "acceptance-matrix.md"
)
INVENTORY_SCRIPT = (
    REPO_ROOT / "backend/scripts/inventory_newcomer_foundation_authoring.py"
)


def test_should_keep_authoring_contract_documents_aligned() -> None:
    adr = ADR.read_text(encoding="utf-8")
    architecture = ARCHITECTURE.read_text(encoding="utf-8")
    api = API.read_text(encoding="utf-8")
    glossary = GLOSSARY.read_text(encoding="utf-8")
    admin_spec = ADMIN_SPEC.read_text(encoding="utf-8")
    mapping = MAPPING.read_text(encoding="utf-8")

    assert "状态：Accepted" in adr
    for resource_type in (
        "source_document",
        "learning_unit",
        "question",
        "quiz",
        "audio_material",
        "scoring_scheme",
        "coach_profile",
        "scenario",
    ):
        assert resource_type in adr
        assert resource_type in architecture
        assert resource_type in api
    for capability in (
        "view_content",
        "edit_content",
        "review_content",
        "view_question_bank",
        "edit_questions",
        "review_questions",
        "edit_quizzes",
        "edit_audio_materials",
        "edit_scoring_schemes",
        "edit_coach_profiles",
        "edit_async_scenarios",
        "edit_paths",
        "manage_cohorts",
        "retry_assessments",
        "regrade_results",
        "review_readiness",
        "publish_releases",
        "rollback_releases",
        "view_sensitive_audit",
    ):
        assert capability in adr
        assert capability in admin_spec
    assert "审核通过不等于发布" in adr
    assert "Seed" in glossary and "不等于 Authoring 完成" in glossary
    assert "石犀ppt讲解" in mapping
    assert "demo讲解" in mapping
    assert "跨组织对象按安全合同返回 404" in adr
    assert "跨组织不可见为 404；capability 拒绝为 403" in api


def test_should_preserve_historical_acceptance_and_reopen_authoring_claims() -> None:
    acceptance = ACCEPTANCE.read_text(encoding="utf-8")

    assert "历史状态：2026-07-18 曾标记全部关闭" in acceptance
    assert "2026-07-20 Authoring 验收勘误" in acceptance
    assert "运行时已具备、Authoring 未闭环" in acceptance
    assert "07-19-foundation-legacy-migration-cutover" in acceptance
    assert "[E-ADMIN]" in acceptance
    assert "[E-RELEASE]" in acceptance


def test_inventory_entrypoint_should_have_no_apply_or_database_write_command() -> None:
    source = INVENTORY_SCRIPT.read_text(encoding="utf-8")
    tree = ast.parse(source)
    session_calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "session"
    }

    assert "--apply" not in source
    assert "--migrate" not in source
    assert not {"commit", "add", "delete", "flush"} & session_calls
    assert "SET TRANSACTION READ ONLY" in source
    assert "session.rollback()" in source


def test_authoring_contract_links_should_exist() -> None:
    for path in (ADR, ARCHITECTURE, MAPPING, API, GLOSSARY, ADMIN_SPEC, ACCEPTANCE):
        assert path.is_file(), path
