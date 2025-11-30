"""
Обработчики для статистики и визуализации.
"""

import logging
from datetime import date, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from bot.database import get_session, crud
from bot.utils.stats import (
    get_student_stats,
    get_subject_stats,
    get_teacher_overall_stats,
)
from bot.utils.charts import (
    create_dates_chart,
    create_students_chart,
    create_overall_chart,
)

logger = logging.getLogger(__name__)

# Состояния для ввода периода
WAITING_STATS_DATE_FROM = 1
WAITING_STATS_DATE_TO = 2


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


def format_percentage(pct: float) -> str:
    """Форматирование процента с эмодзи."""
    if pct >= 80:
        return f"🟢 {pct:.0f}%"
    elif pct >= 60:
        return f"🟡 {pct:.0f}%"
    elif pct >= 40:
        return f"🟠 {pct:.0f}%"
    else:
        return f"🔴 {pct:.0f}%"


def format_date(d: date) -> str:
    """Форматировать дату."""
    return d.strftime("%d.%m.%Y")


def get_period_keyboard(subject_id: int) -> InlineKeyboardMarkup:
    """Клавиатура выбора периода для статистики."""
    today = date.today()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    keyboard = [
        [InlineKeyboardButton("📅 За всё время", callback_data=f"stats_period_{subject_id}_all")],
        [InlineKeyboardButton(f"📅 Последняя неделя ({format_date(week_ago)} — {format_date(today)})", 
                              callback_data=f"stats_period_{subject_id}_week")],
        [InlineKeyboardButton(f"📅 Последний месяц ({format_date(month_ago)} — {format_date(today)})", 
                              callback_data=f"stats_period_{subject_id}_month")],
        [InlineKeyboardButton("📆 Указать период...", callback_data=f"stats_period_{subject_id}_custom")],
        [InlineKeyboardButton("◀️ Назад", callback_data="menu_stats")],
    ]
    return InlineKeyboardMarkup(keyboard)


# === Основные обработчики ===

