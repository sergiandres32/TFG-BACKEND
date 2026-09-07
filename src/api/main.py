from fastapi import FastAPI, Depends, HTTPException, Body, File, UploadFile, Form, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session
from . import models, schemas, crud
from .database import engine, Base, get_db, ensure_phase1_schema, ensure_phase2_multi_subject_schema, ensure_phase3_lti_schema, ensure_phase4_topic_secret_schema, ensure_phase5_exercise_submission_type_schema
from .security import create_access_token, get_current_user, require_teacher, require_student
import base64
import hashlib
import hmac
import json
import os
import re
import time
import urllib.parse

Base.metadata.create_all(bind=engine)
ensure_phase1_schema(engine)
ensure_phase2_multi_subject_schema(engine)
ensure_phase3_lti_schema(engine)
ensure_phase4_topic_secret_schema(engine)
ensure_phase5_exercise_submission_type_schema(engine)

app = FastAPI(
    title="Jutge Mini API",
    description="API del sistema de evaluación Jutge con ejemplos basados en el estado seed de la BD.",
)

LEADERBOARD_EXAMPLE = [
    {
        "user_id": 3,
        "username": "alumno_a_base",
        "completed_count": 2,
        "last_completed_at": "2026-03-12T15:35:12.765432",
    },
    {
        "user_id": 4,
        "username": "alumno_b_base",
        "completed_count": 1,
        "last_completed_at": "2026-03-12T15:30:47.234567",
    },
    {
        "user_id": 1,
        "username": "profesor_seed",
        "completed_count": 0,
        "last_completed_at": None,
    },
]

EXERCISES_LIST_EXAMPLE = [
    {"id": 1, "title": "sum", "description": "Sum two integers", "level": "beginner", "expected_submission_type": "c_file", "is_required": False, "completed": True},
    {"id": 2, "title": "sort_words", "description": "Sort words alphabetically", "level": "mid", "expected_submission_type": "zip_makefile", "is_required": False, "completed": False},
]

SUBMISSION_CREATED_EXAMPLE = {
    "job_id": 5,
    "status": "pending",
    "message": "Submission queued for evaluation",
}

CREATE_EXERCISE_RESPONSE_EXAMPLE = {"id": 3, "title": "Fibonacci"}

CREATE_TEST_CASE_RESPONSE_EXAMPLE = {"id": 5, "name": "sum_hidden_1"}

JOB_PENDING_EXAMPLE = {
    "id": 5,
    "user_id": 3,
    "exercise_id": 1,
    "status": "pending",
    "run_id": None,
    "verdict": None,
    "passed_all": None,
    "duration_ms": None,
    "memory_kb": None,
    "details": None,
    "error_message": None,
    "created_at": "2026-03-12T15:30:45.123456",
    "completed_at": None,
}

JOB_WA_EXAMPLE = {
    "id": 4,
    "user_id": 4,
    "exercise_id": 2,
    "status": "completed",
    "run_id": 4,
    "verdict": "WA",
    "passed_all": False,
    "duration_ms": 38,
    "memory_kb": 524,
    "details": {
        "results": [
            {"test_id": "sort_1", "passed": True, "details": "Exact match"},
            {"test_id": "sort_2", "passed": False, "details": "Output mismatch"},
        ]
    },
    "error_message": None,
    "created_at": "2026-03-12T15:35:10.654321",
    "completed_at": "2026-03-12T15:35:12.765432",
}

SUBMISSION_V2_PREFIX = "__JUTGE_SUBMISSION_V2__:"


def _slugify_filename_fragment(raw: str, max_len: int = 48) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", (raw or "").strip()).strip("_").lower()
    if not cleaned:
        cleaned = "item"
    return cleaned[:max_len]


def _decode_submission_payload_for_download(job_code: str) -> tuple[bytes, str, str]:
    if not (job_code or "").startswith(SUBMISSION_V2_PREFIX):
        return (job_code or "").encode("utf-8"), "text/x-c", ".c"

    payload_json = (job_code or "")[len(SUBMISSION_V2_PREFIX):]
    payload = json.loads(payload_json)
    payload_format = str(payload.get("format") or "")
    if payload_format == "zip_makefile":
        zip_b64 = payload.get("zip_b64")
        if not isinstance(zip_b64, str) or not zip_b64:
            raise ValueError("Invalid zip payload")
        zip_bytes = base64.b64decode(zip_b64)
        return zip_bytes, "application/zip", ".zip"

    raise ValueError("Unsupported submission format")


def _resolve_user_subject_scope(db: Session, user_id: int, subject_id: int | None = None) -> list[int]:
    enrolled_subject_ids = crud.get_enrolled_subject_ids_for_user(db, user_id)
    if not enrolled_subject_ids:
        return []
    if subject_id is None:
        return enrolled_subject_ids
    if subject_id not in enrolled_subject_ids:
        raise HTTPException(status_code=403, detail="Not enrolled in subject")
    return [subject_id]


def _is_lti_instructor(roles: str) -> bool:
    normalized = (roles or "").lower()
    return "instructor" in normalized or "teacher" in normalized


def _resolve_lti_display_name(post_data: dict[str, str], lti_user_id: str) -> str:
    full_name = (post_data.get("lis_person_name_full") or "").strip()
    if full_name:
        return full_name

    given_name = (post_data.get("lis_person_name_given") or "").strip()
    family_name = (post_data.get("lis_person_name_family") or "").strip()
    combined_name = " ".join(part for part in [given_name, family_name] if part).strip()
    if combined_name:
        return combined_name

    ext_username = (post_data.get("ext_user_username") or "").strip()
    if ext_username:
        return ext_username

    return lti_user_id


def _resolve_lti_target(post_data: dict[str, str]) -> str:
    # In LTI 1.1 custom params are usually sent as custom_<name>.
    # Keep a permissive fallback to target for local/manual launch tests.
    return (post_data.get("custom_target") or post_data.get("target") or "").strip().lower()


def _resolve_lti_exercise_id(post_data: dict[str, str]) -> int | None:
    raw_value = (post_data.get("custom_exercise_id") or post_data.get("exercise_id") or "").strip()
    if not raw_value:
        target_value = (post_data.get("custom_target") or post_data.get("target") or "").strip().lower()
        match = re.fullmatch(r"exercise[:=\-](\d+)", target_value)
        if not match:
            return None
        raw_value = match.group(1)
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return None


