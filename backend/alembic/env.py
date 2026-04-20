import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine, pool

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from common.config import settings
from common.db.models import Base

# Import all models to ensure they are registered with Base.metadata
# Core models (already in common.db.models)
# - User, Scenario, Presentation, Page, RequiredTalkingPoint
# - ForbiddenWord, PracticeSession, InterruptionEvent, LeaderboardEntry

# Agent Platform models (R1-R4)
from agent.models import Agent, Persona, AgentPersona  # noqa: F401

# Knowledge Base models (R5)
from common.knowledge.models import KnowledgeBase, KnowledgeDocument  # noqa: F401
from common.knowledge.rag_profile_models import RagProfile  # noqa: F401

# Conversation models (R9)
from common.conversation.models import ConversationMessage  # noqa: F401

# Model config models
from common.ai.models import ModelConfig  # noqa: F401

# this is the Alembic Config object
config = context.config

# Set database URL from settings (override alembic.ini)
# Replace async drivers with sync equivalents for migrations
db_url = str(settings.DATABASE_URL)
db_url = db_url.replace("+asyncpg", "")  # PostgreSQL async -> sync
db_url = db_url.replace("+aiosqlite", "")  # SQLite async -> sync
config.set_main_option("sqlalchemy.url", db_url)

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well. By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    # Use the URL from settings (already set in config)
    url = config.get_main_option("sqlalchemy.url")
    connectable = create_engine(url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
