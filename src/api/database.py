from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import inspect, text
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./dev.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def ensure_phase1_schema(engine):
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    if "exercises" in table_names:
        exercise_columns = {col["name"] for col in inspector.get_columns("exercises")}
        if "topic_id" not in exercise_columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE exercises ADD COLUMN topic_id INTEGER"))
        if "is_required" not in exercise_columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE exercises ADD COLUMN is_required BOOLEAN NOT NULL DEFAULT false"))

    if "topics" in table_names:
        topic_columns = {col["name"] for col in inspector.get_columns("topics")}
        with engine.begin() as conn:
            if "required_beginner" not in topic_columns:
                conn.execute(text("ALTER TABLE topics ADD COLUMN required_beginner INTEGER DEFAULT 0"))
            if "required_mid" not in topic_columns:
                conn.execute(text("ALTER TABLE topics ADD COLUMN required_mid INTEGER DEFAULT 0"))
            if "required_expert" not in topic_columns:
                conn.execute(text("ALTER TABLE topics ADD COLUMN required_expert INTEGER DEFAULT 0"))

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
