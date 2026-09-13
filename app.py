"""
app.py
========
Ponto de entrada do app Streamlit. Monta o menu lateral (Início, Carga e
Higienização dos Dados, Dashboard) e, quando o Dashboard está selecionado,
os filtros de Ano e Fonte de informação. Delega a apresentação de cada
página para as classes em paginas.py, e o acesso a dados para
repositorio_dados.py — este arquivo só cuida de configuração e roteamento.

Para rodar localmente:
    streamlit run app.py

Para publicar no Streamlit Community Cloud:
    1. Suba este repositório (com a pasta BD/ incluída) no GitHub.
    2. Em share.streamlit.io, aponte para este arquivo (app.py).
    3. requirements.txt já lista as dependências necessárias.
"""

import streamlit as st

from repositorio_dados import obter_repositorio
from paginas import PaginaInicio, PaginaCargaHigienizacao, PaginaDashboard, FONTES

st.set_page_config(
    page_title="Evolução do Magazine Luiza",
    page_icon="📊",
    layout="wide",
)

MENU_INICIO = "Início"
MENU_CARGA = "Carga e Higienização dos Dados"
MENU_DASHBOARD = "Dashboard"

PAGINAS = {
    MENU_INICIO: PaginaInicio(),
    MENU_CARGA: PaginaCargaHigienizacao(),
    MENU_DASHBOARD: PaginaDashboard(),
}


def main():
    repositorio = obter_repositorio()

    st.sidebar.title("Menu")
    pagina_escolhida = st.sidebar.radio(
        "Navegação", [MENU_INICIO, MENU_CARGA, MENU_DASHBOARD], label_visibility="collapsed"
    )

    ano = None
    fonte = None
    if pagina_escolhida == MENU_DASHBOARD:
        st.sidebar.markdown("---")
        st.sidebar.subheader("Filtros do dashboard")
        ano = st.sidebar.selectbox("Filtro de ano", repositorio.anos_disponiveis(), index=len(repositorio.anos_disponiveis()) - 1)
        fonte = st.sidebar.radio("Fonte de informações", FONTES)

    if repositorio.erros:
        st.sidebar.markdown("---")
        st.sidebar.caption(f"⚠ {len(repositorio.erros)} fonte(s) com problema de carga")

    pagina = PAGINAS[pagina_escolhida]
    if pagina_escolhida == MENU_DASHBOARD:
        pagina.render(repositorio, ano, fonte)
    else:
        pagina.render(repositorio)


if __name__ == "__main__":
    main()
