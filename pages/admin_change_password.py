import streamlit as st
from database.db_manager import db_manager

def show_change_password(user):
    st.subheader(f"Смена пароля: {user['first_name']} {user['last_name']} (логин: {user['login']})")
    with st.form("change_pwd_form"):
        new_password = st.text_input("Новый пароль", type="password")
        confirm_password = st.text_input("Подтверждение пароля", type="password")
        col1, col2 = st.columns(2)
        with col1:
            submit = st.form_submit_button("Сохранить")
        with col2:
            cancel = st.form_submit_button("Отмена")
        if submit:
            if not new_password:
                st.error("Введите пароль")
            elif new_password != confirm_password:
                st.error("Пароли не совпадают")
            else:
                if db_manager.change_user_password(user['id'], new_password):
                    st.session_state.temp_message = f"✅ Пароль для {user['first_name']} {user['last_name']} успешно изменён!"
                    st.session_state.admin_mode = None
                    st.rerun()
                else:
                    st.error("Ошибка смены пароля")
        if cancel:
            st.session_state.admin_mode = None
            st.rerun()

def set_mode(mode):
    st.session_state.admin_mode = mode
    st.rerun()