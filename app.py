import streamlit as st

st.set_page_config(
    page_title="CLC Folha",
    page_icon="📊",
    layout="wide"
)

st.title("📊 CLC FOLHA")

st.write("Sistema de Automação Contábil da Folha")

csv = st.file_uploader(
    "CLC FOLHA.csv",
    type=["csv"]
)

balancete = st.file_uploader(
    "BALANCETE.xlsx",
    type=["xlsx"]
)

cc = st.file_uploader(
    "CCs ATIVOS.xlsx",
    type=["xlsx"]
)

if st.button("PROCESSAR"):
    if csv and balancete and cc:
        st.success("Arquivos recebidos com sucesso!")
    else:
        st.error("Envie os três arquivos.")
