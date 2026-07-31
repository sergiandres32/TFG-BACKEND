from sqlalchemy.orm import Session
from . import models, schemas
from passlib.context import CryptContext
from sqlalchemy.exc import IntegrityError
import json
import hashlib
import secrets
import re

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _slugify_for_username(raw: str, max_len: int = 24) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_]+", "_", (raw or "").strip()).strip("_").lower()
    if not cleaned:
        cleaned = "lti_user"
    return cleaned[:max_len]


def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()


def upsert_lti_platform(db: Session, payload: schemas.LtiPlatformCreate):
    existing = db.query(models.LtiPlatform).filter(models.LtiPlatform.name == payload.name.strip()).first()
    if existing:
        existing.consumer_key = payload.consumer_key.strip()
        existing.consumer_secret = payload.consumer_secret
        existing.is_active = bool(payload.is_active)
        db.commit()
        db.refresh(existing)
        return existing

    platform = models.LtiPlatform(
        name=payload.name.strip(),
        consumer_key=payload.consumer_key.strip(),
        consumer_secret=payload.consumer_secret,
        is_active=bool(payload.is_active),
    )
    db.add(platform)
    try:
        db.commit()
        db.refresh(platform)
        return platform
    except IntegrityError:
        db.rollback()
        return None


def list_lti_platforms(db: Session):
    return db.query(models.LtiPlatform).order_by(models.LtiPlatform.id.asc()).all()


def get_active_lti_platform_by_consumer_key(db: Session, consumer_key: str):
    return (
        db.query(models.LtiPlatform)
        .filter(models.LtiPlatform.consumer_key == consumer_key, models.LtiPlatform.is_active == True)
        .first()
    )


def get_lti_context_subject_link(db: Session, platform_id: int, context_id: str):
    return (
        db.query(models.LtiContextSubjectLink)
        .filter(
            models.LtiContextSubjectLink.platform_id == platform_id,
            models.LtiContextSubjectLink.context_id == context_id,
            models.LtiContextSubjectLink.is_active == True,
        )
        .first()
    )


