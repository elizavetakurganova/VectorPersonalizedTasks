import streamlit as st
import re
from database.db_manager import db_manager

def show_edit_data(user, org_id, org_type):
    is_university = (org_type == 'university')
    if is_university:
        group_label = "Группа"
        groups_label = "Групп"
        group_label_short = "Групп"
        subject_label = "Дисциплина"
        subjects_label = "Дисциплин"
        current = "Текущая"
    else:
        group_label = "Класс"
        groups_label = "Классов"
        group_label_short = "Класс"
        subject_label = "Предмет"
        subjects_label = "Предмет"
        current = "Текущий"

    st.subheader(f"Редактирование данных: {user['first_name']} {user['last_name']} (роль: {user['role']})")

    if user['role_id'] == 3:  # Студент / Ученик
        current_group = db_manager.get_student_group(user['id'])
        if current_group:
            st.info(f"**{current} {group_label.lower()}:** {current_group.name}")
        else:
            st.info(f"**{current} {group_label.lower()}:** не назначен")

        groups = db_manager.get_organization_groups(org_id)
        # Фильтруем группы по типу
        if is_university:
            groups = [g for g in groups if g['type'] == 'group']
        else:
            groups = [g for g in groups if g['type'] == 'class']
        if not groups:
            st.warning(f"Нет доступных {groups_label.lower()}.")
        current_group = db_manager.get_student_group(user['id'])
        current_group_id = current_group.group_id if current_group else None
        group_options = {g['name']: g['id'] for g in groups}
        if group_options:
            try:
                default_index = list(group_options.values()).index(current_group_id) if current_group_id in group_options.values() else 0
            except ValueError:
                default_index = 0
            selected_group_name = st.selectbox(f"{group_label}", options=list(group_options.keys()), index=default_index)
            if st.button("Сохранить группу"):
                new_group_id = group_options[selected_group_name]
                if db_manager.set_student_group(user['id'], new_group_id):
                    st.session_state.temp_message = f"{group_label} для {user['first_name']} {user['last_name']} изменена на {selected_group_name}."
                    st.session_state.admin_mode = None
                    st.rerun()
                else:
                    st.error("Ошибка сохранения")
                    
    elif user['role_id'] == 2:  # Учитель / Преподаватель
        if 'last_success_time' not in st.session_state:
            st.session_state.last_success_time = 0

        st.markdown(f"### Управление {subjects_label.lower()}ами и {group_label_short.lower()}ами")
        teachings = db_manager.get_teacher_teaching(user['id'])

        if teachings:
            st.markdown(f"**Текущие {subjects_label.lower()}ы и {group_label_short.lower()}ы:**")
            for t in teachings:
                col1, col2, col3 = st.columns([2, 2, 1])
                with col1:
                    st.write(f"**{t['subject']}**")
                with col2:
                    st.write(t['group_name'] or f"{group_label} не указана")
                with col3:
                    if st.button("❌ Удалить", key=f"del_teach_{t['id']}"):
                        if db_manager.remove_teaching(t['id']):
                            st.session_state.temp_message = "Запись удалена."
                            st.rerun()
                        else:
                            st.error("Ошибка удаления")
            st.markdown("---")
        
        form_key = f"add_teaching_form_{st.session_state.last_success_time}"
        
        with st.form(key=form_key):
            group_input = st.text_input(
                f"{group_label}",
                placeholder=f"Пример: {'5Б' if not is_university else 'Группа 101'}"
            )
            subject_input = st.text_input(
                subject_label,
                placeholder=f"{'Математика, Алгебра, Физика...' if not is_university else 'Алгоритмы и структуры данных, Линейная алгебра...'}"
            )
            
            submitted = st.form_submit_button("Добавить")
            
            if submitted:
                if not subject_input.strip():
                    st.error(f"Введите название {subject_label.lower()}")
                elif not group_input.strip():
                    st.error(f"Укажите название {group_label.lower()}")
                else:
                    group_name = group_input.strip()
                    subject_name = subject_input.strip()
                    
                    if is_university:
                        group_type = "group"
                        grade = None
                    else:
                        group_type = "class"
                        grade = None
                        match = re.match(r'(\d+)', group_name)
                        if match:
                            grade = int(match.group(1))
                    
                    group_id = db_manager.get_or_create_group(
                        org_id=org_id,
                        group_name=group_name,
                        group_type=group_type,
                        grade_level=grade,
                        teacher_id=user['id']
                    )
                    
                    # Проверяем существование ДО добавления
                    from database.models import Teaching
                    session_for_check = db_manager.get_session()
                    exists = session_for_check.query(Teaching).filter(
                        Teaching.teacher_id == user['id'],
                        Teaching.group_id == group_id,
                        Teaching.subject == subject_name
                    ).first() is not None
                    session_for_check.close()
                    
                    if exists:
                        st.session_state.edit_data_message = {
                            'type': 'error',
                            'text': f"Не удалось добавить преподавание. {subject_label} '{subject_name}' уже назначен для {group_label.lower()} '{group_name}'"
                        }
                        st.rerun()
                    else:
                        success = db_manager.add_teaching(
                            teacher_id=user['id'],
                            group_id=group_id,
                            subject=subject_name
                        )
                        
                        if success:
                            # Меняем ключ формы, чтобы создать новую "пустую" форму
                            st.session_state.last_success_time += 1
                            st.session_state.edit_data_message = {
                                'type': 'success', 
                                'text': f"{subject_label} '{subject_name}' добавлен для {group_label.lower()} '{group_name}'"
                            }
                            st.rerun()
                        else:
                            st.session_state.edit_data_message = {
                                'type': 'error',
                                'text': f"Ошибка при добавлении {subject_label.lower()}"
                            }
                            st.rerun()

    if st.button("Назад к списку"):
        st.session_state.admin_mode = None
        st.rerun()