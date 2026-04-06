from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import Base, Worker, Attendance, ShiftSelection

engine = create_engine('sqlite:///workers.db')
SessionLocal = sessionmaker(bind=engine)
Base.metadata.create_all(engine)

def get_workers_by_workshop(workshop):
    session = SessionLocal()
    workers = session.query(Worker).filter(Worker.workshop == workshop).all()
    session.close()
    return workers

def add_worker(fullname, workshop):
    session = SessionLocal()
    worker = Worker(fullname=fullname, workshop=workshop)
    session.add(worker)
    session.commit()
    session.close()

def mark_present(worker_id, shift_hours, ktu):
    session = SessionLocal()
    att = Attendance(worker_id=worker_id, shift_hours=shift_hours, ktu=ktu, status="present")
    session.add(att)
    session.commit()
    session.close()

def mark_other(worker_id, status):
    session = SessionLocal()
    att = Attendance(worker_id=worker_id, shift_hours=0, ktu=0, status=status)
    session.add(att)
    session.commit()
    session.close()

def get_current_shift():
    session = SessionLocal()
    last = session.query(ShiftSelection).order_by(ShiftSelection.selected_at.desc()).first()
    session.close()
    return last.shift_hours if last else 8

def set_current_shift(workshop, shift):
    session = SessionLocal()
    ss = ShiftSelection(workshop=workshop, shift_hours=shift)
    session.add(ss)
    session.commit()
    session.close()

def get_attendance_report():
    session = SessionLocal()
    res = session.query(Worker.fullname, Attendance.status, Attendance.ktu, Attendance.shift_hours).join(Attendance).all()
    session.close()
    return [{"fullname": r[0], "status": r[1], "ktu": r[2], "shift_hours": r[3]} for r in res]
