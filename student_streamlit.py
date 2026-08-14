import html
import json
import mimetypes
import uuid
import urllib.error
import urllib.parse
import urllib.request

import streamlit as st
import streamlit.components.v1 as components

# Interfaz de uso para alumnado.
st.set_page_config(page_title="Jutge Alumnat", layout="wide")


def api_post_form(base_url: str, path: str, form_data: dict, token: str | None = None):
    body = urllib.parse.urlencode(form_data).encode()
    req = urllib.request.Request(f"{base_url}{path}", data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode())
        except Exception:
            payload = {"detail": str(exc)}
        return exc.code, payload
    except Exception as exc:
        return 0, {"detail": str(exc)}


def api_post_multipart(base_url: str, path: str, fields: dict, filename: str, file_bytes: bytes, token: str):
    boundary = "----WebKitFormBoundary" + uuid.uuid4().hex
    body = bytearray()

    def add_field(name: str, value: str) -> None:
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        body.extend(value.encode())
        body.extend(b"\r\n")

    def add_file(field_name: str, filename_value: str, data_bytes: bytes) -> None:
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(
            f'Content-Disposition: form-data; name="{field_name}"; filename="{filename_value}"\r\n'.encode()
        )
        content_type = mimetypes.guess_type(filename_value)[0] or "application/octet-stream"
        body.extend(f"Content-Type: {content_type}\r\n\r\n".encode())
        body.extend(data_bytes)
        body.extend(b"\r\n")

    for key, value in fields.items():
        add_field(key, str(value))

    add_file("code_file", filename, file_bytes)
    body.extend(f"--{boundary}--\r\n".encode())

    req = urllib.request.Request(f"{base_url}{path}", data=bytes(body), method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode())
        except Exception:
            payload = {"detail": str(exc)}
        return exc.code, payload
    except Exception as exc:
        return 0, {"detail": str(exc)}


def api_get(base_url: str, path: str, token: str):
    req = urllib.request.Request(f"{base_url}{path}", method="GET")
    req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode())
        except Exception:
            payload = {"detail": str(exc)}
        return exc.code, payload
    except Exception as exc:
        return 0, {"detail": str(exc)}


