import streamlit as st
import logging

st.set_page_config(
    page_title="Вектор.Генератор заданий",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

from pages.login import show_login_page
from pages.student_dashboard import show_student_dashboard
from pages.teacher_dashboard import show_teacher_dashboard
from pages.org_dashboard import show_org_dashboard
from pages.admin_dashboard import show_admin_dashboard
from utils.config import config

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

st.markdown("""
    <style>
        [data-testid="stSidebarNav"] {
            display: none !important;
        }
    </style>
    """, unsafe_allow_html=True)

def hide_sidebar():
    st.markdown("""
        <style>
        [data-testid="stSidebar"] {
            display: none !important;
        }
        
        /* Центрируем через flex */
        .main {
            display: flex !important;
            justify-content: center !important;
        }
        
        .stApp {
            max-width: 500px !important;
            margin: 0 auto !important;
        }
        </style>
        """, unsafe_allow_html=True)

def show_sidebar():
    st.markdown("""
        <style>
        [data-testid="stSidebar"] {
            display: block !important;
        }
        </style>
        """, unsafe_allow_html=True)

if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False

def main():
    if not st.session_state['authenticated']:
        hide_sidebar() 
        show_login_page()
    else:
        show_sidebar()

        st.sidebar.image("images/my_logo-no-bg.png", width=200)

        role = st.session_state['role']
        
        if role == 'student':
            show_student_dashboard()
        elif role == 'teacher':
            show_teacher_dashboard()
        elif role == 'org':
            show_org_dashboard()
        elif role == 'admin':
            show_admin_dashboard()
        else:
            st.error(f"Неизвестная роль: {role}")
            if st.button("Выйти"):
                logout()

def logout():
    """Функция выхода из системы"""
    for key in ['authenticated', 'user', 'role']:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()

if __name__ == "__main__":
    main()