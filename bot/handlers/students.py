"""
Обработчики для управления общим пулом студентов.
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


def get_students_pool_keyboard(teacher_id: int, session) -> InlineKeyboardMarkup:
    """Создать клавиатуру со списком всех студентов (общий пул)."""
    students = crud.get_all_students_by_teacher(session, teacher_id)

    keyboard = []
    for student in students:
        # Количество дисциплин у студента
        subjects = crud.get_subjects_by_student(session, student.id)
        subjects_count = len(subjects)
        badge = f" ({subjects_count} дисц.)" if subjects_count else ""

        keyboard.append([
            InlineKeyboardButton(
                f"👤 {student.full_name}{badge}",
                callback_data=f"pool_student_view_{student.id}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton("➕ Добавить студента",
                             callback_data="pool_student_add"),
    ])
    keyboard.append([
        InlineKeyboardButton("📋 Добавить список",
                             callback_data="pool_student_bulk"),
    ])
    keyboard.append([
        InlineKeyboardButton("◀️ Назад в меню", callback_data="back_to_menu"),
    ])

    return InlineKeyboardMarkup(keyboard)


# === Основные обработчики ===

async def students_pool_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показать общий пул студентов."""
    query = update.callback_query
    if query:
        await query.answer()

    teacher, session = get_teacher_from_update(update)

    try:
        students = crud.get_all_students_by_teacher(session, teacher.id)

        if students:
            text = (
                f"👥 <b>Все студенты</b> ({len(students)})\n\n"
                "Это общий пул студентов.\n"
                "Отсюда можно добавлять их в дисциплины.\n\n"
                "Выберите студента:"
            )
        else:
            text = (
                "👥 <b>Все студенты</b>\n\n"
                "Список пуст.\n\n"
                "Добавьте студентов, а затем привяжите их к дисциплинам."
            )

        keyboard = get_students_pool_keyboard(teacher.id, session)

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


