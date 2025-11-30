"""
Обработчики для отметки посещаемости.
"""

import logging
from datetime import date, datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from bot.database import get_session, crud
from bot.states import AttendanceStates
from bot.utils.calendar import create_calendar, parse_calendar_callback

logger = logging.getLogger(__name__)


# === Вспомогательные функции ===

def get_teacher_from_update(update: Update):
    """Получить или создать преподавателя из update."""
    user = update.effective_user
    session = get_session()
    try:
        teacher = crud.get_or_create_teacher(
            session,
            telegram_id=user.id,
            name=user.full_name
        )
        return teacher, session
    except Exception as e:
        session.close()
        raise e


def format_date(d: date) -> str:
    """Форматировать дату для отображения."""
    return d.strftime("%d.%m.%Y")


def parse_date(date_str: str) -> date | None:
    """Парсинг даты из строки."""
    date_str = date_str.strip()

    # Сначала пробуем ISO формат (YYYY-MM-DD)
    if "-" in date_str and len(date_str) == 10:
        try:
            return date.fromisoformat(date_str)
        except ValueError:
            pass

    # Пробуем разные форматы
    formats = ["%d.%m.%Y", "%d.%m.%y", "%d/%m/%Y", "%d-%m-%Y"]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue

    return None


def get_date_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора даты."""
    today = date.today()
    yesterday = today - timedelta(days=1)

    keyboard = [
        [
            InlineKeyboardButton(
                f"📅 Сегодня ({format_date(today)})", callback_data=f"att_date_{today.isoformat()}"),
        ],
        [
            InlineKeyboardButton(
                f"📅 Вчера ({format_date(yesterday)})", callback_data=f"att_date_{yesterday.isoformat()}"),
        ],
        [
            InlineKeyboardButton("📆 Другая дата...",
                                 callback_data="att_date_custom"),
        ],
        [
            InlineKeyboardButton("◀️ Назад", callback_data="menu_attendance"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_students_attendance_keyboard(
    subject_id: int,
    attendance_date: date,
    session,
    attendance_data: dict[int, bool]
) -> InlineKeyboardMarkup:
    """Клавиатура со списком студентов для отметки."""
    students = crud.get_students_by_subject(session, subject_id)

    keyboard = []
    for student in students:
        is_present = attendance_data.get(student.id, False)
        status = "✅" if is_present else "❌"

        keyboard.append([
            InlineKeyboardButton(
                f"{status} {student.full_name}",
                callback_data=f"att_toggle_{subject_id}_{attendance_date.isoformat()}_{student.id}"
            )
        ])

    # Кнопки быстрых действий
    keyboard.append([
        InlineKeyboardButton(
            "✅ Все присутствуют", callback_data=f"att_all_present_{subject_id}_{attendance_date.isoformat()}"),
    ])
    keyboard.append([
        InlineKeyboardButton(
            "❌ Все отсутствуют", callback_data=f"att_all_absent_{subject_id}_{attendance_date.isoformat()}"),
    ])
    keyboard.append([
        InlineKeyboardButton(
            "💾 Готово", callback_data=f"att_done_{subject_id}_{attendance_date.isoformat()}"),
    ])
    keyboard.append([
        InlineKeyboardButton("◀️ Выбрать другую дату",
                             callback_data=f"att_select_date_{subject_id}"),
    ])

    return InlineKeyboardMarkup(keyboard)


# === Основные обработчики ===

async def attendance_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показать меню отметки посещаемости - выбор дисциплины."""
    query = update.callback_query
    if query:
        await query.answer()

    teacher, session = get_teacher_from_update(update)

    try:
        subjects = crud.get_subjects_by_teacher(session, teacher.id)

        if not subjects:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    "📚 Создать дисциплину", callback_data="subject_add")],
                [InlineKeyboardButton(
                    "◀️ Назад в меню", callback_data="back_to_menu")],
            ])

            text = (
                "✏️ <b>Отметка посещаемости</b>\n\n"
                "У вас нет дисциплин.\n"
                "Сначала создайте дисциплину и добавьте студентов."
            )
        else:
            keyboard = []
            for subject in subjects:
                students_count = crud.count_students_in_subject(
                    session, subject.id)
                badge = f" ({students_count} студ.)" if students_count else " (0 студ.)"
                keyboard.append([
                    InlineKeyboardButton(
                        f"📚 {subject.name}{badge}",
                        callback_data=f"att_select_date_{subject.id}"
                    )
                ])
            keyboard.append([
                InlineKeyboardButton(
                    "◀️ Назад в меню", callback_data="back_to_menu"),
            ])

            text = (
                "✏️ <b>Отметка посещаемости</b>\n\n"
                "Выберите дисциплину:"
            )

        if query:
            await query.edit_message_text(
                text=text,
                reply_markup=InlineKeyboardMarkup(
                    keyboard) if isinstance(keyboard, list) else keyboard,
                parse_mode="HTML"
            )
        else:
            await update.message.reply_text(
                text=text,
                reply_markup=InlineKeyboardMarkup(
                    keyboard) if isinstance(keyboard, list) else keyboard,
                parse_mode="HTML"
            )
    finally:
        session.close()

    return ConversationHandler.END


