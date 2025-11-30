"""
Тесты CRUD операций.
"""

from datetime import date

from bot.database import crud


class TestTeacherCRUD:
    """Тесты для операций с преподавателями."""

    def test_get_or_create_teacher_new(self, session):
        """Создание нового преподавателя."""
        teacher = crud.get_or_create_teacher(
            session, telegram_id=111, name="Новый")

        assert teacher.id is not None
        assert teacher.telegram_id == 111
        assert teacher.name == "Новый"

    def test_get_or_create_teacher_existing(self, session, teacher):
        """Получение существующего преподавателя."""
        same_teacher = crud.get_or_create_teacher(
            session, telegram_id=teacher.telegram_id, name="Другое имя"
        )

        assert same_teacher.id == teacher.id
        assert same_teacher.name == teacher.name  # Имя не меняется

    def test_get_teacher_by_telegram_id(self, session, teacher):
        """Получение преподавателя по telegram_id."""
        found = crud.get_teacher_by_telegram_id(session, teacher.telegram_id)

        assert found is not None
        assert found.id == teacher.id

    def test_get_teacher_by_telegram_id_not_found(self, session):
        """Преподаватель не найден."""
        found = crud.get_teacher_by_telegram_id(session, 999999)

        assert found is None


class TestSubjectCRUD:
    """Тесты для операций с дисциплинами."""

    def test_create_subject(self, session, teacher):
        """Создание дисциплины."""
        subject = crud.create_subject(session, teacher.id, "Математика")

        assert subject.id is not None
        assert subject.name == "Математика"
        assert subject.teacher_id == teacher.id

    def test_get_subjects_by_teacher(self, session, teacher):
        """Получение дисциплин преподавателя."""
        crud.create_subject(session, teacher.id, "Физика")
        crud.create_subject(session, teacher.id, "Химия")

        subjects = crud.get_subjects_by_teacher(session, teacher.id)

        assert len(subjects) == 2
        names = [s.name for s in subjects]
        assert "Физика" in names
        assert "Химия" in names

    def test_get_subject_by_id(self, session, subject):
        """Получение дисциплины по ID."""
        found = crud.get_subject_by_id(session, subject.id)

        assert found is not None
        assert found.name == subject.name

    def test_update_subject(self, session, subject):
        """Обновление названия дисциплины."""
        updated = crud.update_subject(session, subject.id, "Новое название")

        assert updated.name == "Новое название"

    def test_delete_subject(self, session, subject):
        """Удаление дисциплины."""
        subject_id = subject.id
        result = crud.delete_subject(session, subject_id)

        assert result is True
        assert crud.get_subject_by_id(session, subject_id) is None


class TestStudentCRUD:
    """Тесты для операций со студентами."""

    def test_create_student(self, session, teacher):
        """Создание студента."""
        student = crud.create_student(
            session, teacher.id, "Тестов Тест Тестович")

        assert student.id is not None
        assert student.full_name == "Тестов Тест Тестович"
        assert student.teacher_id == teacher.id

    def test_create_students_bulk(self, session, teacher):
        """Массовое создание студентов."""
        names = ["Студент 1", "Студент 2", "Студент 3"]
        students = crud.create_students_bulk(session, teacher.id, names)

        assert len(students) == 3
        assert all(s.teacher_id == teacher.id for s in students)

    def test_get_all_students_by_teacher(self, session, teacher, students):  # pylint: disable=unused-argument
        """Получение всех студентов преподавателя."""
        # students фикстура нужна для создания данных
        found = crud.get_all_students_by_teacher(session, teacher.id)

        assert len(found) == 3

    def test_update_student(self, session, students):
        """Обновление ФИО студента."""
        student = students[0]
        updated = crud.update_student(session, student.id, "Новое ФИО")

        assert updated.full_name == "Новое ФИО"

    def test_delete_student(self, session, students):
        """Удаление студента."""
        student_id = students[0].id
        result = crud.delete_student(session, student_id)

        assert result is True
        assert crud.get_student_by_id(session, student_id) is None


class TestSubjectStudentCRUD:
    """Тесты для связи студент-дисциплина."""

    def test_add_student_to_subject(self, session, subject, students):
        """Добавление студента в дисциплину."""
        link = crud.add_student_to_subject(session, subject.id, students[0].id)

        assert link is not None
        assert link.subject_id == subject.id
        assert link.student_id == students[0].id

    def test_add_student_to_subject_duplicate(self, session, subject, students):
        """Повторное добавление не создаёт дубликат."""
        crud.add_student_to_subject(session, subject.id, students[0].id)
        _ = crud.add_student_to_subject(
            session, subject.id, students[0].id)

        # Должен вернуть существующую связь
        students_in_subject = crud.get_students_by_subject(session, subject.id)
        assert len(students_in_subject) == 1

    def test_get_students_by_subject(self, session, subject_with_students, students):  # pylint: disable=unused-argument
        """Получение студентов дисциплины."""
        # students фикстура нужна для subject_with_students
        found = crud.get_students_by_subject(session, subject_with_students.id)

        assert len(found) == 3

    def test_remove_student_from_subject(self, session, subject_with_students, students):
        """Удаление студента из дисциплины."""
        result = crud.remove_student_from_subject(
            session, subject_with_students.id, students[0].id
        )

        assert result is True

        remaining = crud.get_students_by_subject(
            session, subject_with_students.id)
        assert len(remaining) == 2

    def test_count_students_in_subject(self, session, subject_with_students):
        """Подсчёт студентов в дисциплине."""
        count = crud.count_students_in_subject(
            session, subject_with_students.id)

        assert count == 3


class TestAttendanceCRUD:
    """Тесты для операций с посещаемостью."""

    def test_set_attendance_new(self, session, subject_with_students, students):
        """Создание записи посещаемости."""
        today = date.today()
        att = crud.set_attendance(
            session, students[0].id, subject_with_students.id, today, True
        )

        assert att.id is not None
        assert att.is_present is True

    def test_set_attendance_update(self, session, subject_with_students, students):
        """Обновление записи посещаемости."""
        today = date.today()

        # Создаём с is_present=True
        crud.set_attendance(
            session, students[0].id, subject_with_students.id, today, True)

        # Обновляем на False
        att = crud.set_attendance(
            session, students[0].id, subject_with_students.id, today, False
        )

        assert att.is_present is False

    def test_get_attendance_by_subject_and_date(self, session, attendance_data):
        """Получение посещаемости на дату."""
        subject = attendance_data["subject"]
        test_date = attendance_data["dates"][0]

        result = crud.get_attendance_by_subject_and_date(
            session, subject.id, test_date)

        assert len(result) == 3
        # Все присутствовали 01.11
        assert all(v is True for v in result.values())

    def test_get_subject_attendance_dates(self, session, attendance_data):
        """Получение дат занятий."""
        subject = attendance_data["subject"]

        dates = crud.get_subject_attendance_dates(session, subject.id)

        assert len(dates) == 3
        assert date(2024, 11, 1) in dates
        assert date(2024, 11, 8) in dates
        assert date(2024, 11, 15) in dates

    def test_get_student_attendance_by_subject(self, session, attendance_data):
        """Получение посещаемости студента по дисциплине."""
        subject = attendance_data["subject"]
        students = attendance_data["students"]

        # Иванов - все присутствовал
        att = crud.get_student_attendance_by_subject(
            session, students[0].id, subject.id)

        assert len(att) == 3
        assert all(a.is_present for a in att)