async def pool_student_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начать добавление студента в общий пул."""
    query = update.callback_query
    await query.answer()

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Отмена", callback_data="menu_students")]
    ])

    await query.edit_message_text(
        text=(
            "📝 <b>Добавление студента</b>\n\n"
            "Введите ФИО студента:"
        ),
        reply_markup=keyboard,
        parse_mode="HTML"
    )

    return StudentStates.WAITING_NAME


async def pool_student_add_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохранить ФИО студента в общий пул."""
    full_name = update.message.text.strip()

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
        student = crud.create_student(session, teacher.id, full_name)
        logger.info("Создан студент: %s (teacher_id=%s)",
                    student.full_name, teacher.id)

        keyboard = get_students_pool_keyboard(teacher.id, session)

        await update.message.reply_text(
            f"✅ Студент <b>{full_name}</b> добавлен в общий пул!",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    finally:
        session.close()

    return ConversationHandler.END


async def pool_student_bulk_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начать массовое добавление студентов."""
    query = update.callback_query
    await query.answer()

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Отмена", callback_data="menu_students")]
    ])

    await query.edit_message_text(
        text=(
            "📋 <b>Массовое добавление студентов</b>\n\n"
            "Отправьте список ФИО (каждый с новой строки):\n\n"
            "<i>Пример:\n"
            "Иванов Иван Иванович\n"
            "Петров Пётр Петрович\n"
            "Сидорова Анна Сергеевна</i>"
        ),
        reply_markup=keyboard,
        parse_mode="HTML"
    )

    return StudentStates.WAITING_BULK_NAMES


async def pool_student_bulk_names(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохранить список студентов в общий пул."""
    text = update.message.text.strip()

    # Разбиваем по строкам
    names = [name.strip() for name in text.split("\n") if name.strip()]

    if not names:
        await update.message.reply_text(
            "⚠️ Список пуст. Введите ФИО студентов (каждый с новой строки):"
        )
        return StudentStates.WAITING_BULK_NAMES

    # Фильтруем слишком короткие/длинные
    valid_names = [n for n in names if 2 <= len(n) <= 200]
    skipped = len(names) - len(valid_names)

    if not valid_names:
        await update.message.reply_text(
            "⚠️ Все ФИО некорректны. Введите ФИО от 2 до 200 символов:"
        )
        return StudentStates.WAITING_BULK_NAMES

    teacher, session = get_teacher_from_update(update)

    try:
        students = crud.create_students_bulk(session, teacher.id, valid_names)
        logger.info("Создано %s студентов (teacher_id=%s)",
                    len(students), teacher.id)

        keyboard = get_students_pool_keyboard(teacher.id, session)

        result_text = f"✅ Добавлено студентов: <b>{len(students)}</b>"
        if skipped:
            result_text += f"\n⚠️ Пропущено (некорректные): {skipped}"

        await update.message.reply_text(
            result_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    finally:
        session.close()

    return ConversationHandler.END


async def pool_student_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показать информацию о студенте из общего пула."""
    query = update.callback_query
    await query.answer()

    student_id = int(query.data.split("_")[-1])
    context.user_data["current_student_id"] = student_id

    session = get_session()
    try:
        student = crud.get_student_by_id(session, student_id)

        if not student:
            await query.edit_message_text("❌ Студент не найден.")
            return ConversationHandler.END

        # Дисциплины студента
        subjects = crud.get_subjects_by_student(session, student_id)

        # Общая статистика посещаемости
        all_attendances = crud.get_student_all_attendance(session, student_id)
        total = len(all_attendances)
        present = sum(1 for a in all_attendances if a.is_present)
        percent = round(present / total * 100) if total > 0 else 0

        text = (
            f"👤 <b>{student.full_name}</b>\n\n"
            f"📅 Добавлен: {student.created_at.strftime('%d.%m.%Y')}\n\n"
        )

        if subjects:
            text += f"📚 <b>Дисциплины ({len(subjects)}):</b>\n"
            for subj in subjects:
                text += f"  • {subj.name}\n"
            text += "\n"
        else:
            text += "📚 Не привязан к дисциплинам\n\n"

        if total > 0:
            text += (
                f"📊 <b>Общая посещаемость:</b>\n"
                f"Занятий: {total}\n"
                f"Присутствовал: {present}\n"
                f"Процент: {percent}%"
            )
        else:
            text += "📊 Нет данных о посещаемости"

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "✏️ Изменить ФИО", callback_data=f"pool_student_edit_{student_id}"),
            ],
            [
                InlineKeyboardButton(
                    "🗑 Удалить", callback_data=f"pool_student_delete_{student_id}"),
            ],
            [
                InlineKeyboardButton(
                    "◀️ К списку студентов", callback_data="menu_students"),
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


async def pool_student_edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начать редактирование студента."""
    query = update.callback_query
    await query.answer()

    student_id = int(query.data.split("_")[-1])
    context.user_data["editing_student_id"] = student_id

    session = get_session()
    try:
        student = crud.get_student_by_id(session, student_id)

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "❌ Отмена", callback_data=f"pool_student_view_{student_id}")]
        ])

        await query.edit_message_text(
            text=(
                f"✏️ <b>Редактирование студента</b>\n\n"
                f"Текущее ФИО: <b>{student.full_name}</b>\n\n"
                f"Введите новое ФИО:"
            ),
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    finally:
        session.close()

    return StudentStates.WAITING_NEW_NAME


async def pool_student_edit_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохранить новое ФИО студента."""
    full_name = update.message.text.strip()
    student_id = context.user_data.get("editing_student_id")

    if not student_id:
        await update.message.reply_text("❌ Ошибка. Попробуйте заново.")
        return ConversationHandler.END

    if len(full_name) < 2:
        await update.message.reply_text(
            "⚠️ ФИО слишком короткое. Введите минимум 2 символа:"
        )
        return StudentStates.WAITING_NEW_NAME

    teacher, session = get_teacher_from_update(update)

    try:
        student = crud.update_student(session, student_id, full_name)

        if student:
            logger.info("Студент переименован: %s", student.full_name)

            keyboard = get_students_pool_keyboard(teacher.id, session)

            await update.message.reply_text(
                f"✅ ФИО изменено на <b>{full_name}</b>",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        else:
            await update.message.reply_text("❌ Студент не найден.")
    finally:
        session.close()

    return ConversationHandler.END


async def pool_student_delete_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запросить подтверждение удаления студента."""
    query = update.callback_query
    await query.answer()

    student_id = int(query.data.split("_")[-1])

    session = get_session()
    try:
        student = crud.get_student_by_id(session, student_id)
        subjects = crud.get_subjects_by_student(session, student_id)
        attendances = crud.get_student_all_attendance(session, student_id)

        warnings = []
        if subjects:
            warnings.append(f"• Привязан к {len(subjects)} дисциплин(ам)")
        if attendances:
            warnings.append(
                f"• Будут удалены {len(attendances)} записей посещаемости")

        warning_text = ""
        if warnings:
            warning_text = "\n\n⚠️ <b>Внимание!</b>\n" + "\n".join(warnings)

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "✅ Да, удалить", callback_data=f"pool_student_delete_yes_{student_id}"),
                InlineKeyboardButton(
                    "❌ Отмена", callback_data=f"pool_student_view_{student_id}"),
            ],
        ])

        await query.edit_message_text(
            text=(
                f"🗑 <b>Удаление студента</b>\n\n"
                f"Вы уверены, что хотите удалить студента <b>{student.full_name}</b>?"
                f"{warning_text}"
            ),
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    finally:
        session.close()

    return ConversationHandler.END


async def pool_student_delete_yes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Подтвердить удаление студента."""
    query = update.callback_query
    await query.answer()

    student_id = int(query.data.split("_")[-1])

    teacher, session = get_teacher_from_update(update)

    try:
        student = crud.get_student_by_id(session, student_id)
        name = student.full_name if student else "Неизвестный"

        if crud.delete_student(session, student_id):
            logger.info("Удалён студент: %s", name)

            keyboard = get_students_pool_keyboard(teacher.id, session)

            await query.edit_message_text(
                f"✅ Студент <b>{name}</b> удалён из системы.",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        else:
            await query.edit_message_text("❌ Не удалось удалить студента.")
    finally:
        session.close()

    return ConversationHandler.END


# === ConversationHandler для общего пула студентов ===

def get_students_conversation_handler() -> ConversationHandler:
    """Создать ConversationHandler для управления общим пулом студентов."""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(students_pool_menu,
                                 pattern="^menu_students$"),
            CallbackQueryHandler(pool_student_add_start,
                                 pattern="^pool_student_add$"),
            CallbackQueryHandler(pool_student_bulk_start,
                                 pattern="^pool_student_bulk$"),
            CallbackQueryHandler(
                pool_student_view, pattern=r"^pool_student_view_\d+$"),
            CallbackQueryHandler(pool_student_edit_start,
                                 pattern=r"^pool_student_edit_\d+$"),
            CallbackQueryHandler(pool_student_delete_confirm,
                                 pattern=r"^pool_student_delete_\d+$"),
            CallbackQueryHandler(pool_student_delete_yes,
                                 pattern=r"^pool_student_delete_yes_\d+$"),
        ],
        states={
            StudentStates.WAITING_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND,
                               pool_student_add_name),
                CallbackQueryHandler(students_pool_menu,
                                     pattern="^menu_students$"),
            ],
            StudentStates.WAITING_BULK_NAMES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND,
                               pool_student_bulk_names),
                CallbackQueryHandler(students_pool_menu,
                                     pattern="^menu_students$"),
            ],
            StudentStates.WAITING_NEW_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND,
                               pool_student_edit_name),
                CallbackQueryHandler(
                    pool_student_view, pattern=r"^pool_student_view_\d+$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(students_pool_menu,
                                 pattern="^menu_students$"),
        ],
        allow_reentry=True,
    )