async def attendance_select_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Выбор даты для отметки посещаемости."""
    query = update.callback_query
    await query.answer()

    subject_id = int(query.data.split("_")[-1])
    context.user_data["attendance_subject_id"] = subject_id

    session = get_session()
    try:
        subject = crud.get_subject_by_id(session, subject_id)
        students_count = crud.count_students_in_subject(session, subject_id)

        if students_count == 0:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    "👥 Добавить студентов", callback_data=f"students_menu_{subject_id}")],
                [InlineKeyboardButton(
                    "◀️ Назад", callback_data="menu_attendance")],
            ])

            await query.edit_message_text(
                text=(
                    f"✏️ <b>Отметка: {subject.name}</b>\n\n"
                    "В дисциплине нет студентов.\n"
                    "Сначала добавьте студентов."
                ),
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            return ConversationHandler.END

        # Получаем даты с отметками
        marked_dates = crud.get_subject_attendance_dates(session, subject_id)

        await query.edit_message_text(
            text=(
                f"✏️ <b>Отметка: {subject.name}</b>\n\n"
                f"Студентов: {students_count}\n"
                f"📊 Дней с отметками: {len(marked_dates)}\n\n"
                "📅 Выберите дату занятия:\n"
                "<i>● — дни с отметками</i>"
            ),
            reply_markup=create_calendar(
                callback_prefix="cal", subject_id=subject_id, marked_dates=marked_dates),
            parse_mode="HTML"
        )
    finally:
        session.close()

    return ConversationHandler.END


async def attendance_date_custom(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запрос ввода произвольной даты."""
    query = update.callback_query
    await query.answer()

    subject_id = context.user_data.get("attendance_subject_id")

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "◀️ Назад", callback_data=f"att_select_date_{subject_id}")],
    ])

    await query.edit_message_text(
        text=(
            "📆 <b>Введите дату</b>\n\n"
            "Формат: ДД.ММ.ГГГГ\n"
            "Например: 25.11.2024"
        ),
        reply_markup=keyboard,
        parse_mode="HTML"
    )

    return AttendanceStates.SELECT_DATE


