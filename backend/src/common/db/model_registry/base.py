"""Shared SQLAlchemy declarative metadata for every model registry group."""

from sqlalchemy import JSON, Text
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TypeEngine


class Base(DeclarativeBase):
    """Shared declarative base for all SQLAlchemy ORM models."""


def jsonb_compatible_type() -> TypeEngine[object]:
    return JSON().with_variant(postgresql.JSONB(astext_type=Text()), "postgresql")


_jsonb_compatible_type = jsonb_compatible_type

__all__ = ["Base", "jsonb_compatible_type"]
