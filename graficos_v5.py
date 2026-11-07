"""
graficos_v5.py
==============
Fábrica unificada de gráficos Plotly. Consolida todos os gráficos
usados no dashboard (DRE básico, V2 e V3).
"""

import re
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
# FUNÇÕES BÁSICAS E EXECUTIVAS V1/V2
# ======================================================================

def cotacao_diaria(serie, ano, coluna="Fechamento"):
    """Gráfico de linha da cotação diária da ação, em um ano."""
    fig = go.Figure()
    if serie.empty:
        fig.update_layout(title=f"Cotação — {coluna} — {ano} (sem dados)", template=TEMPLATE)
        return fig

    fig.add_trace(go.Scatter(
        x=serie.index, y=serie.values, mode="lines",
        line=dict(color=CORES["cotacao"], width=2),
    ))
    fig.update_layout(
        title=f"Cotação da ação — {coluna} — {ano}",
        xaxis_title="Data", yaxis_title="R$", template=TEMPLATE,
    )
    return fig

def visao_executiva_evolucao(df, titulo="Evolução dos indicadores selecionados"):
    """Gráfico temporal multilinhas com indicadores escolhidos pelo usuário."""
    fig = go.Figure()
    if df is None or df.empty:
        fig.update_layout(title=f"{titulo} (sem dados)", template=TEMPLATE)
        return fig

    for i, coluna in enumerate(df.columns):
        cor = list(CORES.values())[i % len(CORES)]
        fig.add_trace(go.Scatter(
            name=coluna, x=[str(j) for j in df.index], y=df[coluna].values,
            mode="lines+markers", line=dict(width=2, color=cor),
        ))

    fig.update_layout(title=titulo, template=TEMPLATE, legend=dict(orientation="h", yanchor="bottom", y=1.02), hovermode="x unified", height=500)
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
            name=coluna, x=[str(j) for j in df_base100.index], y=df_base100[coluna].values,
            mode="lines+markers", line=dict(width=2, color=cor),
        ))

    fig.add_hline(y=100, line_dash="dash", line_color="#999999", annotation_text="Base 100", annotation_position="right")
    fig.update_layout(title="Desempenho Operacional × Percepção de Mercado (base 100)", template=TEMPLATE, legend=dict(orientation="h", yanchor="bottom", y=1.02), hovermode="x unified", height=500)
    fig.update_yaxes(title_text="Índice (base 100)")
    return fig

def invest_mercado_cotacao_volume(serie_fech, serie_volume):
    """Cotação (linha) × Volume (barras)."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    if serie_volume is not None and not serie_volume.empty:
        fig.add_trace(go.Bar(name="Volume Financeiro", x=serie_volume.index, y=serie_volume.values / 1_000_000, marker_color=CORES["acento"], opacity=0.7), secondary_y=True)
    if serie_fech is not None and not serie_fech.empty:
        fig.add_trace(go.Scatter(name="Fechamento (R$)", x=serie_fech.index, y=serie_fech.values, mode="lines", line=dict(color=CORES["mercado"], width=2)), secondary_y=False)
    
    fig.update_layout(title="Cotação MGLU3 × Volume negociado", template=TEMPLATE, legend=dict(orientation="h", yanchor="bottom", y=1.02), hovermode="x unified", height=500, xaxis=dict(tickformat="%Y"))
    fig.update_yaxes(title_text="Preço (R$)", secondary_y=False)
    fig.update_yaxes(title_text="Volume (R$ milhões)", secondary_y=True)
    return fig

def omni_receita_por_loja_e_m2(serie_receita_loja, serie_receita_m2, eventos=None):
    """Receita por loja × Receita por m² (linhas, eixos separados), com eventos."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Converte os índices (que podem ser PeriodIndex) para Datas, 
    # permitindo que o Plotly desenhe as linhas de evento corretamente
    if serie_receita_loja is not None and not serie_receita_loja.empty:
        x_loja = [period_para_data(p) if isinstance(p, pd.Period) else p for p in serie_receita_loja.index]
        fig.add_trace(go.Scatter(name="Receita por Loja", x=x_loja, y=serie_receita_loja.values, mode="lines+markers", line=dict(color=CORES["secundaria"], width=3)), secondary_y=False)
        
    if serie_receita_m2 is not None and not serie_receita_m2.empty:
        x_m2 = [period_para_data(p) if isinstance(p, pd.Period) else p for p in serie_receita_m2.index]
        fig.add_trace(go.Scatter(name="Receita por m²", x=x_m2, y=serie_receita_m2.values, mode="lines+markers", line=dict(color=CORES["acento"], width=3, dash="dot")), secondary_y=True)
    
    # Adiciona o fundo de eventos (se houver)
    if eventos:
        _adicionar_eventos(fig, eventos, mostrar_rotulos=True)

    fig.update_layout(
        title="Receita por Loja × Receita por m²", 
        template=TEMPLATE, 
        legend=dict(orientation="h", yanchor="bottom", y=1.02), 
        hovermode="x unified", 
        height=500
    )
    fig.update_yaxes(title_text="R$ / loja", secondary_y=False)
    fig.update_yaxes(title_text="R$ / m²", secondary_y=True)
    return fig

