"""
Утилиты для создания графиков посещаемости.
"""

import io
import matplotlib
matplotlib.use('Agg')  # Для работы без GUI

import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
from datetime import date

from bot.utils.stats import get_attendance_by_dates, get_students_attendance_df


# Настройка стиля
sns.set_theme(style="whitegrid")
plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['figure.figsize'] = (12, 6)
plt.rcParams['figure.dpi'] = 100


def create_dates_chart(subject_id: int, subject_name: str, 
                       date_from=None, date_to=None) -> io.BytesIO | None:
    """
    Создать гистограмму посещаемости по датам.
    
    Args:
        subject_id: ID дисциплины
        subject_name: Название дисциплины для заголовка
        date_from: Начальная дата периода
        date_to: Конечная дата периода
    
    Returns:
        BytesIO с изображением PNG или None если нет данных
    """
    df = get_attendance_by_dates(subject_id)
    
    # Фильтруем по периоду
    if not df.empty:
        if date_from:
            df = df[df['date'] >= date_from]
        if date_to:
            df = df[df['date'] <= date_to]
    
    if df.empty:
        return None
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Форматируем даты для отображения
    df['date_str'] = df['date'].apply(lambda x: x.strftime('%d.%m'))
    
    # Создаём Stacked Bar — один столбец на дату
    x = range(len(df))
    width = 0.6
    
    # Зелёный снизу (присутствовали)
    bars_present = ax.bar(
        x, 
        df['present'], 
        width, 
        label='Присутствовали',
        color='#4CAF50',
        edgecolor='white'
    )
    
    # Красный сверху (отсутствовали)
    bars_absent = ax.bar(
        x, 
        df['absent'], 
        width, 
        bottom=df['present'],  # Начинаем от верха зелёного
        label='Отсутствовали',
        color='#F44336',
        edgecolor='white'
    )
    
    # Настройки осей
    ax.set_xlabel('Дата', fontsize=12)
    ax.set_ylabel('Количество студентов', fontsize=12)
    ax.set_title(f'📊 Посещаемость: {subject_name}', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(df['date_str'], rotation=45, ha='right')
    
    # Подписи на столбцах
    for i, (bar_p, bar_a, present, absent) in enumerate(zip(bars_present, bars_absent, df['present'], df['absent'])):
        total = present + absent
        # Подпись присутствующих (в центре зелёной части)
        if present > 0:
            ax.annotate(f'{int(present)}',
                       xy=(bar_p.get_x() + bar_p.get_width() / 2, present / 2),
                       ha='center', va='center', fontsize=10, fontweight='bold', color='white')
        # Подпись отсутствующих (в центре красной части)
        if absent > 0:
            ax.annotate(f'{int(absent)}',
                       xy=(bar_a.get_x() + bar_a.get_width() / 2, present + absent / 2),
                       ha='center', va='center', fontsize=10, fontweight='bold', color='white')
        # Процент сверху столбца
        pct = present / total * 100 if total > 0 else 0
        ax.annotate(f'{pct:.0f}%',
                   xy=(bar_p.get_x() + bar_p.get_width() / 2, total),
                   xytext=(0, 5),
                   textcoords="offset points",
                   ha='center', va='bottom', fontsize=9, fontweight='bold')
    
    ax.legend(loc='upper right')
    
    plt.tight_layout()
    
    # Сохраняем в BytesIO
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', facecolor='white')
    plt.close(fig)
    buf.seek(0)
    
    return buf


def create_students_chart(subject_id: int, subject_name: str,
                          date_from=None, date_to=None) -> io.BytesIO | None:
    """
    Создать гистограмму посещаемости по студентам.
    
    Args:
        subject_id: ID дисциплины
        subject_name: Название дисциплины для заголовка
        date_from: Начальная дата периода
        date_to: Конечная дата периода
    
    Returns:
        BytesIO с изображением PNG или None если нет данных
    """
    df = get_students_attendance_df(subject_id, date_from, date_to)
    
    if df.empty:
        return None
    
    # Ограничиваем количество студентов для читаемости
    max_students = 20
    if len(df) > max_students:
        df = df.head(max_students)
    
    fig, ax = plt.subplots(figsize=(12, max(6, len(df) * 0.4)))
    
    # Сокращаем длинные имена
    df['short_name'] = df['name'].apply(lambda x: x[:25] + '...' if len(x) > 25 else x)
    
    # Цветовая палитра в зависимости от процента
    colors = []
    for pct in df['percentage']:
        if pct >= 80:
            colors.append('#4CAF50')  # Зелёный
        elif pct >= 60:
            colors.append('#FFC107')  # Жёлтый
        elif pct >= 40:
            colors.append('#FF9800')  # Оранжевый
        else:
            colors.append('#F44336')  # Красный
    
    # Горизонтальная гистограмма
    bars = ax.barh(df['short_name'], df['percentage'], color=colors, edgecolor='white')
    
    # Настройки
    ax.set_xlabel('Посещаемость (%)', fontsize=12)
    ax.set_ylabel('')
    ax.set_title(f'📊 Посещаемость студентов: {subject_name}', fontsize=14, fontweight='bold')
    ax.set_xlim(0, 105)
    
    # Добавляем значения на столбцы
    for bar, pct in zip(bars, df['percentage']):
        width = bar.get_width()
        ax.annotate(f'{pct:.0f}%',
                   xy=(width, bar.get_y() + bar.get_height() / 2),
                   xytext=(5, 0),
                   textcoords="offset points",
                   ha='left', va='center', fontsize=10, fontweight='bold')
    
    # Линии-ориентиры
    ax.axvline(x=80, color='#4CAF50', linestyle='--', linewidth=1, alpha=0.5)
    ax.axvline(x=60, color='#FFC107', linestyle='--', linewidth=1, alpha=0.5)
    
    # Инвертируем ось Y чтобы лучшие были сверху
    ax.invert_yaxis()
    
    plt.tight_layout()
    
    # Сохраняем в BytesIO
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', facecolor='white')
    plt.close(fig)
    buf.seek(0)
    
    return buf


def create_overall_chart(subjects_stats: list) -> io.BytesIO | None:
    """
    Создать общий график по всем дисциплинам.
    
    Args:
        subjects_stats: Список словарей со статистикой по дисциплинам
    
    Returns:
        BytesIO с изображением PNG или None если нет данных
    """
    # Фильтруем дисциплины без данных
    subjects_with_data = [s for s in subjects_stats if s.get("total_dates", 0) > 0]
    
    if not subjects_with_data:
        return None
    
    df = pd.DataFrame([
        {
            "name": s.get("subject_name", ""),
            "avg_attendance": s.get("avg_attendance", 0),
            "total_students": s.get("total_students", 0),
            "total_dates": s.get("total_dates", 0),
        }
        for s in subjects_with_data
    ])
    
    df = df.sort_values("avg_attendance", ascending=True)
    
    fig, ax = plt.subplots(figsize=(10, max(5, len(df) * 0.6)))
    
    # Цветовая палитра
    colors = []
    for pct in df['avg_attendance']:
        if pct >= 80:
            colors.append('#4CAF50')
        elif pct >= 60:
            colors.append('#FFC107')
        elif pct >= 40:
            colors.append('#FF9800')
        else:
            colors.append('#F44336')
    
    bars = ax.barh(df['name'], df['avg_attendance'], color=colors, edgecolor='white')
    
    ax.set_xlabel('Средняя посещаемость (%)', fontsize=12)
    ax.set_ylabel('')
    ax.set_title('📊 Посещаемость по дисциплинам', fontsize=14, fontweight='bold')
    ax.set_xlim(0, 105)
    
    for bar, pct, students, dates in zip(bars, df['avg_attendance'], df['total_students'], df['total_dates']):
        width = bar.get_width()
        ax.annotate(f'{pct:.0f}% ({students} студ., {dates} дат)',
                   xy=(width, bar.get_y() + bar.get_height() / 2),
                   xytext=(5, 0),
                   textcoords="offset points",
                   ha='left', va='center', fontsize=10)
    
    ax.axvline(x=80, color='#4CAF50', linestyle='--', linewidth=1, alpha=0.5)
    ax.axvline(x=60, color='#FFC107', linestyle='--', linewidth=1, alpha=0.5)
    
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', facecolor='white')
    plt.close(fig)
    buf.seek(0)
    
    return buf

