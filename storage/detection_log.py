# storage/detection_log.py

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text
from sqlalchemy.orm import DeclarativeBase, Session
from datetime import datetime
from config import get_settings


class Base(DeclarativeBase):
    pass


class Detection(Base):
    __tablename__ = "detections"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    session_id      = Column(String(64), index=True)
    pattern_id      = Column(String(8), index=True)
    pattern_name    = Column(String(64))
    confidence      = Column(Float)
    input_type      = Column(String(16))   # text | image | json | event
    evidence        = Column(Text)
    prevention      = Column(Text)
    source_url      = Column(String(512))
    platform        = Column(String(64))   # amazon | netflix | swiggy | unknown
    created_at      = Column(DateTime, default=datetime.utcnow)


class DetectionLog:
    def __init__(self):
        settings = get_settings()
        self.engine = create_engine(
            settings.database_url,
            connect_args={"check_same_thread": False}  # SQLite specific
        )
        Base.metadata.create_all(self.engine)

    def insert(self, data: dict) -> int:
        with Session(self.engine) as session:
            record = Detection(**{
                k: v for k, v in data.items()
                if k in Detection.__table__.columns.keys()
            })
            session.add(record)
            session.commit()
            session.refresh(record)
            return record.id

    def get_by_session(self, session_id: str) -> list:
        with Session(self.engine) as session:
            return session.query(Detection)\
                .filter(Detection.session_id == session_id)\
                .order_by(Detection.created_at.desc())\
                .all()

    def get_recent(self, limit: int = 20) -> list:
        with Session(self.engine) as session:
            rows = session.query(Detection)\
                .order_by(Detection.created_at.desc())\
                .limit(limit).all()
            return [
                {c.name: getattr(r, c.name) for c in Detection.__table__.columns}
                for r in rows
            ]

    def get_stats(self) -> dict:
        with Session(self.engine) as session:
            total = session.query(Detection).count()
            by_pattern = {}
            for row in session.query(Detection.pattern_id, Detection.pattern_name).all():
                key = f"{row.pattern_id} - {row.pattern_name}"
                by_pattern[key] = by_pattern.get(key, 0) + 1
            return {"total": total, "by_pattern": by_pattern}