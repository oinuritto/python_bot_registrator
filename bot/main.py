"""
Главный модуль бота-регистратора посещаемости.
Точка входа и запуск бота.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from bot.config import BOT_TOKEN, LOG_LEVEL, LOGS_DIR
from bot.database import init_db
from bot.handlers.subjects import get_subjects_conversation_handler
from bot.handlers.students import get_students_conversation_handler
from bot.handlers.subject_students import get_subject_students_conversation_handler
from bot.handlers.attendance import get_attendance_conversation_handler

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=getattr(logging, LOG_LEVEL),
    handlers=[
        logging.FileHandler(LOGS_DIR / "bot.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


# === Главное меню ===
def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру главного меню."""
    keyboard = [
        [
            InlineKeyboardButton(
                "📚 Дисциплины", callback_data="menu_subjects"),
            InlineKeyboardButton("👥 Студенты", callback_data="menu_students"),
        ],
        [
            InlineKeyboardButton("✏️ Отметить посещаемость",
                                 callback_data="menu_attendance"),
        ],
        [
            InlineKeyboardButton("📊 Статистика", callback_data="menu_stats"),
            InlineKeyboardButton("💾 Экспорт", callback_data="menu_export"),
        ],
        [
            InlineKeyboardButton("ℹ️ Помощь", callback_data="menu_help"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


# === Обработчики команд ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start."""
    user = update.effective_user
    logger.info("Пользователь %s (%s) запустил бота", user.id, user.full_name)

    welcome_text = (
        f"👋 Привет, {user.first_name}!\n\n"
        "Я бот-регистратор посещаемости лекций.\n\n"
        "Что я умею:\n"
        "• 📚 Управлять списком дисциплин\n"
        "• 👥 Вести список студентов\n"
        "• ✏️ Отмечать посещаемость\n"
        "• 📊 Показывать статистику\n"
        "• 💾 Экспортировать данные в Excel\n\n"
        "Выберите действие в меню ниже:"
    )

    await update.message.reply_text(
        welcome_text,
        reply_markup=get_main_menu_keyboard(),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /help."""
    help_text = (
        "📖 <b>Справка по боту</b>\n\n"
        "<b>Команды:</b>\n"
        "/start - Запуск бота и главное меню\n"
        "/help - Показать эту справку\n"
        "/menu - Показать главное меню\n\n"
        "<b>Как пользоваться:</b>\n"
        "1. Добавьте дисциплины\n"
        "2. Добавьте студентов к дисциплинам\n"
        "3. Отмечайте посещаемость по датам\n"
        "4. Просматривайте статистику и экспортируйте данные"
    )

    await update.message.reply_text(help_text, parse_mode="HTML")


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /menu."""
    await update.message.reply_text(
        "📋 Главное меню:",
        reply_markup=get_main_menu_keyboard(),
    )


# === Обработчик кнопок меню ===
async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик нажатий на кнопки главного меню."""
    query = update.callback_query
    await query.answer()

    callback_data = query.data

    # Заглушки для ещё не реализованных функций
    messages = {
        "menu_stats": "📊 <b>Статистика</b>\n\n🚧 В разработке...",
        "menu_export": "💾 <b>Экспорт данных</b>\n\n🚧 В разработке...",
        "menu_help": (
            "ℹ️ <b>Помощь</b>\n\n"
            "Используйте /help для получения справки.\n"
            "Для возврата в меню нажмите /menu"
        ),
    }

    text = messages.get(callback_data, "Неизвестная команда")

    # Добавляем кнопку "Назад" к ответу
    back_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("◀️ Назад в меню", callback_data="back_to_menu")]
    ])

    await query.edit_message_text(
        text=text,
        reply_markup=back_keyboard,
        parse_mode="HTML",
    )


async def back_to_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопки 'Назад в меню'."""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        text="📋 Главное меню:",
        reply_markup=get_main_menu_keyboard(),
    )


def main() -> None:
    """Запуск бота."""
    logger.info("Запуск бота...")

    # Инициализация базы данных
    logger.info("Инициализация базы данных...")
    init_db()
    logger.info("База данных готова!")

    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()

    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("menu", menu_command))

    # Регистрируем ConversationHandler для дисциплин, студентов и посещаемости
    application.add_handler(get_subjects_conversation_handler())
    application.add_handler(get_students_conversation_handler())
    application.add_handler(get_subject_students_conversation_handler())
    application.add_handler(get_attendance_conversation_handler())

    # Регистрируем обработчики кнопок
    application.add_handler(CallbackQueryHandler(
        back_to_menu_callback, pattern="^back_to_menu$"))
    application.add_handler(CallbackQueryHandler(
        menu_callback, pattern="^menu_"))

    # Запускаем бота
    logger.info("Бот запущен и готов к работе!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