def _create_lti_backed_user(db: Session, platform_name: str, lti_user_id: str, display_name: str, email: str | None, role: models.RoleEnum):
    username_base = _slugify_for_username(f"{platform_name}_{lti_user_id}")
    username = username_base
    suffix = 1
    while get_user_by_username(db, username):
        username = f"{username_base}_{suffix}"
        suffix += 1

    normalized_email = (email or "").strip().lower()
    if not normalized_email:
        normalized_email = f"{username}@lti.local"
    else:
        existing_email = db.query(models.User).filter(models.User.email == normalized_email).first()
        if existing_email:
            normalized_email = f"{username}@lti.local"

    random_password = secrets.token_urlsafe(32)
    password_hash = pwd_context.hash(random_password)
    user = models.User(
        username=username,
        email=normalized_email,
        password_hash=password_hash,
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def resolve_or_create_lti_user(
    db: Session,
    platform: models.LtiPlatform,
    lti_user_id: str,
    display_name: str,
    email: str | None,
    is_instructor: bool,
):
    link = (
        db.query(models.LtiUserLink)
        .filter(models.LtiUserLink.platform_id == platform.id, models.LtiUserLink.lti_user_id == lti_user_id)
        .first()
    )
    if link:
        user = db.query(models.User).filter(models.User.id == link.user_id).first()
        if user:
            # Keep teacher privilege if ever received from LMS.
            if is_instructor and user.role != models.RoleEnum.teacher:
                user.role = models.RoleEnum.teacher
            db.commit()
            return user

    role = models.RoleEnum.teacher if is_instructor else models.RoleEnum.student
    user = _create_lti_backed_user(
        db,
        platform_name=platform.name,
        lti_user_id=lti_user_id,
        display_name=display_name,
        email=email,
        role=role,
    )
    link = models.LtiUserLink(platform_id=platform.id, lti_user_id=lti_user_id, user_id=user.id)
    db.add(link)
    db.commit()
    return user


def resolve_or_create_subject_for_lti_context(
    db: Session,
    platform: models.LtiPlatform,
    context_id: str,
    context_title: str | None,
    allow_auto_create: bool,
):
    mapping = get_lti_context_subject_link(db, platform.id, context_id)
    if mapping:
        subject = get_subject_by_id(db, int(mapping.subject_id))
        if subject and bool(subject.is_active):
            return subject, mapping, "existing"

    if not allow_auto_create:
        return None, None, "missing_mapping"

    code_base = _slugify_for_username(f"LTI_{platform.name}_{context_id}", max_len=32).upper()
    code = code_base or "LTI_CTX"
    idx = 1
    while db.query(models.Subject).filter(models.Subject.code == code).first() is not None:
        code = f"{code_base[:28]}_{idx}"
        idx += 1

    name = (context_title or f"LTI {context_id}").strip()[:120]
    if not name:
        name = f"LTI {context_id}"

    subject = models.Subject(code=code, name=name, is_active=True, enrollment_password_hash=None)
    db.add(subject)
    db.commit()
    db.refresh(subject)

    mapping = models.LtiContextSubjectLink(
        platform_id=platform.id,
        context_id=context_id,
        context_title=context_title,
        subject_id=subject.id,
        is_active=True,
    )
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    return subject, mapping, "created"


def upsert_user_subject_enrollment_role(db: Session, user_id: int, subject_id: int, role_in_subject: models.RoleEnum):
    enrollment = (
        db.query(models.UserSubjectEnrollment)
        .filter(
            models.UserSubjectEnrollment.user_id == user_id,
            models.UserSubjectEnrollment.subject_id == subject_id,
        )
        .first()
    )
    if not enrollment:
        enrollment = models.UserSubjectEnrollment(
            user_id=user_id,
            subject_id=subject_id,
            role_in_subject=role_in_subject,
        )
        db.add(enrollment)
        db.commit()
        db.refresh(enrollment)
        return enrollment

    enrollment.role_in_subject = role_in_subject
    db.commit()
    db.refresh(enrollment)
    return enrollment


def create_lti_launch_event(
    db: Session,
    *,
    platform_id: int | None,
    lti_user_id: str | None,
    context_id: str | None,
    resource_link_id: str | None,
    roles: str | None,
    user_id: int | None,
    subject_id: int | None,
    outcome: str,
    details: dict | None = None,
):
    event = models.LtiLaunchEvent(
        platform_id=platform_id,
        lti_user_id=lti_user_id,
        context_id=context_id,
        resource_link_id=resource_link_id,
        roles=roles,
        user_id=user_id,
        subject_id=subject_id,
        outcome=outcome,
        details=details,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def create_user(db: Session, user: schemas.UserCreate):
    hashed = pwd_context.hash(user.password)
    db_user = models.User(username=user.username, email=user.email, password_hash=hashed)
    db.add(db_user)
    try:
        db.commit()
        db.refresh(db_user)

        # Default enrollment keeps legacy UX: newly registered users can see one subject.
        default_subject = (
            db.query(models.Subject)
            .filter(models.Subject.is_active == True, models.Subject.code != "LEGACY")
            .order_by(models.Subject.id.asc())
            .first()
        )
        if not default_subject:
            default_subject = (
                db.query(models.Subject)
                .filter(models.Subject.is_active == True)
                .order_by(models.Subject.id.asc())
                .first()
            )
        if default_subject:
            existing = (
                db.query(models.UserSubjectEnrollment)
                .filter(
                    models.UserSubjectEnrollment.user_id == db_user.id,
                    models.UserSubjectEnrollment.subject_id == default_subject.id,
                )
                .first()
            )
            if not existing:
                db.add(
                    models.UserSubjectEnrollment(
                        user_id=db_user.id,
                        subject_id=default_subject.id,
                        role_in_subject=models.RoleEnum.student,
                    )
                )
                db.commit()

        return db_user
    except IntegrityError:
        db.rollback()
        return None


def authenticate_user(db: Session, username: str, password: str):
    user = get_user_by_username(db, username)
    if not user:
        return None
    if not pwd_context.verify(password, user.password_hash):
        return None
    return user


def list_students(db: Session):
    return (
        db.query(models.User)
        .filter(models.User.role == models.RoleEnum.student)
        .order_by(models.User.id.asc())
        .all()
    )


def list_students_by_subject(db: Session, subject_id: int):
    return (
        db.query(models.User)
        .join(models.UserSubjectEnrollment, models.UserSubjectEnrollment.user_id == models.User.id)
        .filter(
            models.User.role == models.RoleEnum.student,
            models.UserSubjectEnrollment.subject_id == subject_id,
        )
        .order_by(models.User.id.asc())
        .all()
    )


def get_subject_by_id(db: Session, subject_id: int):
    return db.query(models.Subject).filter(models.Subject.id == subject_id).first()


def list_subjects_for_user(db: Session, user_id: int):
    subjects = (
        db.query(models.Subject)
        .join(models.UserSubjectEnrollment, models.UserSubjectEnrollment.subject_id == models.Subject.id)
        .filter(models.UserSubjectEnrollment.user_id == user_id, models.Subject.is_active == True)
        .order_by(models.Subject.id.asc())
        .all()
    )
    non_legacy = [subject for subject in subjects if str(subject.code).upper() != "LEGACY"]
    return non_legacy if non_legacy else subjects


def create_subject_with_owner(db: Session, payload: schemas.SubjectCreate, owner_user_id: int):
    password = (payload.enrollment_password or "").strip()
    password_hash = pwd_context.hash(password) if password else None

    subject = models.Subject(
        code=payload.code.strip(),
        name=payload.name.strip(),
        is_active=bool(payload.is_active),
        enrollment_password_hash=password_hash,
    )
    db.add(subject)
    try:
        db.commit()
        db.refresh(subject)
    except IntegrityError:
        db.rollback()
        return None

    existing = (
        db.query(models.UserSubjectEnrollment)
        .filter(
            models.UserSubjectEnrollment.user_id == owner_user_id,
            models.UserSubjectEnrollment.subject_id == subject.id,
        )
        .first()
    )
    if not existing:
        db.add(
            models.UserSubjectEnrollment(
                user_id=owner_user_id,
                subject_id=subject.id,
                role_in_subject=models.RoleEnum.teacher,
            )
        )
        db.commit()

    return subject


def list_subject_catalog_for_user(db: Session, user_id: int, include_inactive: bool = False):
    query = db.query(models.Subject)
    if not include_inactive:
        query = query.filter(models.Subject.is_active == True)
    subjects = query.order_by(models.Subject.id.asc()).all()
    enrolled_ids = set(get_enrolled_subject_ids_for_user(db, user_id))
    rows = []
    for subject in subjects:
        rows.append(
            {
                "id": subject.id,
                "code": subject.code,
                "name": subject.name,
                "is_active": bool(subject.is_active),
                "is_enrolled": subject.id in enrolled_ids,
                "requires_password": bool(subject.enrollment_password_hash),
            }
        )
    return rows


def assign_user_to_subject(db: Session, user_id: int, subject_id: int, role_in_subject: models.RoleEnum = models.RoleEnum.student):
    subject = get_subject_by_id(db, subject_id)
    if not subject:
        return None, "subject_not_found"

    existing = (
        db.query(models.UserSubjectEnrollment)
        .filter(
            models.UserSubjectEnrollment.user_id == user_id,
            models.UserSubjectEnrollment.subject_id == subject_id,
        )
        .first()
    )
    if existing:
        return existing, "already_assigned"

    enrollment = models.UserSubjectEnrollment(
        user_id=user_id,
        subject_id=subject_id,
        role_in_subject=role_in_subject,
    )
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)
    return enrollment, "assigned"


def unassign_user_from_subject(db: Session, user_id: int, subject_id: int):
    enrollment = (
        db.query(models.UserSubjectEnrollment)
        .filter(
            models.UserSubjectEnrollment.user_id == user_id,
            models.UserSubjectEnrollment.subject_id == subject_id,
        )
        .first()
    )
    if not enrollment:
        return False

    db.delete(enrollment)
    db.commit()
    return True


def update_subject_active(db: Session, subject_id: int, is_active: bool):
    subject = get_subject_by_id(db, subject_id)
    if not subject:
        return None
    subject.is_active = bool(is_active)
    db.commit()
    db.refresh(subject)
    return subject


def update_subject_password(db: Session, subject_id: int, requires_password: bool, enrollment_password: str | None):
    subject = get_subject_by_id(db, subject_id)
    if not subject:
        return None, "subject_not_found"

    if not requires_password:
        subject.enrollment_password_hash = None
        db.commit()
        db.refresh(subject)
        return subject, "updated"

    password = (enrollment_password or "").strip()
    if not password:
        return None, "password_required"

    subject.enrollment_password_hash = pwd_context.hash(password)
    db.commit()
    db.refresh(subject)
    return subject, "updated"


def enroll_student_in_subject(db: Session, user_id: int, subject_id: int, password: str | None):
    subject = get_subject_by_id(db, subject_id)
    if not subject or not bool(subject.is_active):
        return None, "subject_not_found"

    existing = (
        db.query(models.UserSubjectEnrollment)
        .filter(
            models.UserSubjectEnrollment.user_id == user_id,
            models.UserSubjectEnrollment.subject_id == subject_id,
        )
        .first()
    )
    if existing:
        return existing, "already_enrolled"

    if subject.enrollment_password_hash:
        provided = (password or "").strip()
        if not provided:
            return None, "password_required"
        if not pwd_context.verify(provided, subject.enrollment_password_hash):
            return None, "invalid_password"

    enrollment = models.UserSubjectEnrollment(
        user_id=user_id,
        subject_id=subject_id,
        role_in_subject=models.RoleEnum.student,
    )
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)
    return enrollment, "enrolled"


