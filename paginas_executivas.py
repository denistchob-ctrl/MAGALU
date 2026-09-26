"""
paginas_executivas.py
=======================
Páginas do dashboard executivo, uma por "ato" da apresentação. Cada página
tem um seletor de período (com opção "Todos") e renderiza os gráficos
correspondentes. Mantém a lógica de apresentação separada dos gráficos
(graficos_executivos.py) e do acesso a dados (repositorio_dados.py).
"""

import pandas as pd
import streamlit as st

from graficos_executivos import (
    ato1_receita_ebitda,
    ato1_cotacao_volume,
    ato2_reputacao_e_interesse,
    ato2_top_problemas,
    ato3_mapa_interesse,
    ato3_heatmap_ano_regiao,
    ato4_investimentos_por_categoria,
    ato4_fluxo_caixa,
    ato5_tesoura_receita_interesse,
    ato5_scorecard,
)

OPCAO_TODOS = "Todos"


# ======================================================================
# Utilitários de filtro
# ======================================================================

def _seletor_ano(repositorio, key):
    """Seletor de ano com opção 'Todos'. Devolve o ano escolhido ou None."""
    anos = repositorio.anos_disponiveis()
    opcoes = [OPCAO_TODOS] + [str(a) for a in anos]
    escolha = st.sidebar.selectbox("Ano", opcoes, index=0, key=key)
    return None if escolha == OPCAO_TODOS else int(escolha)


def _seletor_mes(key):
    """Seletor de mês (1-12) com opção 'Todos'. Devolve o mês ou None."""
    meses = [OPCAO_TODOS] + [f"{m:02d}" for m in range(1, 13)]
    escolha = st.sidebar.selectbox("Mês", meses, index=0, key=key)
    return None if escolha == OPCAO_TODOS else int(escolha)


def _filtrar_serie_por_ano_mes(serie, ano, mes=None):
    """Filtra uma Series indexada por data (ou por rótulo trimestral)."""
    if serie is None or serie.empty:
        return serie
    if ano is None and mes is None:
        return serie

    if isinstance(serie.index, pd.DatetimeIndex):
        mask = pd.Series(True, index=serie.index)
        if ano is not None:
            mask &= (serie.index.year == ano)
        if mes is not None:
            mask &= (serie.index.month == mes)
        return serie[mask]

    # Índices textuais (ex.: '1T23'): filtra por sufixo do ano
    if ano is not None:
        sufixo = f"{ano % 100:02d}"
        return serie[[c for c in serie.index if str(c).endswith(sufixo)]]
    return serie


# ======================================================================
# Página 0 — Abertura
# ======================================================================

class PaginaAbertura:
    def render(self, repositorio):
        st.title("📊 Dashboard Executivo — Magazine Luiza")
        st.markdown(
            """
            Esta apresentação está organizada em **5 atos**, cada um respondendo
            a uma pergunta-chave da diretoria:

            1. **Onde estamos** — situação financeira e de mercado.
            2. **Como o cliente nos vê** — reputação e relevância de marca.
            3. **Onde a marca é forte/fraca** — geografia do interesse.
            4. **O que estamos fazendo** — investimentos e fluxo de caixa.
            5. **O que fazer** — síntese e recomendações.

            Use o menu à esquerda para navegar entre os atos. Em cada página,
            o seletor de período permite filtrar os dados (opção **"Todos"**
            para ver o histórico completo).
            """
        )
        st.info(
            "💡 **Dica:** comece pelo Ato 5 (síntese) se quiser a conclusão "
            "primeiro. Os outros atos detalham o caminho até ela."
        )


# ======================================================================
# Ato 1 — Onde estamos
# ======================================================================

