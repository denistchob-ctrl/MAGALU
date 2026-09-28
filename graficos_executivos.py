"""
graficos_executivos.py
========================
Gráficos Plotly para o dashboard executivo, organizados por "ato" da
apresentação. Cada função devolve uma figura Plotly pronta para
st.plotly_chart(). Mantém a lógica de visualização separada das páginas
(paginas_executivas.py) e do acesso a dados (repositorio_dados.py).
"""

import re
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Paleta executiva (Magalu: azul + acentos)
CORES = {
    "receita": "#2E86AB",
    "ebitda": "#45B8AC",
    "margem": "#F18F01",
    "cotacao": "#1E6091",
    "volume": "#A9C5D3",
    "interesse": "#8C7AE6",
    "nota_ra": "#C98A4B",
    "lealdade": "#7A5C3A",
    "reclamacoes": "#D64550",
    "positivo": "#2E8B57",
    "negativo": "#C0392B",
    "neutro": "#7F8C8D",
}

TEMPLATE = "plotly_white"


# ======================================================================
# ATO 1 — Onde estamos (situação atual)
# ======================================================================

def ato1_receita_ebitda(df_receita, df_ebitda, df_margem):
    """
    Receita Líquida (barras) + EBITDA (linha) + Margem EBITDA % (linha, eixo 2).
    df_* : Series indexadas por período (trimestre).
    """
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    if not df_receita.empty:
        fig.add_trace(go.Bar(
            name="Receita Líquida",
            x=[str(i) for i in df_receita.index],
            y=df_receita.values,
            marker_color=CORES["receita"],
            opacity=0.85,
        ), secondary_y=False)

    if not df_ebitda.empty:
        fig.add_trace(go.Scatter(
            name="EBITDA",
            x=[str(i) for i in df_ebitda.index],
            y=df_ebitda.values,
            mode="lines+markers",
            line=dict(color=CORES["ebitda"], width=3),
        ), secondary_y=False)

    if not df_margem.empty:
        fig.add_trace(go.Scatter(
            name="Margem EBITDA (%)",
            x=[str(i) for i in df_margem.index],
            y=df_margem.values * 100,
            mode="lines+markers",
            line=dict(color=CORES["margem"], width=2, dash="dot"),
        ), secondary_y=True)

    fig.update_layout(
        title="Receita Líquida, EBITDA e Margem — evolução por trimestre",
        template=TEMPLATE,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        hovermode="x unified",
        height=500,
    )
    fig.update_yaxes(title_text="R$ milhões", secondary_y=False)
    fig.update_yaxes(title_text="Margem EBITDA (%)", secondary_y=True, ticksuffix="%")
    return fig

def ato1_cotacao_volume(serie_fechamento, serie_volume):
    """
    Cotação (linha, eixo 1) + Volume Financeiro (barras, eixo 2).
    As barras ficam num eixo separado porque o volume é ordens de
    magnitude maior que o preço — sem isso, o volume 'achata' o preço.
    """
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # --- Volume primeiro (fica atrás da linha) ---
    if serie_volume is not None and not serie_volume.empty:
        fig.add_trace(go.Bar(
            name="Volume Financeiro (R$ milhões)",
            x=serie_volume.index,
            y=serie_volume.values / 1000000, #em milhões
            marker_color="#115009",       # verde 
            opacity=0.75,                  # mais opaco
            yaxis="y2",                    # garante o eixo secundário
        ), secondary_y=True)

    # --- Cotação depois (fica na frente) ---
    if serie_fechamento is not None and not serie_fechamento.empty:
        fig.add_trace(go.Scatter(
            name="Fechamento (R$)",
            x=serie_fechamento.index,
            y=serie_fechamento.values,
            mode="lines",
            line=dict(color="#1E6091", width=2),   # azul escuro, contrasta com o volume
        ), secondary_y=False)

    fig.update_layout(
        title="Cotação da ação (MGLU3) e volume financeiro",
        template=TEMPLATE,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        hovermode="x unified",
        height=500,
        xaxis=dict(tickformat="%Y", tickangle=-45),
        bargap=0.1,                        # barras mais largas / menos espaço
    )
    fig.update_yaxes(
        title_text="Preço (R$)",
        secondary_y=False,
        range=[0, None],                   # começa em 0, sem forçar teto
    )
    fig.update_yaxes(
        title_text="Volume Financeiro",
        secondary_y=True,
        showgrid=False,                    # evita grid duplicado
    )
    return fig

