import streamlit as st

def show_teacher_profile(user, teacher_subjects, teacher_classes, teacher_students_count, is_university):
    """Страница профиля преподавателя"""

    st.title("👤 Мой профиль")
    st.write(f"**Логин:** {user.get('login', '')}")

    col1, col2, col3 = st.columns(3)
    group_label = "групп" if is_university else "классов"
    students_label = "студентов" if is_university else "учеников"
    subjects_label = "Дисциплины" if is_university else "Предметы"

    with col1:
        unique_groups_count = len(set(cls['name'] for cls in teacher_classes))
        st.metric(label=f"🎓 Всего {group_label}", value=unique_groups_count)

    with col2:
        st.metric(label=f"👥 Всего {students_label}", value=teacher_students_count)

    with col3:
        st.write(f"**📚 {subjects_label}**")
        for subj in teacher_subjects:
            st.write(f"- {subj}")   # обычный маркированный список