def _resolve_ui_base_with_target(
    *,
    default_ui_base: str,
    target: str,
    is_instructor: bool,
    request: Request,
) -> tuple[str, str | None]:
    # Optional LTI deep-link target shortcuts.
    # - subjects  -> subjects portal
    # - admin     -> admin dashboard
    # - exercises -> admin dashboard preselected in exercises section
    target_aliases = {
        "subjects": "subjects",
        "subjects_portal": "subjects",
        "materies": "subjects",
        "materias": "subjects",
        "admin": "admin",
        "dashboard": "admin",
        "tauler": "admin",
        "exercises": "exercises",
        "exercise": "exercises",
        "exercicis": "exercises",
    }
    target_key = target_aliases.get(target or "")

    query_target = None
    role_path = "/admin" if is_instructor else "/student"

    if target_key == "subjects":
        role_path = "/subjects"
    elif target_key == "admin" and is_instructor:
        role_path = "/admin"
    elif target_key == "exercises" and is_instructor:
        role_path = "/admin"
        query_target = "exercises"

    if is_instructor and target_key == "exercise":
        role_path = "/admin"
        query_target = "proves"

    if default_ui_base:
        if target_key in {"subjects", "admin", "exercises"}:
            forwarded_host = (request.headers.get("X-Forwarded-Host") or request.headers.get("Host") or "").strip()
            forwarded_proto = (request.headers.get("X-Forwarded-Proto") or request.url.scheme or "https").strip()
            if (
                forwarded_host
                and not forwarded_host.startswith("localhost")
                and not forwarded_host.startswith("127.0.0.1")
            ):
                return f"{forwarded_proto}://{forwarded_host}{role_path}", query_target
        return default_ui_base, query_target

    forwarded_host = (request.headers.get("X-Forwarded-Host") or request.headers.get("Host") or "").strip()
    forwarded_proto = (request.headers.get("X-Forwarded-Proto") or request.url.scheme or "https").strip()
    if (
        forwarded_host
        and not forwarded_host.startswith("localhost")
        and not forwarded_host.startswith("127.0.0.1")
    ):
        return f"{forwarded_proto}://{forwarded_host}{role_path}", query_target

    return "", query_target


def _oauth_normalize_params(params: dict[str, str]) -> str:
    # OAuth 1.0 signature is calculated over all params except oauth_signature.
    filtered = {k: v for k, v in params.items() if k != "oauth_signature"}
    encoded_pairs = []
    for key in sorted(filtered.keys()):
        value = filtered.get(key, "")
        encoded_pairs.append(
            f"{urllib.parse.quote(str(key), safe='~')}={urllib.parse.quote(str(value), safe='~')}"
        )
    return "&".join(encoded_pairs)


def _compute_oauth_signature(post_data: dict[str, str], http_method: str, base_url: str, consumer_secret: str) -> str:
    normalized_params = _oauth_normalize_params(post_data)
    base_elems = [
        http_method.upper(),
        urllib.parse.quote(base_url, safe='~'),
        urllib.parse.quote(normalized_params, safe='~'),
    ]
    base_string = "&".join(base_elems)
    signing_key = f"{urllib.parse.quote(consumer_secret, safe='~')}&"
    digest = hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha1).digest()
    return base64.b64encode(digest).decode()


def _validate_lti_oauth_11(request: Request, post_data: dict[str, str], consumer_secret: str) -> tuple[bool, str]:
    required = [
        "oauth_consumer_key",
        "oauth_signature_method",
        "oauth_timestamp",
        "oauth_nonce",
        "oauth_signature",
    ]
    for key in required:
        if not post_data.get(key):
            return False, f"Missing {key}"

    if str(post_data.get("oauth_signature_method", "")).upper() != "HMAC-SHA1":
        return False, "Unsupported oauth_signature_method"

    try:
        ts = int(str(post_data.get("oauth_timestamp", "0")))
    except ValueError:
        return False, "Invalid oauth_timestamp"
    now_ts = int(time.time())
    if abs(now_ts - ts) > 3600:
        return False, "oauth_timestamp outside allowed window"

    proto = request.headers.get("X-Forwarded-Proto", request.url.scheme)
    host = request.headers.get("Host", request.url.hostname)
    prefix = request.headers.get("X-Forwarded-Prefix", "")
    base_url = f"{proto}://{host}{prefix}{request.url.path}"

    computed = _compute_oauth_signature(post_data, "POST", base_url, consumer_secret)
    received = str(post_data.get("oauth_signature", ""))
    if not hmac.compare_digest(computed, received):
        return False, "Invalid oauth_signature"

    return True, "ok"


def _bootstrap_lti_platform_if_configured(db: Session, consumer_key: str) -> tuple[models.LtiPlatform | None, str]:
    bootstrap_key = os.environ.get("LTI_BOOTSTRAP_CONSUMER_KEY", "").strip()
    bootstrap_secret = os.environ.get("LTI_BOOTSTRAP_CONSUMER_SECRET", "").strip()
    bootstrap_name = os.environ.get("LTI_BOOTSTRAP_PLATFORM_NAME", "atenea-upc").strip() or "atenea-upc"

    if not consumer_key or not bootstrap_key or not bootstrap_secret:
        return None, "bootstrap_not_configured"
    if consumer_key != bootstrap_key:
        return None, "bootstrap_key_mismatch"

    existing = (
        db.query(models.LtiPlatform)
        .filter(models.LtiPlatform.consumer_key == consumer_key)
        .first()
    )
    if existing:
        existing.consumer_secret = bootstrap_secret
        existing.is_active = True
        if bootstrap_name:
            existing.name = bootstrap_name
        db.commit()
        db.refresh(existing)
        return existing, "bootstrap_updated_existing"

    payload = schemas.LtiPlatformCreate(
        name=bootstrap_name,
        consumer_key=bootstrap_key,
        consumer_secret=bootstrap_secret,
        is_active=True,
    )
    created = crud.upsert_lti_platform(db, payload)
    if not created:
        return None, "bootstrap_create_failed"
    return created, "bootstrap_created"

ME_SUBMISSIONS_EXAMPLE = [
    {
        "job_id": 2,
        "exercise_id": 2,
        "exercise_title": "sort_words",
        "status": "completed",
        "verdict": "AC",
        "passed_all": True,
        "created_at": "2026-03-12T15:35:10.654321",
        "completed_at": "2026-03-12T15:35:12.765432",
    },
    {
        "job_id": 1,
        "exercise_id": 1,
        "exercise_title": "sum",
        "status": "completed",
        "verdict": "AC",
        "passed_all": True,
        "created_at": "2026-03-12T15:30:45.123456",
        "completed_at": "2026-03-12T15:30:47.234567",
    },
]

@app.post(
    "/users",
    summary="Registro local deshabilitado",
    responses={
        410: {
            "description": "Registro deshabilitado",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Local user registration is disabled. Access must be provisioned through Atenea LTI."
                    }
                }
            },
        },
    },
)
def register(
    user: schemas.UserCreate = Body(
        ...,
        examples={
            "base": {
                "summary": "Registro básico",
                "value": {"username": "alumno_nuevo", "email": "alumno@example.com", "password": "pass123"},
            }
        },
    ),
    db: Session = Depends(get_db),
):
    raise HTTPException(
        status_code=410,
        detail="Local user registration is disabled. Access must be provisioned through Atenea LTI.",
    )


