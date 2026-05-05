import logging
from typing import Dict, Optional
from database.db_manager import db_manager

logger = logging.getLogger(__name__)

class StudentProfiler:
    """Анализирует профиль студента из БД"""
    
    def __init__(self, db_manager_instance=None):
        self.db_manager = db_manager_instance or db_manager
    
    def get_profile(self, student_uuid: str) -> Dict:
        """Получает полный профиль студента по UUID"""
        profile = self.db_manager.get_user_profile_by_uuid(student_uuid)
        if not profile:
            logger.warning(f"Профиль не найден для {student_uuid}, возвращаем дефолтный")
            return self._get_default_profile()
        
        user = self.db_manager.get_user_by_id(profile.user_id)
        group_info = self._get_group_info(profile.group_id)
        history = self.db_manager.get_task_history(student_uuid, limit=50)
        recent_scores = []
        if history:
            last_10 = history[-10:]
            recent_scores = [h.get('score', 0) for h in last_10 if isinstance(h, dict)]
        
        return {
            'uuid': student_uuid,
            'name': f"{user.first_name} {user.last_name}" if user else "Студент",
            'group': group_info,
            'academic': {
                'success_rate': float(profile.success_rate or 0.5),
                'avg_mastery': float(profile.avg_mastery or 0.5),
                'avg_struggle': float(profile.avg_struggle or 0.5),
                'performance_group': profile.performance_group or 'beginner',
                'total_problems': profile.total_problems or 0
            },
            'behavior': {
                'avg_time': float(profile.avg_time_sec or 60),
                'hint_usage_rate': float(profile.hint_usage_rate or 0.3),
                'multiple_attempts_rate': float(profile.multiple_attempts_rate or 0.2)
            },
            'history': {
                'total_tasks': len(history),
                'recent_scores': recent_scores
            }
        }
    
    def _get_group_info(self, group_id: Optional[int]) -> Dict:
        """Получает информацию о группе студента"""
        if not group_id:
            return {
                'name': 'Не назначен',
                'type': 'unknown',
                'grade_level': None,
                'grade_text': 'класс не указан'
            }
        
        session = self.db_manager.get_session()
        try:
            from database.models import Group
            group = session.query(Group).filter(Group.group_id == group_id).first()
            if group:
                grade_text = self._format_grade_level(group.grade_level, group.type)
                return {
                    'id': group.group_id,
                    'name': group.name,
                    'type': group.type,
                    'grade_level': group.grade_level,
                    'grade_text': grade_text
                }
            return {
                'name': 'Не найден',
                'type': 'unknown',
                'grade_level': None,
                'grade_text': 'класс не указан'
            }
        finally:
            session.close()
    
    def _format_grade_level(self, grade_level: Optional[int], group_type: str) -> str:
        """Форматирует класс/курс для отображения в промпте"""
        if not grade_level:
            return "класс не указан"
        
        if group_type == 'university':
            suffix = {1: 'й', 2: 'й', 3: 'й', 4: 'й', 5: 'й', 6: 'й'}.get(grade_level, 'й')
            return f"{grade_level}{suffix} курс университета"
        else:
            suffix = {1: 'й', 2: 'й', 3: 'й', 4: 'й', 5: 'й', 6: 'й',
                      7: 'й', 8: 'й', 9: 'й', 10: 'й', 11: 'й'}.get(grade_level, 'й')
            if grade_level <= 4:
                return f"{grade_level}{suffix} класс (начальная школа)"
            elif grade_level <= 9:
                return f"{grade_level}{suffix} класс (основная школа)"
            else:
                return f"{grade_level}{suffix} класс (старшая школа)"
    
    def get_grade_level_for_prompt(self, student_uuid: str) -> str:
        """Возвращает текстовое представление класса для вставки в промпт"""
        profile = self.get_profile(student_uuid)
        return profile['group']['grade_text']
    
    def get_learning_style(self, profile: Dict) -> str:
        """Определяет стиль обучения на основе профиля"""
        success_rate = profile['academic']['success_rate']
        hint_rate = profile['behavior']['hint_usage_rate']
        struggle = profile['academic']['avg_struggle']
        
        if success_rate > 0.8 and hint_rate < 0.2:
            return "самостоятельный"
        elif hint_rate > 0.5:
            return "нуждается в подробных объяснениях"
        elif struggle > 0.6:
            return "нуждается в упрощении"
        elif success_rate < 0.5:
            return "требует повторения основ"
        else:
            return "уравновешенный"
    
    def _get_default_profile(self) -> Dict:
        """Дефолтный профиль для нового студента"""
        return {
            'uuid': 'new_student',
            'name': 'Новый студент',
            'group': {
                'name': 'Не назначен',
                'type': 'unknown',
                'grade_level': None,
                'grade_text': 'класс не указан'
            },
            'academic': {
                'success_rate': 0.5,
                'avg_mastery': 0.5,
                'avg_struggle': 0.3,
                'performance_group': 'beginner',
                'total_problems': 0
            },
            'behavior': {
                'avg_time': 60,
                'hint_usage_rate': 0.3,
                'multiple_attempts_rate': 0.2
            },
            'history': {
                'total_tasks': 0,
                'recent_scores': []
            }
        }
    
    def get_profile_by_user_id(self, user_id: int) -> Dict:
        """Получает профиль по user_id (удобный метод для интеграции)"""
        profile = self.db_manager.get_user_profile(user_id)
        if profile:
            return self.get_profile(profile.uuid)
        return self._get_default_profile()