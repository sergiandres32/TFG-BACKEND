from sqlalchemy.orm import Session
from . import models, schemas
from passlib.context import CryptContext
from sqlalchemy.exc import IntegrityError
import json

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()


def create_user(db: Session, user: schemas.UserCreate):
    hashed = pwd_context.hash(user.password)
    db_user = models.User(username=user.username, email=user.email, password_hash=hashed)
    db.add(db_user)
    try:
        db.commit()
        db.refresh(db_user)
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


def create_topic(db: Session, topic: schemas.TopicCreate):
    db_topic = models.Topic(
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


def update_topic(db: Session, topic_id: int, topic_data: schemas.TopicUpdate):
    topic = get_topic_by_id(db, topic_id)
    if not topic:
        return None

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
    exercises = db.query(models.Exercise).order_by(models.Exercise.id.asc()).all()
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


def list_quiz_questions(db: Session, topic_id: int | None = None):
    query = db.query(models.QuizQuestion)
    if topic_id is not None:
        query = query.filter(models.QuizQuestion.topic_id == topic_id)
    return query.order_by(models.QuizQuestion.id.asc()).all()


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


def get_leaderboard(db: Session, limit: int = 50):
    # count completions per user and latest completion timestamp
    from sqlalchemy import func
    q = db.query(models.User.id, models.User.username, func.count(models.UserExerciseCompletion.exercise_id).label('completed_count'), func.max(models.UserExerciseCompletion.completed_at).label('last_completed_at'))
    q = q.join(models.UserExerciseCompletion, models.User.id == models.UserExerciseCompletion.user_id, isouter=True)
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
    db_run = models.Run(
        user_id=user_id,
        exercise_id=exercise_id,
        verdict=verdict,
        passed=passed,
        details={
            "results": judge_result.get("results"),
            "compile_error": judge_result.get("compile_error"),
        },
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


def get_user_progress(db: Session, user_id: int):
    """
    Retorna estadísticas de progreso del usuario.
    """
    from sqlalchemy import func
    
    # Total de ejercicios
    total_exercises = db.query(func.count(models.Exercise.id)).scalar() or 0
    
    # Ejercicios completados por el usuario
    completed = db.query(
        models.UserExerciseCompletion.exercise_id,
        models.Exercise.title,
        models.UserExerciseCompletion.completed_at,
        models.UserExerciseCompletion.attempts_needed
    ).join(
        models.Exercise,
        models.UserExerciseCompletion.exercise_id == models.Exercise.id
    ).filter(models.UserExerciseCompletion.user_id == user_id).all()
    
    completed_count = len(completed)
    
    # Total de attempts del usuario
    total_attempts = db.query(func.count(models.Run.id)).filter(models.Run.user_id == user_id).scalar() or 0
    
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


def get_user_submissions(db: Session, user_id: int, limit: int = 50):
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
    ).filter(models.Job.user_id == user_id).order_by(models.Job.created_at.desc()).limit(limit).all()
    
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
