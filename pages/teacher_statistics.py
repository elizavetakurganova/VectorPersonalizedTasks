import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

def show_statistics_page(user, teacher_classes, is_university):
    """Страница статистики с графиками"""
    st.title("📊 Статистика")

    # Текстовые переменные в зависимости от типа учреждения
    if is_university:
        groups_label = "групп"
        group_label = "Групп"
        students_label = "студентов"
        student_label = "Студент"
    else:
        groups_label = "класс"
        group_label = "Класс"
        students_label = "учеников"
        student_label = "Ученик"

    tab1, tab2 = st.tabs(["📈 Графики и диаграммы", f"📋 {group_label}ы"])

    with tab1:
        st.subheader(f"Успеваемость по {groups_label}ам")

        if not teacher_classes:
            st.info(f"Пока нет данных")
            return

        # Убираем возможные дубликаты по id класса
        unique_classes = {}
        for cls in teacher_classes:
            if cls['id'] not in unique_classes:
                unique_classes[cls['id']] = cls
        teacher_classes = list(unique_classes.values())

        # Подготовка данных
        data = []
        for cls in teacher_classes:
            students_count = cls.get('students_count', 0)
            avg_success = cls.get('avg_success_rate', 0)
            data.append({
                group_label: cls['name'],
                'Успеваемость (%)': avg_success,
                f'Количество {students_label}': students_count
            })

        df = pd.DataFrame(data)

        if df.empty:
            st.info("Нет данных для построения графиков")
            return

        # Столбчатая диаграмма
        st.bar_chart(df.set_index(group_label)['Успеваемость (%)'])

        # Круговая диаграмма (только если есть ученики)
        total_students = df[f'Количество {students_label}'].sum()
        if total_students > 0:
            st.subheader(f"Распределение {students_label} по {groups_label}ам")
            # Исключаем классы без учеников
            non_empty = df[df[f'Количество {students_label}'] > 0]
            if not non_empty.empty:
                fig, ax = plt.subplots(figsize=(5, 3))
                sizes = non_empty[f'Количество {students_label}'].tolist()
                labels = non_empty[group_label].tolist()
                ax.pie(sizes, labels=labels, autopct='%1.1f%%', radius=0.8)
                ax.set_title(f'Распределение {students_label} по {groups_label}ам', fontsize=6)
                st.pyplot(fig)
            else:
                st.info(f"Нет {students_label} ни в одном {group_label.lower()}е")
        else:
            st.info(f"Нет {students_label} для построения круговой диаграммы")

        # Сохранение статистики
        if st.button("💾 Сохранить статистику в файл"):
            filename = f"Успеваемость_по_{groups_label}ам_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            st.success(f"Статистика сохранена в файл: {filename}")

    with tab2:
        st.subheader(f"Список {groups_label} с успеваемостью")
        if not teacher_classes:
            st.info(f"У вас пока нет {groups_label}")
        else:
            # Сортируем по названию
            sorted_classes = sorted(teacher_classes, key=lambda x: x['name'])
            for cls in sorted_classes:
                with st.container():
                    col1, col2, col3 = st.columns([2, 1, 1])
                    with col1:
                        st.write(f"**{cls['name']}**")
                    with col2:
                        st.write(f"{student_label}ов: {cls.get('students_count', 0)}")
                    with col3:
                        success = cls.get('avg_success_rate', 0)
                        if success >= 75:
                            color = "🟢"
                        elif success >= 50:
                            color = "🟡"
                        else:
                            color = "🔴"
                        st.write(f"{color} Успеваемость: {success}%")
                    st.markdown("---")