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


def ensure_phase2_multi_subject_schema(engine):
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    with engine.begin() as conn:
        if "subjects" not in table_names:
            conn.execute(
                text(
                    """
                    CREATE TABLE subjects (
                        id INTEGER PRIMARY KEY,
                        code VARCHAR NOT NULL UNIQUE,
                        name VARCHAR NOT NULL UNIQUE,
                        enrollment_password_hash VARCHAR,
                        is_active BOOLEAN NOT NULL DEFAULT true,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )

        if "subjects" in table_names:
            subject_columns = {col["name"] for col in inspector.get_columns("subjects")}
            if "enrollment_password_hash" not in subject_columns:
                conn.execute(text("ALTER TABLE subjects ADD COLUMN enrollment_password_hash VARCHAR"))

        if "user_subject_enrollments" not in table_names:
            conn.execute(
                text(
                    """
                    CREATE TABLE user_subject_enrollments (
                        user_id INTEGER NOT NULL,
                        subject_id INTEGER NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (user_id, subject_id),
                        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                        FOREIGN KEY(subject_id) REFERENCES subjects(id) ON DELETE CASCADE
                    )
                    """
                )
            )

        row = conn.execute(text("SELECT id FROM subjects WHERE code = 'LEGACY' LIMIT 1")).fetchone()
        default_subject_id = int(row[0]) if row else None

        if "topics" in table_names:
            topic_columns = {col["name"] for col in inspector.get_columns("topics")}
            if "subject_id" not in topic_columns:
                conn.execute(text("ALTER TABLE topics ADD COLUMN subject_id INTEGER"))

            topics_with_null_subject = int(
                conn.execute(text("SELECT COUNT(*) FROM topics WHERE subject_id IS NULL")).scalar_one()
            )
            if topics_with_null_subject > 0:
                if default_subject_id is None:
                    conn.execute(
                        text(
                            "INSERT INTO subjects (code, name, is_active) VALUES ('LEGACY', 'Legacy Subject', true)"
                        )
                    )
                    default_subject_id = int(
                        conn.execute(text("SELECT id FROM subjects WHERE code = 'LEGACY' LIMIT 1")).scalar_one()
                    )

                conn.execute(
                    text("UPDATE topics SET subject_id = :sid WHERE subject_id IS NULL"),
                    {"sid": default_subject_id},
                )

        non_legacy_subjects = int(
            conn.execute(text("SELECT COUNT(*) FROM subjects WHERE code <> 'LEGACY' AND is_active = true")).scalar_one()
        )

        if default_subject_id is not None and non_legacy_subjects == 0:
            # Pure legacy instance: keep backward-compatible visibility.
            conn.execute(
                text(
                    """
                    INSERT INTO user_subject_enrollments (user_id, subject_id)
                    SELECT u.id, :sid
                    FROM users u
                    WHERE NOT EXISTS (
                        SELECT 1 FROM user_subject_enrollments e
                        WHERE e.user_id = u.id AND e.subject_id = :sid
                    )
                    """
                ),
                {"sid": default_subject_id},
            )

        if default_subject_id is not None and non_legacy_subjects > 0:
            # Once real subjects exist, hide LEGACY from normal selectors.
            conn.execute(text("UPDATE subjects SET is_active = false WHERE code = 'LEGACY'"))

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
