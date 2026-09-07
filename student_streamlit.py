import html
import json
import mimetypes
import os
import uuid
import urllib.error
import urllib.parse
import urllib.request

import streamlit as st
import streamlit.components.v1 as components

# Interfaz de uso para alumnado.
st.set_page_config(page_title="Jutge Alumnat", layout="wide")
st.markdown(
    """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    [data-testid="stToolbar"] {display: none !important;}
    [data-testid="stDecoration"] {display: none !important;}
    [data-testid="stStatusWidget"] {display: none !important;}
    </style>
    """,
    unsafe_allow_html=True,
)


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
        "base_url": os.getenv("JUTGE_API_BASE_URL", "http://localhost:8000"),
        "token": None,
        "profile": None,
        "flash_message": None,
        "flash_target": None,
        "pending_job_id": None,
        "uploader_nonce": 0,
        "selected_subject_id": None,
        "selected_topic_filter_id": None,
        "selected_exercise_id": None,
        "last_result_exercise_id": None,
        "last_result_verdict": None,
        "last_result_status": None,
        "inline_info_exercise_id": None,
        "inline_info_message": None,
        "_lti_exercise_id_processed": False,
        "_lti_pending_exercise_id": None,
        "_lti_params_processed": False,  # Flag para procesar parámetros LTI solo una vez
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


LEVEL_TO_CA = {
    "beginner": "bàsic",
    "mid": "intermedi",
    "expert": "difícil",
}


def level_to_ca(level_value: str) -> str:
    return LEVEL_TO_CA.get(str(level_value or "").strip().lower(), str(level_value or ""))


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


def render_lti_required_message():
    st.title("Jutge Alumnat")
    st.caption("Acces exclusiu via Atenea (LTI)")
    st.warning("El login local està deshabilitat per a alumnat.")
    st.info("Accedeix a aquesta pàgina només des del llançament LTI d'Atenea.")


def render_verdict_guide():
    with st.expander("Que vol dir cada veredicte?"):
        st.markdown(
            """
            - **AC (Accepted):** Solucio correcta. Tots els jocs de prova passen.
            - **WA (Wrong Answer):** El programa compila i executa, pero la sortida no coincideix amb l'esperada.
            - **CE (Compilation Error):** Error de compilacio. Revisa includes, sintaxi i avisos del compilador.
            - **RTE (Runtime Error):** Error en execucio (segmentation fault, divisio per zero, etc.).
            - **TLE (Time Limit Exceeded):** S'ha superat el temps maxim. Cal optimitzar la solucio.
            - **OOM (Out of Memory):** S'ha superat el limit de memoria.
            """
        )


