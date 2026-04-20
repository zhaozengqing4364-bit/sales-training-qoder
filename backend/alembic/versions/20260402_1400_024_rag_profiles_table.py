"""add rag_profiles table and rag_profile_id to knowledge_bases

Revision ID: 024_rag_profiles
Revises: 01240702c090
Create Date: 2026-04-02 14:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "024_rag_profiles"
down_revision: Union[str, None] = "01240702c090"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create rag_profiles table
    op.create_table(
        "rag_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("is_system_default", sa.Integer(), nullable=False, server_default="0"),
        # Chunking
        sa.Column("chunking_strategy", sa.String(50), nullable=False, server_default="element_boundary"),
        sa.Column("chunk_size", sa.Integer(), nullable=False, server_default="500"),
        sa.Column("chunk_overlap", sa.Integer(), nullable=False, server_default="50"),
        # Semantic cache
        sa.Column("semantic_cache_enabled", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("semantic_cache_similarity_threshold", sa.Float(), nullable=False, server_default="0.95"),
        sa.Column("semantic_cache_ttl_seconds", sa.Integer(), nullable=False, server_default="300"),
        # Cross-encoder
        sa.Column("cross_encoder_backend", sa.String(20), nullable=True),
        sa.Column("cross_encoder_model", sa.String(200), nullable=True),
        sa.Column("cross_encoder_device", sa.String(20), nullable=True),
        sa.Column("cross_encoder_api_key", sa.Text(), nullable=True),
        # Audit
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_rag_profiles_name", "rag_profiles", ["name"])
    op.create_index(
        "idx_rag_profiles_system_default", "rag_profiles", ["is_system_default"]
    )

    # 2. Insert system default profile
    op.execute(
        """
        INSERT INTO rag_profiles (id, name, description, is_system_default,
            chunking_strategy, chunk_size, chunk_overlap,
            semantic_cache_enabled, semantic_cache_similarity_threshold,
            semantic_cache_ttl_seconds)
        VALUES (
            'system-default', '系统默认', '系统默认 RAG 配置，所有未指定配置的知识库自动使用',
            1, 'element_boundary', 500, 50, 1, 0.95, 300
        )
        """
    )

    # 3. Add rag_profile_id FK to knowledge_bases
    op.add_column(
        "knowledge_bases",
        sa.Column(
            "rag_profile_id",
            sa.String(36),
            sa.ForeignKey("rag_profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("knowledge_bases", "rag_profile_id")
    op.drop_index("idx_rag_profiles_system_default", table_name="rag_profiles")
    op.drop_index("idx_rag_profiles_name", table_name="rag_profiles")
    op.drop_table("rag_profiles")
