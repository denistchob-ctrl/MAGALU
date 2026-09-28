"""
graficos_executivos_v2.py
==========================
Gráficos Plotly do modelo v2 do dashboard executivo.

Independente do graficos_executivos.py (v1) — não sobrescreve nem
interfere na versão atual. Todos os gráficos usam a paleta definida em
config_indicadores.CORES.
"""

import re
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from config_indicadores import CORES
from formatos import formata_moeda, formata_pct

TEMPLATE = "plotly_white"


# ======================================================================
# HELPERS GENÉRICOS
# ======================================================================

def _converter_rotulos_para_timestamp(serie):
    """Converte índices tipo '1T18' / '1S18' / '2018' em Timestamps
    (para alinhar séries de granularidades diferentes no mesmo eixo)."""
    rotulos, valores = [], []
    for rotulo, valor in serie.items():
        texto = str(rotulo)
        ts = None

        # Trimestre: '1T18'
        m = re.match(r'^(\d)T(\d{2})$', texto)
        if m:
            tri = int(m.group(1)); ano = 2000 + int(m.group(2))
            mes = 1 + (tri - 1) * 3
            ts = pd.Timestamp(year=ano, month=mes, day=1)

        # Semestre: '1S18'
        m = re.match(r'^(\d)S(\d{2})$', texto)
        if m and ts is None:
            sem = int(m.group(1)); ano = 2000 + int(m.group(2))
            mes = 1 if sem == 1 else 7
            ts = pd.Timestamp(year=ano, month=mes, day=1)

        # Ano: '2018'
        m = re.match(r'^(\d{4})$', texto)
        if m and ts is None:
            ts = pd.Timestamp(year=int(m.group(1)), month=1, day=1)

        if ts is not None:
            rotulos.append(ts); valores.append(valor)
    return rotulos, valores


# ======================================================================
# PÁGINA 1 — VISÃO EXECUTIVA
# ======================================================================

def visao_executiva_evolucao(df, titulo="Evolução dos indicadores selecionados"):
    """Gráfico temporal multilinhas com indicadores escolhidos pelo usuário.
    df: DataFrame com uma coluna por indicador, índice = período."""
    fig = go.Figure()
    if df is None or df.empty:
        fig.update_layout(title=f"{titulo} (sem dados)", template=TEMPLATE)
        return fig

    for i, coluna in enumerate(df.columns):
        cor = list(CORES.values())[i % len(CORES)]
        fig.add_trace(go.Scatter(
            name=coluna,
            x=[str(j) for j in df.index],
            y=df[coluna].values,
            mode="lines+markers",
            line=dict(width=2, color=cor),
        ))

    fig.update_layout(
        title=titulo,
        template=TEMPLATE,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        hovermode="x unified",
        height=500,
    )
    return fig


# ======================================================================
# PÁGINA 2 — CRESCIMENTO E RENTABILIDADE
# ======================================================================

def cresc_rent_receita_ebitda(serie_receita, serie_ebitda):
    """Receita (barras) × EBITDA (linha) no mesmo gráfico, eixos separados
    quando a escala for muito diferente."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    if serie_receita is not None and not serie_receita.empty:
        fig.add_trace(go.Bar(
            name="Receita Líquida",
            x=[str(i) for i in serie_receita.index],
            y=serie_receita.values,
            marker_color=CORES["secundaria"],
            opacity=0.85,
        ), secondary_y=False)

    if serie_ebitda is not None and not serie_ebitda.empty:
        fig.add_trace(go.Scatter(
            name="EBITDA",
            x=[str(i) for i in serie_ebitda.index],
            y=serie_ebitda.values,
            mode="lines+markers",
            line=dict(color=CORES["acento"], width=3),
        ), secondary_y=True)

    fig.update_layout(
        title="Receita Líquida × EBITDA",
        template=TEMPLATE,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        hovermode="x unified",
        height=500,
    )
    fig.update_yaxes(title_text="Receita (R$)", secondary_y=False)
    fig.update_yaxes(title_text="EBITDA (R$)", secondary_y=True)
    return fig


def cresc_rent_receita_lucro(serie_receita, serie_lucro):
    """Receita (barras) × Lucro Líquido (linha)."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    if serie_receita is not None and not serie_receita.empty:
        fig.add_trace(go.Bar(
            name="Receita Líquida",
            x=[str(i) for i in serie_receita.index],
            y=serie_receita.values,
            marker_color=CORES["secundaria"],
            opacity=0.85,
        ), secondary_y=False)

    if serie_lucro is not None and not serie_lucro.empty:
        fig.add_trace(go.Scatter(
            name="Lucro Líquido",
            x=[str(i) for i in serie_lucro.index],
            y=serie_lucro.values,
            mode="lines+markers",
            line=dict(color=CORES["positivo"], width=3),
        ), secondary_y=True)

    fig.update_layout(
        title="Receita Líquida × Lucro Líquido",
        template=TEMPLATE,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        hovermode="x unified",
        height=500,
    )
    fig.update_yaxes(title_text="Receita (R$)", secondary_y=False)
    fig.update_yaxes(title_text="Lucro (R$)", secondary_y=True)
    return fig


