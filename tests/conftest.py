"""
Фикстуры для тестов.
"""

import pytest
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from bot.database.models import Base, Teacher, Subject, Student, SubjectStudent, Attendance


@pytest.fixture(scope="function")
def engine():
    """Создать тестовый движок SQLite в памяти."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def session(engine):
    """Создать тестовую сессию."""
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def teacher(session):
    """Создать тестового преподавателя."""
    teacher = Teacher(telegram_id=123456789, name="Тестовый Преподаватель")
    session.add(teacher)
    session.commit()
    session.refresh(teacher)
    return teacher


@pytest.fixture
def subject(session, teacher):
    """Создать тестовую дисциплину."""
    subject = Subject(teacher_id=teacher.id, name="Тестовая дисциплина")
    session.add(subject)
    session.commit()
    session.refresh(subject)
    return subject


@pytest.fixture
def students(session, teacher):
    """Создать тестовых студентов."""
    students_data = [
        Student(teacher_id=teacher.id, full_name="Иванов Иван Иванович"),
        Student(teacher_id=teacher.id, full_name="Петров Пётр Петрович"),
        Student(teacher_id=teacher.id, full_name="Сидоров Сидор Сидорович"),
    ]
    session.add_all(students_data)
    session.commit()
    for s in students_data:
        session.refresh(s)
    return students_data


@pytest.fixture
def subject_with_students(session, subject, students):
    """Дисциплина с привязанными студентами."""
    for student in students:
        link = SubjectStudent(subject_id=subject.id, student_id=student.id)
        session.add(link)
    session.commit()
    return subject


@pytest.fixture
def attendance_data(session, subject_with_students, students):
    """Тестовые данные посещаемости."""
    dates = [date(2024, 11, 1), date(2024, 11, 8), date(2024, 11, 15)]
    
    # Иванов - 100% (3/3)
    # Петров - 66% (2/3)
    # Сидоров - 33% (1/3)
    
    attendance_records = [
        # 01.11 - все присутствовали
        Attendance(student_id=students[0].id, subject_id=subject_with_students.id, date=dates[0], is_present=True),
        Attendance(student_id=students[1].id, subject_id=subject_with_students.id, date=dates[0], is_present=True),
        Attendance(student_id=students[2].id, subject_id=subject_with_students.id, date=dates[0], is_present=True),
        # 08.11 - Сидоров отсутствует
        Attendance(student_id=students[0].id, subject_id=subject_with_students.id, date=dates[1], is_present=True),
        Attendance(student_id=students[1].id, subject_id=subject_with_students.id, date=dates[1], is_present=True),
        Attendance(student_id=students[2].id, subject_id=subject_with_students.id, date=dates[1], is_present=False),
        # 15.11 - только Иванов
        Attendance(student_id=students[0].id, subject_id=subject_with_students.id, date=dates[2], is_present=True),
        Attendance(student_id=students[1].id, subject_id=subject_with_students.id, date=dates[2], is_present=False),
        Attendance(student_id=students[2].id, subject_id=subject_with_students.id, date=dates[2], is_present=False),
    ]
    
    session.add_all(attendance_records)
    session.commit()
    
    return {
        "dates": dates,
        "subject": subject_with_students,
        "students": students,
    }

