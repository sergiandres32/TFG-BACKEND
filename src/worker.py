#!/usr/bin/env python3
"""
worker.py: Worker que procesa Jobs de evaluación de forma asincrónica
Flujo:
1. Lee jobs pendientes de la DB
2. Marca como "evaluating"
3. Ejecuta judge_v2 (en Docker si está disponible, sino local)
4. Guarda resultado en DB (Run + completion si AC)
5. Marca como "completed" o "failed"
"""

import os
import sys
import time
import json
import base64
import io
import shutil
import subprocess
import tempfile
import zipfile
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Agregar raíz del proyecto al path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import judge_v2
from src.api.models import Base, Job, Run, UserExerciseCompletion, RunVerdict, JobStatus
from src.api.database import SessionLocal
import hashlib


SUBMISSION_V2_PREFIX = "__JUTGE_SUBMISSION_V2__:"
MAX_ZIP_SIZE_BYTES = 5 * 1024 * 1024
MAX_EXTRACTED_SIZE_BYTES = 20 * 1024 * 1024


def _build_tests_obj(db_session: sessionmaker, exercise_id: int) -> dict:
    from src.api.models import TestCase

    session = db_session()
    try:
        test_cases = session.query(TestCase).filter(TestCase.exercise_id == exercise_id).all()
        return {
            "tests": [
                {
                    "id": tc.name,
                    "mode": tc.content.get("mode", "exact"),
                    "input": tc.content.get("input", ""),
                    "expected": tc.content.get("expected", ""),
                    "ignore_whitespace": tc.content.get("ignore_whitespace", False),
                }
                for tc in test_cases
            ]
        }
    finally:
        session.close()


def _parse_submission_payload(raw_code: str) -> dict:
    if not raw_code.startswith(SUBMISSION_V2_PREFIX):
        return {"format": "plain_c", "code_text": raw_code}

    payload_json = raw_code[len(SUBMISSION_V2_PREFIX):]
    payload = json.loads(payload_json)
    submission_format = str(payload.get("format") or "").strip()

    if submission_format == "zip_makefile":
        zip_b64 = payload.get("zip_b64")
        if not isinstance(zip_b64, str) or not zip_b64:
            raise ValueError("Invalid zip payload")
        zip_bytes = base64.b64decode(zip_b64)
        if len(zip_bytes) > MAX_ZIP_SIZE_BYTES:
            raise ValueError("Zip submission too large")
        return {
            "format": "zip_makefile",
            "filename": str(payload.get("filename") or "submission.zip"),
            "zip_bytes": zip_bytes,
        }

    raise ValueError("Unsupported submission format")


def _safe_extract_zip(zip_bytes: bytes, project_dir: str) -> None:
    total_size = 0
    root_abs = os.path.abspath(project_dir)

    try:
        archive = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile as exc:
        raise ValueError(f"Invalid zip file: {exc}")

    with archive:
        for entry in archive.infolist():
            if entry.is_dir():
                continue

            name = entry.filename.replace("\\", "/")
            if name.startswith("/"):
                raise ValueError("Zip contains absolute paths")

            parts = [part for part in name.split("/") if part not in ("", ".")]
            if any(part == ".." for part in parts):
                raise ValueError("Zip contains invalid relative paths")
            if not parts:
                continue

            total_size += max(0, int(entry.file_size or 0))
            if total_size > MAX_EXTRACTED_SIZE_BYTES:
                raise ValueError("Extracted project is too large")

            target_path = os.path.abspath(os.path.join(project_dir, *parts))
            if not target_path.startswith(root_abs + os.sep):
                raise ValueError("Zip extraction attempted outside destination")

            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with archive.open(entry, "r") as src, open(target_path, "wb") as dst:
                shutil.copyfileobj(src, dst)


def _resolve_build_executable(project_dir: str) -> str:
    preferred = ["submission", "main", "a.out"]
    for name in preferred:
        candidate = os.path.join(project_dir, name)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate

    executable_candidates = []
    for root, _, files in os.walk(project_dir):
        for name in files:
            path = os.path.join(root, name)
            if os.path.isfile(path) and os.access(path, os.X_OK):
                executable_candidates.append(path)

    if len(executable_candidates) == 1:
        return executable_candidates[0]
    if not executable_candidates:
        raise ValueError("Makefile build succeeded but no executable was found")
    raise ValueError("Multiple executables found. Please generate a single binary (recommended: submission)")