def cresc_rent_crescimento_margens(serie_cresc_pct, serie_margem_ebitda, serie_margem_liquida):
    """Crescimento da receita (%) × margens EBITDA e Líquida (%)."""
    fig = go.Figure()

    if serie_cresc_pct is not None and not serie_cresc_pct.empty:
        fig.add_trace(go.Bar(
            name="Crescimento da Receita (%)",
            x=[str(i) for i in serie_cresc_pct.index],
            y=serie_cresc_pct.values * 100,
            marker_color=CORES["secundaria"],
            opacity=0.6,
        ))

    if serie_margem_ebitda is not None and not serie_margem_ebitda.empty:
        fig.add_trace(go.Scatter(
            name="Margem EBITDA (%)",
            x=[str(i) for i in serie_margem_ebitda.index],
            y=serie_margem_ebitda.values * 100,
            mode="lines+markers",
            line=dict(color=CORES["acento"], width=3),
        ))

    if serie_margem_liquida is not None and not serie_margem_liquida.empty:
        fig.add_trace(go.Scatter(
            name="Margem Líquida (%)",
            x=[str(i) for i in serie_margem_liquida.index],
            y=serie_margem_liquida.values * 100,
            mode="lines+markers",
            line=dict(color=CORES["positivo"], width=3),
        ))

    fig.update_layout(
        title="Crescimento × Margens",
        template=TEMPLATE,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        hovermode="x unified",
        height=500,
    )
    fig.update_yaxes(title_text="%")
    return fig


def cresc_rent_ebitda_fco(serie_ebitda, serie_fco):
    """EBITDA × Fluxo de Caixa Operacional (barras agrupadas)."""
    fig = go.Figure()

    if serie_ebitda is not None and not serie_ebitda.empty:
        fig.add_trace(go.Bar(
            name="EBITDA",
            x=[str(i) for i in serie_ebitda.index],
            y=serie_ebitda.values,
            marker_color=CORES["acento"],
        ))

    if serie_fco is not None and not serie_fco.empty:
        fig.add_trace(go.Bar(
            name="Fluxo de Caixa Operacional",
            x=[str(i) for i in serie_fco.index],
            y=serie_fco.values,
            marker_color=CORES["secundaria"],
        ))

    fig.update_layout(
        title="EBITDA × Fluxo de Caixa Operacional",
        template=TEMPLATE,
        barmode="group",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        hovermode="x unified",
        height=500,
    )
    fig.update_yaxes(title_text="R$")
    return fig


# ======================================================================
# PÁGINA 3 — OMNICHANNEL
# ======================================================================

def omni_mix_canais(df_mix):
    """Área empilhada do mix de canais: Lojas Físicas + E-commerce 1P + Marketplace 3P."""
    fig = go.Figure()
    if df_mix is None or df_mix.empty:
        fig.update_layout(title="Mix de canais (sem dados)", template=TEMPLATE)
        return fig

    cores = [CORES["secundaria"], CORES["invest"], CORES["acento"]]
    for i, coluna in enumerate(df_mix.columns):
        fig.add_trace(go.Scatter(
            name=coluna,
            x=[str(j) for j in df_mix.index],
            y=df_mix[coluna].values,
            mode="lines",
            stackgroup="one",
            line=dict(width=0.5, color=cores[i % len(cores)]),
        ))

    fig.update_layout(
        title="Mix de canais — Lojas Físicas × E-commerce 1P × Marketplace 3P",
        template=TEMPLATE,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        hovermode="x unified",
        height=500,
    )
    fig.update_yaxes(title_text="Vendas (R$)")
    return fig


