import html
import json
import urllib.error
import urllib.parse
import urllib.request

import pandas as pd
import streamlit as st

# Este panel sigue el modelo reactivo de Streamlit:
# cada interacción vuelve a ejecutar el script completo y usa session_state
# para mantener autenticación, configuración y mensajes efímeros.
st.set_page_config(page_title="Jutge Admin", layout="wide")


def api_post_form(base_url: str, path: str, form_data: dict, token: str | None = None):
    # Envía una petición POST con formulario (x-www-form-urlencoded) y devuelve estado + JSON.
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
        "base_url": "http://localhost:8000",
        "token": None,
        "profile": None,
        "default_username": "profesor_seed",
        "default_password": "profesor123",
        "flash_message": None,
        "flash_target": None,
        "selected_subject_id": None,
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


def render_login():
    # Renderiza la pantalla de login y valida que el usuario tenga rol de profesor.
    st.title("Jutge Admin")
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

    if me.get("role") != "teacher":
        st.error("Aquest panell només està disponible per a comptes de professor/admin.")
        return

    st.session_state.token = token
    st.session_state.profile = me
    st.success("Sessió iniciada")
    st.rerun()


def render_dashboard():
    # Muestra métricas básicas del sistema y permite crear temas y ejercicios.
    st.title("Tauler d'administració")
    st.caption("Pantalla 2/2: Tauler")

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

    col_a, col_b = st.columns([4, 1])
    with col_a:
        st.write(f"Connectat com a **{st.session_state.profile.get('username')}**")
    with col_b:
        if st.button("Tanca sessió", type="secondary"):
            logout()
            st.rerun()

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

    topics_section_slot = st.container()
    create_topic_section_slot = st.container()

    with topics_section_slot:
        st.subheader("Temes")
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

                    old_name = str(original.get("name") or "").strip()
                    old_description = str(original.get("description") or "").strip()
                    old_weight = float(original.get("weight", 1.0))
                    old_required_beginner = int(original.get("required_beginner", 0))
                    old_required_mid = int(original.get("required_mid", 0))
                    old_required_expert = int(original.get("required_expert", 0))

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
        else:
            st.info("Encara no hi ha temes creats.")

        show_queued_flash("topics_editor")

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
                st.caption("Accepta un objecte o llista d'objectes amb claus: name, description, weight, required_beginner, required_mid, required_expert.")
                topics_json_input = st.text_area(
                    "JSON de temes",
                    height=180,
                    key="topics_json_import_input",
                    placeholder='[{"name":"Signals","description":"...","weight":1.0,"required_beginner":0,"required_mid":0,"required_expert":0}]',
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

    st.subheader("Preguntes tipus test")
    if topics:
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
                        "nivell": question.get("level") or "",
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
                    quiz_level = st.selectbox("Nivell pregunta", options=["beginner", "mid", "expert"], index=0)
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
                    st.caption("Accepta objecte o llista amb claus: topic_id (opcional), level, statement, options, correct_option_index, is_required.")
                    quiz_json_input = st.text_area(
                        "JSON de preguntes",
                        height=220,
                        key="quiz_json_import_input",
                        placeholder='[{"level":"beginner","statement":"...","options":["A","B"],"correct_option_index":0,"is_required":false}]',
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
                                payload = {
                                    "topic_id": topic_id_value,
                                    "level": str(item.get("level", "beginner")).strip() or "beginner",
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
    else:
        st.info("Cal crear com a mínim un tema per gestionar preguntes tipus test.")

    show_queued_flash("quiz_questions")

    topic_options = {"Sense tema": None}
    for topic in topics:
        topic_id = topic.get("id")
        topic_name = (topic.get("name") or "").strip()
        if topic_name.lower() == "none":
            continue
        if topic_id is not None and topic_name:
            topic_options[topic_name] = topic_id

    st.subheader("Exercicis")
    if exercises:
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
                "level": exercise.get("level") or "beginner",
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
                    "level": st.column_config.SelectboxColumn("Nivell", options=["beginner", "mid", "expert"], required=True),
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
                new_level = str(row["level"]).strip()
                new_topic_name = str(row["tema"]).strip() or "Sense tema"
                if new_topic_name.lower() == "none":
                    new_topic_name = "Sense tema"
                new_topic_id = topic_name_to_id.get(new_topic_name)

                old_title = str(original.get("title") or "").strip()
                old_description = str(original.get("description") or "").strip()
                old_level = str(original.get("level") or "beginner").strip()
                old_topic_id = original.get("topic_id")
                old_is_required = bool(original.get("is_required", False))
                new_is_required = bool(row["obligatori"])

                if not new_title:
                    st.error(f"L'exercici amb id {exercise_id} no pot tenir el títol buit.")
                    continue
                if new_level not in {"beginner", "mid", "expert"}:
                    st.error(f"Nivell invàlid a l'exercici {exercise_id}.")
                    continue
                if new_topic_name not in topic_name_to_id:
                    st.error(f"Tema invàlid a l'exercici {exercise_id}.")
                    continue

                has_changes = (
                    new_title != old_title
                    or new_description != old_description
                    or new_level != old_level
                    or new_topic_id != old_topic_id
                    or new_is_required != old_is_required
                )

                if has_changes:
                    payload = {
                        "title": new_title,
                        "description": new_description or None,
                        "level": new_level,
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
    else:
        st.info("Encara no hi ha exercicis creats.")

    show_queued_flash("exercises_editor")

    st.subheader("Crear exercici")
    if "create_exercise_mode_json" not in st.session_state:
        st.session_state.create_exercise_mode_json = False

    if not st.session_state.create_exercise_mode_json:
        if st.button("Importar des de JSON", key="toggle_exercise_to_json_btn"):
            st.session_state.create_exercise_mode_json = True
            st.rerun()

        with st.form("create_exercise_form", clear_on_submit=True):
            exercise_title = st.text_input("Títol")
            exercise_description = st.text_area("Descripció de l'exercici", height=80)
            exercise_level = st.selectbox("Nivell", options=["beginner", "mid", "expert"], index=0)
            exercise_required = st.checkbox("Exercici obligatori", value=False)
            selected_topic_label = st.selectbox("Tema", options=list(topic_options.keys()), index=0)
            create_exercise = st.form_submit_button("Crear exercici")

        if create_exercise:
            if not exercise_title.strip():
                st.warning("El títol de l'exercici és obligatori.")
            else:
                payload = {
                    "title": exercise_title.strip(),
                    "description": exercise_description.strip() or None,
                    "level": exercise_level,
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
    else:
        st.caption("Mode JSON actiu")
        if st.button("Tornar a creació manual", key="toggle_exercise_to_manual_btn"):
            st.session_state.create_exercise_mode_json = False
            st.rerun()

        with st.form("import_exercises_json_form"):
            st.caption("Accepta objecte o llista amb claus: title, description, level, is_required (opcional), topic_id (opcional), topic_name (opcional).")
            exercises_json_input = st.text_area(
                "JSON d'exercicis",
                height=220,
                key="exercises_json_import_input",
                placeholder='[{"title":"sum","description":"...","level":"beginner","is_required":false,"topic_name":"Basics"}]',
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

                    level = str(item.get("level", "beginner") or "beginner").strip()
                    if level not in {"beginner", "mid", "expert"}:
                        failed_count += 1
                        st.error(f"Exercici #{idx}: 'level' invàlid.")
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

                    payload = {
                        "title": title,
                        "description": (str(item.get("description") or "").strip() or None),
                        "level": level,
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

    show_queued_flash("create_exercise")

    st.subheader("Jocs de prova")
    if exercises:
        exercise_options = {
            f"{exercise.get('title') or 'Sense títol'} (id={exercise.get('id')})": exercise.get("id")
            for exercise in exercises
            if exercise.get("id") is not None
        }

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
                st.caption("Accepta objecte o llista amb claus: exercise_id (opcional), name, hidden (opcional), content{input,expected,mode,ignore_whitespace}.")
                testcases_json_input = st.text_area(
                    "JSON de jocs de prova",
                    height=220,
                    key="testcases_json_import_input",
                    placeholder='[{"name":"sum_1","content":{"input":"2 3\\n","expected":"5\\n","mode":"exact","ignore_whitespace":false}}]',
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
    else:
        st.info("Cal crear com a mínim un exercici per gestionar jocs de prova.")

    show_queued_flash("test_cases")

    st.subheader("Estat alumnat per tema")
    topic_status_api_status = None
    if topics:
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
                        "mínims tema": "Sí" if bool(row.get("topic_minimums_met")) else "No",
                    }
                    for row in topic_status_rows
                ]
                status_df = pd.DataFrame(status_rows)

                def highlight_students_with_minimums(row):
                    # Verde para alumnado que ya cumple mínimos del tema.
                    if row.get("mínims tema") == "Sí":
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
    else:
        st.info("Cal crear temes per consultar l'estat de l'alumnat.")

    st.subheader("Alumnes")
    if students:
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
    else:
        if st_status == 200:
            st.info("Encara no hi ha alumnes registrats.")
        else:
            st.error("No s'ha pogut carregar el llistat d'alumnes.")

    # st.subheader("Top leaderboard")
    # if leaderboard:
    #     st.dataframe(leaderboard[:10], use_container_width=True, hide_index=True)
    # else:
    #     st.info("Encara no hi ha dades del leaderboard.")

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

    with st.sidebar:
        st.header("Configuració")
        base_url = st.text_input("URL base API", value=st.session_state.base_url)
        st.session_state.base_url = base_url.rstrip("/")

    if not st.session_state.token:
        render_login()
        return

    render_dashboard()


if __name__ == "__main__":
    main()
