import streamlit as st
from database.db_manager import db_manager

def show_history_page(profile):
    """Страница истории заданий"""
    st.title("📜 История заданий")
    
    if not profile:
        st.warning("Профиль не найден")
        return
    
    try:
        uuid = profile.uuid if hasattr(profile, 'uuid') else None
        if not uuid:
            st.warning("UUID профиля не найден")
            return
            
        history = db_manager.get_task_history(uuid, limit=100)
        
        if not history:
            st.info("📭 У вас пока нет выполненных заданий")
            return
        
        st.write(f"**Всего заданий:** {len(history)}")
        
        for i, task in enumerate(history):
            with st.expander(f"📌 Задание #{len(history)-i} - {task['topic']} ({task['created_at'].strftime('%d.%m.%Y')})"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Тема:** {task['topic']}")
                    st.write(f"**Сложность:** {task['difficulty']}")
                    st.write(f"**Время:** {task['time_spent']} сек")
                with col2:
                    score_color = "green" if task['score'] >= 0.7 else "orange" if task['score'] >= 0.5 else "red"
                    st.markdown(f"**Результат:** <span style='color:{score_color}; font-size:20px;'>{int(task['score'] * 100)}%</span>", unsafe_allow_html=True)
                    st.write(f"**Подсказки:** {task['hints_used']}")
                
                task_data = task['task_data']
                if isinstance(task_data, dict) and 'questions' in task_data:
                    st.write("**Вопросы и ответы:**")
                    for q_idx, q in enumerate(task_data['questions'], 1):
                        st.write(f"---")
                        st.write(f"**Вопрос {q_idx}:** {q.get('text', 'Нет текста')}")
                        st.write(f"**Ответ:** {q.get('answer', 'Нет ответа')}")
                        st.write(f"**Объяснение:** {q.get('explanation', 'Нет объяснения')}")
                
    except Exception as e:
        st.error(f"Ошибка загрузки истории: {e}")