def get_enrolled_subject_ids_for_user(db: Session, user_id: int) -> list[int]:
    rows = (
        db.query(models.UserSubjectEnrollment.subject_id)
        .filter(models.UserSubjectEnrollment.user_id == user_id)
        .all()
    )
    return [int(row.subject_id) for row in rows]


def is_user_enrolled_in_subject(db: Session, user_id: int, subject_id: int) -> bool:
    return (
        db.query(models.UserSubjectEnrollment)
        .filter(
            models.UserSubjectEnrollment.user_id == user_id,
            models.UserSubjectEnrollment.subject_id == subject_id,
        )
        .first()
        is not None
    )


def is_user_teacher_in_subject(db: Session, user_id: int, subject_id: int) -> bool:
    """Return True only if the user has role_in_subject=teacher in the given subject."""
    return (
        db.query(models.UserSubjectEnrollment)
        .filter(
            models.UserSubjectEnrollment.user_id == user_id,
            models.UserSubjectEnrollment.subject_id == subject_id,
            models.UserSubjectEnrollment.role_in_subject == models.RoleEnum.teacher,
        )
        .first()
        is not None
    )


def create_exercise(db: Session, ex: schemas.ExerciseCreate, creator_id: int = None):
    db_ex = models.Exercise(
        topic_id=ex.topic_id,
        title=ex.title,
        description=ex.description,
        level=ex.level,
        is_required=ex.is_required,
        created_by=creator_id,
    )
    db.add(db_ex)
    db.commit()
    db.refresh(db_ex)
    return db_ex


