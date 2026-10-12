"""
app.py
========
Ponto de entrada do app Streamlit. Menu com quatro seções:
  - v1 — Modelo atual (5 atos)
  - v2 — Modelo proposto (5 páginas + Relações)
  - v3 — Eventos estratégicos × indicadores (6 páginas)
  - Acadêmico (Início, Carga e Higienização)
"""

import streamlit as st

from repositorio_dados import obter_repositorio

# --- v1 (modelo atual) ---
from paginas_executivas import (
    PaginaAbertura as V1Abertura,
    PaginaAto1 as V1Ato1,
    PaginaAto2 as V1Ato2,
    PaginaAto3 as V1Ato3,
    PaginaAto4 as V1Ato4,
    PaginaAto5 as V1Ato5,
    PaginaInicio as V1Inicio,
    PaginaCargaHigienizacao as V1Carga,
)

# --- v2 (modelo proposto) ---
from paginas_executivas_v2 import (
    PaginaV2VisaoExecutiva,
    PaginaV2Crescimento,
    PaginaV2Omnichannel,
    PaginaV2Cliente,
    PaginaV2Investimentos,
    PaginaV2Relacoes,
)

# --- v3 (eventos estratégicos × indicadores) ---
from paginas_executivas_v3 import (
    PaginaV3Timeline,
    PaginaV3EventosIndicadores,
    PaginaV3Digital,
    PaginaV3Juros,
    PaginaV3Marketplace,
    PaginaV3Marca,
)

st.set_page_config(
    page_title="Magazine Luiza — Dashboard Executivo",
    page_icon="📊",
    layout="wide",
)

# --- Menu ---
MENU_V1_ABERTURA = "🏠 Apresentação"
MENU_V1_ATO1 = "v1 · 1️⃣ Onde estamos"
MENU_V1_ATO2 = "v1 · 2️⃣ Como o cliente nos vê"
MENU_V1_ATO3 = "v1 · 3️⃣ Onde a marca é forte/fraca"
MENU_V1_ATO4 = "v1 · 4️⃣ O que estamos fazendo"
MENU_V1_ATO5 = "v1 · 5️⃣ O que fazer"

MENU_V2_EXEC  = "v2 · 1️⃣ Visão Executiva"
MENU_V2_CRESC = "v2 · 2️⃣ Crescimento e Rentabilidade"
MENU_V2_OMNI  = "v2 · 3️⃣ Omnichannel"
MENU_V2_CLI   = "v2 · 4️⃣ Cliente, Marca e Reputação"
MENU_V2_INV   = "v2 · 5️⃣ Investimentos e Mercado"
MENU_V2_REL   = "v2 · 6️⃣ Relações entre Indicadores"

MENU_V3_TL  = "v3 · 1️⃣ Linha do Tempo Estratégica"
MENU_V3_EI  = "v3 · 2️⃣ Eventos × Indicadores"
MENU_V3_DIG = "v3 · 3️⃣ Transformação Digital"
MENU_V3_JUR = "v3 · 4️⃣ Juros, Lucro e Virada"
MENU_V3_MKT = "v3 · 5️⃣ Marketplace e Margem"
MENU_V3_MAR = "v3 · 6️⃣ Marca e Reputação"
Nada1 = "-----------------"
Nada2 = "------------------"
Nada3 = "-------------------"

MENU_INICIO = "📚 Objetivo do Projeto"
MENU_CARGA = "📚 Carga e Higienização"

PAGINAS = {
    MENU_V1_ABERTURA: V1Abertura(),
    MENU_V1_ATO1: V1Ato1(),
    MENU_V1_ATO2: V1Ato2(),
    MENU_V1_ATO3: V1Ato3(),
    MENU_V1_ATO4: V1Ato4(),
    MENU_V1_ATO5: V1Ato5(),
    Nada1: None,
    MENU_V2_EXEC: PaginaV2VisaoExecutiva(),
    MENU_V2_CRESC: PaginaV2Crescimento(),
    MENU_V2_OMNI: PaginaV2Omnichannel(),
    MENU_V2_CLI: PaginaV2Cliente(),
    MENU_V2_INV: PaginaV2Investimentos(),
    MENU_V2_REL: PaginaV2Relacoes(),
    Nada2: None,
    MENU_V3_TL: PaginaV3Timeline(),
    MENU_V3_EI: PaginaV3EventosIndicadores(),
    MENU_V3_DIG: PaginaV3Digital(),
    MENU_V3_JUR: PaginaV3Juros(),
    MENU_V3_MKT: PaginaV3Marketplace(),
    MENU_V3_MAR: PaginaV3Marca(),
    Nada3: None,
    MENU_INICIO: V1Inicio(),
    MENU_CARGA: V1Carga(),
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