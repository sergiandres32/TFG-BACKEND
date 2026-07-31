import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.api import crud, models
from src.api.database import SessionLocal


def load_tests_file(file_path: Path) -> dict:
    with file_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def create_teacher(db, username: str, email: str, password: str) -> models.User:
    teacher = models.User(
        username=username,
        email=email,
        password_hash=crud.pwd_context.hash(password),
        role=models.RoleEnum.teacher,
        is_active=True,
    )
    db.add(teacher)
    db.commit()
    db.refresh(teacher)
    return teacher


def create_student(db, username: str, email: str, password: str) -> models.User:
    student = models.User(
        username=username,
        email=email,
        password_hash=crud.pwd_context.hash(password),
        role=models.RoleEnum.student,
        is_active=True,
    )
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


def create_subject(db, *, code: str, name: str, is_active: bool = True) -> models.Subject:
    subject = models.Subject(code=code, name=name, is_active=is_active)
    db.add(subject)
    db.commit()
    db.refresh(subject)
    return subject


def enroll_user_in_subject(
    db,
    *,
    user_id: int,
    subject_id: int,
    role_in_subject: models.RoleEnum = models.RoleEnum.student,
) -> models.UserSubjectEnrollment:
    enrollment = models.UserSubjectEnrollment(
        user_id=user_id,
        subject_id=subject_id,
        role_in_subject=role_in_subject,
    )
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)
    return enrollment


def create_topic(
    db,
    *,
    subject_id: int,
    name: str,
    description: str,
    weight: float,
    required_beginner: int = 0,
    required_mid: int = 0,
    required_expert: int = 0,
) -> models.Topic:
    topic = models.Topic(
        subject_id=subject_id,
        name=name,
        description=description,
        weight=weight,
        required_beginner=required_beginner,
        required_mid=required_mid,
        required_expert=required_expert,
    )
    db.add(topic)
    db.commit()
    db.refresh(topic)
    return topic


def create_exercise_with_tests(
    db,
    *,
    teacher_id: int,
    topic_id: int,
    title: str,
    level: models.ExerciseLevel,
    tests_payload: dict | None,
    description: str | None = None,
) -> tuple[models.Exercise, int]:
    if not description and tests_payload:
        description = tests_payload.get("description") or tests_payload.get("name", title)
    if not description:
        description = title

    exercise = models.Exercise(
        topic_id=topic_id,
        title=title,
        description=description,
        level=level,
        created_by=teacher_id,
    )
    db.add(exercise)
    db.commit()
    db.refresh(exercise)

    created_tests = 0
    for index, test in enumerate((tests_payload or {}).get("tests", []), start=1):
        test_case = models.TestCase(
            exercise_id=exercise.id,
            name=test.get("id") or f"{title}_{index}",
            content={
                "input": test.get("input", ""),
                "expected": test.get("expected", ""),
                "mode": test.get("mode", "exact"),
                "ignore_whitespace": test.get("ignore_whitespace", False),
            },
            hidden=bool(test.get("hidden", False)),
        )
        db.add(test_case)
        created_tests += 1

    db.commit()
    return exercise, created_tests