# ======================================================================
# ATO 2 — Como o cliente nos vê (reputação)
# ======================================================================

def ato2_reputacao_ra(df_ra, empresa):
    """
    Reputação do Reclame Aqui (apenas RA, sem cruzar com Trends):
    Nota Média (barras, eixo 1) e % Voltariam a fazer negócio (linha, eixo 2).
    """
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    if df_ra is None or df_ra.empty:
        fig.update_layout(title=f"Reclame Aqui — {empresa} (sem dados)",
                          template=TEMPLATE)
        return fig

    periodos = [str(i) for i in df_ra.index]

    if "Nota Média" in df_ra.columns:
        fig.add_trace(go.Bar(
            name="Nota Média (0-10)",
            x=periodos, y=df_ra["Nota Média"].values,
            marker_color=CORES["nota_ra"],
        ), secondary_y=False)

    if "Voltariam a fazer negócio" in df_ra.columns:
        fig.add_trace(go.Scatter(
            name="Voltariam a fazer negócio (%)",
            x=periodos, y=df_ra["Voltariam a fazer negócio"].values * 100,
            mode="lines+markers",
            line=dict(color=CORES["lealdade"], width=2, dash="dot"),
        ), secondary_y=True)

    fig.update_layout(
        title=f"Reclame Aqui — {empresa.capitalize()} ({', '.join(periodos)})",
        template=TEMPLATE,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        hovermode="x unified",
        height=450,
    )
    fig.update_yaxes(title_text="Nota Média (0-10)",
                     secondary_y=False, range=[0, 10])
    fig.update_yaxes(title_text="% Voltariam a fazer negócio",
                     secondary_y=True, range=[0, 100], ticksuffix="%")
    return fig


def ato2_vendas_e_interesse(df_vendas, serie_trends):
    """
    Vendas Totais (barras trimestrais, em R$ milhões) × Interesse de busca
    (linha mensal, 0-100). A granularidade é diferente, mas o eixo X
    compartilhado (tempo) permite ver a relação.

    df_vendas: pandas Series indexada por trimestre ('1T18', '2T18', ...).
    serie_trends: pandas Series indexada por data (mensal).
    """
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # --- Vendas Totais (barras) ---
    if df_vendas is not None and not df_vendas.empty:
        # Converte '1T18' -> data de início do trimestre para alinhar com o eixo
        rotulos, valores = [], []
        for rotulo, valor in df_vendas.items():
            texto = str(rotulo)
            m = re.match(r'^(\d)T(\d{2})$', texto)
            if not m:
                continue
            tri = int(m.group(1))
            ano = 2000 + int(m.group(2))
            # Mês de início do trimestre: 1T=jan, 2T=abr, 3T=jul, 4T=out
            mes = 1 + (tri - 1) * 3
            rotulos.append(pd.Timestamp(year=ano, month=mes, day=1))
            valores.append(valor)

        if rotulos:
            fig.add_trace(go.Bar(
                name="Vendas Totais (R$ milhões)",
                x=rotulos,
                y=valores,
                marker_color=CORES["receita"],
                opacity=0.75,
            ), secondary_y=False)

    # --- Interesse de busca (linha) ---
    if serie_trends is not None and not serie_trends.empty:
        fig.add_trace(go.Scatter(
            name="Interesse de busca (mensal)",
            x=serie_trends.index,
            y=serie_trends.values,
            mode="lines",
            line=dict(color=CORES["interesse"], width=2),
        ), secondary_y=True)

    fig.update_layout(
        title="Vendas Totais × Interesse de busca (Google Trends)",
        template=TEMPLATE,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        hovermode="x unified",
        height=500,
        xaxis=dict(
            tickformat="%m/%Y",   # mostra mês/ano — melhor quando filtra 1 ano
            tickangle=-45,
        ),
    )

    fig.update_yaxes(title_text="Vendas (R$ milhões)", secondary_y=False)
    fig.update_yaxes(title_text="Interesse de busca (0-100)", secondary_y=True)
    return fig