def update_exercise(db: Session, exercise_id: int, ex_data: schemas.ExerciseUpdate):
    exercise = get_exercise_by_id(db, exercise_id)
    if not exercise:
        return None

    exercise.topic_id = ex_data.topic_id
    exercise.title = ex_data.title
    exercise.description = ex_data.description
    exercise.level = ex_data.level
    exercise.is_required = ex_data.is_required
    db.commit()
    db.refresh(exercise)
    return exercise


def delete_exercise(db: Session, exercise_id: int):
    exercise = get_exercise_by_id(db, exercise_id)
    if not exercise:
        return False

    db.delete(exercise)
    db.commit()
    return True


def get_topic_by_id(db: Session, topic_id: int):
    return db.query(models.Topic).filter(models.Topic.id == topic_id).first()


def get_topic_by_name(db: Session, name: str):
    return db.query(models.Topic).filter(models.Topic.name == name).first()


def get_topic_by_name_and_subject(db: Session, subject_id: int, name: str):
    return (
        db.query(models.Topic)
        .filter(models.Topic.subject_id == subject_id, models.Topic.name == name)
        .first()
    )


def create_topic(db: Session, topic: schemas.TopicCreate):
    db_topic = models.Topic(
        subject_id=topic.subject_id,
        name=topic.name,
        description=topic.description,
        weight=topic.weight,
        required_beginner=topic.required_beginner,
        required_mid=topic.required_mid,
        required_expert=topic.required_expert,
    )
    db.add(db_topic)
    try:
        db.commit()
        db.refresh(db_topic)
        return db_topic
    except IntegrityError:
        db.rollback()
        return None


def list_topics(db: Session):
    return db.query(models.Topic).order_by(models.Topic.id.asc()).all()


def list_topics_for_subjects(db: Session, subject_ids: list[int], subject_id: int | None = None):
    if not subject_ids:
        return []
    query = db.query(models.Topic).filter(models.Topic.subject_id.in_(subject_ids))
    if subject_id is not None:
        query = query.filter(models.Topic.subject_id == subject_id)
    return query.order_by(models.Topic.id.asc()).all()


def update_topic(db: Session, topic_id: int, topic_data: schemas.TopicUpdate):
    topic = get_topic_by_id(db, topic_id)
    if not topic:
        return None

    topic.subject_id = topic_data.subject_id
    topic.name = topic_data.name
    topic.description = topic_data.description
    topic.weight = topic_data.weight
    topic.required_beginner = topic_data.required_beginner
    topic.required_mid = topic_data.required_mid
    topic.required_expert = topic_data.required_expert
    try:
        db.commit()
        db.refresh(topic)
        return topic
    except IntegrityError:
        db.rollback()
        return None


def delete_topic(db: Session, topic_id: int):
    topic = get_topic_by_id(db, topic_id)
    if not topic:
        return False

    db.query(models.Exercise).filter(models.Exercise.topic_id == topic_id).update(
        {models.Exercise.topic_id: None},
        synchronize_session=False,
    )
    db.delete(topic)
    db.commit()
    return True


