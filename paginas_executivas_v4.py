"""
paginas_executivas_v4.py
==========================
Versão final (v4) do dashboard executivo. Consolida e mescla:
  1. Linha do Tempo Estratégica
  2. Eventos × Indicadores
  3. Juros, Lucro e Virada
  4. Investimentos, Digital e Mercado (v3 Digital + v2 Investimentos)
  5. Omnichannel e Marketplace (v2 Omnichannel + v3 Marketplace)
  6. Cliente, Marca e Reputação (v2)
  + Páginas acadêmicas (Início, Carga e Higienização)
"""

import streamlit as st
import pandas as pd
import numpy as np

from config_indicadores import CORES, MIN_OBSERVACOES_CORRELACAO
from formatos import formata_moeda, formata_pct
from validacoes import mensagem_sem_dados
from analises import correlacao_pearson, base_100
import graficos_executivos_v2 as g2
import graficos_executivos_v3 as g3
from eventos_estrategicos import EVENTOS_POR_ID
from analises_eventos import FonteSeries, COERENTE, CONTRARIA, INCONCLUSIVO, SEM_DADOS, ICONE_VEREDITO, TEXTO_VEREDITO

# --- Importações da v3 ---
from paginas_executivas_v3 import (
    PaginaV3Timeline,
    PaginaV3EventosIndicadores,
    PaginaV3Juros,
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
    _deslocar_futuro,
)

# --- Importações da v2 ---
from paginas_executivas_v2 import (
    PaginaV2Cliente,
)

# --- Importações da v1 (acadêmico) ---
from paginas_executivas import PaginaInicio, PaginaCargaHigienizacao, PaginaAbertura


