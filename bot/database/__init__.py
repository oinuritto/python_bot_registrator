"""
Модуль базы данных.
Экспортирует основные компоненты для удобного импорта.
"""

from bot.database.connection import get_session, init_db, engine
from bot.database.models import Base, Teacher, Subject, Student, SubjectStudent, Attendance
from bot.database import crud

__all__ = [
    "get_session",
    "init_db", 
    "engine",
    "Base",
    "Teacher",
    "Subject", 
    "Student",
    "SubjectStudent",
    "Attendance",
    "crud",
]
