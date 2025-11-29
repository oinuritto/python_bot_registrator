"""
Подключение к базе данных SQLite через SQLAlchemy.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from bot.config import DATABASE_URL, DATA_DIR

# Убедимся, что папка data существует
DATA_DIR.mkdir(exist_ok=True)

# Создаем движок SQLAlchemy
engine = create_engine(
    DATABASE_URL,
    echo=False,  # True для отладки SQL запросов
    connect_args={"check_same_thread": False}  # Для SQLite в многопоточной среде
)

# Фабрика сессий
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_session() -> Session:
    """Получить сессию БД."""
    return SessionLocal()


def init_db():
    """Инициализация БД - создание всех таблиц."""
    from bot.database.models import Base
    Base.metadata.create_all(bind=engine)

