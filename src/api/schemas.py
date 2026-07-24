from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional, Dict, Any


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "username": "alumno_nuevo",
                "email": "alumno@example.com",
                "password": "pass123",
            }
        }
    )


class UserOut(BaseModel):
    id: int
    username: str
    email: EmailStr
    role: str

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 5,
                "username": "alumno_nuevo",
                "email": "alumno@example.com",
                "role": "student",
            }
        },
    )


class StudentListItem(BaseModel):
    id: int
    username: str
    email: str
    role: str

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 3,
                "username": "alumno_a_base",
                "email": "alumno_a_base@example.com",
                "role": "student",
            }
        },
    )


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
            }
        }
    )


class ExerciseCreate(BaseModel):
    title: str
    description: Optional[str]
    level: str
    topic_id: Optional[int] = None
    is_required: bool = False

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "Fibonacci",
                "description": "Calculate nth Fibonacci number",
                "level": "expert",
                "topic_id": 1,
                "is_required": False,
            }
        }
    )


class ExerciseUpdate(BaseModel):
    title: str
    description: Optional[str]
    level: str
    topic_id: Optional[int] = None
    is_required: bool = False

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "Fibonacci",
                "description": "Calculate nth Fibonacci number",
                "level": "expert",
                "topic_id": 1,
                "is_required": False,
            }
        }
    )


class ExerciseListItem(BaseModel):
    id: int
    topic_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    level: str
    is_required: bool
    completed: bool

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": 1,
                "topic_id": 1,
                "title": "sum",
                "description": "Sum two integers",
                "level": "beginner",
                "is_required": False,
                "completed": True,
            }
        }
    )


class ExercisePublicTestCase(BaseModel):
    id: int
    name: str
    content: Dict[str, Any]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": 1,
                "name": "sum_1",
                "content": {
                    "input": "2 3\\n",
                    "expected": "5\\n",
                    "mode": "exact",
                },
            }
        }
    )


class ExerciseDetail(BaseModel):
    id: int
    topic_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    level: str
    is_required: bool
    completed: bool
    public_test_cases: list[ExercisePublicTestCase]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": 1,
                "topic_id": 1,
                "title": "sum",
                "description": "Sum two integers",
                "level": "beginner",
                "is_required": False,
                "completed": True,
                "public_test_cases": [
                    {
                        "id": 1,
                        "name": "sum_1",
                        "content": {
                            "input": "2 3\\n",
                            "expected": "5\\n",
                            "mode": "exact",
                        },
                    }
                ],
            }
        }
    )


class TopicCreate(BaseModel):
    subject_id: int
    name: str
    description: Optional[str] = None
    weight: float = 1.0
    required_beginner: int = 0
    required_mid: int = 0
    required_expert: int = 0

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "subject_id": 1,
                "name": "Punteros",
                "description": "Tema sobre punteros en C",
                "weight": 2.0,
            }
        }
    )


class TopicOut(BaseModel):
    id: int
    subject_id: int
    name: str
    description: Optional[str] = None
    weight: float
    required_beginner: int
    required_mid: int
    required_expert: int

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "subject_id": 1,
                "name": "Punteros",
                "description": "Tema sobre punteros en C",
                "weight": 2.0,
            }
        },
    )


class TopicUpdate(BaseModel):
    subject_id: int
    name: str
    description: Optional[str] = None
    weight: float = 1.0
    required_beginner: int = 0
    required_mid: int = 0
    required_expert: int = 0

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "subject_id": 1,
                "name": "Punteros",
                "description": "Tema actualizado de punteros en C",
                "weight": 2.5,
            }
        }
    )


class SubjectOut(BaseModel):
    id: int
    code: str
    name: str
    is_active: bool

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "code": "PACO",
                "name": "Programacion Avanzada en C",
                "is_active": True,
            }
        },
    )


class SubjectCreate(BaseModel):
    code: str
    name: str
    is_active: bool = True
    enrollment_password: Optional[str] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "code": "SISTEMAS",
                "name": "Administracion de Sistemas",
                "is_active": True,
                "enrollment_password": "optional-pass",
            }
        }
    )


class SubjectCatalogItem(BaseModel):
    id: int
    code: str
    name: str
    is_active: bool
    is_enrolled: bool
    requires_password: bool


class SubjectEnrollRequest(BaseModel):
    password: Optional[str] = None


class SubjectActiveUpdate(BaseModel):
    is_active: bool


class SubjectPasswordUpdate(BaseModel):
    requires_password: bool
    enrollment_password: Optional[str] = None


