"""SQLAlchemy models. Base.metadata is the target of Alembic autogenerate."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
