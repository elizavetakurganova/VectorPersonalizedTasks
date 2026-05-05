import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from database.db_manager import db_manager

def show_org_dashboard():
    if st.session_state.get('role') != 'org':
        st.error("Доступ запрещён.")
        return

    user = st.session_state['user']
    org_id = user['org_id']
    org_info = db_manager.get_user_organization(user['user_id'])
    org_name = org_info['org_name'] if org_info else "Организация"
    org_type = org_info['org_type'] if org_info else "school"
    is_university = (org_type == 'university')

    # Терминология
    if is_university:
        group_label = "Группа"
        groups_label = "Группам"
        student_label = "Студент"
        students_label = "студентов"
    else:
        group_label = "Класс"
        groups_label = "Классам"
        student_label = "Ученик"
        students_label = "учеников"

    with st.sidebar:
        st.title(f"👋 {user['first_name']} {user['last_name']}")
        st.caption("Сотрудник организации")
        st.markdown(f"**{org_name}**")
        st.markdown("---")
        if st.button("🚪 Выйти", use_container_width=True):
            for key in ['authenticated', 'user', 'role']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

    st.title(f"📊 Статистика")

    # Получаем все группы организации со статистикой
    groups = db_manager.get_organization_groups_with_stats(org_id)

    if not groups:
        st.info(f"В организации пока нет групп.")
        return

    # Инициализация состояния для выбранной группы
    if 'org_selected_group_id' not in st.session_state:
        st.session_state.org_selected_group_id = None
        st.session_state.org_selected_group_name = None

    # Две вкладки
    tab1, tab2 = st.tabs(["📈 Статистика", f"📋 Список групп"])

    # ---- Вкладка 1: Графики ----
    with tab1:
        st.subheader(f"Успеваемость")

        data = []
        for g in groups:
            data.append({
                group_label: g['name'],
                'Успеваемость (%)': g['avg_success_rate'],
                f'Количество {students_label}': g['students_count']
            })
        df = pd.DataFrame(data)

        if df.empty:
            st.info("Нет данных для построения графиков")
        else:
            st.bar_chart(df.set_index(group_label)['Успеваемость (%)'])

            total_students = df[f'Количество {students_label}'].sum()
            if total_students > 0:
                st.subheader(f"Распределение {students_label} по {groups_label.lower()}")
                non_empty = df[df[f'Количество {students_label}'] > 0]
                if not non_empty.empty:
                    fig, ax = plt.subplots(figsize=(5, 3))
                    sizes = non_empty[f'Количество {students_label}'].tolist()
                    labels = non_empty[group_label].tolist()
                    ax.pie(sizes, labels=labels, autopct='%1.1f%%', radius=0.8)
                    ax.set_title(f'Распределение {students_label} по {groups_label.lower()}', fontsize=6)
                    st.pyplot(fig)
            else:
                st.info(f"Нет {students_label} для построения диаграммы")

            if st.button("💾 Сохранить статистику в CSV"):
                filename = f"Статистика_по_{groups_label}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                df.to_csv(filename, index=False, encoding='utf-8-sig')
                st.success(f"Сохранено в {filename}")

    # ---- Вкладка 2: Список групп или таблица учеников ----
    with tab2:
        # Если выбрана группа – показываем таблицу учеников
        if st.session_state.org_selected_group_id:
            group_id = st.session_state.org_selected_group_id
            group_name = st.session_state.org_selected_group_name

            st.subheader(f"{group_label} **{group_name}**")

            students = db_manager.get_group_students_details(group_id)
            if not students:
                st.info(f"В этой {group_label.lower()} нет {students_label}.")
            else:
                df_students = pd.DataFrame(students)
                df_students.columns = [
                    'ID', 'ФИО', 'Успеваемость (%)', 'Решено задач',
                    'Группа успеваемости', 'Ср. время (сек)', 'Использование подсказок (%)',
                    'Уровень мастерства (%)', 'Уровень struggle (%)'
                ]
                st.dataframe(df_students, use_container_width=True, hide_index=True)

            if st.button("← Назад"):
                st.session_state.org_selected_group_id = None
                st.session_state.org_selected_group_name = None
                st.rerun()
        else:
            sorted_groups = sorted(groups, key=lambda x: x['name'])
            for g in sorted_groups:
                col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
                with col1:
                    st.write(f"**{g['name']}**")
                with col2:
                    st.write(f"{student_label}ов: {g['students_count']}")
                with col3:
                    success = g['avg_success_rate']
                    if success >= 75:
                        color = "🟢"
                    elif success >= 50:
                        color = "🟡"
                    else:
                        color = "🔴"
                    st.write(f"{color} Успеваемость: {success}%")
                with col4:
                    if st.button("👥 Показать учеников", key=f"show_org_{g['id']}"):
                        st.session_state.org_selected_group_id = g['id']
                        st.session_state.org_selected_group_name = g['name']
                        st.rerun()
                st.divider()