def create_quiz_question(
    db,
    *,
    topic_id: int,
    level: models.ExerciseLevel,
    statement: str,
    options: list[str],
    correct_option_index: int,
    created_by: int,
    is_required: bool = False,
) -> models.QuizQuestion:
    question = models.QuizQuestion(
        topic_id=topic_id,
        level=level,
        statement=statement,
        options=options,
        correct_option_index=correct_option_index,
        is_required=is_required,
        created_by=created_by,
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    return question


def create_quiz_answer(db, *, user_id: int, question: models.QuizQuestion, selected_option_index: int) -> models.UserQuizAnswer:
    answer = models.UserQuizAnswer(
        user_id=user_id,
        question_id=question.id,
        selected_option_index=selected_option_index,
        is_correct=selected_option_index == int(question.correct_option_index),
    )
    db.add(answer)
    db.commit()
    db.refresh(answer)
    return answer


def create_run(
    db,
    *,
    user_id: int,
    exercise_id: int,
    verdict: models.RunVerdict,
    passed: bool,
    details: dict,
) -> models.Run:
    run = models.Run(
        user_id=user_id,
        exercise_id=exercise_id,
        verdict=verdict,
        passed=passed,
        details=details,
        duration_ms=20 if passed else 35,
        memory_kb=512,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def create_completion(db, *, user_id: int, exercise_id: int, best_run_id: int) -> models.UserExerciseCompletion:
    completion = models.UserExerciseCompletion(
        user_id=user_id,
        exercise_id=exercise_id,
        attempts_needed=1,
        best_run_id=best_run_id,
    )
    db.add(completion)
    db.commit()
    db.refresh(completion)
    return completion


def seed_database(teacher_username: str, teacher_email: str, teacher_password: str) -> None:
    sum_tests_path = ROOT_DIR / "test_cases" / "sum" / "tests.json"
    sort_words_tests_path = ROOT_DIR / "test_cases" / "sort_words" / "tests.json"

    if not sum_tests_path.exists() or not sort_words_tests_path.exists():
        raise FileNotFoundError("No se encontraron test_cases/sum/tests.json o test_cases/sort_words/tests.json")

    sum_payload = load_tests_file(sum_tests_path)
    sort_words_payload = load_tests_file(sort_words_tests_path)

    db = SessionLocal()
    try:
        teacher = create_teacher(
            db,
            username=teacher_username,
            email=teacher_email,
            password=teacher_password,
        )

        paco_subject = create_subject(
            db,
            code="PACO",
            name="Programacio Avancada en C",
        )
        adso_subject = create_subject(
            db,
            code="ADSO",
            name="Administracio de Sistemes i Xarxes",
        )

        enroll_user_in_subject(
            db,
            user_id=teacher.id,
            subject_id=paco_subject.id,
            role_in_subject=models.RoleEnum.teacher,
        )
        enroll_user_in_subject(
            db,
            user_id=teacher.id,
            subject_id=adso_subject.id,
            role_in_subject=models.RoleEnum.teacher,
        )

        perfect_student = create_student(
            db,
            username="alumno_perfecto",
            email="alumno_perfecto@jutge.local",
            password="alumno123",
        )
        failing_student = create_student(
            db,
            username="alumno_falla",
            email="alumno_falla@jutge.local",
            password="alumno123",
        )
        basic_student = create_student(
            db,
            username="alumno_a_base",
            email="alumno_a_base@example.com",
            password="alumno123",
        )

        enroll_user_in_subject(db, user_id=perfect_student.id, subject_id=paco_subject.id)
        enroll_user_in_subject(db, user_id=failing_student.id, subject_id=paco_subject.id)
        enroll_user_in_subject(db, user_id=basic_student.id, subject_id=paco_subject.id)

        basics_topic = create_topic(
            db,
            subject_id=paco_subject.id,
            name="Basics",
            description="Tema inicial amb càlcul bàsic i preguntes senzilles.",
            weight=1.0,
            required_beginner=1,
            required_mid=0,
            required_expert=0,
        )
        process_topic = create_topic(
            db,
            subject_id=paco_subject.id,
            name="Processos",
            description="Tema de processos i ordenació.",
            weight=1.0,
            required_beginner=0,
            required_mid=1,
            required_expert=0,
        )
        empty_topic = create_topic(
            db,
            subject_id=paco_subject.id,
            name="Signals",
            description="Tema de prova sense preguntes tipus test.",
            weight=1.0,
            required_beginner=0,
            required_mid=0,
            required_expert=0,
        )

        math_exercise, math_count = create_exercise_with_tests(
            db,
            teacher_id=teacher.id,
            topic_id=basics_topic.id,
            title="math",
            level=models.ExerciseLevel.beginner,
            tests_payload=sum_payload,
            description="Exercici de sumes senzilles.",
        )
        sort_exercise, sort_count = create_exercise_with_tests(
            db,
            teacher_id=teacher.id,
            topic_id=process_topic.id,
            title="sort",
            level=models.ExerciseLevel.mid,
            tests_payload=sort_words_payload,
            description="Exercici d'ordenació de paraules.",
        )
        no_tests_exercise, no_tests_count = create_exercise_with_tests(
            db,
            teacher_id=teacher.id,
            topic_id=empty_topic.id,
            title="sense_tests",
            level=models.ExerciseLevel.expert,
            tests_payload=None,
            description="Exercici sense joc de prova per validar el panell.",
        )

        basics_questions = [
            create_quiz_question(
                db,
                topic_id=basics_topic.id,
                level=models.ExerciseLevel.beginner,
                statement="Quant és 2 + 3?",
                options=["4", "5", "6"],
                correct_option_index=1,
                created_by=teacher.id,
                is_required=False,
            ),
            create_quiz_question(
                db,
                topic_id=basics_topic.id,
                level=models.ExerciseLevel.beginner,
                statement="Quin operador s'utilitza per sumar en C?",
                options=["+", "-", "*"],
                correct_option_index=0,
                created_by=teacher.id,
                is_required=False,
            ),
        ]
        process_questions = [
            create_quiz_question(
                db,
                topic_id=process_topic.id,
                level=models.ExerciseLevel.mid,
                statement="Quin resultat és correcte després d'ordenar apple, zebra?",
                options=["zebra apple", "apple zebra", "apple apple"],
                correct_option_index=1,
                created_by=teacher.id,
                is_required=False,
            ),
            create_quiz_question(
                db,
                topic_id=process_topic.id,
                level=models.ExerciseLevel.mid,
                statement="Ordenar una sola paraula canvia la sortida?",
                options=["Sí", "No"],
                correct_option_index=1,
                created_by=teacher.id,
                is_required=False,
            ),
        ]

        for question in basics_questions + process_questions:
            create_quiz_answer(
                db,
                user_id=perfect_student.id,
                question=question,
                selected_option_index=int(question.correct_option_index),
            )
            wrong_index = 0 if int(question.correct_option_index) != 0 else 1
            create_quiz_answer(
                db,
                user_id=failing_student.id,
                question=question,
                selected_option_index=wrong_index,
            )

        perfect_math_run = create_run(
            db,
            user_id=perfect_student.id,
            exercise_id=math_exercise.id,
            verdict=models.RunVerdict.AC,
            passed=True,
            details={"seed": True, "exercise": "math", "result": "perfect"},
        )
        perfect_sort_run = create_run(
            db,
            user_id=perfect_student.id,
            exercise_id=sort_exercise.id,
            verdict=models.RunVerdict.AC,
            passed=True,
            details={"seed": True, "exercise": "sort", "result": "perfect"},
        )
        create_completion(
            db,
            user_id=perfect_student.id,
            exercise_id=math_exercise.id,
            best_run_id=perfect_math_run.id,
        )
        create_completion(
            db,
            user_id=perfect_student.id,
            exercise_id=sort_exercise.id,
            best_run_id=perfect_sort_run.id,
        )

        create_run(
            db,
            user_id=failing_student.id,
            exercise_id=math_exercise.id,
            verdict=models.RunVerdict.WA,
            passed=False,
            details={"seed": True, "exercise": "math", "result": "failed"},
        )
        create_run(
            db,
            user_id=failing_student.id,
            exercise_id=sort_exercise.id,
            verdict=models.RunVerdict.WA,
            passed=False,
            details={"seed": True, "exercise": "sort", "result": "failed"},
        )

        print("Seed completado ✅")
        print(f"Profesor: id={teacher.id}, username={teacher.username}, email={teacher.email}")
        print(f"Asignatura PACO: id={paco_subject.id}, code={paco_subject.code}")
        print(f"Asignatura ADSO: id={adso_subject.id}, code={adso_subject.code} (sin temas ni alumnos)")
        print(f"Alumno base: id={basic_student.id}, username={basic_student.username}")
        print(f"Alumno perfecto: id={perfect_student.id}, username={perfect_student.username}")
        print(f"Alumno fallo: id={failing_student.id}, username={failing_student.username}")
        print(f"Tema Basics: id={basics_topic.id}, ejercicio math id={math_exercise.id}, tests={math_count}, preguntas={len(basics_questions)}")
        print(f"Tema Processos: id={process_topic.id}, ejercicio sort id={sort_exercise.id}, tests={sort_count}, preguntas={len(process_questions)}")
        print(f"Tema Signals: id={empty_topic.id}, ejercicio sense_tests id={no_tests_exercise.id}, tests={no_tests_count}")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--teacher-username", default="profesor_seed")
    parser.add_argument("--teacher-email", default="profesor_seed@jutge.local")
    parser.add_argument("--teacher-password", default="profesor123")
    args = parser.parse_args()

    seed_database(
        teacher_username=args.teacher_username,
        teacher_email=args.teacher_email,
        teacher_password=args.teacher_password,
    )


if __name__ == "__main__":
    main()
