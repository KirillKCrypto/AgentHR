"""Базовый класс ORM-моделей SQLAlchemy."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Базовый класс всех моделей; `metadata` используется Alembic."""
