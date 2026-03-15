import streamlit as st
from utils import get_options_by_user

### Проверка через бд будет
# if not st.session_state.get("is_auth", False):
#     st.warning("Требуется авторизация")
#     st.switch_page("pages/auth.py")
#     st.stop()

user_login = st.session_state.get("login", "")
options = get_options_by_user(user_login)

st.title("Управление ссылками")

new_long_url = st.text_input("Введите длинную ссылку:")
if st.button("Преобразовать в короткую ссылку", key="apply_short_url"):
    if new_long_url:
        st.success(f"Ссылка преобразована: {new_long_url}")
    else:
        st.warning("Введите ссылку")

st.divider()

if options:
    open_url = st.selectbox(
        label="Выберите ссылку, которую хотите открыть:",
        options=options,
        key="open_url",
    )
    if st.button("Перейти по ссылке", key="move_to_url"):
        st.markdown(f"🔗 Переход по ссылке: {open_url}")

    st.divider()

    change_url = st.selectbox(
        label="Выберите ссылку, которую хотите изменить:",
        options=options,
        key="change_url",
    )
    new_url_value = st.text_input("Введите новую ссылку:", key="new_url_input")
    if st.button("Применить изменение", key="apply_change"):
        if new_url_value:
            st.success(f"Ссылка '{change_url}' обновлена")
        else:
            st.warning("Введите новую ссылку")

    st.divider()

    delete_url = st.selectbox(
        label="Выберите ссылку, которую хотите удалить:",
        options=options,
        key="delete_url",
    )
    if st.button("Удалить ссылкply_delete"):
        st.success(f"Ссылка '{delete_url}' удалена")
        st.rerun()
else:
    st.info("У вас пока нет сохранённых ссылок")
