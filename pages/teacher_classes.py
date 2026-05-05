import streamlit as st
from database.db_manager import db_manager
from tracker.progress_tracker import ProgressTracker

def show_classes_page(user, teacher_classes, is_university):
    """Страница со списком групп с фильтрацией и возможностью отключить сортировку"""

    group_label = "Группа" if is_university else "Класс"
    groups_label = "Группы" if is_university else "Классы"
    students_label = "студентов" if is_university else "учеников"
    subjects_label = "Дисциплина" if is_university else "Предмет"
    student_label = "Студент" if is_university else "Ученик"

    st.title(f"Мои {groups_label}")
    
    # Если выбран класс – показываем учеников
    if st.session_state.get('selected_class'):
        show_class_students(user, st.session_state['selected_class'], is_university, group_label, subjects_label, student_label)
        return
    
    # Если выбран ученик – показываем его статистику
    if st.session_state.get('selected_student'):
        show_student_statistics(st.session_state['selected_student'], is_university)
        return
    
    # Блок фильтров и сортировки    
    all_class_names = sorted(set(cls['name'] for cls in teacher_classes))
    all_subjects = sorted(set(cls['subject'] for cls in teacher_classes))
    
    col_filter1, col_filter2, col_sort = st.columns([1.5, 2, 3])
    
    with col_filter1:
        selected_class_names = st.multiselect(
            f"Фильтр по полю {group_label}",
            options=all_class_names,
            default=[],
            help=f"Выберите один или несколько"
        )
    
    with col_filter2:
        selected_subjects = st.multiselect(
            f"Фильтр по полю {subjects_label}",
            options=all_subjects,
            default=[],
            help=f"Выберите один или несколько"
        )
    
    with col_sort:
        # Опции сортировки: сначала "Без сортировки", затем динамический текст для группы/класса
        if is_university:
            sort_options = ["Без сортировки", "Группа", subjects_label, f"Количеству {students_label}"]
        else:
            sort_options = ["Без сортировки", "Класс", subjects_label, f"Количеству {students_label}"]
        
        sort_by = st.selectbox(
            "Сортировать по",
            options=sort_options,
            index=0  # по умолчанию "Без сортировки"
        )
        
        # Показываем переключатель направления только если выбран не "Без сортировки"
        if sort_by != "Без сортировки":
            sort_ascending = st.toggle("По убыванию", value=True)
        else:
            sort_ascending = True
    
    # Применяем фильтры
    filtered_classes = teacher_classes[:]
    
    if selected_class_names:
        filtered_classes = [cls for cls in filtered_classes if cls['name'] in selected_class_names]
    
    if selected_subjects:
        filtered_classes = [cls for cls in filtered_classes if cls['subject'] in selected_subjects]
    
    # Применяем сортировку, только если выбран не "Без сортировки"
    if sort_by != "Без сортировки":
        if sort_by in ("Класс", "Группа"):
            key_func = lambda x: x['name']
        elif sort_by == subjects_label:
            key_func = lambda x: x['subject']
        else:  # сортировка по количеству учеников
            key_func = lambda x: x['students_count']
        
        filtered_classes.sort(key=key_func, reverse=sort_ascending)
    # иначе оставляем в исходном порядке (как пришло из базы)
    
    if not filtered_classes:
        st.info(f"Нет данных, соответствующих выбранным фильтрам.")
        return
    
    # Отображение таблицы
    col1, col2, col3, col4 = st.columns([1.5, 2, 2, 1])
    with col1:
        st.markdown(f"**📚 {group_label}**")
    with col2:
        st.markdown(f"**📖 {subjects_label}**")
    with col3:
        st.markdown(f"**👨‍🎓 Кол-во {students_label}**")
    with col4:
        st.markdown("**⚙️ Действия**")  

    st.markdown("---")
    
    for idx, class_item in enumerate(filtered_classes):
        col1, col2, col3, col4 = st.columns([1.5, 2, 2, 1])
        with col1:
            st.write(f"**{class_item['name']}**")
        with col2:
            st.write(class_item['subject'])
        with col3:
            st.write(f"{class_item['students_count']}")
        with col4:
            button_key = f"open_{class_item['id']}_{idx}"
            if st.button("Открыть", key=button_key, use_container_width=True):
                st.session_state['selected_class'] = class_item
                st.rerun()
        st.markdown("---")

def show_class_students(user, selected_class, is_university, group_label, subjects_label, student_label):
    """Страница со списком учеников/студентов"""

    st.write(f"*👨‍🎓 {group_label}*: {selected_class['name']}")
    st.write(f"*{subjects_label}:* {selected_class['subject']}")
    
    # Кнопка назад
    if st.button("← Назад"):
        st.session_state['selected_class'] = None
        st.rerun()
    
    st.markdown("---")
    
    # Список учеников
    students = db_manager.get_class_students(selected_class['name'], user['user_id'])
    
    if not students:
        st.info(f"У вас пока нет {"студентов" if is_university else "учеников"}")
        return
    
    # Заголовки столбцов
    col1, col2, col3 = st.columns([3, 1, 2])
    with col1:
        st.markdown(f"**👨‍🎓 {student_label}**")
    with col2:
        st.markdown("**📊 Успеваемость**")
    with col3:
        st.markdown("**⚙️ Действия**")

    st.markdown("---")

    # Данные учеников
    for idx, student in enumerate(students):
        col1, col2, col3 = st.columns([3, 1, 2])
        with col1:
            st.write(f"**{student['name']}**")
        with col2:
            # Цвет в зависимости от успеваемости
            success_rate = student['success_rate']
            if success_rate >= 75:
                color = "🟢"
            elif success_rate >= 50:
                color = "🟡"
            else:
                color = "🔴"
            st.write(f"{color} {success_rate}%")
        with col3:
            if st.button("📊 Статистика", key=f"student_{student['id']}"):
                st.session_state['selected_class'] = None 
                st.session_state['selected_student'] = student
                st.rerun()

    st.markdown("---")

