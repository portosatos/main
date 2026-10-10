"""dev_clock: the clock offset used in APP_ENV=dev (SPEC F0). A single row with id = 1."""

from sqlalchemy import CheckConstraint, Integer, SmallInteger, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DevClock(Base):
    __tablename__ = "dev_clock"
    __table_args__ = (CheckConstraint("id = 1", name="dev_clock_single_row"),)

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, server_default=text("1"))
    offset_seconds: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