async def stats_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Главное меню статистики."""
    query = update.callback_query
    if query:
        await query.answer()
    
    teacher, session = get_teacher_from_update(update)
    
    try:
        subjects = crud.get_subjects_by_teacher(session, teacher.id)
        
        if not subjects:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📚 Создать дисциплину", callback_data="subject_add")],
                [InlineKeyboardButton("◀️ Назад в меню", callback_data="back_to_menu")],
            ])
            
            text = (
                "📊 <b>Статистика</b>\n\n"
                "У вас нет дисциплин.\n"
                "Сначала создайте дисциплину и добавьте студентов."
            )
        else:
            keyboard = [
                [InlineKeyboardButton("📈 Общая статистика", callback_data="stats_overall")],
                [InlineKeyboardButton("— Или выберите дисциплину —", callback_data="noop")],
            ]
            
            for subject in subjects:
                students_count = crud.count_students_in_subject(session, subject.id)
                dates = crud.get_subject_attendance_dates(session, subject.id)
                
                badge = f"({students_count} студ., {len(dates)} дат)"
                keyboard.append([
                    InlineKeyboardButton(
                        f"📚 {subject.name} {badge}",
                        callback_data=f"stats_subject_{subject.id}"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton("◀️ Назад в меню", callback_data="back_to_menu"),
            ])
            
            text = (
                "📊 <b>Статистика посещаемости</b>\n\n"
                "Выберите что посмотреть:\n\n"
                "• <b>Общая статистика</b> — по всем дисциплинам\n"
                "• <b>Дисциплина</b> — детальная статистика"
            )
        
        if query:
            await query.edit_message_text(
                text=text,
                reply_markup=InlineKeyboardMarkup(keyboard) if isinstance(keyboard, list) else keyboard,
                parse_mode="HTML"
            )
        else:
            await update.message.reply_text(
                text=text,
                reply_markup=InlineKeyboardMarkup(keyboard) if isinstance(keyboard, list) else keyboard,
                parse_mode="HTML"
            )
    finally:
        session.close()
    
    return ConversationHandler.END


async def stats_overall(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Выбор периода для общей статистики."""
    query = update.callback_query
    await query.answer()
    
    today = date.today()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    keyboard = [
        [InlineKeyboardButton("📅 За всё время", callback_data="stats_overall_period_all")],
        [InlineKeyboardButton(f"📅 Последняя неделя ({format_date(week_ago)} — {format_date(today)})", 
                              callback_data="stats_overall_period_week")],
        [InlineKeyboardButton(f"📅 Последний месяц ({format_date(month_ago)} — {format_date(today)})", 
                              callback_data="stats_overall_period_month")],
        [InlineKeyboardButton("◀️ Назад", callback_data="menu_stats")],
    ]
    
    await query.edit_message_text(
        text="📊 <b>Общая статистика</b>\n\nВыберите период:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )
    
    return ConversationHandler.END


async def stats_overall_period_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показать общую статистику за выбранный период."""
    query = update.callback_query
    await query.answer("📊 Загрузка статистики...")
    
    period = query.data.split("_")[-1]
    
    today = date.today()
    date_from = None
    date_to = None
    period_text = "за всё время"
    
    if period == "week":
        date_from = today - timedelta(days=7)
        date_to = today
        period_text = f"за неделю ({format_date(date_from)} — {format_date(date_to)})"
    elif period == "month":
        date_from = today - timedelta(days=30)
        date_to = today
        period_text = f"за месяц ({format_date(date_from)} — {format_date(date_to)})"
    
    # Сохраняем период для графика
    context.user_data["stats_overall_date_from"] = date_from
    context.user_data["stats_overall_date_to"] = date_to
    context.user_data["stats_overall_period_text"] = period_text
    
    teacher, session = get_teacher_from_update(update)
    session.close()
    
    stats = get_teacher_overall_stats(teacher.id, date_from, date_to)
    
    if stats.get("total_subjects", 0) == 0:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Назад", callback_data="menu_stats")],
        ])
        await query.edit_message_text(
            text="📊 <b>Общая статистика</b>\n\nНет данных.",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        return ConversationHandler.END
    
    # Формируем текст
    lines = [
        "📊 <b>Общая статистика</b>",
        f"<i>{period_text}</i>\n",
        f"📚 Дисциплин: <b>{stats['total_subjects']}</b>",
        f"👥 Студентов: <b>{stats['total_students']}</b>",
        f"📅 Занятий: <b>{stats['total_dates']}</b>",
        f"📈 Средняя посещаемость: <b>{format_percentage(stats['overall_avg_attendance'])}</b>",
        "\n<b>По дисциплинам:</b>",
    ]
    
    for subj in stats.get("subjects_stats", []):
        if subj.get("total_dates", 0) > 0:
            lines.append(
                f"• {subj['subject_name']}: {format_percentage(subj['avg_attendance'])}"
            )
        else:
            lines.append(f"• {subj['subject_name']}: <i>нет данных</i>")
    
    keyboard = [
        [InlineKeyboardButton("📈 График по дисциплинам", callback_data="stats_overall_chart")],
        [InlineKeyboardButton("📅 Другой период", callback_data="stats_overall")],
        [InlineKeyboardButton("◀️ Назад", callback_data="menu_stats")],
    ]
    
    await query.edit_message_text(
        text="\n".join(lines),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )
    
    return ConversationHandler.END


async def stats_overall_chart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отправить график по всем дисциплинам."""
    query = update.callback_query
    await query.answer("📊 Создаю график...")
    
    # Получаем период из контекста
    date_from = context.user_data.get("stats_overall_date_from")
    date_to = context.user_data.get("stats_overall_date_to")
    period_text = context.user_data.get("stats_overall_period_text", "")
    
    teacher, session = get_teacher_from_update(update)
    session.close()
    
    stats = get_teacher_overall_stats(teacher.id, date_from, date_to)
    
    chart = create_overall_chart(stats.get("subjects_stats", []))
    
    if not chart:
        await query.answer("Недостаточно данных для графика", show_alert=True)
        return ConversationHandler.END
    
    caption = "📊 Посещаемость по дисциплинам"
    if period_text:
        caption += f"\n{period_text}"
    
    await query.message.reply_photo(
        photo=chart,
        caption=caption
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("◀️ Назад", callback_data="stats_overall")],
    ])
    
    await query.edit_message_text(
        text="✅ График отправлен!",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    return ConversationHandler.END


async def stats_subject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Выбор периода для статистики дисциплины."""
    query = update.callback_query
    await query.answer()
    
    subject_id = int(query.data.split("_")[-1])
    context.user_data["stats_subject_id"] = subject_id
    
    session = get_session()
    try:
        subject = crud.get_subject_by_id(session, subject_id)
        dates = crud.get_subject_attendance_dates(session, subject_id)
        
        if not dates:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✏️ Отметить посещаемость", callback_data=f"att_select_date_{subject_id}")],
                [InlineKeyboardButton("◀️ Назад", callback_data="menu_stats")],
            ])
            await query.edit_message_text(
                text=f"📊 <b>{subject.name}</b>\n\nНет данных о посещаемости.",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            return ConversationHandler.END
        
        await query.edit_message_text(
            text=(
                f"📊 <b>Статистика: {subject.name}</b>\n\n"
                f"📅 Всего дат: {len(dates)}\n\n"
                "Выберите период:"
            ),
            reply_markup=get_period_keyboard(subject_id),
            parse_mode="HTML"
        )
    finally:
        session.close()
    
    return ConversationHandler.END


async def stats_period_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показать статистику за выбранный период."""
    query = update.callback_query
    await query.answer("📊 Загрузка...")
    
    # Парсим callback: stats_period_SUBJECTID_PERIOD
    parts = query.data.split("_")
    subject_id = int(parts[2])
    period = parts[3]
    
    today = date.today()
    date_from = None
    date_to = None
    period_text = "за всё время"
    
    if period == "week":
        date_from = today - timedelta(days=7)
        date_to = today
        period_text = f"за неделю ({format_date(date_from)} — {format_date(date_to)})"
    elif period == "month":
        date_from = today - timedelta(days=30)
        date_to = today
        period_text = f"за месяц ({format_date(date_from)} — {format_date(date_to)})"
    elif period == "custom":
        context.user_data["stats_subject_id"] = subject_id
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Отмена", callback_data=f"stats_subject_{subject_id}")]
        ])
        await query.edit_message_text(
            text=(
                "📆 <b>Укажите период</b>\n\n"
                "Введите <b>начальную дату</b>\n"
                "в формате ДД.ММ.ГГГГ:"
            ),
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        return WAITING_STATS_DATE_FROM
    
    # Сохраняем период для графиков
    context.user_data["stats_date_from"] = date_from
    context.user_data["stats_date_to"] = date_to
    context.user_data["stats_period_text"] = period_text
    
    return await show_subject_stats(query, context, subject_id, date_from, date_to, period_text)


async def show_subject_stats(query, context, subject_id: int, date_from, date_to, period_text: str) -> int:
    """Показать статистику дисциплины."""
    stats = get_subject_stats(subject_id, date_from, date_to)
    
    if not stats:
        await query.answer("Дисциплина не найдена", show_alert=True)
        return ConversationHandler.END
    
    if stats.get("total_dates", 0) == 0:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📅 Другой период", callback_data=f"stats_subject_{subject_id}")],
            [InlineKeyboardButton("◀️ Назад", callback_data="menu_stats")],
        ])
        await query.edit_message_text(
            text=f"📊 <b>{stats['subject_name']}</b>\n\nНет данных {period_text}.",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        return ConversationHandler.END
    
    # Формируем текст
    lines = [
        f"📊 <b>{stats['subject_name']}</b>",
        f"<i>{period_text}</i>\n",
        f"👥 Студентов: <b>{stats['total_students']}</b>",
        f"📅 Занятий: <b>{stats['total_dates']}</b>",
        f"📈 Средняя посещаемость: <b>{format_percentage(stats['avg_attendance'])}</b>",
        "\n<b>Топ студентов:</b>",
    ]
    
    # Показываем топ-5 и худших 3
    students = stats.get("students_stats", [])
    
    # Лучшие
    for i, st in enumerate(students[:5], 1):
        lines.append(f"{i}. {st['student_name']}: {format_percentage(st['percentage'])}")
    
    if len(students) > 8:
        lines.append("...")
        # Худшие
        for st in students[-3:]:
            idx = students.index(st) + 1
            lines.append(f"{idx}. {st['student_name']}: {format_percentage(st['percentage'])}")
    elif len(students) > 5:
        for i, st in enumerate(students[5:], 6):
            lines.append(f"{i}. {st['student_name']}: {format_percentage(st['percentage'])}")
    
    keyboard = [
        [
            InlineKeyboardButton("📊 По датам", callback_data=f"stats_chart_dates_{subject_id}"),
            InlineKeyboardButton("👥 По студентам", callback_data=f"stats_chart_students_{subject_id}"),
        ],
        [InlineKeyboardButton("📅 Другой период", callback_data=f"stats_subject_{subject_id}")],
        [InlineKeyboardButton("◀️ Назад", callback_data="menu_stats")],
    ]
    
    await query.edit_message_text(
        text="\n".join(lines),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )
    
    return ConversationHandler.END


async def stats_chart_dates(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отправить график посещаемости по датам."""
    query = update.callback_query
    await query.answer("📊 Создаю график...")
    
    subject_id = int(query.data.split("_")[-1])
    
    # Получаем период из контекста
    date_from = context.user_data.get("stats_date_from")
    date_to = context.user_data.get("stats_date_to")
    period_text = context.user_data.get("stats_period_text", "")
    
    session = get_session()
    try:
        subject = crud.get_subject_by_id(session, subject_id)
        subject_name = subject.name if subject else "Дисциплина"
    finally:
        session.close()
    
    chart = create_dates_chart(subject_id, subject_name, date_from, date_to)
    
    if not chart:
        await query.answer("Недостаточно данных для графика", show_alert=True)
        return ConversationHandler.END
    
    caption = f"📊 Посещаемость по датам: {subject_name}"
    if period_text:
        caption += f"\n{period_text}"
    
    await query.message.reply_photo(
        photo=chart,
        caption=caption
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("◀️ Назад к статистике", callback_data=f"stats_subject_{subject_id}")],
    ])
    
    await query.edit_message_text(
        text="✅ График отправлен!",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    return ConversationHandler.END


async def stats_chart_students(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отправить график и список посещаемости по студентам."""
    query = update.callback_query
    await query.answer("📊 Создаю отчёт...")
    
    subject_id = int(query.data.split("_")[-1])
    
    # Получаем период из контекста
    date_from = context.user_data.get("stats_date_from")
    date_to = context.user_data.get("stats_date_to")
    period_text = context.user_data.get("stats_period_text", "")
    
    stats = get_subject_stats(subject_id, date_from, date_to)
    
    if not stats:
        await query.answer("Дисциплина не найдена", show_alert=True)
        return ConversationHandler.END
    
    subject_name = stats.get("subject_name", "Дисциплина")
    
    # Создаём график
    chart = create_students_chart(subject_id, subject_name, date_from, date_to)
    
    # Формируем текстовый список
    students = stats.get("students_stats", [])
    lines = [f"📊 <b>{subject_name}</b>"]
    if period_text:
        lines.append(f"<i>{period_text}</i>")
    lines.append("\n<b>Все студенты:</b>\n")
    
    for i, st in enumerate(students, 1):
        lines.append(
            f"{i}. {st['student_name']}: {format_percentage(st['percentage'])} "
            f"({st['present']}/{st['total']})"
        )
    
    text = "\n".join(lines)
    if len(text) > 1000:
        text = text[:1000] + "\n\n... (список обрезан)"
    
    # Отправляем график (если есть данные)
    if chart:
        await query.message.reply_photo(
            photo=chart,
            caption=text,
            parse_mode="HTML"
        )
    else:
        await query.message.reply_text(
            text=text,
            parse_mode="HTML"
        )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("◀️ Назад к статистике", callback_data=f"stats_subject_{subject_id}")],
    ])
    
    await query.edit_message_text(
        text="✅ Отчёт отправлен!",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    return ConversationHandler.END


async def stats_date_from_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка ввода начальной даты периода."""
    from datetime import datetime
    
    date_str = update.message.text.strip()
    subject_id = context.user_data.get("stats_subject_id")
    
    # Парсинг даты
    formats = ["%d.%m.%Y", "%d.%m.%y", "%d/%m/%Y"]
    parsed = None
    for fmt in formats:
        try:
            parsed = datetime.strptime(date_str, fmt).date()
            break
        except ValueError:
            continue
    
    if not parsed:
        await update.message.reply_text(
            "⚠️ Неверный формат даты.\n"
            "Введите в формате ДД.ММ.ГГГГ:"
        )
        return WAITING_STATS_DATE_FROM
    
    if parsed > date.today():
        await update.message.reply_text(
            "⚠️ Дата не может быть в будущем.\n"
            "Введите другую дату:"
        )
        return WAITING_STATS_DATE_FROM
    
    context.user_data["stats_date_from"] = parsed
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("◀️ Отмена", callback_data=f"stats_subject_{subject_id}")]
    ])
    
    await update.message.reply_text(
        text=(
            f"✅ Начало: <b>{format_date(parsed)}</b>\n\n"
            "Введите <b>конечную дату</b>:"
        ),
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    return WAITING_STATS_DATE_TO


async def stats_date_to_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка ввода конечной даты периода."""
    from datetime import datetime
    
    date_str = update.message.text.strip()
    subject_id = context.user_data.get("stats_subject_id")
    date_from = context.user_data.get("stats_date_from")
    
    # Парсинг даты
    formats = ["%d.%m.%Y", "%d.%m.%y", "%d/%m/%Y"]
    parsed = None
    for fmt in formats:
        try:
            parsed = datetime.strptime(date_str, fmt).date()
            break
        except ValueError:
            continue
    
    if not parsed:
        await update.message.reply_text(
            "⚠️ Неверный формат даты.\n"
            "Введите в формате ДД.ММ.ГГГГ:"
        )
        return WAITING_STATS_DATE_TO
    
    if parsed < date_from:
        await update.message.reply_text(
            f"⚠️ Конечная дата не может быть раньше начальной ({format_date(date_from)}).\n"
            "Введите другую дату:"
        )
        return WAITING_STATS_DATE_TO
    
    date_to = parsed
    period_text = f"за период {format_date(date_from)} — {format_date(date_to)}"
    
    context.user_data["stats_date_to"] = date_to
    context.user_data["stats_period_text"] = period_text
    
    # Получаем статистику и отправляем
    stats = get_subject_stats(subject_id, date_from, date_to)
    
    if not stats or stats.get("total_dates", 0) == 0:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📅 Другой период", callback_data=f"stats_subject_{subject_id}")],
            [InlineKeyboardButton("◀️ Назад", callback_data="menu_stats")],
        ])
        await update.message.reply_text(
            text=f"📊 <b>{stats.get('subject_name', 'Дисциплина')}</b>\n\nНет данных {period_text}.",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        return ConversationHandler.END
    
    # Формируем текст
    lines = [
        f"📊 <b>{stats['subject_name']}</b>",
        f"<i>{period_text}</i>\n",
        f"👥 Студентов: <b>{stats['total_students']}</b>",
        f"📅 Занятий: <b>{stats['total_dates']}</b>",
        f"📈 Средняя посещаемость: <b>{format_percentage(stats['avg_attendance'])}</b>",
        "\n<b>Топ студентов:</b>",
    ]
    
    students = stats.get("students_stats", [])
    for i, st in enumerate(students[:5], 1):
        lines.append(f"{i}. {st['student_name']}: {format_percentage(st['percentage'])}")
    
    if len(students) > 5:
        lines.append(f"... и ещё {len(students) - 5}")
    
    keyboard = [
        [
            InlineKeyboardButton("📊 По датам", callback_data=f"stats_chart_dates_{subject_id}"),
            InlineKeyboardButton("👥 По студентам", callback_data=f"stats_chart_students_{subject_id}"),
        ],
        [InlineKeyboardButton("📅 Другой период", callback_data=f"stats_subject_{subject_id}")],
        [InlineKeyboardButton("◀️ Назад", callback_data="menu_stats")],
    ]
    
    await update.message.reply_text(
        text="\n".join(lines),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )
    
    return ConversationHandler.END


async def noop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Пустой обработчик для декоративных кнопок."""
    query = update.callback_query
    await query.answer()
    return ConversationHandler.END


# === ConversationHandler для статистики ===

def get_stats_conversation_handler() -> ConversationHandler:
    """Создать ConversationHandler для статистики."""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(stats_menu, pattern="^menu_stats$"),
            CallbackQueryHandler(stats_overall, pattern="^stats_overall$"),
            CallbackQueryHandler(stats_overall_period_selected, pattern=r"^stats_overall_period_\w+$"),
            CallbackQueryHandler(stats_overall_chart, pattern="^stats_overall_chart$"),
            CallbackQueryHandler(stats_subject, pattern=r"^stats_subject_\d+$"),
            CallbackQueryHandler(stats_period_selected, pattern=r"^stats_period_\d+_\w+$"),
            CallbackQueryHandler(stats_chart_dates, pattern=r"^stats_chart_dates_\d+$"),
            CallbackQueryHandler(stats_chart_students, pattern=r"^stats_chart_students_\d+$"),
            CallbackQueryHandler(noop_callback, pattern="^noop$"),
        ],
        states={
            WAITING_STATS_DATE_FROM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, stats_date_from_input),
                CallbackQueryHandler(stats_subject, pattern=r"^stats_subject_\d+$"),
            ],
            WAITING_STATS_DATE_TO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, stats_date_to_input),
                CallbackQueryHandler(stats_subject, pattern=r"^stats_subject_\d+$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(stats_menu, pattern="^menu_stats$"),
        ],
        allow_reentry=True,
    )

