"""
Модуль обработчиков команд бота.
"""

from bot.handlers.subjects import get_subjects_conversation_handler
from bot.handlers.students import get_students_conversation_handler
from bot.handlers.subject_students import get_subject_students_conversation_handler
from bot.handlers.attendance import get_attendance_conversation_handler
from bot.handlers.export import get_export_conversation_handler

__all__ = [
    "get_subjects_conversation_handler",
    "get_students_conversation_handler",
    "get_subject_students_conversation_handler",
    "get_attendance_conversation_handler",
    "get_export_conversation_handler",
]
