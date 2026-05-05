from werkzeug.security import generate_password_hash, check_password_hash
from database.db_manager import db_manager
import logging

logger = logging.getLogger(__name__)

def hash_password(password: str) -> str:
    """Хэширование пароля с использованием Werkzeug"""
    return generate_password_hash(password, method='scrypt')

def verify_password(password_hash: str, password: str) -> bool:
    """Проверка пароля"""
    return check_password_hash(password_hash, password)

def authenticate_user(login: str, password: str):
    """Аутентификация пользователя"""
    try:
        user = db_manager.get_user_by_login(login)
        
        if not user:
            logger.warning(f"Попытка входа с несуществующим логином: {login}")
            return None
        
        if verify_password(user.password_hash, password):
            logger.info(f"Успешный вход пользователя: {login}")
            return {
                'user_id': user.user_id,
                'login': user.login,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'role_id': user.role_id,
                'org_id': user.org_id
            }
        else:
            logger.warning(f"Неверный пароль для пользователя: {login}")
            return None
            
    except Exception as e:
        logger.error(f"Ошибка аутентификации: {e}")
        return None

def get_user_role_name(role_id: int):
    """Получение названия роли по ID"""
    role_map = {
        1: 'admin',
        2: 'teacher', 
        3: 'student',
        4: 'org'
    }
    return role_map.get(role_id, 'unknown')