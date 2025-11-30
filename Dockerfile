FROM python:3.12-slim

# Метаданные
LABEL maintainer="oinuritto"
LABEL description="Telegram Bot для учёта посещаемости"

# Рабочая директория
WORKDIR /app

# Системные зависимости для matplotlib
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Копируем зависимости
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код
COPY bot/ ./bot/

# Создаём директории для данных
RUN mkdir -p /app/data /app/logs

# Переменные окружения по умолчанию
ENV PYTHONUNBUFFERED=1
ENV DATABASE_URL=sqlite:///data/bot.db
ENV LOGS_DIR=/app/logs

# Запуск
CMD ["python", "-m", "bot.main"]