def cliente_trends_vs_vendas(serie_trends, serie_vendas, nome_vendas="Vendas Totais"):
    """Google Trends (linha) × Vendas (linha, eixo 2)."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    if serie_trends is not None and not serie_trends.empty:
        fig.add_trace(go.Scatter(name="Interesse de busca (Google Trends)", x=serie_trends.index, y=serie_trends.values, mode="lines", line=dict(color=CORES["trends"], width=2)), secondary_y=False)
    if serie_vendas is not None and not serie_vendas.empty:
        fig.add_trace(go.Scatter(name=nome_vendas, x=[str(i) for i in serie_vendas.index], y=serie_vendas.values, mode="lines+markers", line=dict(color=CORES["secundaria"], width=3)), secondary_y=True)
    
    fig.update_layout(title=f"Google Trends × {nome_vendas}", template=TEMPLATE, legend=dict(orientation="h", yanchor="bottom", y=1.02), hovermode="x unified", height=500)
    fig.update_yaxes(title_text="Interesse (0-100)", secondary_y=False)
    fig.update_yaxes(title_text="Vendas (R$)", secondary_y=True)
    return fig

def cliente_ra_vs_vendas_online(df_ra, serie_vendas_online):
    """Nota Média RA (área preenchida) × Vendas E-commerce (linha)."""
    import re
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    if df_ra is not None and not df_ra.empty and "Nota Média" in df_ra.columns:
        for i, (rotulo, row) in enumerate(df_ra.iterrows()):
            texto = str(rotulo).strip()
            if texto.lower() in ("geral", "total"):
                continue
                
            nota = row["Nota Média"]
            if pd.isna(nota):
                continue
                
            x0, x1 = None, None
            
            # Caso Anual: 2024
            m_ano = re.match(r'^(\d{4})$', texto)
            if m_ano:
                ano = int(m_ano.group(1))
                x0 = pd.Timestamp(year=ano, month=1, day=1)
                x1 = pd.Timestamp(year=ano, month=12, day=31)
                
            # Caso Semestral: 1S2024 ou 2S2024
            m_sem = re.match(r'^(\d)S(\d{4})$', texto)
            if m_sem and x0 is None:
                sem = int(m_sem.group(1))
                ano = int(m_sem.group(2))
                mes_ini = 1 if sem == 1 else 7
                mes_fim = 6 if sem == 1 else 12
                x0 = pd.Timestamp(year=ano, month=mes_ini, day=1)
                x1 = pd.Timestamp(year=ano, month=mes_fim, day=1) + pd.offsets.MonthEnd(0)
                
            if x0 and x1:
                # Usa Scatter com preenchimento em vez de Bar
                fig.add_trace(go.Scatter(
                    name="Nota Média (RA Online)", 
                    x=[x0, x1, x1, x0, x0], # Desenha o retângulo completo (fechando o ciclo)
                    y=[0, 0, nota, nota, 0],
                    fill='toself',
                    fillcolor='rgba(201, 138, 75, 0.4)', # Cor do RA com transparência
                    line=dict(color='rgba(255,255,255,0)'), # Sem borda
                    hovertemplate=f"Período: {texto}<br>Nota: {nota:.1f}<extra></extra>",
                    showlegend=(i == 0) # Mostra a legenda apenas na primeira vez
                ), secondary_y=False)

    if serie_vendas_online is not None and not serie_vendas_online.empty:
        x_vendas = [period_para_data(p) if isinstance(p, pd.Period) else p for p in serie_vendas_online.index]
        fig.add_trace(go.Scatter(
            name="Vendas E-commerce", 
            x=x_vendas, 
            y=serie_vendas_online.values, 
            mode="lines+markers", 
            line=dict(color=CORES["secundaria"], width=3)
        ), secondary_y=True)
    
    fig.update_layout(
        title="Reclame Aqui (Online) × Vendas E-commerce", 
        template=TEMPLATE, 
        legend=dict(orientation="h", yanchor="bottom", y=1.02), 
        hovermode="x unified", 
        height=500
    )
    fig.update_yaxes(title_text="Nota (0-10)", secondary_y=False, range=[0, 10])
    fig.update_yaxes(title_text="Vendas (R$)", secondary_y=True)
    return fig

def cliente_ra_vs_vendas_fisica(df_ra, serie_vendas_fisica):
    """Nota Média RA (área preenchida) × Vendas Lojas Físicas (linha)."""
    import re
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    if df_ra is not None and not df_ra.empty and "Nota Média" in df_ra.columns:
        for i, (rotulo, row) in enumerate(df_ra.iterrows()):
            texto = str(rotulo).strip()
            if texto.lower() in ("geral", "total"):
                continue
                
            nota = row["Nota Média"]
            if pd.isna(nota):
                continue
                
            x0, x1 = None, None
            
            m_ano = re.match(r'^(\d{4})$', texto)
            if m_ano:
                ano = int(m_ano.group(1))
                x0 = pd.Timestamp(year=ano, month=1, day=1)
                x1 = pd.Timestamp(year=ano, month=12, day=31)
                
            m_sem = re.match(r'^(\d)S(\d{4})$', texto)
            if m_sem and x0 is None:
                sem = int(m_sem.group(1))
                ano = int(m_sem.group(2))
                x0 = pd.Timestamp(year=ano, month=1 if sem==1 else 7, day=1)
                x1 = pd.Timestamp(year=ano, month=6 if sem==1 else 12, day=1) + pd.offsets.MonthEnd(0)
                
            if x0 and x1:
                fig.add_trace(go.Scatter(
                    name="Nota Média (RA Física)", 
                    x=[x0, x1, x1, x0, x0], 
                    y=[0, 0, nota, nota, 0],
                    fill='toself',
                    fillcolor='rgba(201, 138, 75, 0.4)',
                    line=dict(color='rgba(255,255,255,0)'),
                    hovertemplate=f"Período: {texto}<br>Nota: {nota:.1f}<extra></extra>",
                    showlegend=(i == 0)
                ), secondary_y=False)

    if serie_vendas_fisica is not None and not serie_vendas_fisica.empty:
        x_vendas = [period_para_data(p) if isinstance(p, pd.Period) else p for p in serie_vendas_fisica.index]
        fig.add_trace(go.Scatter(
            name="Vendas Lojas Físicas", 
            x=x_vendas, 
            y=serie_vendas_fisica.values, 
            mode="lines+markers", 
            line=dict(color=CORES["secundaria"], width=3)
        ), secondary_y=True)
        
    fig.update_layout(
        title="Reclame Aqui (Física) × Vendas Lojas Físicas", 
        template=TEMPLATE, 
        legend=dict(orientation="h", yanchor="bottom", y=1.02), 
        hovermode="x unified", 
        height=500
    )
    fig.update_yaxes(title_text="Nota (0-10)", secondary_y=False, range=[0, 10])
    fig.update_yaxes(title_text="Vendas (R$)", secondary_y=True)
    return fig

def cliente_luizacred(df_ra, serie_faturamento, serie_lucro):
    """Luizacred: Nota RA + Faturamento + Lucro (3 séries, 2 eixos)."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    if df_ra is not None and not df_ra.empty and "Nota Média" in df_ra.columns:
        fig.add_trace(go.Bar(name="Nota Média (RA Luizacred)", x=[str(i) for i in df_ra.index], y=df_ra["Nota Média"].values, marker_color=CORES["ra"]), secondary_y=False)
    if serie_faturamento is not None and not serie_faturamento.empty:
        fig.add_trace(go.Scatter(name="Faturamento Luizacred", x=[str(i) for i in serie_faturamento.index], y=serie_faturamento.values, mode="lines+markers", line=dict(color=CORES["secundaria"], width=3)), secondary_y=True)
    if serie_lucro is not None and not serie_lucro.empty:
        fig.add_trace(go.Scatter(name="Lucro Luizacred", x=[str(i) for i in serie_lucro.index], y=serie_lucro.values, mode="lines+markers", line=dict(color=CORES["positivo"], width=3, dash="dot")), secondary_y=True)
    
    fig.update_layout(title="Luizacred: Reputação × Faturamento × Lucro", template=TEMPLATE, legend=dict(orientation="h", yanchor="bottom", y=1.02), hovermode="x unified", height=500)
    fig.update_yaxes(title_text="Nota (0-10)", secondary_y=False, range=[0, 10])
    fig.update_yaxes(title_text="R$", secondary_y=True)
    return fig

