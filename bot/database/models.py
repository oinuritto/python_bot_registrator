"""
Модели базы данных SQLAlchemy.

Схема:
- Teacher: преподаватель (привязан к telegram_id)
- Subject: дисциплина (принадлежит преподавателю)
- Student: студент (принадлежит дисциплине)
- Attendance: запись о посещаемости
"""

from datetime import datetime, date
from typing import List, Optional

from sqlalchemy import ForeignKey, String, Date, DateTime, Boolean
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Базовый класс для всех моделей."""
    pass


class Teacher(Base):
    """Модель преподавателя."""
    __tablename__ = "teachers"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Связь с дисциплинами
    subjects: Mapped[List["Subject"]] = relationship(
        back_populates="teacher",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"Teacher(id={self.id}, name={self.name!r}, telegram_id={self.telegram_id})"


class Subject(Base):
    """Модель дисциплины."""
    __tablename__ = "subjects"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Связь с преподавателем
    teacher: Mapped["Teacher"] = relationship(back_populates="subjects")
    
    # Связь со студентами
    students: Mapped[List["Student"]] = relationship(
        back_populates="subject",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"Subject(id={self.id}, name={self.name!r})"


class Student(Base):
    """Модель студента."""
    __tablename__ = "students"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(200))
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Связь с дисциплиной
    subject: Mapped["Subject"] = relationship(back_populates="students")
    
    # Связь с записями посещаемости
    attendances: Mapped[List["Attendance"]] = relationship(
        back_populates="student",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"Student(id={self.id}, full_name={self.full_name!r})"


class Attendance(Base):
    """Модель записи посещаемости."""
    __tablename__ = "attendance"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"))
    date: Mapped[date] = mapped_column(Date, index=True)
    is_present: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Связь со студентом
    student: Mapped["Student"] = relationship(back_populates="attendances")
    
    def __repr__(self) -> str:
        status = "✓" if self.is_present else "✗"
        return f"Attendance(student_id={self.student_id}, date={self.date}, {status})"