def ato2_top_problemas(df_problemas, empresa, top_n=5):
    """Top N problemas do Reclame Aqui — barras horizontais."""
    fig = go.Figure()
    if df_problemas is None or df_problemas.empty:
        fig.update_layout(title=f"Top problemas — {empresa} (sem dados)", template=TEMPLATE)
        return fig

    coluna_qtd = df_problemas.columns[-1]
    coluna_label = df_problemas.columns[0]
    top = df_problemas.sort_values(coluna_qtd, ascending=False).head(top_n).iloc[::-1]

    fig.add_trace(go.Bar(
        x=top[coluna_qtd], y=top[coluna_label], orientation="h",
        marker_color=CORES["reclamacoes"],
        text=top[coluna_qtd], textposition="outside",
    ))
    fig.update_layout(
        title=f"Top {top_n} problemas — {empresa.capitalize()}",
        xaxis_title="Reclamações",
        template=TEMPLATE,
        height=max(350, 30 * len(top)),
    )
    return fig


# ======================================================================
# ATO 3 — Onde a marca é forte/fraca (geografia)
# ======================================================================

def ato3_mapa_interesse(serie_regiao, ano_label="todos os anos"):
    """
    Mapa coroplético do Brasil com o interesse por estado.
    serie_regiao: Series indexada pelo nome do estado.
    """
    fig = go.Figure()
    if serie_regiao is None or serie_regiao.empty:
        fig.update_layout(title=f"Interesse por região — {ano_label} (sem dados)",
                          template=TEMPLATE)
        return fig

    df = serie_regiao.reset_index()
    df.columns = ["Estado", "Quantidade"]

    fig.add_trace(go.Choropleth(
        geojson="https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/brazil-states.geojson",
        locations=df["Estado"],
        z=df["Quantidade"],
        locationmode="geojson-id",
        featureidkey="properties.name",
        colorscale="YlGnBu",
        colorbar=dict(title="Interesse"),
        marker_line_color="white",
        marker_line_width=0.5,
    ))
    fig.update_geos(
        fitbounds="locations",
        visible=False,
        showcountries=False,
        showcoastlines=False,
        showland=False,
    )
    fig.update_layout(
        title=f"Interesse de busca por estado — {ano_label}",
        template=TEMPLATE,
        height=550,
        margin=dict(l=0, r=0, t=40, b=0),
    )
    return fig


def ato3_heatmap_ano_regiao(matriz):
    """Heatmap Ano × Região do interesse de busca."""
    fig = go.Figure()
    if matriz is None or matriz.empty:
        fig.update_layout(title="Heatmap Ano × Região (sem dados)", template=TEMPLATE)
        return fig

    fig.add_trace(go.Heatmap(
        z=matriz.values,
        x=matriz.columns.tolist(),
        y=matriz.index.tolist(),
        colorscale="YlGnBu",
        colorbar=dict(title="Interesse"),
    ))
    fig.update_layout(
        title="Interesse de busca — Ano × Região",
        xaxis_title="Região",
        yaxis_title="Ano",
        template=TEMPLATE,
        height=500,
        xaxis=dict(tickangle=-45),
    )
    return fig


# ======================================================================
# ATO 4 — O que estamos fazendo (investimentos)
# ======================================================================