def get_exercise_by_id(db: Session, exercise_id: int):
    return db.query(models.Exercise).filter(models.Exercise.id == exercise_id).first()


def list_exercises_with_completion(db: Session, user_id: int):
    subject_ids = get_enrolled_subject_ids_for_user(db, user_id)
    if not subject_ids:
        return [], set()

    exercises = (
        db.query(models.Exercise)
        .join(models.Topic, models.Topic.id == models.Exercise.topic_id)
        .filter(models.Topic.subject_id.in_(subject_ids))
        .order_by(models.Exercise.id.asc())
        .all()
    )
    completed_ids = {
        row.exercise_id
        for row in db.query(models.UserExerciseCompletion.exercise_id)
        .filter(models.UserExerciseCompletion.user_id == user_id)
        .all()
    }
    return exercises, completed_ids


def get_public_test_cases_for_exercise(db: Session, exercise_id: int):
    return (
        db.query(models.TestCase)
        .filter(models.TestCase.exercise_id == exercise_id, models.TestCase.hidden == False)
        .order_by(models.TestCase.id.asc())
        .all()
    )


def create_test_case(db: Session, tc: schemas.TestCaseCreate):
    db_tc = models.TestCase(exercise_id=tc.exercise_id, name=tc.name, content=tc.content)
    db.add(db_tc)
    db.commit()
    db.refresh(db_tc)
    return db_tc


def get_quiz_question_by_id(db: Session, question_id: int):
    return db.query(models.QuizQuestion).filter(models.QuizQuestion.id == question_id).first()


def list_quiz_questions(db: Session, topic_id: int | None = None, subject_ids: list[int] | None = None):
    query = db.query(models.QuizQuestion).join(models.Topic, models.Topic.id == models.QuizQuestion.topic_id)
    if subject_ids is not None:
        if not subject_ids:
            return []
        query = query.filter(models.Topic.subject_id.in_(subject_ids))
    if topic_id is not None:
        query = query.filter(models.QuizQuestion.topic_id == topic_id)
    return query.order_by(models.QuizQuestion.id.asc()).all()


def get_topic_subject_id(db: Session, topic_id: int) -> int | None:
    row = db.query(models.Topic.subject_id).filter(models.Topic.id == topic_id).first()
    return int(row.subject_id) if row else None


def get_exercise_subject_id(db: Session, exercise_id: int) -> int | None:
    row = (
        db.query(models.Topic.subject_id)
        .join(models.Exercise, models.Exercise.topic_id == models.Topic.id)
        .filter(models.Exercise.id == exercise_id)
        .first()
    )
    return int(row.subject_id) if row else None


def create_quiz_question(db: Session, payload: schemas.QuizQuestionCreate, creator_id: int):
    db_question = models.QuizQuestion(
        topic_id=payload.topic_id,
        level=payload.level,
        statement=payload.statement,
        options=payload.options,
        correct_option_index=payload.correct_option_index,
        is_required=payload.is_required,
        created_by=creator_id,
    )
    db.add(db_question)
    db.commit()
    db.refresh(db_question)
    return db_question


def update_quiz_question(db: Session, question_id: int, payload: schemas.QuizQuestionUpdate):
    question = get_quiz_question_by_id(db, question_id)
    if not question:
        return None

    question.level = payload.level
    question.statement = payload.statement
    question.options = payload.options
    question.correct_option_index = payload.correct_option_index
    question.is_required = payload.is_required
    db.commit()
    db.refresh(question)
    return question


def delete_quiz_question(db: Session, question_id: int):
    question = get_quiz_question_by_id(db, question_id)
    if not question:
        return False

    db.delete(question)
    db.commit()
    return True


def upsert_user_quiz_answer(db: Session, user_id: int, question_id: int, selected_option_index: int):
    question = get_quiz_question_by_id(db, question_id)
    if not question:
        return None

    is_correct = selected_option_index == int(question.correct_option_index)
    existing = (
        db.query(models.UserQuizAnswer)
        .filter(
            models.UserQuizAnswer.user_id == user_id,
            models.UserQuizAnswer.question_id == question_id,
        )
        .first()
    )

    if existing:
        existing.selected_option_index = selected_option_index
        existing.is_correct = is_correct
    else:
        existing = models.UserQuizAnswer(
            user_id=user_id,
            question_id=question_id,
            selected_option_index=selected_option_index,
            is_correct=is_correct,
        )
        db.add(existing)

    db.commit()
    db.refresh(existing)
    return existing


