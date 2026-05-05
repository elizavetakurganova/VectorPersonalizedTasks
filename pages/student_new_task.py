import streamlit as st
import time
import re
from datetime import datetime
from database.db_manager import db_manager
from generator.student_profiler import StudentProfiler
from tracker.progress_tracker import ProgressTracker
from generator.task_generator import YandexGPTTaskGenerator

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
    history = db_manager.get_task_history(student_uuid, limit=1000)
    topics = set()
    for task in history:
        topic = task.get('topic')
        if topic:
            topics.add(topic)
    return sorted(list(topics))

def show_new_task_page(profile):
    st.title("📝 Новое задание")
    
    if not profile or not profile.uuid:
        st.warning("Профиль не найден. Войдите в систему.")
        return
    
    student_uuid = profile.uuid
    
    # Инициализация состояния
    if 'current_task' not in st.session_state:
        st.session_state.current_task = None
    if 'answers' not in st.session_state:
        st.session_state.answers = {}
    if 'task_start_time' not in st.session_state:
        st.session_state.task_start_time = None
    if 'task_checked' not in st.session_state:
        st.session_state.task_checked = False
    if 'hints_count' not in st.session_state:
        st.session_state.hints_count = 0
    if 'hints_expanders' not in st.session_state:
        st.session_state.hints_expanders = {}
    if 'auto_topic_message' not in st.session_state:
        st.session_state.auto_topic_message = None
    
    # Плашки со слабыми и сильными темами
    tracker = get_tracker()
    progress = tracker.get_progress(student_uuid)
    if progress:
        col1, col2 = st.columns(2)
        with col1:
            if progress.get('weak_topics'):
                st.warning(f"🎯 Темы для повторения: {', '.join(progress['weak_topics'])}")
            else:
                st.success(f"🎯 Закрепите изученное: {', '.join(progress['strong_topics'])}")
        with col2:
            if progress.get('strong_topics') and not(progress.get('weak_topics')):
                pass
            elif progress.get('strong_topics'):
                st.success(f"✨ Сильные темы: {', '.join(progress['strong_topics'])}")
    st.markdown("---")
    
    # Получаем темы ученика для выбора
    student_topics = get_student_topics(student_uuid)
    if not student_topics:
        st.info("📭 У вас пока нет решённых заданий. Рекомендуемые темы будут доступны позже.")
        available_topics = ["математика", "русский язык", "физика", "информатика"]
    else:
        available_topics = student_topics
    
    # Форма настройки (показывается, только если нет текущего задания)
    if st.session_state.current_task is None:
        col1, col2 = st.columns(2)
        with col1:
            topic_option = st.radio(
                "Выбор темы:",
                ["Автовыбор", "Выбрать тему"],
                key="topic_option"
            )
            if topic_option == "Выбрать тему":
                topic = st.selectbox("Тема:", available_topics, key="topic_select")
            else:
                topic = None
                if progress and progress.get('weak_topics'):
                    weak = progress['weak_topics']
                    st.session_state.auto_topic_message = f"🎯 Будет выбрана тема: **{weak[0]}**"
                else:
                    st.session_state.auto_topic_message = None
                    st.session_state.auto_topic_message = f"🎯 Будет выбрана тема: **{available_topics[0]}**"
                if st.session_state.auto_topic_message:
                    st.info(st.session_state.auto_topic_message)
        
        with col2:
            num_questions = st.slider("Количество заданий:", 1, 5, 3, key="num_questions")
        
        if st.button("🎯 Сгенерировать задание", type="primary", use_container_width=True):
            generator = get_generator()
            if not generator.is_configured:
                st.error("Генератор не настроен. Проверьте API-ключи YandexGPT.")
            else:
                with st.spinner("Генерация вашего задания..."):
                    try:
                        final_topic = topic
                        if not final_topic:
                            if progress and progress.get('weak_topics'):
                                final_topic = progress['weak_topics'][0]
                            elif student_topics:
                                final_topic = student_topics[0]
                            else:
                                final_topic = "математика"
                        
                        task = generator.generate_task(
                            student_id=student_uuid,
                            topic=final_topic,
                            num_questions=num_questions,
                            temperature=0.7
                        )
                        
                        if task and task.get('questions'):
                            st.session_state.current_task = task
                            st.session_state.answers = {}
                            st.session_state.hints_count = 0
                            st.session_state.hints_expanders = {}
                            st.session_state.task_start_time = time.time()
                            st.session_state.task_checked = False
                            st.session_state.auto_topic_message = None
                            st.success(f"✅ Задание сгенерировано! Тема: **{final_topic}**")
                            st.rerun()
                        else:
                            st.error("Не удалось сгенерировать задание. Попробуйте ещё раз.")
                    except Exception as e:
                        st.error(f"Ошибка генерации: {e}")
    else:
        # Отображение текущего задания
        task = st.session_state.current_task
        st.subheader(f"📝 Задание: {task.get('topic')}")
        st.caption(f"⚙️ Сложность: {task.get('parameters', {}).get('difficulty', 'средний')}")
        
        questions = task.get('questions', [])
        for i, q in enumerate(questions):
            with st.container():
                st.markdown(f"**{i+1}. {q.get('text')}**")
                answer = st.text_input(
                    "Ваш ответ:",
                    key=f"answer_{i}",
                    value=st.session_state.answers.get(str(i), ""),
                    disabled=st.session_state.task_checked
                )
                st.session_state.answers[str(i)] = answer
                if q.get('hint'):
                    hint_key = f"hint_{i}"
                    if st.button("💡 Показать подсказку", key=hint_key):
                        st.session_state.hints_count += 1
                        st.info(q['hint'])
        
        # Кнопки
        col_btn1, col_btn2 = st.columns(2)

        with col_btn1:
            # Кнопка отправки – неактивна после проверки
            if st.button("📨 Отправить на проверку", type="primary", 
                        use_container_width=True, disabled=st.session_state.task_checked):
                elapsed_time = int(time.time() - st.session_state.task_start_time) if st.session_state.task_start_time else 30
                
                correct_count = 0
                results = []
                for i, q in enumerate(questions):
                    user_answer = st.session_state.answers.get(str(i), "").strip()
                    correct_answer = str(q.get('answer', '')).strip()
                    is_correct = normalize_answer(user_answer) == normalize_answer(correct_answer)
                    if is_correct:
                        correct_count += 1
                    results.append({
                        'question': q.get('text'),
                        'user_answer': user_answer,
                        'correct_answer': correct_answer,
                        'explanation': q.get('explanation', 'Объяснение отсутствует'),
                        'is_correct': is_correct
                    })
                score = correct_count / len(questions)
                
                try:
                    db_manager.save_task_result(
                        student_uuid=student_uuid,
                        task_data=task,
                        score=score,
                        time_spent=elapsed_time,
                        hints_used=st.session_state.hints_count
                    )
                except Exception as e:
                    st.error(f"Ошибка сохранения: {e}")
                
                st.balloons()
                st.success(f"✅ Результат: {correct_count}/{len(questions)} правильных ({score*100:.0f}%)")
                st.info(f"⏱️ Время выполнения: {elapsed_time} сек | 💡 Использовано подсказок: {st.session_state.hints_count}")
                
                # Сохраняем результаты в сессию и помечаем задание как проверенное
                st.session_state.results = results
                st.session_state.task_checked = True

        with col_btn2:
            if st.button("🔄 Новое задание", use_container_width=True):
                st.session_state.current_task = None
                st.session_state.answers = {}
                st.session_state.hints_count = 0
                st.session_state.hints_expanders = {}
                st.session_state.task_start_time = None
                st.session_state.task_checked = False
                st.session_state.results = None
                st.session_state.auto_topic_message = None
                st.rerun()

        # Детальная проверка (отображается только после отправки)
        if st.session_state.task_checked and st.session_state.results:
            with st.expander("📊 Детальная проверка", expanded=True):
                for i, res in enumerate(st.session_state.results):
                    if res['is_correct']:
                        st.success(f"**{i+1}. ✅ Правильно**")
                    else:
                        st.error(f"**{i+1}. ❌ Неправильно**")
                    
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.write("📝 **Ваш ответ:**")
                        st.write(res['user_answer'] if res['user_answer'] else "(пусто)")
                    with col_b:
                        st.write("✅ **Правильный ответ:**")
                        st.write(res['correct_answer'])
                    
                    st.write("📖 **Объяснение:**")
                    st.write(res['explanation'])
                    st.markdown("---")
            # Помечаем задание как проверенное (форма остаётся, поля ввода блокируются)
            st.session_state.task_checked = True