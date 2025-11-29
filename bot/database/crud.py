"""
CRUD операции для работы с базой данных.
"""

from datetime import date
from typing import Optional, List

from sqlalchemy.orm import Session
from sqlalchemy import select

from bot.database.models import Teacher, Subject, Student, Attendance


# === Teacher CRUD ===

def get_or_create_teacher(session: Session, telegram_id: int, name: str) -> Teacher:
    """Получить или создать преподавателя по telegram_id."""
    teacher = session.execute(
        select(Teacher).where(Teacher.telegram_id == telegram_id)
    ).scalar_one_or_none()
    
    if not teacher:
        teacher = Teacher(telegram_id=telegram_id, name=name)
        session.add(teacher)
        session.commit()
        session.refresh(teacher)
    
    return teacher


def get_teacher_by_telegram_id(session: Session, telegram_id: int) -> Optional[Teacher]:
    """Получить преподавателя по telegram_id."""
    return session.execute(
        select(Teacher).where(Teacher.telegram_id == telegram_id)
    ).scalar_one_or_none()


# === Subject CRUD ===

def create_subject(session: Session, teacher_id: int, name: str) -> Subject:
    """Создать новую дисциплину."""
    subject = Subject(teacher_id=teacher_id, name=name)
    session.add(subject)
    session.commit()
    session.refresh(subject)
    return subject


def get_subjects_by_teacher(session: Session, teacher_id: int) -> List[Subject]:
    """Получить все дисциплины преподавателя."""
    result = session.execute(
        select(Subject).where(Subject.teacher_id == teacher_id).order_by(Subject.name)
    )
    return list(result.scalars().all())


def get_subject_by_id(session: Session, subject_id: int) -> Optional[Subject]:
    """Получить дисциплину по ID."""
    return session.get(Subject, subject_id)


def update_subject(session: Session, subject_id: int, name: str) -> Optional[Subject]:
    """Обновить название дисциплины."""
    subject = session.get(Subject, subject_id)
    if subject:
        subject.name = name
        session.commit()
        session.refresh(subject)
    return subject


def delete_subject(session: Session, subject_id: int) -> bool:
    """Удалить дисциплину."""
    subject = session.get(Subject, subject_id)
    if subject:
        session.delete(subject)
        session.commit()
        return True
    return False


# === Student CRUD ===

def create_student(session: Session, subject_id: int, full_name: str) -> Student:
    """Создать нового студента."""
    student = Student(subject_id=subject_id, full_name=full_name)
    session.add(student)
    session.commit()
    session.refresh(student)
    return student


def create_students_bulk(session: Session, subject_id: int, names: List[str]) -> List[Student]:
    """Массовое создание студентов."""
    students = [Student(subject_id=subject_id, full_name=name.strip()) for name in names if name.strip()]
    session.add_all(students)
    session.commit()
    for student in students:
        session.refresh(student)
    return students


def get_students_by_subject(session: Session, subject_id: int) -> List[Student]:
    """Получить всех студентов дисциплины."""
    result = session.execute(
        select(Student).where(Student.subject_id == subject_id).order_by(Student.full_name)
    )
    return list(result.scalars().all())


def get_student_by_id(session: Session, student_id: int) -> Optional[Student]:
    """Получить студента по ID."""
    return session.get(Student, student_id)


def update_student(session: Session, student_id: int, full_name: str) -> Optional[Student]:
    """Обновить ФИО студента."""
    student = session.get(Student, student_id)
    if student:
        student.full_name = full_name
        session.commit()
        session.refresh(student)
    return student


def delete_student(session: Session, student_id: int) -> bool:
    """Удалить студента."""
    student = session.get(Student, student_id)
    if student:
        session.delete(student)
        session.commit()
        return True
    return False


# === Attendance CRUD ===

def set_attendance(
    session: Session, 
    student_id: int, 
    attendance_date: date, 
    is_present: bool
) -> Attendance:
    """Установить/обновить посещаемость студента на дату."""
    # Ищем существующую запись
    attendance = session.execute(
        select(Attendance).where(
            Attendance.student_id == student_id,
            Attendance.date == attendance_date
        )
    ).scalar_one_or_none()
    
    if attendance:
        attendance.is_present = is_present
    else:
        attendance = Attendance(
            student_id=student_id,
            date=attendance_date,
            is_present=is_present
        )
        session.add(attendance)
    
    session.commit()
    session.refresh(attendance)
    return attendance


def get_attendance_by_subject_and_date(
    session: Session,
    subject_id: int,
    attendance_date: date
) -> dict[int, bool]:
    """Получить посещаемость по дисциплине на дату. 
    Возвращает {student_id: is_present}."""
    result = session.execute(
        select(Attendance)
        .join(Student)
        .where(
            Student.subject_id == subject_id,
            Attendance.date == attendance_date
        )
    )
    return {att.student_id: att.is_present for att in result.scalars().all()}


def get_student_attendance(session: Session, student_id: int) -> List[Attendance]:
    """Получить все записи посещаемости студента."""
    result = session.execute(
        select(Attendance)
        .where(Attendance.student_id == student_id)
        .order_by(Attendance.date)
    )
    return list(result.scalars().all())


def get_subject_attendance_dates(session: Session, subject_id: int) -> List[date]:
    """Получить все даты занятий по дисциплине."""
    result = session.execute(
        select(Attendance.date)
        .join(Student)
        .where(Student.subject_id == subject_id)
        .distinct()
        .order_by(Attendance.date)
    )
    return list(result.scalars().all())

