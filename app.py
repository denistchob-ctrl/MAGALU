"""
app.py
========
Ponto de entrada do app Streamlit. Menu da versão 4 (Final).
"""

import streamlit as st
from repositorio_dados import obter_repositorio

# --- Importações da v4 (Abertura, Investimentos, Omnichannel, Projeções) ---
from paginas_executivas_v4 import (
    PaginaAbertura,
    PaginaV4InvestimentosDigitalMercado,
    PaginaV4OmnichannelMarketplace,
    PaginaV4Projecoes,
)

# --- Importações da v3 (páginas mantidas) ---
from paginas_executivas_v3 import (
    PaginaV3Timeline,
    PaginaV3EventosIndicadores,
    PaginaV3Juros,
)

# --- Importações da v2 (página Cliente) ---
from paginas_executivas_v2 import (
    PaginaV2Cliente,
)

# --- Importações da v1 (Acadêmico) ---
from paginas_executivas import (
    PaginaInicio,
    PaginaCargaHigienizacao,
)

st.set_page_config(page_title="Magazine Luiza — Dashboard Executivo", page_icon="📊", layout="wide")

# --- Menu ---
MENU_ABERTURA = "Apresentação"
MENU_V4_TL    = "1️⃣ Linha do Tempo Estratégica"
MENU_V4_EI    = "2️⃣ Eventos × Indicadores"
MENU_V4_JUR   = "3️⃣ Juros, Lucro e Virada"
MENU_V4_INV   = "4️⃣ Investimentos, Digital e Mercado"
MENU_V4_OMNI  = "5️⃣ Omnichannel e Marketplace"
MENU_V4_CLI   = "6️⃣ Cliente, Marca e Reputação"
MENU_V4_PROJ  = "7️⃣ Projeções Preditivas"

SEP_VISUAL    = "──────────────"
SEP_ACADEMICO = "Acadêmico"
SEP_OUTROS    = "─────────────────"

PAGINAS = {
    "Apresentação": PaginaAbertura(),
    SEP_VISUAL: None,
    MENU_V4_TL: PaginaV3Timeline(),
    MENU_V4_EI: PaginaV3EventosIndicadores(),
    MENU_V4_JUR: PaginaV3Juros(),
    MENU_V4_INV: PaginaV4InvestimentosDigitalMercado(),
    MENU_V4_OMNI: PaginaV4OmnichannelMarketplace(),
    MENU_V4_CLI: PaginaV2Cliente(),
    MENU_V4_PROJ: PaginaV4Projecoes(),
    SEP_OUTROS: None,
    SEP_ACADEMICO: None,
    "Objetivo do Projeto": PaginaInicio(),
    "Carga e Higienização": PaginaCargaHigienizacao(),
}

def mudar_pagina(nome_pagina):
    """Função de callback para atualizar o session_state antes do rerun."""
    st.session_state['pagina_atual'] = nome_pagina

def main():
    repositorio = obter_repositorio()

    # --- Sidebar com Logo ---
    try:
        st.sidebar.image("logo.png", width=150)
    except:
        pass
    
    st.sidebar.markdown("---")

    # Inicializa a página padrão se não existir
    if 'pagina_atual' not in st.session_state:
        st.session_state['pagina_atual'] = MENU_ABERTURA

    # --- Renderização do Menu Customizado ---
    for nome in PAGINAS.keys():
        if PAGINAS[nome] is None:
            # Se for um separador, renderiza como texto
            if nome == SEP_ACADEMICO:
                st.sidebar.markdown(f"**{nome}**")
            else:
                st.sidebar.markdown(f"<div style='color: #ccc; font-size: 12px; margin: 5px 0;'>{nome}</div>", unsafe_allow_html=True)
        else:
            # Define o tipo do botão baseado na página atual
            tipo_botao = "primary" if st.session_state['pagina_atual'] == nome else "secondary"
            
            # Usa on_click para atualizar o estado ANTES do rerun
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