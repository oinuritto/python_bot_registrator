"""
Модели базы данных SQLAlchemy.

Схема:
- Teacher: преподаватель (привязан к telegram_id)
- Subject: дисциплина (принадлежит преподавателю)
- Student: студент (принадлежит преподавателю - общий пул)
- SubjectStudent: связь многие-ко-многим между Subject и Student
- Attendance: запись о посещаемости (привязана к студенту И дисциплине)
"""

from datetime import datetime, date
from typing import List

from sqlalchemy import ForeignKey, String, Date, DateTime, Boolean, UniqueConstraint
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow)

    # Связь с дисциплинами
    subjects: Mapped[List["Subject"]] = relationship(
        back_populates="teacher",
        cascade="all, delete-orphan"
    )

    # Связь со студентами (общий пул)
    students: Mapped[List["Student"]] = relationship(
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow)

    # Связь с преподавателем
    teacher: Mapped["Teacher"] = relationship(back_populates="subjects")

    # Связь со студентами через промежуточную таблицу
    subject_students: Mapped[List["SubjectStudent"]] = relationship(
        back_populates="subject",
        cascade="all, delete-orphan"
    )

    # Связь с записями посещаемости
    attendances: Mapped[List["Attendance"]] = relationship(
        back_populates="subject",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"Subject(id={self.id}, name={self.name!r})"


class Student(Base):
    """Модель студента (общий пул преподавателя)."""
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(200))
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow)

    # Связь с преподавателем
    teacher: Mapped["Teacher"] = relationship(back_populates="students")

    # Связь с дисциплинами через промежуточную таблицу
    subject_students: Mapped[List["SubjectStudent"]] = relationship(
        back_populates="student",
        cascade="all, delete-orphan"
    )

    # Связь с записями посещаемости
    attendances: Mapped[List["Attendance"]] = relationship(
        back_populates="student",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"Student(id={self.id}, full_name={self.full_name!r})"


class SubjectStudent(Base):
    """Связь многие-ко-многим между дисциплиной и студентом."""
    __tablename__ = "subject_students"

    id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"))
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"))
    added_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow)

    # Уникальное ограничение - студент может быть в дисциплине только один раз
    __table_args__ = (
        UniqueConstraint('subject_id', 'student_id',
                         name='unique_subject_student'),
    )

    # Связи
    subject: Mapped["Subject"] = relationship(
        back_populates="subject_students")
    student: Mapped["Student"] = relationship(
        back_populates="subject_students")

    def __repr__(self) -> str:
        return f"SubjectStudent(subject_id={self.subject_id}, student_id={self.student_id})"


class Attendance(Base):
    """Модель записи посещаемости."""
    __tablename__ = "attendance"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"))
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"))
    date: Mapped[date] = mapped_column(Date, index=True)
    is_present: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow)

    # Уникальное ограничение - одна запись на студента/дисциплину/дату
    __table_args__ = (
        UniqueConstraint('student_id', 'subject_id',
                         'date', name='unique_attendance'),
    )

    # Связи
    student: Mapped["Student"] = relationship(back_populates="attendances")
    subject: Mapped["Subject"] = relationship(back_populates="attendances")

    def __repr__(self) -> str:
        status = "✓" if self.is_present else "✗"
        return f"Attendance(student_id={self.student_id}, subject_id={self.subject_id}, date={self.date}, {status})"
