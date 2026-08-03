from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml
from scripts.architecture_dependency_guard import (
    collect_edges,
    strongly_connected_components,
    validate_foundation_repository,
    validate_repository,
)

SYNTHETIC_TODAY = date(2026, 7, 10)


def _write(path: Path, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def _policy(
    *,
    packages: list[str],
    stable_edges: list[list[str]] | None = None,
    temporary_edges: list[dict[str, object]] | None = None,
    baseline_sccs: list[list[str]] | None = None,
) -> dict[str, object]:
    return {
        "version": 1,
        "packages": packages,
        "stable_edges": stable_edges or [],
        "temporary_edges": temporary_edges or [],
        "baseline_sccs": baseline_sccs or [],
    }


def _write_policy(path: Path, policy: dict[str, object]) -> None:
    path.write_text(
        yaml.safe_dump(policy, sort_keys=False),
        encoding="utf-8",
    )


def _temporary_group(
    source: str,
    targets: list[str],
    *,
    expires_on: str = "2026-10-31",
) -> dict[str, object]:
    return {
        "source": source,
        "targets": targets,
        "owner": "architecture-owner",
        "reason": "legacy dependency under migration",
        "retire_when": "the neutral port owns the dependency",
        "expires_on": expires_on,
    }


def test_should_collect_static_local_typing_and_literal_dynamic_imports(
    tmp_path: Path,
) -> None:
    src = tmp_path / "src"
    _write(
        src / "alpha" / "module.py",
        """
from typing import TYPE_CHECKING
import beta.service

if TYPE_CHECKING:
    from gamma.types import Contract

from . import local_helper
from .local import local_value

def load():
    from delta.runtime import Runtime
    import importlib
    from importlib import import_module
    importlib.import_module("epsilon.adapter")
    __import__("zeta.plugin")
    import_module("eta.plugin")
    import_module(variable_plugin_path)
    return Runtime, Contract, local_helper, local_value
""",
    )
    for package in ("beta", "gamma", "delta", "epsilon", "eta", "zeta"):
        _write(src / package / "__init__.py", "")

    edges = collect_edges(
        src,
        {"alpha", "beta", "gamma", "delta", "epsilon", "eta", "zeta"},
    )

    assert set(edges) == {
        ("alpha", "beta"),
        ("alpha", "gamma"),
        ("alpha", "delta"),
        ("alpha", "epsilon"),
        ("alpha", "eta"),
        ("alpha", "zeta"),
    }
    assert edges[("alpha", "delta")] == {"alpha/module.py:12"}


def test_should_return_strongly_connected_components_deterministically() -> None:
    edges = {
        ("beta", "alpha"),
        ("delta", "gamma"),
        ("alpha", "beta"),
        ("beta", "gamma"),
        ("gamma", "delta"),
    }

    components = strongly_connected_components(
        {"delta", "beta", "alpha", "gamma", "epsilon"},
        edges,
    )

    assert components == [
        frozenset({"gamma", "delta"}),
        frozenset({"alpha", "beta"}),
        frozenset({"epsilon"}),
    ]


def test_current_repository_dependency_policy_is_valid() -> None:
    assert validate_repository() == []


def test_should_allow_a_baseline_component_to_shrink(tmp_path: Path) -> None:
    src = tmp_path / "src"
    _write(src / "alpha" / "module.py", "import beta\n")
    _write(src / "beta" / "module.py", "import alpha\n")
    _write(src / "gamma" / "__init__.py", "")
    policy_path = tmp_path / "policy.yaml"
    _write_policy(
        policy_path,
        _policy(
            packages=["alpha", "beta", "gamma"],
            stable_edges=[["alpha", "beta"], ["beta", "alpha"]],
            baseline_sccs=[["alpha", "beta", "gamma"]],
        ),
    )

    assert (
        validate_repository(
            src_root=src,
            policy_path=policy_path,
            today=SYNTHETIC_TODAY,
        )
        == []
    )


def test_should_reject_missing_top_level_policy_fields(tmp_path: Path) -> None:
    src = tmp_path / "src"
    policy_path = tmp_path / "policy.yaml"
    _write_policy(policy_path, {"version": 1})

    violations = validate_repository(
        src_root=src,
        policy_path=policy_path,
        today=SYNTHETIC_TODAY,
    )

    assert {
        "Policy is missing required field: baseline_sccs",
        "Policy is missing required field: packages",
        "Policy is missing required field: stable_edges",
        "Policy is missing required field: temporary_edges",
    } <= set(violations)


@pytest.mark.parametrize(
    "missing_field",
    ["source", "targets", "owner", "reason", "retire_when", "expires_on"],
)
def test_should_reject_incomplete_temporary_dependency_groups(
    tmp_path: Path,
    missing_field: str,
) -> None:
    src = tmp_path / "src"
    _write(src / "alpha" / "module.py", "import beta\n")
    _write(src / "beta" / "__init__.py", "")
    group = _temporary_group("alpha", ["beta"])
    del group[missing_field]
    policy_path = tmp_path / "policy.yaml"
    _write_policy(
        policy_path,
        _policy(packages=["alpha", "beta"], temporary_edges=[group]),
    )

    violations = validate_repository(
        src_root=src,
        policy_path=policy_path,
        today=SYNTHETIC_TODAY,
    )

    assert any(
        f"missing required fields: {missing_field}" in violation
        for violation in violations
    )


@pytest.mark.parametrize(
    ("expires_on", "expected"),
    [
        ("not-a-date", "Invalid expires_on"),
        ("2026-07-09", "Expired temporary dependency group"),
    ],
)
def test_should_reject_invalid_or_expired_temporary_dependencies(
    tmp_path: Path,
    expires_on: str,
    expected: str,
) -> None:
    src = tmp_path / "src"
    _write(src / "alpha" / "module.py", "import beta\n")
    _write(src / "beta" / "__init__.py", "")
    policy_path = tmp_path / "policy.yaml"
    _write_policy(
        policy_path,
        _policy(
            packages=["alpha", "beta"],
            temporary_edges=[
                _temporary_group("alpha", ["beta"], expires_on=expires_on)
            ],
        ),
    )

    violations = validate_repository(
        src_root=src,
        policy_path=policy_path,
        today=SYNTHETIC_TODAY,
    )

    assert any(expected in violation for violation in violations)


def test_should_reject_stale_temporary_dependency_exception(
    tmp_path: Path,
) -> None:
    src = tmp_path / "src"
    _write(src / "alpha" / "__init__.py", "")
    _write(src / "beta" / "__init__.py", "")
    policy_path = tmp_path / "policy.yaml"
    _write_policy(
        policy_path,
        _policy(
            packages=["alpha", "beta"],
            temporary_edges=[_temporary_group("alpha", ["beta"])],
        ),
    )

    violations = validate_repository(
        src_root=src,
        policy_path=policy_path,
        today=SYNTHETIC_TODAY,
    )

    assert violations == [
        "Stale temporary dependency exception alpha->beta; remove it from policy"
    ]


def test_should_reject_unexpected_edge_and_expanded_component(
    tmp_path: Path,
) -> None:
    src = tmp_path / "src"
    _write(src / "alpha" / "module.py", "import beta\nimport gamma\n")
    _write(src / "beta" / "module.py", "import alpha\n")
    _write(src / "gamma" / "module.py", "import alpha\n")
    policy_path = tmp_path / "policy.yaml"
    _write_policy(
        policy_path,
        _policy(
            packages=["alpha", "beta", "gamma"],
            stable_edges=[["alpha", "beta"], ["gamma", "alpha"]],
            temporary_edges=[_temporary_group("beta", ["alpha"])],
            baseline_sccs=[["alpha", "beta"]],
        ),
    )

    violations = validate_repository(
        src_root=src,
        policy_path=policy_path,
        today=SYNTHETIC_TODAY,
    )

    assert any(
        violation.startswith("Unexpected dependency alpha->gamma")
        for violation in violations
    )
    assert "Expanded strongly connected component: alpha, beta, gamma" in violations


def test_should_reject_an_unexpected_edge_inside_an_existing_component(
    tmp_path: Path,
) -> None:
    src = tmp_path / "src"
    _write(src / "alpha" / "module.py", "import beta\nimport gamma\n")
    _write(src / "beta" / "module.py", "import gamma\n")
    _write(src / "gamma" / "module.py", "import alpha\n")
    policy_path = tmp_path / "policy.yaml"
    _write_policy(
        policy_path,
        _policy(
            packages=["alpha", "beta", "gamma"],
            stable_edges=[
                ["alpha", "beta"],
                ["beta", "gamma"],
                ["gamma", "alpha"],
            ],
            baseline_sccs=[["alpha", "beta", "gamma"]],
        ),
    )

    violations = validate_repository(
        src_root=src,
        policy_path=policy_path,
        today=SYNTHETIC_TODAY,
    )

    assert violations == [
        "Unexpected dependency alpha->gamma: alpha/module.py:2"
    ]


def test_should_reject_invalid_yaml(tmp_path: Path) -> None:
    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text("packages: [alpha\n", encoding="utf-8")

    violations = validate_repository(
        src_root=tmp_path / "src",
        policy_path=policy_path,
        today=SYNTHETIC_TODAY,
    )

    assert len(violations) == 1
    assert violations[0].startswith("Dependency policy is invalid YAML:")


def test_should_reject_duplicate_overlapping_and_undeclared_edges(
    tmp_path: Path,
) -> None:
    src = tmp_path / "src"
    _write(src / "alpha" / "module.py", "import beta\n")
    _write(src / "beta" / "__init__.py", "")
    policy_path = tmp_path / "policy.yaml"
    _write_policy(
        policy_path,
        _policy(
            packages=["alpha", "beta"],
            stable_edges=[
                ["alpha", "beta"],
                ["alpha", "beta"],
                ["alpha", "gamma"],
            ],
            temporary_edges=[
                _temporary_group("alpha", ["beta", "beta", "delta"])
            ],
        ),
    )

    violations = validate_repository(
        src_root=src,
        policy_path=policy_path,
        today=SYNTHETIC_TODAY,
    )

    assert "Duplicate stable dependency: alpha->beta" in violations
    assert "temporary_edges[0] targets must not contain duplicates" in violations
    assert "Duplicate temporary dependency: alpha->beta" in violations
    assert "Dependency cannot be both stable and temporary: alpha->beta" in violations
    assert any(
        "references undeclared package: ('alpha', 'gamma')" in violation
        for violation in violations
    )
    assert any(
        "references undeclared package: ('alpha', 'delta')" in violation
        for violation in violations
    )


def test_should_reject_duplicate_packages_and_missing_package_directory(
    tmp_path: Path,
) -> None:
    src = tmp_path / "src"
    _write(src / "alpha" / "__init__.py", "")
    policy_path = tmp_path / "policy.yaml"
    _write_policy(
        policy_path,
        _policy(packages=["alpha", "alpha", "beta"]),
    )

    violations = validate_repository(
        src_root=src,
        policy_path=policy_path,
        today=SYNTHETIC_TODAY,
    )

    assert "Policy packages must not contain duplicates" in violations
    assert "Declared package directory is missing: beta" in violations


def _foundation_policy() -> dict[str, object]:
    return {
        "version": 1,
        "status": "enforced",
        "business_modules": [
            "newcomer_training",
            "learning",
            "audio_assessment",
        ],
        "stable_edges": [
            ["newcomer_training", "learning"],
            ["newcomer_training", "audio_assessment"],
        ],
        "stable_edge_import_scope": {
            "allowed_path_segments": ["contracts", "ports", "public", "identifiers"],
            "forbidden_path_segments": [
                "models",
                "repositories",
                "repository",
                "sqlalchemy",
                "adapters",
                "services",
                "internal",
            ],
        },
        "module_paths": {
            "newcomer_training": ["newcomer_training"],
            "learning": ["learning"],
            "audio_assessment": ["audio_assessment"],
            "shared_kernel": ["common"],
            "application_root": ["foundation_composition.py"],
        },
        "composition_root": "application_root",
        "composition_root_edges": [
            ["application_root", "newcomer_training"],
            ["application_root", "learning"],
            ["application_root", "audio_assessment"],
            ["application_root", "shared_kernel"],
        ],
        "temporary_exceptions": [],
    }


def test_foundation_guard_should_allow_contract_scoped_business_imports(
    tmp_path: Path,
) -> None:
    src = tmp_path / "src"
    _write(
        src / "newcomer_training" / "application.py",
        "from learning.contracts import LearningActor\n",
    )
    _write(src / "learning" / "contracts.py", "class LearningActor: ...\n")
    _write(src / "audio_assessment" / "__init__.py", "")
    _write(src / "common" / "__init__.py", "")
    _write(src / "foundation_composition.py", "")
    policy_path = tmp_path / "foundation-policy.yaml"
    _write_policy(policy_path, _foundation_policy())

    assert (
        validate_foundation_repository(src_root=src, policy_path=policy_path) == []
    )


@pytest.mark.parametrize(
    ("import_line", "expected_code"),
    [
        (
            "from audio_assessment.models import AudioArtifact\n",
            "ARCH_CROSS_MODULE_ORM_FORBIDDEN",
        ),
        (
            "from learning.services.internal import QuestionWriter\n",
            "ARCH_BUSINESS_EDGE_SCOPE_FORBIDDEN",
        ),
    ],
)
def test_foundation_guard_should_reject_cross_business_internal_imports(
    tmp_path: Path,
    import_line: str,
    expected_code: str,
) -> None:
    src = tmp_path / "src"
    _write(src / "newcomer_training" / "application.py", import_line)
    _write(src / "learning" / "__init__.py", "")
    _write(src / "audio_assessment" / "__init__.py", "")
    _write(src / "common" / "__init__.py", "")
    _write(src / "foundation_composition.py", "")
    policy_path = tmp_path / "foundation-policy.yaml"
    _write_policy(policy_path, _foundation_policy())

    violations = validate_foundation_repository(
        src_root=src,
        policy_path=policy_path,
    )

    assert any(expected_code in violation for violation in violations)
    assert any("newcomer_training/application.py:1" in violation for violation in violations)


def test_foundation_guard_should_reject_shared_kernel_reverse_dependency(
    tmp_path: Path,
) -> None:
    src = tmp_path / "src"
    _write(
        src / "common" / "bridge.py",
        "from newcomer_training.contracts import PathRevisionDraft\n",
    )
    _write(src / "newcomer_training" / "contracts.py", "")
    _write(src / "learning" / "__init__.py", "")
    _write(src / "audio_assessment" / "__init__.py", "")
    _write(src / "foundation_composition.py", "")
    policy_path = tmp_path / "foundation-policy.yaml"
    _write_policy(policy_path, _foundation_policy())

    violations = validate_foundation_repository(
        src_root=src,
        policy_path=policy_path,
    )

    assert any("ARCH_SHARED_KERNEL_REVERSE_DEPENDENCY" in item for item in violations)


def test_foundation_guard_should_reject_literal_dynamic_activity_import(
    tmp_path: Path,
) -> None:
    src = tmp_path / "src"
    _write(
        src / "newcomer_training" / "registry.py",
        'from importlib import import_module\nimport_module("learning.activities.lesson")\n',
    )
    _write(src / "learning" / "__init__.py", "")
    _write(src / "audio_assessment" / "__init__.py", "")
    _write(src / "common" / "__init__.py", "")
    _write(src / "foundation_composition.py", "")
    policy_path = tmp_path / "foundation-policy.yaml"
    _write_policy(policy_path, _foundation_policy())

    violations = validate_foundation_repository(
        src_root=src,
        policy_path=policy_path,
    )

    assert any("ARCH_DYNAMIC_ACTIVITY_IMPORT_FORBIDDEN" in item for item in violations)


@pytest.mark.parametrize(
    "provider_source",
    [
        "import openai\n",
        "from ai_platform.openai_provider import OpenAICompatibleProvider\n",
        "result = service.llm.apredict('answer')\n",
    ],
)
def test_foundation_guard_should_reject_direct_business_provider_access(
    tmp_path: Path,
    provider_source: str,
) -> None:
    src = tmp_path / "src"
    _write(src / "learning" / "question_generation.py", provider_source)
    _write(src / "newcomer_training" / "__init__.py", "")
    _write(src / "audio_assessment" / "__init__.py", "")
    _write(src / "common" / "__init__.py", "")
    _write(src / "foundation_composition.py", "")
    policy_path = tmp_path / "foundation-policy.yaml"
    _write_policy(policy_path, _foundation_policy())

    violations = validate_foundation_repository(
        src_root=src,
        policy_path=policy_path,
    )

    assert any("ARCH_DIRECT_AI_PROVIDER_FORBIDDEN" in item for item in violations)


def test_foundation_guard_should_fail_when_policy_is_not_enforced_or_keeps_exceptions(
    tmp_path: Path,
) -> None:
    src = tmp_path / "src"
    for package in ("newcomer_training", "learning", "audio_assessment", "common"):
        _write(src / package / "__init__.py", "")
    _write(src / "foundation_composition.py", "")
    policy = _foundation_policy()
    policy["status"] = "design_only_not_enforced"
    policy["temporary_exceptions"] = [
        {
            "id": "legacy",
            "owner": "owner",
            "reason": "legacy",
            "retire_when": "deleted",
            "expires_on": "2026-10-31",
        }
    ]
    policy_path = tmp_path / "foundation-policy.yaml"
    _write_policy(policy_path, policy)

    violations = validate_foundation_repository(
        src_root=src,
        policy_path=policy_path,
    )

    assert any("Foundation architecture policy status must be enforced" in item for item in violations)
    assert any("Foundation temporary exception remains: legacy" in item for item in violations)


def test_foundation_guard_should_reject_delivery_transaction_with_provider_io(
    tmp_path: Path,
) -> None:
    src = tmp_path / "src"
    _write(
        src / "newcomer_training" / "api.py",
        """
from fastapi import APIRouter

router = APIRouter()

@router.post("/attempts")
async def submit_attempt(db, provider, row):
    db.add(row)
    await provider.apredict("score")
    await db.commit()
""",
    )
    _write(src / "learning" / "__init__.py", "")
    _write(src / "audio_assessment" / "__init__.py", "")
    _write(src / "common" / "__init__.py", "")
    _write(src / "foundation_composition.py", "")
    policy_path = tmp_path / "foundation-policy.yaml"
    _write_policy(policy_path, _foundation_policy())

    violations = validate_foundation_repository(
        src_root=src,
        policy_path=policy_path,
    )

    assert any(
        "ARCH_DELIVERY_ORCHESTRATION_FORBIDDEN" in item
        and "newcomer_training/api.py:7" in item
        for item in violations
    )


def test_foundation_guard_should_accept_declared_composition_root_edges(
    tmp_path: Path,
) -> None:
    src = tmp_path / "src"
    _write(src / "newcomer_training" / "__init__.py", "")
    _write(src / "learning" / "__init__.py", "")
    _write(src / "audio_assessment" / "__init__.py", "")
    _write(src / "common" / "__init__.py", "")
    _write(
        src / "foundation_composition.py",
        """
from newcomer_training.application import PathEnrollmentService
from learning.models import LearningUnit
from audio_assessment.storage import LocalAudioStorage
from common.db.session import get_db

def build_services(db):
    return PathEnrollmentService(db), LearningUnit, LocalAudioStorage, get_db
""",
    )
    policy_path = tmp_path / "foundation-policy.yaml"
    _write_policy(policy_path, _foundation_policy())

    assert (
        validate_foundation_repository(src_root=src, policy_path=policy_path) == []
    )


def test_foundation_guard_should_reject_undeclared_composition_root_target(
    tmp_path: Path,
) -> None:
    src = tmp_path / "src"
    _write(src / "newcomer_training" / "__init__.py", "")
    _write(src / "learning" / "__init__.py", "")
    _write(src / "audio_assessment" / "__init__.py", "")
    _write(src / "common" / "__init__.py", "")
    _write(src / "foundation_composition.py", "from readiness.models import ReadinessDossier\n")
    _write(src / "readiness" / "models.py", "class ReadinessDossier: ...\n")
    policy = _foundation_policy()
    module_paths = policy["module_paths"]
    assert isinstance(module_paths, dict)
    module_paths["readiness"] = ["readiness"]
    policy_path = tmp_path / "foundation-policy.yaml"
    _write_policy(policy_path, policy)

    violations = validate_foundation_repository(
        src_root=src,
        policy_path=policy_path,
    )

    assert any("ARCH_COMPOSITION_ROOT_EDGE_UNDECLARED" in item for item in violations)


@pytest.mark.parametrize(
    ("root_source", "expected_code"),
    [
        (
            """
async def mutate_business_state(db, entity):
    db.add(entity)
    await db.commit()
""",
            "ARCH_COMPOSITION_ROOT_BUSINESS_MUTATION_FORBIDDEN",
        ),
        (
            """
def locate_service(service_name):
    return globals()[service_name]
""",
            "ARCH_COMPOSITION_ROOT_SERVICE_LOCATOR_FORBIDDEN",
        ),
    ],
)
def test_foundation_guard_should_reject_composition_root_runtime_behavior(
    tmp_path: Path,
    root_source: str,
    expected_code: str,
) -> None:
    src = tmp_path / "src"
    _write(src / "newcomer_training" / "__init__.py", "")
    _write(src / "learning" / "__init__.py", "")
    _write(src / "audio_assessment" / "__init__.py", "")
    _write(src / "common" / "__init__.py", "")
    _write(src / "foundation_composition.py", root_source)
    policy_path = tmp_path / "foundation-policy.yaml"
    _write_policy(policy_path, _foundation_policy())

    violations = validate_foundation_repository(
        src_root=src,
        policy_path=policy_path,
    )

    assert any(expected_code in item for item in violations)
