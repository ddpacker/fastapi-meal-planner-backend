from enum import Enum

from sqlalchemy import Enum as SAEnum, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class UnitSystem(str, Enum):
    metric = "metric"
    imperial = "imperial"


_unit_system_col = SAEnum(
    UnitSystem,
    name="unit_system",
    native_enum=False,
    values_callable=lambda x: [e.value for e in x],
)


class UserPreferences(Base):
    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), unique=True, index=True, nullable=False
    )
    unit_system: Mapped[UnitSystem] = mapped_column(
        _unit_system_col,
        nullable=False,
        default=UnitSystem.metric,
        server_default=UnitSystem.metric.value,
    )

    user = relationship("User", back_populates="preferences")
