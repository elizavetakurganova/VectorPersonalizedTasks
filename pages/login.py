import streamlit as st
from auth.auth_manager import authenticate_user, get_user_role_name
from database.db_manager import db_manager

def show_login_page():
    """Страница входа в систему"""
    
    # Центрируем форму входа
    st.markdown("""
        <style>
        .login-container {
            max-width: 400px;
            margin: 0 auto;
            padding: 2rem;
            border-radius: 10px;
            background: #f9f9f9;
        }
        </style>
    """, unsafe_allow_html=True)

    st.image("images/my_logo-no-bg.png", width=300)
    st.markdown("### Вход в систему")
    
    # Форма входа
    with st.form("login_form"):
        login = st.text_input("Логин", placeholder="Введите ваш логин")
        password = st.text_input("Пароль", type="password", placeholder="Введите пароль")
        
        submitted = st.form_submit_button("Войти", type="primary", use_container_width=True)
        
        if submitted:
            if not login or not password:
                st.error("❌ Пожалуйста, заполните все поля")
            else:
                user = authenticate_user(login, password)
                
                if user:
                    # Сохраняем данные пользователя в сессии
                    st.session_state['authenticated'] = True
                    st.session_state['user'] = user
                    st.session_state['role'] = get_user_role_name(user['role_id'])

                    # Если роль - студент, загружаем его профиль
                    if st.session_state['role'] == 'student':
                        # Получаем профиль студента по user_id
                        profile = db_manager.get_user_profile(user['user_id'])
                        if profile:
                            st.session_state['user_profile'] = profile
                        else:
                            # Если профиля нет, создаем заглушку
                            st.warning("Профиль студента не найден, создайте его в админке")
                            st.session_state['user_profile'] = None
                    
                    st.success(f"✅ Добро пожаловать, {user['first_name']} {user['last_name']}!")
                    st.rerun()
                else:
                    st.error("❌ Неверный логин или пароль")
    
    # Информация для тестирования
    with st.expander("ℹ️ Тестовые учетные записи"):
        st.markdown("""
        - **Администратор**: `admin` / `admin123`
        - **Преподаватель**: `teacher` / `teacher123`
        - **Обучающийся**: `student` / `student123`
        - **Сотрудник**: `org_user` / `org123`
        """)
    
    st.markdown("</div>", unsafe_allow_html=True)