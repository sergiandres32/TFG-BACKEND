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


def evaluate_job_docker(job_id: int, user_id: int, exercise_id: int, code: str, db: sessionmaker, timeout: int = 5):
    """
    Evalúa un job usando Docker (run_in_docker.py) para mayor seguridad.
    Si Docker no está disponible, usa evaluación local.
    """
    # Obtener tests del ejercicio
    from src.api.models import TestCase
    session = db()
    try:
        test_cases = session.query(TestCase).filter(TestCase.exercise_id == exercise_id).all()
        if not test_cases:
            return {"error": "No test cases found", "verdict": "CE"}
        
        # Construir objeto tests
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
        
        # Intentar ejecutar en Docker (si falla, ejecuta local)
        judge_result = None
        try:
            # Guardar código temporalmente para Docker
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.c', delete=False) as f:
                f.write(code)
                code_file = f.name
            
            # Intentar usar run_in_docker.py (si existe)
            docker_available = False
            try:
                import subprocess
                result = subprocess.run(
                    ["python3", os.path.join(ROOT, "run_in_docker.py"), code_file, "--tests-json", json.dumps(tests_obj)],
                    capture_output=True,
                    text=True,
                    timeout=timeout + 10
                )
                if result.returncode == 0:
                    docker_available = True
                    judge_result = json.loads(result.stdout)
            except Exception as e:
                print(f"[Worker] Docker execution failed ({e}), falling back to local", flush=True)
            
            if not docker_available:
                # Ejecución local
                judge_result = judge_v2.run_and_evaluate_all_tests(code, tests_obj, timeout=timeout)
            
            os.unlink(code_file)
        except Exception as e:
            return {"error": f"Execution failed: {e}", "verdict": "RTE"}
        
        return judge_result
    
    finally:
        session.close()


def process_job(job: Job, db_session_factory):
    """Procesa un job individual."""
    db = db_session_factory()
    try:
        print(f"[Worker] Processing job {job.id} (user={job.user_id}, exercise={job.exercise_id})", flush=True)
        
        # Marcar como evaluating
        crud_update_job_to_evaluating(db, job.id)
        
        # Evaluar
        judge_result = evaluate_job_docker(job.id, job.user_id, job.exercise_id, job.code, db_session_factory)
        
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
        excerpt = (submitted_code or "")[:400]
        print(f"[Worker] job={job.id} submitted_code_excerpt={excerpt!r}", flush=True)
        code_preview = (submitted_code or "")[:1000]
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