async def attendance_date_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка введённой даты."""
    date_str = update.message.text.strip()
    subject_id = context.user_data.get("attendance_subject_id")

    if not subject_id:
        await update.message.reply_text("❌ Ошибка. Начните заново через меню.")
        return ConversationHandler.END

    parsed_date = parse_date(date_str)

    if not parsed_date:
        await update.message.reply_text(
            "⚠️ Неверный формат даты.\n"
            "Введите в формате ДД.ММ.ГГГГ (например: 25.11.2024):"
        )
        return AttendanceStates.SELECT_DATE

    # Проверка что дата не в будущем
    if parsed_date > date.today():
        await update.message.reply_text(
            "⚠️ Нельзя отметить посещаемость на будущую дату.\n"
            "Введите другую дату:"
        )
        return AttendanceStates.SELECT_DATE

    context.user_data["attendance_date"] = parsed_date

    # Показываем список студентов
    return await show_attendance_marking(update, context, subject_id, parsed_date)


async def attendance_date_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбранной даты (кнопка)."""
    query = update.callback_query
    await query.answer()

    date_str = query.data.split("_")[-1]
    attendance_date = date.fromisoformat(date_str)
    subject_id = context.user_data.get("attendance_subject_id")

    if not subject_id:
        await query.edit_message_text("❌ Ошибка. Начните заново через меню.")
        return ConversationHandler.END

    context.user_data["attendance_date"] = attendance_date

    # Показываем список студентов
    return await show_attendance_marking(update, context, subject_id, attendance_date)


