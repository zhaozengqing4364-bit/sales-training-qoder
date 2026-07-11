from __future__ import annotations

import ast
import hashlib
import importlib
import json
from pathlib import Path
from typing import Any

from sqlalchemy import CheckConstraint, UniqueConstraint

from common.db import models

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_SRC = REPO_ROOT / "backend" / "src"
EXPECTED_METADATA_SHA256 = (
    "cc9bb58232ea600b9c88574bceac9f495feab4e18e02ae8d21af7165f7eeb63b"
)

EXPECTED_PUBLIC_MODEL_CLASSES = {
    "Achievement",
    "AdminRolePermission",
    "Base",
    "BusinessRuleConfig",
    "BusinessRuleConfigAuditLog",
    "ComprehensiveReport",
    "ConfigBundle",
    "ConfigBundleAuditLog",
    "ConfigVersion",
    "ConversationMessage",
    "EvaluationRun",
    "EvaluationRunStatus",
    "ForbiddenWord",
    "HighlightReview",
    "HighlightReviewItem",
    "HighlightReviewShare",
    "HighlightReviewShareAccessLog",
    "InterruptionEvent",
    "InterruptionType",
    "KnowledgeAnswerRun",
    "KnowledgeAnswerRunStep",
    "KnowledgeAnswerabilityProfile",
    "KnowledgeChunkingPreset",
    "KnowledgeConfigVersion",
    "KnowledgeEntityAlias",
    "KnowledgeIntentRule",
    "KnowledgeQueryProfile",
    "KnowledgeRankingProfile",
    "LeaderboardEntry",
    "ManagerIntervention",
    "ManagerInterventionDueState",
    "ManagerInterventionReminderStatus",
    "Notification",
    "Page",
    "PasswordResetToken",
    "PracticeSession",
    "Presentation",
    "PresentationStatus",
    "PromptTemplate",
    "ReleaseVerificationRecord",
    "ReleaseVerificationSummary",
    "ReportGenerationStatus",
    "RequiredTalkingPoint",
    "RetrainingTask",
    "Scenario",
    "ScenarioPrompt",
    "ScenarioType",
    "ScoringRuleset",
    "SessionAudioSegment",
    "SessionStatus",
    "StagedEvaluationResult",
    "SupervisorReview",
    "SupervisorScoreCalibration",
    "SystemLog",
    "SystemLogStatus",
    "TrainingReportSnapshot",
    "TrainingTask",
    "TrainingTaskStatus",
    "UploadStatus",
    "User",
    "UserAchievement",
    "UserGoal",
    "UserPresentationProgress",
    "UserTrainingPreference",
    "VerificationCheckType",
    "VerificationStatus",
}


def _default_signature(default: Any) -> str | None:
    if default is None:
        return None
    argument = default.arg
    if callable(argument):
        return f"callable:{getattr(argument, '__name__', type(argument).__name__)}"
    return repr(argument)


def _server_default_signature(default: Any) -> str | None:
    if default is None:
        return None
    argument = default.arg
    return str(getattr(argument, "text", argument))


def _metadata_snapshot() -> dict[str, Any]:
    result: dict[str, Any] = {}
    for table_name, table in sorted(models.Base.metadata.tables.items()):
        result[table_name] = {
            "columns": [
                {
                    "name": column.name,
                    "type": str(column.type),
                    "nullable": column.nullable,
                    "primary_key": column.primary_key,
                    "unique": column.unique,
                    "index": column.index,
                    "default": _default_signature(column.default),
                    "server_default": _server_default_signature(column.server_default),
                    "foreign_keys": sorted(
                        foreign_key.target_fullname
                        for foreign_key in column.foreign_keys
                    ),
                }
                for column in table.columns
            ],
            "indexes": sorted(
                [
                    {
                        "name": index.name,
                        "unique": index.unique,
                        "columns": [column.name for column in index.columns],
                    }
                    for index in table.indexes
                ],
                key=lambda item: str(item["name"]),
            ),
            "checks": sorted(
                [
                    {
                        "name": constraint.name,
                        "sqltext": str(constraint.sqltext),
                    }
                    for constraint in table.constraints
                    if isinstance(constraint, CheckConstraint)
                ],
                key=lambda item: str(item["name"]),
            ),
            "uniques": sorted(
                [
                    {
                        "name": constraint.name,
                        "columns": [column.name for column in constraint.columns],
                    }
                    for constraint in table.constraints
                    if isinstance(constraint, UniqueConstraint)
                ],
                key=lambda item: str(item["name"]),
            ),
        }
    return result


def _imported_names(path: Path, module_name: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == module_name
        for alias in node.names
    }


def test_common_model_registry_preserves_public_class_inventory() -> None:
    actual = {
        name
        for name, value in vars(models).items()
        if isinstance(value, type)
        and not name.startswith("_")
        and value.__module__ == models.__name__
    }
    assert actual == EXPECTED_PUBLIC_MODEL_CLASSES


def test_common_model_registry_preserves_complete_metadata_snapshot() -> None:
    canonical = json.dumps(
        _metadata_snapshot(), sort_keys=True, separators=(",", ":")
    ).encode()
    assert len(models.Base.metadata.tables) == 98
    assert hashlib.sha256(canonical).hexdigest() == EXPECTED_METADATA_SHA256


def test_common_model_registry_is_an_identity_preserving_facade() -> None:
    registry = importlib.import_module("common.db.model_registry")
    for name in EXPECTED_PUBLIC_MODEL_CLASSES:
        assert getattr(models, name) is getattr(registry, name)
        assert getattr(models, name).__module__ == "common.db.models"


def test_journey_and_readiness_application_modules_do_not_import_foreign_orm() -> None:
    journey_imports = _imported_names(
        BACKEND_SRC / "sales_trainer" / "services" / "training_journey_service.py",
        "common.db.models",
    )
    readiness_imports = _imported_names(
        BACKEND_SRC / "sales_trainer" / "services" / "readiness_dossier_service.py",
        "common.db.models",
    )

    assert not ({"User", "PracticeSession"} & journey_imports)
    assert "User" not in readiness_imports


def test_journey_read_port_and_projection_modules_exist() -> None:
    assert (
        BACKEND_SRC / "sales_trainer" / "services" / "journey_read_repository.py"
    ).is_file()
    assert (
        BACKEND_SRC / "sales_trainer" / "services" / "journey_sqlalchemy_adapter.py"
    ).is_file()
    assert (
        BACKEND_SRC / "sales_trainer" / "services" / "training_journey_projection.py"
    ).is_file()
    assert (
        BACKEND_SRC / "sales_trainer" / "services" / "readiness_dossier_projection.py"
    ).is_file()
