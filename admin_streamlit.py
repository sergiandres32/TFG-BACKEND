import html
import json
import os
import re
import base64
import io
import zipfile
import urllib.error
import urllib.parse
import urllib.request

import pandas as pd
import streamlit as st

# Este panel sigue el modelo reactivo de Streamlit:
# cada interacción vuelve a ejecutar el script completo y usa session_state
# para mantener autenticación, configuración y mensajes efímeros.
st.set_page_config(page_title="Jutge Admin", layout="wide")
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


def api_post_json(base_url: str, path: str, payload: dict, token: str):
    # Envía una petición POST JSON autenticada y devuelve estado + JSON.
    body = json.dumps(payload).encode()
    req = urllib.request.Request(f"{base_url}{path}", data=body, method="POST")
    req.add_header("Content-Type", "application/json")
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


def api_put_json(base_url: str, path: str, payload: dict, token: str):
    # Envía una petición PUT JSON autenticada y devuelve estado + JSON.
    body = json.dumps(payload).encode()
    req = urllib.request.Request(f"{base_url}{path}", data=body, method="PUT")
    req.add_header("Content-Type", "application/json")
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


def api_delete(base_url: str, path: str, token: str):
    # Envía una petición DELETE autenticada y devuelve estado + JSON.
    req = urllib.request.Request(f"{base_url}{path}", method="DELETE")
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


def api_get(base_url: str, path: str, token: str):
    # Realiza una petición GET autenticada y devuelve estado + JSON.
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


def api_get_bytes(base_url: str, path: str, token: str):
    # Realiza una petición GET autenticada y devuelve estado + bytes + headers.
    req = urllib.request.Request(f"{base_url}{path}", method="GET")
    req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            return response.status, response.read(), dict(response.headers.items()), None
    except urllib.error.HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode())
        except Exception:
            payload = {"detail": str(exc)}
        return exc.code, None, dict(exc.headers.items()) if exc.headers else {}, payload
    except Exception as exc:
        return 0, None, {}, {"detail": str(exc)}


def _filename_from_content_disposition(content_disposition: str, fallback: str = "entrega.bin") -> str:
    match = re.search(r'filename="?([^";]+)"?', content_disposition or "")
    if match:
        return match.group(1).strip()
    return fallback


def _sanitize_pack_name_fragment(raw: str, fallback: str) -> str:
    candidate = str(raw or "").strip().lower()
    # Normalize each filter fragment as kebab-case: words separated by '-'.
    cleaned = re.sub(r"[^a-z0-9]+", "-", candidate).strip("-")
    if cleaned:
        return cleaned
    fallback_cleaned = re.sub(r"[^a-z0-9]+", "-", str(fallback or "").strip().lower()).strip("-")
    return fallback_cleaned or "sense-valor"


LEVEL_TO_CA = {
    "beginner": "bàsic",
    "mid": "intermedi",
    "expert": "difícil",
}
CA_TO_LEVEL = {
    "bàsic": "beginner",
    "basic": "beginner",
    "intermedi": "mid",
    "difícil": "expert",
    "dificil": "expert",
}


def level_to_ca(level_value: str) -> str:
    return LEVEL_TO_CA.get(str(level_value or "").strip().lower(), str(level_value or ""))


def normalize_level_value(level_value: str) -> str:
    normalized = str(level_value or "").strip().lower()
    if normalized in LEVEL_TO_CA:
        return normalized
    return CA_TO_LEVEL.get(normalized, normalized)


def parse_json_items(raw_json: str):
    # Acepta un objeto JSON o un array de objetos JSON y normaliza a lista.
    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        return None, f"JSON invàlid: {exc}"

    if isinstance(parsed, dict):
        return [parsed], None

    if isinstance(parsed, list):
        if any(not isinstance(item, dict) for item in parsed):
            return None, "El JSON ha de ser un objecte o una llista d'objectes."
        return parsed, None

    return None, "El JSON ha de ser un objecte o una llista d'objectes."


