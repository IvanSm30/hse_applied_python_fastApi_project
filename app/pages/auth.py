import streamlit as st

if "is_auth" not in st.session_state:
    st.session_state.is_auth = False
if "auth_tg_id" not in st.session_state:
    st.session_state.auth_tg_id = ""
if "user_data" not in st.session_state:
    st.session_state.user_data = {}


def auth_user():
    auth_tg_id = st.session_state.auth_tg_id
    if auth_tg_id == "test":
        st.session_state.is_auth = True
        st.rerun()
    else:
        st.error("Неверный телеграмм id")


@st.dialog("Регистрация")
def reg_dialog():
    st.text_input("Телеграмм Id", key="reg_tg_id")
    st.text_input("Имя пользователя", key="username")
    st.text_input("Отображаемое имя", key="display_name")
    if st.button("Зарегистрироваться"):
        tg_id = st.session_state.get("reg_tg_id", "")
        username = st.session_state.get("username", "")
        display_name = st.session_state.get("display_name", "")

        st.session_state.user_data = {
            "tg_id": tg_id,
            "username": username,
            "display_name": display_name,
        }

        st.rerun()


if not st.session_state.is_auth:
    st.title("Вход в систему")
    st.text_input("Телеграмм Id", key="auth_tg_id")
    st.button("Войти", on_click=auth_user)
    if st.button("Перейти к регистрации"):
        reg_dialog()
else:
    st.switch_page("pages/app.py")