def ensure_session():
    defaults = {
        "base_url": "http://localhost:8000",
        "token": None,
        "profile": None,
        "default_username": "alumno_a_base",
        "default_password": "alumno123",
        "flash_message": None,
        "flash_target": None,
        "pending_job_id": None,
        "uploader_nonce": 0,
        "selected_subject_id": None,
        "selected_exercise_id": None,
        "last_result_exercise_id": None,
        "last_result_verdict": None,
        "last_result_status": None,
        "inline_info_exercise_id": None,
        "inline_info_message": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def show_inline_info(message: str):
    safe_message = html.escape(message)
    st.markdown(
        f"""
        <style>
        .jutge-inline-info {{
            background: #f3f4f6;
            border: 1px solid #d1d5db;
            color: #374151;
            border-radius: 0.5rem;
            padding: 0.6rem 0.9rem;
            margin: 0.4rem 0 0.6rem 0;
        }}
        </style>
        <div class="jutge-inline-info">{safe_message}</div>
        """,
        unsafe_allow_html=True,
    )


def queue_flash(message: str, target: str = "top"):
    st.session_state.flash_message = message
    st.session_state.flash_target = target


def show_queued_flash(target: str):
    flash_message = st.session_state.get("flash_message")
    flash_target = st.session_state.get("flash_target")
    if flash_message and flash_target == target:
        safe_message = html.escape(flash_message)
        # Color rojo para errores, verde para éxito
        if flash_target == "error":
            bg_color = "#fee2e2"
            border_color = "#fca5a5"
            text_color = "#991b1b"
        else:
            bg_color = "#d1fae5"
            border_color = "#6ee7b7"
            text_color = "#065f46"
        st.markdown(
            f"""
            <style>
            .jutge-flash-message {{
                background: {bg_color};
                border: 1px solid {border_color};
                color: {text_color};
                border-radius: 0.5rem;
                padding: 0.75rem 1rem;
                margin-bottom: 1rem;
            }}
            </style>
            <div class="jutge-flash-message">{safe_message}</div>
            """,
            unsafe_allow_html=True,
        )
        st.session_state.flash_message = None
        st.session_state.flash_target = None


def schedule_soft_refresh():
    """Schedule a Streamlit rerun to check job status without losing session."""
    import time
    time.sleep(2)
    st.rerun()


def render_login():
    st.title("Jutge Alumnat")
    st.caption("Pantalla 1/2: Inici de sessió")

    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("Usuari", value=st.session_state.default_username)
        password = st.text_input("Contrasenya", value=st.session_state.default_password, type="password")
        submitted = st.form_submit_button("Inicia sessió")

    if not submitted:
        return

    if not username or not password:
        st.warning("Introdueix usuari i contrasenya.")
        return

    status, token_data = api_post_form(
        st.session_state.base_url,
        "/token",
        {"username": username, "password": password},
    )

    if status != 200:
        st.error(token_data.get("detail", "No s'ha pogut iniciar sessió"))
        return

    token = token_data.get("access_token")
    if not token:
        st.error("L'API no ha retornat access_token")
        return

    status, me = api_get(st.session_state.base_url, "/me", token)
    if status != 200:
        st.error(me.get("detail", "No s'ha pogut validar l'usuari"))
        return

    if me.get("role") != "student":
        st.error("Aquesta pàgina només està disponible per a alumnes.")
        return

    st.session_state.token = token
    st.session_state.profile = me
    st.success("Sessió iniciada")
    st.rerun()


def render_dashboard():
    st.title("Jutge Alumnat")
    st.caption("Pantalla 2/2: Envia la teva tasca")

    base_url = st.session_state.base_url
    token = st.session_state.token

    sb_status, enrolled_subjects = api_get(base_url, "/subjects/me", token)
    enrolled_subjects = enrolled_subjects if sb_status == 200 and isinstance(enrolled_subjects, list) else []
    if not enrolled_subjects:
        st.warning("No tens assignatures inscrites. Contacta amb el professor.")
        return

    subject_options = {
        f"{subject.get('code') or 'SUBJ'} - {subject.get('name') or 'Sense nom'} (id={subject.get('id')})": subject.get("id")
        for subject in enrolled_subjects
        if subject.get("id") is not None
    }
    subject_labels = list(subject_options.keys())
    default_index = 0
    if st.session_state.selected_subject_id in subject_options.values():
        selected_label = next((label for label, sid in subject_options.items() if sid == st.session_state.selected_subject_id), subject_labels[0])
        default_index = subject_labels.index(selected_label)

    st.markdown("### Assignatura")
    selected_subject_label = st.selectbox("Assignatura activa", options=subject_labels, index=default_index)
    selected_subject_id = int(subject_options[selected_subject_label])
    st.session_state.selected_subject_id = selected_subject_id
    subject_query = f"?subject_id={selected_subject_id}"

    pending_job_id = st.session_state.get("pending_job_id")
    pending_inline_message = None
    should_refresh_pending = False
    if pending_job_id:
        pending_status, pending_payload = api_get(base_url, f"/jobs/{pending_job_id}", token)
        if pending_status == 200:
            current_status = str(pending_payload.get("status") or "")
            if current_status in {"pending", "evaluating"}:
                pending_inline_message = f"Job {pending_job_id} en curs (estat: {current_status})"
                should_refresh_pending = True
            else:
                st.session_state.pending_job_id = None
                verdict = pending_payload.get("verdict")
                current_exercise_id = st.session_state.get("selected_exercise_id")
                # Si la correccion termina, limpiar el uploader para evitar reenvios accidentales
                if current_status == "completed":
                    st.session_state.uploader_nonce = int(st.session_state.uploader_nonce) + 1
                    st.session_state.last_result_exercise_id = current_exercise_id
                    st.session_state.last_result_verdict = verdict
                    st.session_state.last_result_status = current_status
                    st.session_state.inline_info_exercise_id = None
                    st.session_state.inline_info_message = None

                if current_status != "completed":
                    queue_flash("La correccio ha finalitzat amb error.", target="top")
                st.rerun()
        else:
            # Evita bucles de refresco si el job ya no es consultable por cualquier motivo.
            st.session_state.pending_job_id = None

    show_queued_flash("top")
    show_queued_flash("error")

    col_a, col_b = st.columns([4, 1])
    with col_a:
        st.write(f"Connectat com a **{st.session_state.profile.get('username')}**")
        st.write(f"Rol: **{st.session_state.profile.get('role')}**")

    exercise_status, exercises = api_get(base_url, f"/exercises{subject_query}", token)
    progress_status, progress = api_get(base_url, f"/me/progress{subject_query}", token)
    submissions_status, submissions = api_get(base_url, f"/me/submissions{subject_query}", token)

    exercises = exercises if exercise_status == 200 and isinstance(exercises, list) else []
    progress = progress if progress_status == 200 and isinstance(progress, dict) else {}
    submissions = submissions if submissions_status == 200 and isinstance(submissions, list) else []

    def normalize_metric(value):
        if isinstance(value, (int, float, str)):
            return value
        return 0

    completed_value = progress.get("completed_exercises_count", progress.get("completed_exercises", 0))
    attempts_value = progress.get("total_attempts", progress.get("attempts", 0))

    progress_cols = st.columns(3)
    progress_cols[0].metric("Exercicis totals", normalize_metric(progress.get("total_exercises", 0)))
    progress_cols[1].metric("Completats", normalize_metric(completed_value))
    progress_cols[2].metric("Intentos totals", normalize_metric(attempts_value))

    st.subheader("Enviar tasca")
    selected_id = None
    if not exercises:
        st.info("Encara no hi ha exercicis disponibles.")
    else:
        exercise_by_id = {
            int(ex.get("id")): ex
            for ex in exercises
            if ex.get("id") is not None
        }
        exercise_ids = list(exercise_by_id.keys())
        if not exercise_ids:
            st.info("Encara no hi ha exercicis disponibles.")
            selected_exercise = None
        else:
            previous_selected_id = st.session_state.selected_exercise_id
            if previous_selected_id not in exercise_ids:
                previous_selected_id = exercise_ids[0]

            selected_id = st.selectbox(
                "Tria un exercici",
                options=exercise_ids,
                index=exercise_ids.index(previous_selected_id),
                format_func=lambda ex_id: f"{exercise_by_id[ex_id].get('title')} (id={ex_id})",
            )

            # Si el usuario cambió de ejercicio, limpiar el uploader
            if selected_id != st.session_state.selected_exercise_id:
                st.session_state.uploader_nonce = int(st.session_state.uploader_nonce) + 1
            st.session_state.selected_exercise_id = selected_id

            selected_exercise = exercise_by_id.get(selected_id)

        if selected_exercise:
            completion_label = "Sí" if selected_exercise.get("completed") else "No"
            st.markdown(
                f"**{selected_exercise.get('title')}** — nivell: {selected_exercise.get('level')} — obligatori: {'Sí' if selected_exercise.get('is_required') else 'No'}"
            )
            st.write(selected_exercise.get("description") or "Sense descripció")
            st.write(f"Completat: **{completion_label}**")

            inline_ex_id = st.session_state.get("inline_info_exercise_id")
            inline_message = st.session_state.get("inline_info_message")
            if selected_id == inline_ex_id and inline_message:
                show_inline_info(inline_message)

            if selected_id == st.session_state.get("selected_exercise_id") and pending_inline_message:
                show_inline_info(pending_inline_message)

            # Mostrar resultado de la ultima correccion justo debajo de "Completat"
            last_ex_id = st.session_state.get("last_result_exercise_id")
            last_status = st.session_state.get("last_result_status")
            last_verdict = st.session_state.get("last_result_verdict")
            if selected_id == last_ex_id and last_status == "completed":
                if last_verdict == "AC":
                    st.success(f"Correccio finalitzada. Veredicte: {last_verdict}")
                elif last_verdict:
                    st.error(f"Correccio finalitzada. Veredicte: {last_verdict}")
                else:
                    st.info("Correccio finalitzada.")

            if selected_exercise.get("completed"):
                st.success("Ja has completat aquest exercici correctament. No cal enviar mes entregues.")
            else:
                with st.form("submission_form", clear_on_submit=False):
                    uploader_key = f"submission_file_{st.session_state.uploader_nonce}"
                    code_file = st.file_uploader("Arxiu .c", type=["c"], key=uploader_key)
                    submit = st.form_submit_button("Enviar entrega")

                if submit:
                    if not code_file:
                        st.warning("Selecciona un fitxer .c abans d'enviar.")
                    else:
                        code_bytes = code_file.getvalue()
                        status, result = api_post_multipart(
                            base_url,
                            "/submissions",
                            {"exercise_id": selected_id},
                            code_file.name,
                            code_bytes,
                            token,
                        )
                        if status == 200:
                            job_id = result.get("job_id")
                            st.session_state.pending_job_id = job_id
                            st.session_state.inline_info_exercise_id = selected_id
                            st.session_state.inline_info_message = f"Entrega enviada correctament. Job id: {job_id}"
                            st.session_state.last_result_exercise_id = None
                            st.session_state.last_result_verdict = None
                            st.session_state.last_result_status = None
                            st.rerun()
                        else:
                            st.error(result.get("detail", "No s'ha pogut enviar l'entrega"))

    st.subheader("Historial d'entregues")
    if selected_id is not None:
        submissions = [item for item in submissions if item.get("exercise_id") == selected_id]

    if submissions:
        submission_rows = []
        for item in submissions:
            submission_rows.append(
                {
                    "job_id": item.get("job_id"),
                    "exercise_id": item.get("exercise_id"),
                    "status": item.get("status"),
                    "verdict": item.get("verdict") or "pendents",
                    "passed_all": item.get("passed_all"),
                    "created_at": item.get("created_at"),
                }
            )
        st.dataframe(submission_rows, use_container_width=True)
    else:
        st.info("No tens entregues al sistema encara.")

    if should_refresh_pending:
        schedule_soft_refresh()


def main():
    ensure_session()
    if not st.session_state.token:
        render_login()
    else:
        render_dashboard()


if __name__ == "__main__":
    main()