def ensure_session():
    # Inicializa valores por defecto de sesión para configuración y autenticación.
    defaults = {
        "base_url": os.getenv("JUTGE_API_BASE_URL", "http://localhost:8000"),
        "token": None,
        "profile": None,
        "_lti_params_processed": False,
        "_lti_target_processed": False,
        "_lti_exercise_id_processed": False,
        "flash_message": None,
        "flash_target": None,
        "selected_subject_id": None,
        "admin_section": "Inici",
        "teacher_download_bytes": None,
        "teacher_download_filename": None,
        "teacher_download_mime": "application/octet-stream",
        "teacher_download_job_id": None,
        "teacher_auto_download_last_job_id": None,
        "teacher_bulk_download_bytes": None,
        "teacher_bulk_download_filename": None,
        "teacher_bulk_download_signature": None,
        "teacher_bulk_auto_download_signature": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def queue_flash(message: str, target: str = "top"):
    # Guarda un mensaje breve para mostrarlo en la siguiente ejecución completa de Streamlit.
    st.session_state.flash_message = message
    st.session_state.flash_target = target


def show_queued_flash(target: str):
    # Muestra el mensaje pendiente para un bloque concreto y deja que el navegador lo oculte automáticamente.
    flash_message = st.session_state.get("flash_message")
    flash_target = st.session_state.get("flash_target")
    if flash_message and flash_target == target:
        safe_message = html.escape(flash_message)
        st.markdown(
            f"""
            <style>
            @keyframes fadeOutFlashMessage {{
                0% {{ opacity: 1; max-height: 80px; margin-bottom: 1rem; }}
                80% {{ opacity: 1; max-height: 80px; margin-bottom: 1rem; }}
                100% {{ opacity: 0; max-height: 0; margin-bottom: 0; }}
            }}
            .jutge-flash-message {{
                background: #d1fae5;
                border: 1px solid #6ee7b7;
                color: #065f46;
                border-radius: 0.5rem;
                padding: 0.75rem 1rem;
                animation: fadeOutFlashMessage 2s ease forwards;
                overflow: hidden;
            }}
            </style>
            <div class="jutge-flash-message">{safe_message}</div>
            """,
            unsafe_allow_html=True,
        )
        st.session_state.flash_message = None
        st.session_state.flash_target = None


def logout():
    # Cierra la sesión local eliminando token y perfil.
    st.session_state.token = None
    st.session_state.profile = None
    st.session_state._lti_params_processed = False
    st.session_state._lti_target_processed = False
    st.session_state._lti_exercise_id_processed = False


def render_lti_required_message():
    # Acceso solo via launch LTI con rol docente.
    st.title("Jutge Admin")
    st.caption("Acces exclusiu via Atenea (LTI)")
    st.warning("El login local està deshabilitat.")
    st.info("Accedeix a aquest panell des del launch LTI d'Atenea amb rol de professor.")


def render_dashboard():
    # Muestra métricas básicas del sistema y permite crear temas y ejercicios.
    st.title("Tauler d'administració")

    token = st.session_state.token
    base_url = st.session_state.base_url

    sb_status, enrolled_subjects = api_get(base_url, "/subjects/me", token)
    enrolled_subjects = enrolled_subjects if sb_status == 200 and isinstance(enrolled_subjects, list) else []
    if not enrolled_subjects:
        st.warning("No tens assignatures inscrites. Contacta amb l'administrador.")
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

    show_queued_flash("top")

    # Carga inicial de datos para renderizar todo el tablero en una sola pasada.
    # Si alguna llamada falla, degradamos a lista vacía y mostramos mensajes en cada bloque.
    ex_status, exercises = api_get(base_url, f"/exercises{subject_query}", token)
    tp_status, topics = api_get(base_url, f"/topics{subject_query}", token)
    st_status, students = api_get(base_url, f"/students{subject_query}", token)
    qq_status, quiz_questions = api_get(base_url, f"/quiz-questions{subject_query}", token)
    # lb_status, leaderboard = api_get(base_url, "/leaderboard", token)

    exercises = exercises if ex_status == 200 and isinstance(exercises, list) else []
    topics = topics if tp_status == 200 and isinstance(topics, list) else []
    students = students if st_status == 200 and isinstance(students, list) else []
    quiz_questions = quiz_questions if qq_status == 200 and isinstance(quiz_questions, list) else []
    # leaderboard = leaderboard if lb_status == 200 and isinstance(leaderboard, list) else []

    # total_completed = sum((row.get("completed_count") or 0) for row in leaderboard)

    c1, c2 = st.columns(2)
    c1.metric("Temes", len(topics))
    c2.metric("Exercicis", len(exercises))
    # c3.metric("Entrades leaderboard", len(leaderboard))
    # c4.metric("Completats globals", total_completed)

    selected_section = st.session_state.get("admin_section", "Inici")
    show_overview = selected_section == "Inici"
    show_topics = selected_section == "Temari"
    show_quiz = selected_section == "Preguntes"
    show_exercises = selected_section == "Exercicis"
    show_test_cases = selected_section == "Proves"
    show_tracking = selected_section == "Alumnat"

    if show_overview:
        st.info("Selecciona un apartat a la barra lateral per treballar de forma enfocada.")

    topics_section_slot = st.container()
    create_topic_section_slot = st.container()

    if show_topics:
        with topics_section_slot:
            st.subheader("Temes")
            submit_topic_update = False
            submit_topic_delete = False
            if topics:
                # Copiamos snapshot original para poder detectar cambios por fila
                # tras editar en data_editor.
                topic_rows = [
                    {
                        "id": topic.get("id"),
                        "name": topic.get("name") or "",
                        "description": topic.get("description") or "",
                        "weight": float(topic.get("weight", 1.0)),
                        "required_beginner": int(topic.get("required_beginner", 0)),
                        "required_mid": int(topic.get("required_mid", 0)),
                        "required_expert": int(topic.get("required_expert", 0)),
                        "secret_message": topic.get("secret_message") or "",
                        "eliminar": False,
                    }
                    for topic in topics
                ]
                topic_df = pd.DataFrame(topic_rows)
                original_by_id = {topic.get("id"): topic for topic in topics}
                with st.form("topics_editor_form"):
                    edited_topic_df = st.data_editor(
                        topic_df,
                        hide_index=True,
                        use_container_width=True,
                        disabled=["id"],
                        column_config={
                            "id": "ID",
                            "name": "Nom",
                            "description": "Descripció",
                            "weight": st.column_config.NumberColumn("Pes", min_value=0.0, step=0.1),
                            "required_beginner": st.column_config.NumberColumn("Req. bàsic", min_value=0, step=1),
                            "required_mid": st.column_config.NumberColumn("Req. intermedi", min_value=0, step=1),
                            "required_expert": st.column_config.NumberColumn("Req. difícil", min_value=0, step=1),
                            "secret_message": "Retroaccio",
                            "eliminar": "Eliminar",
                        },
                        key="topics_data_editor",
                    )

                    st.caption("Si estàs editant una cel·la, prem Enter o fes clic fora abans de confirmar els canvis.")
                    update_col, delete_col = st.columns(2)
                    submit_topic_update = update_col.form_submit_button("Guardar")
                    submit_topic_delete = delete_col.form_submit_button("Eliminar seleccionats")

            if submit_topic_update:
                updated_count = 0
                for _, row in edited_topic_df.iterrows():
                    topic_id = int(row["id"])
                    original = original_by_id.get(topic_id, {})

                    new_name = str(row["name"]).strip()
                    new_description = str(row["description"]).strip()
                    new_weight = float(row["weight"])
                    new_required_beginner = int(row["required_beginner"])
                    new_required_mid = int(row["required_mid"])
                    new_required_expert = int(row["required_expert"])
                    new_secret_message = str(row["secret_message"]).strip()

                    old_name = str(original.get("name") or "").strip()
                    old_description = str(original.get("description") or "").strip()
                    old_weight = float(original.get("weight", 1.0))
                    old_required_beginner = int(original.get("required_beginner", 0))
                    old_required_mid = int(original.get("required_mid", 0))
                    old_required_expert = int(original.get("required_expert", 0))
                    old_secret_message = str(original.get("secret_message") or "").strip()

                    if not new_name:
                        st.error(f"El tema amb id {topic_id} no pot tenir el nom buit.")
                        continue

                    has_changes = (
                        new_name != old_name
                        or new_description != old_description
                        or new_weight != old_weight
                        or new_required_beginner != old_required_beginner
                        or new_required_mid != old_required_mid
                        or new_required_expert != old_required_expert
                        or new_secret_message != old_secret_message
                    )

                    if has_changes:
                        payload = {
                            "subject_id": selected_subject_id,
                            "name": new_name,
                            "description": new_description or None,
                            "weight": new_weight,
                            "required_beginner": new_required_beginner,
                            "required_mid": new_required_mid,
                            "required_expert": new_required_expert,
                            "secret_code": None,
                            "secret_message": new_secret_message or None,
                        }
                        status, result = api_put_json(base_url, f"/topics/{topic_id}", payload, token)
                        if status == 200:
                            updated_count += 1
                        else:
                            st.error(result.get("detail", f"No s'ha pogut actualitzar el tema {topic_id}"))

                if updated_count > 0:
                    queue_flash(f"S'han actualitzat {updated_count} tema(es).", target="topics_editor")
                    st.rerun()
                else:
                    st.info("No hi ha canvis per desar.")

            if submit_topic_delete:
                ids_to_delete = [int(row["id"]) for _, row in edited_topic_df.iterrows() if bool(row["eliminar"])]

                if not ids_to_delete:
                    st.warning("Marca almenys un tema a la columna 'Eliminar'.")
                else:
                    deleted_count = 0
                    for topic_id in ids_to_delete:
                        status, result = api_delete(base_url, f"/topics/{topic_id}", token)
                        if status == 200:
                            deleted_count += 1
                        else:
                            st.error(result.get("detail", f"No s'ha pogut eliminar el tema {topic_id}"))

                    if deleted_count > 0:
                        queue_flash(f"S'han eliminat {deleted_count} tema(es).", target="topics_editor")
                        st.rerun()
            if not topics:
                st.info("Encara no hi ha temes creats.")

            show_queued_flash("topics_editor")

    if show_topics:
        with create_topic_section_slot:
            st.subheader("Crear tema")
            if "create_topic_mode_json" not in st.session_state:
                st.session_state.create_topic_mode_json = False

            if not st.session_state.create_topic_mode_json:
                if st.button("Importar des de JSON", key="toggle_topic_to_json_btn"):
                    st.session_state.create_topic_mode_json = True
                    st.rerun()

                with st.form("create_topic_form", clear_on_submit=True):
                    topic_name = st.text_input("Nom")
                    topic_description = st.text_area("Descripció", height=80)
                    topic_weight = st.number_input("Pes", min_value=0.1, value=1.0, step=0.1)
                    req_col1, req_col2, req_col3 = st.columns(3)
                    topic_required_beginner = req_col1.number_input("Req. bàsic", min_value=0, value=0, step=1)
                    topic_required_mid = req_col2.number_input("Req. intermedi", min_value=0, value=0, step=1)
                    topic_required_expert = req_col3.number_input("Req. difícil", min_value=0, value=0, step=1)
                    topic_secret_message = st.text_area("Retroaccio (opcional)", height=80)
                    create_topic = st.form_submit_button("Crear tema")

                if create_topic:
                    if not topic_name.strip():
                        st.warning("El nom del tema és obligatori.")
                    else:
                        status, created_topic = api_post_json(
                            base_url,
                            "/topics",
                            {
                                "subject_id": selected_subject_id,
                                "name": topic_name.strip(),
                                "description": topic_description.strip() or None,
                                "weight": float(topic_weight),
                                "required_beginner": int(topic_required_beginner),
                                "required_mid": int(topic_required_mid),
                                "required_expert": int(topic_required_expert),
                                "secret_code": None,
                                "secret_message": topic_secret_message.strip() or None,
                            },
                            token,
                        )
                        if status == 200:
                            queue_flash(f"Tema creat: {created_topic.get('name')}", target="create_topic")
                            st.rerun()
                        else:
                            st.error(created_topic.get("detail", "No s'ha pogut crear el tema"))
            else:
                st.caption("Mode JSON actiu")
                if st.button("Tornar a creació manual", key="toggle_topic_to_manual_btn"):
                    st.session_state.create_topic_mode_json = False
                    st.rerun()

                with st.form("import_topics_json_form"):
                    st.caption("Accepta un objecte o llista d'objectes amb claus: name, description, weight, required_beginner, required_mid, required_expert, retroaccio (opcional).")
                    topics_json_input = st.text_area(
                        "JSON de temes",
                        height=180,
                        key="topics_json_import_input",
                        placeholder='[{"name":"Signals","description":"Gestio de senyals","weight":1.0,"required_beginner":1,"required_mid":0,"required_expert":0,"retroaccio":"Bon progrés en aquest tema."}]',
                    )
                    import_topics = st.form_submit_button("Importar temes")

                if import_topics:
                    items, parse_error = parse_json_items(topics_json_input.strip())
                    if parse_error:
                        st.error(parse_error)
                    else:
                        created_count = 0
                        failed_count = 0
                        for idx, item in enumerate(items, start=1):
                            name = str(item.get("name") or "").strip()
                            if not name:
                                failed_count += 1
                                st.error(f"Tema #{idx}: falta 'name'.")
                                continue
                            try:
                                payload = {
                                    "subject_id": selected_subject_id,
                                    "name": name,
                                    "description": (str(item.get("description") or "").strip() or None),
                                    "weight": float(item.get("weight", 1.0)),
                                    "required_beginner": int(item.get("required_beginner", 0)),
                                    "required_mid": int(item.get("required_mid", 0)),
                                    "required_expert": int(item.get("required_expert", 0)),
                                    "secret_code": None,
                                    "secret_message": (
                                        str(item.get("retroaccio") or item.get("secret_message") or "").strip() or None
                                    ),
                                }
                            except (TypeError, ValueError):
                                failed_count += 1
                                st.error(f"Tema #{idx}: format numèric invàlid.")
                                continue

                            status, result = api_post_json(base_url, "/topics", payload, token)
                            if status == 200:
                                created_count += 1
                            else:
                                failed_count += 1
                                st.error(f"Tema #{idx}: {result.get('detail', 'No s\'ha pogut crear el tema')}")

                        if created_count:
                            st.success(f"Importació completada: {created_count} tema(es) creat(s).")
                        if failed_count:
                            st.warning(f"Importació amb incidències: {failed_count} element(s) no creat(s).")
                        if created_count > 0:
                            queue_flash(f"Importació de temes: {created_count} creat(s).", target="create_topic")
                            st.rerun()

            show_queued_flash("create_topic")

    if show_quiz:
        st.subheader("Preguntes tipus test")
    if show_quiz and topics:
        topic_selector_options = {
            f"{topic.get('name') or 'Tema'} (id={topic.get('id')})": topic.get("id")
            for topic in topics
            if topic.get("id") is not None
        }
        selected_quiz_topic_label = st.selectbox(
            "Tema de les preguntes",
            options=list(topic_selector_options.keys()),
            key="quiz_topic_selector",
        )
        selected_quiz_topic_id = topic_selector_options[selected_quiz_topic_label]

        topic_quiz_questions = [
            question for question in quiz_questions if question.get("topic_id") == selected_quiz_topic_id
        ]

        quiz_questions_section_slot = st.container()
        create_quiz_section_slot = st.container()

        with quiz_questions_section_slot:
            if topic_quiz_questions:
                quiz_rows = [
                    {
                        "id": question.get("id"),
                        "nivell": level_to_ca(question.get("level") or ""),
                        "enunciat": question.get("statement") or "",
                        "opcions": len(question.get("options") or []),
                        "correcta": int(question.get("correct_option_index", 0)) + 1,
                        "obligatòria": "Sí" if bool(question.get("is_required")) else "No",
                        "eliminar": False,
                    }
                    for question in topic_quiz_questions
                ]
                quiz_df = pd.DataFrame(quiz_rows)
                with st.form("quiz_questions_editor_form"):
                    edited_quiz_df = st.data_editor(
                        quiz_df,
                        hide_index=True,
                        use_container_width=True,
                        disabled=["id", "nivell", "enunciat", "opcions", "correcta", "obligatòria"],
                        column_config={
                            "id": "ID",
                            "nivell": "Nivell",
                            "enunciat": "Enunciat",
                            "opcions": "Opcions",
                            "correcta": "Correcta",
                            "obligatòria": "Obligatòria",
                            "eliminar": "Eliminar",
                        },
                        key="quiz_questions_data_editor",
                    )
                    st.caption("Marca les preguntes que vols eliminar i prem 'Eliminar seleccionats'.")
                    delete_quiz_questions = st.form_submit_button("Eliminar seleccionats")

                if delete_quiz_questions:
                    ids_to_delete = [int(row["id"]) for _, row in edited_quiz_df.iterrows() if bool(row["eliminar"])]
                    if not ids_to_delete:
                        st.warning("Marca almenys una pregunta a la columna 'Eliminar'.")
                    else:
                        deleted_count = 0
                        for question_id in ids_to_delete:
                            status, result = api_delete(base_url, f"/quiz-questions/{question_id}", token)
                            if status == 200:
                                deleted_count += 1
                            else:
                                st.error(result.get("detail", f"No s'ha pogut eliminar la pregunta {question_id}"))

                        if deleted_count > 0:
                            queue_flash(f"S'han eliminat {deleted_count} pregunta(es).", target="quiz_questions")
                            st.rerun()
            else:
                st.info("Encara no hi ha preguntes tipus test per aquest tema.")

        with create_quiz_section_slot:
            st.subheader("Crear pregunta tipus test")
            if "create_quiz_mode_json" not in st.session_state:
                st.session_state.create_quiz_mode_json = False

            if not st.session_state.create_quiz_mode_json:
                if st.button("Importar des de JSON", key="toggle_quiz_to_json_btn"):
                    st.session_state.create_quiz_mode_json = True
                    st.rerun()

                # Este selector va fuera del form para forzar rerender inmediato
                # de campos de opciones (dentro del form solo cambia al submit).
                quiz_options_count = st.number_input(
                    "Nombre d'opcions de la nova pregunta",
                    min_value=2,
                    max_value=8,
                    value=4,
                    step=1,
                    key="quiz_options_count_selector",
                )

                with st.form("create_quiz_question_form", clear_on_submit=True):
                    quiz_statement = st.text_area("Enunciat", height=100)
                    quiz_level = st.selectbox(
                        "Nivell pregunta",
                        options=["beginner", "mid", "expert"],
                        index=0,
                        format_func=level_to_ca,
                    )
                    quiz_required = st.checkbox("Pregunta obligatòria", value=False)

                    option_values = []
                    option_indices = list(range(int(quiz_options_count)))
                    for option_idx in option_indices:
                        option_values.append(
                            st.text_input(f"Opció {option_idx + 1}", key=f"quiz_option_{option_idx}")
                        )

                    quiz_correct_option = st.selectbox(
                        "Opció correcta",
                        options=option_indices,
                        format_func=lambda idx: f"Opció {idx + 1}",
                        index=0,
                    )
                    create_quiz_question = st.form_submit_button("Crear pregunta")

                if create_quiz_question:
                    cleaned_options = [option.strip() for option in option_values]
                    if not quiz_statement.strip():
                        st.warning("L'enunciat és obligatori.")
                    elif any(not option for option in cleaned_options):
                        st.warning("Totes les opcions han de tenir text.")
                    elif int(quiz_correct_option) >= len(cleaned_options):
                        st.warning("L'opció correcta ha de correspondre a una opció no buida.")
                    else:
                        payload = {
                            "topic_id": selected_quiz_topic_id,
                            "level": quiz_level,
                            "statement": quiz_statement.strip(),
                            "options": cleaned_options,
                            "correct_option_index": int(quiz_correct_option),
                            "is_required": bool(quiz_required),
                        }
                        status, result = api_post_json(base_url, "/quiz-questions", payload, token)
                        if status == 200:
                            queue_flash("Pregunta tipus test creada.", target="quiz_questions")
                            st.rerun()
                        else:
                            st.error(result.get("detail", "No s'ha pogut crear la pregunta tipus test"))
            else:
                st.caption("Mode JSON actiu")
                if st.button("Tornar a creació manual", key="toggle_quiz_to_manual_btn"):
                    st.session_state.create_quiz_mode_json = False
                    st.rerun()

                with st.form("import_quiz_questions_json_form"):
                    st.caption("Accepta objecte o llista amb claus: topic_id (opcional), level (beginner|mid|expert o bàsic/basic|intermedi|difícil/dificil), statement, options, correct_option_index, is_required.")
                    quiz_json_input = st.text_area(
                        "JSON de preguntes",
                        height=220,
                        key="quiz_json_import_input",
                        placeholder='[{"level":"intermedi","statement":"Quin senyal finalitza un procés?","options":["SIGKILL","SIGTERM","SIGSTOP"],"correct_option_index":1,"is_required":true}]',
                    )
                    import_quiz = st.form_submit_button("Importar preguntes")

                if import_quiz:
                    items, parse_error = parse_json_items(quiz_json_input.strip())
                    if parse_error:
                        st.error(parse_error)
                    else:
                        created_count = 0
                        failed_count = 0
                        for idx, item in enumerate(items, start=1):
                            try:
                                options = item.get("options", [])
                                cleaned_options = [str(option).strip() for option in options]
                                topic_id_value = int(item.get("topic_id", selected_quiz_topic_id))
                                normalized_level = normalize_level_value(str(item.get("level", "beginner") or "beginner"))
                                payload = {
                                    "topic_id": topic_id_value,
                                    "level": normalized_level,
                                    "statement": str(item.get("statement") or "").strip(),
                                    "options": cleaned_options,
                                    "correct_option_index": int(item.get("correct_option_index", 0)),
                                    "is_required": bool(item.get("is_required", False)),
                                }
                            except (TypeError, ValueError):
                                failed_count += 1
                                st.error(f"Pregunta #{idx}: format invàlid.")
                                continue

                            if not payload["statement"]:
                                failed_count += 1
                                st.error(f"Pregunta #{idx}: falta 'statement'.")
                                continue
                            if len(payload["options"]) < 2 or any(not option for option in payload["options"]):
                                failed_count += 1
                                st.error(f"Pregunta #{idx}: 'options' ha de tenir almenys 2 textos no buits.")
                                continue
                            if payload["level"] not in {"beginner", "mid", "expert"}:
                                failed_count += 1
                                st.error(f"Pregunta #{idx}: 'level' invàlid.")
                                continue
                            if payload["correct_option_index"] < 0 or payload["correct_option_index"] >= len(payload["options"]):
                                failed_count += 1
                                st.error(f"Pregunta #{idx}: 'correct_option_index' fora de rang.")
                                continue

                            status, result = api_post_json(base_url, "/quiz-questions", payload, token)
                            if status == 200:
                                created_count += 1
                            else:
                                failed_count += 1
                                st.error(f"Pregunta #{idx}: {result.get('detail', 'No s\'ha pogut crear la pregunta')}")

                        if created_count:
                            st.success(f"Importació completada: {created_count} pregunta(es) creada(es).")
                        if failed_count:
                            st.warning(f"Importació amb incidències: {failed_count} element(s) no creat(s).")
                        if created_count > 0:
                            queue_flash(f"Importació de preguntes: {created_count} creada(es).", target="quiz_questions")
                            st.rerun()
    elif show_quiz:
        st.info("Cal crear com a mínim un tema per gestionar preguntes tipus test.")

    if show_quiz:
        show_queued_flash("quiz_questions")

    topic_options = {"Sense tema": None}
    for topic in topics:
        topic_id = topic.get("id")
        topic_name = (topic.get("name") or "").strip()
        if topic_name.lower() == "none":
            continue
        if topic_id is not None and topic_name:
            topic_options[topic_name] = topic_id

    if show_exercises:
        st.subheader("Exercicis")
    if show_exercises and exercises:
        test_count_by_exercise_id = {}
        for exercise in exercises:
            exercise_id = exercise.get("id")
            if exercise_id is None:
                continue
            detail_status, detail_payload = api_get(base_url, f"/exercises/{exercise_id}", token)
            if detail_status == 200 and isinstance(detail_payload, dict):
                public_test_cases = detail_payload.get("public_test_cases") or []
                test_count_by_exercise_id[exercise_id] = len(public_test_cases)
            else:
                test_count_by_exercise_id[exercise_id] = 0

        topic_id_to_name = {}
        topic_name_options = ["Sense tema"]
        topic_name_to_id = {"Sense tema": None}

        for topic in topics:
            topic_name = (topic.get("name") or "").strip()
            topic_id = topic.get("id")
            if topic_id is None:
                continue
            if not topic_name or topic_name.lower() == "none":
                continue
            topic_id_to_name[topic_id] = topic_name
            topic_name_to_id[topic_name] = topic_id
            if topic_name not in topic_name_options:
                topic_name_options.append(topic_name)

        exercise_rows = [
            {
                "id": exercise.get("id"),
                "tema": topic_id_to_name.get(exercise.get("topic_id"), "Sense tema"),
                "title": exercise.get("title") or "",
                "description": exercise.get("description") or "",
                "level": level_to_ca(exercise.get("level") or "beginner"),
                "tipus_entrega": exercise.get("expected_submission_type") or "c_file",
                "obligatori": bool(exercise.get("is_required", False)),
                "num_tests": test_count_by_exercise_id.get(exercise.get("id"), 0),
                "eliminar": False,
            }
            for exercise in exercises
        ]
        exercise_df = pd.DataFrame(exercise_rows)

        def highlight_rows_without_tests(row):
            styles = [""] * len(row)
            if int(row.get("num_tests", 0)) == 0:
                num_tests_col_idx = row.index.get_loc("num_tests")
                styles[num_tests_col_idx] = "background-color: #fff4e5"
            return styles

        styled_exercise_df = exercise_df.style.apply(highlight_rows_without_tests, axis=1)
        original_exercises_by_id = {exercise.get("id"): exercise for exercise in exercises}
        with st.form("exercises_editor_form"):
            edited_exercise_df = st.data_editor(
                styled_exercise_df,
                hide_index=True,
                use_container_width=True,
                disabled=["id", "num_tests"],
                column_config={
                    "id": "ID",
                    "tema": st.column_config.SelectboxColumn("Tema", options=topic_name_options, required=True),
                    "title": "Títol",
                    "description": "Descripció",
                    "level": st.column_config.SelectboxColumn("Nivell", options=["bàsic", "intermedi", "difícil"], required=True),
                    "tipus_entrega": st.column_config.SelectboxColumn("Tipus entrega", options=["c_file", "zip_makefile"], required=True),
                    "obligatori": "Obligatori",
                    "num_tests": st.column_config.NumberColumn("Num tests", min_value=0, step=1),
                    "eliminar": "Eliminar",
                },
                key="exercises_data_editor",
            )

            st.caption("Si estàs editant una cel·la, prem Enter o fes clic fora abans de confirmar els canvis.")
            ex_update_col, ex_delete_col = st.columns(2)
            submit_exercise_update = ex_update_col.form_submit_button("Guardar")
            submit_exercise_delete = ex_delete_col.form_submit_button("Eliminar seleccionats")

        if submit_exercise_update:
            updated_count = 0
            for _, row in edited_exercise_df.iterrows():
                exercise_id = int(row["id"])
                original = original_exercises_by_id.get(exercise_id, {})

                new_title = str(row["title"]).strip()
                new_description = str(row["description"]).strip()
                new_level = normalize_level_value(str(row["level"]).strip())
                new_expected_submission_type = str(row["tipus_entrega"]).strip() or "c_file"
                new_topic_name = str(row["tema"]).strip() or "Sense tema"
                if new_topic_name.lower() == "none":
                    new_topic_name = "Sense tema"
                new_topic_id = topic_name_to_id.get(new_topic_name)

                old_title = str(original.get("title") or "").strip()
                old_description = str(original.get("description") or "").strip()
                old_level = normalize_level_value(str(original.get("level") or "beginner").strip())
                old_expected_submission_type = str(original.get("expected_submission_type") or "c_file").strip()
                old_topic_id = original.get("topic_id")
                old_is_required = bool(original.get("is_required", False))
                new_is_required = bool(row["obligatori"])

                if not new_title:
                    st.error(f"L'exercici amb id {exercise_id} no pot tenir el títol buit.")
                    continue
                if new_level not in {"beginner", "mid", "expert"}:
                    st.error(f"Nivell invàlid a l'exercici {exercise_id}.")
                    continue
                if new_expected_submission_type not in {"c_file", "zip_makefile"}:
                    st.error(f"Tipus d'entrega invàlid a l'exercici {exercise_id}.")
                    continue
                if new_topic_name not in topic_name_to_id:
                    st.error(f"Tema invàlid a l'exercici {exercise_id}.")
                    continue

                has_changes = (
                    new_title != old_title
                    or new_description != old_description
                    or new_level != old_level
                    or new_expected_submission_type != old_expected_submission_type
                    or new_topic_id != old_topic_id
                    or new_is_required != old_is_required
                )

                if has_changes:
                    payload = {
                        "title": new_title,
                        "description": new_description or None,
                        "level": new_level,
                        "expected_submission_type": new_expected_submission_type,
                        "topic_id": new_topic_id,
                        "is_required": new_is_required,
                    }
                    status, result = api_put_json(base_url, f"/exercises/{exercise_id}", payload, token)
                    if status == 200:
                        updated_count += 1
                    else:
                        st.error(result.get("detail", f"No s'ha pogut actualitzar l'exercici {exercise_id}"))

            if updated_count > 0:
                queue_flash(f"S'han actualitzat {updated_count} exercici(s).", target="exercises_editor")
                st.rerun()
            else:
                st.info("No hi ha canvis per desar.")

        if submit_exercise_delete:
            ids_to_delete = [int(row["id"]) for _, row in edited_exercise_df.iterrows() if bool(row["eliminar"])]

            if not ids_to_delete:
                st.warning("Marca almenys un exercici a la columna 'Eliminar'.")
            else:
                deleted_count = 0
                for exercise_id in ids_to_delete:
                    status, result = api_delete(base_url, f"/exercises/{exercise_id}", token)
                    if status == 200:
                        deleted_count += 1
                    else:
                        st.error(result.get("detail", f"No s'ha pogut eliminar l'exercici {exercise_id}"))

                if deleted_count > 0:
                    queue_flash(f"S'han eliminat {deleted_count} exercici(s).", target="exercises_editor")
                    st.rerun()
    elif show_exercises:
        st.info("Encara no hi ha exercicis creats.")

    if show_exercises:
        show_queued_flash("exercises_editor")

    if show_exercises:
        st.subheader("Crear exercici")
        if "create_exercise_mode_json" not in st.session_state:
            st.session_state.create_exercise_mode_json = False

    if show_exercises and not st.session_state.create_exercise_mode_json:
        if st.button("Importar des de JSON", key="toggle_exercise_to_json_btn"):
            st.session_state.create_exercise_mode_json = True
            st.rerun()

        selected_topic_label = st.selectbox(
            "Tema",
            options=list(topic_options.keys()),
            index=0,
            key="create_exercise_topic_selector",
        )

        with st.form("create_exercise_form", clear_on_submit=True):
            exercise_title = st.text_input("Títol")
            exercise_description = st.text_area("Descripció de l'exercici", height=80)
            exercise_level = st.selectbox(
                "Nivell",
                options=["beginner", "mid", "expert"],
                index=0,
                format_func=level_to_ca,
            )
            exercise_submission_type = st.selectbox(
                "Tipus d'entrega esperat",
                options=["c_file", "zip_makefile"],
                index=0,
                help="c_file = fitxer C unic (.c), zip_makefile = projecte .zip amb Makefile",
            )
            exercise_required = st.checkbox("Exercici obligatori", value=False)
            create_exercise = st.form_submit_button("Crear exercici")

        if create_exercise:
            if not exercise_title.strip():
                st.warning("El títol de l'exercici és obligatori.")
            else:
                payload = {
                    "title": exercise_title.strip(),
                    "description": exercise_description.strip() or None,
                    "level": exercise_level,
                    "expected_submission_type": exercise_submission_type,
                    "is_required": bool(exercise_required),
                }
                selected_topic_id = topic_options[selected_topic_label]
                if selected_topic_id is not None:
                    payload["topic_id"] = selected_topic_id

                status, created_exercise = api_post_json(base_url, "/exercises", payload, token)
                if status == 200:
                    queue_flash(f"Exercici creat: {created_exercise.get('title')}", target="create_exercise")
                    st.rerun()
                else:
                    st.error(created_exercise.get("detail", "No s'ha pogut crear l'exercici"))
    elif show_exercises:
        st.caption("Mode JSON actiu")
        if st.button("Tornar a creació manual", key="toggle_exercise_to_manual_btn"):
            st.session_state.create_exercise_mode_json = False
            st.rerun()

        with st.form("import_exercises_json_form"):
            st.caption("Accepta objecte o llista amb claus: title, description, level (beginner|mid|expert o bàsic/basic|intermedi|difícil/dificil), expected_submission_type (opcional: c_file|zip_makefile), is_required (opcional), i topic_id o topic_name (almenys un dels dos).")
            exercises_json_input = st.text_area(
                "JSON d'exercicis",
                height=220,
                key="exercises_json_import_input",
                placeholder='[{"title":"Suma 2+2","description":"Llegeix dos enters i mostra la suma","level":"bàsic","expected_submission_type":"c_file","is_required":true,"topic_name":"Tema 1"}]',
            )
            import_exercises = st.form_submit_button("Importar exercicis")

        if import_exercises:
            items, parse_error = parse_json_items(exercises_json_input.strip())
            if parse_error:
                st.error(parse_error)
            else:
                looks_like_test_cases = (
                    len(items) > 0
                    and all("title" not in item for item in items)
                    and all("content" in item for item in items)
                    and any("exercise_id" in item for item in items)
                )
                if looks_like_test_cases:
                    st.error(
                        "Aquest JSON sembla de jocs de prova (test cases). "
                        "Importa'l a l'apartat 'Importar jocs de prova des de JSON'."
                    )
                    st.stop()

                created_count = 0
                failed_count = 0
                for idx, item in enumerate(items, start=1):
                    title = str(item.get("title") or "").strip()
                    if not title:
                        failed_count += 1
                        st.error(f"Exercici #{idx}: falta 'title'.")
                        continue

                    level = normalize_level_value(str(item.get("level", "beginner") or "beginner"))
                    if level not in {"beginner", "mid", "expert"}:
                        failed_count += 1
                        st.error(f"Exercici #{idx}: 'level' invàlid.")
                        continue

                    expected_submission_type = str(item.get("expected_submission_type", "c_file") or "c_file").strip()
                    if expected_submission_type not in {"c_file", "zip_makefile"}:
                        failed_count += 1
                        st.error(f"Exercici #{idx}: 'expected_submission_type' invàlid.")
                        continue

                    topic_id_value = item.get("topic_id")
                    if topic_id_value is None:
                        topic_name_value = str(item.get("topic_name") or "").strip()
                        if topic_name_value:
                            topic_id_value = topic_options.get(topic_name_value)
                            if topic_name_value not in topic_options:
                                failed_count += 1
                                st.error(f"Exercici #{idx}: topic_name '{topic_name_value}' no existeix.")
                                continue
                    if topic_id_value is None:
                        failed_count += 1
                        st.error(f"Exercici #{idx}: cal indicar 'topic_id' o 'topic_name'.")
                        continue

                    payload = {
                        "title": title,
                        "description": (str(item.get("description") or "").strip() or None),
                        "level": level,
                        "expected_submission_type": expected_submission_type,
                        "is_required": bool(item.get("is_required", False)),
                    }

                    if topic_id_value is not None:
                        try:
                            payload["topic_id"] = int(topic_id_value)
                        except (TypeError, ValueError):
                            failed_count += 1
                            st.error(f"Exercici #{idx}: 'topic_id' invàlid.")
                            continue

                    status, result = api_post_json(base_url, "/exercises", payload, token)
                    if status == 200:
                        created_count += 1
                    else:
                        failed_count += 1
                        st.error(f"Exercici #{idx}: {result.get('detail', 'No s\'ha pogut crear l\'exercici')}")

                if created_count:
                    st.success(f"Importació completada: {created_count} exercici(s) creat(s).")
                if failed_count:
                    st.warning(f"Importació amb incidències: {failed_count} element(s) no creat(s).")
                if created_count > 0:
                    queue_flash(f"Importació d'exercicis: {created_count} creat(s).", target="create_exercise")
                    st.rerun()

    if show_exercises:
        show_queued_flash("create_exercise")

    if show_test_cases:
        st.subheader("Jocs de prova")
    if show_test_cases and exercises:
        exercise_options = {
            f"{exercise.get('title') or 'Sense títol'} (id={exercise.get('id')})": exercise.get("id")
            for exercise in exercises
            if exercise.get("id") is not None
        }

        selected_testcase_exercise_id = st.session_state.get("selected_testcase_exercise_id")
        if selected_testcase_exercise_id is not None:
            selected_testcase_label = next(
                (
                    label
                    for label, exercise_id in exercise_options.items()
                    if int(exercise_id) == int(selected_testcase_exercise_id)
                ),
                None,
            )
            if selected_testcase_label is not None:
                st.session_state["testcases_exercise_selector"] = selected_testcase_label
                st.session_state.selected_testcase_exercise_id = None

        selected_exercise_label = st.selectbox(
            "Exercici per gestionar jocs de prova",
            options=list(exercise_options.keys()),
            key="testcases_exercise_selector",
        )
        selected_exercise_id = exercise_options[selected_exercise_label]

        ex_detail_status, ex_detail = api_get(base_url, f"/exercises/{selected_exercise_id}", token)
        if ex_detail_status == 200 and isinstance(ex_detail, dict):
            public_test_cases = ex_detail.get("public_test_cases") or []
            st.metric("Jocs de prova públics", len(public_test_cases))

            if public_test_cases:
                test_rows = [
                    {
                        "id": tc.get("id"),
                        "nom": tc.get("name") or "",
                        "mode": (tc.get("content") or {}).get("mode", "exact"),
                        "input": (tc.get("content") or {}).get("input", ""),
                        "expected": (tc.get("content") or {}).get("expected", ""),
                    }
                    for tc in public_test_cases
                ]
                st.dataframe(pd.DataFrame(test_rows), use_container_width=True, hide_index=True)
            else:
                st.info("Aquest exercici encara no té jocs de prova públics.")
        else:
            st.error(ex_detail.get("detail", "No s'ha pogut carregar el detall de l'exercici"))

        st.subheader("Crear joc de prova")
        if "create_testcase_mode_json" not in st.session_state:
            st.session_state.create_testcase_mode_json = False

        if not st.session_state.create_testcase_mode_json:
            if st.button("Importar des de JSON", key="toggle_testcase_to_json_btn"):
                st.session_state.create_testcase_mode_json = True
                st.rerun()

            with st.form("create_test_case_form", clear_on_submit=True):
                test_name = st.text_input("Nom del joc de prova")
                test_mode = st.selectbox("Mode de comparació", options=["exact", "contains"], index=0)
                test_input = st.text_area("Input", height=100)
                test_expected = st.text_area("Output esperat", height=100)
                test_ignore_ws = st.checkbox("Ignorar espais en blanc", value=False)
                create_test_case = st.form_submit_button("Afegir joc de prova")

            if create_test_case:
                if not test_name.strip():
                    st.warning("El nom del joc de prova és obligatori.")
                else:
                    tc_payload = {
                        "exercise_id": selected_exercise_id,
                        "name": test_name.strip(),
                        "content": {
                            "input": test_input,
                            "expected": test_expected,
                            "mode": test_mode,
                            "ignore_whitespace": test_ignore_ws,
                        },
                    }
                    tc_status, tc_result = api_post_json(base_url, "/test_cases", tc_payload, token)
                    if tc_status == 200:
                        queue_flash(f"Joc de prova creat: {tc_result.get('name')}", target="test_cases")
                        st.rerun()
                    else:
                        st.error(tc_result.get("detail", "No s'ha pogut crear el joc de prova"))
        else:
            st.caption("Mode JSON actiu")
            if st.button("Tornar a creació manual", key="toggle_testcase_to_manual_btn"):
                st.session_state.create_testcase_mode_json = False
                st.rerun()

            with st.form("import_testcases_json_form"):
                st.caption("Accepta objecte o llista amb claus: exercise_id (opcional), name, hidden (opcional), content{input, expected, mode(exact|contains), ignore_whitespace}.")
                testcases_json_input = st.text_area(
                    "JSON de jocs de prova",
                    height=220,
                    key="testcases_json_import_input",
                    placeholder='[{"name":"suma_2_mes_2","content":{"input":"2 2","expected":"4","mode":"exact","ignore_whitespace":true}}]',
                )
                import_testcases = st.form_submit_button("Importar jocs de prova")

            if import_testcases:
                items, parse_error = parse_json_items(testcases_json_input.strip())
                if parse_error:
                    st.error(parse_error)
                else:
                    created_count = 0
                    failed_count = 0
                    for idx, item in enumerate(items, start=1):
                        name = str(item.get("name") or "").strip()
                        if not name:
                            failed_count += 1
                            st.error(f"Test #{idx}: falta 'name'.")
                            continue

                        exercise_id_value = item.get("exercise_id", selected_exercise_id)
                        try:
                            exercise_id_value = int(exercise_id_value)
                        except (TypeError, ValueError):
                            failed_count += 1
                            st.error(f"Test #{idx}: 'exercise_id' invàlid.")
                            continue

                        content = item.get("content")
                        if not isinstance(content, dict):
                            failed_count += 1
                            st.error(f"Test #{idx}: falta objecte 'content'.")
                            continue

                        payload = {
                            "exercise_id": exercise_id_value,
                            "name": name,
                            "content": {
                                "input": str(content.get("input") or ""),
                                "expected": str(content.get("expected") or ""),
                                "mode": str(content.get("mode") or "exact"),
                                "ignore_whitespace": bool(content.get("ignore_whitespace", False)),
                            },
                        }
                        if "hidden" in item:
                            payload["hidden"] = bool(item.get("hidden"))

                        status, result = api_post_json(base_url, "/test_cases", payload, token)
                        if status == 200:
                            created_count += 1
                        else:
                            failed_count += 1
                            st.error(f"Test #{idx}: {result.get('detail', 'No s\'ha pogut crear el joc de prova')}")

                    if created_count:
                        st.success(f"Importació completada: {created_count} joc(s) de prova creat(s).")
                    if failed_count:
                        st.warning(f"Importació amb incidències: {failed_count} element(s) no creat(s).")
                    if created_count > 0:
                        queue_flash(f"Importació de jocs de prova: {created_count} creat(s).", target="test_cases")
                        st.rerun()
    elif show_test_cases:
        st.info("Cal crear com a mínim un exercici per gestionar jocs de prova.")

    if show_test_cases:
        show_queued_flash("test_cases")

    topic_status_api_status = None
    if show_tracking:
        st.subheader("Estat alumnat per tema")
    if show_tracking and topics:
        status_topic_options = {
            f"{topic.get('name') or 'Tema'} (id={topic.get('id')})": topic.get("id")
            for topic in topics
            if topic.get("id") is not None
        }
        selected_status_topic_label = st.selectbox(
            "Tema per consultar estat",
            options=list(status_topic_options.keys()),
            key="status_topic_selector",
        )
        selected_status_topic_id = status_topic_options[selected_status_topic_label]
        topic_status_api_status, topic_status_rows = api_get(
            base_url,
            f"/topics/{selected_status_topic_id}/students-status",
            token,
        )

        if topic_status_api_status == 200 and isinstance(topic_status_rows, list):
            if topic_status_rows:
                # Mostramos ratio completados/mínimo por nivel y un estado final de mínimos.
                # La nota final la decide la profesora fuera de esta pantalla.
                status_rows = [
                    {
                        "id": row.get("user_id"),
                        "usuari": row.get("username") or "",
                        "bàsic": f"{row.get('completed_beginner', 0)}/{row.get('required_beginner', 0)}",
                        "intermedi": f"{row.get('completed_mid', 0)}/{row.get('required_mid', 0)}",
                        "difícil": f"{row.get('completed_expert', 0)}/{row.get('required_expert', 0)}",
                        "obligatoris": f"{row.get('required_exercises_completed', 0)}/{row.get('required_exercises_total', 0)}",
                    }
                    for row in topic_status_rows
                ]
                status_df = pd.DataFrame(status_rows)
                topic_passed_by_idx = {
                    idx: bool(row.get("topic_minimums_met"))
                    for idx, row in enumerate(topic_status_rows)
                }

                def highlight_students_with_minimums(row):
                    # Verde para alumnado que ya cumple mínimos del tema.
                    if topic_passed_by_idx.get(int(row.name), False):
                        return ["background-color: #d1fae5"] * len(row)
                    return [""] * len(row)

                styled_status_df = status_df.style.apply(highlight_students_with_minimums, axis=1)

                st.dataframe(
                    styled_status_df,
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("No hi ha dades d'estat per aquest tema.")
        else:
            detail_message = topic_status_rows.get("detail", "No s'ha pogut carregar l'estat per tema") if isinstance(topic_status_rows, dict) else "No s'ha pogut carregar l'estat per tema"
            st.error(detail_message)
    elif show_tracking:
        st.info("Cal crear temes per consultar l'estat de l'alumnat.")

    if show_tracking:
        st.subheader("Alumnes")
    if show_tracking and students:
        student_rows = [
            {
                "id": student.get("id"),
                "usuari": student.get("username") or "",
                "email": student.get("email") or "",
                "rol": student.get("role") or "",
            }
            for student in students
        ]
        st.dataframe(pd.DataFrame(student_rows), use_container_width=True, hide_index=True)
    elif show_tracking:
        if st_status == 200:
            st.info("Encara no hi ha alumnes registrats.")
        else:
            st.error("No s'ha pogut carregar el llistat d'alumnes.")

    if show_tracking:
        st.subheader("Entregues")

        student_filter_options = {"Tots els alumnes": None}
        for student in students:
            student_id = student.get("id")
            if student_id is None:
                continue
            student_filter_options[
                f"{student.get('username') or 'alumne'} ({student.get('email') or 'sense email'})"
            ] = int(student_id)

        exercise_filter_options = {"Tots els exercicis": None}
        for exercise in exercises:
            exercise_id = exercise.get("id")
            if exercise_id is None:
                continue
            exercise_filter_options[f"{exercise.get('title') or 'exercici'} (id={exercise_id})"] = int(exercise_id)

        preselected_exercise_id = st.session_state.get("selected_teacher_submission_exercise_id")
        if preselected_exercise_id is not None:
            preselected_exercise_label = next(
                (
                    label
                    for label, exercise_id in exercise_filter_options.items()
                    if exercise_id is not None and int(exercise_id) == int(preselected_exercise_id)
                ),
                None,
            )
            if preselected_exercise_label is not None:
                st.session_state["teacher_submissions_exercise_filter"] = preselected_exercise_label
                st.session_state.selected_teacher_submission_exercise_id = None

        filter_col1, filter_col2 = st.columns(2)
        selected_student_filter = filter_col1.selectbox(
            "Filtre alumne",
            options=list(student_filter_options.keys()),
            key="teacher_submissions_student_filter",
        )
        selected_exercise_filter = filter_col2.selectbox(
            "Filtre exercici",
            options=list(exercise_filter_options.keys()),
            key="teacher_submissions_exercise_filter",
        )
        user_query = st.text_input("Cerca per usuari/email", key="teacher_submissions_user_query")

        query_parts = [
            f"subject_id={selected_subject_id}",
            "limit=200",
        ]
        selected_student_id = student_filter_options[selected_student_filter]
        selected_exercise_id_filter = exercise_filter_options[selected_exercise_filter]
        if selected_student_id is not None:
            query_parts.append(f"user_id={selected_student_id}")
        if selected_exercise_id_filter is not None:
            query_parts.append(f"exercise_id={selected_exercise_id_filter}")
        if user_query.strip():
            query_parts.append(f"user_query={urllib.parse.quote_plus(user_query.strip())}")

        submissions_path = "/teacher/submissions?" + "&".join(query_parts)
        ts_status, teacher_submissions_raw = api_get(base_url, submissions_path, token)
        teacher_submissions = teacher_submissions_raw if ts_status == 200 and isinstance(teacher_submissions_raw, list) else []

        if ts_status != 200:
            if isinstance(teacher_submissions_raw, dict):
                st.error(teacher_submissions_raw.get("detail", "No s'han pogut carregar les entregues."))
            else:
                st.error("No s'han pogut carregar les entregues.")
        elif not teacher_submissions:
            st.info("No hi ha entregues amb aquests filtres.")
        else:
            submission_rows = [
                {
                    "job_id": item.get("job_id"),
                    "usuari": item.get("username") or "",
                    "email": item.get("email") or "",
                    "exercici": item.get("exercise_title") or "",
                    "estat": item.get("status") or "",
                    "veredicte": item.get("verdict") or "-",
                    "creat": item.get("created_at") or "",
                    "finalitzat": item.get("completed_at") or "",
                }
                for item in teacher_submissions
            ]

            submission_df = pd.DataFrame(submission_rows)

            def _highlight_ac_rows(row):
                verdict = str(row.get("veredicte") or "").strip().upper()
                if verdict == "AC":
                    return ["background-color: #dcfce7"] * len(row)
                return [""] * len(row)

            st.caption("Fes clic en una fila per descarregar automàticament l'entrega.")
            selection_event = st.dataframe(
                submission_df.style.apply(_highlight_ac_rows, axis=1),
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key="teacher_submissions_table",
            )

            selected_download_job_id = None
            selected_rows = []
            if selection_event and isinstance(selection_event, dict):
                selected_rows = selection_event.get("selection", {}).get("rows", [])
            elif selection_event:
                selection_payload = getattr(selection_event, "selection", None)
                if isinstance(selection_payload, dict):
                    selected_rows = selection_payload.get("rows", [])
                elif selection_payload is not None:
                    selected_rows = getattr(selection_payload, "rows", []) or []

            if selected_rows:
                row_idx = int(selected_rows[0])
                if 0 <= row_idx < len(submission_df):
                    selected_download_job_id = int(submission_df.iloc[row_idx]["job_id"])

            if selected_download_job_id is None:
                st.info("Selecciona una fila de la taula per activar la descàrrega de l'entrega.")

            if selected_download_job_id is not None:
                selected_row = next(
                    (item for item in teacher_submissions if int(item.get("job_id") or -1) == selected_download_job_id),
                    None,
                )
                if selected_row:
                    st.write(
                        f"Entrega seleccionada: Job {selected_download_job_id} - "
                        f"{selected_row.get('exercise_title') or 'exercici'} - "
                        f"{selected_row.get('username') or 'usuari'}"
                    )

            if selected_download_job_id is not None and st.session_state.teacher_download_job_id != selected_download_job_id:
                dl_status, dl_bytes, dl_headers, dl_error = api_get_bytes(
                    base_url,
                    f"/teacher/submissions/{selected_download_job_id}/download",
                    token,
                )
                if dl_status == 200 and dl_bytes is not None:
                    content_disposition = dl_headers.get("Content-Disposition") or dl_headers.get("content-disposition") or ""
                    st.session_state.teacher_download_filename = _filename_from_content_disposition(
                        content_disposition,
                        fallback=f"submission_job_{selected_download_job_id}.bin",
                    )
                    st.session_state.teacher_download_mime = dl_headers.get("Content-Type") or dl_headers.get("content-type") or "application/octet-stream"
                    st.session_state.teacher_download_bytes = dl_bytes
                    st.session_state.teacher_download_job_id = selected_download_job_id
                else:
                    detail = dl_error.get("detail", "No s'ha pogut descarregar l'entrega.") if isinstance(dl_error, dict) else "No s'ha pogut descarregar l'entrega."
                    st.session_state.teacher_download_job_id = None
                    st.session_state.teacher_download_bytes = None
                    st.error(detail)
            elif selected_download_job_id is None:
                st.session_state.teacher_download_job_id = None
                st.session_state.teacher_download_bytes = None

            if selected_download_job_id is not None and st.session_state.teacher_download_bytes and st.session_state.teacher_download_job_id == selected_download_job_id:
                if st.session_state.teacher_auto_download_last_job_id != selected_download_job_id:
                    data_b64 = base64.b64encode(st.session_state.teacher_download_bytes).decode("ascii")
                    safe_filename = html.escape(st.session_state.teacher_download_filename or "entrega.bin")
                    safe_mime = html.escape(st.session_state.teacher_download_mime or "application/octet-stream")
                    st.markdown(
                        f"""
                        <a id=\"jutge-auto-download\" href=\"data:{safe_mime};base64,{data_b64}\" download=\"{safe_filename}\"></a>
                        <script>
                        const anchor = document.getElementById("jutge-auto-download");
                        if (anchor) {{
                          anchor.click();
                        }}
                        </script>
                        """,
                        unsafe_allow_html=True,
                    )
                    st.session_state.teacher_auto_download_last_job_id = selected_download_job_id

                st.download_button(
                    "Descarregar entrega (si el navegador bloqueja l'automàtica)",
                    data=st.session_state.teacher_download_bytes,
                    file_name=st.session_state.teacher_download_filename or "entrega.bin",
                    mime=st.session_state.teacher_download_mime or "application/octet-stream",
                    key=f"teacher_download_button_{selected_download_job_id}",
                )

            ac_submissions = [
                item
                for item in teacher_submissions
                if str(item.get("verdict") or "").strip().upper() == "AC" and item.get("job_id") is not None
            ]
            ac_job_ids = sorted(int(item.get("job_id")) for item in ac_submissions)

            selected_student_name = "tots els alumnes"
            if selected_student_id is not None:
                selected_student_name = next(
                    (
                        str(student.get("username") or "")
                        for student in students
                        if student.get("id") is not None and int(student.get("id")) == int(selected_student_id)
                    ),
                    "tots els alumnes",
                )

            selected_exercise_name = "tots els exercicis"
            if selected_exercise_id_filter is not None:
                selected_exercise_name = next(
                    (
                        str(exercise.get("title") or "")
                        for exercise in exercises
                        if exercise.get("id") is not None and int(exercise.get("id")) == int(selected_exercise_id_filter)
                    ),
                    "tots els exercicis",
                )

            student_fragment = _sanitize_pack_name_fragment(selected_student_name, "tots els alumnes")
            exercise_fragment = _sanitize_pack_name_fragment(selected_exercise_name, "tots els exercicis")
            bulk_zip_filename = f"{student_fragment}_{exercise_fragment}.zip"

            ac_signature = (
                f"subject={selected_subject_id}|student={student_fragment}|exercise={exercise_fragment}|"
                f"ac_jobs={','.join(str(job_id) for job_id in ac_job_ids)}"
            )

            st.divider()
            st.subheader("Descàrrega massiva")
            st.caption("Descarrega en un clic un ZIP amb totes les entregues AC del filtre actual.")
            st.write(f"Entregues AC detectades: **{len(ac_submissions)}**")
            st.write(f"Nom del pack: **{bulk_zip_filename}**")

            if not ac_submissions:
                st.info("No hi ha entregues AC en el filtre actual.")
                st.session_state.teacher_bulk_download_bytes = None
                st.session_state.teacher_bulk_download_filename = None
                st.session_state.teacher_bulk_download_signature = None
            else:
                if st.session_state.teacher_bulk_download_signature != ac_signature:
                    file_buffer = io.BytesIO()
                    used_names: set[str] = set()
                    success_count = 0
                    failed_jobs: list[int] = []

                    with st.spinner("Actualitzant ZIP d'entregues AC per aquest filtre..."):
                        with zipfile.ZipFile(file_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zip_out:
                            for item in ac_submissions:
                                job_id = int(item.get("job_id"))
                                dl_status, dl_bytes, dl_headers, _ = api_get_bytes(
                                    base_url,
                                    f"/teacher/submissions/{job_id}/download",
                                    token,
                                )
                                if dl_status != 200 or dl_bytes is None:
                                    failed_jobs.append(job_id)
                                    continue

                                content_disposition = dl_headers.get("Content-Disposition") or dl_headers.get("content-disposition") or ""
                                base_name = _filename_from_content_disposition(
                                    content_disposition,
                                    fallback=f"submission_job_{job_id}.bin",
                                )
                                safe_base_name = re.sub(r"[^a-zA-Z0-9._-]", "_", base_name).strip("._") or f"submission_job_{job_id}.bin"
                                final_name = f"job_{job_id}_{safe_base_name}"
                                dedupe_idx = 1
                                while final_name in used_names:
                                    root, ext = os.path.splitext(f"job_{job_id}_{safe_base_name}")
                                    final_name = f"{root}_{dedupe_idx}{ext}"
                                    dedupe_idx += 1
                                used_names.add(final_name)
                                zip_out.writestr(final_name, dl_bytes)
                                success_count += 1

                    if success_count == 0:
                        st.error("No s'ha pogut descarregar cap entrega AC per generar el ZIP.")
                        st.session_state.teacher_bulk_download_bytes = None
                        st.session_state.teacher_bulk_download_filename = None
                        st.session_state.teacher_bulk_download_signature = None
                    else:
                        st.session_state.teacher_bulk_download_bytes = file_buffer.getvalue()
                        st.session_state.teacher_bulk_download_filename = bulk_zip_filename
                        st.session_state.teacher_bulk_download_signature = ac_signature
                        if failed_jobs:
                            st.warning(
                                "ZIP generat amb incidències. No s'han pogut incloure els jobs: "
                                + ", ".join(str(job_id) for job_id in failed_jobs)
                            )

                bulk_ready = (
                    st.session_state.teacher_bulk_download_bytes
                    and st.session_state.teacher_bulk_download_signature == ac_signature
                )
                if bulk_ready:
                    st.download_button(
                        "Descarregar totes les AC (ZIP)",
                        data=st.session_state.teacher_bulk_download_bytes,
                        file_name=st.session_state.teacher_bulk_download_filename or bulk_zip_filename,
                        mime="application/zip",
                        key=f"teacher_bulk_ac_download_btn_{student_fragment}_{exercise_fragment}",
                    )

    # st.subheader("Top leaderboard")
    # if leaderboard:
    #     st.dataframe(leaderboard[:10], use_container_width=True, hide_index=True)
    # else:
    #     st.info("Encara no hi ha dades del leaderboard.")

    if show_overview:
        with st.expander("Estat de connexió API"):
            st.write(
                {
                    "GET /topics": tp_status,
                    "GET /exercises": ex_status,
                    "GET /students": st_status,
                    "GET /quiz-questions": qq_status,
                    "GET /topics/{id}/students-status": topic_status_api_status,
                    # "GET /leaderboard": lb_status,
                }
            )


def main():
    # Punto de entrada de la aplicación: carga configuración y decide qué pantalla mostrar.
    ensure_session()

    params = st.query_params
    lti_token = params.get("token")
    lti_subject_id = params.get("subject_id")
    lti_exercise_id = params.get("exercise_id")

    # Apply LTI-derived defaults before any widget is instantiated.
    if not st.session_state.get("_lti_target_processed"):
        target_value = str(params.get("target") or "").strip().lower()
        target_to_section = {
            "overview": "Inici",
            "inici": "Inici",
            "topics": "Temari",
            "temari": "Temari",
            "questions": "Preguntes",
            "preguntes": "Preguntes",
            "exercises": "Exercicis",
            "exercicis": "Exercicis",
            "tests": "Proves",
            "proves": "Proves",
            "testcases": "Proves",
            "students": "Alumnat",
            "alumnat": "Alumnat",
        }
        selected_section = target_to_section.get(target_value)
        if lti_exercise_id:
            selected_section = "Alumnat"
        if selected_section:
            st.session_state.admin_section = selected_section
        st.session_state._lti_target_processed = True

    if not st.session_state.get("_lti_exercise_id_processed") and lti_exercise_id:
        try:
            st.session_state.selected_teacher_submission_exercise_id = int(lti_exercise_id)
        except (TypeError, ValueError):
            pass
        st.session_state._lti_exercise_id_processed = True

    if lti_subject_id and st.session_state.get("selected_subject_id") is None:
        try:
            st.session_state.selected_subject_id = int(lti_subject_id)
        except (TypeError, ValueError):
            pass

    with st.sidebar:
        if st.session_state.get("token"):
            profile = st.session_state.get("profile") or {}
            email_value = (profile.get("email") or "").strip()
            friendly_email = email_value if email_value and not email_value.endswith("@lti.local") else None
            role_value = (profile.get("role") or "").strip().lower()
            fallback_label = "Professor" if role_value == "teacher" else "Usuari"
            display_name = (
                profile.get("full_name")
                or profile.get("name")
                or profile.get("display_name")
                or friendly_email
                or fallback_label
            )
            st.markdown(f"Connectat com a **{display_name}**")

            st.radio(
                "Apartats",
                options=[
                    "Inici",
                    "Temari",
                    "Preguntes",
                    "Exercicis",
                    "Proves",
                    "Alumnat",
                ],
                key="admin_section",
                label_visibility="collapsed",
            )
    if lti_token and not st.session_state._lti_params_processed and not st.session_state.token:
        status, me = api_get(st.session_state.base_url, "/me", lti_token)
        if status == 200 and me.get("role") == "teacher":
            st.session_state.token = lti_token
            st.session_state.profile = me
            st.session_state._lti_params_processed = True
            if lti_subject_id:
                try:
                    st.session_state.selected_subject_id = int(lti_subject_id)
                except (TypeError, ValueError):
                    pass
            st.rerun()
        if status == 200 and me.get("role") != "teacher":
            st.error("Aquest panell requereix rol teacher a Atenea.")
            return
        st.error("Token LTI invàlid. Torna a entrar des d'Atenea.")
        return

    if not st.session_state.token:
        render_lti_required_message()
        return

    # Refresca perfil para reflejar cambios de nombre legible en /me sin requerir reinicio manual.
    profile_status, refreshed_profile = api_get(st.session_state.base_url, "/me", st.session_state.token)
    if profile_status == 200 and isinstance(refreshed_profile, dict):
        st.session_state.profile = refreshed_profile

    render_dashboard()


if __name__ == "__main__":
    main()
