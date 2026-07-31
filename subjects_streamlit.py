import json
import os
import urllib.error
import urllib.parse
import urllib.request

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Jutge Assignatures", layout="wide")


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


def api_post_json(base_url: str, path: str, payload: dict, token: str):
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


def ensure_session():
    defaults = {
        "base_url": os.getenv("JUTGE_API_BASE_URL", "http://localhost:8000"),
        "token": None,
        "profile": None,
        "default_username": "alumno_a_base",
        "default_password": "alumno123",
        "flash_message": None,
        "flash_target": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def queue_flash(message: str, target: str = "top"):
    st.session_state.flash_message = message
    st.session_state.flash_target = target


def show_queued_flash(target: str):
    flash_message = st.session_state.get("flash_message")
    flash_target = st.session_state.get("flash_target")
    if flash_message and flash_target == target:
        safe_message = flash_message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        st.markdown(
            f"""
            <style>
            @keyframes fadeOutSubjectFlash {{
                0% {{ opacity: 1; max-height: 80px; margin-bottom: 1rem; }}
                80% {{ opacity: 1; max-height: 80px; margin-bottom: 1rem; }}
                100% {{ opacity: 0; max-height: 0; margin-bottom: 0; }}
            }}
            .jutge-subjects-flash {{
                background: #d1fae5;
                border: 1px solid #6ee7b7;
                color: #065f46;
                border-radius: 0.5rem;
                padding: 0.75rem 1rem;
                animation: fadeOutSubjectFlash 2s ease forwards;
                overflow: hidden;
            }}
            </style>
            <div class="jutge-subjects-flash">{safe_message}</div>
            """,
            unsafe_allow_html=True,
        )
        st.session_state.flash_message = None
        st.session_state.flash_target = None


def logout():
    st.session_state.token = None
    st.session_state.profile = None


def render_login():
    st.title("Portal d'assignatures")
    st.caption("Inicia sessio com a professor o alumne")

    with st.form("subjects_login_form", clear_on_submit=False):
        username = st.text_input("Usuari", value=st.session_state.default_username)
        password = st.text_input("Contrasenya", value=st.session_state.default_password, type="password")
        submitted = st.form_submit_button("Inicia sessio")

    if not submitted:
        return

    status, token_data = api_post_form(st.session_state.base_url, "/token", {"username": username, "password": password})
    if status != 200:
        st.error(token_data.get("detail", "No s'ha pogut iniciar sessio"))
        return

    token = token_data.get("access_token")
    if not token:
        st.error("L'API no ha retornat access_token")
        return

    me_status, me_payload = api_get(st.session_state.base_url, "/me", token)
    if me_status != 200:
        st.error(me_payload.get("detail", "No s'ha pogut carregar el perfil"))
        return

    st.session_state.token = token
    st.session_state.profile = me_payload
    st.success("Sessio iniciada")
    st.rerun()


def render_teacher_panel(base_url: str, token: str):
    st.subheader("Crear assignatura (professor)")

    # Fora del form per forcar rerender immediat del camp de password.
    protected = st.checkbox(
        "Protegir amb contrasenya",
        value=False,
        key="subject_create_protected_toggle",
    )

    with st.form("create_subject_form", clear_on_submit=True):
        code = st.text_input("Codi assignatura", placeholder="PACO")
        name = st.text_input("Nom assignatura", placeholder="Programacio Avancada en C")
        is_active = st.checkbox(
            "Activa (visible al cataleg d'alumnat)",
            value=True,
            help="Si esta desactivada, no apareixera al cataleg d'inscripcio de l'alumnat.",
        )
        enrollment_password = st.text_input("Contrasenya d'inscripcio", type="password") if protected else ""
        submitted = st.form_submit_button("Crear assignatura")

    if submitted:
        payload = {
            "code": code.strip(),
            "name": name.strip(),
            "is_active": bool(is_active),
            "enrollment_password": enrollment_password.strip() or None,
        }
        status, result = api_post_json(base_url, "/subjects", payload, token)
        if status == 200:
            st.success(f"Assignatura creada: {result.get('code')} - {result.get('name')}")
        else:
            st.error(result.get("detail", "No s'ha pogut crear l'assignatura"))

    st.subheader("Gestio d'assignatures (professor)")
    status, subjects = api_get(base_url, "/subjects/manage", token)
    if status == 200 and isinstance(subjects, list):
        if subjects:
            rows = [
                {
                    "id": s.get("id"),
                    "code": s.get("code"),
                    "name": s.get("name"),
                    "assignat": bool(s.get("is_enrolled")),
                    "activa": bool(s.get("is_active")),
                    "requereix_pass": bool(s.get("requires_password")),
                    "nova_contrasenya": "",
                }
                for s in subjects
            ]
            source_df = pd.DataFrame(rows)
            original_by_id = {int(s.get("id")): s for s in subjects if s.get("id") is not None}

            st.caption("Edita la taula i prem Guardar canvis. Per activar/modificar password, escriu-la a 'nova_contrasenya' abans de guardar.")
            edited_df = st.data_editor(
                source_df,
                hide_index=True,
                use_container_width=True,
                disabled=["id", "code", "name"],
                column_config={
                    "id": "ID",
                    "code": "Codi",
                    "name": "Assignatura",
                    "assignat": "Assignat a mi",
                    "activa": "Activa",
                    "requereix_pass": "Requereix password",
                    "nova_contrasenya": st.column_config.TextColumn("Nova contrasenya", help="Obligatoria si marques requereix_pass i vols activar/canviar password"),
                },
                key="teacher_subjects_editor",
            )

            if st.button("Guardar canvis", key="teacher_subjects_save"):
                changes = 0
                for _, row in edited_df.iterrows():
                    subject_id = int(row["id"])
                    original = original_by_id.get(subject_id)
                    if not original:
                        continue

                    old_assigned = bool(original.get("is_enrolled"))
                    old_active = bool(original.get("is_active"))
                    old_requires = bool(original.get("requires_password"))

                    new_assigned = bool(row["assignat"])
                    new_active = bool(row["activa"])
                    new_requires = bool(row["requereix_pass"])
                    new_password = str(row.get("nova_contrasenya") or "").strip()

                    if new_assigned != old_assigned:
                        if new_assigned:
                            as_status, as_result = api_post_json(base_url, f"/subjects/{subject_id}/assign-self", {}, token)
                            if as_status != 200:
                                st.error(as_result.get("detail", f"No s'ha pogut assignar a {subject_id}"))
                                continue
                        else:
                            rm_status, rm_result = api_delete(base_url, f"/subjects/{subject_id}/assign-self", token)
                            if rm_status != 200:
                                st.error(rm_result.get("detail", f"No s'ha pogut desassignar de {subject_id}"))
                                continue
                        changes += 1

                    current_assigned = new_assigned

                    if current_assigned and new_active != old_active:
                        up_status, up_result = api_put_json(
                            base_url,
                            f"/subjects/{subject_id}/active",
                            {"is_active": new_active},
                            token,
                        )
                        if up_status != 200:
                            st.error(up_result.get("detail", f"No s'ha pogut actualitzar l'estat de {subject_id}"))
                            continue
                        changes += 1

                    if current_assigned and (new_requires != old_requires or (new_requires and new_password)):
                        payload = {
                            "requires_password": new_requires,
                            "enrollment_password": new_password or None,
                        }
                        pw_status, pw_result = api_put_json(
                            base_url,
                            f"/subjects/{subject_id}/password",
                            payload,
                            token,
                        )
                        if pw_status != 200:
                            st.error(pw_result.get("detail", f"No s'ha pogut actualitzar password de {subject_id}"))
                            continue
                        changes += 1

                if changes > 0:
                    st.success(f"Canvis aplicats: {changes}")
                    st.rerun()
                else:
                    st.info("No hi ha canvis per guardar.")
        else:
            st.info("No hi ha assignatures disponibles.")
    else:
        st.error(subjects.get("detail", "No s'han pogut carregar les assignatures"))


def render_student_panel(base_url: str, token: str):
    st.subheader("Inscripcio d'assignatures (alumne)")

    status, catalog = api_get(base_url, "/subjects/catalog", token)
    if status != 200 or not isinstance(catalog, list):
        st.error((catalog or {}).get("detail", "No s'ha pogut carregar el cataleg"))
        return

    if not catalog:
        st.info("No hi ha assignatures actives disponibles.")
        return

    rows = [
        {
            "id": item.get("id"),
            "code": item.get("code"),
            "name": item.get("name"),
            "inscrit": "Si" if item.get("is_enrolled") else "No",
            "requereix_pass": "Si" if item.get("requires_password") else "No",
        }
        for item in catalog
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    enrollable = [item for item in catalog if not item.get("is_enrolled")]
    if not enrollable:
        st.success("Ja estàs inscrit a totes les assignatures disponibles.")
        return

    options = {f"{s.get('code')} - {s.get('name')} (id={s.get('id')})": s for s in enrollable}
    selected_label = st.selectbox("Assignatura per inscriure't", options=list(options.keys()))
    selected_subject = options[selected_label]

    with st.form("enroll_subject_form"):
        needs_password = bool(selected_subject.get("requires_password"))
        password = st.text_input(
            "Contrasenya d'assignatura" if needs_password else "Contrasenya (opcional)",
            type="password",
            help="Nomes necessaria si l'assignatura esta protegida",
        )
        submit = st.form_submit_button("Inscriure'm")

    if submit:
        payload = {"password": password.strip() or None}
        enroll_status, enroll_result = api_post_json(base_url, f"/subjects/{selected_subject.get('id')}/enroll", payload, token)
        if enroll_status == 200:
            queue_flash(enroll_result.get("message", "Inscripcio completada"), target="top")
            st.rerun()
        else:
            st.error(enroll_result.get("detail", "No s'ha pogut completar la inscripcio"))


def render_dashboard():
    st.title("Portal d'assignatures")
    show_queued_flash("top")

    base_url = st.session_state.base_url
    token = st.session_state.token
    profile = st.session_state.profile or {}

    role = profile.get("role")
    username = profile.get("username")

    top_left, top_right = st.columns([4, 1])
    with top_left:
        st.write(f"Connectat com a **{username}**")
        st.write(f"Rol: **{role}**")
    with top_right:
        if st.button("Tanca sessio", type="secondary"):
            logout()
            st.rerun()

    if role == "teacher":
        render_teacher_panel(base_url, token)
    elif role == "student":
        render_student_panel(base_url, token)
    else:
        st.error("Aquest portal nomes permet rols teacher o student.")


def main():
    ensure_session()

    with st.sidebar:
        st.header("Configuracio")
        base_url = st.text_input("URL base API", value=st.session_state.base_url)
        st.session_state.base_url = base_url.rstrip("/")

    if not st.session_state.token:
        render_login()
    else:
        render_dashboard()


if __name__ == "__main__":
    main()
