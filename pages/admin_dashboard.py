import streamlit as st
from database.db_manager import db_manager
from pages.admin_change_password import show_change_password
from pages.admin_add_user import show_add_user
from pages.admin_edit_data import show_edit_data

def show_admin_dashboard():
    if st.session_state.get('role') != 'admin':
        st.error("Доступ запрещён.")
        return

    user = st.session_state['user']
    org_id = user['org_id']
    org_info = db_manager.get_user_organization(user['user_id'])
    org_name = org_info['org_name'] if org_info else "Организация"
    org_type = db_manager.get_organization_type(org_id)

    if 'temp_message' in st.session_state:
        st.success(st.session_state.temp_message)
        del st.session_state.temp_message

    if 'admin_mode' not in st.session_state:
        st.session_state.admin_mode = None

    with st.sidebar:
        st.title(f"👋 {user['first_name']} {user['last_name']}")
        st.caption("Администратор")
        st.markdown("---")
        if st.button("🚪 Выйти", use_container_width=True):
            for key in ['authenticated', 'user', 'role', 'admin_mode', 'temp_message']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

    st.title("🔧 Управление пользователями")
    st.subheader(f"{org_name}")

    if st.session_state.admin_mode == 'change_password' and 'change_user' in st.session_state:
        show_change_password(st.session_state.change_user)
        return
    elif st.session_state.admin_mode == 'edit_data' and 'edit_user' in st.session_state:
        show_edit_data(st.session_state.edit_user, org_id, org_type)
        return
    elif st.session_state.admin_mode == 'add_user':
        show_add_user(org_id, org_type)
        return

    tab1, tab2 = st.tabs(["📋 Список пользователей", "➕ Добавить пользователя"])

    with tab1:
        users = db_manager.get_organization_users(org_id)
        if not users:
            st.info("Нет пользователей.")
        else:
            all_roles = sorted(set(u['role'] for u in users))
            
            col_filter, col_sort = st.columns([2, 3])
            with col_filter:
                selected_roles = st.multiselect(
                    "Фильтр по роли",
                    options=all_roles,
                    default=[],
                    help="Выберите одну или несколько ролей"
                )
            with col_sort:
                sort_option = st.selectbox(
                    "Сортировка",
                    options=["Без сортировки", "Имя (А-Я)", "Имя (Я-А)", "Логин (А-Я)", "Логин (Я-А)"],
                    index=0
                )
            
            # Применяем фильтр по роли
            filtered_users = users.copy()
            if selected_roles:
                filtered_users = [u for u in filtered_users if u['role'] in selected_roles]
            
            # Применяем сортировку
            if sort_option != "Без сортировки":
                reverse = False
                if sort_option == "Имя (А-Я)":
                    key_func = lambda u: f"{u['first_name']} {u['last_name']}".lower()
                    reverse = False
                elif sort_option == "Имя (Я-А)":
                    key_func = lambda u: f"{u['first_name']} {u['last_name']}".lower()
                    reverse = True
                elif sort_option == "Логин (А-Я)":
                    key_func = lambda u: u['login'].lower()
                    reverse = False
                elif sort_option == "Логин (Я-А)":
                    key_func = lambda u: u['login'].lower()
                    reverse = True
                filtered_users.sort(key=key_func, reverse=reverse)
            
            if not filtered_users:
                st.info("Нет пользователей, соответствующих выбранным фильтрам.")
            else:
                # Выводим количество отфильтрованных пользователей
                st.caption(f"Найдено: {len(filtered_users)} из {len(users)}")
                st.divider()
                
                # Заголовки таблицы
                cols = st.columns([2, 2, 2, 1.5, 1.5])
                cols[0].markdown("**Имя**")
                cols[1].markdown("**Логин**")
                cols[2].markdown("**Роль**")
                cols[3].markdown("**Пароль**")
                cols[4].markdown("**Данные**")
                st.divider()
                
                for u in filtered_users:
                    col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 1.5, 1.5])
                    col1.write(f"{u['first_name']} {u['last_name']}")
                    col2.write(u['login'])
                    col3.write(u['role'])
                    if col4.button("Изменить пароль", key=f"change_pwd_{u['id']}"):
                        st.session_state.admin_mode = 'change_password'
                        st.session_state.change_user = u
                        st.rerun()
                    if u['role_id'] in (2, 3):
                        if col5.button("Изменить данные", key=f"edit_data_{u['id']}"):
                            st.session_state.admin_mode = 'edit_data'
                            st.session_state.edit_user = u
                            st.rerun()
                    st.divider()

    with tab2:
        if st.button("➕ Добавить нового пользователя", use_container_width=True):
            st.session_state.admin_mode = 'add_user'
            st.rerun()