"""
graficos.py
=============
Fábrica de gráficos do dashboard, um método por fonte de dados. Mantém a
lógica de visualização separada das páginas (paginas.py) e do acesso a
dados (repositorio_dados.py) — cada camada com uma única responsabilidade.

Todos os métodos devolvem uma figura Plotly pronta para st.plotly_chart().
"""

import plotly.express as px
import plotly.graph_objects as go

CORES = {
    "dre": "#2E86AB",
    "cotacao": "#45B8AC",
    "reclame_aqui": "#C98A4B",
    "trends": "#8C7AE6",
}


class FabricaGraficos:
    """Constrói as figuras Plotly exibidas no dashboard."""

    # ------------------------------------------------------------------
    # DRE
    # ------------------------------------------------------------------
    @staticmethod
    def dre_trimestral(serie, indicador, ano):
        """Gráfico de barras do indicador de DRE por trimestre, em um ano."""
        fig = go.Figure()
        if serie.empty:
            fig.update_layout(title=f"{indicador} — {ano} (sem dados)")
            return fig

        fig.add_trace(go.Bar(
            x=list(serie.index), y=serie.values,
            marker_color=CORES["dre"],
        ))
        fig.update_layout(
            title=f"{indicador} por trimestre — {ano}",
            xaxis_title="Trimestre",
            yaxis_title=f"{indicador} (R$ milhões)",
            template="plotly_white",
        )
        return fig

    # ------------------------------------------------------------------
    # Cotações
    # ------------------------------------------------------------------
    @staticmethod
    def cotacao_diaria(serie, ano, coluna="Fechamento"):
        """Gráfico de linha da cotação diária da ação, em um ano."""
        fig = go.Figure()
        if serie.empty:
            fig.update_layout(title=f"Cotação — {coluna} — {ano} (sem dados)")
            return fig

        fig.add_trace(go.Scatter(
            x=serie.index, y=serie.values, mode="lines",
            line=dict(color=CORES["cotacao"], width=2),
        ))
        fig.update_layout(
            title=f"Cotação da ação — {coluna} — {ano}",
            xaxis_title="Data",
            yaxis_title="R$",
            template="plotly_white",
        )
        return fig

    # ------------------------------------------------------------------
    # Reclame Aqui
    # ------------------------------------------------------------------
    @staticmethod
    def reclame_aqui_desempenho(df, empresa, ano):
        """Gráfico com as principais métricas de desempenho do Reclame Aqui
        de uma empresa em um ano (ou período disponível mais próximo):
        Nota Média (0-10, eixo esquerdo) e % que voltariam a fazer negócio
        (eixo direito) — em eixos separados por terem escalas diferentes."""
        fig = go.Figure()
        if df.empty:
            fig.update_layout(title=f"Reclame Aqui — {empresa} (sem dados)")
            return fig

        periodos = [str(i) for i in df.index]

        if "Nota Média" in df.columns:
            fig.add_trace(go.Bar(
                name="Nota Média (0-10)",
                x=periodos, y=df["Nota Média"],
                marker_color=CORES["reclame_aqui"],
            ))
        if "Voltariam a fazer negócio" in df.columns:
            fig.add_trace(go.Scatter(
                name="Voltariam a fazer negócio (%)",
                x=periodos, y=df["Voltariam a fazer negócio"] * 100,
                mode="lines+markers", yaxis="y2",
                line=dict(color="#7A5C3A", width=2),
            ))

        fig.update_layout(
            title=f"Reclame Aqui — {empresa.capitalize()} ({', '.join(periodos)})",
            xaxis_title="Período",
            yaxis=dict(title="Nota Média (0-10)", range=[0, 10]),
            yaxis2=dict(title="Voltariam a fazer negócio (%)",
                        overlaying="y", side="right", range=[0, 100]),
            template="plotly_white",
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        return fig

    @staticmethod
    def reclame_aqui_top_problemas(df_problemas, empresa, top_n=10):
        """Gráfico de barras horizontais com os problemas mais reportados de
        uma empresa no Reclame Aqui (sem filtro de ano — o relatório de
        'problemas' do RA não é quebrado por ano)."""
        fig = go.Figure()
        if df_problemas is None or df_problemas.empty:
            fig.update_layout(title=f"Principais problemas — {empresa} (sem dados)")
            return fig

        coluna_qtd = df_problemas.columns[-1]
        coluna_label = df_problemas.columns[0]
        top = df_problemas.sort_values(coluna_qtd, ascending=False).head(top_n).iloc[::-1]

        fig.add_trace(go.Bar(
            x=top[coluna_qtd], y=top[coluna_label], orientation="h",
            marker_color=CORES["reclame_aqui"],
        ))
        fig.update_layout(
            title=f"Principais problemas reportados — {empresa.capitalize()}",
            xaxis_title="Quantidade de reclamações",
            template="plotly_white",
        )
        return fig

    # ------------------------------------------------------------------
    # Google Trends
    # ------------------------------------------------------------------
    @staticmethod
    def google_trends_mensal(df, ano):
        """Gráfico de linha do interesse de busca mensal (Google Trends), em um ano."""
        fig = go.Figure()
        if df.empty:
            fig.update_layout(title=f"Google Trends — {ano} (sem dados)")
            return fig

        fig.add_trace(go.Scatter(
            x=df["Data"], y=df["Quantidade"], mode="lines+markers",
            line=dict(color=CORES["trends"], width=2),
        ))
        fig.update_layout(
            title=f"Interesse de busca (Google Trends) — {ano}",
            xaxis_title="Mês",
            yaxis_title="Índice de interesse",
            template="plotly_white",
        )
        return fig

    @staticmethod
    def google_trends_regiao_barras(serie, ano, top_n=15):
        """Ranking de interesse por região (barras horizontais) em um ano."""
        fig = go.Figure()
        if serie.empty:
            fig.update_layout(title=f"Google Trends por região — {ano} (sem dados)")
            return fig

        serie = serie.head(top_n).iloc[::-1]
        fig.add_trace(go.Bar(
            x=serie.values, y=serie.index, orientation="h",
            marker_color=CORES["trends"],
        ))
        fig.update_layout(
            title=f"Interesse de busca por região — {ano} (Top {top_n})",
            xaxis_title="Índice de interesse (0-100)",
            template="plotly_white",
            height=max(400, 25 * len(serie)),
        )
        return fig

    @staticmethod
    def google_trends_regiao_agregada(serie, top_n=15):
        """Ranking de regiões pelo interesse agregado (soma de todos os anos)."""
        fig = go.Figure()
        if serie.empty:
            fig.update_layout(title="Google Trends — regiões (agregado) — sem dados")
            return fig

        serie = serie.sort_values(ascending=False).head(top_n).iloc[::-1]
        fig.add_trace(go.Bar(
            x=serie.values, y=serie.index, orientation="h",
            marker_color=CORES["trends"],
        ))
        fig.update_layout(
            title=f"Interesse de busca por região — agregado histórico (Top {top_n})",
            xaxis_title="Soma dos índices anuais (0–100 por ano)",
            template="plotly_white",
            height=max(400, 25 * len(serie)),
        )
        return fig

    @staticmethod
    def google_trends_heatmap_ano_regiao(matriz):
        """Heatmap Ano × Região do interesse de busca."""
        fig = go.Figure()
        if matriz is None or matriz.empty:
            fig.update_layout(title="Heatmap Ano × Região (sem dados)")
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
            template="plotly_white",
            height=500,
            xaxis=dict(tickangle=-45),
        )
        return fig