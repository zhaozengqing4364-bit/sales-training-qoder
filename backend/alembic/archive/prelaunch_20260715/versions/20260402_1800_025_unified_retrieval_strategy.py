"""unified retrieval strategy: chunking presets + ranking weight columns + kb chunking_preset_key

Revision ID: 025_unified_retrieval
Revises: 024_rag_profiles
Create Date: 2026-04-02 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "025_unified_retrieval"
down_revision: Union[str, None] = "024_rag_profiles"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create knowledge_chunking_presets table
    op.create_table(
        "knowledge_chunking_presets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "config_version_id",
            sa.String(36),
            sa.ForeignKey("knowledge_config_versions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("profile_key", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("chunking_strategy", sa.String(50), nullable=False, server_default="element_boundary"),
        sa.Column("chunk_size", sa.Integer(), nullable=False, server_default="500"),
        sa.Column("chunk_overlap", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("updated_by", sa.String(36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "config_version_id",
            "profile_key",
            name="uq_chunking_preset_version_key",
        ),
    )
    op.create_index(
        "idx_knowledge_chunking_presets_profile_key",
        "knowledge_chunking_presets",
        ["profile_key"],
    )

    # 2. Add unified scoring weight columns to knowledge_ranking_profiles
    op.add_column(
        "knowledge_ranking_profiles",
        sa.Column("base_weight", sa.Float(), nullable=False, server_default="0.50"),
    )
    op.add_column(
        "knowledge_ranking_profiles",
        sa.Column("coverage_weight", sa.Float(), nullable=False, server_default="0.20"),
    )
    op.add_column(
        "knowledge_ranking_profiles",
        sa.Column("phrase_bonus", sa.Float(), nullable=False, server_default="0.15"),
    )
    op.add_column(
        "knowledge_ranking_profiles",
        sa.Column("title_bonus_max", sa.Float(), nullable=False, server_default="0.10"),
    )
    op.add_column(
        "knowledge_ranking_profiles",
        sa.Column("ratio_bonus_max", sa.Float(), nullable=False, server_default="0.05"),
    )
    op.add_column(
        "knowledge_ranking_profiles",
        sa.Column("cross_encoder_weight", sa.Float(), nullable=False, server_default="0.0"),
    )
    op.add_column(
        "knowledge_ranking_profiles",
        sa.Column("diversity_penalty", sa.Float(), nullable=False, server_default="0.12"),
    )

    # 3. Add chunking_preset_key column to knowledge_bases
    op.add_column(
        "knowledge_bases",
        sa.Column("chunking_preset_key", sa.String(100), nullable=True),
    )

    # 4. Migrate data from rag_profiles to knowledge_chunking_presets.
    #    rag_profiles columns: id, name, description, chunking_strategy, chunk_size, chunk_overlap, is_system_default
    #    We map name → profile_key, keep other chunking fields, and reference active config version.
    op.execute(
        """
        INSERT INTO knowledge_chunking_presets (
            id, config_version_id, profile_key, description,
            chunking_strategy, chunk_size, chunk_overlap,
            is_default, enabled, created_at, updated_at
        )
        SELECT
            rp.id,
            kcv.id,
            LOWER(REPLACE(rp.name, ' ', '_')),
            rp.description,
            rp.chunking_strategy,
            rp.chunk_size,
            rp.chunk_overlap,
            rp.is_system_default,
            1,
            rp.created_at,
            COALESCE(rp.updated_at, rp.created_at)
        FROM rag_profiles rp
        CROSS JOIN (
            SELECT kcv.id FROM knowledge_config_versions kcv
            WHERE kcv.status = 'active' AND kcv.enabled = 1
            ORDER BY kcv.updated_at DESC LIMIT 1
        ) kcv
        """
    )

    # 5. Update knowledge_bases.chunking_preset_key from rag_profile mapping
    op.execute(
        """
        UPDATE knowledge_bases kb
        SET chunking_preset_key = (
            SELECT LOWER(REPLACE(rp.name, ' ', '_'))
            FROM rag_profiles rp
            WHERE rp.id = kb.rag_profile_id
        )
        WHERE kb.rag_profile_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_column("knowledge_bases", "chunking_preset_key")

    op.drop_column("knowledge_ranking_profiles", "diversity_penalty")
    op.drop_column("knowledge_ranking_profiles", "cross_encoder_weight")
    op.drop_column("knowledge_ranking_profiles", "ratio_bonus_max")
    op.drop_column("knowledge_ranking_profiles", "title_bonus_max")
    op.drop_column("knowledge_ranking_profiles", "phrase_bonus")
    op.drop_column("knowledge_ranking_profiles", "coverage_weight")
    op.drop_column("knowledge_ranking_profiles", "base_weight")

    op.drop_index(
        "idx_knowledge_chunking_presets_profile_key",
        table_name="knowledge_chunking_presets",
    )
    op.drop_table("knowledge_chunking_presets")
