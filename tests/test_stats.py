"""
Тесты для модуля статистики.
"""

import pytest
from datetime import date
from unittest.mock import patch, MagicMock

from bot.database.models import Teacher, Subject, Student, Attendance


class TestStudentStats:
    """Тесты статистики по студенту."""
    
    def test_student_stats_full_attendance(self, session, attendance_data):
        """Студент с полной посещаемостью."""
        from bot.utils.stats import get_student_stats
        
        students = attendance_data["students"]
        subject = attendance_data["subject"]
        
        # Мокаем get_session чтобы использовать тестовую сессию
        with patch('bot.utils.stats.get_session', return_value=session):
            with patch('bot.utils.stats.crud') as mock_crud:
                # Настраиваем моки
                mock_crud.get_student_by_id.return_value = students[0]
                mock_crud.get_subject_attendance_dates.return_value = attendance_data["dates"]
                mock_crud.get_student_attendance_by_subject.return_value = [
                    MagicMock(date=d, is_present=True) for d in attendance_data["dates"]
                ]
                
                stats = get_student_stats(students[0].id, subject.id)
        
        assert stats["student_name"] == students[0].full_name
        assert stats["total"] == 3
        assert stats["present"] == 3
        assert stats["absent"] == 0
        assert stats["percentage"] == 100.0
    
    def test_student_stats_partial_attendance(self, session, attendance_data):
        """Студент с частичной посещаемостью."""
        from bot.utils.stats import get_student_stats
        
        students = attendance_data["students"]
        subject = attendance_data["subject"]
        dates = attendance_data["dates"]
        
        with patch('bot.utils.stats.get_session', return_value=session):
            with patch('bot.utils.stats.crud') as mock_crud:
                mock_crud.get_student_by_id.return_value = students[2]  # Сидоров
                mock_crud.get_subject_attendance_dates.return_value = dates
                # Сидоров: 1 присутствие, 2 пропуска
                mock_crud.get_student_attendance_by_subject.return_value = [
                    MagicMock(date=dates[0], is_present=True),
                    MagicMock(date=dates[1], is_present=False),
                    MagicMock(date=dates[2], is_present=False),
                ]
                
                stats = get_student_stats(students[2].id, subject.id)
        
        assert stats["total"] == 3
        assert stats["present"] == 1
        assert stats["absent"] == 2
        assert stats["percentage"] == pytest.approx(33.3, rel=0.1)
    
    def test_student_stats_no_records(self, session, attendance_data):
        """Студент без записей посещаемости."""
        from bot.utils.stats import get_student_stats
        
        students = attendance_data["students"]
        subject = attendance_data["subject"]
        dates = attendance_data["dates"]
        
        with patch('bot.utils.stats.get_session', return_value=session):
            with patch('bot.utils.stats.crud') as mock_crud:
                mock_crud.get_student_by_id.return_value = students[0]
                mock_crud.get_subject_attendance_dates.return_value = dates
                mock_crud.get_student_attendance_by_subject.return_value = []  # Нет записей
                
                stats = get_student_stats(students[0].id, subject.id)
        
        # Нет записей = все пропуски
        assert stats["total"] == 3
        assert stats["present"] == 0
        assert stats["absent"] == 3
        assert stats["percentage"] == 0


class TestSubjectStats:
    """Тесты статистики по дисциплине."""
    
    def test_subject_stats_basic(self, session, attendance_data):
        """Базовая статистика по дисциплине."""
        from bot.utils.stats import get_subject_stats
        
        subject = attendance_data["subject"]
        students = attendance_data["students"]
        dates = attendance_data["dates"]
        
        with patch('bot.utils.stats.get_session', return_value=session):
            with patch('bot.utils.stats.crud') as mock_crud:
                mock_crud.get_subject_by_id.return_value = subject
                mock_crud.get_students_by_subject.return_value = students
                mock_crud.get_subject_attendance_dates.return_value = dates
                
                # Мокаем get_student_stats для каждого студента
                with patch('bot.utils.stats.get_student_stats') as mock_student_stats:
                    mock_student_stats.side_effect = [
                        {"student_name": "Иванов", "percentage": 100.0, "total": 3, "present": 3, "absent": 0},
                        {"student_name": "Петров", "percentage": 66.7, "total": 3, "present": 2, "absent": 1},
                        {"student_name": "Сидоров", "percentage": 33.3, "total": 3, "present": 1, "absent": 2},
                    ]
                    
                    stats = get_subject_stats(subject.id)
        
        assert stats["subject_name"] == subject.name
        assert stats["total_students"] == 3
        assert stats["total_dates"] == 3
        # Средняя: (100 + 66.7 + 33.3) / 3 ≈ 66.7
        assert stats["avg_attendance"] == pytest.approx(66.7, rel=0.1)
    
    def test_subject_stats_empty(self, session, subject):
        """Статистика по пустой дисциплине."""
        from bot.utils.stats import get_subject_stats
        
        with patch('bot.utils.stats.get_session', return_value=session):
            with patch('bot.utils.stats.crud') as mock_crud:
                mock_crud.get_subject_by_id.return_value = subject
                mock_crud.get_students_by_subject.return_value = []
                mock_crud.get_subject_attendance_dates.return_value = []
                
                stats = get_subject_stats(subject.id)
        
        assert stats["total_students"] == 0
        assert stats["total_dates"] == 0
        assert stats["avg_attendance"] == 0


class TestPeriodFiltering:
    """Тесты фильтрации по периоду."""
    
    def test_student_stats_with_period(self, session, attendance_data):
        """Статистика студента за период."""
        from bot.utils.stats import get_student_stats
        
        students = attendance_data["students"]
        subject = attendance_data["subject"]
        all_dates = attendance_data["dates"]
        
        # Фильтруем только первые 2 даты
        date_from = date(2024, 11, 1)
        date_to = date(2024, 11, 10)
        filtered_dates = [d for d in all_dates if date_from <= d <= date_to]
        
        with patch('bot.utils.stats.get_session', return_value=session):
            with patch('bot.utils.stats.crud') as mock_crud:
                mock_crud.get_student_by_id.return_value = students[0]
                mock_crud.get_subject_attendance_dates.return_value = all_dates
                mock_crud.get_student_attendance_by_subject.return_value = [
                    MagicMock(date=d, is_present=True) for d in all_dates
                ]
                
                stats = get_student_stats(students[0].id, subject.id, date_from, date_to)
        
        # Должно быть 2 даты в периоде
        assert stats["total"] == 2
        assert stats["present"] == 2


class TestModels:
    """Тесты моделей."""
    
    def test_teacher_repr(self, teacher):
        """Представление преподавателя."""
        repr_str = repr(teacher)
        assert "Teacher" in repr_str
        assert str(teacher.telegram_id) in repr_str
    
    def test_subject_repr(self, subject):
        """Представление дисциплины."""
        repr_str = repr(subject)
        assert "Subject" in repr_str
        assert subject.name in repr_str
    
    def test_student_repr(self, students):
        """Представление студента."""
        repr_str = repr(students[0])
        assert "Student" in repr_str
        assert students[0].full_name in repr_str
    
    def test_attendance_repr(self, session, attendance_data):
        """Представление записи посещаемости."""
        subject = attendance_data["subject"]
        att = session.query(Attendance).filter_by(subject_id=subject.id).first()
        
        repr_str = repr(att)
        assert "Attendance" in repr_str