def relacoes_dispersao(serie_x, serie_y, nome_x, nome_y, r=None, n=None):
    """Dispersão com linha de tendência e anotação de correlação."""
    fig = go.Figure()
    df = pd.DataFrame({"x": serie_x, "y": serie_y}).dropna()
    if df.empty:
        fig.update_layout(title="Dispersão (sem dados alinhados)", template=TEMPLATE)
        return fig

    fig.add_trace(go.Scatter(x=df["x"], y=df["y"], mode="markers", marker=dict(size=9, color=CORES["secundaria"]), name="Observações", text=[str(i) for i in df.index]))

    if len(df) >= 8 and df["x"].std() > 0:
        coef = np.polyfit(df["x"], df["y"], 1)
        x_linha = np.linspace(df["x"].min(), df["x"].max(), 50)
        y_linha = coef[0] * x_linha + coef[1]
        fig.add_trace(go.Scatter(x=x_linha, y=y_linha, mode="lines", line=dict(color=CORES["negativo"], width=2, dash="dash"), name="Tendência linear"))

    anotacao = f"r = {r:.3f}" if r is not None and not np.isnan(r) else "r indisponível"
    if n: anotacao += f" · n = {n}"

    fig.update_layout(title=f"Dispersão: {nome_x} × {nome_y}", template=TEMPLATE, xaxis_title=nome_x, yaxis_title=nome_y, height=500,
                      annotations=[dict(text=anotacao, xref="paper", yref="paper", x=0.02, y=0.98, showarrow=False, bgcolor="rgba(255,255,255,0.85)", bordercolor="#cccccc", borderwidth=1)])
    return fig

