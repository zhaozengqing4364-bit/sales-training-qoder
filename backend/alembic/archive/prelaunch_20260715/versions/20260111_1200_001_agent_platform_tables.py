"""Agent Platform Tables Migration

Creates tables for Agent Platform upgrade:
- agents: AI training scenarios (R1, R2)
- personas: AI characters for practice (R3)
- knowledge_bases: Document collections for AI context (R5)
- knowledge_documents: Documents within knowledge bases (R5)
- agent_personas: Agent-Persona associations (R4)
- conversation_messages: Practice conversation messages (R9)
- ALTER practice_sessions: Add agent_id, persona_id (R12)

Revision ID: 001
Revises: None
Create Date: 2026-01-11 12:00:00.000000

Requirements: R1-R5, R9, R12, R13
Design: Section 13-19, 21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create Agent Platform tables in dependency order."""
    
    # 1. Create agents table (R1, R2)
    # No foreign key dependencies except users (optional)
    op.create_table(
        'agents',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('icon', sa.String(50), nullable=True),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('system_prompt', sa.Text(), nullable=True),
        sa.Column('welcome_message', sa.Text(), nullable=True),
        sa.Column('capabilities_config', sa.JSON(), nullable=True, default=dict),
        sa.Column('default_knowledge_base_ids', sa.JSON(), nullable=True, default=list),
        sa.Column('status', sa.String(20), nullable=False, default='draft'),
        sa.Column('version', sa.Integer(), nullable=False, default=1),
        sa.Column('created_by', sa.String(36), sa.ForeignKey('users.user_id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name='ck_agent_status'
        ),
        sa.CheckConstraint(
            "category IN ('sales', 'presentation', 'interview', 'customer_service')",
            name='ck_agent_category'
        ),
    )
    op.create_index('idx_agents_status', 'agents', ['status'])
    op.create_index('idx_agents_category', 'agents', ['category'])
    op.create_index('idx_agents_created_at', 'agents', ['created_at'])
    
    # 2. Create personas table (R3)
    # No foreign key dependencies except users (optional)
    op.create_table(
        'personas',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('icon', sa.String(50), nullable=True),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('difficulty', sa.String(20), nullable=False, default='medium'),
        sa.Column('system_prompt', sa.Text(), nullable=False),
        sa.Column('traits', sa.JSON(), nullable=True, default=dict),
        sa.Column('knowledge_base_ids', sa.JSON(), nullable=True, default=list),
        sa.Column('behavior_config', sa.JSON(), nullable=True, default=dict),
        sa.Column('scoring_weights', sa.JSON(), nullable=True),
        sa.Column('is_public', sa.Boolean(), nullable=False, default=True),
        sa.Column('status', sa.String(20), nullable=False, default='active'),
        sa.Column('created_by', sa.String(36), sa.ForeignKey('users.user_id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('active', 'inactive')",
            name='ck_persona_status'
        ),
        sa.CheckConstraint(
            "category IN ('customer', 'interviewer', 'coach', 'examiner')",
            name='ck_persona_category'
        ),
        sa.CheckConstraint(
            "difficulty IN ('easy', 'medium', 'hard')",
            name='ck_persona_difficulty'
        ),
    )
    op.create_index('idx_personas_category', 'personas', ['category'])
    op.create_index('idx_personas_difficulty', 'personas', ['difficulty'])
    op.create_index('idx_personas_status', 'personas', ['status'])
    
    # 3. Create knowledge_bases table (R5)
    # No foreign key dependencies
    op.create_table(
        'knowledge_bases',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('vector_collection', sa.String(100), nullable=False),
        sa.Column('embedding_model', sa.String(100), nullable=False, default='text-embedding-ada-002'),
        sa.Column('document_count', sa.Integer(), nullable=False, default=0),
        sa.Column('total_chunks', sa.Integer(), nullable=False, default=0),
        sa.Column('status', sa.String(20), nullable=False, default='active'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('active', 'archived')",
            name='ck_knowledge_base_status'
        ),
        sa.CheckConstraint(
            "category IN ('product', 'competitor', 'faq', 'policy')",
            name='ck_knowledge_base_category'
        ),
    )
    op.create_index('idx_knowledge_bases_status', 'knowledge_bases', ['status'])
    op.create_index('idx_knowledge_bases_category', 'knowledge_bases', ['category'])
    op.create_index('idx_knowledge_bases_created_at', 'knowledge_bases', ['created_at'])
    
    # 4. Create knowledge_documents table (R5)
    # Depends on: knowledge_bases
    op.create_table(
        'knowledge_documents',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('knowledge_base_id', sa.String(36), sa.ForeignKey('knowledge_bases.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('file_type', sa.String(20), nullable=False),
        sa.Column('file_url', sa.String(500), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, default='pending'),
        sa.Column('chunk_count', sa.Integer(), nullable=False, default=0),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'ready', 'failed')",
            name='ck_knowledge_document_status'
        ),
        sa.CheckConstraint(
            "file_type IN ('pdf', 'docx', 'txt', 'md')",
            name='ck_knowledge_document_file_type'
        ),
    )
    op.create_index('idx_knowledge_documents_status', 'knowledge_documents', ['status'])
    op.create_index('idx_knowledge_documents_knowledge_base', 'knowledge_documents', ['knowledge_base_id'])
    op.create_index('idx_knowledge_documents_created_at', 'knowledge_documents', ['created_at'])
    
    # 5. Create agent_personas table (R4)
    # Depends on: agents, personas
    op.create_table(
        'agent_personas',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('agent_id', sa.String(36), sa.ForeignKey('agents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('persona_id', sa.String(36), sa.ForeignKey('personas.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('display_order', sa.Integer(), nullable=False, default=0),
        sa.Column('is_default', sa.Boolean(), nullable=False, default=False),
        sa.Column('override_config', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('agent_id', 'persona_id', name='uq_agent_persona'),
    )
    op.create_index('idx_agent_personas_agent', 'agent_personas', ['agent_id'])
    op.create_index('idx_agent_personas_persona', 'agent_personas', ['persona_id'])
    
    # 6. Create conversation_messages table (R9)
    # Depends on: practice_sessions
    op.create_table(
        'conversation_messages',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('session_id', sa.String(36), sa.ForeignKey('practice_sessions.session_id', ondelete='CASCADE'), nullable=False),
        sa.Column('turn_number', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('audio_url', sa.String(500), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('fuzzy_words', sa.JSON(), nullable=True),
        sa.Column('sales_stage', sa.String(50), nullable=True),
        sa.Column('score_snapshot', sa.JSON(), nullable=True),
        sa.Column('ai_feedback', sa.Text(), nullable=True),
        sa.Column('is_highlight', sa.Boolean(), nullable=False, default=False),
        sa.Column('highlight_type', sa.String(20), nullable=True),
        sa.Column('highlight_reason', sa.String(200), nullable=True),
        sa.CheckConstraint(
            "role IN ('user', 'assistant')",
            name='ck_conversation_message_role'
        ),
        sa.CheckConstraint(
            "highlight_type IS NULL OR highlight_type IN ('good', 'bad', 'neutral')",
            name='ck_conversation_message_highlight_type'
        ),
        sa.CheckConstraint(
            "sales_stage IS NULL OR sales_stage IN ('opening', 'discovery', 'presentation', 'objection', 'closing')",
            name='ck_conversation_message_sales_stage'
        ),
    )
    op.create_index('ix_conversation_messages_session_turn', 'conversation_messages', ['session_id', 'turn_number'])
    op.create_index('idx_conversation_messages_session', 'conversation_messages', ['session_id'])
    op.create_index('idx_conversation_messages_timestamp', 'conversation_messages', ['timestamp'])
    op.create_index('idx_conversation_messages_is_highlight', 'conversation_messages', ['is_highlight'])
    
    # 7. ALTER practice_sessions table (R12)
    # Add agent_id and persona_id columns with foreign keys
    op.add_column('practice_sessions', sa.Column('agent_id', sa.String(36), nullable=True))
    op.add_column('practice_sessions', sa.Column('persona_id', sa.String(36), nullable=True))
    
    # Create foreign key constraints with SET NULL on delete
    op.create_foreign_key(
        'fk_practice_sessions_agent',
        'practice_sessions', 'agents',
        ['agent_id'], ['id'],
        ondelete='SET NULL'
    )
    op.create_foreign_key(
        'fk_practice_sessions_persona',
        'practice_sessions', 'personas',
        ['persona_id'], ['id'],
        ondelete='SET NULL'
    )
    
    # Create indexes for the new columns
    op.create_index('idx_sessions_agent', 'practice_sessions', ['agent_id'])
    op.create_index('idx_sessions_persona', 'practice_sessions', ['persona_id'])


def downgrade() -> None:
    """Drop Agent Platform tables in reverse dependency order."""
    
    # 7. Remove agent_id and persona_id from practice_sessions
    op.drop_index('idx_sessions_persona', table_name='practice_sessions')
    op.drop_index('idx_sessions_agent', table_name='practice_sessions')
    op.drop_constraint('fk_practice_sessions_persona', 'practice_sessions', type_='foreignkey')
    op.drop_constraint('fk_practice_sessions_agent', 'practice_sessions', type_='foreignkey')
    op.drop_column('practice_sessions', 'persona_id')
    op.drop_column('practice_sessions', 'agent_id')
    
    # 6. Drop conversation_messages
    op.drop_index('idx_conversation_messages_is_highlight', table_name='conversation_messages')
    op.drop_index('idx_conversation_messages_timestamp', table_name='conversation_messages')
    op.drop_index('idx_conversation_messages_session', table_name='conversation_messages')
    op.drop_index('ix_conversation_messages_session_turn', table_name='conversation_messages')
    op.drop_table('conversation_messages')
    
    # 5. Drop agent_personas
    op.drop_index('idx_agent_personas_persona', table_name='agent_personas')
    op.drop_index('idx_agent_personas_agent', table_name='agent_personas')
    op.drop_table('agent_personas')
    
    # 4. Drop knowledge_documents
    op.drop_index('idx_knowledge_documents_created_at', table_name='knowledge_documents')
    op.drop_index('idx_knowledge_documents_knowledge_base', table_name='knowledge_documents')
    op.drop_index('idx_knowledge_documents_status', table_name='knowledge_documents')
    op.drop_table('knowledge_documents')
    
    # 3. Drop knowledge_bases
    op.drop_index('idx_knowledge_bases_created_at', table_name='knowledge_bases')
    op.drop_index('idx_knowledge_bases_category', table_name='knowledge_bases')
    op.drop_index('idx_knowledge_bases_status', table_name='knowledge_bases')
    op.drop_table('knowledge_bases')
    
    # 2. Drop personas
    op.drop_index('idx_personas_status', table_name='personas')
    op.drop_index('idx_personas_difficulty', table_name='personas')
    op.drop_index('idx_personas_category', table_name='personas')
    op.drop_table('personas')
    
    # 1. Drop agents
    op.drop_index('idx_agents_created_at', table_name='agents')
    op.drop_index('idx_agents_category', table_name='agents')
    op.drop_index('idx_agents_status', table_name='agents')
    op.drop_table('agents')
