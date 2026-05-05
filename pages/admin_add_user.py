import streamlit as st
from database.db_manager import db_manager
from auth.auth_manager import hash_password

def show_add_user(org_id, org_type):
    # Определяем терминологию в зависимости от типа организации
    is_university = (org_type == 'university')
    
    if is_university:
        teacher_label = "Преподаватель"
        student_label = "Студент"
        role_options = [teacher_label, student_label]
    else:
        teacher_label = "Учитель"
        student_label = "Ученик"
        role_options = [teacher_label, student_label]
    
    # Инициализация счетчика формы
    if 'add_form_counter' not in st.session_state:
        st.session_state.add_form_counter = 0
    
    form_key = f"add_user_{st.session_state.add_form_counter}"
    
    with st.form(key=form_key):
        st.subheader(f"Добавление нового пользователя")
        
        role = st.selectbox("Роль", options=role_options, key=f"role_{form_key}")
        first_name = st.text_input("Имя", key=f"first_{form_key}")
        last_name = st.text_input("Фамилия", key=f"last_{form_key}")
        
        submitted = st.form_submit_button("Добавить")
        
        if submitted:
            if not first_name.strip() or not last_name.strip():
                st.error("Заполните имя и фамилию.")
            else:
                if is_university:
                    role_id = 2 if role == "Преподаватель" else 3
                else:
                    role_id = 2 if role == "Учитель" else 3
                
                # Определяем префикс для пароля
                role_prefix = "teacher" if role_id == 2 else "student"
                
                # Генерируем логин и пароль
                login = db_manager.generate_unique_login(first_name, last_name)
                raw_password = db_manager.generate_random_password(role_prefix)
                password_hash = hash_password(raw_password)
                
                try:
                    new_user = db_manager.add_user(
                        org_id=org_id,
                        role_id=role_id,
                        login=login,
                        password_hash=password_hash,
                        first_name=first_name.strip(),
                        last_name=last_name.strip()
                    )
                    
                    # Сохраняем сообщение об успехе
                    st.session_state.temp_message = (
                        f"✅ {role} {first_name} {last_name} добавлен!\n"
                        f"Логин: {login}\n"
                        f"Пароль: {raw_password}"
                    )
                    st.session_state.admin_mode = None
                    st.session_state.add_form_counter += 1
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"Ошибка при добавлении {role.lower()}: {e}")
    
    if st.button("Назад к списку"):
        st.session_state.admin_mode = None
        st.rerun()