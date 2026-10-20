"""
app.py
========
Ponto de entrada do app Streamlit. Menu da versão 4 (Final).
"""

import streamlit as st
from repositorio_dados import obter_repositorio

# --- Importações da v4 ---
from paginas_executivas_v4 import (
    PaginaAbertura,
    PaginaV3Timeline,
    PaginaV3EventosIndicadores,
    PaginaV3Digital,
    PaginaV3Juros,
    PaginaV4Marketplace,
    PaginaV2Omnichannel,
    PaginaV2Cliente,
    PaginaV2Investimentos,
    PaginaInicio,
    PaginaCargaHigienizacao,
)

st.set_page_config(page_title="Magazine Luiza — Dashboard Executivo", page_icon="📊", layout="wide")

# --- Menu ---
MENU_ABERTURA = "🏠 Apresentação"
MENU_V4_TL   = " 1️⃣ Linha do Tempo Estratégica"
MENU_V4_EI   = " 2️⃣ Eventos × Indicadores"
MENU_V4_DIG  = " 3️⃣ Transformação Digital"
MENU_V4_JUR  = " 4️⃣ Juros, Lucro e Virada"
MENU_V4_MKT  = " 5️⃣ Marketplace e Margem"
MENU_V4_OMNI = " 6️⃣ Omnichannel"
MENU_V4_CLI  = " 7️⃣ Cliente, Marca e Reputação"
MENU_V4_INV  = " 8️⃣ Investimentos e Mercado"
Nada1 = "-----------------"

MENU_INICIO  = "📚 Objetivo do Projeto"
MENU_CARGA   = "📚 Carga e Higienização"

PAGINAS = {
    MENU_ABERTURA: PaginaAbertura(),
    MENU_V4_TL: PaginaV3Timeline(),
    MENU_V4_EI: PaginaV3EventosIndicadores(),
    MENU_V4_DIG: PaginaV3Digital(),
    MENU_V4_JUR: PaginaV3Juros(),
    MENU_V4_MKT: PaginaV4Marketplace(),
    MENU_V4_OMNI: PaginaV2Omnichannel(),
    MENU_V4_CLI: PaginaV2Cliente(),
    MENU_V4_INV: PaginaV2Investimentos(),
    Nada1: None,
    MENU_INICIO: PaginaInicio(),
    MENU_CARGA: PaginaCargaHigienizacao(),
}

def main():
    repositorio = obter_repositorio()

    st.sidebar.title("📊 Dashboard Executivo")
    st.sidebar.caption("Magazine Luiza — análise 2018–2026")
    st.sidebar.markdown("---")

    pagina_escolhida = st.sidebar.radio(
        "Navegação",
        list(PAGINAS.keys()),
        label_visibility="collapsed",
    )

    # Checagem de erros amigável
    if repositorio.erros and pagina_escolhida not in (MENU_INICIO, MENU_CARGA):
        st.sidebar.markdown("---")
        st.sidebar.caption(f"⚠ {len(repositorio.erros)} fonte(s) com problema")

    pagina = PAGINAS[pagina_escolhida]
    if pagina is None:
        st.info("Selecione uma página do menu.")
        return
    pagina.render(repositorio)

if __name__ == "__main__":
    main()