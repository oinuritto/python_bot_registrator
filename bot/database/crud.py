"""
CRUD операции для работы с базой данных.
"""

from datetime import date
from typing import Optional, List

from sqlalchemy.orm import Session
from sqlalchemy import select

from bot.database.models import Teacher, Subject, Student, SubjectStudent, Attendance


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


# === Student CRUD (общий пул) ===

def create_student(session: Session, teacher_id: int, full_name: str) -> Student:
    """Создать нового студента в общем пуле преподавателя."""
    student = Student(teacher_id=teacher_id, full_name=full_name)
    session.add(student)
    session.commit()
    session.refresh(student)
    return student


def create_students_bulk(session: Session, teacher_id: int, names: List[str]) -> List[Student]:
    """Массовое создание студентов в общем пуле."""
    students = [Student(teacher_id=teacher_id, full_name=name.strip()) for name in names if name.strip()]
    session.add_all(students)
    session.commit()
    for student in students:
        session.refresh(student)
    return students


def get_all_students_by_teacher(session: Session, teacher_id: int) -> List[Student]:
    """Получить всех студентов преподавателя (общий пул)."""
    result = session.execute(
        select(Student).where(Student.teacher_id == teacher_id).order_by(Student.full_name)
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
    """Удалить студента из общего пула."""
    student = session.get(Student, student_id)
    if student:
        session.delete(student)
        session.commit()
        return True
    return False


# === SubjectStudent CRUD (связь студент-дисциплина) ===

def add_student_to_subject(session: Session, subject_id: int, student_id: int) -> Optional[SubjectStudent]:
    """Добавить студента в дисциплину."""
    # Проверяем, не добавлен ли уже
    existing = session.execute(
        select(SubjectStudent).where(
            SubjectStudent.subject_id == subject_id,
            SubjectStudent.student_id == student_id
        )
    ).scalar_one_or_none()
    
    if existing:
        return existing  # Уже добавлен
    
    link = SubjectStudent(subject_id=subject_id, student_id=student_id)
    session.add(link)
    session.commit()
    session.refresh(link)
    return link


def remove_student_from_subject(session: Session, subject_id: int, student_id: int) -> bool:
    """Удалить студента из дисциплины (отвязать)."""
    link = session.execute(
        select(SubjectStudent).where(
            SubjectStudent.subject_id == subject_id,
            SubjectStudent.student_id == student_id
        )
    ).scalar_one_or_none()
    
    if link:
        # Удаляем также записи посещаемости этого студента по этой дисциплине
        session.execute(
            Attendance.__table__.delete().where(
                Attendance.student_id == student_id,
                Attendance.subject_id == subject_id
            )
        )
        session.delete(link)
        session.commit()
        return True
    return False


def get_students_by_subject(session: Session, subject_id: int) -> List[Student]:
    """Получить всех студентов дисциплины."""
    result = session.execute(
        select(Student)
        .join(SubjectStudent)
        .where(SubjectStudent.subject_id == subject_id)
        .order_by(Student.full_name)
    )
    return list(result.scalars().all())


def get_students_not_in_subject(session: Session, teacher_id: int, subject_id: int) -> List[Student]:
    """Получить студентов преподавателя, которые НЕ в дисциплине."""
    # Получаем ID студентов, которые уже в дисциплине
    in_subject = session.execute(
        select(SubjectStudent.student_id).where(SubjectStudent.subject_id == subject_id)
    ).scalars().all()
    
    # Получаем остальных
    result = session.execute(
        select(Student)
        .where(
            Student.teacher_id == teacher_id,
            Student.id.notin_(in_subject) if in_subject else True
        )
        .order_by(Student.full_name)
    )
    return list(result.scalars().all())


def get_subjects_by_student(session: Session, student_id: int) -> List[Subject]:
    """Получить все дисциплины студента."""
    result = session.execute(
        select(Subject)
        .join(SubjectStudent)
        .where(SubjectStudent.student_id == student_id)
        .order_by(Subject.name)
    )
    return list(result.scalars().all())


def count_students_in_subject(session: Session, subject_id: int) -> int:
    """Подсчитать количество студентов в дисциплине."""
    result = session.execute(
        select(SubjectStudent).where(SubjectStudent.subject_id == subject_id)
    )
    return len(list(result.scalars().all()))


# === Attendance CRUD ===

def set_attendance(
    session: Session, 
    student_id: int,
    subject_id: int,
    attendance_date: date, 
    is_present: bool
) -> Attendance:
    """Установить/обновить посещаемость студента на дату."""
    # Ищем существующую запись
    attendance = session.execute(
        select(Attendance).where(
            Attendance.student_id == student_id,
            Attendance.subject_id == subject_id,
            Attendance.date == attendance_date
        )
    ).scalar_one_or_none()
    
    if attendance:
        attendance.is_present = is_present
    else:
        attendance = Attendance(
            student_id=student_id,
            subject_id=subject_id,
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
        select(Attendance).where(
            Attendance.subject_id == subject_id,
            Attendance.date == attendance_date
        )
    )
    return {att.student_id: att.is_present for att in result.scalars().all()}


def get_student_attendance_by_subject(
    session: Session, 
    student_id: int, 
    subject_id: int
) -> List[Attendance]:
    """Получить все записи посещаемости студента по конкретной дисциплине."""
    result = session.execute(
        select(Attendance)
        .where(
            Attendance.student_id == student_id,
            Attendance.subject_id == subject_id
        )
        .order_by(Attendance.date)
    )
    return list(result.scalars().all())


def get_student_all_attendance(session: Session, student_id: int) -> List[Attendance]:
    """Получить все записи посещаемости студента по всем дисциплинам."""
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
        .where(Attendance.subject_id == subject_id)
        .distinct()
        .order_by(Attendance.date)
    )
    return list(result.scalars().all())


def get_attendance(
    session: Session,
    student_id: int,
    subject_id: int,
    attendance_date: date
) -> Optional[Attendance]:
    """Получить запись посещаемости студента на конкретную дату."""
    return session.execute(
        select(Attendance).where(
            Attendance.student_id == student_id,
            Attendance.subject_id == subject_id,
            Attendance.date == attendance_date
        )
    ).scalar_one_or_none()
