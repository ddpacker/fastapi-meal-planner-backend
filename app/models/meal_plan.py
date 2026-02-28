from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class MealPlanWeek(Base):
    __tablename__ = "meal_plan_weeks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user = relationship("User", back_populates="meal_plan_weeks")
    planned_meals = relationship(
        "PlannedMeal", back_populates="meal_plan_week", cascade="all, delete-orphan"
    )
    grocery_lists = relationship(
        "GroceryList", back_populates="meal_plan_week", cascade="all, delete-orphan"
    )


class PlannedMeal(Base):
    __tablename__ = "planned_meals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    meal_plan_week_id: Mapped[int] = mapped_column(
        ForeignKey("meal_plan_weeks.id"), index=True, nullable=False
    )
    day_index: Mapped[int] = mapped_column(Integer, nullable=False)  # 0–6
    meal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")
    # Optional reference to a reusable recipe
    recipe_id: Mapped[int | None] = mapped_column(
        ForeignKey("recipes.id"), nullable=True, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    meal_plan_week = relationship("MealPlanWeek", back_populates="planned_meals")
    recipe = relationship("Recipe", back_populates="planned_meals")