def _evaluate_prebuilt_executable(executable_path: str, tests_obj: dict, timeout: int = 5) -> dict:
    start_time = time.time()

    results = []
    all_passed = True
    has_tle = False
    has_rte = False
    has_oom = False

    for test in tests_obj.get("tests", []):
        test_id = test.get("id") or test.get("name") or "unnamed"
        input_data = test.get("input", "")

        run_result = judge_v2.run_executable(executable_path, input_data, timeout=timeout)

        if run_result.get("oom_killed"):
            has_oom = True
            all_passed = False
            results.append({"test_id": test_id, "passed": False, "details": "Out of Memory"})
            continue

        if run_result.get("timed_out"):
            has_tle = True
            all_passed = False
            results.append({"test_id": test_id, "passed": False, "details": "Time Limit Exceeded"})
            continue

        if run_result.get("exit_code") != 0:
            has_rte = True
            all_passed = False
            results.append(
                {
                    "test_id": test_id,
                    "passed": False,
                    "details": f"Runtime Error (exit code {run_result.get('exit_code')})",
                }
            )
            continue

        eval_result = judge_v2.evaluate_test(run_result.get("stdout", ""), test)
        if not eval_result.get("passed"):
            all_passed = False
        results.append(
            {
                "test_id": test_id,
                "passed": bool(eval_result.get("passed")),
                "details": eval_result.get("verdict_detail"),
            }
        )

    if all_passed and results:
        verdict = "AC"
    elif has_oom:
        verdict = "OOM"
    elif has_tle:
        verdict = "TLE"
    elif has_rte:
        verdict = "RTE"
    else:
        verdict = "WA"

    duration = int((time.time() - start_time) * 1000)
    return {
        "verdict": verdict,
        "passed_all": all_passed,
        "results": results,
        "compile_error": None,
        "duration_ms": duration,
    }


def _submission_preview_text(raw_code: str) -> str:
    try:
        payload = _parse_submission_payload(raw_code)
        if payload.get("format") == "zip_makefile":
            filename = payload.get("filename") or "submission.zip"
            zip_size = len(payload.get("zip_bytes") or b"")
            return f"[zip_makefile] filename={filename} size={zip_size}"
        return (payload.get("code_text") or "")[:1000]
    except Exception:
        return (raw_code or "")[:1000]


def evaluate_job_submission(job_id: int, user_id: int, exercise_id: int, code: str, db: sessionmaker, timeout: int = 5):
    tests_obj = _build_tests_obj(db, exercise_id)
    if not tests_obj.get("tests"):
        return {"error": "No test cases found", "verdict": "CE"}

    try:
        payload = _parse_submission_payload(code)

        if payload.get("format") == "plain_c":
            return judge_v2.run_and_evaluate_all_tests(payload.get("code_text") or "", tests_obj, timeout=timeout)

        if payload.get("format") == "zip_makefile":
            with tempfile.TemporaryDirectory(prefix="judge_project_") as tmp_dir:
                project_dir = os.path.join(tmp_dir, "project")
                os.makedirs(project_dir, exist_ok=True)
                _safe_extract_zip(payload.get("zip_bytes") or b"", project_dir)

                makefile_upper = os.path.join(project_dir, "Makefile")
                makefile_lower = os.path.join(project_dir, "makefile")
                if not os.path.exists(makefile_upper) and not os.path.exists(makefile_lower):
                    return {
                        "verdict": "CE",
                        "passed_all": False,
                        "results": [],
                        "compile_error": "Zip project must include Makefile or makefile at project root",
                        "duration_ms": 0,
                    }

                build = subprocess.run(
                    ["make", "-C", project_dir],
                    capture_output=True,
                    text=True,
                    timeout=timeout + 10,
                )
                if build.returncode != 0:
                    return {
                        "verdict": "CE",
                        "passed_all": False,
                        "results": [],
                        "compile_error": (build.stdout + "\n" + build.stderr).strip()[:8000],
                        "duration_ms": 0,
                    }

                executable = _resolve_build_executable(project_dir)
                return _evaluate_prebuilt_executable(executable, tests_obj, timeout=timeout)

        return {"error": "Unsupported submission format", "verdict": "CE"}

    except (ValueError, zipfile.BadZipFile, subprocess.TimeoutExpired) as exc:
        return {
            "verdict": "CE",
            "passed_all": False,
            "results": [],
            "compile_error": str(exc),
            "duration_ms": 0,
        }
    except Exception as exc:
        return {"error": f"Execution failed: {exc}", "verdict": "RTE"}