async def show_attendance_marking(update: Update, context: ContextTypes.DEFAULT_TYPE, subject_id: int, attendance_date: date) -> int:
    """Показать список студентов для отметки (универсальная функция)."""
    session = get_session()
    try:
        subject = crud.get_subject_by_id(session, subject_id)
        students = crud.get_students_by_subject(session, subject_id)

        # Получаем текущие данные посещаемости
        attendance_data = crud.get_attendance_by_subject_and_date(
            session, subject_id, attendance_date)

        # Сохраняем в контексте для быстрого доступа
        context.user_data["attendance_data"] = attendance_data

        present_count = sum(1 for v in attendance_data.values() if v)

        text = (
            f"✏️ <b>Отметка посещаемости</b>\n\n"
            f"📚 {subject.name}\n"
            f"📅 {format_date(attendance_date)}\n\n"
            f"Присутствует: {present_count}/{len(students)}\n\n"
            "Нажмите на студента для изменения статуса:"
        )

        keyboard = get_students_attendance_keyboard(
            subject_id, attendance_date, session, attendance_data)

        # Определяем откуда вызов: кнопка или текст
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        else:
            await update.message.reply_text(
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
    finally:
        session.close()

    return ConversationHandler.END


async def attendance_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Переключить статус посещаемости студента."""
    query = update.callback_query
    await query.answer()

    parts = query.data.split("_")
    subject_id = int(parts[2])
    date_str = parts[3]
    student_id = int(parts[4])

    attendance_date = date.fromisoformat(date_str)

    session = get_session()
    try:
        # Получаем текущий статус
        attendance_data = context.user_data.get("attendance_data", {})
        current_status = attendance_data.get(student_id, False)
        new_status = not current_status

        # Сохраняем в БД
        crud.set_attendance(session, student_id, subject_id,
                            attendance_date, new_status)

        # Обновляем локальный кэш
        attendance_data[student_id] = new_status
        context.user_data["attendance_data"] = attendance_data

        # Обновляем интерфейс
        subject = crud.get_subject_by_id(session, subject_id)
        students = crud.get_students_by_subject(session, subject_id)

        present_count = sum(1 for v in attendance_data.values() if v)

        text = (
            f"✏️ <b>Отметка посещаемости</b>\n\n"
            f"📚 {subject.name}\n"
            f"📅 {format_date(attendance_date)}\n\n"
            f"Присутствует: {present_count}/{len(students)}\n\n"
            "Нажмите на студента для изменения статуса:"
        )

        keyboard = get_students_attendance_keyboard(
            subject_id, attendance_date, session, attendance_data)

        await query.edit_message_text(
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    finally:
        session.close()

    return ConversationHandler.END


async def attendance_all_present(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отметить всех как присутствующих."""
    query = update.callback_query
    await query.answer("✅ Все отмечены как присутствующие")

    parts = query.data.split("_")
    subject_id = int(parts[3])
    date_str = parts[4]
    attendance_date = date.fromisoformat(date_str)

    session = get_session()
    try:
        students = crud.get_students_by_subject(session, subject_id)
        attendance_data = {}

        for student in students:
            crud.set_attendance(session, student.id,
                                subject_id, attendance_date, True)
            attendance_data[student.id] = True

        context.user_data["attendance_data"] = attendance_data

        # Обновляем интерфейс
        subject = crud.get_subject_by_id(session, subject_id)

        text = (
            f"✏️ <b>Отметка посещаемости</b>\n\n"
            f"📚 {subject.name}\n"
            f"📅 {format_date(attendance_date)}\n\n"
            f"Присутствует: {len(students)}/{len(students)}\n\n"
            "Нажмите на студента для изменения статуса:"
        )

        keyboard = get_students_attendance_keyboard(
            subject_id, attendance_date, session, attendance_data)

        await query.edit_message_text(
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    finally:
        session.close()

    return ConversationHandler.END


async def attendance_all_absent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отметить всех как отсутствующих."""
    query = update.callback_query
    await query.answer("❌ Все отмечены как отсутствующие")

    parts = query.data.split("_")
    subject_id = int(parts[3])
    date_str = parts[4]
    attendance_date = date.fromisoformat(date_str)

    session = get_session()
    try:
        students = crud.get_students_by_subject(session, subject_id)
        attendance_data = {}

        for student in students:
            crud.set_attendance(session, student.id,
                                subject_id, attendance_date, False)
            attendance_data[student.id] = False

        context.user_data["attendance_data"] = attendance_data

        # Обновляем интерфейс
        subject = crud.get_subject_by_id(session, subject_id)

        text = (
            f"✏️ <b>Отметка посещаемости</b>\n\n"
            f"📚 {subject.name}\n"
            f"📅 {format_date(attendance_date)}\n\n"
            f"Присутствует: 0/{len(students)}\n\n"
            "Нажмите на студента для изменения статуса:"
        )

        keyboard = get_students_attendance_keyboard(
            subject_id, attendance_date, session, attendance_data)

        await query.edit_message_text(
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    finally:
        session.close()

    return ConversationHandler.END


async def attendance_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Завершить отметку посещаемости."""
    query = update.callback_query
    await query.answer("✅ Посещаемость сохранена!")

    parts = query.data.split("_")
    subject_id = int(parts[2])
    date_str = parts[3]
    attendance_date = date.fromisoformat(date_str)

    session = get_session()
    try:
        subject = crud.get_subject_by_id(session, subject_id)
        students = crud.get_students_by_subject(session, subject_id)
        attendance_data = crud.get_attendance_by_subject_and_date(
            session, subject_id, attendance_date)

        present_count = sum(1 for v in attendance_data.values() if v)

        logger.info(
            "Посещаемость сохранена: %s, %s, %s/%s присутствует",
            subject.name, format_date(
                attendance_date), present_count, len(students)
        )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "📅 Другая дата", callback_data=f"att_select_date_{subject_id}")],
            [InlineKeyboardButton("📚 Другая дисциплина",
                                  callback_data="menu_attendance")],
            [InlineKeyboardButton("◀️ В главное меню",
                                  callback_data="back_to_menu")],
        ])

        await query.edit_message_text(
            text=(
                f"✅ <b>Посещаемость сохранена!</b>\n\n"
                f"📚 {subject.name}\n"
                f"📅 {format_date(attendance_date)}\n\n"
                f"Присутствовало: {present_count} из {len(students)} студентов"
            ),
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    finally:
        session.close()

    # Очищаем данные из контекста
    context.user_data.pop("attendance_data", None)
    context.user_data.pop("attendance_date", None)
    context.user_data.pop("attendance_subject_id", None)

    return ConversationHandler.END


# === Обработчики календаря ===

async def calendar_navigate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Навигация по календарю (переключение месяцев)."""
    query = update.callback_query
    await query.answer()

    data = parse_calendar_callback(query.data)
    subject_id = data.get("subject_id")
    year = data.get("year")
    month = data.get("month")

    session = get_session()
    try:
        subject = crud.get_subject_by_id(session, subject_id)
        students_count = crud.count_students_in_subject(session, subject_id)
        marked_dates = crud.get_subject_attendance_dates(session, subject_id)

        await query.edit_message_text(
            text=(
                f"✏️ <b>Отметка: {subject.name}</b>\n\n"
                f"Студентов: {students_count}\n"
                f"📊 Дней с отметками: {len(marked_dates)}\n\n"
                "📅 Выберите дату занятия:\n"
                "<i>● — дни с отметками</i>"
            ),
            reply_markup=create_calendar(
                year, month, callback_prefix="cal", subject_id=subject_id, marked_dates=marked_dates),
            parse_mode="HTML"
        )
    finally:
        session.close()

    return ConversationHandler.END


async def calendar_select_day(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Выбор дня в календаре."""
    query = update.callback_query
    await query.answer()

    data = parse_calendar_callback(query.data)
    subject_id = data.get("subject_id")
    selected_date = data.get("date")

    if not selected_date or not subject_id:
        await query.answer("Ошибка выбора даты", show_alert=True)
        return ConversationHandler.END

    context.user_data["attendance_subject_id"] = subject_id
    context.user_data["attendance_date"] = selected_date

    return await show_attendance_marking(update, context, subject_id, selected_date)


async def calendar_quick_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Быстрый выбор даты (сегодня/вчера)."""
    query = update.callback_query
    await query.answer()

    data = parse_calendar_callback(query.data)
    subject_id = data.get("subject_id")
    selected_date = data.get("date")

    if not selected_date or not subject_id:
        await query.answer("Ошибка выбора даты", show_alert=True)
        return ConversationHandler.END

    context.user_data["attendance_subject_id"] = subject_id
    context.user_data["attendance_date"] = selected_date

    return await show_attendance_marking(update, context, subject_id, selected_date)


# === ConversationHandler для отметки посещаемости ===

def get_attendance_conversation_handler() -> ConversationHandler:
    """Создать ConversationHandler для отметки посещаемости."""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(attendance_menu, pattern="^menu_attendance$"),
            CallbackQueryHandler(attendance_select_date,
                                 pattern=r"^att_select_date_\d+$"),
            # Календарь
            CallbackQueryHandler(
                calendar_navigate, pattern=r"^cal_nav_\d+_\d+_\d+$"),
            CallbackQueryHandler(calendar_select_day,
                                 pattern=r"^cal_day_\d+_\d+_\d+_\d+$"),
            CallbackQueryHandler(calendar_quick_date,
                                 pattern=r"^cal_today_\d+$"),
            CallbackQueryHandler(calendar_quick_date,
                                 pattern=r"^cal_yesterday_\d+$"),
            # Старые обработчики (для совместимости)
            CallbackQueryHandler(attendance_date_selected,
                                 pattern=r"^att_date_\d{4}-\d{2}-\d{2}$"),
            CallbackQueryHandler(attendance_date_custom,
                                 pattern="^att_date_custom$"),
            CallbackQueryHandler(
                attendance_toggle, pattern=r"^att_toggle_\d+_\d{4}-\d{2}-\d{2}_\d+$"),
            CallbackQueryHandler(
                attendance_all_present, pattern=r"^att_all_present_\d+_\d{4}-\d{2}-\d{2}$"),
            CallbackQueryHandler(
                attendance_all_absent, pattern=r"^att_all_absent_\d+_\d{4}-\d{2}-\d{2}$"),
            CallbackQueryHandler(
                attendance_done, pattern=r"^att_done_\d+_\d{4}-\d{2}-\d{2}$"),
        ],
        states={
            AttendanceStates.SELECT_DATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND,
                               attendance_date_input),
                CallbackQueryHandler(attendance_select_date,
                                     pattern=r"^att_select_date_\d+$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(attendance_menu, pattern="^menu_attendance$"),
        ],
        allow_reentry=True,
    )
