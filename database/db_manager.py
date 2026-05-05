import random
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy import func
from werkzeug.security import generate_password_hash
from utils.config import config
from database.models import User, Role, Organization, Group, UserProfile, TaskHistory, Teaching
import logging

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self.engine = create_engine(config.DATABASE_URL)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
    
    def get_session(self):
        return self.Session()
    
    def execute_query(self, query, params=None):
        """Выполнение raw SQL запроса"""
        with self.engine.connect() as conn:
            result = conn.execute(text(query), params or {})
            conn.commit()
            return result

    def get_user_by_id(self, user_id):
        """Получение пользователя по ID"""
        session = self.get_session()
        try:
            user = session.query(User).filter(User.user_id == user_id).first()
            return user
        finally:
            session.close()
    
    def get_user_by_login(self, login):
        """Получение пользователя по логину"""
        session = self.get_session()
        try:
            user = session.query(User).filter(User.login == login).first()
            return user
        finally:
            session.close()

    def get_user_profile(self, user_id):
        """Получение профиля студента по ID пользователя"""
        session = self.get_session()
        try:
            from database.models import UserProfile
            profile = session.query(UserProfile).filter(
                UserProfile.user_id == user_id
            ).first()
            return profile
        finally:
            session.close()

    def get_user_profile_by_uuid(self, uuid):
        """Получение профиля пользователя по uuid"""
        session = self.get_session()
        try:
            profile = session.query(UserProfile).filter(UserProfile.uuid == uuid).first()
            return profile
        finally:
            session.close()

    def get_user_organization(self, user_id):
        """Получить информацию об организации пользователя по его ID"""
        session = self.get_session()
        try:
            from database.models import User, Organization
            org = session.query(Organization).join(User, User.org_id == Organization.org_id).filter(User.user_id == user_id).first()
            if org:
                return {
                    'org_id': org.org_id,
                    'org_type': org.org_type,
                    'org_name': org.org_name
                }
            return None
        except Exception as e:
            logger.error(f"Ошибка получения организации пользователя {user_id}: {e}")
            return None
        finally:
            session.close()

    def is_university_user(self, user_id):
        """Проверить, принадлежит ли пользователь к университету"""
        org = self.get_user_organization(user_id)
        return org and org['org_type'] == 'university'

    def get_teacher_subjects(self, teacher_id):
        """Получить список предметов, которые ведет учитель"""
        session = self.get_session()
        try:
            from database.models import Teaching
            
            subjects = session.query(Teaching.subject).filter(
                Teaching.teacher_id == teacher_id
            ).distinct().all()
            
            return [s[0] for s in subjects] if subjects else []
        except Exception as e:
            logger.error(f"Ошибка получения предметов учителя {teacher_id}: {e}")
            return []
        finally:
            session.close()

    def get_teacher_subjects_for_student(self, teacher_id, student_user_id):
        """Возвращает список предметов, которые учитель ведёт в группе, где состоит ученик."""
        session = self.get_session()
        try:
            # 1. Находим группу ученика через его профиль
            profile = session.query(UserProfile).filter(UserProfile.user_id == student_user_id).first()
            if not profile or not profile.group_id:
                return []
            group_id = profile.group_id

            # 2. Находим все Teaching для этого учителя и этой группы
            teachings = session.query(Teaching).filter(
                Teaching.teacher_id == teacher_id,
                Teaching.group_id == group_id
            ).all()

            subjects = list(set(t.subject for t in teachings if t.subject))
            return subjects
        except Exception as e:
            logger.error(f"Ошибка get_teacher_subjects_for_student: {e}")
            return []
        finally:
            session.close()

    def get_teacher_students_count(self, teacher_id):
        """Получить общее количество учеников у учителя (по всем его группам)"""
        session = self.get_session()
        try:
            from database.models import Teaching, Group, UserProfile
            from sqlalchemy import func
            
            count = session.query(func.count(UserProfile.user_id.distinct())).join(
                Group, UserProfile.group_id == Group.group_id
            ).join(
                Teaching, Group.group_id == Teaching.group_id
            ).filter(
                Teaching.teacher_id == teacher_id
            ).scalar()
            
            return count or 0
        except Exception as e:
            logger.error(f"Ошибка получения количества учеников учителя {teacher_id}: {e}")
            return 0
        finally:
            session.close()

    def get_students_by_teacher(self, teacher_id):
        """Получение списка учеников для учителя"""
        session = self.get_session()
        try:
            # Получаем группы учителя
            teacher_groups = session.query(Teaching.group_id).filter(Teaching.teacher_id == teacher_id).subquery()
            
            # Получаем учеников из этих групп
            students = session.query(User).join(UserProfile).filter(
                UserProfile.group_id.in_(teacher_groups),
                User.role_id == 3
            ).distinct().all()
            return students
        except Exception as e:
            logger.error(f"Ошибка получения учеников: {e}")
            return []
        finally:
            session.close()

    def get_class_students(self, class_name, teacher_id):
        """Получение списка учеников класса с полной статистикой"""
        session = self.get_session()
        try:
            students = session.query(
                User.user_id,
                UserProfile.uuid,
                User.first_name,
                User.last_name,
                UserProfile.success_rate,
                UserProfile.total_problems,
                UserProfile.performance_group,
                UserProfile.avg_time_sec,
                UserProfile.hint_usage_rate,
                UserProfile.avg_mastery,
                UserProfile.avg_struggle
            ).join(
                UserProfile, User.user_id == UserProfile.user_id
            ).join(
                Group, UserProfile.group_id == Group.group_id
            ).filter(
                Group.name == class_name,
                Group.teacher_id == teacher_id,
                User.role_id == 3
            ).all()
            
            result = []
            for student in students:
                result.append({
                    'id': student.user_id,
                    'uuid': student.uuid,
                    'name': f"{student.first_name} {student.last_name}",
                    'success_rate': int(student.success_rate * 100) if student.success_rate else 0,
                    'total_problems': student.total_problems if student.total_problems else 0,
                    'performance_group': student.performance_group if student.performance_group else 'beginner',
                    'avg_time': int(student.avg_time_sec) if student.avg_time_sec else 0,
                    'hint_rate': int(student.hint_usage_rate * 100) if student.hint_usage_rate else 0,
                    'mastery': int(student.avg_mastery * 100) if student.avg_mastery else 0,
                    'struggle': int(student.avg_struggle * 100) if student.avg_struggle else 0
                })
            
            return result
        except Exception as e:
            logger.error(f"Ошибка получения учеников класса {class_name}: {e}")
            return []
        finally:
            session.close()

    def get_teacher_classes(self, teacher_id):
        """Получение всех групп преподавателя с полной информацией"""
        session = self.get_session()
        try:
            classes = session.query(
                Group.group_id,
                Group.name,
                Teaching.subject,
                func.count(UserProfile.user_id).label('students_count')
            ).join(
                Teaching, Group.group_id == Teaching.group_id
            ).outerjoin(
                UserProfile, Group.group_id == UserProfile.group_id
            ).filter(
                Teaching.teacher_id == teacher_id
            ).group_by(
                Group.group_id, Group.name, Teaching.subject
            ).all()
            
            result = []
            for cls in classes:
                # Вычисляем среднюю успеваемость по классу
                avg_success = session.query(
                    func.avg(UserProfile.success_rate)
                ).join(
                    Group, UserProfile.group_id == Group.group_id
                ).filter(
                    Group.group_id == cls.group_id
                ).scalar()
                
                result.append({
                    'id': cls.group_id,
                    'name': cls.name,
                    'subject': cls.subject,
                    'students_count': cls.students_count or 0,
                    'avg_success_rate': int(avg_success * 100) if avg_success else 0
                })
            
            return result
        except Exception as e:
            logger.error(f"Ошибка получения групп преподавателя {teacher_id}: {e}")
            return []
        finally:
            session.close()
    
    def get_organization_groups(self, org_id):
        """Получение всех групп (классов) организации"""
        session = self.get_session()
        try:
            from database.models import Group
            
            groups = session.query(Group).filter(Group.org_id == org_id).all()
            
            result = []
            for group in groups:
                result.append({
                    'id': group.group_id,
                    'name': group.name,
                    'type': group.type,
                    'grade_level': group.grade_level,
                    'teacher_id': group.teacher_id
                })
            return result
        except Exception as e:
            logger.error(f"Ошибка получения групп организации {org_id}: {e}")
            return []
        finally:
            session.close()

    def get_organization_users(self, org_id, role_id=None):
        """Получение всех пользователей организации.
        
        Args:
            org_id: ID организации
            role_id: опционально, фильтр по роли (1-админ,2-учитель,3-ученик,4-сотрудник)
        """
        session = self.get_session()
        try:
            from database.models import User, Role
            
            query = session.query(
                User.user_id,
                User.login,
                User.first_name,
                User.last_name,
                Role.role_name,
                User.role_id
            ).join(Role, User.role_id == Role.role_id).filter(User.org_id == org_id)
            
            if role_id is not None:
                query = query.filter(User.role_id == role_id)
            
            users = query.all()
            
            result = []
            for user in users:
                result.append({
                    'id': user.user_id,
                    'login': user.login,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'role': user.role_name,
                    'role_id': user.role_id
                })
            return result
        except Exception as e:
            logger.error(f"Ошибка получения пользователей организации {org_id}: {e}")
            return []
        finally:
            session.close()

    def get_all_students(self):
        """Получение всех учеников"""
        session = self.get_session()
        try:
            students = session.query(User).filter(User.role_id == 3).all()
            return students
        finally:
            session.close()
    
    def save_task_result(self, student_uuid, task_data, score, time_spent, hints_used):
        """Сохранение результата задания"""
        session = self.get_session()
        try:
            task = TaskHistory(
                student_id=student_uuid,
                task_data=task_data,
                topic=task_data.get('topic', 'unknown'),
                difficulty=task_data.get('difficulty', 'medium'),
                score=score,
                time_spent=time_spent,
                hints_used=hints_used
            )
            session.add(task)
            session.commit()
            logger.info(f"Задание сохранено для студента {student_uuid}, score={score}")

            self.update_user_profile(student_uuid)
            
            return task.id
        except Exception as e:
            session.rollback()
            logger.error(f"Ошибка сохранения результата: {e}")
            raise
        finally:
            session.close()
                    
    def update_user_profile(self, student_uuid):
        """Обновление профиля пользователя на основе истории заданий"""
        session = self.get_session()
        try:
            tasks = session.query(TaskHistory).filter(TaskHistory.student_id == student_uuid).all()
            
            if not tasks:
                logger.warning(f"Нет заданий для студента {student_uuid}")
                return

            total_problems = len(tasks)
            avg_score = sum(t.score for t in tasks) / total_problems
            avg_time = sum(t.time_spent for t in tasks) / total_problems
            hint_rate = sum(1 for t in tasks if t.hints_used > 0) / total_problems
            multiple_attempts_rate = 0.0 
            
            if avg_score >= 0.85:
                performance_group = 'advanced'
            elif avg_score >= 0.7:
                performance_group = 'proficient'
            elif avg_score >= 0.5:
                performance_group = 'developing'
            else:
                performance_group = 'beginner'
            
            profile = session.query(UserProfile).filter(UserProfile.uuid == student_uuid).first()
            if profile:
                profile.success_rate = avg_score
                profile.total_problems = total_problems
                profile.avg_time_sec = avg_time
                profile.hint_usage_rate = hint_rate
                profile.multiple_attempts_rate = multiple_attempts_rate
                profile.performance_group = performance_group
                profile.avg_mastery = avg_score * 0.7 + (1 - hint_rate) * 0.3
                profile.avg_struggle = (1 - avg_score) * 0.8 + hint_rate * 0.2
                session.commit()
                logger.info(f"Профиль обновлен для студента {student_uuid}: {performance_group}, score={avg_score:.2f}")
            else:
                logger.error(f"Профиль не найден для студента {student_uuid}")
                
        except Exception as e:
            session.rollback()
            logger.error(f"Ошибка обновления профиля: {e}")
            raise
        finally:
            session.close()
            
    def get_task_history(self, student_uuid, limit=50):
        """Получение истории заданий студента"""
        session = self.get_session()
        try:
            from database.models import TaskHistory
            history = session.query(TaskHistory).filter(
                TaskHistory.student_id == student_uuid
            ).order_by(TaskHistory.created_at.desc()).limit(limit).all()
            
            return [{
                'created_at': h.created_at,
                'topic': h.topic,
                'difficulty': h.difficulty,
                'score': h.score,
                'time_spent': h.time_spent,
                'hints_used': h.hints_used,
                'task_data': h.task_data
            } for h in history]
        finally:
            session.close()
    
    def get_student_history(self, student_uuid, limit=100):
        """Алиас для get_task_history (нужен для ProgressTracker)"""
        return self.get_task_history(student_uuid, limit)

    def get_all_users(self):
        """Получение всех пользователей (для админа)"""
        session = self.get_session()
        try:
            users = session.query(User).all()
            return users
        finally:
            session.close()
    
    def add_user(self, org_id, role_id, login, password_hash, first_name, last_name):
        """Добавление нового пользователя"""
        session = self.get_session()
        try:
            user = User(
                org_id=org_id,
                role_id=role_id,
                login=login,
                password_hash=password_hash,
                first_name=first_name,
                last_name=last_name
            )
            session.add(user)
            session.commit()
            logger.info(f"Пользователь {login} добавлен")
            return user
        except Exception as e:
            session.rollback()
            logger.error(f"Ошибка добавления пользователя: {e}")
            raise
        finally:
            session.close()

    def generate_unique_login(self, first_name: str, last_name: str) -> str:
        """Генерация уникального логина из имени и фамилии (транслит + цифры при коллизии)"""
        # Простая транслитерация русских букв
        def translit(text: str) -> str:
            mapping = {
                'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
                'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
                'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
                'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
                'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
            }
            result = []
            for ch in text.lower():
                if ch in mapping:
                    result.append(mapping[ch])
                elif ch.isalpha() and ch not in mapping:
                    result.append(ch)
            return ''.join(result)

        base_login = translit(first_name) + translit(last_name)
        if not base_login:
            base_login = "user"

        session = self.get_session()
        try:
            # Проверка уникальности логина глобально
            existing = session.query(User).filter(User.login == base_login).first()
            if not existing:
                return base_login
            counter = 1
            while True:
                test_login = f"{base_login}{counter}"
                if not session.query(User).filter(User.login == test_login).first():
                    return test_login
                counter += 1
        finally:
            session.close()

    def generate_random_password(self, role_type: str) -> str:
        """Генерация пароля вида student12345 или teacher12345"""
        num = random.randint(10000, 99999)
        return f"{role_type}{num}"

    def change_user_password(self, user_id: int, new_password: str) -> bool:
        """Смена пароля пользователя (хэширует и сохраняет)"""
        session = self.get_session()
        try:
            user = session.query(User).filter(User.user_id == user_id).first()
            if user:
                user.password_hash = generate_password_hash(new_password, method='scrypt')
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            logger.error(f"Ошибка смены пароля user_id={user_id}: {e}")
            return False
        finally:
            session.close()

    def get_organization_type(self, org_id):
        """Получить тип организации по id (school/university)."""
        session = self.get_session()
        try:
            org = session.query(Organization).filter(Organization.org_id == org_id).first()
            return org.org_type if org else "school"
        finally:
            session.close()

    def get_or_create_group(self, org_id, group_name, group_type="class", grade_level=None, teacher_id=None):
        """Найти группу по имени и организации, если нет — создать."""
        session = self.get_session()
        try:
            group = session.query(Group).filter(
                Group.org_id == org_id,
                Group.name == group_name
            ).first()
            if group:
                return group.group_id
            new_group = Group(
                org_id=org_id,
                name=group_name,
                type=group_type,
                grade_level=grade_level,
                teacher_id=teacher_id
            )
            session.add(new_group)
            session.commit()
            return new_group.group_id
        except Exception as e:
            session.rollback()
            logger.error(f"Ошибка get_or_create_group: {e}")
            raise
        finally:
            session.close()

    def _fix_teaching_sequence(self):
        """Синхронизирует последовательность teaching_id_seq с максимальным ID в таблице"""
        with self.engine.connect() as conn:
            conn.execute(text("SELECT setval('teaching_id_seq', (SELECT COALESCE(MAX(id), 0) FROM teaching))"))
            conn.commit()

    def add_teaching(self, teacher_id: int, group_id: int, subject: str) -> bool:
        """Добавление записи о преподавании (связь учитель-группа-предмет)"""
        session = self.get_session()
        try:
            # Проверяем, существует ли уже такая запись
            existing = session.query(Teaching).filter(
                Teaching.teacher_id == teacher_id,
                Teaching.group_id == group_id,
                Teaching.subject == subject
            ).first()
            
            if existing:
                logger.warning(f"Запись о преподавании уже существует: учитель {teacher_id}, группа {group_id}, предмет {subject}")
                return False
            
            teaching = Teaching(
                teacher_id=teacher_id,
                group_id=group_id,
                subject=subject
            )
            session.add(teaching)
            session.commit()
            
            # Синхронизируем последовательность после добавления
            self._fix_teaching_sequence()
            
            logger.info(f"Добавлено преподавание: учитель {teacher_id}, группа {group_id}, предмет {subject}")
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"Ошибка добавления преподавания: {e}")
            return False
        finally:
            session.close()

    def remove_teaching(self, teaching_id: int) -> bool:
        """Удаление записи о преподавании по ID"""
        session = self.get_session()
        try:
            teaching = session.query(Teaching).filter(Teaching.id == teaching_id).first()
            if not teaching:
                logger.warning(f"Запись о преподавании с ID {teaching_id} не найдена")
                return False
            
            session.delete(teaching)
            session.commit()
            logger.info(f"Удалена запись о преподавании с ID {teaching_id}")
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"Ошибка удаления преподавания: {e}")
            return False
        finally:
            session.close()

    def get_teacher_teaching(self, teacher_id):
        """Получить все записи о преподавании учителя с названиями групп."""
        session = self.get_session()
        try:
            teachings = session.query(Teaching).filter(Teaching.teacher_id == teacher_id).all()
            result = []
            for t in teachings:
                group_name = t.group.name if t.group else None
                result.append({
                    'id': t.id,
                    'group_id': t.group_id,
                    'group_name': group_name,
                    'subject': t.subject
                })
            return result
        finally:
            session.close()

    def set_student_group(self, user_id, group_id):
        """Установить group_id в профиле студента (user_profiles)."""
        session = self.get_session()
        try:
            profile = session.query(UserProfile).filter(UserProfile.user_id == user_id).first()
            if not profile:
                logger.warning(f"Профиль студента {user_id} не найден")
                return False
            profile.group_id = group_id
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"Ошибка set_student_group: {e}")
            return False
        finally:
            session.close()

    def get_student_group(self, user_id):
        """Получить объект Group студента (или None)."""
        session = self.get_session()
        try:
            profile = session.query(UserProfile).filter(UserProfile.user_id == user_id).first()
            if profile and profile.group_id:
                return session.query(Group).filter(Group.group_id == profile.group_id).first()
            return None
        finally:
            session.close()

    # ---------- Методы для панели сотрудника организации ----------
    def get_organization_groups_with_stats(self, org_id):
        """Получить все группы организации с количеством учеников и средней успеваемостью."""
        session = self.get_session()
        try:
            result = session.query(
                Group.group_id,
                Group.name,
                Group.type,
                func.count(UserProfile.user_id).label('students_count'),
                func.avg(UserProfile.success_rate).label('avg_success_rate')
            ).outerjoin(UserProfile, Group.group_id == UserProfile.group_id)\
            .filter(Group.org_id == org_id)\
            .group_by(Group.group_id, Group.name, Group.type)\
            .all()

            groups = []
            for row in result:
                groups.append({
                    'id': row.group_id,
                    'name': row.name,
                    'type': row.type,
                    'students_count': row.students_count or 0,
                    'avg_success_rate': int((row.avg_success_rate or 0) * 100)  # в процентах
                })
            return groups
        except Exception as e:
            logger.error(f"Ошибка получения групп организации {org_id}: {e}")
            return []
        finally:
            session.close()

    def get_group_students_details(self, group_id):
        """Получить список учеников группы с их профилями (для сотрудника)."""
        session = self.get_session()
        try:
            students = session.query(
                User.user_id,
                User.first_name,
                User.last_name,
                UserProfile.success_rate,
                UserProfile.total_problems,
                UserProfile.performance_group,
                UserProfile.avg_time_sec,
                UserProfile.hint_usage_rate,
                UserProfile.avg_mastery,
                UserProfile.avg_struggle
            ).join(UserProfile, User.user_id == UserProfile.user_id)\
            .filter(UserProfile.group_id == group_id, User.role_id == 3)\
            .all()

            result = []
            for s in students:
                result.append({
                    'id': s.user_id,
                    'name': f"{s.first_name} {s.last_name}",
                    'success_rate': int(s.success_rate * 100) if s.success_rate else 0,
                    'total_problems': s.total_problems or 0,
                    'performance_group': s.performance_group or 'beginner',
                    'avg_time': int(s.avg_time_sec) if s.avg_time_sec else 0,
                    'hint_rate': int(s.hint_usage_rate * 100) if s.hint_usage_rate else 0,
                    'mastery': int(s.avg_mastery * 100) if s.avg_mastery else 0,
                    'struggle': int(s.avg_struggle * 100) if s.avg_struggle else 0
                })
            return result
        except Exception as e:
            logger.error(f"Ошибка получения учеников группы {group_id}: {e}")
            return []
        finally:
            session.close()

db_manager = DatabaseManager()