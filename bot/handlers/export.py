"""
Обработчики для экспорта данных в Excel.
"""

import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
)

from bot.database import get_session, crud
from bot.utils.export import create_attendance_report, create_all_subjects_report

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
                    callback_data="export_all"
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
                        callback_data=f"export_subject_{subject.id}"
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


async def export_subject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Экспортировать посещаемость по одной дисциплине."""
    query = update.callback_query
    await query.answer("📊 Формирую отчёт...")
    
    subject_id = int(query.data.split("_")[-1])
    
    session = get_session()
    try:
        subject = crud.get_subject_by_id(session, subject_id)
        students = crud.get_students_by_subject(session, subject_id)
        dates = crud.get_subject_attendance_dates(session, subject_id)
        
        if not students:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("👥 Добавить студентов", callback_data=f"students_menu_{subject_id}")],
                [InlineKeyboardButton("◀️ Назад", callback_data="menu_export")],
            ])
            
            await query.edit_message_text(
                text=(
                    f"💾 <b>Экспорт: {subject.name}</b>\n\n"
                    "В дисциплине нет студентов.\n"
                    "Добавьте студентов для экспорта."
                ),
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            return ConversationHandler.END
        
        if not dates:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✏️ Отметить посещаемость", callback_data=f"att_select_date_{subject_id}")],
                [InlineKeyboardButton("◀️ Назад", callback_data="menu_export")],
            ])
            
            await query.edit_message_text(
                text=(
                    f"💾 <b>Экспорт: {subject.name}</b>\n\n"
                    "Нет данных о посещаемости.\n"
                    "Сначала отметьте посещаемость."
                ),
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            return ConversationHandler.END
        
    finally:
        session.close()
    
    # Генерируем отчёт
    try:
        file_data = create_attendance_report(subject_id)
        
        # Имя файла
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        safe_name = "".join(c for c in subject.name if c.isalnum() or c in " _-").strip()[:30]
        filename = f"Посещаемость_{safe_name}_{timestamp}.xlsx"
        
        logger.info("Экспорт дисциплины %s в файл %s", subject.name, filename)
        
        # Отправляем файл
        await query.message.reply_document(
            document=file_data,
            filename=filename,
            caption=(
                f"📊 <b>Отчёт о посещаемости</b>\n\n"
                f"📚 {subject.name}\n"
                f"👥 Студентов: {len(students)}\n"
                f"📅 Дат: {len(dates)}"
            ),
            parse_mode="HTML"
        )
        
        # Обновляем сообщение
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
            [InlineKeyboardButton("🔄 Попробовать снова", callback_data=f"export_subject_{subject_id}")],
            [InlineKeyboardButton("◀️ Назад", callback_data="menu_export")],
        ])
        
        await query.edit_message_text(
            text=f"❌ Ошибка при экспорте:\n{str(e)}",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    
    return ConversationHandler.END


async def export_all(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Экспортировать все дисциплины в один файл."""
    query = update.callback_query
    await query.answer("📊 Формирую общий отчёт...")
    
    teacher, session = get_teacher_from_update(update)
    
    try:
        subjects = crud.get_subjects_by_teacher(session, teacher.id)
        
        # Проверяем есть ли данные
        has_data = False
        for subject in subjects:
            if crud.get_subject_attendance_dates(session, subject.id):
                has_data = True
                break
        
        if not has_data:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✏️ Отметить посещаемость", callback_data="menu_attendance")],
                [InlineKeyboardButton("◀️ Назад", callback_data="menu_export")],
            ])
            
            await query.edit_message_text(
                text=(
                    "💾 <b>Экспорт всех дисциплин</b>\n\n"
                    "Нет данных о посещаемости.\n"
                    "Сначала отметьте посещаемость хотя бы по одной дисциплине."
                ),
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            return ConversationHandler.END
    finally:
        session.close()
    
    # Генерируем отчёт
    try:
        file_data = create_all_subjects_report(teacher.id)
        
        # Имя файла
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"Посещаемость_все_дисциплины_{timestamp}.xlsx"
        
        logger.info("Экспорт всех дисциплин в файл %s", filename)
        
        # Отправляем файл
        await query.message.reply_document(
            document=file_data,
            filename=filename,
            caption=(
                f"📊 <b>Общий отчёт о посещаемости</b>\n\n"
                f"📚 Дисциплин: {len(subjects)}\n"
                f"Каждая дисциплина на отдельном листе."
            ),
            parse_mode="HTML"
        )
        
        # Обновляем сообщение
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
            [InlineKeyboardButton("🔄 Попробовать снова", callback_data="export_all")],
            [InlineKeyboardButton("◀️ Назад", callback_data="menu_export")],
        ])
        
        await query.edit_message_text(
            text=f"❌ Ошибка при экспорте:\n{str(e)}",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    
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
            CallbackQueryHandler(export_subject, pattern=r"^export_subject_\d+$"),
            CallbackQueryHandler(export_all, pattern="^export_all$"),
            CallbackQueryHandler(noop_callback, pattern="^noop$"),
        ],
        states={},
        fallbacks=[
            CallbackQueryHandler(export_menu, pattern="^menu_export$"),
        ],
        allow_reentry=True,
    )