# ======================================================================
# PÁGINA 4 — INVESTIMENTOS, DIGITAL E MERCADO
# ======================================================================
class PaginaV4InvestimentosDigitalMercado:
    def render(self, repositorio):
        st.title("Investimentos, Digital e Mercado")
        st.caption("Como os investimentos em tecnologia e logística impulsionaram o digital e "
                   "como o mercado reagiu a essa transformação?")

        ctx, ano_ini, ano_fim, mostrar = _controles("v4_inv", repositorio)
        fonte = ctx.fonte
        evs = _evs(["covid", "aquisicoes", "kabum", "followon", "aporte_2024", "virada_4t23"], ano_ini, ano_fim)
        
        _avisar_faltantes(fonte, ["vendas_ecommerce_1p", "vendas_marketplace_3p", "participacao_ecommerce",
                                  "invest_tecnologia", "invest_total", "invest_logistica", "ebitda", "mglu3"])

        # --- 1. O avanço do digital e o investimento em tecnologia
        st.header("1. A transformação digital e os investimentos")
        st.subheader("Investimento em tecnologia × participação do e-commerce")
        fig = g3.serie_com_eventos(
            [_spec(fonte, "invest_tecnologia", cor=CORES["invest"]),
             _spec(fonte, "participacao_ecommerce", eixo=2, cor=CORES["primaria"], largura=3)],
            evs, "Investimento em tecnologia × participação do e-commerce",
            y1_titulo="R$ milhões", y2_titulo="Participação (%)", fmt_y2="pct",
            ano_ini=ano_ini, ano_fim=ano_fim, mostrar_rotulos=mostrar)
        st.plotly_chart(fig, width="stretch", key="v4_inv_tec")

        st.subheader("Mix do e-commerce (1P × marketplace 3P) e participação nas vendas totais")
        fig = g3.serie_com_eventos(
            [_spec(fonte, "vendas_ecommerce_1p", cor=CORES["secundaria"]),
             _spec(fonte, "vendas_marketplace_3p", cor=CORES["acento"]),
             _spec(fonte, "participacao_ecommerce", eixo=2, cor=CORES["primaria"], largura=3)],
            evs, "E-commerce 1P + Marketplace 3P × participação do e-commerce",
            y1_titulo="R$ milhões", y2_titulo="Participação (%)", fmt_y2="pct",
            ano_ini=ano_ini, ano_fim=ano_fim, mostrar_rotulos=mostrar, empilhar=True)
        st.plotly_chart(fig, width="stretch", key="v4_inv_mix")

        # --- 2. Investimentos vs EBITDA e Base 100
        st.header("2. O retorno dos investimentos e a percepção do mercado")
        
        st.subheader("Investimentos por categoria × EBITDA")
        df_inv = pd.DataFrame({
            "Tecnologia": fonte.trimestral("invest_tecnologia"),
            "Logística": fonte.trimestral("invest_logistica"),
            "Lojas Físicas": fonte.trimestral("invest_lojas"),
        })
        serie_ebitda = fonte.trimestral("ebitda")
        if not df_inv.dropna(how="all").empty:
            fig = g3.serie_com_eventos(
                [dict(nome=c, serie=df_inv[c].dropna(), tipo="barra", eixo=1, fmt="num", cor=CORES["invest"] if c=="Tecnologia" else (CORES["secundaria"] if c=="Logística" else CORES["acento"]))
                 for c in df_inv.columns] + 
                [_spec(fonte, "ebitda", eixo=2, cor=CORES["acento"], largura=3)],
                evs, "Investimentos por categoria × EBITDA",
                y1_titulo="R$ milhões", y2_titulo="EBITDA (R$)", fmt_y2="num",
                ano_ini=ano_ini, ano_fim=ano_fim, mostrar_rotulos=mostrar, empilhar=True
            )
            st.plotly_chart(fig, width="stretch", key="v4_inv_ebitda")
            
        st.subheader("Base 100 — desempenho operacional × percepção de mercado")
        st.caption("Usa 2018 como período inicial quando disponível. Permite comparar trajetórias de escalas diferentes.")
        series_base = {
            "Receita": fonte.anual("receita_liquida"),
            "EBITDA": fonte.anual("ebitda"),
            "Lucro": fonte.anual("lucro_liquido"),
            "Vendas Totais": fonte.anual("vendas_totais"),
        }
        if not fonte.trimestral("mglu3").empty:
            series_base["MGLU3"] = fonte.anual("mglu3")

        df_base = pd.DataFrame({
            k: base_100(v) for k, v in series_base.items()
            if v is not None and not v.empty
        })
        if not df_base.empty:
            # Gráfico via g2
            st.plotly_chart(g2.invest_mercado_base100(df_base), width="stretch", key="v4_inv_base100")

        st.subheader("Cotação MGLU3 × Volume negociado")
        st.plotly_chart(
            g2.invest_mercado_cotacao_volume(fonte.trimestral("mglu3"), 
                                             repositorio.cotacao.get_serie("Volume_Financeiro") if repositorio.cotacao else None),
            width="stretch", key="v4_inv_cotacao"
        )

        # Avaliações e insights
        n = st.sidebar.slider("Janela de comparação (trimestres)", 2, 8, 4, key="v4_inv_n")
        df_kabum = _tabela_avaliacao(fonte, EVENTOS_POR_ID["kabum"], n, "Aquisição da KaBuM! — antes × depois")
        df_aporte = _tabela_avaliacao(fonte, EVENTOS_POR_ID["aporte_2024"], n, "Aporte R$ 1,25 bi — antes × depois")

        _bloco_fontes(evs)
        _secao_insights(
            fatos=[_cobertura(fonte, "participacao_ecommerce"), _cobertura(fonte, "invest_total")] + _frases_numeros(df_kabum)[:3],
            associacoes=_frases_associacao(df_kabum) + _frases_associacao(df_aporte),
            hipoteses=["O descolamento entre fundamentos (Receita, EBITDA) e cotação pode refletir mudanças na percepção de risco do mercado — requer análise de múltiplos."])
        _como_interpretar(
            "Esta página une **o que a empresa fez** (investimentos) com **o que o mercado achou** (cotação e Base 100). "
            "A análise de tecnologia x e-commerce mostra se o investimento acompanhou a transformação digital. "
            "A Base 100 permite ver se o preço da ação está seguindo os fundamentos.")


