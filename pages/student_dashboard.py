import streamlit as st
from database.db_manager import db_manager
from pages.student_progress import show_progress_page
from pages.student_history import show_history_page
from pages.student_new_task import show_new_task_page

st.markdown("""
    <style>
    [data-testid="stSidebar"] {
        display: block !important;
    }
    </style>
    """, unsafe_allow_html=True)

def show_student_dashboard():
    """Панель ученика"""

    if 'student_page' not in st.session_state:
        st.session_state['student_page'] = "Мой прогресс"

    user = st.session_state.get('user')
    if not user:
        st.error("Ошибка: пользователь не найден")
        return

    try:
        profile = db_manager.get_user_profile(user['user_id'])
        user_org = db_manager.get_user_organization(user['user_id'])
        is_university = user_org and user_org['org_type'] == 'university'
    except Exception as e:
        st.error(f"Ошибка загрузки профиля: {e}")
        profile = None
    
    student_label = "Студент" if is_university else "Ученик"

    with st.sidebar:
        st.markdown(f"### 👋 {user.get('first_name', '')} {user.get('last_name', '')}")
        st.caption(student_label)
        st.markdown("---")

        if st.button("📊 Мой прогресс", key="btn_progress", use_container_width=True):
            st.session_state['student_page'] = "Мой прогресс"
        
        if st.button("📝 Новое задание", key="btn_new_task", use_container_width=True):
            st.session_state['student_page'] = "Новое задание"
        
        if st.button("📜 История заданий", key="btn_history", use_container_width=True):
            st.session_state['student_page'] = "История заданий"
        
        st.markdown("---")
        if st.button("🚪 Выйти", key="btn_logout", use_container_width=True):
            for key in ['authenticated', 'user', 'role', 'student_page']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

    current_page = st.session_state['student_page']
    
    if current_page == "Мой прогресс":
        show_progress_page(profile)
    elif current_page == "Новое задание":
        show_new_task_page(profile)
    elif current_page == "История заданий":
        show_history_page(profile)