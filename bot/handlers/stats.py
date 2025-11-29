"""
Обработчики для статистики и визуализации.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
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
    """Общая статистика по всем дисциплинам."""
    query = update.callback_query
    await query.answer("📊 Загрузка статистики...")
    
    teacher, session = get_teacher_from_update(update)
    session.close()
    
    stats = get_teacher_overall_stats(teacher.id)
    
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
        "📊 <b>Общая статистика</b>\n",
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
    
    teacher, session = get_teacher_from_update(update)
    session.close()
    
    stats = get_teacher_overall_stats(teacher.id)
    
    chart = create_overall_chart(stats.get("subjects_stats", []))
    
    if not chart:
        await query.answer("Недостаточно данных для графика", show_alert=True)
        return ConversationHandler.END
    
    await query.message.reply_photo(
        photo=chart,
        caption="📊 Посещаемость по дисциплинам"
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("◀️ Назад", callback_data="menu_stats")],
    ])
    
    await query.edit_message_text(
        text="✅ График отправлен!",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    return ConversationHandler.END


async def stats_subject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Статистика по конкретной дисциплине."""
    query = update.callback_query
    await query.answer()
    
    subject_id = int(query.data.split("_")[-1])
    
    stats = get_subject_stats(subject_id)
    
    if not stats:
        await query.answer("Дисциплина не найдена", show_alert=True)
        return ConversationHandler.END
    
    if stats.get("total_dates", 0) == 0:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ Отметить посещаемость", callback_data=f"att_select_date_{subject_id}")],
            [InlineKeyboardButton("◀️ Назад", callback_data="menu_stats")],
        ])
        await query.edit_message_text(
            text=f"📊 <b>{stats['subject_name']}</b>\n\nНет данных о посещаемости.",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        return ConversationHandler.END
    
    # Формируем текст
    lines = [
        f"📊 <b>{stats['subject_name']}</b>\n",
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
    
    session = get_session()
    try:
        subject = crud.get_subject_by_id(session, subject_id)
        subject_name = subject.name if subject else "Дисциплина"
    finally:
        session.close()
    
    chart = create_dates_chart(subject_id, subject_name)
    
    if not chart:
        await query.answer("Недостаточно данных для графика", show_alert=True)
        return ConversationHandler.END
    
    await query.message.reply_photo(
        photo=chart,
        caption=f"📊 Посещаемость по датам: {subject_name}"
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
    
    stats = get_subject_stats(subject_id)
    
    if not stats:
        await query.answer("Дисциплина не найдена", show_alert=True)
        return ConversationHandler.END
    
    subject_name = stats.get("subject_name", "Дисциплина")
    
    # Создаём график
    chart = create_students_chart(subject_id, subject_name)
    
    # Формируем текстовый список
    students = stats.get("students_stats", [])
    lines = [f"📊 <b>{subject_name}</b>\n", "<b>Все студенты:</b>\n"]
    
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
            CallbackQueryHandler(stats_overall_chart, pattern="^stats_overall_chart$"),
            CallbackQueryHandler(stats_subject, pattern=r"^stats_subject_\d+$"),
            CallbackQueryHandler(stats_chart_dates, pattern=r"^stats_chart_dates_\d+$"),
            CallbackQueryHandler(stats_chart_students, pattern=r"^stats_chart_students_\d+$"),
            CallbackQueryHandler(noop_callback, pattern="^noop$"),
        ],
        states={},
        fallbacks=[
            CallbackQueryHandler(stats_menu, pattern="^menu_stats$"),
        ],
        allow_reentry=True,
    )

