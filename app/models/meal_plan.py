from datetime import date, datetime
from enum import Enum

from sqlalchemy import Date, DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class MealCourseRole(str, Enum):
    starter = "starter"
    entree = "entree"
    side = "side"
    dessert = "dessert"


_meal_course_role_col = SAEnum(
    MealCourseRole,
    name="meal_course_role",
    native_enum=False,
    values_callable=lambda x: [e.value for e in x],
)


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

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    meal_plan_week = relationship("MealPlanWeek", back_populates="planned_meals")
    courses = relationship(
        "PlannedMealCourse", back_populates="planned_meal", cascade="all, delete-orphan"
    )
    recipes = relationship(
        "PlannedMealRecipe", back_populates="planned_meal", cascade="all, delete-orphan"
    )


class PlannedMealCourse(Base):
    __tablename__ = "planned_meal_courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    planned_meal_id: Mapped[int] = mapped_column(
        ForeignKey("planned_meals.id", ondelete="CASCADE"), index=True, nullable=False
    )
    role: Mapped[MealCourseRole] = mapped_column(_meal_course_role_col, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    planned_meal = relationship("PlannedMeal", back_populates="courses")
    planned_meal_recipes = relationship(
        "PlannedMealRecipe",
        back_populates="planned_meal_course",
        cascade="all, delete-orphan",
    )


class PlannedMealRecipe(Base):
    __tablename__ = "planned_meal_recipes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    planned_meal_id: Mapped[int] = mapped_column(
        ForeignKey("planned_meals.id"), index=True, nullable=False
    )
    planned_meal_course_id: Mapped[int] = mapped_column(
        ForeignKey("planned_meal_courses.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id"), index=True, nullable=False)
    role: Mapped[MealCourseRole] = mapped_column(_meal_course_role_col, nullable=False)

    planned_meal = relationship("PlannedMeal", back_populates="recipes")
    planned_meal_course = relationship("PlannedMealCourse", back_populates="planned_meal_recipes")
    recipe = relationship("Recipe", back_populates="planned_meal_links")
