"""
app.py
========
Ponto de entrada do app Streamlit. Menu lateral com as páginas do dashboard
executivo (Abertura + 5 atos) e um seletor de período em cada página.
"""

import streamlit as st

from repositorio_dados import obter_repositorio
from paginas_executivas import (
    PaginaAbertura,
    PaginaAto1,
    PaginaAto2,
    PaginaAto3,
    PaginaAto4,
    PaginaAto5,
)

st.set_page_config(
    page_title="Magazine Luiza — Dashboard Executivo",
    page_icon="📊",
    layout="wide",
)

MENU_ABERTURA = "🏠 Abertura"
MENU_ATO1 = "1️⃣ Onde estamos"
MENU_ATO2 = "2️⃣ Como o cliente nos vê"
MENU_ATO3 = "3️⃣ Onde a marca é forte/fraca"
MENU_ATO4 = "4️⃣ O que estamos fazendo"
MENU_ATO5 = "5️⃣ O que fazer"

PAGINAS = {
    MENU_ABERTURA: PaginaAbertura(),
    MENU_ATO1: PaginaAto1(),
    MENU_ATO2: PaginaAto2(),
    MENU_ATO3: PaginaAto3(),
    MENU_ATO4: PaginaAto4(),
    MENU_ATO5: PaginaAto5(),
}


def main():
    repositorio = obter_repositorio()

    st.sidebar.title("📊 Dashboard Executivo")
    st.sidebar.caption("Magazine Luiza — análise 2021–2026")
    st.sidebar.markdown("---")

    pagina_escolhida = st.sidebar.radio(
        "Navegação",
        list(PAGINAS.keys()),
        label_visibility="collapsed",
    )

    # Aviso de fontes com problema
    if repositorio.erros:
        st.sidebar.markdown("---")
        st.sidebar.caption(f"⚠ {len(repositorio.erros)} fonte(s) com problema")

    # Render
    PAGINAS[pagina_escolhida].render(repositorio)


if __name__ == "__main__":
    main()