def ato4_investimentos_por_categoria(df_investimentos, df_margem_ebitda):
    """
    Investimentos por categoria (barras empilhadas) + Margem EBITDA (linha, eixo 2).
    df_investimentos: DataFrame com colunas = categorias, índice = período.
    """
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    if df_investimentos is not None and not df_investimentos.empty:
        for coluna in df_investimentos.columns:
            fig.add_trace(go.Bar(
                name=coluna,
                x=[str(i) for i in df_investimentos.index],
                y=df_investimentos[coluna].values,
            ), secondary_y=False)

    if df_margem_ebitda is not None and not df_margem_ebitda.empty:
        fig.add_trace(go.Scatter(
            name="Margem EBITDA (%)",
            x=[str(i) for i in df_margem_ebitda.index],
            y=df_margem_ebitda.values * 100,
            mode="lines+markers",
            line=dict(color=CORES["margem"], width=3),
        ), secondary_y=True)

    fig.update_layout(
        title="Investimentos por categoria × Margem EBITDA",
        template=TEMPLATE,
        barmode="stack",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        hovermode="x unified",
        height=500,
    )
    fig.update_yaxes(title_text="Investimentos (R$ milhões)", secondary_y=False)
    fig.update_yaxes(title_text="Margem EBITDA (%)", secondary_y=True, ticksuffix="%")
    return fig


def ato4_fluxo_caixa(df_fluxo_operacional, df_fluxo_investimento, df_fluxo_financiamento):
    """
    Fluxo de Caixa: 3 atividades (barras agrupadas).
    """
    fig = go.Figure()

    periodos = None
    for nome, serie, cor in [
        ("Operacional", df_fluxo_operacional, CORES["positivo"]),
        ("Investimento", df_fluxo_investimento, CORES["cotacao"]),
        ("Financiamento", df_fluxo_financiamento, CORES["reclamacoes"]),
    ]:
        if serie is not None and not serie.empty:
            periodos = [str(i) for i in serie.index]
            fig.add_trace(go.Bar(
                name=nome,
                x=periodos,
                y=serie.values,
                marker_color=cor,
            ))

    fig.update_layout(
        title="Fluxo de Caixa por atividade",
        template=TEMPLATE,
        barmode="group",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        hovermode="x unified",
        height=500,
    )
    fig.update_yaxes(title_text="R$ milhões")
    return fig


# ======================================================================
# ATO 5 — O que fazer (recomendações) — o gráfico "tesoura"
# ======================================================================

def ato5_tesoura_receita_interesse(df_receita_anual, serie_interesse_anual):
    """
    O gráfico mais impactante: Receita (barras) crescendo × Interesse
    de busca (linha) caindo. A 'tesoura' que mostra o divórcio entre
    crescimento financeiro e relevância de marca.

    O eixo X é tratado como NUMÉRICO (ano inteiro) para garantir a
    ordenação cronológica correta e o alinhamento das duas séries,
    mesmo quando elas cobrem intervalos diferentes (Receita começa em
    2018; Google Trends começa em 2004).
    """
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # --- Receita Líquida (barras) ---
    if df_receita_anual is not None and not df_receita_anual.empty:
        anos_receita = [int(a) for a in df_receita_anual.index]
        fig.add_trace(go.Bar(
            name="Receita Líquida (R$ bi)",
            x=anos_receita,
            y=df_receita_anual.values / 1000,  # converte para bilhões
            marker_color=CORES["receita"],
            opacity=0.85,
        ), secondary_y=False)

    # --- Interesse de busca (linha) ---
    if serie_interesse_anual is not None and not serie_interesse_anual.empty:
        anos_interesse = [int(a) for a in serie_interesse_anual.index]
        fig.add_trace(go.Scatter(
            name="Interesse de busca (média anual)",
            x=anos_interesse,
            y=serie_interesse_anual.values,
            mode="lines+markers",
            line=dict(color=CORES["interesse"], width=3),
            marker=dict(size=8),
        ), secondary_y=True)

    fig.update_layout(
        title="A tesoura: Receita cresce, interesse de busca cai",
        template=TEMPLATE,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        hovermode="x unified",
        height=550,
        # Força o eixo X a ser tratado como numérico, com ticks inteiros
        xaxis=dict(
            type="linear",
            tickmode="linear",
            dtick=1,
            tickformat="d",
            title="Ano",
        ),
    )
    fig.update_yaxes(title_text="Receita Líquida (R$ bilhões)", secondary_y=False)
    fig.update_yaxes(title_text="Interesse de busca (0-100)", secondary_y=True)
    return fig

