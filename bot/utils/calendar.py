"""
Интерактивный inline-календарь для Telegram.
"""

import calendar
from datetime import date, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# Названия месяцев на русском
MONTHS_RU = [
    "", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
]

# Дни недели на русском (сокращённые)
DAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def create_calendar(
    year: int = None,
    month: int = None,
    callback_prefix: str = "cal",
    subject_id: int = None,
    marked_dates: list[date] = None,
) -> InlineKeyboardMarkup:
    """
    Создать inline-клавиатуру с календарём.

    Args:
        year: Год (по умолчанию текущий)
        month: Месяц (по умолчанию текущий)
        callback_prefix: Префикс для callback_data
        subject_id: ID дисциплины (для передачи в callback)
        marked_dates: Список дат, когда были отметки (будут выделены)

    Returns:
        InlineKeyboardMarkup с календарём
    """
    today = date.today()
    marked_dates = marked_dates or []

    if year is None:
        year = today.year
    if month is None:
        month = today.month

    keyboard = []

    # Заголовок: ◀️ Месяц Год ▶️
    nav_row = []

    # Кнопка "назад" (предыдущий месяц)
    prev_month = month - 1
    prev_year = year
    if prev_month < 1:
        prev_month = 12
        prev_year -= 1
    nav_row.append(InlineKeyboardButton(
        "◀️",
        callback_data=f"{callback_prefix}_nav_{subject_id}_{prev_year}_{prev_month}"
    ))

    # Название месяца и год
    nav_row.append(InlineKeyboardButton(
        f"{MONTHS_RU[month]} {year}",
        callback_data="noop"  # Не кликабельно
    ))

    # Кнопка "вперёд" (следующий месяц)
    next_month = month + 1
    next_year = year
    if next_month > 12:
        next_month = 1
        next_year += 1
    nav_row.append(InlineKeyboardButton(
        "▶️",
        callback_data=f"{callback_prefix}_nav_{subject_id}_{next_year}_{next_month}"
    ))

    keyboard.append(nav_row)

    # Дни недели
    days_row = [InlineKeyboardButton(
        day, callback_data="noop") for day in DAYS_RU]
    keyboard.append(days_row)

    # Получаем календарь месяца
    cal = calendar.monthcalendar(year, month)

    for week in cal:
        week_row = []
        for day in week:
            if day == 0:
                # Пустая ячейка
                week_row.append(InlineKeyboardButton(
                    " ", callback_data="noop"))
            else:
                current_date = date(year, month, day)

                # Проверяем, не в будущем ли дата
                if current_date > today:
                    # Будущая дата — некликабельна
                    week_row.append(InlineKeyboardButton(
                        f"·{day}·",
                        callback_data="noop"
                    ))
                else:
                    # Форматируем день
                    is_marked = current_date in marked_dates

                    if current_date == today and is_marked:
                        day_text = f"●[{day}]"  # Сегодня + отмечено
                    elif current_date == today:
                        day_text = f"[{day}]"  # Сегодня
                    elif is_marked:
                        day_text = f"●{day}"  # Отмечено
                    else:
                        day_text = str(day)

                    week_row.append(InlineKeyboardButton(
                        day_text,
                        callback_data=f"{callback_prefix}_day_{subject_id}_{year}_{month}_{day}"
                    ))

        keyboard.append(week_row)

    # Быстрые кнопки
    quick_row = [
        InlineKeyboardButton(
            "📅 Сегодня", callback_data=f"{callback_prefix}_today_{subject_id}"),
        InlineKeyboardButton(
            "📅 Вчера", callback_data=f"{callback_prefix}_yesterday_{subject_id}"),
    ]
    keyboard.append(quick_row)

    # Кнопка "Назад"
    keyboard.append([
        InlineKeyboardButton("◀️ Назад", callback_data="menu_attendance")
    ])

    return InlineKeyboardMarkup(keyboard)


def parse_calendar_callback(callback_data: str) -> dict:
    """
    Распарсить callback_data от календаря.

    Returns:
        dict с полями: action, subject_id, year, month, day
    """
    parts = callback_data.split("_")

    result = {
        "prefix": parts[0],  # "cal"
        "action": parts[1],   # "nav", "day", "today", "yesterday"
        "subject_id": int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None,
    }

    if result["action"] == "nav":
        result["year"] = int(parts[3])
        result["month"] = int(parts[4])
    elif result["action"] == "day":
        result["year"] = int(parts[3])
        result["month"] = int(parts[4])
        result["day"] = int(parts[5])
        result["date"] = date(result["year"], result["month"], result["day"])
    elif result["action"] == "today":
        result["date"] = date.today()
    elif result["action"] == "yesterday":
        result["date"] = date.today() - timedelta(days=1)

    return result
