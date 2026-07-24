from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Enum, JSON, Float, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .database import Base
import enum


class RoleEnum(str, enum.Enum):
    student = "student"
    teacher = "teacher"


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(Enum(RoleEnum), default=RoleEnum.student, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Subject(Base):
    __tablename__ = "subjects"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, nullable=False)
    name = Column(String, unique=True, nullable=False)
    enrollment_password_hash = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class UserSubjectEnrollment(Base):
    __tablename__ = "user_subject_enrollments"
    __table_args__ = (UniqueConstraint("user_id", "subject_id", name="uq_user_subject_enrollment"),)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), primary_key=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ExerciseLevel(str, enum.Enum):
    beginner = "beginner"
    mid = "mid"
    expert = "expert"


class Topic(Base):
    __tablename__ = "topics"
    __table_args__ = (UniqueConstraint("subject_id", "name", name="uq_topic_subject_name"),)
    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    weight = Column(Float, nullable=False, default=1.0)
    required_beginner = Column(Integer, nullable=False, default=0)
    required_mid = Column(Integer, nullable=False, default=0)
    required_expert = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Exercise(Base):
    __tablename__ = "exercises"
    id = Column(Integer, primary_key=True, index=True)
    topic_id = Column(Integer, ForeignKey("topics.id", ondelete="SET NULL"), nullable=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    level = Column(Enum(ExerciseLevel), default=ExerciseLevel.beginner, nullable=False)
    is_required = Column(Boolean, default=False, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class TestCase(Base):
    __tablename__ = "test_cases"
    id = Column(Integer, primary_key=True, index=True)
    exercise_id = Column(Integer, ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    content = Column(JSON, nullable=False)
    hidden = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"
    id = Column(Integer, primary_key=True, index=True)
    topic_id = Column(Integer, ForeignKey("topics.id", ondelete="CASCADE"), nullable=False)
    level = Column(Enum(ExerciseLevel), default=ExerciseLevel.beginner, nullable=False)
    statement = Column(String, nullable=False)
    options = Column(JSON, nullable=False)
    correct_option_index = Column(Integer, nullable=False)
    is_required = Column(Boolean, default=False, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class UserQuizAnswer(Base):
    __tablename__ = "user_quiz_answers"
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    question_id = Column(Integer, ForeignKey("quiz_questions.id", ondelete="CASCADE"), primary_key=True)
    selected_option_index = Column(Integer, nullable=False)
    is_correct = Column(Boolean, nullable=False)
    answered_at = Column(DateTime(timezone=True), server_default=func.now())


class RunVerdict(str, enum.Enum):
    AC = "AC"
    WA = "WA"
    TLE = "TLE"
    CE = "CE"
    RTE = "RTE"
    OOM = "OOM"


class Run(Base):
    __tablename__ = "runs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    exercise_id = Column(Integer, ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False)
    verdict = Column(Enum(RunVerdict), nullable=False)
    passed = Column(Boolean, nullable=False)
    details = Column(JSON, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    memory_kb = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    # Optional traceability fields for submitted code
    code_preview = Column(String, nullable=True)
    code_sha256 = Column(String, nullable=True)


class UserExerciseCompletion(Base):
    __tablename__ = "user_exercise_completions"
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    exercise_id = Column(Integer, ForeignKey("exercises.id", ondelete="CASCADE"), primary_key=True)
    completed_at = Column(DateTime(timezone=True), server_default=func.now())
    attempts_needed = Column(Integer, nullable=False, default=1)
    best_run_id = Column(Integer, ForeignKey("runs.id", ondelete="SET NULL"), nullable=True)


class JobStatus(str, enum.Enum):
    pending = "pending"
    evaluating = "evaluating"
    completed = "completed"
    failed = "failed"


class Job(Base):
    __tablename__ = "jobs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    exercise_id = Column(Integer, ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False)
    code = Column(String, nullable=False)
    status = Column(Enum(JobStatus), default=JobStatus.pending, nullable=False)
    run_id = Column(Integer, ForeignKey("runs.id", ondelete="SET NULL"), nullable=True)
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
