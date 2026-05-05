import streamlit as st
from database.db_manager import db_manager
import pandas as pd
import io
from pages.teacher_profile import show_teacher_profile
from pages.teacher_new_task import show_new_task_teacher_page
from pages.teacher_classes import show_classes_page
from pages.teacher_statistics import show_statistics_page

def show_teacher_dashboard():
    """Панель преподавателя"""
    
    # Инициализация состояния страницы
    if 'teacher_page' not in st.session_state:
        st.session_state['teacher_page'] = "Мой профиль"
    
    if 'selected_class' not in st.session_state:
        st.session_state['selected_class'] = None
    
    if 'selected_student' not in st.session_state:
        st.session_state['selected_student'] = None
    
    # Получаем данные пользователя из сессии
    user = st.session_state.get('user')
    if not user:
        st.error("Ошибка: пользователь не найден")
        return
    
    # Получаем данные преподавателя
    teacher_subjects = db_manager.get_teacher_subjects(user['user_id'])
    teacher_classes = db_manager.get_teacher_classes(user['user_id'])
    teacher_students_count = db_manager.get_teacher_students_count(user['user_id'])

    # Получить организацию текущего пользователя
    user_org = db_manager.get_user_organization(user['user_id'])
    is_university = user_org and user_org['org_type'] == 'university'

    # Условные надписи
    group_label = "группы" if is_university else "классы"
    teacher_label = "Преподаватель" if is_university else "Учитель"
    
    # Боковое меню
    with st.sidebar:
        st.markdown(f"### 👋 {user.get('first_name', '')} {user.get('last_name', '')}")
        st.caption(teacher_label)
        st.markdown("---")
        
        # Кнопки навигации
        if st.button("👤 Мой профиль", key="btn_profile", use_container_width=True):
            st.session_state['teacher_page'] = "Мой профиль"
            st.session_state['selected_class'] = None
            st.session_state['selected_student'] = None
        
        if st.button("📝 Новое задание", key="btn_new_task", use_container_width=True):
            st.session_state['teacher_page'] = "Новое задание"
        
        if st.button(f"🏫 Мои {group_label}", key="btn_classes", use_container_width=True):
            st.session_state['teacher_page'] = f"Мои {group_label}"
            st.session_state['selected_class'] = None
            st.session_state['selected_student'] = None

        if st.button("📊 Статистика", key="btn_statistic", use_container_width=True):
            st.session_state['teacher_page'] = "Статистика"
            st.session_state['selected_class'] = None
            st.session_state['selected_student'] = None
        
        st.markdown("---")
        if st.button("🚪 Выйти", key="btn_logout", use_container_width=True):
            for key in ['authenticated', 'user', 'role', 'teacher_page', 'selected_class', 'selected_student']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
    
    # Отображение выбранной страницы
    current_page = st.session_state['teacher_page']
    
    if current_page == "Мой профиль":
        show_teacher_profile(user, teacher_subjects, teacher_classes, teacher_students_count, is_university)
    elif current_page == "Новое задание":
        show_new_task_teacher_page(user, teacher_classes, is_university)
    elif current_page == f"Мои {group_label}":
        show_classes_page(user, teacher_classes, is_university)
    elif current_page == "Статистика":
        show_statistics_page(user, teacher_classes, is_university)