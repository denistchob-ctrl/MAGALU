"""
app.py
========
Ponto de entrada do app Streamlit. Menu da versão 5 (Final Unificada).
"""

import streamlit as st
from repositorio_dados import obter_repositorio

# --- Importações da v5 ---
from paginas_executivas_v5 import (
    PaginaAbertura,
    PaginaV5Timeline,
    PaginaV5EventosIndicadores,
    PaginaV5Juros,
    PaginaV5InvestimentosDigitalMercado,
    PaginaV5OmnichannelMarketplace,
    PaginaV5Cliente,
    PaginaV5Projecoes,
    PaginaInicio,
    PaginaCargaHigienizacao,
)

st.set_page_config(page_title="Magazine Luiza — Dashboard Executivo", page_icon="📊", layout="wide")

# --- Menu ---
MENU_ABERTURA = "Apresentação"
MENU_V5_TL    = "1️⃣ Linha do Tempo Estratégica"
MENU_V5_EI    = "2️⃣ Eventos × Indicadores"
MENU_V5_JUR   = "3️⃣ Juros, Lucro e Virada"
MENU_V5_INV   = "4️⃣ Investimentos, Digital e Mercado"
MENU_V5_OMNI  = "5️⃣ Omnichannel e Marketplace"
MENU_V5_CLI   = "6️⃣ Cliente, Marca e Reputação"
MENU_V5_PROJ  = "7️⃣ Projeções Preditivas"

SEP_VISUAL    = "──────────────"
SEP_ACADEMICO = "Acadêmico"

PAGINAS = {
    MENU_ABERTURA: PaginaAbertura(),
    MENU_V5_TL: PaginaV5Timeline(),
    MENU_V5_EI: PaginaV5EventosIndicadores(),
    MENU_V5_JUR: PaginaV5Juros(),
    MENU_V5_INV: PaginaV5InvestimentosDigitalMercado(),
    MENU_V5_OMNI: PaginaV5OmnichannelMarketplace(),
    MENU_V5_CLI: PaginaV5Cliente(),
    MENU_V5_PROJ: PaginaV5Projecoes(),
    "Objetivo do Projeto": PaginaInicio(),
    "Carga e Higienização": PaginaCargaHigienizacao(),
}

def mudar_pagina(nome_pagina):
    st.session_state['pagina_atual'] = nome_pagina

def main():
    repositorio = obter_repositorio()

    # --- Sidebar com Logo ---
    try:
        st.sidebar.image("logo.png", width=150)
    except:
        pass
    
    if 'pagina_atual' not in st.session_state:
        st.session_state['pagina_atual'] = MENU_ABERTURA

    # --- Renderização do Menu Customizado ---
    for nome in PAGINAS.keys():
        if PAGINAS[nome] is None:
            if nome == SEP_ACADEMICO:
                st.sidebar.markdown(f"**{nome}**")
            else:
                st.sidebar.markdown(f"<div style='color: #ccc; font-size: 12px; margin: 5px 0;'>{nome}</div>", unsafe_allow_html=True)
        else:
            tipo_botao = "primary" if st.session_state['pagina_atual'] == nome else "secondary"
            st.sidebar.button(
                nome, 
                use_container_width=True, 
                type=tipo_botao,
                on_click=mudar_pagina,
                args=(nome,)
            )

    # Checagem de erros amigável
    pagina_escolhida = st.session_state['pagina_atual']
    if repositorio.erros and pagina_escolhida not in ("Objetivo do Projeto", "Carga e Higienização"):
        st.sidebar.markdown("---")
        st.sidebar.caption(f"⚠ {len(repositorio.erros)} fonte(s) com problema")

    # Renderiza a página escolhida
    pagina = PAGINAS[pagina_escolhida]
    if pagina is not None:
        pagina.render(repositorio)

if __name__ == "__main__":
    main()