from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

Base = declarative_base()

class Worker(Base):
    __tablename__ = 'workers'
    id = Column(Integer, primary_key=True)
    fullname = Column(String, nullable=False)
    workshop = Column(String, nullable=False)  # "ДМТ" або "Пакування"
    shift = Column(Integer, default=8)  # 8 або 9 годин

class Attendance(Base):
    __tablename__ = 'attendance'
    id = Column(Integer, primary_key=True)
    worker_id = Column(Integer, ForeignKey('workers.id'))
    date = Column(DateTime, default=datetime.utcnow)
    shift_hours = Column(Integer)
    ktu = Column(Float, default=1.0)
    status = Column(String, default="present")  # present, vacation, sick, no_show, other
    notes = Column(String, nullable=True)

class ShiftSelection(Base):
    __tablename__ = 'shift_selection'
    id = Column(Integer, primary_key=True)
    workshop = Column(String)
    shift_hours = Column(Integer)
    selected_at = Column(DateTime, default=datetime.utcnow)
