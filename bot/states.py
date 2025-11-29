"""
Состояния для ConversationHandler (FSM).
"""

from enum import IntEnum, auto


class SubjectStates(IntEnum):
    """Состояния для управления дисциплинами."""
    WAITING_NAME = auto()           # Ожидание названия новой дисциплины
    WAITING_NEW_NAME = auto()       # Ожидание нового названия (редактирование)
    CONFIRM_DELETE = auto()         # Подтверждение удаления


class StudentStates(IntEnum):
    """Состояния для управления студентами."""
    WAITING_NAME = auto()           # Ожидание ФИО студента
    WAITING_BULK_NAMES = auto()     # Ожидание списка ФИО (массовое добавление)
    WAITING_NEW_NAME = auto()       # Ожидание нового ФИО (редактирование)
    CONFIRM_DELETE = auto()         # Подтверждение удаления


class AttendanceStates(IntEnum):
    """Состояния для отметки посещаемости."""
    SELECT_SUBJECT = auto()         # Выбор дисциплины
    SELECT_DATE = auto()            # Выбор даты
    MARKING = auto()                # Отметка студентов