class PaginaAto1:
    def render(self, repositorio):
        st.title("Ato 1 — Onde estamos")
        st.caption("Situação financeira e de mercado do Magazine Luiza")

        ano = _seletor_ano(repositorio, key="ato1_ano")

        # --- Receita, EBITDA e Margem ---
        st.subheader("1.1 Receita, EBITDA e Margem")
        serie_receita = _serie_dre(repositorio, "1. Indicadores", "Receita Líquida Total", ano)
        serie_ebitda = _serie_dre(repositorio, "1. Indicadores", "EBITDA", ano)
        serie_margem = _serie_dre(repositorio, "1. Indicadores", "Margem EBITDA", ano)

        fig = ato1_receita_ebitda(serie_receita, serie_ebitda, serie_margem)
        st.plotly_chart(fig, width="stretch")

        with st.expander("Ver valores"):
            st.dataframe(pd.DataFrame({
                "Receita Líquida": serie_receita,
                "EBITDA": serie_ebitda,
                "Margem EBITDA": serie_margem,
            }))

        # --- Cotação e Volume ---
        st.subheader("1.2 Cotação da ação e volume")
        cot = repositorio.cotacao
        if cot is not None:
            serie_fech = _filtrar_serie_por_ano_mes(cot.get_serie("Fechamento"), ano)
            serie_vol = _filtrar_serie_por_ano_mes(cot.get_serie("Volume_Financeiro"), ano)
            fig2 = ato1_cotacao_volume(serie_fech, serie_vol)
            st.plotly_chart(fig2, width="stretch")
        else:
            st.info("Dados de cotação não disponíveis.")


# ======================================================================
# Ato 2 — Como o cliente nos vê
# ======================================================================

class PaginaAto2:
    def render(self, repositorio):
        st.title("Ato 2 — Como o cliente nos vê")
        st.caption("Reputação (Reclame Aqui) × Relevância de marca (Google Trends)")

        col1, col2 = st.sidebar.columns(2)
        ano = _seletor_ano(repositorio, key="ato2_ano")
        mes = _seletor_mes(key="ato2_mes")

        # --- Reputação + Interesse ---
        st.subheader("2.1 Reputação × Interesse de busca")
        ra = repositorio.reclame_aqui
        df_ra = ra.desempenho("online") if ra is not None else None

        trends = repositorio.trends
        serie_trends = None
        if trends is not None and not trends.serie_temporal.empty:
            serie_trends = trends.serie_temporal.set_index("Data")["Quantidade"]
            serie_trends = _filtrar_serie_por_ano_mes(serie_trends, ano, mes)

        fig = ato2_reputacao_e_interesse(df_ra, serie_trends)
        st.plotly_chart(fig, width="stretch")

        # --- Top problemas ---
        st.subheader("2.2 Top problemas por empresa")
        if ra is not None:
            empresa = st.selectbox(
                "Empresa",
                ra.listar_empresas(),
                key="ato2_empresa",
            )
            df_prob = ra.problemas(empresa)
            fig2 = ato2_top_problemas(df_prob, empresa, top_n=5)
            st.plotly_chart(fig2, width="stretch")
        else:
            st.info("Dados do Reclame Aqui não disponíveis.")


# ======================================================================
# Ato 3 — Onde a marca é forte/fraca
# ======================================================================

class PaginaAto3:
    def render(self, repositorio):
        st.title("Ato 3 — Onde a marca é forte/fraca")
        st.caption("Geografia do interesse de busca")

        ano = _seletor_ano(repositorio, key="ato3_ano")

        ga = getattr(repositorio, "ga_anual", None)

        # --- Mapa ---
        st.subheader("3.1 Mapa de interesse por estado")
        if ga is not None and not ga.df.empty:
            if ano is not None:
                serie_regiao = repositorio.trends_regiao_por_ano(ano)
                label = str(ano)
            else:
                serie_regiao = repositorio.trends_regiao_agregada(como="soma")
                label = "soma de todos os anos"
            fig = ato3_mapa_interesse(serie_regiao, label)
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("Dados anuais por região não disponíveis.")

        # --- Heatmap Ano × Região ---
        st.subheader("3.2 Evolução Ano × Região")
        if ga is not None and not ga.df.empty:
            matriz = repositorio.trends_regiao_matriz()
            fig2 = ato3_heatmap_ano_regiao(matriz)
            st.plotly_chart(fig2, width="stretch")
        else:
            st.info("Matriz Ano × Região não disponível.")


