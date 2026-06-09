from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

CurriculumAssetType = Literal[
    "practice_template",
    "curriculum",
    "lesson",
    "knowledge_point",
    "question_bank",
    "question_item",
    "case_item",
    "role_profile",
    "rubric_set",
    "scoring_ruleset",
    "knowledge_base",
    "prompt_contract",
    "model_config",
    "learning_content",
    "examiner_agent",
]
SnapshotLabel = Literal["published", "superseded", "legacy_unversioned"]
AssetTypeT = TypeVar("AssetTypeT", bound=str)
AssetVersionT = TypeVar("AssetVersionT", int, str, int | str)
SnapshotLabelT = TypeVar("SnapshotLabelT", bound=str)


class AssetRef(BaseModel, Generic[AssetTypeT, AssetVersionT, SnapshotLabelT]):
    asset_type: AssetTypeT
    asset_id: str
    version: AssetVersionT
    hash: str
    snapshot_label: SnapshotLabelT


@dataclass(frozen=True, slots=True)
class PublishedAssetRef:
    asset_type: str
    asset_id: str | None
    asset_code: str | None
    version: str
    content_hash: str
    snapshot_label: str
    source_bundle_key: str | None
    source_config_version_id: str | None
    source_config_id: str | None
    snapshot_selector: str | None
    source_snapshot_hash: str | None
    resolved_at: str
    logical_id: str | None = None
    revision_id: str | None = None
    revision_no: int | None = None

    def can_reconstruct_from_snapshot(self) -> bool:
        return bool(self.source_config_version_id and self.snapshot_selector)

    @classmethod
    def from_schema(cls, schema: PublishedAssetRefSchema) -> PublishedAssetRef:
        return cls(**schema.model_dump())

    def to_schema(self) -> PublishedAssetRefSchema:
        return PublishedAssetRefSchema.model_validate(asdict(self))


class PublishedAssetRefSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_type: str = Field(..., min_length=1, max_length=80)
    asset_id: str | None = Field(None, min_length=1, max_length=36)
    asset_code: str | None = Field(None, min_length=1, max_length=120)
    version: str = Field(..., min_length=1, max_length=80)
    content_hash: str = Field(..., min_length=1, max_length=80)
    snapshot_label: SnapshotLabel
    source_bundle_key: str | None = Field(None, min_length=1, max_length=160)
    source_config_version_id: str | None = Field(None, min_length=1, max_length=36)
    source_config_id: str | None = Field(None, min_length=1, max_length=36)
    snapshot_selector: str | None = Field(None, min_length=1, max_length=200)
    source_snapshot_hash: str | None = Field(None, min_length=1, max_length=80)
    resolved_at: str = Field(..., min_length=1, max_length=40)
    logical_id: str | None = Field(None, min_length=1, max_length=80)
    revision_id: str | None = Field(None, min_length=1, max_length=36)
    revision_no: int | None = Field(None, ge=1)

    @model_validator(mode="after")
    def validate_governance_source(self) -> PublishedAssetRefSchema:
        governance_fields = {
            "source_config_version_id": self.source_config_version_id,
            "source_config_id": self.source_config_id,
            "snapshot_selector": self.snapshot_selector,
            "source_snapshot_hash": self.source_snapshot_hash,
        }
        has_bundle = bool(self.source_bundle_key)
        present = {key for key, value in governance_fields.items() if value}
        if has_bundle:
            missing = sorted(set(governance_fields) - present)
            if missing:
                raise ValueError(
                    "ConfigBundle-governed PublishedAssetRef requires "
                    f"{', '.join(missing)}"
                )
        elif present:
            raise ValueError(
                "Native PublishedAssetRef cannot include partial ConfigBundle "
                f"governance fields: {', '.join(sorted(present))}"
            )
        return self

    def to_dataclass(self) -> PublishedAssetRef:
        return PublishedAssetRef.from_schema(self)


class PublishedTemplateRef(
    AssetRef[Literal["practice_template"], int, Literal["published"]]
):
    asset_type: Literal["practice_template"] = "practice_template"
    version: int
    snapshot_label: Literal["published"] = "published"


class CurriculumVersionRef(AssetRef[CurriculumAssetType, int | str, SnapshotLabel]):
    asset_type: CurriculumAssetType
    snapshot_label: SnapshotLabel


class LearningContentRef(
    AssetRef[Literal["learning_content"], int, Literal["published"]]
):
    asset_type: Literal["learning_content"] = "learning_content"
    version: int
    snapshot_label: Literal["published"] = "published"


class TestBankRef(AssetRef[Literal["question_item"], int, Literal["published"]]):
    asset_type: Literal["question_item"] = "question_item"
    version: int
    snapshot_label: Literal["published"] = "published"