# ======================================================================
# FUNÇÕES V3 (Eventos e Linha do Tempo)
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
    return {"pct": "%{y:.1%}", "pct2": "%{y:.2%}", "num": "%{y:,.0f}", "preco": "R$ %{y:,.2f}", "indice": "%{y:,.0f}", "nota": "%{y:.2f}"}.get(fmt, "%{y:,.0f}")

def _adicionar_eventos(fig, eventos, mostrar_rotulos=True):
    """Marca eventos no gráfico: linha (pontual) ou faixa (período)."""
    ult_x, desloc = None, 0
    for ev in sorted(eventos, key=lambda e: e.data_inicio):
        cor = COR_ORIGEM.get(ev.origem, CORES["neutro"])
        x0 = pd.Timestamp(ev.data_inicio)
        if ev.eh_periodo:
            x1 = pd.Timestamp(ev.data_fim)
            fig.add_shape(type="rect", xref="x", yref="paper", x0=x0, x1=x1, y0=0, y1=1, fillcolor=cor, opacity=0.10, line=dict(width=0), layer="below")
            fig.add_shape(type="line", xref="x", yref="paper", x0=x0, x1=x0, y0=0, y1=1, line=dict(color=cor, width=1, dash="dot"))
        else:
            fig.add_shape(type="line", xref="x", yref="paper", x0=x0, x1=x0, y0=0, y1=1, line=dict(color=cor, width=1.6, dash="dash"))
        if mostrar_rotulos:
            if ult_x is not None and (x0 - ult_x).days < 150: desloc += 15
            else: desloc = 0
            ult_x = x0
            fig.add_annotation(x=x0, y=1.0, xref="x", yref="paper", text=f"<b>{ev.rotulo_curto}</b>", showarrow=False, textangle=-90, xanchor="left", yanchor="top", xshift=3 + desloc, font=dict(size=10, color=cor), bgcolor="rgba(255,255,255,0.65)")

def _adicionar_faixas(fig, faixas):
    """faixas: lista de dict(x0, x1, rotulo, cor) — janelas 'antes'/'depois' da avaliação."""
    for f in faixas or []:
        fig.add_shape(type="rect", xref="x", yref="paper", x0=f["x0"], x1=f["x1"], y0=0, y1=1, fillcolor=f.get("cor", "#999999"), opacity=0.16, line=dict(width=0), layer="below")
        fig.add_annotation(x=f["x0"], y=0.0, xref="x", yref="paper", text=f.get("rotulo", ""), showarrow=False, xanchor="left", yanchor="bottom", font=dict(size=10, color="#555555"))