def get_topic_students_status(db: Session, topic_id: int):
    topic = get_topic_by_id(db, topic_id)
    if not topic:
        return None

    students = list_students(db)
    completion_rows = (
        db.query(
            models.UserExerciseCompletion.user_id,
            models.Exercise.level,
        )
        .join(models.Exercise, models.Exercise.id == models.UserExerciseCompletion.exercise_id)
        .filter(models.Exercise.topic_id == topic_id)
        .all()
    )

    completions_by_user: dict[int, dict[str, int]] = {}
    for row in completion_rows:
        level = row.level.value if hasattr(row.level, "value") else row.level
        if row.user_id not in completions_by_user:
            completions_by_user[row.user_id] = {"beginner": 0, "mid": 0, "expert": 0}
        if level in completions_by_user[row.user_id]:
            completions_by_user[row.user_id][level] += 1

    results = []
    for student in students:
        student_counts = completions_by_user.get(student.id, {"beginner": 0, "mid": 0, "expert": 0})
        completed_beginner = int(student_counts.get("beginner", 0))
        completed_mid = int(student_counts.get("mid", 0))
        completed_expert = int(student_counts.get("expert", 0))
        beginner_minimum_met = completed_beginner >= int(topic.required_beginner)
        mid_minimum_met = completed_mid >= int(topic.required_mid)
        expert_minimum_met = completed_expert >= int(topic.required_expert)
        topic_minimums_met = beginner_minimum_met and mid_minimum_met and expert_minimum_met

        results.append(
            {
                "user_id": student.id,
                "username": student.username,
                "required_beginner": int(topic.required_beginner),
                "required_mid": int(topic.required_mid),
                "required_expert": int(topic.required_expert),
                "completed_beginner": completed_beginner,
                "completed_mid": completed_mid,
                "completed_expert": completed_expert,
                "beginner_minimum_met": beginner_minimum_met,
                "mid_minimum_met": mid_minimum_met,
                "expert_minimum_met": expert_minimum_met,
                "topic_minimums_met": topic_minimums_met,
            }
        )

    return results


def create_run(db: Session, user_id: int, submission: schemas.SubmissionCreate):
    # evaluate: passed if all results True
    passed = all(submission.results.values())
    verdict = models.RunVerdict.AC if passed else models.RunVerdict.WA
    db_run = models.Run(user_id=user_id, exercise_id=submission.exercise_id, verdict=verdict, passed=passed, details=submission.results)
    db.add(db_run)
    db.commit()
    db.refresh(db_run)

    # if passed and no completion exists, create completion
    if passed:
        existing = db.query(models.UserExerciseCompletion).filter_by(user_id=user_id, exercise_id=submission.exercise_id).first()
        if not existing:
            comp = models.UserExerciseCompletion(user_id=user_id, exercise_id=submission.exercise_id, attempts_needed=1, best_run_id=db_run.id)
            db.add(comp)
            db.commit()
    return db_run


def get_leaderboard(db: Session, limit: int = 50, subject_ids: list[int] | None = None):
    # count completions per user and latest completion timestamp
    from sqlalchemy import func
    q = db.query(models.User.id, models.User.username, func.count(models.UserExerciseCompletion.exercise_id).label('completed_count'), func.max(models.UserExerciseCompletion.completed_at).label('last_completed_at'))
    q = q.join(models.UserExerciseCompletion, models.User.id == models.UserExerciseCompletion.user_id, isouter=True)
    if subject_ids is not None:
        if not subject_ids:
            return []
        q = q.join(models.Exercise, models.Exercise.id == models.UserExerciseCompletion.exercise_id, isouter=True)
        q = q.join(models.Topic, models.Topic.id == models.Exercise.topic_id, isouter=True)
        q = q.filter((models.Topic.subject_id.in_(subject_ids)) | (models.Topic.subject_id.is_(None)))
    q = q.group_by(models.User.id, models.User.username).order_by(func.count(models.UserExerciseCompletion.exercise_id).desc(), func.coalesce(func.max(models.UserExerciseCompletion.completed_at),'1970-01-01').asc())
    return q.limit(limit).all()