def ato5_scorecard(df_scorecard):
    """
    Scorecard final com indicadores-chave e variação vs. período anterior.
    df_scorecard: DataFrame com colunas ['Indicador', 'Valor', 'Variacao_Pct', 'Status'].
    Status: 'positivo', 'negativo', 'neutro'.
    """
    fig = go.Figure()

    cores = {
        "positivo": CORES["positivo"],
        "negativo": CORES["negativo"],
        "neutro": CORES["neutro"],
    }

    if df_scorecard is None or df_scorecard.empty:
        fig.update_layout(title="Scorecard (sem dados)", template=TEMPLATE)
        return fig

    fig.add_trace(go.Table(
        header=dict(
            values=["Indicador", "Valor", "Variação", "Status"],
            fill_color="#2E86AB",
            font=dict(color="white", size=13),
            align="left",
            height=35,
        ),
        cells=dict(
            values=[
                df_scorecard["Indicador"],
                df_scorecard["Valor"],
                df_scorecard["Variacao_Pct"],
                df_scorecard["Status"].apply(
                    lambda s: {"positivo": "▲", "negativo": "▼", "neutro": "●"}.get(s, "●")
                ),
            ],
            fill_color=[
                ["#F8F9FA"] * len(df_scorecard),
                ["#F8F9FA"] * len(df_scorecard),
                ["#F8F9FA"] * len(df_scorecard),
                df_scorecard["Status"].apply(lambda s: cores.get(s, "#F8F9FA")).tolist(),
            ],
            font=dict(color=["#212529"] * 3 + ["white"], size=12),
            align="left",
            height=30,
        ),
    ))
    fig.update_layout(
        title="Scorecard executivo — indicadores-chave",
        template=TEMPLATE,
        height=max(300, 40 * len(df_scorecard) + 80),
    )
    return fig

# ======================================================================
# GRÁFICOS ADICIONAIS — para as 5 páginas executivas
# ======================================================================

def grafico_temporal_multilinhas(df, titulo, yaxis_titulo, cores=None):
    """
    Gráfico temporal genérico com múltiplas séries (linhas). Útil para
    comparar indicadores selecionados pelo usuário.
    df: DataFrame com uma coluna por indicador e índice = período.
    """
    fig = go.Figure()
    if df is None or df.empty:
        fig.update_layout(title=f"{titulo} (sem dados)", template=TEMPLATE)
        return fig

    for coluna in df.columns:
        fig.add_trace(go.Scatter(
            name=coluna,
            x=[str(i) for i in df.index],
            y=df[coluna].values,
            mode="lines+markers",
            line=dict(width=2),
        ))

    fig.update_layout(
        title=titulo,
        template=TEMPLATE,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        hovermode="x unified",
        height=500,
    )
    fig.update_yaxes(title_text=yaxis_titulo)
    return fig


