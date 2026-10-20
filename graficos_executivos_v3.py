"""
graficos_executivos_v3.py
==========================
Gráficos Plotly do modelo v3 (Eventos Estratégicos × Indicadores).
Independente de v1/v2 — usa apenas config_indicadores.CORES.

Convenções:
  - Séries trimestrais chegam com PeriodIndex('Q') (ou DatetimeIndex, ex.: Google
    Trends mensal / Selic diária) e são plotadas em eixo de datas, o que permite
    sobrepor marcadores de eventos em datas exatas.
  - Eventos pontuais -> linha vertical tracejada; períodos -> faixa sombreada.
    Laranja = evento externo (mercado/macro); azul = evento interno (empresa).
  - Marcadores desenhados com add_shape (e não add_vline), que falha com
    eixos de data em versões recentes do pandas/plotly.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from config_indicadores import CORES
from eventos_estrategicos import CATEGORIAS
from analises_eventos import period_para_data, period_para_rotulo

TEMPLATE = "plotly_white"
COR_EXTERNO = CORES["acento"]
COR_INTERNO = CORES["primaria"]
COR_ORIGEM = {"externo": COR_EXTERNO, "interno": COR_INTERNO}
COR_VEREDITO = {"coerente": CORES["positivo"], "contraria": CORES["negativo"],
                "inconclusivo": CORES["neutro"], "sem_dados": "#BDC3C7"}


# ======================================================================
# Helpers
# ======================================================================
def _x_e_rotulos(serie):
    """Eixo X (datas) e rótulos de hover ('3T21' para trimestres)."""
    if isinstance(serie.index, pd.PeriodIndex):
        x = [period_para_data(p) for p in serie.index]
        rot = [period_para_rotulo(p) for p in serie.index]
    else:
        x = list(pd.to_datetime(serie.index))
        rot = [d.strftime("%b/%Y") for d in x]
    return x, rot


def _tickformat(fmt):
    return {"pct": ".0%", "pct2": ".1%", "num": ",.0f", "preco": ",.2f", "indice": ",.0f", "nota": ".1f"}.get(fmt, ",.0f")


def _hover_y(fmt):
    return {"pct": "%{y:.1%}", "pct2": "%{y:.2%}", "num": "%{y:,.0f}",
            "preco": "R$ %{y:,.2f}", "indice": "%{y:,.0f}", "nota": "%{y:.2f}"}.get(fmt, "%{y:,.0f}")


def _adicionar_eventos(fig, eventos, mostrar_rotulos=True):
    """Marca eventos no gráfico: linha (pontual) ou faixa (período)."""
    ult_x, desloc = None, 0
    for ev in sorted(eventos, key=lambda e: e.data_inicio):
        cor = COR_ORIGEM.get(ev.origem, CORES["neutro"])
        x0 = pd.Timestamp(ev.data_inicio)
        if ev.eh_periodo:
            x1 = pd.Timestamp(ev.data_fim)
            fig.add_shape(type="rect", xref="x", yref="paper", x0=x0, x1=x1, y0=0, y1=1,
                          fillcolor=cor, opacity=0.10, line=dict(width=0), layer="below")
            fig.add_shape(type="line", xref="x", yref="paper", x0=x0, x1=x0, y0=0, y1=1,
                          line=dict(color=cor, width=1, dash="dot"))
        else:
            fig.add_shape(type="line", xref="x", yref="paper", x0=x0, x1=x0, y0=0, y1=1,
                          line=dict(color=cor, width=1.6, dash="dash"))
        if mostrar_rotulos:
            # eventos muito próximos: desloca o rótulo para não sobrepor
            if ult_x is not None and (x0 - ult_x).days < 150:
                desloc += 15
            else:
                desloc = 0
            ult_x = x0
            fig.add_annotation(
                x=x0, y=1.0, xref="x", yref="paper", text=f"<b>{ev.rotulo_curto}</b>",
                showarrow=False, textangle=-90, xanchor="left", yanchor="top",
                xshift=3 + desloc, font=dict(size=10, color=cor),
                bgcolor="rgba(255,255,255,0.65)",
            )


def _adicionar_faixas(fig, faixas):
    """faixas: lista de dict(x0, x1, rotulo, cor) — janelas 'antes'/'depois' da avaliação."""
    for f in faixas or []:
        fig.add_shape(type="rect", xref="x", yref="paper", x0=f["x0"], x1=f["x1"], y0=0, y1=1,
                      fillcolor=f.get("cor", "#999999"), opacity=0.16, line=dict(width=0), layer="below")
        fig.add_annotation(x=f["x0"], y=0.0, xref="x", yref="paper", text=f.get("rotulo", ""),
                           showarrow=False, xanchor="left", yanchor="bottom",
                           font=dict(size=10, color="#555555"))


# ======================================================================
# Gráfico genérico: séries + eventos
# ======================================================================
def serie_com_eventos(series, eventos, titulo, y1_titulo="", y2_titulo=None,
                      fmt_y1="num", fmt_y2="num", faixas=None, ano_ini=None, ano_fim=None,
                      mostrar_rotulos=True, altura=480, empilhar=False, log_y1=False,
                      eventos_leves=None, range_y1=None):
    """Gráfico de séries temporais com marcadores de eventos.

    series: lista de dict:
        nome, serie (Series), tipo ('linha'|'barra'), eixo (1|2), cor, fmt,
        dash (opcional), degrau (bool), cor_sinal (bool — barras verdes/vermelhas), opacidade.
    eventos_leves: lista de datas (date) desenhadas como linhas finas, sem rótulo (ex.: Black Friday).
    range_y1: [min, max] para fixar o eixo esquerdo (ex.: [0, 10] para notas).
    """
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    tem_y2 = False
    paleta = [CORES["secundaria"], CORES["acento"], CORES["positivo"], CORES["trends"],
              CORES["negativo"], CORES["invest"]]

    for i, sp in enumerate(series):
        s = sp.get("serie")
        if s is None or len(s) == 0:
            continue
        s = s.dropna()
        if s.empty:
            continue
        x, rot = _x_e_rotulos(s)
        fmt = sp.get("fmt", fmt_y1 if sp.get("eixo", 1) == 1 else fmt_y2)
        cor = sp.get("cor", paleta[i % len(paleta)])
        hover = f"<b>%{{customdata}}</b><br>{sp['nome']}: {_hover_y(fmt)}<extra></extra>"
        eixo2 = sp.get("eixo", 1) == 2
        tem_y2 = tem_y2 or eixo2

        if sp.get("tipo", "linha") == "barra":
            if sp.get("cor_sinal"):
                cores = [CORES["positivo"] if v >= 0 else CORES["negativo"] for v in s.values]
            else:
                cores = cor
            trace = go.Bar(name=sp["nome"], x=x, y=s.values, customdata=rot,
                           marker_color=cores, opacity=sp.get("opacidade", 0.85),
                           hovertemplate=hover)
        else:
            mostrar_pontos = len(s) <= 60
            trace = go.Scatter(
                name=sp["nome"], x=x, y=s.values, customdata=rot,
                mode="lines+markers" if mostrar_pontos else "lines",
                line=dict(color=cor, width=sp.get("largura", 2.6), dash=sp.get("dash"),
                          shape="hv" if sp.get("degrau") else "linear"),
                marker=dict(size=5), hovertemplate=hover,
            )
        fig.add_trace(trace, secondary_y=eixo2)

    _adicionar_faixas(fig, faixas)
    for d in eventos_leves or []:
        fig.add_shape(type="line", xref="x", yref="paper", x0=pd.Timestamp(d), x1=pd.Timestamp(d),
                      y0=0, y1=1, line=dict(color="#9AA5B1", width=0.9, dash="dot"), layer="below")
    _adicionar_eventos(fig, eventos, mostrar_rotulos)

    fig.update_layout(
        title=titulo, template=TEMPLATE, height=altura, hovermode="x unified",
        barmode="stack" if empilhar else "group",
        legend=dict(orientation="h", yanchor="top", y=-0.12, x=0),
        margin=dict(t=70, b=70),
    )
    fig.update_yaxes(title_text=y1_titulo, tickformat=_tickformat(fmt_y1), secondary_y=False,
                     type="log" if log_y1 else "linear", range=range_y1)
    if tem_y2:
        fig.update_yaxes(title_text=y2_titulo or "", tickformat=_tickformat(fmt_y2),
                         secondary_y=True, showgrid=False)
    else:
        fig.update_yaxes(visible=False, secondary_y=True)
    if ano_ini and ano_fim:
        fig.update_xaxes(range=[f"{ano_ini}-01-01", f"{ano_fim}-12-31"])
    return fig


# ======================================================================
# Linha do tempo estratégica (raias por categoria)
# ======================================================================
def timeline_estrategica(eventos, ano_ini=2018, ano_fim=2026, altura=520):
    fig = go.Figure()
    for ev in eventos:
        cor = COR_ORIGEM.get(ev.origem, CORES["neutro"])
        info = [[ev.nome, ev.data_exibicao]]
        if ev.eh_periodo:
            x0, x1 = pd.Timestamp(ev.data_inicio), pd.Timestamp(ev.data_fim)
            meio = x0 + (x1 - x0) / 2
            fig.add_trace(go.Scatter(
                x=[x0, meio, x1], y=[ev.categoria] * 3, mode="lines+text",
                line=dict(color=cor, width=18), opacity=0.55,
                text=["", ev.rotulo_curto, ""], textposition=ev.texto_pos,
                textfont=dict(size=12, color="#000000", weight="bold"),
                customdata=info * 3,
                hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]}<extra></extra>",
                showlegend=False))
        else:
            fig.add_trace(go.Scatter(
                x=[pd.Timestamp(ev.data_inicio)], y=[ev.categoria], mode="markers+text",
                marker=dict(symbol="diamond", size=17, color=cor, line=dict(color="white", width=1.5)),
                text=[ev.rotulo_curto], textposition=ev.texto_pos,
                textfont=dict(size=12, color="#000000", weight="bold"),
                customdata=info,
                hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]}<extra></extra>",
                showlegend=False))
    for nome, cor in (("Evento externo (mercado/economia)", COR_EXTERNO),
                      ("Evento interno (estratégia da empresa)", COR_INTERNO)):
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers",
                                 marker=dict(size=11, color=cor, symbol="diamond"), name=nome))
    fig.update_layout(
        title="Linha do Tempo Estratégica do Magalu", template=TEMPLATE, height=altura,
        yaxis=dict(categoryorder="array", categoryarray=CATEGORIAS[::-1], title=""),
        xaxis=dict(range=[f"{ano_ini}-01-01", f"{ano_fim}-12-31"], title=""),
        legend=dict(orientation="h", yanchor="top", y=-0.1, x=0),
        margin=dict(t=70, b=60),
    )
    return fig


# ======================================================================
# Correlação por defasagem
# ======================================================================
def barras_defasagem(df, titulo, r_crit=None, rotulo_x="Defasagem (trimestres): X(t) × Y(t+k)"):
    fig = go.Figure()
    if df is None or df.empty:
        fig.update_layout(title=f"{titulo} (sem dados)", template=TEMPLATE)
        return fig
    cores = [CORES["secundaria"] if (not np.isnan(r) and r >= 0) else CORES["negativo"] for r in df["r"]]
    cores = [CORES["acento"] if k == 0 else c for k, c in zip(df["defasagem"], cores)]
    fig.add_trace(go.Bar(
        x=df["defasagem"], y=df["r"], marker_color=cores,
        text=[f"n={n}" for n in df["n"]], textposition="outside",
        hovertemplate="k=%{x}<br>r=%{y:.2f}<extra></extra>", showlegend=False))
    if r_crit and not np.isnan(r_crit):
        for sinal in (1, -1):
            fig.add_shape(type="line", xref="paper", yref="y", x0=0, x1=1,
                          y0=sinal * r_crit, y1=sinal * r_crit,
                          line=dict(color=CORES["neutro"], dash="dash", width=1))
        fig.add_annotation(xref="paper", yref="y", x=1, y=r_crit, showarrow=False, xanchor="right",
                           yanchor="bottom", text=f"|r| crítico ≈ {r_crit:.2f} (ref. aprox.)",
                           font=dict(size=10, color="#777777"))
    fig.update_layout(title=titulo, template=TEMPLATE, height=380,
                      xaxis=dict(title=rotulo_x, dtick=1),
                      yaxis=dict(title="Correlação de Pearson (r)", range=[-1.05, 1.05]),
                      margin=dict(t=60))
    return fig


# ======================================================================
# Placar de coerência (todos os eventos)
# ======================================================================
def placar_coerencia(df_todos):
    fig = go.Figure()
    if df_todos is None or df_todos.empty:
        fig.update_layout(title="Placar de coerência (sem dados)", template=TEMPLATE)
        return fig
    tab = (df_todos.groupby(["Evento", "Veredito"]).size().unstack(fill_value=0))
    ordem = list(dict.fromkeys(df_todos["Evento"]))
    tab = tab.reindex(ordem)
    nomes = {"coerente": "Coerente", "contraria": "Contrária",
             "inconclusivo": "Inconclusiva", "sem_dados": "Sem dados"}
    for v in ("coerente", "contraria", "inconclusivo", "sem_dados"):
        if v in tab.columns:
            fig.add_trace(go.Bar(name=nomes[v], y=tab.index, x=tab[v], orientation="h",
                                 marker_color=COR_VEREDITO[v]))
    fig.update_layout(
        title="Placar de coerência por evento (nº de hipóteses)", template=TEMPLATE,
        barmode="stack", height=max(340, 60 * len(tab) + 120),
        yaxis=dict(autorange="reversed"), xaxis=dict(title="Nº de hipóteses testadas", dtick=1),
        legend=dict(orientation="h", yanchor="top", y=-0.15, x=0), margin=dict(l=10, t=60),
    )
    return fig


# ======================================================================
# Modelo conceitual (Graphviz DOT para st.graphviz_chart)
# ======================================================================
def modelo_conceitual_dot():
    return """