class TestCaseCreate(BaseModel):
    exercise_id: int
    name: str
    content: Dict[str, Any]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "exercise_id": 1,
                "name": "sum_hidden_1",
                "content": {
                    "input": "100 200\\n",
                    "expected": "300\\n",
                    "mode": "exact",
                },
            }
        }
    )


class QuizQuestionCreate(BaseModel):
    topic_id: int
    level: str
    statement: str
    options: list[str]
    correct_option_index: int
    is_required: bool = False


class QuizQuestionUpdate(BaseModel):
    level: str
    statement: str
    options: list[str]
    correct_option_index: int
    is_required: bool = False


class QuizQuestionOut(BaseModel):
    id: int
    topic_id: int
    level: str
    statement: str
    options: list[str]
    correct_option_index: int
    is_required: bool


class QuizAnswerCreate(BaseModel):
    selected_option_index: int


class QuizAnswerOut(BaseModel):
    question_id: int
    selected_option_index: int
    is_correct: bool


class TopicStudentStatusItem(BaseModel):
    user_id: int
    username: str
    required_beginner: int
    required_mid: int
    required_expert: int
    completed_beginner: int
    completed_mid: int
    completed_expert: int
    beginner_minimum_met: bool
    mid_minimum_met: bool
    expert_minimum_met: bool
    topic_minimums_met: bool


class SubmissionCreate(BaseModel):
    exercise_id: int
    # Opción 1: resultados simulados (para testing)
    results: Optional[Dict[str, bool]] = None
    # Opción 2: código C real para evaluar
    code: Optional[str] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "exercise_id": 1,
                "code": "#include <stdio.h>\\nint main() {\\n  int a, b;\\n  scanf(\\\"%d %d\\\", &a, &b);\\n  printf(\\\"%d\\\\n\\\", a + b);\\n  return 0;\\n}\\n",
            }
        }
    )


class JobResponse(BaseModel):
    id: int
    user_id: int
    exercise_id: int
    status: str
    run_id: Optional[int] = None
    verdict: Optional[str] = None
    passed_all: Optional[bool] = None
    duration_ms: Optional[int] = None
    memory_kb: Optional[int] = None
    details: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "user_id": 3,
                "exercise_id": 1,
                "status": "completed",
                "run_id": 1,
                "verdict": "AC",
                "passed_all": True,
                "duration_ms": 45,
                "memory_kb": 512,
                "details": {
                    "results": [
                        {"test_id": "sum_1", "passed": True, "details": "Exact match"},
                        {"test_id": "sum_2", "passed": True, "details": "Exact match"},
                    ]
                },
                "error_message": None,
                "created_at": "2026-03-12T15:30:45.123456",
                "completed_at": "2026-03-12T15:30:47.234567",
            }
        },
    )


class UserProfile(BaseModel):
    id: int
    username: str
    email: str
    role: str
    leaderboard_rank: int
    completed_exercises: int

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": 3,
                "username": "alumno_a_base",
                "email": "alumno_a_base@example.com",
                "role": "student",
                "leaderboard_rank": 1,
                "completed_exercises": 2,
            }
        }
    )


class CompletedExerciseInfo(BaseModel):
    exercise_id: int
    exercise_title: str
    completed_at: str
    attempts_needed: int

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "exercise_id": 1,
                "exercise_title": "sum",
                "completed_at": "2026-03-12T15:30:47.234567",
                "attempts_needed": 1,
            }
        }
    )


class UserProgress(BaseModel):
    completed_exercises_count: int
    total_exercises: int
    total_attempts: int
    completion_rate: float  # 0.0 to 1.0
    completed_exercises: list[CompletedExerciseInfo]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "completed_exercises_count": 2,
                "total_exercises": 2,
                "total_attempts": 2,
                "completion_rate": 1.0,
                "completed_exercises": [
                    {
                        "exercise_id": 1,
                        "exercise_title": "sum",
                        "completed_at": "2026-03-12T15:30:47.234567",
                        "attempts_needed": 1,
                    },
                    {
                        "exercise_id": 2,
                        "exercise_title": "sort_words",
                        "completed_at": "2026-03-12T15:35:12.765432",
                        "attempts_needed": 1,
                    },
                ],
            }
        }
    )


class UserSubmissionItem(BaseModel):
    job_id: int
    exercise_id: int
    exercise_title: str
    status: str
    verdict: Optional[str] = None
    passed_all: Optional[bool] = None
    created_at: str
    completed_at: Optional[str] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job_id": 2,
                "exercise_id": 2,
                "exercise_title": "sort_words",
                "status": "completed",
                "verdict": "AC",
                "passed_all": True,
                "created_at": "2026-03-12T15:35:10.654321",
                "completed_at": "2026-03-12T15:35:12.765432",
            }
        }
    )