# ======================================================================
# Ato 4 — O que estamos fazendo
# ======================================================================

class PaginaAto4:
    def render(self, repositorio):
        st.title("Ato 4 — O que estamos fazendo")
        st.caption("Investimentos e fluxo de caixa")

        ano = _seletor_ano(repositorio, key="ato4_ano")

        # --- Investimentos × Margem ---
        st.subheader("4.1 Investimentos por categoria × Margem EBITDA")
        guia_inv = "10.Investimentos"
        df_inv = _df_dre_por_ano(repositorio, guia_inv, ano)
        serie_margem = _serie_dre(repositorio, "1. Indicadores", "Margem EBITDA", ano)

        if df_inv is not None and not df_inv.empty:
            fig = ato4_investimentos_por_categoria(df_inv.T, serie_margem)
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("Dados de investimentos não disponíveis.")

        # --- Fluxo de Caixa ---
        st.subheader("4.2 Fluxo de caixa por atividade")
        guia_fc = "7. Fluxo de Caixa Gerencial"
        df_oper = _serie_dre(repositorio, guia_fc, "Fluxo de Caixa das Atividades Operacionais", ano)
        df_invest = _serie_dre(repositorio, guia_fc, "Fluxo de Caixa das Atividades de Investimentos", ano)
        df_financ = _serie_dre(repositorio, guia_fc, "Fluxo de Caixa das Atividades de Financiamentos", ano)

        if any(s is not None and not s.empty for s in [df_oper, df_invest, df_financ]):
            fig2 = ato4_fluxo_caixa(df_oper, df_invest, df_financ)
            st.plotly_chart(fig2, width="stretch")
        else:
            st.info("Dados de fluxo de caixa não disponíveis.")


# ======================================================================
# Ato 5 — O que fazer
# ======================================================================

class PaginaAto5:
    def render(self, repositorio):
        st.title("Ato 5 — O que fazer")
        st.caption("Síntese executiva e recomendações")

        # --- A tesoura ---
        st.subheader("5.1 A tesoura: Receita cresce, interesse de busca cai")

        # Receita anual (soma dos trimestres por ano)
        serie_receita = _serie_dre(repositorio, "1. Indicadores", "Receita Líquida Total", None)
        receita_anual = _agregar_por_ano(serie_receita)

        # Interesse anual (média por ano do Trends)
        trends = repositorio.trends
        interesse_anual = None
        if trends is not None and not trends.serie_temporal.empty:
            df_t = trends.serie_temporal.copy()
            interesse_anual = df_t.groupby("Ano")["Quantidade"].mean()

        if receita_anual is not None and not receita_anual.empty:
            fig = ato5_tesoura_receita_interesse(receita_anual, interesse_anual)
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("Dados de receita anual não disponíveis.")

        # --- Scorecard ---
        st.subheader("5.2 Scorecard executivo")
        df_score = _montar_scorecard(repositorio)
        if df_score is not None and not df_score.empty:
            fig2 = ato5_scorecard(df_score)
            st.plotly_chart(fig2, width="stretch")
        else:
            st.info("Não foi possível montar o scorecard.")

        # --- Recomendações ---
        st.subheader("5.3 Recomendações")
        st.markdown(
            """
            1. **Reconquistar relevância de marca** — investir em marketing de
               massa, não apenas em performance digital.
            2. **Investigar regiões com alto interesse e alta reclamação** —
               oportunidade de ganho rápido.
            3. **Reavaliar mix de canais** — decidir se lojas físicas continuam
               ou viram hubs logísticos.
            4. **Atacar os top problemas do Reclame Aqui** — cada ponto de nota
               recuperado tem correlação com a cotação.
            5. **Reposicionar a marca para o público geral**, não apenas o digital.
            """
        )


# ======================================================================
# Helpers de acesso a dados do DRE
# ======================================================================

def _serie_dre(repositorio, guia, indicador, ano):
    """Extrai uma série do DRE filtrando por ano (ou todos se ano=None)."""
    if repositorio.loader_dre is None:
        return pd.Series(dtype=float)
    try:
        serie = repositorio.loader_dre.get_series(guia, indicador)
    except KeyError:
        return pd.Series(dtype=float)
    if ano is None:
        return serie
    sufixo = f"{ano % 100:02d}"
    return serie[[c for c in serie.index if str(c).endswith(sufixo)]]


