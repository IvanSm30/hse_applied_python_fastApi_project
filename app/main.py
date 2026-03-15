import streamlit as st


st.write("Вы хотите зарегистрироваться?")
st.caption("Без регистрации вам не будет доступен полный функционал сервиса")


if st.button("Перейти на страницу регистрации"):
    st.switch_page("pages/auth.py")

if st.button("Продолжить без регистрации"):
    st.switch_page("pages/app.py")