def evaluate_submission_with_judge(db: Session, user_id: int, exercise_id: int, code: str, timeout: int = 5):
    """
    Evalúa un submission de código real usando judge_v2.
    Retorna Run result y crea UserExerciseCompletion si todos los tests pasaron.
    """
    try:
        from src import judge_v2
    except ImportError:
        # Fallback: retornar error si judge_v2 no está disponible
        return {
            "error": "Judge module not available",
            "verdict": models.RunVerdict.CE
        }
    
    # Obtener tests del ejercicio
    test_cases = db.query(models.TestCase).filter(models.TestCase.exercise_id == exercise_id).all()
    if not test_cases:
        return {"error": "No test cases found for exercise", "verdict": models.RunVerdict.CE}
    
    # Construir objeto tests en formato que espera judge_v2
    tests_obj = {
        "tests": [
            {
                "id": tc.name,
                "mode": tc.content.get("mode", "exact"),
                "input": tc.content.get("input", ""),
                "expected": tc.content.get("expected", ""),
                "ignore_whitespace": tc.content.get("ignore_whitespace", False)
            }
            for tc in test_cases
        ]
    }
    
    # Evaluar
    judge_result = judge_v2.run_and_evaluate_all_tests(code, tests_obj, timeout=timeout)
    
    # Mapear verdict string a enum
    verdict_str = judge_result.get("verdict", "WA")
    try:
        verdict = models.RunVerdict[verdict_str]
    except KeyError:
        verdict = models.RunVerdict.WA
    
    passed = verdict_str == "AC"
    
    # Crear run en DB
    # Add a short preview and hash of the submitted code for traceability
    code_preview = (code or "")[:1000]
    code_hash = hashlib.sha256((code or "").encode("utf-8")).hexdigest() if code else None

    db_run = models.Run(
        user_id=user_id,
        exercise_id=exercise_id,
        verdict=verdict,
        passed=passed,
        details={
            "results": judge_result.get("results"),
            "compile_error": judge_result.get("compile_error"),
        },
        code_preview=code_preview,
        code_sha256=code_hash,
        duration_ms=judge_result.get("duration_ms")
    )
    db.add(db_run)
    db.commit()
    
    # Crear o actualizar completion si pasó
    if passed:
        existing = db.query(models.UserExerciseCompletion).filter_by(user_id=user_id, exercise_id=exercise_id).first()
        if not existing:
            comp = models.UserExerciseCompletion(
                user_id=user_id,
                exercise_id=exercise_id,
                attempts_needed=1,
                best_run_id=db_run.id
            )
            db.add(comp)
            db.commit()
    
    db.refresh(db_run)
    return {"run": db_run, "judge_result": judge_result, "passed": passed}


def create_job(db: Session, user_id: int, exercise_id: int, code: str):
    """Crea un Job pending para evaluación asincrónica."""
    job = models.Job(user_id=user_id, exercise_id=exercise_id, code=code, status=models.JobStatus.pending)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_pending_jobs(db: Session, limit: int = 10):
    """Obtiene jobs pendientes para evaluar."""
    return db.query(models.Job).filter(models.Job.status == models.JobStatus.pending).limit(limit).all()


def update_job_to_evaluating(db: Session, job_id: int):
    """Marca job como 'evaluating'."""
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if job:
        job.status = models.JobStatus.evaluating
        job.started_at = json.dumps({"current_timestamp": True})  # Will be overwritten
        from datetime import datetime
        job.started_at = datetime.utcnow()
        db.commit()
        db.refresh(job)
    return job


def update_job_completed(db: Session, job_id: int, run_id: int):
    """Marca job como 'completed' y linkea con run."""
    from datetime import datetime
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if job:
        job.status = models.JobStatus.completed
        job.run_id = run_id
        job.completed_at = datetime.utcnow()
        db.commit()
        db.refresh(job)
    return job


def update_job_failed(db: Session, job_id: int, error_msg: str):
    """Marca job como 'failed' con mensaje de error."""
    from datetime import datetime
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if job:
        job.status = models.JobStatus.failed
        job.error_message = error_msg
        job.completed_at = datetime.utcnow()
        db.commit()
        db.refresh(job)
    return job


def get_job_result(db: Session, job_id: int):
    """Obtiene resultado de un job (Run si completed, o estado pendiente)."""
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        return None
    
    if job.status == models.JobStatus.completed and job.run_id:
        run = db.query(models.Run).filter(models.Run.id == job.run_id).first()
        return {"job": job, "run": run, "status": "completed"}
    
    return {"job": job, "run": None, "status": job.status.value}


def get_user_leaderboard_rank(db: Session, user_id: int):
    """
    Retorna (rank, total_completed) de un usuario en el leaderboard.
    Rank 1 es el mejor.
    """
    from sqlalchemy import func
    
    # Query para obtener ranking: usuarios ordenados por completions DESC, luego por fecha ASC
    leaderboard = db.query(
        models.User.id,
        models.User.username,
        func.count(models.UserExerciseCompletion.exercise_id).label('completed_count'),
        func.max(models.UserExerciseCompletion.completed_at).label('last_completed_at')
    ).join(
        models.UserExerciseCompletion,
        models.User.id == models.UserExerciseCompletion.user_id,
        isouter=True
    ).group_by(
        models.User.id,
        models.User.username
    ).order_by(
        func.count(models.UserExerciseCompletion.exercise_id).desc(),
        func.coalesce(func.max(models.UserExerciseCompletion.completed_at), '1970-01-01').asc()
    ).all()
    
    # Encontrar posición del usuario
    for rank, (uid, username, completed_count, last_completed_at) in enumerate(leaderboard, 1):
        if uid == user_id:
            return rank, completed_count or 0
    
    # Si no está en el leaderboard, retorna sin rank
    return None, 0


