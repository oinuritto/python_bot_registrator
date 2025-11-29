"""
Обработчики для экспорта данных в Excel.
"""

import logging
from datetime import datetime, date, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from bot.database import get_session, crud
from bot.utils.export import create_attendance_report, create_all_subjects_report

logger = logging.getLogger(__name__)

# Состояния для выбора периода
WAITING_DATE_FROM = 1
WAITING_DATE_TO = 2


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
    """Форматировать дату."""
    return d.strftime("%d.%m.%Y")


def parse_date(date_str: str) -> date | None:
    """Парсинг даты из строки."""
    formats = ["%d.%m.%Y", "%d.%m.%y", "%d/%m/%Y", "%d-%m-%Y"]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    return None


def get_period_keyboard(export_type: str, subject_id: int | None = None) -> InlineKeyboardMarkup:
    """Клавиатура выбора периода."""
    today = date.today()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    # Формируем callback_data с типом экспорта
    prefix = f"exp_period_{export_type}"
    if subject_id:
        prefix += f"_{subject_id}"
    
    keyboard = [
        [InlineKeyboardButton("📅 За всё время", callback_data=f"{prefix}_all")],
        [InlineKeyboardButton(f"📅 Последняя неделя ({format_date(week_ago)} — {format_date(today)})", 
                              callback_data=f"{prefix}_week")],
        [InlineKeyboardButton(f"📅 Последний месяц ({format_date(month_ago)} — {format_date(today)})", 
                              callback_data=f"{prefix}_month")],
        [InlineKeyboardButton("📆 Указать период...", callback_data=f"{prefix}_custom")],
        [InlineKeyboardButton("◀️ Назад", callback_data="menu_export")],
    ]
    return InlineKeyboardMarkup(keyboard)


# === Основные обработчики ===