def omni_investimento_tecnologia_vs_ecommerce(serie_invest_tec, serie_participacao_ecommerce):
    """Investimento em Tecnologia (barras) × Participação do E-commerce (linha %)."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    if serie_invest_tec is not None and not serie_invest_tec.empty:
        fig.add_trace(go.Bar(
            name="Investimento em Tecnologia (R$)",
            x=[str(i) for i in serie_invest_tec.index],
            y=serie_invest_tec.values,
            marker_color=CORES["invest"],
        ), secondary_y=False)

    if serie_participacao_ecommerce is not None and not serie_participacao_ecommerce.empty:
        fig.add_trace(go.Scatter(
            name="Participação do E-commerce (%)",
            x=[str(i) for i in serie_participacao_ecommerce.index],
            y=serie_participacao_ecommerce.values * 100,
            mode="lines+markers",
            line=dict(color=CORES["acento"], width=3),
        ), secondary_y=True)

    fig.update_layout(
        title="Investimento em Tecnologia × Participação do E-commerce",
        template=TEMPLATE,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        hovermode="x unified",
        height=500,
    )
    fig.update_yaxes(title_text="Investimento (R$)", secondary_y=False)
    fig.update_yaxes(title_text="Participação (%)", secondary_y=True, ticksuffix="%")
    return fig


def omni_receita_por_loja_e_m2(serie_receita_loja, serie_receita_m2):
    """Receita por loja × Receita por m² (linhas, eixos separados)."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    if serie_receita_loja is not None and not serie_receita_loja.empty:
        fig.add_trace(go.Scatter(
            name="Receita por Loja",
            x=[str(i) for i in serie_receita_loja.index],
            y=serie_receita_loja.values,
            mode="lines+markers",
            line=dict(color=CORES["secundaria"], width=3),
        ), secondary_y=False)

    if serie_receita_m2 is not None and not serie_receita_m2.empty:
        fig.add_trace(go.Scatter(
            name="Receita por m²",
            x=[str(i) for i in serie_receita_m2.index],
            y=serie_receita_m2.values,
            mode="lines+markers",
            line=dict(color=CORES["acento"], width=3, dash="dot"),
        ), secondary_y=True)

    fig.update_layout(
        title="Receita por Loja × Receita por m²",
        template=TEMPLATE,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        hovermode="x unified",
        height=500,
    )
    fig.update_yaxes(title_text="R$ / loja", secondary_y=False)
    fig.update_yaxes(title_text="R$ / m²", secondary_y=True)
    return fig


# ======================================================================
# PÁGINA 4 — CLIENTE, MARCA E REPUTAÇÃO
# ======================================================================

def cliente_trends_vs_vendas(serie_trends, serie_vendas, nome_vendas="Vendas Totais"):
    """Google Trends (linha) × Vendas (linha, eixo 2)."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    if serie_trends is not None and not serie_trends.empty:
        fig.add_trace(go.Scatter(
            name="Interesse de busca (Google Trends)",
            x=serie_trends.index,
            y=serie_trends.values,
            mode="lines",
            line=dict(color=CORES["trends"], width=2),
        ), secondary_y=False)

    if serie_vendas is not None and not serie_vendas.empty:
        fig.add_trace(go.Scatter(
            name=nome_vendas,
            x=[str(i) for i in serie_vendas.index],
            y=serie_vendas.values,
            mode="lines+markers",
            line=dict(color=CORES["secundaria"], width=3),
        ), secondary_y=True)

    fig.update_layout(
        title=f"Google Trends × {nome_vendas}",
        template=TEMPLATE,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        hovermode="x unified",
        height=500,
    )
    fig.update_yaxes(title_text="Interesse (0-100)", secondary_y=False)
    fig.update_yaxes(title_text="Vendas (R$)", secondary_y=True)
    return fig


def cliente_ra_vs_vendas_online(df_ra, serie_vendas_online):
    """Nota Média RA (barras) × Vendas E-commerce (linha)."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    if df_ra is not None and not df_ra.empty and "Nota Média" in df_ra.columns:
        fig.add_trace(go.Bar(
            name="Nota Média (RA Online)",
            x=[str(i) for i in df_ra.index],
            y=df_ra["Nota Média"].values,
            marker_color=CORES["ra"],
        ), secondary_y=False)

    if serie_vendas_online is not None and not serie_vendas_online.empty:
        fig.add_trace(go.Scatter(
            name="Vendas E-commerce",
            x=[str(i) for i in serie_vendas_online.index],
            y=serie_vendas_online.values,
            mode="lines+markers",
            line=dict(color=CORES["secundaria"], width=3),
        ), secondary_y=True)

    fig.update_layout(
        title="Reclame Aqui (Online) × Vendas E-commerce",
        template=TEMPLATE,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        hovermode="x unified",
        height=500,
    )
    fig.update_yaxes(title_text="Nota (0-10)", secondary_y=False, range=[0, 10])
    fig.update_yaxes(title_text="Vendas (R$)", secondary_y=True)
    return fig