def process_job(job: Job, db_session_factory):
    """Procesa un job individual."""
    db = db_session_factory()
    try:
        print(f"[Worker] Processing job {job.id} (user={job.user_id}, exercise={job.exercise_id})", flush=True)
        
        # Marcar como evaluating
        crud_update_job_to_evaluating(db, job.id)
        
        # Evaluar
        judge_result = evaluate_job_submission(job.id, job.user_id, job.exercise_id, job.code, db_session_factory)
        
        if "error" in judge_result:
            print(f"[Worker] Job {job.id} failed: {judge_result['error']}", flush=True)
            crud_update_job_failed(db, job.id, judge_result["error"])
            return
        
        # Mapear verdict
        verdict_str = judge_result.get("verdict", "WA")
        try:
            verdict = RunVerdict[verdict_str]
        except KeyError:
            verdict = RunVerdict.WA
        
        passed = verdict_str == "AC"
        
        # Crear Run
        # Read the latest job row in this DB session to ensure code is available
        fresh_job = db.query(Job).filter(Job.id == job.id).first()
        submitted_code = (fresh_job.code if fresh_job and fresh_job.code is not None else (job.code or ""))

        # Log a short excerpt of the submitted code, include a short preview and a SHA256
        excerpt = _submission_preview_text(submitted_code)[:400]
        print(f"[Worker] job={job.id} submitted_code_excerpt={excerpt!r}", flush=True)
        code_preview = _submission_preview_text(submitted_code)
        code_hash = hashlib.sha256((submitted_code or "").encode("utf-8")).hexdigest() if submitted_code else None

        print(f"[Worker] job={job.id} preview_len={len(code_preview)} sha={code_hash}", flush=True)

        db_run = Run(
            user_id=job.user_id,
            exercise_id=job.exercise_id,
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
        db.flush()
        
        # Crear completion si pasó
        if passed:
            existing = db.query(UserExerciseCompletion).filter_by(user_id=job.user_id, exercise_id=job.exercise_id).first()
            if not existing:
                comp = UserExerciseCompletion(
                    user_id=job.user_id,
                    exercise_id=job.exercise_id,
                    attempts_needed=1,
                    best_run_id=db_run.id
                )
                db.add(comp)
        
        db.commit()
        
        # Marcar job como completed
        crud_update_job_completed(db, job.id, db_run.id)
        
        print(f"[Worker] Job {job.id} completed with verdict {verdict_str}", flush=True)
    
    except Exception as e:
        print(f"[Worker] Error processing job {job.id}: {e}", flush=True)
        crud_update_job_failed(db, job.id, str(e))
    
    finally:
        db.close()


def crud_update_job_to_evaluating(db, job_id: int):
    job = db.query(Job).filter(Job.id == job_id).first()
    if job:
        job.status = JobStatus.evaluating
        job.started_at = datetime.utcnow()
        db.commit()


def crud_update_job_completed(db, job_id: int, run_id: int):
    job = db.query(Job).filter(Job.id == job_id).first()
    if job:
        job.status = JobStatus.completed
        job.run_id = run_id
        job.completed_at = datetime.utcnow()
        db.commit()


def crud_update_job_failed(db, job_id: int, error_msg: str):
    job = db.query(Job).filter(Job.id == job_id).first()
    if job:
        job.status = JobStatus.failed
        job.error_message = error_msg[:500]  # Limitar a 500 chars
        job.completed_at = datetime.utcnow()
        db.commit()


def worker_loop(poll_interval: int = 2, batch_size: int = 5):
    """Loop principal del worker."""
    print("[Worker] Starting judge worker", flush=True)
    
    while True:
        try:
            db = SessionLocal()
            
            # Obtener jobs pendientes
            pending_jobs = db.query(Job).filter(Job.status == JobStatus.pending).limit(batch_size).all()
            
            if pending_jobs:
                print(f"[Worker] Found {len(pending_jobs)} pending jobs", flush=True)
                for job in pending_jobs:
                    process_job(job, SessionLocal)
            else:
                print(f"[Worker] No pending jobs, sleeping {poll_interval}s...", flush=True)
            
            db.close()
            time.sleep(poll_interval)
        
        except Exception as e:
            print(f"[Worker] Error in loop: {e}", flush=True)
            time.sleep(poll_interval)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Judge worker")
    parser.add_argument("--poll-interval", type=int, default=2, help="Segundos entre polls")
    parser.add_argument("--batch-size", type=int, default=5, help="Máximo jobs por ciclo")
    args = parser.parse_args()
    
    worker_loop(poll_interval=args.poll_interval, batch_size=args.batch_size)
