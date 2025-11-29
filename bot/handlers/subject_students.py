"""
Обработчики для управления студентами конкретной дисциплины.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from bot.database import get_session, crud
from bot.states import StudentStates

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


def get_subject_students_keyboard(subject_id: int, session) -> InlineKeyboardMarkup:
    """Создать клавиатуру со списком студентов дисциплины."""
    students = crud.get_students_by_subject(session, subject_id)
    
    keyboard = []
    for student in students:
        keyboard.append([
            InlineKeyboardButton(
                f"👤 {student.full_name}", 
                callback_data=f"subj_student_view_{subject_id}_{student.id}"
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton("➕ Добавить из пула", callback_data=f"subj_student_from_pool_{subject_id}"),
    ])
    keyboard.append([
        InlineKeyboardButton("🆕 Создать нового", callback_data=f"subj_student_create_{subject_id}"),
    ])
    keyboard.append([
        InlineKeyboardButton("◀️ К дисциплине", callback_data=f"subject_view_{subject_id}"),
    ])
    
    return InlineKeyboardMarkup(keyboard)


# === Основные обработчики ===

async def subject_students_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показать студентов дисциплины."""
    query = update.callback_query
    await query.answer()
    
    subject_id = int(query.data.split("_")[-1])
    context.user_data["current_subject_id"] = subject_id
    
    session = get_session()
    try:
        subject = crud.get_subject_by_id(session, subject_id)
        if not subject:
            await query.edit_message_text("❌ Дисциплина не найдена.")
            return ConversationHandler.END
        
        students = crud.get_students_by_subject(session, subject_id)
        
        if students:
            text = (
                f"👥 <b>Студенты: {subject.name}</b>\n\n"
                f"Всего: {len(students)} чел.\n\n"
                "Выберите студента или добавьте:"
            )
        else:
            text = (
                f"👥 <b>Студенты: {subject.name}</b>\n\n"
                "Список пуст.\n\n"
                "• <b>Добавить из пула</b> — выбрать из имеющихся студентов\n"
                "• <b>Создать нового</b> — создать и привязать к дисциплине"
            )
        
        keyboard = get_subject_students_keyboard(subject_id, session)
        
        await query.edit_message_text(
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    finally:
        session.close()
    
    return ConversationHandler.END


async def subject_student_from_pool(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показать список студентов из пула для добавления в дисциплину."""
    query = update.callback_query
    await query.answer()
    
    subject_id = int(query.data.split("_")[-1])
    context.user_data["adding_to_subject_id"] = subject_id
    
    teacher, session = get_teacher_from_update(update)
    
    try:
        subject = crud.get_subject_by_id(session, subject_id)
        available_students = crud.get_students_not_in_subject(session, teacher.id, subject_id)
        
        if not available_students:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🆕 Создать нового", callback_data=f"subj_student_create_{subject_id}")],
                [InlineKeyboardButton("◀️ Назад", callback_data=f"students_menu_{subject_id}")],
            ])
            
            await query.edit_message_text(
                text=(
                    f"📋 <b>Добавить студента: {subject.name}</b>\n\n"
                    "В пуле нет доступных студентов.\n"
                    "Все студенты уже добавлены в эту дисциплину,\n"
                    "или пул пуст.\n\n"
                    "Создайте нового студента."
                ),
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            return ConversationHandler.END
        
        # Показываем список доступных студентов
        keyboard = []
        for student in available_students:
            keyboard.append([
                InlineKeyboardButton(
                    f"➕ {student.full_name}", 
                    callback_data=f"subj_student_add_{subject_id}_{student.id}"
                )
            ])
        
        keyboard.append([
            InlineKeyboardButton("◀️ Назад", callback_data=f"students_menu_{subject_id}"),
        ])
        
        await query.edit_message_text(
            text=(
                f"📋 <b>Добавить студента: {subject.name}</b>\n\n"
                f"Доступно: {len(available_students)} чел.\n\n"
                "Выберите студента для добавления:"
            ),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
    finally:
        session.close()
    
    return ConversationHandler.END


async def subject_student_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Добавить студента из пула в дисциплину."""
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split("_")
    subject_id = int(parts[-2])
    student_id = int(parts[-1])
    
    session = get_session()
    try:
        student = crud.get_student_by_id(session, student_id)
        subject = crud.get_subject_by_id(session, subject_id)
        
        crud.add_student_to_subject(session, subject_id, student_id)
        logger.info(
            "Студент %s добавлен в дисциплину %s", 
            student.full_name, subject.name
        )
        
        keyboard = get_subject_students_keyboard(subject_id, session)
        
        await query.edit_message_text(
            f"✅ Студент <b>{student.full_name}</b> добавлен в дисциплину!",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    finally:
        session.close()
    
    return ConversationHandler.END


async def subject_student_create_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начать создание нового студента для дисциплины."""
    query = update.callback_query
    await query.answer()
    
    subject_id = int(query.data.split("_")[-1])
    context.user_data["creating_for_subject_id"] = subject_id
    
    session = get_session()
    try:
        subject = crud.get_subject_by_id(session, subject_id)
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Отмена", callback_data=f"students_menu_{subject_id}")]
        ])
        
        await query.edit_message_text(
            text=(
                f"🆕 <b>Создание студента</b>\n"
                f"Дисциплина: {subject.name}\n\n"
                "Введите ФИО нового студента:\n\n"
                "<i>Студент будет создан и сразу добавлен в дисциплину.</i>"
            ),
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    finally:
        session.close()
    
    return StudentStates.WAITING_NAME


async def subject_student_create_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Создать студента и добавить в дисциплину."""
    full_name = update.message.text.strip()
    subject_id = context.user_data.get("creating_for_subject_id")
    
    if not subject_id:
        await update.message.reply_text("❌ Ошибка. Попробуйте заново.")
        return ConversationHandler.END
    
    if len(full_name) < 2:
        await update.message.reply_text(
            "⚠️ ФИО слишком короткое. Введите минимум 2 символа:"
        )
        return StudentStates.WAITING_NAME
    
    if len(full_name) > 200:
        await update.message.reply_text(
            "⚠️ ФИО слишком длинное. Максимум 200 символов:"
        )
        return StudentStates.WAITING_NAME
    
    teacher, session = get_teacher_from_update(update)
    
    try:
        # Создаём студента в пуле
        student = crud.create_student(session, teacher.id, full_name)
        # Добавляем в дисциплину
        crud.add_student_to_subject(session, subject_id, student.id)
        
        logger.info(
            "Создан студент %s и добавлен в дисциплину %s", 
            student.full_name, subject_id
        )
        
        keyboard = get_subject_students_keyboard(subject_id, session)
        
        await update.message.reply_text(
            f"✅ Студент <b>{full_name}</b> создан и добавлен в дисциплину!",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    finally:
        session.close()
    
    return ConversationHandler.END


async def subject_student_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показать информацию о студенте в контексте дисциплины."""
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split("_")
    subject_id = int(parts[-2])
    student_id = int(parts[-1])
    
    session = get_session()
    try:
        student = crud.get_student_by_id(session, student_id)
        subject = crud.get_subject_by_id(session, subject_id)
        
        if not student or not subject:
            await query.edit_message_text("❌ Данные не найдены.")
            return ConversationHandler.END
        
        # Статистика посещаемости по этой дисциплине
        attendances = crud.get_student_attendance_by_subject(session, student_id, subject_id)
        total = len(attendances)
        present = sum(1 for a in attendances if a.is_present)
        percent = round(present / total * 100) if total > 0 else 0
        
        text = (
            f"👤 <b>{student.full_name}</b>\n"
            f"📚 Дисциплина: {subject.name}\n\n"
        )
        
        if total > 0:
            text += (
                f"📊 <b>Посещаемость:</b>\n"
                f"Занятий: {total}\n"
                f"Присутствовал: {present}\n"
                f"Процент: {percent}%"
            )
        else:
            text += "📊 Нет данных о посещаемости"
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🔓 Убрать из дисциплины", 
                    callback_data=f"subj_student_remove_{subject_id}_{student_id}"
                ),
            ],
            [
                InlineKeyboardButton("◀️ К студентам", callback_data=f"students_menu_{subject_id}"),
            ],
        ])
        
        await query.edit_message_text(
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    finally:
        session.close()
    
    return ConversationHandler.END


async def subject_student_remove_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Подтверждение удаления студента из дисциплины."""
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split("_")
    subject_id = int(parts[-2])
    student_id = int(parts[-1])
    
    session = get_session()
    try:
        student = crud.get_student_by_id(session, student_id)
        subject = crud.get_subject_by_id(session, subject_id)
        attendances = crud.get_student_attendance_by_subject(session, student_id, subject_id)
        
        warning = ""
        if attendances:
            warning = f"\n\n⚠️ Будут удалены {len(attendances)} записей посещаемости!"
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "✅ Да, убрать", 
                    callback_data=f"subj_student_remove_yes_{subject_id}_{student_id}"
                ),
                InlineKeyboardButton(
                    "❌ Отмена", 
                    callback_data=f"subj_student_view_{subject_id}_{student_id}"
                ),
            ],
        ])
        
        await query.edit_message_text(
            text=(
                f"🔓 <b>Убрать из дисциплины</b>\n\n"
                f"Убрать студента <b>{student.full_name}</b>\n"
                f"из дисциплины <b>{subject.name}</b>?\n\n"
                f"<i>Студент останется в общем пуле.</i>"
                f"{warning}"
            ),
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    finally:
        session.close()
    
    return ConversationHandler.END


async def subject_student_remove_yes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Убрать студента из дисциплины."""
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split("_")
    subject_id = int(parts[-2])
    student_id = int(parts[-1])
    
    session = get_session()
    try:
        student = crud.get_student_by_id(session, student_id)
        name = student.full_name if student else "Студент"
        
        if crud.remove_student_from_subject(session, subject_id, student_id):
            logger.info("Студент %s убран из дисциплины %s", name, subject_id)
            
            keyboard = get_subject_students_keyboard(subject_id, session)
            
            await query.edit_message_text(
                f"✅ Студент <b>{name}</b> убран из дисциплины.\n"
                f"<i>Он остался в общем пуле.</i>",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        else:
            await query.edit_message_text("❌ Не удалось убрать студента.")
    finally:
        session.close()
    
    return ConversationHandler.END


# === ConversationHandler для студентов дисциплины ===

def get_subject_students_conversation_handler() -> ConversationHandler:
    """Создать ConversationHandler для управления студентами дисциплины."""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(subject_students_menu, pattern=r"^students_menu_\d+$"),
            CallbackQueryHandler(subject_student_from_pool, pattern=r"^subj_student_from_pool_\d+$"),
            CallbackQueryHandler(subject_student_add, pattern=r"^subj_student_add_\d+_\d+$"),
            CallbackQueryHandler(subject_student_create_start, pattern=r"^subj_student_create_\d+$"),
            CallbackQueryHandler(subject_student_view, pattern=r"^subj_student_view_\d+_\d+$"),
            CallbackQueryHandler(subject_student_remove_confirm, pattern=r"^subj_student_remove_\d+_\d+$"),
            CallbackQueryHandler(subject_student_remove_yes, pattern=r"^subj_student_remove_yes_\d+_\d+$"),
        ],
        states={
            StudentStates.WAITING_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, subject_student_create_name),
                CallbackQueryHandler(subject_students_menu, pattern=r"^students_menu_\d+$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(subject_students_menu, pattern=r"^students_menu_\d+$"),
        ],
        allow_reentry=True,
    )