def cliente_ra_vs_vendas_fisica(df_ra, serie_vendas_fisica):
    """Nota Média RA (barras) × Vendas Lojas Físicas (linha)."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    if df_ra is not None and not df_ra.empty and "Nota Média" in df_ra.columns:
        fig.add_trace(go.Bar(
            name="Nota Média (RA Física)",
            x=[str(i) for i in df_ra.index],
            y=df_ra["Nota Média"].values,
            marker_color=CORES["ra"],
        ), secondary_y=False)

    if serie_vendas_fisica is not None and not serie_vendas_fisica.empty:
        fig.add_trace(go.Scatter(
            name="Vendas Lojas Físicas",
            x=[str(i) for i in serie_vendas_fisica.index],
            y=serie_vendas_fisica.values,
            mode="lines+markers",
            line=dict(color=CORES["secundaria"], width=3),
        ), secondary_y=True)

    fig.update_layout(
        title="Reclame Aqui (Física) × Vendas Lojas Físicas",
        template=TEMPLATE,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        hovermode="x unified",
        height=500,
    )
    fig.update_yaxes(title_text="Nota (0-10)", secondary_y=False, range=[0, 10])
    fig.update_yaxes(title_text="Vendas (R$)", secondary_y=True)
    return fig


def cliente_luizacred(df_ra, serie_faturamento, serie_lucro):
    """Luizacred: Nota RA + Faturamento + Lucro (3 séries, 2 eixos)."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    if df_ra is not None and not df_ra.empty and "Nota Média" in df_ra.columns:
        fig.add_trace(go.Bar(
            name="Nota Média (RA Luizacred)",
            x=[str(i) for i in df_ra.index],
            y=df_ra["Nota Média"].values,
            marker_color=CORES["ra"],
        ), secondary_y=False)

    if serie_faturamento is not None and not serie_faturamento.empty:
        fig.add_trace(go.Scatter(
            name="Faturamento Luizacred",
            x=[str(i) for i in serie_faturamento.index],
            y=serie_faturamento.values,
            mode="lines+markers",
            line=dict(color=CORES["secundaria"], width=3),
        ), secondary_y=True)

    if serie_lucro is not None and not serie_lucro.empty:
        fig.add_trace(go.Scatter(
            name="Lucro Luizacred",
            x=[str(i) for i in serie_lucro.index],
            y=serie_lucro.values,
            mode="lines+markers",
            line=dict(color=CORES["positivo"], width=3, dash="dot"),
        ), secondary_y=True)

    fig.update_layout(
        title="Luizacred: Reputação × Faturamento × Lucro",
        template=TEMPLATE,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        hovermode="x unified",
        height=500,
    )
    fig.update_yaxes(title_text="Nota (0-10)", secondary_y=False, range=[0, 10])
    fig.update_yaxes(title_text="R$", secondary_y=True)
    return fig


# ======================================================================
# PÁGINA 5 — INVESTIMENTOS E MERCADO
# ======================================================================