def _df_dre_por_ano(repositorio, guia, ano):
    """Extrai uma guia inteira do DRE filtrando por ano."""
    if repositorio.loader_dre is None:
        return pd.DataFrame()
    try:
        df = repositorio.loader_dre.get_sheet_df(guia)
    except KeyError:
        return pd.DataFrame()
    if ano is None:
        return df
    sufixo = f"{ano % 100:02d}"
    cols = [c for c in df.columns if str(c).endswith(sufixo)]
    return df[cols]


def _agregar_por_ano(serie):
    """Agrega uma série trimestral em anual (soma por ano)."""
    if serie is None or serie.empty:
        return pd.Series(dtype=float)

    dados = {}
    for rotulo, valor in serie.items():
        texto = str(rotulo)
        # Extrai o ano de rótulos como '1T23', '01/03/2023' etc.
        ano = None
        if len(texto) >= 2 and texto[-2:].isdigit():
            ano = 2000 + int(texto[-2:])
        elif "/" in texto:
            partes = texto.split("/")
            if len(partes) == 3 and partes[-1].isdigit():
                ano = int(partes[-1])
        if ano is not None:
            dados.setdefault(ano, 0)
            dados[ano] += valor if pd.notna(valor) else 0

    if not dados:
        return pd.Series(dtype=float)
    return pd.Series(dados).sort_index()


def _montar_scorecard(repositorio):
    """Monta o scorecard com indicadores-chave e variação vs. período anterior."""
    linhas = []

    # Receita
    serie = _serie_dre(repositorio, "1. Indicadores", "Receita Líquida Total", None)
    if not serie.empty and len(serie) >= 2:
        atual, anterior = serie.iloc[-1], serie.iloc[-2]
        var = (atual - anterior) / abs(anterior) * 100 if anterior else 0
        linhas.append({
            "Indicador": "Receita Líquida (últ. tri)",
            "Valor": f"R$ {atual:,.0f} mi",
            "Variacao_Pct": f"{var:+.1f}%",
            "Status": "positivo" if var > 0 else "negativo" if var < 0 else "neutro",
        })

    # Margem EBITDA
    serie = _serie_dre(repositorio, "1. Indicadores", "Margem EBITDA", None)
    if not serie.empty:
        atual = serie.iloc[-1] * 100
        linhas.append({
            "Indicador": "Margem EBITDA (últ. tri)",
            "Valor": f"{atual:.1f}%",
            "Variacao_Pct": "—",
            "Status": "positivo" if atual > 10 else "negativo" if atual < 5 else "neutro",
        })

    # Nota RA
    ra = repositorio.reclame_aqui
    if ra is not None:
        try:
            df_ra = ra.desempenho("online")
            if not df_ra.empty and "Nota Média" in df_ra.columns:
                atual = df_ra["Nota Média"].iloc[-1]
                linhas.append({
                    "Indicador": "Nota Média (RA)",
                    "Valor": f"{atual:.1f}",
                    "Variacao_Pct": "—",
                    "Status": "positivo" if atual >= 7 else "negativo" if atual < 6 else "neutro",
                })
        except Exception:
            pass

    # Interesse de busca
    trends = repositorio.trends
    if trends is not None and not trends.serie_temporal.empty:
        atual = trends.serie_temporal["Quantidade"].iloc[-1]
        anterior = trends.serie_temporal["Quantidade"].iloc[-12] if len(trends.serie_temporal) >= 12 else atual
        var = (atual - anterior) / abs(anterior) * 100 if anterior else 0
        linhas.append({
            "Indicador": "Interesse de busca (últ. mês)",
            "Valor": f"{atual:.0f}",
            "Variacao_Pct": f"{var:+.1f}%",
            "Status": "positivo" if var > 0 else "negativo" if var < 0 else "neutro",
        })

    return pd.DataFrame(linhas)