@app.get(
    "/students",
    response_model=list[schemas.StudentListItem],
    summary="Listar alumnos (solo profesor)",
    responses={
        200: {"description": "Listado de alumnos"},
        403: {"description": "Solo profesores", "content": {"application/json": {"example": {"detail": "Only teachers can list students"}}}},
    },
)
def list_students(subject_id: int | None = None, current: models.User = Depends(require_teacher), db: Session = Depends(get_db)):
    if subject_id is not None:
        _resolve_user_subject_scope(db, current.id, subject_id)
        students = crud.list_students_by_subject(db, subject_id)
    else:
        students = crud.list_students(db)
    return [
        {
            "id": student.id,
            "username": student.username,
            "email": student.email,
            "role": student.role.value if hasattr(student.role, "value") else student.role,
        }
        for student in students
    ]


@app.get(
    "/subjects/me",
    response_model=list[schemas.SubjectOut],
    summary="Listar asignaturas inscritas del usuario autenticado",
)
def list_my_subjects(current=Depends(get_current_user), db: Session = Depends(get_db)):
    return crud.list_subjects_for_user(db, current.id)


@app.post(
    "/subjects",
    response_model=schemas.SubjectOut,
    summary="Crear asignatura (solo profesor)",
)
def create_subject(payload: schemas.SubjectCreate, current: models.User = Depends(require_teacher), db: Session = Depends(get_db)):
    if not payload.code.strip() or not payload.name.strip():
        raise HTTPException(status_code=400, detail="code and name are required")

    subject = crud.create_subject_with_owner(db, payload, owner_user_id=current.id)
    if not subject:
        raise HTTPException(status_code=400, detail="Subject code or name already exists")
    return subject


@app.get(
    "/subjects/catalog",
    response_model=list[schemas.SubjectCatalogItem],
    summary="Catalogo de asignaturas activas con estado de inscripcion",
)
def list_subject_catalog(current=Depends(get_current_user), db: Session = Depends(get_db)):
    return crud.list_subject_catalog_for_user(db, current.id)


@app.get(
    "/subjects/manage",
    response_model=list[schemas.SubjectCatalogItem],
    summary="Catalogo de asignaturas para gestion docente",
)
def list_subject_manage(current: models.User = Depends(require_teacher), db: Session = Depends(get_db)):
    return crud.list_subject_catalog_for_user(db, current.id, include_inactive=True)


@app.post(
    "/subjects/{subject_id}/enroll",
    summary="Inscribir alumno en asignatura",
)
def enroll_subject(subject_id: int, payload: schemas.SubjectEnrollRequest, current: models.User = Depends(require_student), db: Session = Depends(get_db)):
    _, status = crud.enroll_student_in_subject(db, user_id=current.id, subject_id=subject_id, password=payload.password)
    if status == "subject_not_found":
        raise HTTPException(status_code=404, detail="Subject not found")
    if status == "password_required":
        raise HTTPException(status_code=400, detail="Password required for this subject")
    if status == "invalid_password":
        raise HTTPException(status_code=400, detail="Invalid subject password")
    if status == "already_enrolled":
        return {"ok": True, "message": "Already enrolled"}
    return {"ok": True, "message": "Inscripcio completada"}


@app.post(
    "/subjects/{subject_id}/assign-self",
    summary="Asignar profesor autenticado a una asignatura",
)
def assign_teacher_subject(subject_id: int, current: models.User = Depends(require_teacher), db: Session = Depends(get_db)):
    _, status = crud.assign_user_to_subject(
        db,
        user_id=current.id,
        subject_id=subject_id,
        role_in_subject=models.RoleEnum.teacher,
    )
    if status == "subject_not_found":
        raise HTTPException(status_code=404, detail="Subject not found")
    if status == "already_assigned":
        return {"ok": True, "message": "Already assigned"}
    return {"ok": True, "message": "Assigned"}


