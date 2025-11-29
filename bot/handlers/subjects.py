"""
Обработчики для управления дисциплинами.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from bot.database import get_session, crud
from bot.states import SubjectStates

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


def get_subjects_keyboard(teacher_id: int, session) -> InlineKeyboardMarkup:
    """Создать клавиатуру со списком дисциплин."""
    subjects = crud.get_subjects_by_teacher(session, teacher_id)

    keyboard = []
    for subject in subjects:
        keyboard.append([
            InlineKeyboardButton(
                f"📚 {subject.name}",
                callback_data=f"subject_view_{subject.id}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton("➕ Добавить дисциплину",
                             callback_data="subject_add")
    ])
    keyboard.append([
        InlineKeyboardButton("◀️ Назад в меню", callback_data="back_to_menu")
    ])

    return InlineKeyboardMarkup(keyboard)


# === Основные обработчики ===

async def subjects_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показать меню дисциплин."""
    query = update.callback_query
    if query:
        await query.answer()

    teacher, session = get_teacher_from_update(update)

    try:
        subjects = crud.get_subjects_by_teacher(session, teacher.id)

        if subjects:
            text = f"📚 <b>Ваши дисциплины</b> ({len(subjects)}):\n\n"
            text += "Выберите дисциплину для управления:"
        else:
            text = (
                "📚 <b>Дисциплины</b>\n\n"
                "У вас пока нет дисциплин.\n"
                "Нажмите кнопку ниже, чтобы добавить первую!"
            )

        keyboard = get_subjects_keyboard(teacher.id, session)

        if query:
            await query.edit_message_text(
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


async def subject_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начать добавление дисциплины."""
    query = update.callback_query
    await query.answer()

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Отмена", callback_data="subjects_menu")]
    ])

    await query.edit_message_text(
        text=(
            "📝 <b>Добавление дисциплины</b>\n\n"
            "Введите название новой дисциплины:"
        ),
        reply_markup=keyboard,
        parse_mode="HTML"
    )

    return SubjectStates.WAITING_NAME


async def subject_add_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохранить название дисциплины."""
    name = update.message.text.strip()

    if len(name) < 2:
        await update.message.reply_text(
            "⚠️ Название слишком короткое. Введите минимум 2 символа:"
        )
        return SubjectStates.WAITING_NAME

    if len(name) > 200:
        await update.message.reply_text(
            "⚠️ Название слишком длинное. Максимум 200 символов:"
        )
        return SubjectStates.WAITING_NAME

    teacher, session = get_teacher_from_update(update)

    try:
        subject = crud.create_subject(session, teacher.id, name)
        logger.info(
            "Создана дисциплина: %s (teacher_id=%s)", subject.name, teacher.id)

        keyboard = get_subjects_keyboard(teacher.id, session)

        await update.message.reply_text(
            f"✅ Дисциплина <b>«{name}»</b> успешно добавлена!",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    finally:
        session.close()

    return ConversationHandler.END


async def subject_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показать информацию о дисциплине."""
    query = update.callback_query
    await query.answer()

    # Извлекаем ID дисциплины из callback_data
    subject_id = int(query.data.split("_")[-1])
    context.user_data["current_subject_id"] = subject_id

    session = get_session()
    try:
        subject = crud.get_subject_by_id(session, subject_id)

        if not subject:
            await query.edit_message_text("❌ Дисциплина не найдена.")
            return ConversationHandler.END

        students = crud.get_students_by_subject(session, subject_id)
        students_count = len(students)

        text = (
            f"📚 <b>{subject.name}</b>\n\n"
            f"👥 Студентов: {students_count}\n"
            f"📅 Создана: {subject.created_at.strftime('%d.%m.%Y')}\n"
        )

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "👥 Студенты", callback_data=f"students_menu_{subject_id}"),
                InlineKeyboardButton(
                    "✏️ Переименовать", callback_data=f"subject_edit_{subject_id}"),
            ],
            [
                InlineKeyboardButton(
                    "🗑 Удалить", callback_data=f"subject_delete_{subject_id}"),
            ],
            [
                InlineKeyboardButton("◀️ К дисциплинам",
                                     callback_data="subjects_menu"),
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


async def subject_edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начать редактирование дисциплины."""
    query = update.callback_query
    await query.answer()

    subject_id = int(query.data.split("_")[-1])
    context.user_data["editing_subject_id"] = subject_id

    session = get_session()
    try:
        subject = crud.get_subject_by_id(session, subject_id)

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "❌ Отмена", callback_data=f"subject_view_{subject_id}")]
        ])

        await query.edit_message_text(
            text=(
                f"✏️ <b>Редактирование дисциплины</b>\n\n"
                f"Текущее название: <b>{subject.name}</b>\n\n"
                f"Введите новое название:"
            ),
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    finally:
        session.close()

    return SubjectStates.WAITING_NEW_NAME


async def subject_edit_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохранить новое название дисциплины."""
    name = update.message.text.strip()
    subject_id = context.user_data.get("editing_subject_id")

    if not subject_id:
        await update.message.reply_text("❌ Ошибка. Попробуйте заново.")
        return ConversationHandler.END

    if len(name) < 2:
        await update.message.reply_text(
            "⚠️ Название слишком короткое. Введите минимум 2 символа:"
        )
        return SubjectStates.WAITING_NEW_NAME

    session = get_session()
    try:
        subject = crud.update_subject(session, subject_id, name)

        if subject:
            logger.info("Дисциплина переименована: %s", subject.name)

            teacher, _ = get_teacher_from_update(update)
            keyboard = get_subjects_keyboard(teacher.id, session)

            await update.message.reply_text(
                f"✅ Дисциплина переименована в <b>«{name}»</b>",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        else:
            await update.message.reply_text("❌ Дисциплина не найдена.")
    finally:
        session.close()

    return ConversationHandler.END


async def subject_delete_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запросить подтверждение удаления дисциплины."""
    query = update.callback_query
    await query.answer()

    subject_id = int(query.data.split("_")[-1])
    context.user_data["deleting_subject_id"] = subject_id

    session = get_session()
    try:
        subject = crud.get_subject_by_id(session, subject_id)
        students = crud.get_students_by_subject(session, subject_id)

        warning = ""
        if students:
            warning = f"\n\n⚠️ <b>Внимание!</b> Будут удалены {len(students)} студент(ов) и все записи посещаемости!"

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "✅ Да, удалить", callback_data=f"subject_delete_yes_{subject_id}"),
                InlineKeyboardButton(
                    "❌ Отмена", callback_data=f"subject_view_{subject_id}"),
            ],
        ])

        await query.edit_message_text(
            text=(
                f"🗑 <b>Удаление дисциплины</b>\n\n"
                f"Вы уверены, что хотите удалить дисциплину <b>«{subject.name}»</b>?"
                f"{warning}"
            ),
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    finally:
        session.close()

    return ConversationHandler.END


async def subject_delete_yes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Подтвердить удаление дисциплины."""
    query = update.callback_query
    await query.answer()

    subject_id = int(query.data.split("_")[-1])

    teacher, session = get_teacher_from_update(update)

    try:
        subject = crud.get_subject_by_id(session, subject_id)
        name = subject.name if subject else "Неизвестная"

        if crud.delete_subject(session, subject_id):
            logger.info("Удалена дисциплина: %s", name)

            keyboard = get_subjects_keyboard(teacher.id, session)

            await query.edit_message_text(
                f"✅ Дисциплина <b>«{name}»</b> удалена.",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        else:
            await query.edit_message_text("❌ Не удалось удалить дисциплину.")
    finally:
        session.close()

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена текущей операции."""
    # Очищаем данные
    context.user_data.pop("editing_subject_id", None)
    context.user_data.pop("deleting_subject_id", None)

    # Возвращаемся к меню дисциплин
    return await subjects_menu(update, context)


# === ConversationHandler для дисциплин ===

def get_subjects_conversation_handler() -> ConversationHandler:
    """Создать ConversationHandler для управления дисциплинами."""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(subjects_menu, pattern="^menu_subjects$"),
            CallbackQueryHandler(subjects_menu, pattern="^subjects_menu$"),
            CallbackQueryHandler(subject_add_start, pattern="^subject_add$"),
            CallbackQueryHandler(subject_view, pattern=r"^subject_view_\d+$"),
            CallbackQueryHandler(subject_edit_start,
                                 pattern=r"^subject_edit_\d+$"),
            CallbackQueryHandler(subject_delete_confirm,
                                 pattern=r"^subject_delete_\d+$"),
            CallbackQueryHandler(subject_delete_yes,
                                 pattern=r"^subject_delete_yes_\d+$"),
        ],
        states={
            SubjectStates.WAITING_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND,
                               subject_add_name),
                CallbackQueryHandler(subjects_menu, pattern="^subjects_menu$"),
            ],
            SubjectStates.WAITING_NEW_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND,
                               subject_edit_name),
                CallbackQueryHandler(
                    subject_view, pattern=r"^subject_view_\d+$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(subjects_menu, pattern="^subjects_menu$"),
            CallbackQueryHandler(cancel, pattern="^back_to_menu$"),
        ],
        allow_reentry=True,
    )
