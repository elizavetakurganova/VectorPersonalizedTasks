from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
from utils.config import config

Base = declarative_base()

class Organization(Base):
    __tablename__ = 'organizations'
    
    org_id = Column(Integer, primary_key=True, autoincrement=True)
    org_type = Column(String(100), nullable=False)
    org_name = Column(String(200), nullable=False)
    
    # Relationships
    users = relationship('User', back_populates='organization')
    groups = relationship('Group', back_populates='organization')

class Role(Base):
    __tablename__ = 'roles'
    
    role_id = Column(Integer, primary_key=True, autoincrement=True)
    role_type = Column(String(50), unique=True, nullable=False)
    role_name = Column(String(100), nullable=False)
    
    # Relationships
    users = relationship('User', back_populates='role')


class User(Base):
    __tablename__ = 'users'
    
    user_id = Column(Integer, primary_key=True, autoincrement=True)
    org_id = Column(Integer, ForeignKey('organizations.org_id'), nullable=False)
    role_id = Column(Integer, ForeignKey('roles.role_id'), nullable=False)
    login = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    
    # Relationships
    organization = relationship('Organization', back_populates='users')
    role = relationship('Role', back_populates='users')
    user_profile = relationship('UserProfile', back_populates='user', uselist=False, foreign_keys='UserProfile.user_id')
    teaching = relationship('Teaching', foreign_keys='Teaching.teacher_id', back_populates='teacher')

class Group(Base):
    __tablename__ = 'groups'
    
    group_id = Column(Integer, primary_key=True, autoincrement=True)
    org_id = Column(Integer, ForeignKey('organizations.org_id'), nullable=False)
    teacher_id = Column(Integer, ForeignKey('users.user_id'), nullable=True)
    name = Column(String(100), nullable=False)
    type = Column(String(50), nullable=False)
    grade_level = Column(Integer, nullable=True)
    
    # Relationships
    organization = relationship('Organization', back_populates='groups')
    teacher = relationship('User', foreign_keys=[teacher_id], back_populates=None)
    teachings = relationship('Teaching', back_populates='group')
    user_profiles = relationship('UserProfile', back_populates='group')


class UserProfile(Base):
    __tablename__ = 'user_profiles'
    
    uuid = Column(String(255), primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    group_id = Column(Integer, ForeignKey('groups.group_id'), nullable=True)
    success_rate = Column(Float, default=0.0)
    avg_mastery = Column(Float, default=0.0)
    avg_struggle = Column(Float, default=0.0)
    total_problems = Column(Integer, default=0)
    performance_group = Column(String(50), default='beginner')
    hint_usage_rate = Column(Float, default=0.0)
    multiple_attempts_rate = Column(Float, default=0.0)
    avg_time_sec = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationships
    user = relationship('User', back_populates='user_profile', foreign_keys=[user_id])
    group = relationship('Group', back_populates='user_profiles')
    task_history = relationship('TaskHistory', back_populates='student_profile', foreign_keys='TaskHistory.student_id')

class TaskHistory(Base):
    __tablename__ = 'task_history'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String(255), ForeignKey('user_profiles.uuid'), nullable=False)
    task_data = Column(JSON, nullable=False)
    topic = Column(String(200), nullable=False)
    difficulty = Column(String(50), nullable=False)
    score = Column(Float, nullable=False)
    time_spent = Column(Integer, nullable=False)
    hints_used = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)
    
    # Relationships
    student_profile = relationship('UserProfile', back_populates='task_history', foreign_keys=[student_id])


class Teaching(Base):
    __tablename__ = 'teaching'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    teacher_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    group_id = Column(Integer, ForeignKey('groups.group_id'), nullable=False)
    subject = Column(String(100), nullable=False)
    
    # Relationships
    teacher = relationship('User', foreign_keys=[teacher_id], back_populates='teaching')
    group = relationship('Group', back_populates='teachings')


def init_db():
    """Создание всех таблиц в базе данных"""
    engine = create_engine(config.DATABASE_URL, echo=True)
    Base.metadata.create_all(engine)
    print("✅ База данных и таблицы созданы успешно!")
    return engine


def get_session():
    """Получение сессии базы данных"""
    engine = create_engine(config.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    return Session()