def show_student_statistics(student, is_university):
    """Страница статистики ученика с русским уровнем, советом и темами"""
    student_label = "Студент" if is_university else "Ученик"
    st.title(f"📊 Статистика {student['name']}")

    if st.button("← Назад", key="back_to_class"):
        st.session_state['selected_student'] = None
        st.rerun()

    st.markdown("---")

    # Перевод уровня
    level_map = {
        'developing': 'Развивающийся',
        'proficient': 'Опытный',
        'excellent': 'Отличный',
        'struggling': 'Упорный',
        'beginner': 'Начинающий'
    }
    advice_for_teacher_map = {
        'excellent': f'🎓 {student_label} показывает отличные результаты. Предложите олимпиадные задачи или углублённые темы для дальнейшего роста.',
        'proficient': f'📚 {student_label} стабильно учится. Рекомендуйте задачи повышенной сложности, чтобы развивать навыки.',
        'developing': f'📈 {student_label} прогрессирует, есть потенциал роста. Давайте больше практических заданий, анализируйте типичные ошибки.',
        'struggling': f'🤝 {student_label}у требуется помощь. Проведите индивидуальную консультацию, разберите сложные темы, предложите дополнительные упражнения.',
        'beginner': f'🌟 {student_label} в начале пути. Начните с базовых заданий, постепенно повышайте сложность, отмечайте даже малые успехи.'
    }


    level_en = student.get('performance_group', 'beginner') or 'beginner'
    level_ru = level_map.get(level_en, 'Начинающий')
    advice = advice_for_teacher_map.get(level_en, advice_for_teacher_map['beginner'])

    success = student.get('success_rate', 0) or 0
    # если значение в долях (0.705) -> умножаем, иначе оставляем как есть
    if success < 1:
        success_pct = int(success * 100)
    else:
        success_pct = int(success)

    total = student.get('total_problems', 0) or 0
    avg_time = student.get('avg_time', 0) or 0
    hint_rate = student.get('hint_rate', 0) or 0
    if hint_rate < 1:
        hint_pct = int(hint_rate * 100)
    else:
        hint_pct = int(hint_rate)

    # краткие подписи (дельта) без мотивации
    if success_pct >= 80:
        success_delta = "высокая"
    elif success_pct >= 60:
        success_delta = "средняя"
    else:
        success_delta = "низкая"

    if avg_time < 60:
        time_delta = "очень быстро"
    elif avg_time < 120:
        time_delta = "решает быстро"
    else:
        time_delta = "решает медленно"

    if hint_pct < 30:
        hint_delta = "редко"
    elif hint_pct < 70:
        hint_delta = "умеренно"
    else:
        hint_delta = "часто"

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("✅ Успеваемость", f"{success_pct}%", delta=success_delta, delta_color="off")
    with col2:
        st.metric("📚 Решено задач", total)
    with col3:
        st.metric("🎯 Уровень", level_ru)
    with col4:
        st.metric("⏱️ Среднее время", f"{avg_time:.0f} сек", delta=time_delta, delta_color="off")

    st.markdown("---")
    mastery = student.get('mastery', 0) or 0
    if mastery < 1:
        mastery_pct = int(mastery * 100)
    else:
        mastery_pct = int(mastery)

    struggle = student.get('struggle', 0) or 0
    if struggle < 1:
        struggle_val = struggle
    else:
        struggle_val = struggle / 100.0

    # преобразуем struggle в текстовый уровень сложности
    if struggle_val <= 0.2:
        struggle_level = "очень легко"
    elif struggle_val <= 0.4:
        struggle_level = "легко"
    elif struggle_val <= 0.6:
        struggle_level = "средне"
    elif struggle_val <= 0.8:
        struggle_level = "сложно"
    else:
        struggle_level = "продвинуто"

    col1, col2, col3 = st.columns(3)
    with col1:
        # подпись: что означает процент стабильности
        if mastery_pct >= 80:
            mastery_delta = "уверенный"
        elif mastery_pct >= 60:
            mastery_delta = "устойчивый"
        else:
            mastery_delta = "требует внимания"
        st.metric("📐 Уверенность", f"{mastery_pct}%", delta=mastery_delta, delta_color="off")
    with col2:
        st.metric("🧩 Сложность заданий", struggle_level, delta=f"{int(struggle_val*100)}%", delta_color="off")
    with col3:
        st.metric("💡 Использование подсказок", f"{hint_pct}%", delta=hint_delta, delta_color="off")

    st.info(advice)

    st.subheader("📌 Рекомендации по темам")
    tracker = ProgressTracker(db_manager=db_manager)
    progress = tracker.get_progress(student.get('uuid'), days=30) if student.get('uuid') else None
    if progress:
        weak = progress.get('weak_topics', [])
        strong = progress.get('strong_topics', [])
        if weak:
            st.warning("⚠️ **Уделить внимание:** " + ", ".join(weak))
        else:
            st.info("✅ Проблем с освоением материала нет.")
        if strong:
            st.success("💪 **Сильные темы:** " + ", ".join(strong))
        else:
            st.info("📭 Необходимо больше выполненных заданий для появления рекомендаций.")
    else:
        st.info("Невозможно определить ID – рекомендации временно недоступны.")