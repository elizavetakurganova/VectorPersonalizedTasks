"""
ETL процесс для загрузки данных в PostgreSQL
"""
import sys
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import re

sys.path.append(str(Path(__file__).parent.parent))

from database.models import Base
from database.db_manager import db_manager
from utils.config import config
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
db = Base

class DataValidator:
    """Класс для валидации данных"""
    
    @staticmethod
    def validate_uuid(uuid_value: str) -> bool:
        """Проверка корректности UUID"""
        if pd.isna(uuid_value) or not uuid_value:
            return False
        uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        return bool(re.match(uuid_pattern, str(uuid_value), re.IGNORECASE))
    
    @staticmethod
    def validate_rate(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
        """Валидация и нормализация процентных значений"""
        if pd.isna(value):
            return 0.5 
        try:
            value = float(value)
            return max(min_val, min(value, max_val))
        except (ValueError, TypeError):
            return 0.5
    
    @staticmethod
    def validate_int(value, default: int = 0, min_val: int = 0) -> int:
        """Валидация целочисленных значений"""
        if pd.isna(value):
            return default
        try:
            value = int(value)
            return max(min_val, value)
        except (ValueError, TypeError):
            return default
    
    @staticmethod
    def validate_performance_group(success_rate: float) -> str:
        """Определение группы успеваемости на основе success_rate"""
        if success_rate >= 0.8:
            return 'excellent'
        elif success_rate >= 0.6:
            return 'advanced'
        elif success_rate >= 0.4:
            return 'developing'
        elif success_rate >= 0.2:
            return 'beginner'
        else:
            return 'struggling'


class DataTransformer:
    """Класс для трансформации данных"""
    
    def __init__(self):
        self.validation_stats = {
            'total_rows': 0,
            'valid_rows': 0,
            'invalid_rows': 0,
            'fixed_missing': 0,
            'fixed_outliers': 0
        }
    
    def transform_users_data(self, df: pd.DataFrame) -> Tuple[List[Dict], Dict]:
        """
        Трансформация данных пользователей
        Возвращает: (список профилей, статистика трансформации)
        """
        profiles = []
        stats = self.validation_stats.copy()
        stats['total_rows'] = len(df)
        
        for idx, row in df.iterrows():
            try:
                # Проверка UUID
                uuid = row.get('uuid')
                if not DataValidator.validate_uuid(uuid):
                    stats['invalid_rows'] += 1
                    logger.warning(f"Строка {idx}: неверный UUID - {uuid}")
                    continue
   
                success_rate = DataValidator.validate_rate(row.get('success_rate', 0.5))
                avg_mastery = DataValidator.validate_rate(row.get('avg_mastery', 0.5))
                avg_struggle = DataValidator.validate_rate(row.get('avg_struggle', 0.3))

                if avg_mastery + avg_struggle > 1.1: 
                    stats['fixed_outliers'] += 1
                    total = avg_mastery + avg_struggle
                    avg_mastery = avg_mastery / total
                    avg_struggle = avg_struggle / total
                    logger.debug(f"Строка {idx}: нормализованы mastery+struggle")
                
                total_problems = DataValidator.validate_int(row.get('total_problems', 0))
                
                # Определение группы успеваемости (если не указана или некорректна)
                performance_group = row.get('performance_group', '')
                valid_groups = ['excellent', 'advanced', 'developing', 'beginner', 'struggling']
                
                if pd.isna(performance_group) or performance_group not in valid_groups:
                    performance_group = DataValidator.validate_performance_group(success_rate)
                    stats['fixed_missing'] += 1
                
                # Обработка пропусков в других полях
                hint_usage_rate = DataValidator.validate_rate(row.get('hint_usage_rate', 0.3))
                multiple_attempts_rate = DataValidator.validate_rate(row.get('multiple_attempts_rate', 0.2))
                avg_time_sec = DataValidator.validate_int(row.get('avg_time_sec', 120), min_val=1)
                
                profile = {
                    'uuid': str(uuid),
                    'success_rate': success_rate,
                    'avg_mastery': avg_mastery,
                    'avg_struggle': avg_struggle,
                    'total_problems': total_problems,
                    'performance_group': performance_group,
                    'hint_usage_rate': hint_usage_rate,
                    'multiple_attempts_rate': multiple_attempts_rate,
                    'avg_time_sec': avg_time_sec
                }
                
                profiles.append(profile)
                stats['valid_rows'] += 1
                
            except Exception as e:
                stats['invalid_rows'] += 1
                logger.error(f"Ошибка обработки строки {idx}: {e}")
                continue
        
        return profiles, stats
    
    def _calculate_learning_efficiency(self, success_rate: float, 
                                       avg_time_sec: int, 
                                       hint_usage_rate: float) -> float:
        """
        Расчет эффективности обучения
        Формула: успеваемость * (1 - время/макс_время) * (1 - использование_подсказок)
        """
        max_time = 600  # 10 минут максимальное время
        time_factor = max(0, 1 - (avg_time_sec / max_time))
        hint_factor = 1 - hint_usage_rate
        return round(success_rate * time_factor * hint_factor, 3)
    
    def _determine_risk_level(self, success_rate: float, 
                              avg_struggle: float, 
                              multiple_attempts_rate: float) -> str:
        """Определение уровня риска отставания"""
        risk_score = (1 - success_rate) * 0.4 + avg_struggle * 0.4 + multiple_attempts_rate * 0.2
        
        if risk_score < 0.3:
            return 'low'
        elif risk_score < 0.6:
            return 'medium'
        else:
            return 'high'


class ETLLoader:
    """Класс для загрузки данных в БД"""
    
    def __init__(self):
        self.load_stats = {
            'inserted': 0,
            'updated': 0,
            'errors': 0
        }
    
    def load_users(self, profiles: List[Dict]) -> Dict:
        """
        Загрузка профилей пользователей в БД с обработкой конфликтов
        """
        try:
            db.connect()
            
            for profile in profiles:
                try:
                    with db.cursor() as cur:
                        cur.execute(
                            "SELECT uuid FROM user_profiles WHERE uuid = %s",
                            (profile['uuid'],)
                        )
                        exists = cur.fetchone()
                    
                    if exists:
                        self._update_user(profile)
                        self.load_stats['updated'] += 1
                    else:
                        self._insert_user(profile)
                        self.load_stats['inserted'] += 1
                    
                except Exception as e:
                    self.load_stats['errors'] += 1
                    logger.error(f"Ошибка загрузки пользователя {profile['uuid']}: {e}")
                    
        except Exception as e:
            logger.error(f"Ошибка подключения к БД: {e}")
        finally:
            db.disconnect()
        
        return self.load_stats
    
    def _insert_user(self, profile: Dict):
        """Вставка нового пользователя"""
        with db.cursor() as cur:
            cur.execute("""
                INSERT INTO user_profiles (
                    uuid, success_rate, avg_mastery, avg_struggle, 
                    total_problems, performance_group, hint_usage_rate,
                    multiple_attempts_rate, avg_time_sec, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                profile['uuid'], profile['success_rate'], profile['avg_mastery'],
                profile['avg_struggle'], profile['total_problems'], profile['performance_group'],
                profile['hint_usage_rate'], profile['multiple_attempts_rate'],
                profile['avg_time_sec'], datetime.now()
            ))
    
    def _update_user(self, profile: Dict):
        """Обновление существующего пользователя"""
        with db.cursor() as cur:
            cur.execute("""
                UPDATE user_profiles 
                SET success_rate = %s, avg_mastery = %s, avg_struggle = %s,
                    total_problems = %s, performance_group = %s, hint_usage_rate = %s,
                    multiple_attempts_rate = %s, avg_time_sec = %s, updated_at = %s
                WHERE uuid = %s
            """, (
                profile['success_rate'], profile['avg_mastery'], profile['avg_struggle'],
                profile['total_problems'], profile['performance_group'], profile['hint_usage_rate'],
                profile['multiple_attempts_rate'], profile['avg_time_sec'], datetime.now(),
                profile['uuid']
            ))


class ETLPipeline:
    """Основной ETL пайплайн"""
    
    def __init__(self):
        self.extractor = None
        self.transformer = DataTransformer()
        self.loader = ETLLoader()
    
    def run(self) -> Dict:
        """
        Запуск ETL процесса
        
        Returns:
            Dict: Статистика выполнения ETL
        """
        logger.info("="*60)
        logger.info("🚀 ЗАПУСК ETL ПРОЦЕССА")
        logger.info("="*60)
        
        # STEP 1: EXTRACT - Извлечение данных
        logger.info("\n📥 STEP 1: EXTRACT - Загрузка данных из CSV")
        csv_path = config.USER_PROFILES_PATH
        
        if not Path(csv_path).exists():
            logger.error(f"❌ Файл не найден: {csv_path}")
            return {'error': 'CSV file not found'}
        
        try:
            df = pd.read_csv(csv_path)
            logger.info(f"✓ Загружено {len(df)} записей из {csv_path}")
            
            logger.info(f"  Столбцы: {list(df.columns)}")
            logger.info(f"  Пропуски: {df.isnull().sum().to_dict()}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка извлечения данных: {e}")
            return {'error': str(e)}
        
        # STEP 2: TRANSFORM - Трансформация данных
        logger.info("\n🔄 STEP 2: TRANSFORM - Обработка и подготовка данных")

        required_columns = ['uuid', 'success_rate', 'avg_mastery', 'avg_struggle']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            logger.warning(f"⚠️ Отсутствуют столбцы: {missing_columns}")
            for col in missing_columns:
                if col == 'uuid':
                    logger.error("❌ Столбец 'uuid' обязателен!")
                    return {'error': 'Missing required column: uuid'}
                df[col] = 0.5

        profiles, transform_stats = self.transformer.transform_users_data(df)
        
        logger.info(f"✓ Трансформация завершена:")
        logger.info(f"  - Всего строк: {transform_stats['total_rows']}")
        logger.info(f"  - Валидных: {transform_stats['valid_rows']}")
        logger.info(f"  - Невалидных: {transform_stats['invalid_rows']}")
        logger.info(f"  - Исправлено пропусков: {transform_stats['fixed_missing']}")
        logger.info(f"  - Исправлено выбросов: {transform_stats['fixed_outliers']}")
        
        if transform_stats['valid_rows'] == 0:
            logger.error("❌ Нет валидных данных для загрузки")
            return {'error': 'No valid data to load'}
        
        # STEP 3: LOAD - Загрузка в БД
        logger.info("\nSTEP 3: LOAD - Загрузка в PostgreSQL")
        
        load_stats = self.loader.load_users(profiles)
        
        logger.info(f"✓ Загрузка завершена:")
        logger.info(f"  - Вставлено новых: {load_stats['inserted']}")
        logger.info(f"  - Обновлено: {load_stats['updated']}")
        logger.info(f"  - Ошибок: {load_stats['errors']}")
        
        etl_stats = {
            'extract': {'total_rows': len(df)},
            'transform': transform_stats,
            'load': load_stats,
            'success': load_stats['errors'] == 0
        }
        
        logger.info("\n" + "="*60)
        logger.info("✅ ETL ПРОЦЕСС ЗАВЕРШЕН УСПЕШНО")
        logger.info("="*60)
        
        return etl_stats


def verify_database():
    """Верификация загруженных данных"""
    print("\n" + "="*60)
    print("🔍 ВЕРИФИКАЦИЯ БАЗЫ ДАННЫХ")
    print("="*60)
    
    try:
        db.connect()
        
        with db.cursor() as cur:
            cur.execute("""
                SELECT 
                    COUNT(*) as total_users,
                    ROUND(AVG(success_rate), 3) as avg_success,
                    MIN(success_rate) as min_success,
                    MAX(success_rate) as max_success
                FROM user_profiles
            """)
            stats = cur.fetchone()
            
            print(f"\n📊 Статистика user_profiles:")
            print(f"   • Всего записей: {stats['total_users']}")
            print(f"   • Средняя успеваемость: {stats['avg_success']:.1%}")
            print(f"   • Мин. успеваемость: {stats['min_success']:.1%}")
            print(f"   • Макс. успеваемость: {stats['max_success']:.1%}")
            
            cur.execute("""
                SELECT performance_group, COUNT(*) as cnt
                FROM user_profiles
                GROUP BY performance_group
                ORDER BY cnt DESC
            """)
            groups = cur.fetchall()
            
            print(f"\n📈 Распределение по группам:")
            for group in groups:
                print(f"   • {group['performance_group']}: {group['cnt']} учеников")
            
            cur.execute("""
                SELECT uuid, success_rate, performance_group, 
                       learning_efficiency, risk_level
                FROM user_profiles 
                LIMIT 5
            """)
            samples = cur.fetchall()
            
            print(f"\n👥 Примеры обработанных записей:")
            for sample in samples:
                print(f"   • {sample['uuid'][:20]}... | "
                      f"Успех: {sample['success_rate']:.1%} | "
                      f"Группа: {sample['performance_group']} | "
                      f"Эффект: {sample.get('learning_efficiency', 'N/A')}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка верификации: {e}")
    finally:
        db.disconnect()


if __name__ == "__main__":
    etl = ETLPipeline()
    result = etl.run()
    
    if result.get('success'):
        verify_database()
        print("\n✅ ETL процесс успешно завершен!")
    else:
        print(f"\n❌ ETL процесс завершен с ошибками: {result.get('error')}")
        sys.exit(1)