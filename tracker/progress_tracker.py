"""
Отслеживание прогресса учеников
"""
import json
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class ProgressTracker:
    """
    Отслеживает прогресс ученика и сохраняет в PostgreSQL
    """
    
    def __init__(self, db_manager=None):
        """
        Args:
            db_manager: менеджер PostgreSQL
        """
        self.db_manager = db_manager
        
        if db_manager:
            logger.info("✅ ProgressTracker связан с PostgreSQL")
    
    def add_task_result(self, student_id: str, task_result: Dict):
        """
        Добавляет результат выполненного задания
        """
        task_result['timestamp'] = datetime.now().isoformat()
        student_id = str(student_id)
        if self.db_manager:
            try:
                self.db_manager.save_task_history(student_id, task_result)
                logger.info(f"✅ Результат сохранён в PostgreSQL для {student_id[:20]}...")
            except Exception as e:
                logger.error(f"❌ Ошибка сохранения в PostgreSQL: {e}")
    
    def get_progress(self, student_id: str, days: int = 30) -> Optional[Dict]:
        """
        Анализирует прогресс ученика
        """
        student_id = str(student_id)
        
        if self.db_manager:
            try:
                history = self.db_manager.get_student_history(student_id, limit=100)
                if len(history) >= 3:
                    return self._calculate_progress_from_list(history)
            except Exception as e:
                logger.warning(f"Не удалось получить данные из PostgreSQL: {e}")

        return None
    
    def _calculate_progress_from_list(self, tasks: List[Dict]) -> Dict:
        """Вычисляет прогресс из списка задач"""
        if len(tasks) < 3:
            return None
        recent = tasks[-20:]  # последние 20 заданий
        scores, times, hints = [], [], []
        
        for t in recent:
            score = t.get('score', 0)
            if isinstance(score, (int, float)): scores.append(float(score))
            else: scores.append(0.0)

            time_spent = t.get('time_spent', 0)
            if isinstance(time_spent, (int, float)): times.append(float(time_spent))

            hints_used = t.get('hints_used', 0)
            if isinstance(hints_used, (int, float)): hints.append(float(hints_used))

        topics = defaultdict(list)
        for task in recent:
            topic = task.get('topic', 'unknown')
            score = task.get('score', 0)
            if isinstance(score, (int, float)): topics[topic].append(float(score))

        trend = self._calculate_trend(scores)

        weak_topics, strong_topics = [], []
        for topic, topic_scores in topics.items():
            if topic_scores: 
                avg_score = np.mean(topic_scores)
                if avg_score < 0.6: weak_topics.append(topic)
                elif avg_score > 0.8: strong_topics.append(topic)
        
        return {
            'total_tasks': len(recent),
            'avg_score': float(np.mean(scores)) if scores else 0,
            'avg_time': float(np.mean(times)) if times else 0,
            'avg_hints': float(np.mean(hints)) if hints else 0,
            'trend': trend,
            'weak_topics': weak_topics[:3],
            'strong_topics': strong_topics[:3],
            'score_stability': float(np.std(scores)) if len(scores) > 1 else 0,
            'speed_trend': self._calculate_speed_trend(times) if times else "неизвестно"
        }
    
    def _calculate_trend(self, scores: List[float]) -> str:
        """Вычисляет тренд успеваемости"""
        if len(scores) < 3:
            return "недостаточно данных"

        n = len(scores)
        first_third = scores[:n//3]
        last_third = scores[-n//3:]
        
        if not first_third or not last_third:
            return "стабилен"
        
        first_avg = np.mean(first_third)
        last_avg = np.mean(last_third)
        
        if last_avg > first_avg + 0.1: return "растёт 📈"
        elif last_avg < first_avg - 0.1: return "падает 📉"
        else: return "стабилен ➡️"
    
    def _calculate_speed_trend(self, times: List[float]) -> str:
        """Анализирует изменение скорости решения"""
        if len(times) < 3:
            return "стабильно"
        
        if times[-1] < times[0] * 0.8: return "решает быстрее"
        elif times[-1] > times[0] * 1.2: return "решает медленнее"
        else: return "стабильно"