def get_user_progress(db: Session, user_id: int, subject_ids: list[int] | None = None):
    """
    Retorna estadísticas de progreso del usuario.
    """
    from sqlalchemy import func
    
    # Total de ejercicios
    exercises_query = db.query(models.Exercise.id)
    if subject_ids is not None:
        if not subject_ids:
            return {
                "completed_exercises_count": 0,
                "total_exercises": 0,
                "total_attempts": 0,
                "completion_rate": 0.0,
                "completed_exercises": [],
            }
        exercises_query = (
            exercises_query
            .join(models.Topic, models.Topic.id == models.Exercise.topic_id)
            .filter(models.Topic.subject_id.in_(subject_ids))
        )
    total_exercises = exercises_query.count() or 0
    
    # Ejercicios completados por el usuario
    completed = db.query(
        models.UserExerciseCompletion.exercise_id,
        models.Exercise.title,
        models.UserExerciseCompletion.completed_at,
        models.UserExerciseCompletion.attempts_needed
    ).join(
        models.Exercise,
        models.UserExerciseCompletion.exercise_id == models.Exercise.id
    ).filter(models.UserExerciseCompletion.user_id == user_id)
    if subject_ids is not None:
        completed = completed.join(models.Topic, models.Topic.id == models.Exercise.topic_id).filter(models.Topic.subject_id.in_(subject_ids))
    completed = completed.all()
    
    completed_count = len(completed)
    
    # Total de attempts del usuario
    attempts_query = db.query(func.count(models.Run.id)).filter(models.Run.user_id == user_id)
    if subject_ids is not None:
        attempts_query = (
            attempts_query
            .join(models.Exercise, models.Exercise.id == models.Run.exercise_id)
            .join(models.Topic, models.Topic.id == models.Exercise.topic_id)
            .filter(models.Topic.subject_id.in_(subject_ids))
        )
    total_attempts = attempts_query.scalar() or 0
    
    completion_rate = completed_count / total_exercises if total_exercises > 0 else 0.0
    
    completed_list = [
        {
            "exercise_id": c[0],
            "exercise_title": c[1],
            "completed_at": c[2].isoformat() if c[2] else None,
            "attempts_needed": c[3]
        }
        for c in completed
    ]
    
    return {
        "completed_exercises_count": completed_count,
        "total_exercises": total_exercises,
        "total_attempts": total_attempts,
        "completion_rate": round(completion_rate, 2),
        "completed_exercises": completed_list
    }


def get_user_submissions(db: Session, user_id: int, limit: int = 50, subject_ids: list[int] | None = None):
    """
    Retorna historial de submissions (jobs) del usuario.
    """
    jobs = db.query(
        models.Job.id,
        models.Job.exercise_id,
        models.Exercise.title,
        models.Job.status,
        models.Job.created_at
    ).join(
        models.Exercise,
        models.Job.exercise_id == models.Exercise.id
    ).filter(models.Job.user_id == user_id)
    if subject_ids is not None:
        if not subject_ids:
            return []
        jobs = jobs.join(models.Topic, models.Topic.id == models.Exercise.topic_id).filter(models.Topic.subject_id.in_(subject_ids))
    jobs = jobs.order_by(models.Job.created_at.desc()).limit(limit).all()
    
    submissions = []
    for job_id, exercise_id, exercise_title, status, created_at in jobs:
        # Obtener run si el job está completado
        job_row = db.query(models.Job).filter(models.Job.id == job_id).first()
        run = None
        if job_row and job_row.run_id:
            run = db.query(models.Run).filter(models.Run.id == job_row.run_id).first()
        
        verdict = None
        passed_all = None
        completed_at = None
        if run:
            verdict = run.verdict.value if hasattr(run.verdict, "value") else run.verdict
            passed_all = run.passed
            completed_at = job_row.completed_at
        
        submissions.append({
            "job_id": job_id,
            "exercise_id": exercise_id,
            "exercise_title": exercise_title,
            "status": status.value if hasattr(status, "value") else status,
            "verdict": verdict,
            "passed_all": passed_all,
            "created_at": created_at.isoformat() if created_at else None,
            "completed_at": completed_at.isoformat() if completed_at else None
        })
    
    return submissions
