import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.models import init_db

def main():
    try:
        init_db()
        print("   ✅ Таблицы созданы/проверены")
    except Exception as e:
        print(f"   ❌ Ошибка при создании таблиц: {e}")
        return

if __name__ == "__main__":
    main()