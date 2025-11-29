"""
Конфигурация бота.
Загрузка переменных окружения из .env файла.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные окружения из .env
load_dotenv()

# Токен бота (обязательный)
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не установлен! Проверьте .env файл.")

# Путь к базе данных
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/attendance.db")

# Часовой пояс
TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow")

# Уровень логирования
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")


# Путь к директории с данными
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

# Путь к директории с логами
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)