async def export_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показать меню экспорта."""
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
                "💾 <b>Экспорт данных</b>\n\n"
                "У вас нет дисциплин для экспорта.\n"
                "Сначала создайте дисциплину."
            )
        else:
            keyboard = []
            
            # Кнопка экспорта всего
            keyboard.append([
                InlineKeyboardButton(
                    "📊 Экспорт всех дисциплин",
                    callback_data="export_select_period_all"
                )
            ])
            
            keyboard.append([
                InlineKeyboardButton("— Или выберите дисциплину —", callback_data="noop")
            ])
            
            # Кнопки по дисциплинам
            for subject in subjects:
                students_count = crud.count_students_in_subject(session, subject.id)
                dates = crud.get_subject_attendance_dates(session, subject.id)
                
                badge = f"({students_count} студ., {len(dates)} дат)"
                keyboard.append([
                    InlineKeyboardButton(
                        f"📚 {subject.name} {badge}",
                        callback_data=f"export_select_period_subj_{subject.id}"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton("◀️ Назад в меню", callback_data="back_to_menu"),
            ])
            
            text = (
                "💾 <b>Экспорт данных в Excel</b>\n\n"
                "Выберите что экспортировать:\n\n"
                "• <b>Все дисциплины</b> — каждая на отдельном листе\n"
                "• <b>Одна дисциплина</b> — подробный отчёт"
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


async def export_select_period(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показать выбор периода для экспорта."""
    query = update.callback_query
    await query.answer()
    
    data = query.data.replace("export_select_period_", "")
    
    if data == "all":
        context.user_data["export_type"] = "all"
        context.user_data["export_subject_id"] = None
        keyboard = get_period_keyboard("all")
        text = "📆 <b>Экспорт всех дисциплин</b>\n\nВыберите период:"
    else:
        # subj_123
        subject_id = int(data.split("_")[-1])
        context.user_data["export_type"] = "subject"
        context.user_data["export_subject_id"] = subject_id
        
        session = get_session()
        try:
            subject = crud.get_subject_by_id(session, subject_id)
            text = f"📆 <b>Экспорт: {subject.name}</b>\n\nВыберите период:"
        finally:
            session.close()
        
        keyboard = get_period_keyboard("subj", subject_id)
    
    await query.edit_message_text(
        text=text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    return ConversationHandler.END


async def export_with_period(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Экспорт с выбранным периодом."""
    query = update.callback_query
    await query.answer("📊 Формирую отчёт...")
    
    # Парсим callback_data: exp_period_TYPE_SUBJECTID_PERIOD
    parts = query.data.split("_")
    period = parts[-1]  # all, week, month, custom
    
    export_type = context.user_data.get("export_type", "all")
    subject_id = context.user_data.get("export_subject_id")
    
    today = date.today()
    date_from = None
    date_to = None
    
    if period == "week":
        date_from = today - timedelta(days=7)
        date_to = today
    elif period == "month":
        date_from = today - timedelta(days=30)
        date_to = today
    elif period == "custom":
        # Переходим к вводу дат
        context.user_data["export_period_step"] = "from"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Отмена", callback_data="menu_export")]
        ])
        
        await query.edit_message_text(
            text=(
                "📆 <b>Укажите период</b>\n\n"
                "Введите <b>начальную дату</b> периода\n"
                "в формате ДД.ММ.ГГГГ\n\n"
                "Например: 01.09.2024"
            ),
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        return WAITING_DATE_FROM
    # period == "all" — date_from и date_to остаются None
    
    # Выполняем экспорт
    return await do_export(update, context, export_type, subject_id, date_from, date_to)


async def export_date_from_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка ввода начальной даты периода."""
    date_str = update.message.text.strip()
    parsed = parse_date(date_str)
    
    if not parsed:
        await update.message.reply_text(
            "⚠️ Неверный формат даты.\n"
            "Введите в формате ДД.ММ.ГГГГ (например: 01.09.2024):"
        )
        return WAITING_DATE_FROM
    
    if parsed > date.today():
        await update.message.reply_text(
            "⚠️ Дата не может быть в будущем.\n"
            "Введите другую дату:"
        )
        return WAITING_DATE_FROM
    
    context.user_data["export_date_from"] = parsed
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("◀️ Отмена", callback_data="menu_export")]
    ])
    
    await update.message.reply_text(
        text=(
            f"✅ Начало периода: <b>{format_date(parsed)}</b>\n\n"
            "Теперь введите <b>конечную дату</b> периода\n"
            "в формате ДД.ММ.ГГГГ:"
        ),
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    return WAITING_DATE_TO


async def export_date_to_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка ввода конечной даты периода."""
    date_str = update.message.text.strip()
    parsed = parse_date(date_str)
    
    if not parsed:
        await update.message.reply_text(
            "⚠️ Неверный формат даты.\n"
            "Введите в формате ДД.ММ.ГГГГ (например: 30.11.2024):"
        )
        return WAITING_DATE_TO
    
    date_from = context.user_data.get("export_date_from")
    
    if parsed < date_from:
        await update.message.reply_text(
            f"⚠️ Конечная дата не может быть раньше начальной ({format_date(date_from)}).\n"
            "Введите другую дату:"
        )
        return WAITING_DATE_TO
    
    date_to = parsed
    export_type = context.user_data.get("export_type", "all")
    subject_id = context.user_data.get("export_subject_id")
    
    # Выполняем экспорт
    return await do_export_from_message(update, context, export_type, subject_id, date_from, date_to)


async def do_export(update: Update, context, export_type: str, subject_id: int | None, 
                    date_from: date | None, date_to: date | None) -> int:
    """Выполнить экспорт (из callback query)."""
    query = update.callback_query
    
    session = get_session()
    try:
        if export_type == "subject" and subject_id:
            subject = crud.get_subject_by_id(session, subject_id)
            students = crud.get_students_by_subject(session, subject_id)
            dates = crud.get_subject_attendance_dates(session, subject_id)
            
            # Фильтруем даты
            if date_from:
                dates = [d for d in dates if d >= date_from]
            if date_to:
                dates = [d for d in dates if d <= date_to]
            
            if not students:
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("👥 Добавить студентов", callback_data=f"students_menu_{subject_id}")],
                    [InlineKeyboardButton("◀️ Назад", callback_data="menu_export")],
                ])
                await query.edit_message_text(
                    text=f"💾 <b>Экспорт: {subject.name}</b>\n\nВ дисциплине нет студентов.",
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
                return ConversationHandler.END
            
            if not dates:
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✏️ Отметить посещаемость", callback_data=f"att_select_date_{subject_id}")],
                    [InlineKeyboardButton("◀️ Назад", callback_data="menu_export")],
                ])
                msg = "Нет данных о посещаемости"
                if date_from or date_to:
                    msg += " за выбранный период"
                await query.edit_message_text(
                    text=f"💾 <b>Экспорт: {subject.name}</b>\n\n{msg}.",
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
                return ConversationHandler.END
    finally:
        session.close()
    
    try:
        if export_type == "subject" and subject_id:
            file_data = create_attendance_report(subject_id, date_from, date_to)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            safe_name = "".join(c for c in subject.name if c.isalnum() or c in " _-").strip()[:30]
            filename = f"Посещаемость_{safe_name}_{timestamp}.xlsx"
            
            period_text = ""
            if date_from and date_to:
                period_text = f"\n📆 Период: {format_date(date_from)} — {format_date(date_to)}"
            
            caption = (
                f"📊 <b>Отчёт о посещаемости</b>\n\n"
                f"📚 {subject.name}\n"
                f"👥 Студентов: {len(students)}\n"
                f"📅 Дат: {len(dates)}{period_text}"
            )
        else:
            teacher, session = get_teacher_from_update(update)
            try:
                subjects = crud.get_subjects_by_teacher(session, teacher.id)
            finally:
                session.close()
            
            file_data = create_all_subjects_report(teacher.id, date_from, date_to)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            filename = f"Посещаемость_все_дисциплины_{timestamp}.xlsx"
            
            period_text = ""
            if date_from and date_to:
                period_text = f"\n📆 Период: {format_date(date_from)} — {format_date(date_to)}"
            
            caption = (
                f"📊 <b>Общий отчёт о посещаемости</b>\n\n"
                f"📚 Дисциплин: {len(subjects)}{period_text}"
            )
        
        logger.info("Экспорт в файл %s", filename)
        
        await query.message.reply_document(
            document=file_data,
            filename=filename,
            caption=caption,
            parse_mode="HTML"
        )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 Экспортировать ещё", callback_data="menu_export")],
            [InlineKeyboardButton("◀️ В главное меню", callback_data="back_to_menu")],
        ])
        
        await query.edit_message_text(
            text="✅ Файл отправлен!",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error("Ошибка экспорта: %s", e)
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Попробовать снова", callback_data="menu_export")],
            [InlineKeyboardButton("◀️ Назад", callback_data="menu_export")],
        ])
        
        await query.edit_message_text(
            text=f"❌ Ошибка при экспорте:\n{str(e)}",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    
    return ConversationHandler.END


async def do_export_from_message(update: Update, context, export_type: str, subject_id: int | None,
                                  date_from: date | None, date_to: date | None) -> int:
    """Выполнить экспорт (из текстового сообщения)."""
    
    session = get_session()
    try:
        if export_type == "subject" and subject_id:
            subject = crud.get_subject_by_id(session, subject_id)
            students = crud.get_students_by_subject(session, subject_id)
            dates = crud.get_subject_attendance_dates(session, subject_id)
            
            # Фильтруем даты
            if date_from:
                dates = [d for d in dates if d >= date_from]
            if date_to:
                dates = [d for d in dates if d <= date_to]
            
            if not dates:
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("◀️ Назад", callback_data="menu_export")],
                ])
                await update.message.reply_text(
                    text=f"💾 <b>Экспорт: {subject.name}</b>\n\nНет данных о посещаемости за выбранный период.",
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
                return ConversationHandler.END
    finally:
        session.close()
    
    try:
        if export_type == "subject" and subject_id:
            file_data = create_attendance_report(subject_id, date_from, date_to)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            safe_name = "".join(c for c in subject.name if c.isalnum() or c in " _-").strip()[:30]
            filename = f"Посещаемость_{safe_name}_{timestamp}.xlsx"
            
            caption = (
                f"📊 <b>Отчёт о посещаемости</b>\n\n"
                f"📚 {subject.name}\n"
                f"👥 Студентов: {len(students)}\n"
                f"📅 Дат: {len(dates)}\n"
                f"📆 Период: {format_date(date_from)} — {format_date(date_to)}"
            )
        else:
            teacher, session = get_teacher_from_update(update)
            try:
                subjects = crud.get_subjects_by_teacher(session, teacher.id)
            finally:
                session.close()
            
            file_data = create_all_subjects_report(teacher.id, date_from, date_to)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            filename = f"Посещаемость_все_дисциплины_{timestamp}.xlsx"
            
            caption = (
                f"📊 <b>Общий отчёт о посещаемости</b>\n\n"
                f"📚 Дисциплин: {len(subjects)}\n"
                f"📆 Период: {format_date(date_from)} — {format_date(date_to)}"
            )
        
        logger.info("Экспорт в файл %s", filename)
        
        await update.message.reply_document(
            document=file_data,
            filename=filename,
            caption=caption,
            parse_mode="HTML"
        )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 Экспортировать ещё", callback_data="menu_export")],
            [InlineKeyboardButton("◀️ В главное меню", callback_data="back_to_menu")],
        ])
        
        await update.message.reply_text(
            text="✅ Файл отправлен!",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error("Ошибка экспорта: %s", e)
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Назад", callback_data="menu_export")],
        ])
        
        await update.message.reply_text(
            text=f"❌ Ошибка при экспорте:\n{str(e)}",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    
    # Очищаем данные
    context.user_data.pop("export_date_from", None)
    context.user_data.pop("export_type", None)
    context.user_data.pop("export_subject_id", None)
    
    return ConversationHandler.END


async def noop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Пустой обработчик для декоративных кнопок."""
    query = update.callback_query
    await query.answer()
    return ConversationHandler.END


# === ConversationHandler для экспорта ===

def get_export_conversation_handler() -> ConversationHandler:
    """Создать ConversationHandler для экспорта."""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(export_menu, pattern="^menu_export$"),
            CallbackQueryHandler(export_select_period, pattern=r"^export_select_period_"),
            CallbackQueryHandler(export_with_period, pattern=r"^exp_period_"),
            CallbackQueryHandler(noop_callback, pattern="^noop$"),
        ],
        states={
            WAITING_DATE_FROM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, export_date_from_input),
                CallbackQueryHandler(export_menu, pattern="^menu_export$"),
            ],
            WAITING_DATE_TO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, export_date_to_input),
                CallbackQueryHandler(export_menu, pattern="^menu_export$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(export_menu, pattern="^menu_export$"),
        ],
        allow_reentry=True,
    )
