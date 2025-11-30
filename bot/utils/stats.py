"""
Утилиты для расчёта статистики посещаемости.
"""

import pandas as pd
from datetime import date
from typing import Optional

from bot.database import get_session, crud


def get_student_stats(student_id: int, subject_id: Optional[int] = None, 
                      date_from: Optional[date] = None, date_to: Optional[date] = None) -> dict:
    """
    Статистика по конкретному студенту.
    
    Args:
        student_id: ID студента
        subject_id: ID дисциплины (если None - по всем дисциплинам)
    
    Returns:
        dict с полями: total, present, absent, percentage, dates_present, dates_absent
    """
    session = get_session()
    try:
        student = crud.get_student_by_id(session, student_id)
        if not student:
            return {}
        
        if subject_id:
            # Получаем ВСЕ даты занятий по дисциплине
            all_dates = crud.get_subject_attendance_dates(session, subject_id)
            
            # Фильтруем по периоду
            if date_from:
                all_dates = [d for d in all_dates if d >= date_from]
            if date_to:
                all_dates = [d for d in all_dates if d <= date_to]
            
            # Получаем записи посещаемости студента
            attendances = crud.get_student_attendance_by_subject(
                session, student_id, subject_id
            )
            attendance_dict = {att.date: att.is_present for att in attendances}
            
            dates_present = []
            dates_absent = []
            
            # Проверяем каждую дату занятия
            for d in all_dates:
                if d in attendance_dict:
                    if attendance_dict[d]:
                        dates_present.append(d)
                    else:
                        dates_absent.append(d)
                else:
                    # Нет записи = пропуск
                    dates_absent.append(d)
            
            total = len(all_dates)
        else:
            # Статистика по всем дисциплинам (старая логика)
            attendances = crud.get_student_all_attendance(session, student_id)
            
            dates_present = []
            dates_absent = []
            
            for att in attendances:
                if att.is_present:
                    dates_present.append(att.date)
                else:
                    dates_absent.append(att.date)
            
            total = len(attendances)
        
        present = len(dates_present)
        absent = len(dates_absent)
        percentage = round(present / total * 100, 1) if total > 0 else 0
        
        return {
            "student_name": student.full_name,
            "total": total,
            "present": present,
            "absent": absent,
            "percentage": percentage,
            "dates_present": sorted(dates_present),
            "dates_absent": sorted(dates_absent),
        }
    finally:
        session.close()


def get_subject_stats(subject_id: int, date_from: Optional[date] = None, 
                      date_to: Optional[date] = None) -> dict:
    """
    Статистика по дисциплине.
    
    Returns:
        dict с полями: subject_name, total_dates, total_students, 
                       avg_attendance, students_stats (отсортированные)
    """
    session = get_session()
    try:
        subject = crud.get_subject_by_id(session, subject_id)
        if not subject:
            return {}
        
        students = crud.get_students_by_subject(session, subject_id)
        dates = crud.get_subject_attendance_dates(session, subject_id)
        
        # Фильтруем по периоду
        if date_from:
            dates = [d for d in dates if d >= date_from]
        if date_to:
            dates = [d for d in dates if d <= date_to]
        
        if not students or not dates:
            return {
                "subject_name": subject.name,
                "total_dates": 0,
                "total_students": len(students),
                "avg_attendance": 0,
                "students_stats": [],
            }
        
        students_stats = []
        total_percentage = 0
        
        for student in students:
            stats = get_student_stats(student.id, subject_id, date_from, date_to)
            students_stats.append(stats)
            total_percentage += stats.get("percentage", 0)
        
        # Сортируем по проценту (лучшие сверху)
        students_stats.sort(key=lambda x: x.get("percentage", 0), reverse=True)
        
        avg_attendance = round(total_percentage / len(students), 1) if students else 0
        
        return {
            "subject_name": subject.name,
            "total_dates": len(dates),
            "total_students": len(students),
            "avg_attendance": avg_attendance,
            "students_stats": students_stats,
        }
    finally:
        session.close()


def get_attendance_by_dates(subject_id: int) -> pd.DataFrame:
    """
    Получить DataFrame с посещаемостью по датам.
    
    Returns:
        DataFrame: index=даты, columns=['date', 'present', 'absent', 'total', 'percentage']
    """
    session = get_session()
    try:
        dates = crud.get_subject_attendance_dates(session, subject_id)
        students = crud.get_students_by_subject(session, subject_id)
        
        if not dates or not students:
            return pd.DataFrame()
        
        data = []
        for d in sorted(dates):
            present = 0
            absent = 0
            
            for student in students:
                att = crud.get_attendance(session, student.id, subject_id, d)
                if att:
                    if att.is_present:
                        present += 1
                    else:
                        absent += 1
                else:
                    absent += 1  # Нет записи = отсутствие
            
            total = present + absent
            percentage = round(present / total * 100, 1) if total > 0 else 0
            
            data.append({
                "date": d,
                "present": present,
                "absent": absent,
                "total": total,
                "percentage": percentage,
            })
        
        return pd.DataFrame(data)
    finally:
        session.close()


def get_students_attendance_df(subject_id: int, date_from: Optional[date] = None,
                                date_to: Optional[date] = None) -> pd.DataFrame:
    """
    Получить DataFrame с посещаемостью по студентам.
    
    Returns:
        DataFrame: columns=['name', 'present', 'absent', 'total', 'percentage']
    """
    session = get_session()
    try:
        students = crud.get_students_by_subject(session, subject_id)
        
        if not students:
            return pd.DataFrame()
        
        data = []
        for student in students:
            stats = get_student_stats(student.id, subject_id, date_from, date_to)
            data.append({
                "name": student.full_name,
                "present": stats.get("present", 0),
                "absent": stats.get("absent", 0),
                "total": stats.get("total", 0),
                "percentage": stats.get("percentage", 0),
            })
        
        df = pd.DataFrame(data)
        df = df.sort_values("percentage", ascending=False)
        
        return df
    finally:
        session.close()


def get_teacher_overall_stats(teacher_id: int, date_from: Optional[date] = None,
                               date_to: Optional[date] = None) -> dict:
    """
    Общая статистика преподавателя по всем дисциплинам.
    """
    session = get_session()
    try:
        subjects = crud.get_subjects_by_teacher(session, teacher_id)
        
        total_students = 0
        total_subjects = len(subjects)
        total_dates = 0
        subjects_stats = []
        
        for subject in subjects:
            stats = get_subject_stats(subject.id, date_from, date_to)
            subjects_stats.append(stats)
            total_students += stats.get("total_students", 0)
            total_dates += stats.get("total_dates", 0)
        
        # Средняя посещаемость по всем дисциплинам
        avg_attendances = [s.get("avg_attendance", 0) for s in subjects_stats if s.get("total_dates", 0) > 0]
        overall_avg = round(sum(avg_attendances) / len(avg_attendances), 1) if avg_attendances else 0
        
        return {
            "total_subjects": total_subjects,
            "total_students": total_students,
            "total_dates": total_dates,
            "overall_avg_attendance": overall_avg,
            "subjects_stats": subjects_stats,
        }
    finally:
        session.close()