# ======================================================================
# PÁGINA 5 — OMNICHANNEL E MARKETPLACE
# ======================================================================
class PaginaV4OmnichannelMarketplace:
    def render(self, repositorio):
        st.title("Omnichannel e Marketplace")
        st.caption("Como mudou o motor de crescimento do Magalu e qual foi o papel do marketplace "
                   "na rentabilidade?")

        ctx, ano_ini, ano_fim, mostrar = _controles("v4_omni", repositorio)
        fonte = ctx.fonte
        n = st.sidebar.slider("Janela de comparação (trimestres)", 2, 8, 4, key="v4_omni_n")
        evs = _evs(["marketplace", "virada_4t23", "reversao_2t26", "covid"], ano_ini, ano_fim)
        _avisar_faltantes(fonte, ["vendas_lojas_fisicas", "vendas_ecommerce_1p", "vendas_marketplace_3p", "vendas_totais", "share_3p", "margem_ebitda"])

        # --- 1. O Mix de Canais
        st.header("1. O mix de canais")
        st.subheader("Lojas Físicas × E-commerce 1P × Marketplace 3P")
        fig = g3.serie_com_eventos(
            [_spec(fonte, "vendas_lojas_fisicas", cor=CORES["secundaria"]),
             _spec(fonte, "vendas_ecommerce_1p", cor=CORES["invest"]),
             _spec(fonte, "vendas_marketplace_3p", cor=CORES["acento"]),
             _spec(fonte, "participacao_ecommerce", eixo=2, cor=CORES["primaria"], largura=3)],
            evs, "Mix de canais e participação do e-commerce",
            y1_titulo="R$ milhões", y2_titulo="Participação E-commerce (%)", fmt_y2="pct",
            ano_ini=ano_ini, ano_fim=ano_fim, mostrar_rotulos=mostrar, empilhar=True)
        st.plotly_chart(fig, width="stretch", key="v4_omni_mix")

        st.subheader("Receita por loja × Receita por m²")
        serie_vendas_lf = fonte.trimestral("vendas_lojas_fisicas")
        serie_n_lojas = fonte.trimestral("numero_lojas")
        serie_area = fonte.trimestral("area_vendas")

        rec_loja = (serie_vendas_lf / serie_n_lojas.replace(0, np.nan)).dropna() if not serie_vendas_lf.empty else pd.Series(dtype=float)
        rec_m2 = (serie_vendas_lf / serie_area.replace(0, np.nan)).dropna() if not serie_vendas_lf.empty else pd.Series(dtype=float)
        
        if not rec_loja.empty or not rec_m2.empty:
            st.plotly_chart(
                g2.omni_receita_por_loja_e_m2(rec_loja, rec_m2),
                width="stretch", key="v4_omni_loja_m2"
            )

        # --- 2. O Marketplace e a Margem
        st.header("2. Marketplace, margem e rentabilidade")
        st.subheader("Marketplace 3P e sua participação nas vendas totais")
        fig = g3.serie_com_eventos(
            [_spec(fonte, "vendas_marketplace_3p", cor=CORES["acento"]),
             _spec(fonte, "share_3p", eixo=2, cor=CORES["primaria"], largura=3)],
            evs, "Marketplace 3P (R$) × participação nas vendas totais",
            y1_titulo="R$ milhões", y2_titulo="% das vendas totais", fmt_y2="pct",
            ano_ini=ano_ini, ano_fim=ano_fim, mostrar_rotulos=mostrar)
        st.plotly_chart(fig, width="stretch", key="v4_omni_3p")

        st.subheader("Participação do marketplace × margens")
        fig = g3.serie_com_eventos(
            [_spec(fonte, "share_3p", cor=CORES["acento"], largura=3),
             _spec(fonte, "margem_bruta", cor=CORES["secundaria"]),
             _spec(fonte, "margem_ebitda", cor=CORES["positivo"], largura=3)],
            evs, "Participação do marketplace × margem bruta × margem EBITDA",
            y1_titulo="%", fmt_y1="pct", ano_ini=ano_ini, ano_fim=ano_fim, mostrar_rotulos=mostrar)
        st.plotly_chart(fig, width="stretch", key="v4_omni_margens")

        df_mk = _tabela_avaliacao(fonte, EVENTOS_POR_ID["marketplace"], n, "Marketplace 2023–24 — durante × antes")
        df_rev = _tabela_avaliacao(fonte, EVENTOS_POR_ID["reversao_2t26"], n, "2T26 — contra o 2T25")

        _bloco_fontes(evs)
        _secao_insights(
            fatos=[_cobertura(fonte, "vendas_marketplace_3p")] + _frases_numeros(df_mk)[:4],
            associacoes=_frases_associacao(df_mk) + _frases_associacao(df_rev),
            hipoteses=["O ganho de margem pode vir de mix (mais marketplace, que não carrega estoque), de "
                       "monetização (ads, fintech, fulfillment) ou de disciplina de despesas.",
                       "Em 2026 o marketplace recua (-12,6% a/a no 2T26 segundo a divulgação) enquanto a margem se "
                       "mantém: pode indicar que o motor de margem migrou para lojas físicas e crédito."])
        _como_interpretar(
            "Esta página cruza **canais** e **rentabilidade**. A área empilhada mostra para onde a empresa está "
            "vendendo. Os gráficos de margem mostram se o marketplace (que exige menos estoque) está ajudando a "
            "empresa a lucrar mais ou apenas a vender mais.")


# --- As páginas 1, 2, 3 e 6 são importadas ou reaproveitadas ---
# PaginaV3Timeline, PaginaV3EventosIndicadores, PaginaV3Juros e PaginaV2Cliente
