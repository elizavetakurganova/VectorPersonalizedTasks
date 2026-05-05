import streamlit as st 
from tracker.progress_tracker import ProgressTracker
from database.db_manager import db_manager

def show_progress_page(profile):
    """Страница прогресса ученика с советами и рекомендациями"""
    st.title("📊 Мой прогресс")

    if not profile:
        st.warning("Профиль не найден. Начните выполнять задания, чтобы увидеть статистику.")
        return

    level_map = {
        'beginner':   'Первооткрыватель',
        'struggling': 'Настойчивый',
        'developing': 'Восходящая\nзвезда',
        'proficient': 'Мастер',
        'excellent':  'Легенда'
    }
    advice_map = {
        'excellent': '🎉 Великолепно! Вы – пример для подражания.',
        'proficient': '👍 Отличная работа! Ещё немного – и вы станете отличником.',
        'developing': '📈 Хороший прогресс! Продолжайте в том же духе.',
        'struggling': '💪 Не сдавайтесь! С каждой задачей вы становитесь сильнее.',
        'beginner': '🌟 Добро пожаловать! Начните с простых заданий.'
    }

    level_en = getattr(profile, 'performance_group', 'beginner') or 'beginner'
    level_ru = level_map.get(level_en, 'Начинающий')
    advice = advice_map.get(level_en, advice_map['beginner'])

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        success_rate = getattr(profile, 'success_rate', 0) or 0
        st.metric("✅ Средний результат", f"{int(success_rate * 100)}%")
    with col2:
        total = getattr(profile, 'total_problems', 0) or 0
        st.metric("📚 Решено задач", total)
    with col3:
        st.metric("🎯 Уровень", level_ru)

    avg_time = getattr(profile, 'avg_time_sec', 0) or 0
    if avg_time < 60:
        time_text = "Быстро и точно"
    elif avg_time < 120:
        time_text = "Вдумчивый подход"
    else:
        time_text = "Тщательный подход"
    with col4:
        st.metric("⏱️ Время на задание", f"{avg_time:.1f} сек", delta=time_text, delta_color="off")

    st.info(advice)

    st.subheader("🎓 Личностный рост")
    col1, col2, col3 = st.columns(3)

    mastery = getattr(profile, 'avg_mastery', 0) or 0
    if mastery >= 0.8:
        mastery_text = "Глубокое понимание"
    elif mastery >= 0.5:
        mastery_text = "Хорошая опора"
    else:
        mastery_text = "Активное освоение"
    with col1:
        st.metric("🧘 Уверенность в знаниях", f"{int(mastery * 100)}%", delta=mastery_text, delta_color="off")

    struggle = getattr(profile, 'avg_struggle', 0) or 0
    if struggle >= 0.7:
        growth_text = "Упорность"
    elif struggle >= 0.3:
        growth_text = "Уверенное продвижение"
    else:
        growth_text = "Легко и с удовольствием"
    with col2:
        st.metric("⛰️ Преодоление трудностей", f"{int(struggle * 100)}%", delta=growth_text, delta_color="off")

    hint_rate = getattr(profile, 'hint_usage_rate', 0) or 0
    if hint_rate < 0.3:
        hint_text = "Самостоятельный"
    elif hint_rate < 0.7:
        hint_text = "Осознанный"
    else:
        hint_text = "Любознательный"
    with col3:
        st.metric("📖 Стиль обучения", hint_text)

    st.subheader("📌 Анализ тем")
    tracker = ProgressTracker(db_manager=db_manager)
    progress = tracker.get_progress(profile.uuid, days=30) if profile.uuid else None

    if progress:
        weak = progress.get('weak_topics', [])
        strong = progress.get('strong_topics', [])
        if weak:
            st.warning("⚠️ **Уделите внимание:** " + ", ".join(weak))
        else:
            st.success("✅ Отлично! Вы хорошо усваиваете все темы.")
        if strong:
            st.success("💪 **Сильные темы:** " + ", ".join(strong))
        else:
            st.info("📭 Необходимо больше выполненных заданий для анализа.")
    else:
        st.info("📭 Выполните ещё несколько заданий, чтобы получить рекомендации по темам.")