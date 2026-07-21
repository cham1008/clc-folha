import streamlit as st
from processamento import processar_arquivos

st.set_page_config(
    page_title="CLC Folha",
    page_icon="📊",
    layout="wide"
)

st.markdown("""
<style>
.block-container {padding-top: 2rem; max-width: 1350px;}
div[data-testid="stMetric"] {
    background: #f7f8fb;
    border: 1px solid #e5e7eb;
    padding: 15px;
    border-radius: 12px;
}
.stButton > button {
    width: 100%;
    background: #102a43;
    color: white;
    font-weight: 700;
    border-radius: 10px;
    min-height: 46px;
}
.stDownloadButton > button {
    width: 100%;
    border-radius: 10px;
    min-height: 44px;
}
</style>
""", unsafe_allow_html=True)

st.title("📊 CLC FOLHA")
st.caption("Automação contábil da folha de pagamento")

with st.expander("Regras aplicadas nesta versão", expanded=False):
    st.markdown("""
- Valor negativo é convertido para positivo.
- Valores com vírgula/ponto decimal são convertidos para centavos.
- Valores inteiros, como `301547`, são considerados já em centavos.
- Data convertida para `DDMMAAAA`.
- Código do histórico alterado para `116`.
- Centro de custo `1010` é separado como Pró-labore e recebe filial `741`.
- Crédito em `FGTS A RECOLHER` é alterado para `SALARIOS A PAGAR`.
- Contas e centros de custo são validados.
- Filial é corrigida conforme o estabelecimento do centro de custo.
- Contas de custo 3.3 podem ser convertidas para a equivalente 3.4 quando houver correspondência segura.
- Contas B2B creditadas podem ser convertidas para B2C quando houver correspondência segura.
""")

col1, col2, col3 = st.columns(3)

with col1:
    arquivo_csv = st.file_uploader(
        "1. CLC FOLHA.csv",
        type=["csv"],
        help="Arquivo mensal da folha"
    )

with col2:
    arquivo_balancete = st.file_uploader(
        "2. BALANCETE.xlsx",
        type=["xlsx"],
        help="Plano de contas atualizado"
    )

with col3:
    arquivo_cc = st.file_uploader(
        "3. CCs ATIVOS.xlsx",
        type=["xlsx"],
        help="Relação de centros de custo ativos"
    )

st.divider()

processar = st.button("PROCESSAR ARQUIVOS", type="primary")

if processar:
    if not all([arquivo_csv, arquivo_balancete, arquivo_cc]):
        st.error("Envie os três arquivos antes de processar.")
    else:
        barra = st.progress(10, text="Lendo os arquivos...")
        try:
            resultado = processar_arquivos(
                arquivo_csv.getvalue(),
                arquivo_balancete.getvalue(),
                arquivo_cc.getvalue()
            )
            barra.progress(100, text="Processamento concluído!")

            st.success("Arquivos processados com sucesso.")

            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Lançamentos", f"{resultado['metricas']['total_lancamentos']:,}".replace(",", "."))
            m2.metric("Base principal", f"{resultado['metricas']['base_principal']:,}".replace(",", "."))
            m3.metric("Pró-labore", f"{resultado['metricas']['pro_labore']:,}".replace(",", "."))
            m4.metric("Ajustes", f"{resultado['metricas']['ajustes']:,}".replace(",", "."))
            m5.metric("Pendências", f"{resultado['metricas']['pendencias']:,}".replace(",", "."))

            total_fmt = f"R$ {resultado['metricas']['valor_total_centavos'] / 100:,.2f}"
            total_fmt = total_fmt.replace(",", "X").replace(".", ",").replace("X", ".")
            st.info(f"**Total bruto processado:** {total_fmt}")

            if resultado["metricas"]["pendencias"] > 0:
                st.warning(
                    "Existem pendências para revisão. Consulte as abas "
                    "'Pendências' e 'Validação Contábil' no arquivo Excel."
                )

            d1, d2, d3 = st.columns(3)
            with d1:
                st.download_button(
                    "⬇️ BASE - CLC FOLHA.xlsx",
                    data=resultado["base_excel"],
                    file_name="BASE - CLC FOLHA.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            with d2:
                st.download_button(
                    "⬇️ PRO-LABORE BASE.xlsx",
                    data=resultado["prolabore_excel"],
                    file_name="PRO-LABORE BASE.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            with d3:
                st.download_button(
                    "⬇️ CLC FOLHA.csv",
                    data=resultado["csv_final"],
                    file_name="CLC FOLHA.csv",
                    mime="text/csv"
                )

            st.subheader("Prévia da base corrigida")
            st.dataframe(resultado["preview"], use_container_width=True, hide_index=True)

        except Exception as erro:
            barra.empty()
            st.error(f"Não foi possível processar: {erro}")
            st.exception(erro)