@app.delete(
    "/subjects/{subject_id}/assign-self",
    summary="Desasignar profesor autenticado de una asignatura",
)
def unassign_teacher_subject(subject_id: int, current: models.User = Depends(require_teacher), db: Session = Depends(get_db)):
    removed = crud.unassign_user_from_subject(db, user_id=current.id, subject_id=subject_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return {"ok": True, "message": "Unassigned"}


@app.put(
    "/subjects/{subject_id}/active",
    response_model=schemas.SubjectOut,
    summary="Activar/desactivar asignatura (profesor asignado)",
)
def update_subject_active(subject_id: int, payload: schemas.SubjectActiveUpdate, current: models.User = Depends(require_teacher), db: Session = Depends(get_db)):
    subject = crud.get_subject_by_id(db, subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    if not crud.is_user_enrolled_in_subject(db, current.id, subject_id):
        raise HTTPException(status_code=403, detail="Not assigned to subject")

    updated = crud.update_subject_active(db, subject_id, payload.is_active)
    if not updated:
        raise HTTPException(status_code=404, detail="Subject not found")
    return updated


@app.put(
    "/subjects/{subject_id}/password",
    response_model=schemas.SubjectOut,
    summary="Configurar proteccion por password de asignatura (profesor asignado)",
)
def update_subject_password(subject_id: int, payload: schemas.SubjectPasswordUpdate, current: models.User = Depends(require_teacher), db: Session = Depends(get_db)):
    subject = crud.get_subject_by_id(db, subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    if not crud.is_user_enrolled_in_subject(db, current.id, subject_id):
        raise HTTPException(status_code=403, detail="Not assigned to subject")

    updated, status = crud.update_subject_password(
        db,
        subject_id=subject_id,
        requires_password=payload.requires_password,
        enrollment_password=payload.enrollment_password,
    )
    if status == "password_required":
        raise HTTPException(status_code=400, detail="Password required when protection is enabled")
    if not updated:
        raise HTTPException(status_code=404, detail="Subject not found")
    return updated


@app.post(
    "/lti/platforms",
    response_model=schemas.LtiPlatformOut,
    summary="Crear o actualizar configuracion de plataforma LTI (solo profesor)",
)
def upsert_lti_platform(payload: schemas.LtiPlatformCreate, current: models.User = Depends(require_teacher), db: Session = Depends(get_db)):
    if not payload.name.strip() or not payload.consumer_key.strip() or not payload.consumer_secret.strip():
        raise HTTPException(status_code=400, detail="name, consumer_key and consumer_secret are required")
    platform = crud.upsert_lti_platform(db, payload)
    if not platform:
        raise HTTPException(status_code=400, detail="Could not create/update LTI platform")
    return platform


@app.get(
    "/lti/platforms",
    response_model=list[schemas.LtiPlatformOut],
    summary="Listar plataformas LTI configuradas (solo profesor)",
)
def list_lti_platforms(current: models.User = Depends(require_teacher), db: Session = Depends(get_db)):
    return crud.list_lti_platforms(db)


@app.post(
    "/lti/launch",
    response_model=schemas.LtiLaunchResponse,
    summary="Launch LTI 1.1 desde LMS (Atenea/Moodle)",
)
async def lti_launch(request: Request, db: Session = Depends(get_db)):
    form_data = await request.form()
    post_data = {key: str(form_data.get(key) or "") for key in form_data.keys()}

    consumer_key = post_data.get("oauth_consumer_key", "").strip()
    platform = crud.get_active_lti_platform_by_consumer_key(db, consumer_key)
    bootstrap_status = "not_attempted"
    if not platform:
        platform, bootstrap_status = _bootstrap_lti_platform_if_configured(db, consumer_key)
    if not platform:
        crud.create_lti_launch_event(
            db,
            platform_id=None,
            lti_user_id=post_data.get("user_id"),
            context_id=post_data.get("context_id"),
            resource_link_id=post_data.get("resource_link_id"),
            roles=post_data.get("roles"),
            user_id=None,
            subject_id=None,
            outcome="invalid_consumer_key",
            details={
                "consumer_key": consumer_key,
                "bootstrap_status": bootstrap_status,
            },
        )
        raise HTTPException(status_code=401, detail="Invalid oauth_consumer_key")

    is_valid, reason = _validate_lti_oauth_11(request, post_data, platform.consumer_secret)
    if not is_valid:
        crud.create_lti_launch_event(
            db,
            platform_id=platform.id,
            lti_user_id=post_data.get("user_id"),
            context_id=post_data.get("context_id"),
            resource_link_id=post_data.get("resource_link_id"),
            roles=post_data.get("roles"),
            user_id=None,
            subject_id=None,
            outcome="invalid_signature",
            details={"reason": reason},
        )
        raise HTTPException(status_code=401, detail=reason)

    lti_user_id = post_data.get("user_id", "").strip()
    context_id = post_data.get("context_id", "").strip()
    if not lti_user_id:
        raise HTTPException(status_code=400, detail="Missing user_id")
    if not context_id:
        raise HTTPException(status_code=400, detail="Missing context_id")

    roles = post_data.get("roles", "")
    is_instructor = _is_lti_instructor(roles)
    display_name = _resolve_lti_display_name(post_data, lti_user_id)
    email = post_data.get("lis_person_contact_email_primary") or None

    user = crud.resolve_or_create_lti_user(
        db,
        platform=platform,
        lti_user_id=lti_user_id,
        display_name=display_name,
        email=email,
        is_instructor=is_instructor,
    )

    subject, _, mapping_status = crud.resolve_or_create_subject_for_lti_context(
        db,
        platform=platform,
        context_id=context_id,
        context_title=post_data.get("context_title") or None,
        allow_auto_create=is_instructor,
    )
    if not subject:
        crud.create_lti_launch_event(
            db,
            platform_id=platform.id,
            lti_user_id=lti_user_id,
            context_id=context_id,
            resource_link_id=post_data.get("resource_link_id"),
            roles=roles,
            user_id=user.id,
            subject_id=None,
            outcome="missing_context_mapping",
            details={"mapping_status": mapping_status},
        )
        raise HTTPException(status_code=403, detail="Context not mapped to subject")

    role_in_subject = models.RoleEnum.teacher if is_instructor else models.RoleEnum.student
    enrollment = crud.upsert_user_subject_enrollment_role(
        db,
        user_id=user.id,
        subject_id=subject.id,
        role_in_subject=role_in_subject,
    )

    token = create_access_token({"sub": user.username})
    crud.create_lti_launch_event(
        db,
        platform_id=platform.id,
        lti_user_id=lti_user_id,
        context_id=context_id,
        resource_link_id=post_data.get("resource_link_id"),
        roles=roles,
        user_id=user.id,
        subject_id=subject.id,
        outcome="ok",
        details={
            "mapping_status": mapping_status,
            "display_name": display_name,
        },
    )

    user_role = user.role.value if hasattr(user.role, "value") else str(user.role)
    enrollment_role = (
        enrollment.role_in_subject.value
        if hasattr(enrollment.role_in_subject, "value")
        else str(enrollment.role_in_subject)
    )

    lti_target = _resolve_lti_target(post_data)
    lti_exercise_id = _resolve_lti_exercise_id(post_data)

    # Redirect UI by role with query token.
    # Priority:
    # - instructor -> LTI_UI_BASE_URL_TEACHER
    # - student    -> LTI_UI_BASE_URL_STUDENT
    # - fallback   -> LTI_UI_BASE_URL (legacy)
    default_ui_base = ""
    if is_instructor:
        default_ui_base = os.environ.get("LTI_UI_BASE_URL_TEACHER", "").strip()
    else:
        default_ui_base = os.environ.get("LTI_UI_BASE_URL_STUDENT", "").strip()
    if not default_ui_base:
        default_ui_base = os.environ.get("LTI_UI_BASE_URL", "").strip()

    ui_base, query_target = _resolve_ui_base_with_target(
        default_ui_base=default_ui_base,
        target=lti_target,
        is_instructor=is_instructor,
        request=request,
    )

    if lti_exercise_id is not None:
        query_target = "alumnat" if is_instructor else None

    # If not set, fall back to JSON (useful for local testing / Swagger).
    if ui_base:
        # Keep Streamlit path canonical (/student/) to avoid proxy slash-redirects
        # that can leak internal ports (e.g. :8080) in external clients.
        if "?" not in ui_base and not ui_base.endswith("/"):
            ui_base = f"{ui_base}/"
        separator = "&" if "?" in ui_base else "?"
        redirect_url = f"{ui_base}{separator}token={token}&subject_id={subject.id}"
        if query_target:
            redirect_url = f"{redirect_url}&target={urllib.parse.quote(query_target, safe='')}"
        if lti_exercise_id is not None:
            redirect_url = f"{redirect_url}&exercise_id={urllib.parse.quote(str(lti_exercise_id), safe='')}"
        return RedirectResponse(url=redirect_url, status_code=303)

    # Fallback: return JSON (local dev / test scripts)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user.id,
        "username": user.username,
        "role": user_role,
        "subject_id": subject.id,
        "role_in_subject": enrollment_role,
    }


@app.post(
    "/token",
    summary="Login local deshabilitado",
    responses={
        410: {
            "description": "Login local deshabilitado",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Local password login is disabled. Access through Atenea LTI launch."
                    }
                }
            },
        },
    },
)
def login_disabled():
    raise HTTPException(
        status_code=410,
        detail="Local password login is disabled. Access through Atenea LTI launch.",
    )