def render_dashboard():
    st.title("Jutge Alumnat")

    base_url = st.session_state.base_url
    token = st.session_state.token

    sb_status, enrolled_subjects = api_get(base_url, "/subjects/me", token)
    enrolled_subjects = enrolled_subjects if sb_status == 200 and isinstance(enrolled_subjects, list) else []
    if not enrolled_subjects:
        st.warning("No tens assignatures inscrites. Contacta amb el professor.")
        return

    subject_options = {
        f"{subject.get('code') or 'SUBJ'} - {subject.get('name') or 'Sense nom'}": subject.get("id")
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

    topic_secrets_status, topic_secrets = api_get(base_url, f"/me/topic-retroaccions{subject_query}", token)
    topic_secrets = topic_secrets if topic_secrets_status == 200 and isinstance(topic_secrets, list) else []

    col_a, col_b = st.columns([4, 1])
    with col_a:
        st.write(f"Connectat com a **{st.session_state.profile.get('username')}**")
        st.write(f"Rol: **{st.session_state.profile.get('role')}**")

    exercise_status, exercises = api_get(base_url, f"/exercises{subject_query}", token)
    topics_status, topics = api_get(base_url, f"/topics{subject_query}", token)
    progress_status, progress = api_get(base_url, f"/me/progress{subject_query}", token)
    submissions_status, submissions = api_get(base_url, f"/me/submissions{subject_query}", token)

    exercises = exercises if exercise_status == 200 and isinstance(exercises, list) else []
    topics = topics if topics_status == 200 and isinstance(topics, list) else []
    progress = progress if progress_status == 200 and isinstance(progress, dict) else {}
    submissions = submissions if submissions_status == 200 and isinstance(submissions, list) else []

    pending_lti_exercise_id = st.session_state.get("_lti_pending_exercise_id")
    if pending_lti_exercise_id is not None and not st.session_state.get("_lti_exercise_id_processed"):
        matched_exercise = next(
            (
                exercise
                for exercise in exercises
                if exercise.get("id") is not None and int(exercise.get("id")) == int(pending_lti_exercise_id)
            ),
            None,
        )
        if matched_exercise:
            matched_topic_id = matched_exercise.get("topic_id")
            if matched_topic_id is not None:
                st.session_state.selected_topic_filter_id = int(matched_topic_id)
            st.session_state.selected_exercise_id = int(matched_exercise.get("id"))
        st.session_state._lti_exercise_id_processed = True
        st.session_state._lti_pending_exercise_id = None

    topic_filter_options = {"Tots els temes": None}
    for topic in topics:
        topic_id = topic.get("id")
        if topic_id is None:
            continue
        topic_filter_options[f"{topic.get('name') or 'Tema'}"] = int(topic_id)

    topic_labels = list(topic_filter_options.keys())
    selected_topic_label = topic_labels[0]
    selected_topic_id = st.session_state.get("selected_topic_filter_id")
    if selected_topic_id is not None:
        selected_topic_label = next(
            (label for label, topic_id in topic_filter_options.items() if topic_id == selected_topic_id),
            topic_labels[0],
        )
    selected_topic_label = st.selectbox(
        "Filtre per tema",
        options=topic_labels,
        index=topic_labels.index(selected_topic_label),
    )
    selected_topic_id = topic_filter_options[selected_topic_label]
    st.session_state.selected_topic_filter_id = selected_topic_id

    st.markdown("### Temes")
    filtered_topic_feedback = [
        item
        for item in topic_secrets
        if item.get("topic_id") is not None and (selected_topic_id is None or int(item.get("topic_id")) == int(selected_topic_id))
    ]
    if filtered_topic_feedback:
        for item in filtered_topic_feedback:
            topic_name = item.get("topic_name") or "Tema"
            retroaccio = str(item.get("retroaccio") or "").strip()
            if not retroaccio:
                continue
            if item.get("newly_unlocked"):
                st.success(f"Retroaccio desbloquejada a {topic_name}: {retroaccio}")
            else:
                st.info(f"Retroaccio de {topic_name}: {retroaccio}")
    else:
        st.caption("No tens retroaccions desbloquejades per aquest filtre de tema.")

    def normalize_metric(value):
        if isinstance(value, (int, float, str)):
            return value
        return 0

    completed_value = progress.get("completed_exercises_count", progress.get("completed_exercises", 0))
    attempts_value = progress.get("total_attempts", progress.get("attempts", 0))

    progress_cols = st.columns(3)
    progress_cols[0].metric("Exercicis totals", normalize_metric(progress.get("total_exercises", 0)))
    progress_cols[1].metric("Completats", normalize_metric(completed_value))
    progress_cols[2].metric("Intents totals", normalize_metric(attempts_value))

    st.subheader("Enviar tasca")
    selected_id = None
    filtered_exercises = exercises
    if selected_topic_id is not None:
        filtered_exercises = [exercise for exercise in exercises if exercise.get("topic_id") == selected_topic_id]

    if not filtered_exercises:
        st.info("Encara no hi ha exercicis disponibles.")
    else:
        exercise_by_id = {
            int(ex.get("id")): ex
            for ex in filtered_exercises
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
                format_func=lambda ex_id: f"{exercise_by_id[ex_id].get('title')}",
            )

            # Si el usuario cambió de ejercicio, limpiar el uploader
            if selected_id != st.session_state.selected_exercise_id:
                st.session_state.uploader_nonce = int(st.session_state.uploader_nonce) + 1
            st.session_state.selected_exercise_id = selected_id

            selected_exercise = exercise_by_id.get(selected_id)

        if selected_exercise:
            completion_label = "Sí" if selected_exercise.get("completed") else "No"
            expected_submission_type = str(selected_exercise.get("expected_submission_type") or "c_file")
            expected_file_label = ".zip (projecte amb Makefile)" if expected_submission_type == "zip_makefile" else ".c"
            st.markdown(
                f"**{selected_exercise.get('title')}** — nivell: {level_to_ca(selected_exercise.get('level'))} — obligatori: {'Sí' if selected_exercise.get('is_required') else 'No'} — tipus entrega: {expected_file_label}"
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
                    allowed_types = ["zip"] if expected_submission_type == "zip_makefile" else ["c"]
                    code_file = st.file_uploader(
                        f"Arxiu requerit: {expected_file_label}",
                        type=allowed_types,
                        key=uploader_key,
                    )
                    submit = st.form_submit_button("Enviar entrega")

                if submit:
                    if not code_file:
                        st.warning(f"Selecciona un fitxer {expected_file_label} abans d'enviar.")
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
    if selected_topic_id is not None:
        exercise_ids_in_topic = {
            int(ex.get("id"))
            for ex in exercises
            if ex.get("id") is not None and ex.get("topic_id") == selected_topic_id
        }
        submissions = [item for item in submissions if item.get("exercise_id") in exercise_ids_in_topic]

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

    render_verdict_guide()

    if should_refresh_pending:
        schedule_soft_refresh()


def _try_restore_from_localstorage():
    """Try to restore token from localStorage using a Streamlit component."""
    # This component reads from localStorage and stores the value in a hidden element
    # Unfortunately, this is limited because JavaScript execution in Streamlit components
    # doesn't allow synchronous communication back to Python.
    # For now, we rely on query params + localStorage for persistence in the browser.
    pass


def main():
    ensure_session()

    # Setup JavaScript to persist token in localStorage
    components.html("""
    <script>
    // Auto-save token to localStorage when present in URL or session
    const params = new URLSearchParams(window.location.search);
    const urlToken = params.get('token');
    if (urlToken) {
        localStorage.setItem('jutge_auth_token', urlToken);
        const subjectId = params.get('subject_id');
        if (subjectId) localStorage.setItem('jutge_subject_id', subjectId);
    }
    </script>
    """, height=0)

    # LTI SSO: procesar parámetros ?token=xxx solo si no los hemos procesado ya
    params = st.query_params
    lti_token = params.get("token")
    lti_subject_id = params.get("subject_id")
    lti_exercise_id = params.get("exercise_id")
    
    if lti_token and not st.session_state._lti_params_processed and not st.session_state.token:
        # Verificar que el token es válido contra la API
        status, me = api_get(st.session_state.base_url, "/me", lti_token)
        if status == 200:
            st.session_state.token = lti_token
            st.session_state.profile = me
            st.session_state._lti_params_processed = True
            if lti_subject_id:
                try:
                    st.session_state.selected_subject_id = int(lti_subject_id)
                except (ValueError, TypeError):
                    pass
            if lti_exercise_id:
                try:
                    st.session_state._lti_pending_exercise_id = int(lti_exercise_id)
                except (ValueError, TypeError):
                    pass
            st.rerun()
        else:
            st.error("Token LTI inválido. Accede de nuevo desde Atenea.")
            return

    if not st.session_state.token:
        render_lti_required_message()
    else:
        render_dashboard()


if __name__ == "__main__":
    main()