def grafico_barras_linha(x, serie_barra, serie_linha,
                         nome_barra, nome_linha,
                         titulo, yaxis_barra, yaxis_linha):
    """Gráfico combinado barras + linha em dois eixos Y."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    if serie_barra is not None and not serie_barra.empty:
        fig.add_trace(go.Bar(
            name=nome_barra,
            x=[str(i) for i in serie_barra.index],
            y=serie_barra.values,
            marker_color=CORES["receita"],
            opacity=0.85,
        ), secondary_y=False)

    if serie_linha is not None and not serie_linha.empty:
        fig.add_trace(go.Scatter(
            name=nome_linha,
            x=[str(i) for i in serie_linha.index],
            y=serie_linha.values * 100 if "margem" in nome_linha.lower() else serie_linha.values,
            mode="lines+markers",
            line=dict(color=CORES["margem"], width=2, dash="dot"),
        ), secondary_y=True)

    fig.update_layout(
        title=titulo,
        template=TEMPLATE,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        hovermode="x unified",
        height=500,
    )
    fig.update_yaxes(title_text=yaxis_barra, secondary_y=False)
    fig.update_yaxes(title_text=yaxis_linha, secondary_y=True)
    return fig


def grafico_area_mix(df_mix, titulo):
    """
    Gráfico de área empilhada para mostrar a mudança do mix de canais.
    df_mix: DataFrame com colunas ['Lojas Físicas', 'E-commerce 1P', 'Marketplace 3P'].
    """
    fig = go.Figure()
    if df_mix is None or df_mix.empty:
        fig.update_layout(title=f"{titulo} (sem dados)", template=TEMPLATE)
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
        title=titulo,
        template=TEMPLATE,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        hovermode="x unified",
        height=500,
    )
    fig.update_yaxes(title_text="Vendas (R$ milhões)")
    return fig


def grafico_base_100(df_base100, titulo="Base 100 — comparação de trajetórias"):
    """
    Gráfico de linhas comparando séries na base 100.
    df_base100: DataFrame com uma coluna por série, índice = período.
    """
    fig = go.Figure()
    if df_base100 is None or df_base100.empty:
        fig.update_layout(title=f"{titulo} (sem dados)", template=TEMPLATE)
        return fig

    for coluna in df_base100.columns:
        fig.add_trace(go.Scatter(
            name=coluna,
            x=[str(i) for i in df_base100.index],
            y=df_base100[coluna].values,
            mode="lines+markers",
            line=dict(width=2),
        ))

    # Linha de referência em 100
    fig.add_hline(y=100, line_dash="dash", line_color="#999999",
                  annotation_text="Base 100", annotation_position="right")

    fig.update_layout(
        title=titulo,
        template=TEMPLATE,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        hovermode="x unified",
        height=500,
    )
    fig.update_yaxes(title_text="Índice (base 100)")
    return fig


def grafico_dispersao(serie_x, serie_y, nome_x, nome_y,
                      r=None, n=None, titulo=None):
    """
    Gráfico de dispersão com linha de tendência (se n >= mínimo) e
    anotação de correlação.
    """
    fig = go.Figure()
    if serie_x is None or serie_y is None:
        fig.update_layout(title="Dispersão (sem dados)", template=TEMPLATE)
        return fig

    df = pd.DataFrame({"x": serie_x, "y": serie_y}).dropna()
    if df.empty:
        fig.update_layout(title="Dispersão (sem dados alinhados)", template=TEMPLATE)
        return fig

    fig.add_trace(go.Scatter(
        x=df["x"], y=df["y"],
        mode="markers",
        marker=dict(size=8, color=CORES["secundaria"]),
        name="Observações",
        text=[str(i) for i in df.index],
    ))

    # Linha de tendência (regressão linear simples) se n >= mínimo
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
    anotacao += f" · n = {n}" if n else ""

    fig.update_layout(
        title=titulo or f"Dispersão: {nome_x} × {nome_y}",
        template=TEMPLATE,
        xaxis_title=nome_x,
        yaxis_title=nome_y,
        height=500,
        annotations=[dict(
            text=anotacao,
            xref="paper", yref="paper",
            x=0.02, y=0.98, showarrow=False,
            bgcolor="rgba(255,255,255,0.8)",
            bordercolor="#cccccc", borderwidth=1,
        )],
    )
    return fig