def serie_com_eventos(series, eventos, titulo, y1_titulo="", y2_titulo=None, fmt_y1="num", fmt_y2="num", faixas=None, ano_ini=None, ano_fim=None, mostrar_rotulos=True, altura=480, empilhar=False, log_y1=False, eventos_leves=None, range_y1=None):
    """Gráfico de séries temporais com marcadores de eventos."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    tem_y2 = False
    paleta = [CORES["secundaria"], CORES["acento"], CORES["positivo"], CORES["trends"], CORES["negativo"], CORES["invest"]]

    for i, sp in enumerate(series):
        s = sp.get("serie")
        if s is None or len(s) == 0: continue
        s = s.dropna()
        if s.empty: continue
        x, rot = _x_e_rotulos(s)
        fmt = sp.get("fmt", fmt_y1 if sp.get("eixo", 1) == 1 else fmt_y2)
        cor = sp.get("cor", paleta[i % len(paleta)])
        hover = f"<b>%{{customdata}}</b><br>{sp['nome']}: {_hover_y(fmt)}<extra></extra>"
        eixo2 = sp.get("eixo", 1) == 2
        tem_y2 = tem_y2 or eixo2

        if sp.get("tipo", "linha") == "barra":
            if sp.get("cor_sinal"): cores = [CORES["positivo"] if v >= 0 else CORES["negativo"] for v in s.values]
            else: cores = cor
            trace = go.Bar(name=sp["nome"], x=x, y=s.values, customdata=rot, marker_color=cores, opacity=sp.get("opacidade", 0.85), hovertemplate=hover)
        else:
            mostrar_pontos = len(s) <= 60
            trace = go.Scatter(name=sp["nome"], x=x, y=s.values, customdata=rot, mode="lines+markers" if mostrar_pontos else "lines", line=dict(color=cor, width=sp.get("largura", 2.6), dash=sp.get("dash"), shape="hv" if sp.get("degrau") else "linear"), marker=dict(size=5), hovertemplate=hover)
        fig.add_trace(trace, secondary_y=eixo2)

    _adicionar_faixas(fig, faixas)
    for d in eventos_leves or []:
        fig.add_shape(type="line", xref="x", yref="paper", x0=pd.Timestamp(d), x1=pd.Timestamp(d), y0=0, y1=1, line=dict(color="#9AA5B1", width=0.9, dash="dot"), layer="below")
    _adicionar_eventos(fig, eventos, mostrar_rotulos)

    fig.update_layout(title=titulo, template=TEMPLATE, height=altura, hovermode="x unified", barmode="stack" if empilhar else "group", legend=dict(orientation="h", yanchor="top", y=-0.12, x=0), margin=dict(t=70, b=70))
    fig.update_yaxes(title_text=y1_titulo, tickformat=_tickformat(fmt_y1), secondary_y=False, type="log" if log_y1 else "linear", range=range_y1)
    if tem_y2: fig.update_yaxes(title_text=y2_titulo or "", tickformat=_tickformat(fmt_y2), secondary_y=True, showgrid=False)
    else: fig.update_yaxes(visible=False, secondary_y=True)
    if ano_ini and ano_fim: fig.update_xaxes(range=[f"{ano_ini}-01-01", f"{ano_fim}-12-31"])
    return fig

def timeline_estrategica(eventos, ano_ini=2018, ano_fim=2026, altura=520):
    """Linha do tempo com raias por categoria."""
    fig = go.Figure()
    for ev in eventos:
        cor = COR_ORIGEM.get(ev.origem, CORES["neutro"])
        info = [[ev.nome, ev.data_exibicao]]
        if ev.eh_periodo:
            x0, x1 = pd.Timestamp(ev.data_inicio), pd.Timestamp(ev.data_fim)
            meio = x0 + (x1 - x0) / 2
            fig.add_trace(go.Scatter(x=[x0, meio, x1], y=[ev.categoria] * 3, mode="lines+text", line=dict(color=cor, width=18), opacity=0.85, text=["", ev.rotulo_curto, ""], textposition=ev.texto_pos, textfont=dict(size=12, color="#000000", weight="bold"), customdata=info * 3, hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]}<extra></extra>", showlegend=False))
        else:
            fig.add_trace(go.Scatter(x=[pd.Timestamp(ev.data_inicio)], y=[ev.categoria], mode="markers+text", marker=dict(symbol="diamond", size=17, color=cor, line=dict(color="white", width=1.5)), text=[ev.rotulo_curto], textposition=ev.texto_pos, textfont=dict(size=12, color="#000000", weight="bold"), customdata=info, hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]}<extra></extra>", showlegend=False))
    
    for nome, cor in (("Evento externo (mercado/economia)", COR_EXTERNO), ("Evento interno (estratégia da empresa)", COR_INTERNO)):
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", marker=dict(size=11, color=cor, symbol="diamond"), name=nome))
    
    fig.update_layout(title="Linha do Tempo Estratégica do Magalu", template=TEMPLATE, height=altura, yaxis=dict(categoryorder="array", categoryarray=CATEGORIAS[::-1], title=""), xaxis=dict(range=[f"{ano_ini}-01-01", f"{ano_fim}-12-31"], title=""), legend=dict(orientation="h", yanchor="top", y=-0.1, x=0), margin=dict(t=70, b=60))
    return fig

def barras_defasagem(df, titulo, r_crit=None, rotulo_x="Defasagem (trimestres): X(t) × Y(t+k)"):
    """Gráfico de barras para mostrar a correlação em diferentes defasagens."""
    fig = go.Figure()
    if df is None or df.empty:
        fig.update_layout(title=f"{titulo} (sem dados)", template=TEMPLATE)
        return fig
    
    cores = [CORES["secundaria"] if (not np.isnan(r) and r >= 0) else CORES["negativo"] for r in df["r"]]
    cores = [CORES["acento"] if k == 0 else c for k, c in zip(df["defasagem"], cores)]
    fig.add_trace(go.Bar(x=df["defasagem"], y=df["r"], marker_color=cores, text=[f"n={n}" for n in df["n"]], textposition="outside", hovertemplate="k=%{x}<br>r=%{y:.2f}<extra></extra>", showlegend=False))
    
    if r_crit and not np.isnan(r_crit):
        for sinal in (1, -1):
            fig.add_shape(type="line", xref="paper", yref="y", x0=0, x1=1, y0=sinal * r_crit, y1=sinal * r_crit, line=dict(color=CORES["neutro"], dash="dash", width=1))
        fig.add_annotation(xref="paper", yref="y", x=1, y=r_crit, showarrow=False, xanchor="right", yanchor="bottom", text=f"|r| crítico ≈ {r_crit:.2f} (ref. aprox.)", font=dict(size=10, color="#777777"))
    
    fig.update_layout(title=titulo, template=TEMPLATE, height=380, xaxis=dict(title=rotulo_x, dtick=1), yaxis=dict(title="Correlação de Pearson (r)", range=[-1.05, 1.05]), margin=dict(t=60))
    return fig

def placar_coerencia(df_todos):
    """Gráfico de barras empilhadas mostrando o veredito de cada evento."""
    fig = go.Figure()
    if df_todos is None or df_todos.empty:
        fig.update_layout(title="Placar de coerência (sem dados)", template=TEMPLATE)
        return fig
    
    tab = (df_todos.groupby(["Evento", "Veredito"]).size().unstack(fill_value=0))
    ordem = list(dict.fromkeys(df_todos["Evento"]))
    tab = tab.reindex(ordem)
    nomes = {"coerente": "Coerente", "contraria": "Contrária", "inconclusivo": "Inconclusiva", "sem_dados": "Sem dados"}
    
    for v in ("coerente", "contraria", "inconclusivo", "sem_dados"):
        if v in tab.columns:
            fig.add_trace(go.Bar(name=nomes[v], y=tab.index, x=tab[v], orientation="h", marker_color=COR_VEREDITO[v]))
            
    fig.update_layout(title="Placar de coerência por evento (nº de hipóteses)", template=TEMPLATE, barmode="stack", height=max(340, 60 * len(tab) + 120), yaxis=dict(autorange="reversed"), xaxis=dict(title="Nº de hipóteses testadas", dtick=1), legend=dict(orientation="h", yanchor="top", y=-0.15, x=0), margin=dict(l=10, t=60))
    return fig

def modelo_conceitual_dot():
    """Retorna o código DOT (Graphviz) para o diagrama de fluxo."""
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

