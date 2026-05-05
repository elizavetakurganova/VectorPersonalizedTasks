import streamlit as st
import time
import re
from database.db_manager import db_manager
from generator.student_profiler import StudentProfiler
from tracker.progress_tracker import ProgressTracker
from generator.task_generator import YandexGPTTaskGenerator

# Кешируем ресурсы (как в student_page)
@st.cache_resource
def get_profiler():
    return StudentProfiler(db_manager)

@st.cache_resource
def get_tracker():
    return ProgressTracker(db_manager)

@st.cache_resource
def get_generator():
    profiler = get_profiler()
    tracker = get_tracker()
    return YandexGPTTaskGenerator(profiler, tracker)

def normalize_answer(s):
    if not s:
        return ""
    s = s.lower().strip()
    s = re.sub(r'\s*,\s*', ',', s)
    return s

def get_student_topics(student_uuid):
    """Получить список тем из истории заданий ученика (для выбора)"""
    history = db_manager.get_task_history(student_uuid, limit=1000)
    topics = set()
    for task in history:
        topic = task.get('topic')
        if topic:
            topics.add(topic)
    return sorted(list(topics))

def show_new_task_teacher_page(user, teacher_classes, is_university):
    """Страница генерации нового задания"""
    st.title("📝 Новое задание")

    if not teacher_classes:
        st.warning("У вас нет классов для генерации заданий")
        return

    group_label = "Группа" if is_university else "Класс"
    student_label = "Студент" if is_university else "Ученик"
    subject_label = "Дисциплина" if is_university else "Предмет"

    # отображение задание, если оно уже сгенерировано
    if st.session_state.get('teacher_current_task'):
        task = st.session_state['teacher_current_task']
        st.markdown("---")
        st.subheader("📋 Сгенерированное задание")

        st.write(f"**{group_label}:** {task['group_name']}")
        st.write(f"**{student_label}:** {task['student']['name']}")
        st.write(f"**{subject_label}:** {task['subject']}")
        st.write(f"**Тема:** {task['topic']}")
        st.write(f"**Сложность:** {task['difficulty']}")

        for i, q in enumerate(task['questions'], 1):
            st.write(f"**Вопрос {i}:** {q.get('text')}")
            with st.expander("Ответ и объяснение"):
                st.write(f"**Ответ:** {q.get('answer', '—')}")
                st.write(f"**Объяснение:** {q.get('explanation', '—')}")
            st.write("---")

        # Две колонки для кнопок: Сохранить и Новое задание
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("💾 Сохранить задание в файл", use_container_width=True):
                save_task_to_file(task, student_label, group_label, subject_label)
        with col_btn2:
            if st.button("🔄 Новое задание", use_container_width=True):
                st.session_state['teacher_current_task'] = None
                st.rerun()
    else:
        # ---------- ФОРМА НАСТРОЙКИ ----------
        # Выбор класса
        class_names = sorted(set(cls['name'] for cls in teacher_classes))
        selected_class_name = st.selectbox(group_label, class_names)

        # Выбор ученика
        students = db_manager.get_class_students(selected_class_name, user['user_id'])
        if not students:
            st.info("В группе нет студентов" if is_university else "В классе нет учеников")
            return

        selected_student = st.selectbox(
            student_label,
            options=students,
            format_func=lambda x: x['name'],
            index=0
        )

        student_uuid = selected_student['uuid']
        student_user_id = selected_student['id']
        tracker = get_tracker()
        progress = tracker.get_progress(student_uuid)

        # Слабые и сильные темы
        col1, col2 = st.columns(2)
        with col1:
            if progress and progress.get('weak_topics'):
                st.warning(f"🎯 Слабые темы: {', '.join(progress['weak_topics'][:3])}")
            else:
                st.success("🎯 Нет явно слабых тем")
        with col2:
            if progress and progress.get('strong_topics'):
                st.success(f"💪 Сильные темы: {', '.join(progress['strong_topics'][:3])}")

        # Предметы учителя для этого ученика
        teacher_id = user['user_id']
        subjects = db_manager.get_teacher_subjects_for_student(teacher_id, student_user_id)
        if not subjects:
            st.error(f"Для этого {student_label.lower()} нет доступных предметов (учитель не ведёт ни одного предмета в его группе)")
            return

        subject = st.selectbox(subject_label, subjects)

        # Рекомендуемая сложность
        if progress:
            avg_score = progress.get('avg_score', 0.5)
            if avg_score >= 0.85:
                recommended_difficulty = "Средняя"
            elif avg_score >= 0.7:
                recommended_difficulty = "Средняя"
            elif avg_score >= 0.5:
                recommended_difficulty = "Легко"
            else:
                recommended_difficulty = "Очень легко"
        else:
            recommended_difficulty = "Средняя"

        st.info(f"💡 Рекомендуемая сложность на основе успеваемости: **{recommended_difficulty}**")
        difficulty = st.selectbox(
            "Сложность",
            ["Очень легко", "Легко", "Средняя", "Сложно", "Повышенной сложности"],
            index=["Очень легко", "Легко", "Средняя", "Сложно", "Повышенной сложности"].index(recommended_difficulty)
        )

        # Выбор темы
        student_topics = get_student_topics(student_uuid)
        topic_option = st.radio(
            "Выбор темы:",
            ["Автовыбор", "Выбрать из истории", "Ввести свою тему"],
            horizontal=True
        )

        final_topic = None

        if topic_option == "Автовыбор":
            if progress and progress.get('weak_topics'):
                auto_topic = progress['weak_topics'][0]
                st.info(f"🎯 Будет выбрана тема: **{auto_topic}**")
            elif student_topics:
                auto_topic = student_topics[0]
                st.info(f"📚 Будет выбрана тема: **{auto_topic}**")
            else:
                auto_topic = subject
                st.info(f"📚 Будет выбрана тема: **{auto_topic}**")
            final_topic = auto_topic

        elif topic_option == "Выбрать из истории":
            if not student_topics:
                st.warning("Нет тем в истории, используйте автовыбор или введите свою тему")
            else:
                final_topic = st.selectbox("Тема из истории:", student_topics)
        else:  # Ввести свою тему
            final_topic = st.text_input("Введите тему задания:", placeholder="Например, квадратные уравнения")

        num_questions = st.slider("Количество заданий:", 1, 5, 3)

        # Кнопка генерации
        if st.button("🎲 Сгенерировать задание", type="primary", use_container_width=True):
            # Проверка введённой темы
            if topic_option == "Ввести свою тему" and (not final_topic or final_topic.strip() == ""):
                st.error("Тема не может быть пустой. Пожалуйста, введите тему.")
            elif topic_option == "Выбрать из истории" and not final_topic:
                st.error("Тема не выбрана. Пожалуйста, выберите другую опцию.")
            else:
                generator = get_generator()
                if not generator.is_configured:
                    st.error("Генератор не настроен. Проверьте API-ключи YandexGPT.")
                else:
                    with st.spinner(f"Генерация задания по теме '{final_topic}'..."):
                        try:
                            task = generator.generate_task(
                                student_id=student_uuid,
                                topic=final_topic,
                                num_questions=num_questions,
                                difficulty=difficulty,
                                temperature=0.7
                            )
                            if task and task.get('questions'):
                                st.session_state['teacher_current_task'] = {
                                    'group_name': selected_class_name,
                                    'student': selected_student,
                                    'subject': subject,
                                    'topic': final_topic,
                                    'difficulty': difficulty,
                                    'questions': task['questions'],
                                    'task_data': task
                                }
                                st.success(f"✅ Задание сгенерировано! Тема: **{final_topic}**, сложность: {difficulty}")
                                st.rerun()
                            else:
                                st.error("Не удалось сгенерировать задание. Попробуйте ещё раз.")
                        except Exception as e:
                            st.error(f"Ошибка генерации: {e}")


def save_task_to_file(task, student_label, group_label, subject_label):
    """Сохранение задания в TXT файл (только вопросы)"""
    from datetime import datetime

    filename = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(f"{student_label}: {task['student']['name']}\n")
        f.write(f"{group_label}: {task['group_name']}\n")
        f.write(f"{subject_label}: {task['subject']}\n")
        f.write(f"Тема: {task['topic']}\n")
        f.write(f"Сложность: {task['difficulty']}\n")
        f.write("=" * 50 + "\n\n")

        for i, q in enumerate(task['questions'], 1):
            f.write(f"Вопрос {i}: {q.get('text')}\n\n")

        f.write("=" * 50 + "\n")
        f.write(f"Дата: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n")

    st.success(f"✅ Задание сохранено в файл: {filename}")