def invest_mercado_investimentos_vs_ebitda(df_invest, serie_ebitda):
    """Investimentos por categoria (barras empilhadas) × EBITDA (linha)."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    if df_invest is not None and not df_invest.empty:
        for coluna in df_invest.columns:
            fig.add_trace(go.Bar(
                name=coluna,
                x=[str(i) for i in df_invest.index],
                y=df_invest[coluna].values,
            ), secondary_y=False)

    if serie_ebitda is not None and not serie_ebitda.empty:
        fig.add_trace(go.Scatter(
            name="EBITDA",
            x=[str(i) for i in serie_ebitda.index],
            y=serie_ebitda.values,
            mode="lines+markers",
            line=dict(color=CORES["acento"], width=3),
        ), secondary_y=True)

    fig.update_layout(
        title="Investimentos por categoria × EBITDA",
        template=TEMPLATE,
        barmode="stack",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        hovermode="x unified",
        height=500,
    )
    fig.update_yaxes(title_text="Investimentos (R$)", secondary_y=False)
    fig.update_yaxes(title_text="EBITDA (R$)", secondary_y=True)
    return fig


def invest_mercado_base100(df_base100):
    """Base 100 comparando Receita, EBITDA, Lucro, Vendas e MGLU3."""
    fig = go.Figure()
    if df_base100 is None or df_base100.empty:
        fig.update_layout(title="Base 100 (sem dados)", template=TEMPLATE)
        return fig

    for i, coluna in enumerate(df_base100.columns):
        cor = list(CORES.values())[i % len(CORES)]
        fig.add_trace(go.Scatter(
            name=coluna,
            x=[str(j) for j in df_base100.index],
            y=df_base100[coluna].values,
            mode="lines+markers",
            line=dict(width=2, color=cor),
        ))

    fig.add_hline(y=100, line_dash="dash", line_color="#999999",
                  annotation_text="Base 100", annotation_position="right")

    fig.update_layout(
        title="Base 100 — desempenho operacional × percepção de mercado",
        template=TEMPLATE,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        hovermode="x unified",
        height=500,
    )
    fig.update_yaxes(title_text="Índice (base 100)")
    return fig


def invest_mercado_cotacao_volume(serie_fech, serie_volume):
    """Cotação (linha) × Volume (barras)."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    if serie_volume is not None and not serie_volume.empty:
        fig.add_trace(go.Bar(
            name="Volume Financeiro",
            x=serie_volume.index,
            y=serie_volume.values / 1_000_000,
            marker_color=CORES["volume"],
            opacity=0.7,
        ), secondary_y=True)

    if serie_fech is not None and not serie_fech.empty:
        fig.add_trace(go.Scatter(
            name="Fechamento (R$)",
            x=serie_fech.index,
            y=serie_fech.values,
            mode="lines",
            line=dict(color=CORES["mercado"], width=2),
        ), secondary_y=False)

    fig.update_layout(
        title="Cotação MGLU3 × Volume negociado",
        template=TEMPLATE,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        hovermode="x unified",
        height=500,
        xaxis=dict(tickformat="%Y"),
    )
    fig.update_yaxes(title_text="Preço (R$)", secondary_y=False)
    fig.update_yaxes(title_text="Volume (R$ milhões)", secondary_y=True)
    return fig


# ======================================================================
# RELAÇÕES ENTRE INDICADORES
# ======================================================================

def relacoes_dispersao(serie_x, serie_y, nome_x, nome_y, r=None, n=None):
    """Dispersão com linha de tendência e anotação de correlação."""
    fig = go.Figure()

    df = pd.DataFrame({"x": serie_x, "y": serie_y}).dropna()
    if df.empty:
        fig.update_layout(title="Dispersão (sem dados alinhados)", template=TEMPLATE)
        return fig

    fig.add_trace(go.Scatter(
        x=df["x"], y=df["y"],
        mode="markers",
        marker=dict(size=9, color=CORES["secundaria"]),
        name="Observações",
        text=[str(i) for i in df.index],
    ))

    if len(df) >= 8 and df["x"].std() > 0:
        coef = np.polyfit(df["x"], df["y"], 1)
        x_linha = np.linspace(df["x"].min(), df["x"].max(), 50)
        y_linha = coef[0] * x_linha + coef[1]
        fig.add_trace(go.Scatter(
            x=x_linha, y=y_linha,
            mode="lines",
            line=dict(color=CORES["negativo"], width=2, dash="dash"),
            name="Tendência linear",
        ))

    anotacao = f"r = {r:.3f}" if r is not None and not np.isnan(r) else "r indisponível"
    if n:
        anotacao += f" · n = {n}"

    fig.update_layout(
        title=f"Dispersão: {nome_x} × {nome_y}",
        template=TEMPLATE,
        xaxis_title=nome_x,
        yaxis_title=nome_y,
        height=500,
        annotations=[dict(
            text=anotacao,
            xref="paper", yref="paper",
            x=0.02, y=0.98, showarrow=False,
            bgcolor="rgba(255,255,255,0.85)",
            bordercolor="#cccccc", borderwidth=1,
        )],
    )
    return fig