@app.post(
    "/exercises",
    summary="Crear ejercicio",
    responses={
        200: {"description": "Ejercicio creado", "content": {"application/json": {"example": CREATE_EXERCISE_RESPONSE_EXAMPLE}}},
    },
)
def create_exercise(ex: schemas.ExerciseCreate, current: models.User = Depends(require_teacher), db: Session = Depends(get_db)):
    if ex.topic_id is None:
        raise HTTPException(status_code=400, detail="topic_id is required")

    topic = crud.get_topic_by_id(db, ex.topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    if not crud.is_user_teacher_in_subject(db, current.id, int(topic.subject_id)):
        raise HTTPException(status_code=403, detail="Not a teacher in this subject")
    e = crud.create_exercise(db, ex, creator_id=current.id)
    return {"id": e.id, "title": e.title}


@app.get(
    "/quiz-questions",
    response_model=list[schemas.QuizQuestionOut],
    summary="Listar preguntas tipo test",
)
def list_quiz_questions(topic_id: int | None = None, subject_id: int | None = None, current=Depends(get_current_user), db: Session = Depends(get_db)):
    subject_ids = _resolve_user_subject_scope(db, current.id, subject_id)
    return crud.list_quiz_questions(db, topic_id=topic_id, subject_ids=subject_ids)


@app.post(
    "/quiz-questions",
    response_model=schemas.QuizQuestionOut,
    summary="Crear pregunta tipo test (solo profesor)",
)
def create_quiz_question(payload: schemas.QuizQuestionCreate, current: models.User = Depends(require_teacher), db: Session = Depends(get_db)):
    if not payload.options or len(payload.options) < 2:
        raise HTTPException(status_code=400, detail="Quiz question must have at least 2 options")
    if payload.correct_option_index < 0 or payload.correct_option_index >= len(payload.options):
        raise HTTPException(status_code=400, detail="correct_option_index out of range")
    if payload.level not in {"beginner", "mid", "expert"}:
        raise HTTPException(status_code=400, detail="Invalid level")
    topic = crud.get_topic_by_id(db, payload.topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    if not crud.is_user_teacher_in_subject(db, current.id, int(topic.subject_id)):
        raise HTTPException(status_code=403, detail="Not a teacher in this subject")

    return crud.create_quiz_question(db, payload, creator_id=current.id)


@app.put(
    "/quiz-questions/{question_id}",
    response_model=schemas.QuizQuestionOut,
    summary="Actualizar pregunta tipo test (solo profesor)",
)
def update_quiz_question(question_id: int, payload: schemas.QuizQuestionUpdate, current: models.User = Depends(require_teacher), db: Session = Depends(get_db)):
    if not payload.options or len(payload.options) < 2:
        raise HTTPException(status_code=400, detail="Quiz question must have at least 2 options")
    if payload.correct_option_index < 0 or payload.correct_option_index >= len(payload.options):
        raise HTTPException(status_code=400, detail="correct_option_index out of range")
    if payload.level not in {"beginner", "mid", "expert"}:
        raise HTTPException(status_code=400, detail="Invalid level")

    question = crud.get_quiz_question_by_id(db, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Quiz question not found")
    topic_subject_id = crud.get_topic_subject_id(db, int(question.topic_id))
    if topic_subject_id is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    if not crud.is_user_teacher_in_subject(db, current.id, topic_subject_id):
        raise HTTPException(status_code=403, detail="Not a teacher in this subject")

    updated = crud.update_quiz_question(db, question_id, payload)
    if not updated:
        raise HTTPException(status_code=404, detail="Quiz question not found")
    return updated


@app.delete(
    "/quiz-questions/{question_id}",
    summary="Eliminar pregunta tipo test (solo profesor)",
)
def delete_quiz_question(question_id: int, current: models.User = Depends(require_teacher), db: Session = Depends(get_db)):
    question = crud.get_quiz_question_by_id(db, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Quiz question not found")
    topic_subject_id = crud.get_topic_subject_id(db, int(question.topic_id))
    if topic_subject_id is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    if not crud.is_user_teacher_in_subject(db, current.id, topic_subject_id):
        raise HTTPException(status_code=403, detail="Not a teacher in this subject")

    deleted = crud.delete_quiz_question(db, question_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Quiz question not found")
    return {"ok": True}


@app.post(
    "/quiz-questions/{question_id}/answer",
    response_model=schemas.QuizAnswerOut,
    summary="Responder pregunta tipo test",
)
def answer_quiz_question(question_id: int, payload: schemas.QuizAnswerCreate, current=Depends(get_current_user), db: Session = Depends(get_db)):
    question = crud.get_quiz_question_by_id(db, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Quiz question not found")
    topic_subject_id = crud.get_topic_subject_id(db, int(question.topic_id))
    if topic_subject_id is None or not crud.is_user_enrolled_in_subject(db, current.id, topic_subject_id):
        raise HTTPException(status_code=403, detail="Not enrolled in subject")

    options = question.options or []
    if payload.selected_option_index < 0 or payload.selected_option_index >= len(options):
        raise HTTPException(status_code=400, detail="selected_option_index out of range")

    answer = crud.upsert_user_quiz_answer(db, current.id, question_id, payload.selected_option_index)
    return {
        "question_id": question_id,
        "selected_option_index": answer.selected_option_index,
        "is_correct": answer.is_correct,
    }


@app.put(
    "/exercises/{exercise_id}",
    summary="Actualizar ejercicio",
    responses={
        200: {"description": "Ejercicio actualizado"},
        404: {"description": "Exercise not found", "content": {"application/json": {"example": {"detail": "Exercise not found"}}}},
        400: {"description": "Topic inválido", "content": {"application/json": {"example": {"detail": "Topic not found"}}}},
    },
)
def update_exercise(exercise_id: int, ex: schemas.ExerciseUpdate, current: models.User = Depends(require_teacher), db: Session = Depends(get_db)):
    existing = crud.get_exercise_by_id(db, exercise_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Exercise not found")

    current_subject_id = crud.get_exercise_subject_id(db, exercise_id)
    if current_subject_id is None:
        raise HTTPException(status_code=404, detail="Exercise topic not found")
    if not crud.is_user_teacher_in_subject(db, current.id, current_subject_id):
        raise HTTPException(status_code=403, detail="Not a teacher in this subject")

    if ex.topic_id is not None:
        topic = crud.get_topic_by_id(db, ex.topic_id)
        if not topic:
            raise HTTPException(status_code=400, detail="Topic not found")
        if not crud.is_user_teacher_in_subject(db, current.id, int(topic.subject_id)):
            raise HTTPException(status_code=403, detail="Not a teacher in this subject")

    updated = crud.update_exercise(db, exercise_id, ex)
    return {
        "id": updated.id,
        "topic_id": updated.topic_id,
        "title": updated.title,
        "description": updated.description,
        "level": updated.level.value if hasattr(updated.level, "value") else updated.level,
        "expected_submission_type": (
            updated.expected_submission_type.value
            if hasattr(updated.expected_submission_type, "value")
            else updated.expected_submission_type
        ),
        "is_required": bool(updated.is_required),
    }


@app.delete(
    "/exercises/{exercise_id}",
    summary="Eliminar ejercicio",
    responses={
        200: {"description": "Ejercicio eliminado", "content": {"application/json": {"example": {"ok": True}}}},
        404: {"description": "Exercise not found", "content": {"application/json": {"example": {"detail": "Exercise not found"}}}},
    },
)
def delete_exercise(exercise_id: int, current: models.User = Depends(require_teacher), db: Session = Depends(get_db)):
    current_subject_id = crud.get_exercise_subject_id(db, exercise_id)
    if current_subject_id is None:
        raise HTTPException(status_code=404, detail="Exercise topic not found")
    if not crud.is_user_teacher_in_subject(db, current.id, current_subject_id):
        raise HTTPException(status_code=403, detail="Not a teacher in this subject")

    deleted = crud.delete_exercise(db, exercise_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Exercise not found")
    return {"ok": True}


@app.post(
    "/topics",
    response_model=schemas.TopicOut,
    summary="Crear topic",
    responses={
        200: {"description": "Topic creado"},
        400: {
            "description": "Topic ya existe",
            "content": {"application/json": {"example": {"detail": "Topic name already exists"}}},
        },
    },
)
def create_topic(topic: schemas.TopicCreate, current: models.User = Depends(require_teacher), db: Session = Depends(get_db)):
    if not crud.get_subject_by_id(db, topic.subject_id):
        raise HTTPException(status_code=404, detail="Subject not found")
    if not crud.is_user_teacher_in_subject(db, current.id, topic.subject_id):
        raise HTTPException(status_code=403, detail="Not a teacher in this subject")

    db_topic = crud.create_topic(db, topic)
    if db_topic is None:
        raise HTTPException(status_code=400, detail="Topic name already exists in subject")
    return db_topic


@app.get(
    "/topics",
    response_model=list[schemas.TopicOut],
    summary="Listar topics",
)
def list_topics(subject_id: int | None = None, current=Depends(get_current_user), db: Session = Depends(get_db)):
    subject_ids = _resolve_user_subject_scope(db, current.id, subject_id)
    return crud.list_topics_for_subjects(db, subject_ids=subject_ids, subject_id=subject_id)


@app.put(
    "/topics/{topic_id}",
    response_model=schemas.TopicOut,
    summary="Actualizar topic",
    responses={
        404: {"description": "Topic no encontrado", "content": {"application/json": {"example": {"detail": "Topic not found"}}}},
        400: {"description": "Nombre duplicado", "content": {"application/json": {"example": {"detail": "Topic name already exists"}}}},
    },
)
def update_topic(topic_id: int, topic: schemas.TopicUpdate, current: models.User = Depends(require_teacher), db: Session = Depends(get_db)):
    existing = crud.get_topic_by_id(db, topic_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Topic not found")
    if not crud.is_user_teacher_in_subject(db, current.id, int(existing.subject_id)):
        raise HTTPException(status_code=403, detail="Not a teacher in this subject")
    if not crud.is_user_teacher_in_subject(db, current.id, int(topic.subject_id)):
        raise HTTPException(status_code=403, detail="Not a teacher in this subject")
    if not crud.get_subject_by_id(db, int(topic.subject_id)):
        raise HTTPException(status_code=404, detail="Subject not found")

    updated = crud.update_topic(db, topic_id, topic)
    if updated is None:
        raise HTTPException(status_code=400, detail="Topic name already exists")
    return updated


@app.delete(
    "/topics/{topic_id}",
    summary="Eliminar topic",
    responses={
        200: {"description": "Topic eliminado", "content": {"application/json": {"example": {"ok": True}}}},
        404: {"description": "Topic no encontrado", "content": {"application/json": {"example": {"detail": "Topic not found"}}}},
    },
)
def delete_topic(topic_id: int, current: models.User = Depends(require_teacher), db: Session = Depends(get_db)):
    existing = crud.get_topic_by_id(db, topic_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Topic not found")
    if not crud.is_user_teacher_in_subject(db, current.id, int(existing.subject_id)):
        raise HTTPException(status_code=403, detail="Not a teacher in this subject")

    deleted = crud.delete_topic(db, topic_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Topic not found")
    return {"ok": True}


@app.get(
    "/topics/{topic_id}/students-status",
    response_model=list[schemas.TopicStudentStatusItem],
    summary="Estado de alumnos por tema (solo profesor)",
)
def get_topic_students_status(topic_id: int, current: models.User = Depends(require_teacher), db: Session = Depends(get_db)):
    topic = crud.get_topic_by_id(db, topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    if not crud.is_user_teacher_in_subject(db, current.id, int(topic.subject_id)):
        raise HTTPException(status_code=403, detail="Not a teacher in this subject")

    status_rows = crud.get_topic_students_status(db, topic_id)
    if status_rows is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    return status_rows


@app.get(
    "/exercises",
    response_model=list[schemas.ExerciseListItem],
    summary="Listar ejercicios",
    responses={
        200: {"description": "Listado de ejercicios", "content": {"application/json": {"example": EXERCISES_LIST_EXAMPLE}}},
    },
)
def list_exercises(subject_id: int | None = None, current=Depends(get_current_user), db: Session = Depends(get_db)):
    subject_ids = _resolve_user_subject_scope(db, current.id, subject_id)
    exercises, completed_ids = crud.list_exercises_with_completion(db, current.id)
    if subject_id is not None:
        exercises = [ex for ex in exercises if ex.topic_id is not None and crud.get_topic_subject_id(db, int(ex.topic_id)) == subject_id]
    return [
        {
            "id": ex.id,
            "topic_id": ex.topic_id,
            "title": ex.title,
            "description": ex.description,
            "level": ex.level.value if hasattr(ex.level, "value") else ex.level,
            "expected_submission_type": (
                ex.expected_submission_type.value
                if hasattr(ex.expected_submission_type, "value")
                else ex.expected_submission_type
            ),
            "is_required": bool(ex.is_required),
            "completed": ex.id in completed_ids,
        }
        for ex in exercises
    ]


@app.get(
    "/exercises/{exercise_id}",
    response_model=schemas.ExerciseDetail,
    summary="Detalle de ejercicio con test cases públicos",
    responses={
        404: {"description": "Exercise not found", "content": {"application/json": {"example": {"detail": "Exercise not found"}}}},
    },
)
def get_exercise(exercise_id: int, current=Depends(get_current_user), db: Session = Depends(get_db)):
    exercise = crud.get_exercise_by_id(db, exercise_id)
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")
    subject_id = crud.get_exercise_subject_id(db, exercise_id)
    if subject_id is None or not crud.is_user_enrolled_in_subject(db, current.id, subject_id):
        raise HTTPException(status_code=403, detail="Not authorized")

    _, completed_ids = crud.list_exercises_with_completion(db, current.id)
    public_test_cases = crud.get_public_test_cases_for_exercise(db, exercise_id)

    return {
        "id": exercise.id,
        "topic_id": exercise.topic_id,
        "title": exercise.title,
        "description": exercise.description,
        "level": exercise.level.value if hasattr(exercise.level, "value") else exercise.level,
        "expected_submission_type": (
            exercise.expected_submission_type.value
            if hasattr(exercise.expected_submission_type, "value")
            else exercise.expected_submission_type
        ),
        "is_required": bool(exercise.is_required),
        "completed": exercise.id in completed_ids,
        "public_test_cases": [
            {
                "id": tc.id,
                "name": tc.name,
                "content": tc.content,
            }
            for tc in public_test_cases
        ],
    }


@app.post(
    "/test_cases",
    summary="Crear test case",
    responses={
        200: {"description": "Test case creado", "content": {"application/json": {"example": CREATE_TEST_CASE_RESPONSE_EXAMPLE}}},
    },
)
def create_test_case(tc: schemas.TestCaseCreate, current: models.User = Depends(require_teacher), db: Session = Depends(get_db)):
    exercise_subject_id = crud.get_exercise_subject_id(db, tc.exercise_id)
    if exercise_subject_id is None:
        raise HTTPException(status_code=404, detail="Exercise not found")
    if not crud.is_user_teacher_in_subject(db, current.id, exercise_subject_id):
        raise HTTPException(status_code=403, detail="Not a teacher in this subject")

    t = crud.create_test_case(db, tc)
    return {"id": t.id, "name": t.name}


@app.post(
    "/submissions",
    summary="Enviar submission",
    responses={
        200: {"description": "Submission en cola", "content": {"application/json": {"example": SUBMISSION_CREATED_EXAMPLE}}},
        400: {"description": "Payload inválido", "content": {"application/json": {"example": {"detail": "Provide code_file for submission"}}}},
        404: {"description": "Exercise not found", "content": {"application/json": {"example": {"detail": "Exercise not found"}}}},
    },
)
async def submit(current=Depends(get_current_user), db: Session = Depends(get_db), exercise_id: int = Form(...), code_file: UploadFile = File(...)):
    """
    Enviar un submission de código (multipart/form-data).
    - Recibe exercise_id y fichero .c o .zip (proyecto con Makefile)
    - Crea un Job en status 'pending'
    - Devuelve job_id para que el cliente pueda hacer polling
    - El worker evaluará asincrónica y guardará resultado en DB
    """
    if not code_file:
        raise HTTPException(status_code=400, detail="Provide code_file for submission")

    exercise = crud.get_exercise_by_id(db, exercise_id)
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")
    subject_id = crud.get_exercise_subject_id(db, exercise_id)
    if subject_id is None or not crud.is_user_enrolled_in_subject(db, current.id, subject_id):
        raise HTTPException(status_code=403, detail="Not enrolled in subject")

    filename = (code_file.filename or "submission.c").strip()
    lower_filename = filename.lower()

    if not (lower_filename.endswith(".c") or lower_filename.endswith(".zip")):
        raise HTTPException(status_code=400, detail="Only .c or .zip submissions are supported")

    incoming_submission_type = "zip_makefile" if lower_filename.endswith(".zip") else "c_file"
    expected_submission_type = (
        exercise.expected_submission_type.value
        if hasattr(exercise.expected_submission_type, "value")
        else str(exercise.expected_submission_type or "c_file")
    )
    if incoming_submission_type != expected_submission_type:
        expected_ext = ".zip" if expected_submission_type == "zip_makefile" else ".c"
        received_ext = ".zip" if incoming_submission_type == "zip_makefile" else ".c"
        raise HTTPException(
            status_code=400,
            detail=(
                f"This exercise expects {expected_ext} submissions, "
                f"but received {received_ext}"
            ),
        )

    # Leer contenido del fichero
    code_content = await code_file.read()
    if not code_content:
        raise HTTPException(status_code=400, detail="Code file is empty")

    if lower_filename.endswith(".c"):
        try:
            code_text = code_content.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="C source must be UTF-8 text")
        if not code_text.strip():
            raise HTTPException(status_code=400, detail="Code file is empty")
        job_code_payload = code_text
    else:
        max_zip_bytes = 5 * 1024 * 1024
        if len(code_content) > max_zip_bytes:
            raise HTTPException(status_code=400, detail="Zip submission too large (max 5 MB)")

        payload = {
            "format": "zip_makefile",
            "filename": filename,
            "zip_b64": base64.b64encode(code_content).decode("ascii"),
        }
        job_code_payload = SUBMISSION_V2_PREFIX + json.dumps(payload, ensure_ascii=False)

    job = crud.create_job(db, current.id, exercise_id, job_code_payload)
    return {"job_id": job.id, "status": "pending", "message": "Submission queued for evaluation"}


@app.get(
    "/jobs/{job_id}",
    response_model=schemas.JobResponse,
    summary="Consultar estado de job",
    responses={
        200: {
            "description": "Estado y resultado del job",
            "content": {
                "application/json": {
                    "examples": {
                        "pending": {"summary": "Job en cola", "value": JOB_PENDING_EXAMPLE},
                        "wa": {"summary": "Job completado con WA", "value": JOB_WA_EXAMPLE},
                    }
                }
            },
        },
        403: {"description": "No autorizado", "content": {"application/json": {"example": {"detail": "Not authorized"}}}},
        404: {"description": "Job not found", "content": {"application/json": {"example": {"detail": "Job not found"}}}},
    },
)
def get_job_status(job_id: int, current=Depends(get_current_user), db: Session = Depends(get_db)):
    """Obtener estado de un job completado."""
    result = crud.get_job_result(db, job_id)
    if not result:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = result["job"]
    # Verificar que el usuario sea el dueño
    if job.user_id != current.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    if result["run"]:
        run = result["run"]
        return {
            "id": job.id,
            "user_id": job.user_id,
            "exercise_id": job.exercise_id,
            "status": job.status.value,
            "run_id": job.run_id,
            "verdict": run.verdict.value if hasattr(run.verdict, "value") else run.verdict,
            "passed_all": run.passed,
            "duration_ms": run.duration_ms,
            "memory_kb": run.memory_kb,
            "details": run.details,
            "error_message": job.error_message,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        }
    
    return {
        "id": job.id,
        "user_id": job.user_id,
        "exercise_id": job.exercise_id,
        "status": job.status.value,
        "run_id": None,
        "verdict": None,
        "passed_all": None,
        "duration_ms": None,
        "memory_kb": None,
        "details": None,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


@app.get(
    "/teacher/submissions",
    summary="Listar entregas por asignatura (solo profesor)",
)
def list_teacher_submissions(
    subject_id: int,
    exercise_id: int | None = None,
    user_id: int | None = None,
    user_query: str | None = None,
    limit: int = 200,
    current: models.User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    if not crud.is_user_teacher_in_subject(db, current.id, subject_id):
        raise HTTPException(status_code=403, detail="Not a teacher in this subject")

    if exercise_id is not None:
        ex_subject_id = crud.get_exercise_subject_id(db, exercise_id)
        if ex_subject_id is None:
            raise HTTPException(status_code=404, detail="Exercise not found")
        if ex_subject_id != subject_id:
            raise HTTPException(status_code=403, detail="Exercise outside selected subject")

    max_limit = min(max(int(limit), 1), 500)
    rows = (
        db.query(models.Job, models.User, models.Exercise, models.Run)
        .join(models.User, models.User.id == models.Job.user_id)
        .join(models.Exercise, models.Exercise.id == models.Job.exercise_id)
        .outerjoin(models.Run, models.Run.id == models.Job.run_id)
        .order_by(models.Job.id.desc())
        .limit(max_limit * 3)
        .all()
    )

    q = (user_query or "").strip().lower()
    items = []
    for job, user, exercise, run in rows:
        ex_subject_id = crud.get_exercise_subject_id(db, int(job.exercise_id))
        if ex_subject_id != subject_id:
            continue
        if exercise_id is not None and int(job.exercise_id) != int(exercise_id):
            continue
        if user_id is not None and int(job.user_id) != int(user_id):
            continue
        if q and q not in (user.username or "").lower() and q not in (user.email or "").lower():
            continue

        items.append(
            {
                "job_id": job.id,
                "user_id": user.id,
                "username": user.username,
                "email": user.email,
                "exercise_id": exercise.id,
                "exercise_title": exercise.title,
                "status": job.status.value if hasattr(job.status, "value") else str(job.status),
                "verdict": (
                    run.verdict.value if run and hasattr(run.verdict, "value") else (str(run.verdict) if run else None)
                ),
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            }
        )
        if len(items) >= max_limit:
            break

    return items


@app.get(
    "/teacher/submissions/{job_id}/download",
    summary="Descargar código original de una entrega (solo profesor)",
)
def download_teacher_submission(job_id: int, current: models.User = Depends(require_teacher), db: Session = Depends(get_db)):
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    subject_id = crud.get_exercise_subject_id(db, int(job.exercise_id))
    if subject_id is None:
        raise HTTPException(status_code=404, detail="Exercise not found")
    if not crud.is_user_teacher_in_subject(db, current.id, subject_id):
        raise HTTPException(status_code=403, detail="Not a teacher in this subject")

    user = db.query(models.User).filter(models.User.id == job.user_id).first()
    exercise = db.query(models.Exercise).filter(models.Exercise.id == job.exercise_id).first()
    if not user or not exercise:
        raise HTTPException(status_code=404, detail="Submission context not found")

    try:
        content_bytes, media_type, extension = _decode_submission_payload_for_download(job.code or "")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Cannot decode submission payload: {exc}")

    exercise_part = _slugify_filename_fragment(exercise.title or f"exercise_{exercise.id}")
    user_part = _slugify_filename_fragment((user.email or "").split("@")[0] or user.username)
    filename = f"{exercise_part}__{user_part}__job{job.id}{extension}"

    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=content_bytes, media_type=media_type, headers=headers)


@app.get(
    "/leaderboard",
    summary="Leaderboard global",
    responses={
        200: {"description": "Ranking global", "content": {"application/json": {"example": LEADERBOARD_EXAMPLE}}},
    },
)
def leaderboard(current=Depends(get_current_user), db: Session = Depends(get_db)):
    subject_ids = crud.get_enrolled_subject_ids_for_user(db, current.id)
    rows = crud.get_leaderboard(db, subject_ids=subject_ids)
    return [{"user_id": r[0], "username": r[1], "completed_count": r[2], "last_completed_at": r[3].isoformat() if r[3] else None} for r in rows]


@app.get(
    "/me",
    response_model=schemas.UserProfile,
    summary="Perfil del usuario autenticado",
    responses={
        200: {
            "description": "Perfil del usuario",
            "content": {
                "application/json": {
                    "example": {
                        "id": 3,
                        "username": "alumno_a_base",
                        "email": "alumno_a_base@example.com",
                        "role": "student",
                        "leaderboard_rank": 1,
                        "completed_exercises": 2,
                    }
                }
            },
        }
    },
)
def get_current_user_profile(current=Depends(get_current_user), db: Session = Depends(get_db)):
    """Obtener perfil del usuario actual con posición en leaderboard."""
    rank, completed_count = crud.get_user_leaderboard_rank(db, current.id)
    lti_display_name = crud.get_latest_lti_display_name_for_user(db, current.id)
    
    return {
        "id": current.id,
        "username": current.username,
        "display_name": lti_display_name,
        "email": current.email,
        "role": current.role.value if hasattr(current.role, "value") else current.role,
        "leaderboard_rank": rank or 0,
        "completed_exercises": completed_count
    }


@app.get(
    "/me/progress",
    response_model=schemas.UserProgress,
    summary="Progreso del usuario autenticado",
)
def get_current_user_progress(subject_id: int | None = None, current=Depends(get_current_user), db: Session = Depends(get_db)):
    """Obtener estadísticas de progreso del usuario actual."""
    subject_ids = _resolve_user_subject_scope(db, current.id, subject_id)
    return crud.get_user_progress(db, current.id, subject_ids=subject_ids)


@app.get(
    "/me/submissions",
    response_model=list[schemas.UserSubmissionItem],
    summary="Historial de submissions del usuario",
    responses={
        200: {"description": "Lista de submissions", "content": {"application/json": {"example": ME_SUBMISSIONS_EXAMPLE}}}
    },
)
def get_current_user_submissions(subject_id: int | None = None, current=Depends(get_current_user), db: Session = Depends(get_db)):
    """Obtener historial de submissions del usuario actual."""
    subject_ids = _resolve_user_subject_scope(db, current.id, subject_id)
    return crud.get_user_submissions(db, current.id, subject_ids=subject_ids)


@app.get(
    "/me/topic-retroaccions",
    response_model=list[schemas.TopicSecretUnlockOut],
    summary="Retroaccions desbloquejades per tema",
)
def get_current_user_topic_retroaccions(subject_id: int | None = None, current=Depends(get_current_user), db: Session = Depends(get_db)):
    subject_ids = _resolve_user_subject_scope(db, current.id, subject_id)
    return crud.get_user_topic_secret_unlocks(db, current.id, subject_ids)