digraph G {
  rankdir=TB; nodesep=0.35; ranksep=0.45;
  node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=11, margin="0.18,0.10"];
  edge [color="#7F8C8D", arrowsize=0.8];

  ext [label="EVENTOS EXTERNOS\\nPandemia · Selic · Ciclo de juros", fillcolor="#FDEBD0", color="#F18F01"];
  int [label="EVENTOS INTERNOS\\nAquisições · Follow-on · Aporte · Foco em rentabilidade", fillcolor="#D6E4F0", color="#1F4E79"];
  op  [label="INDICADORES OPERACIONAIS\\nMix de canais · Marketplace 3P · Investimentos (tecnologia, logística, lojas)", fillcolor="#EAF2F8", color="#2E86AB"];
  fin [label="INDICADORES FINANCEIROS\\nReceita · EBITDA · Margens · Resultado financeiro · Lucro · Fluxo de caixa", fillcolor="#EAF2F8", color="#2E86AB"];
  cli [label="PERCEPÇÃO DO CLIENTE\\nGoogle Trends (atenção) · Reclame Aqui (experiência)", fillcolor="#F4ECF7", color="#8C7AE6"];
  mer [label="PERCEPÇÃO DO MERCADO\\nCotação MGLU3 (ajustada) · Volume", fillcolor="#E8F6F3", color="#45B8AC"];

  ext -> op; int -> op;
  ext -> fin [style=dashed, label=" juros ", fontsize=9, fontcolor="#7F8C8D"];
  op -> fin; fin -> cli [style=dashed]; op -> cli [style=dashed];
  fin -> mer; cli -> mer [style=dashed];
  {rank=same; ext; int;}
}
"""
