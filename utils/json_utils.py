import json
import re
import logging

logger = logging.getLogger(__name__)

def clean_json_response(response_text: str) -> str:
    """
    Очищает ответ API от маркеров кода и лишних символов,
    чтобы получить валидную JSON-строку.
    """
    if not response_text:
        return ""

    # Удаляем маркеры markdown кода: ```json ... ``` или ``` ... ```
    code_block_pattern = r"```(?:json)?\s*([\s\S]*?)```"
    match = re.search(code_block_pattern, response_text)
    if match:
        response_text = match.group(1).strip()
    else:
        response_text = response_text.strip()

    # Находим первую '{' и последнюю '}'
    start = response_text.find('{')
    end = response_text.rfind('}')
    if start != -1 and end != -1 and start < end:
        response_text = response_text[start:end+1]

    return response_text

def safe_json_parse(json_str: str, default=None):
    """
    Безопасно парсит JSON-строку.
    Возвращает словарь или default при ошибке.
    """
    if not json_str:
        logger.warning("Попытка парсинга пустой строки JSON")
        return default

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка парсинга JSON: {e}\nСтрока: {json_str[:200]}...")
        return default