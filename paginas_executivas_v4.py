"""
paginas_executivas_v4.py
==========================
Versão final (v4) do dashboard executivo. Consolida:
  - 5 páginas da v3 (Eventos Estratégicos) — com ajuste no Marketplace
  - 3 páginas da v2 (Omnichannel, Cliente/Marca, Investimentos/Mercado)
  - Páginas acadêmicas (Início, Carga e Higienização)
"""

import streamlit as st
import pandas as pd
import numpy as np

from config_indicadores import CORES, MIN_OBSERVACOES_CORRELACAO
from formatos import formata_moeda, formata_pct
from validacoes import mensagem_sem_dados
from analises import correlacao_pearson, base_100
import graficos_executivos_v2 as g2
from analises_eventos import FonteSeries, COERENTE, CONTRARIA, INCONCLUSIVO, SEM_DADOS, ICONE_VEREDITO, TEXTO_VEREDITO

# --- Importações da v3 ---
from paginas_executivas_v3 import (
    PaginaV3Timeline,
    PaginaV3EventosIndicadores,
    PaginaV3Digital,
    PaginaV3Juros,
    PaginaV3Marca,
    _controles,
    _evs,
    _tabela_avaliacao,
    _frases_numeros,
    _frases_associacao,
    _secao_insights,
    _como_interpretar,
    _bloco_fontes,
    _avisar_faltantes,
    _spec,
    _cobertura,
)

# --- Importações da v2 ---
from paginas_executivas_v2 import (
    PaginaV2Omnichannel,
    PaginaV2Cliente,
    PaginaV2Investimentos,
)

# --- Importações da v1 (acadêmico) ---
from paginas_executivas import PaginaInicio, PaginaCargaHigienizacao, PaginaAbertura


# ======================================================================
# PÁGINA 5 — MARKETPLACE E MARGEM (VERSÃO V4 - SEM ESTATÍSTICA)
# ======================================================================
class PaginaV4Marketplace:
    def render(self, repositorio):
        st.title("Marketplace e Margem")
        st.caption("O marketplace passou a contribuir mais para a rentabilidade do que apenas para o crescimento?")

        ctx, ano_ini, ano_fim, mostrar = _controles("v4_mk", repositorio)
        fonte = ctx.fonte
        n = st.sidebar.slider("Janela de comparação (trimestres)", 2, 8, 4, key="v4_mk_n")
        evs = _evs(["marketplace", "virada_4t23", "reversao_2t26", "covid"], ano_ini, ano_fim)
        _avisar_faltantes(fonte, ["vendas_marketplace_3p", "vendas_totais", "margem_ebitda", "margem_bruta"])

        # Gráfico 1
        st.subheader("Marketplace 3P e sua participação nas vendas totais")
        fig = g3.serie_com_eventos(
            [_spec(fonte, "vendas_marketplace_3p", cor=CORES["acento"]),
             _spec(fonte, "share_3p", eixo=2, cor=CORES["primaria"], largura=3)],
            evs, "Marketplace 3P (R$) × participação nas vendas totais",
            y1_titulo="R$ milhões", y2_titulo="% das vendas totais", fmt_y2="pct",
            ano_ini=ano_ini, ano_fim=ano_fim, mostrar_rotulos=mostrar)
        st.plotly_chart(fig, width="stretch", key="v4_mk_3p")

        # Gráfico 2
        st.subheader("Participação do marketplace × margens")
        fig = g3.serie_com_eventos(
            [_spec(fonte, "share_3p", cor=CORES["acento"], largura=3),
             _spec(fonte, "margem_bruta", cor=CORES["secundaria"]),
             _spec(fonte, "margem_ebitda", cor=CORES["positivo"], largura=3)],
            evs, "Participação do marketplace × margem bruta × margem EBITDA",
            y1_titulo="%", fmt_y1="pct", ano_ini=ano_ini, ano_fim=ano_fim, mostrar_rotulos=mostrar)
        st.plotly_chart(fig, width="stretch", key="v4_mk_margens")

        # Gráfico 3
        st.subheader("Crescimento ou rentabilidade? Variação a/a do marketplace × variação a/a da margem EBITDA")
        from analises_eventos import variacao_aa
        cresc = variacao_aa(fonte.trimestral("vendas_marketplace_3p"))
        m = fonte.trimestral("margem_ebitda")
        dm = pd.Series(dtype=float)
        if not m.empty:
            full = m.reindex(pd.period_range(m.index.min(), m.index.max(), freq="Q"))
            dm = (full - full.shift(4)).dropna()
        fig = g3.serie_com_eventos(
            [dict(nome="Crescimento a/a do marketplace 3P", serie=cresc.dropna(), tipo="barra", eixo=1,
                  fmt="pct", cor_sinal=True),
             dict(nome="Variação a/a da margem EBITDA (p.p.)", serie=dm, tipo="linha", eixo=2, fmt="pct2",
                  cor=CORES["primaria"], largura=3)],
            evs, "Crescimento do marketplace × ganho de margem EBITDA (a/a)",
            y1_titulo="Crescimento a/a", fmt_y1="pct", y2_titulo="Δ margem EBITDA (p.p.)", fmt_y2="pct2",
            ano_ini=ano_ini, ano_fim=ano_fim, mostrar_rotulos=mostrar)
        st.plotly_chart(fig, width="stretch", key="v4_mk_cresc_margem")

        # A seção "Relação estatística" foi REMOVIDA conforme solicitado.

        df_mk = _tabela_avaliacao(fonte, EVENTOS_POR_ID["marketplace"], n, "Marketplace 2023–24 — durante × antes")
        df_rev = _tabela_avaliacao(fonte, EVENTOS_POR_ID["reversao_2t26"], n, "2T26 — contra o 2T25")
        _bloco_fontes(evs)

        _secao_insights(
            fatos=[_cobertura(fonte, "vendas_marketplace_3p")] + _frases_numeros(df_mk)[:4],
            associacoes=_frases_associacao(df_mk) + _frases_associacao(df_rev),
            hipoteses=["O ganho de margem pode vir de mix (mais marketplace, que não carrega estoque), de "
                       "monetização (ads, fintech, fulfillment) ou de disciplina de despesas; os dados "
                       "disponíveis não separam esses efeitos.",
                       "Em 2026 o marketplace recua (-12,6% a/a no 2T26 segundo a divulgação) enquanto a margem se "
                       "mantém: pode indicar que o motor de margem migrou para lojas físicas e crédito."])
        _como_interpretar(
            "A pergunta é de **composição**: o marketplace ajuda mais a vender ou a lucrar? Compare as barras "
            "(crescimento) com a linha (ganho de margem). O 2T26 funciona como teste de estresse da narrativa: "
            "se o marketplace cai e a margem não cai, o vínculo causal é mais fraco do que o roteiro sugere.")