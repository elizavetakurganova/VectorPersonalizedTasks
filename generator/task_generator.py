import requests
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
import re

from utils.config import config
from generator.student_profiler import StudentProfiler
from tracker.progress_tracker import ProgressTracker
from utils.json_utils import safe_json_parse, clean_json_response
from generator.prompt_templates import build_task_prompt

logger = logging.getLogger(__name__)

class YandexGPTTaskGenerator:
    """Генератор персонализированных заданий на основе YandexGPT"""
    
    def __init__(self, 
                 profiler: StudentProfiler,
                 tracker: Optional[ProgressTracker] = None,
                 api_key: str = None,
                 folder_id: str = None,
                 model: str = None):
        
        self.profiler = profiler
        self.tracker = tracker
        
        # Настройки API из конфига
        self.api_key = api_key or getattr(config, 'YANDEX_API_KEY', None)
        self.folder_id = folder_id or getattr(config, 'YANDEX_FOLDER_ID', None)
        self.model = model or getattr(config, 'YANDEX_MODEL', 'yandexgpt')
        
        self.api_url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
        
        if not self.api_key or not self.folder_id:
            logger.error("❌ API ключ или Folder ID не указаны! Задайте их в config или .env")
            self.is_configured = False
        else:
            self.headers = {
                'Authorization': f'Api-Key {self.api_key}',
                'Content-Type': 'application/json'
            }
            self.is_configured = True
            logger.info(f"✅ YandexGPT настроен, модель: {self.model}")
    
    def generate_task(self, 
                     student_id: str,   # UUID студента
                     topic: str = None,
                     num_questions: int = 3,
                     difficulty: str = None,
                     temperature: float = 0.7) -> Dict:
        """Генерирует персонализированное задание для студента"""
        
        if not self.is_configured:
            raise ValueError("❌ API ключ не настроен! Проверьте config.YANDEX_API_KEY и YANDEX_FOLDER_ID")

        profile = self.profiler.get_profile(student_id)
        learning_style = self.profiler.get_learning_style(profile)

        progress = None
        if self.tracker:
            progress = self.tracker.get_progress(student_id) 

        if topic is None:
            topic = self._suggest_topic(profile, progress)

        # Если учитель явно задал сложность, используем её
        if difficulty is not None:
            final_difficulty = difficulty
        else:
            final_difficulty = self._determine_difficulty(profile, progress)
   
        prompt = build_task_prompt(
            profile=profile,
            learning_style=learning_style,
            topic=topic,
            difficulty=final_difficulty,
            num_questions=num_questions,
            examples=None,
            progress=progress
        )
        
        try:
            response_text = self._call_api(prompt, temperature)
            cleaned = clean_json_response(response_text)
            task_data = safe_json_parse(cleaned)
            
            if not task_data or 'questions' not in task_data:
                task_data = self._create_fallback_task(topic, num_questions)
            
            task = {
                'student_id': student_id,
                'topic': topic,
                'generated_at': datetime.now().isoformat(),
                'parameters': {
                    'difficulty': final_difficulty,
                    'learning_style': learning_style,
                    'num_questions': num_questions,
                    'model': self.model
                },
                'questions': task_data['questions'],
                'metadata': {
                    'based_on_profile': profile['academic']['performance_group'],
                    'success_rate': profile['academic']['success_rate'],
                    'estimated_time': self._estimate_time(profile, num_questions, difficulty)
                }
            }
            if progress:
                task['progress'] = {
                    'trend': progress.get('trend', 'неизвестно'),
                    'weak_topics': progress.get('weak_topics', [])
                }
            return task
        except Exception as e:
            logger.error(f"❌ Ошибка генерации: {e}")
            return self._create_error_task(student_id, topic, str(e))
    
    def _call_api(self, prompt: str, temperature: float) -> str:
        """Отправляет запрос к YandexGPT и возвращает текст ответа"""
        payload = {
            "modelUri": f"gpt://{self.folder_id}/{self.model}",
            "completionOptions": {
                "stream": False,
                "temperature": temperature,
                "maxTokens": 2000
            },
            "messages": [
                {
                    "role": "system",
                    "text": "Ты — опытный репетитор по математике и точным наукам. Отвечай только в формате JSON."
                },
                {
                    "role": "user",
                    "text": prompt
                }
            ]
        }
        
        response = requests.post(self.api_url, headers=self.headers, json=payload, timeout=30)
        
        if response.status_code != 200:
            raise Exception(f"API Error {response.status_code}: {response.text}")
        
        result = response.json()
        # Извлекаем текст ответа
        try:
            text = result['result']['alternatives'][0]['message']['text']
            return text
        except (KeyError, IndexError) as e:
            raise Exception(f"Не удалось распарсить ответ API: {e}")
    
    def _determine_difficulty(self, profile: Dict, progress: Dict = None) -> str:
        """Определяет сложность на основе успеваемости и тренда"""
        success_rate = profile['academic']['success_rate']
        
        if success_rate > 0.8:
            base = "сложный"
        elif success_rate > 0.6:
            base = "средний"
        elif success_rate > 0.4:
            base = "легкий"
        else:
            base = "очень легкий"
        
        if progress and isinstance(progress, dict):
            trend = progress.get('trend', '')
            avg_score = progress.get('avg_score', 0)
            if isinstance(avg_score, (int, float)):
                if 'растёт' in trend and avg_score > 0.8:
                    if base == "легкий":
                        return "средний"
                    elif base == "средний":
                        return "сложный"
                elif 'падает' in trend or avg_score < 0.5:
                    if base == "сложный":
                        return "средний"
                    elif base == "средний":
                        return "легкий"
                    elif base == "легкий":
                        return "очень легкий"
        return base
    
    def _suggest_topic(self, profile: Dict, progress: Dict = None) -> str:
        """Предлагает тему для задания (слабая тема или дефолтная)"""
        if progress and progress.get('weak_topics'):
            return progress['weak_topics'][0]
        # Список тем по умолчанию – можно расширить или брать из конфига
        default_topics = ['линейные уравнения', 'дроби', 'проценты', 'геометрия']
        return default_topics[0]
    
    def _estimate_time(self, profile: Dict, num_questions: int, difficulty: str) -> int:
        """Оценивает примерное время выполнения задания (в секундах)"""
        base_time = profile['behavior']['avg_time']  # уже число
        factor = {"очень легкий": 0.8, "легкий": 1.0, "средний": 1.3, "сложный": 1.6}
        return int(base_time * num_questions * factor.get(difficulty, 1.0))
    
    def _create_fallback_task(self, topic: str, num_questions: int) -> Dict:
        """Заглушка для генерации простых заданий при сбое API"""
        questions = []
        for i in range(num_questions):
            a = i+1
            b = 10 - (i+1)
            questions.append({
                "text": f"Решите уравнение: {a}x + {b} = 10",
                "explanation": f"Перенесите {b}: {a}x = {10 - b}, x = {(10 - b)/a}",
                "hint": "Соберите все члены с x в левой части, числа перенесите вправо.",
                "answer": str((10 - b)/a)
            })
        return {"questions": questions}
    
    def _create_error_task(self, student_id: str, topic: str, error: str) -> Dict:
        """Задание-заглушка при любой ошибке генерации"""
        return {
            'student_id': student_id,
            'topic': topic,
            'generated_at': datetime.now().isoformat(),
            'parameters': {'difficulty': 'легкий', 'num_questions': 3},
            'questions': [
                {
                    "text": "2x + 3 = 7",
                    "explanation": "2x = 4, x = 2",
                    "hint": "Вычтите 3 из обеих частей",
                    "answer": "2"
                },
                {
                    "text": "3x - 5 = 10",
                    "explanation": "3x = 15, x = 5",
                    "hint": "Прибавьте 5 к обеим частям",
                    "answer": "5"
                },
                {
                    "text": "4x + 7 = 31",
                    "explanation": "4x = 24, x = 6",
                    "hint": "Вычтите 7, затем разделите на 4",
                    "answer": "6"
                }
            ],
            'metadata': {'error': error}
        }