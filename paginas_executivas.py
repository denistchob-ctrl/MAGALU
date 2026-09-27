"""
paginas_executivas.py
=======================
Páginas do dashboard executivo (5 atos) + páginas acadêmicas
(Início, Carga e Higienização), que ficam ao final do menu.

Cada página tem um seletor de período (com opção "Todos") e, quando faz
sentido, um seletor de granularidade (Trimestral / Semestral / Anual) para
evitar misturar no mesmo gráfico informações de períodos diferentes.
"""

import pandas as pd
import streamlit as st

from graficos_executivos import (
    ato1_receita_ebitda,
    ato1_cotacao_volume,
    ato2_vendas_e_interesse,
    ato2_reputacao_ra,
    ato2_top_problemas,
    ato3_mapa_interesse,
    ato3_heatmap_ano_regiao,
    ato4_investimentos_por_categoria,
    ato4_fluxo_caixa,
    ato5_tesoura_receita_interesse,
    ato5_scorecard,
)
from graficos import FabricaGraficos

OPCAO_TODOS = "Todos"
GRANULARIDADES = ["Trimestral", "Semestral", "Anual"]


# ======================================================================
# Helpers de seletor
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


def _seletor_granularidade(key):
    """Seletor de granularidade do DRE. Devolve 'trimestral', 'semestral'
    ou 'anual'."""
    escolha = st.sidebar.radio(
        "Granularidade",
        GRANULARIDADES,
        index=0,
        key=key,
        help="Evita misturar no mesmo gráfico trimestres, semestres e anos.",
    )
    return escolha.lower()


def _filtrar_serie_por_ano_mes(serie, ano, mes=None):
    """Filtra uma Series indexada por data."""
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

            Ao final do menu, há também **duas páginas acadêmicas**:
            **Início** (objetivo e fontes) e **Carga e Higienização**
            (transparência sobre o processo).
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
        gran = _seletor_granularidade(key="ato1_gran")

        # --- Receita, EBITDA e Margem ---
        st.subheader(f"1.1 Receita, EBITDA e Margem ({gran.capitalize()})")
        serie_receita = repositorio.serie_dre_por_granularidade(
            "1. Indicadores", "Receita Líquida Total", gran, ano)
        serie_ebitda = repositorio.serie_dre_por_granularidade(
            "1. Indicadores", "EBITDA", gran, ano)
        serie_margem = repositorio.serie_dre_por_granularidade(
            "1. Indicadores", "Margem EBITDA", gran, ano)

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
        st.caption("Relevância de marca (Google Trends) × Vendas × Reputação (Reclame Aqui)")

        ano = _seletor_ano(repositorio, key="ato2_ano")
        mes = _seletor_mes(key="ato2_mes")

        # --- Vendas × Interesse de busca (substitui o antigo RA × Trends) ---
        st.subheader("2.1 Vendas Totais × Interesse de busca")
        st.caption(
            "O interesse de busca cai enquanto as vendas sobem — a mesma "
            "tese do Ato 5, agora no nível operacional."
        )

        # Vendas Totais (trimestral)
        serie_vendas = repositorio.serie_dre_por_granularidade(
            "1. Indicadores", "Vendas Totais (incluindo marketplace)",
            "trimestral", None,
        )

        # Interesse de busca (mensal)
        trends = repositorio.trends
        serie_trends = None
        if trends is not None and not trends.serie_temporal.empty:
            serie_trends = trends.serie_temporal.set_index("Data")["Quantidade"]
            serie_trends = _filtrar_serie_por_ano_mes(serie_trends, ano, mes)

        fig = ato2_vendas_e_interesse(serie_vendas, serie_trends)
        st.plotly_chart(fig, width="stretch")

        # --- Reputação (Reclame Aqui) em seção própria ---
        st.markdown("---")
        st.subheader("2.2 Reputação — Reclame Aqui")

        ra = repositorio.reclame_aqui
        if ra is not None:
            empresa = st.selectbox(
                "Empresa", ra.listar_empresas(), key="ato2_empresa",
            )

            # Nota Média e % Voltariam — gráfico próprio, sem misturar com Trends
            df_ra = ra.desempenho(empresa)
            fig2 = ato2_reputacao_ra(df_ra, empresa)
            st.plotly_chart(fig2, width="stretch")

            # Top problemas
            df_prob = ra.problemas(empresa)
            fig3 = ato2_top_problemas(df_prob, empresa, top_n=5)
            st.plotly_chart(fig3, width="stretch")
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
        gran = _seletor_granularidade(key="ato4_gran")

        # --- Investimentos × Margem ---
        st.subheader(f"4.1 Investimentos por categoria × Margem EBITDA ({gran.capitalize()})")
        df_inv = _df_dre_por_granularidade(
            repositorio, "10.Investimentos", gran, ano)
        serie_margem = repositorio.serie_dre_por_granularidade(
            "1. Indicadores", "Margem EBITDA", gran, ano)

        if df_inv is not None and not df_inv.empty:
            fig = ato4_investimentos_por_categoria(df_inv.T, serie_margem)
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("Dados de investimentos não disponíveis.")

        # --- Fluxo de Caixa ---
        st.subheader(f"4.2 Fluxo de caixa por atividade ({gran.capitalize()})")
        guia_fc = "7. Fluxo de Caixa Gerencial"
        df_oper = repositorio.serie_dre_por_granularidade(
            guia_fc, "Fluxo de Caixa das Atividades Operacionais", gran, ano)
        df_invest = repositorio.serie_dre_por_granularidade(
            guia_fc, "Fluxo de Caixa das Atividades de Investimentos", gran, ano)
        df_financ = repositorio.serie_dre_por_granularidade(
            guia_fc, "Fluxo de Caixa das Atividades de Financiamentos", gran, ano)

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

        st.subheader("5.1 A tesoura: Receita cresce, interesse de busca cai")

        # Receita anual (agregada por ano, independente da granularidade)
        serie_receita = repositorio.serie_dre_por_granularidade(
            "1. Indicadores", "Receita Líquida Total", "anual", None)

        # Interesse anual (média por ano do Trends), limitado a 2018 em diante
        # para alinhar com a janela da Receita Líquida no gráfico "tesoura".
        trends = repositorio.trends
        interesse_anual = None
        if trends is not None and not trends.serie_temporal.empty:
            df_t = trends.serie_temporal.copy()
            # Filtra o período do Google Trends para coincidir com o da Receita
            df_t = df_t[df_t["Ano"] >= 2018]
            interesse_anual = df_t.groupby("Ano")["Quantidade"].mean()

        if not serie_receita.empty:
            fig = ato5_tesoura_receita_interesse(serie_receita, interesse_anual)
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("Dados de receita anual não disponíveis.")

        st.subheader("5.2 Scorecard executivo")
        df_score = _montar_scorecard(repositorio)
        if df_score is not None and not df_score.empty:
            fig2 = ato5_scorecard(df_score)
            st.plotly_chart(fig2, width="stretch")
        else:
            st.info("Não foi possível montar o scorecard.")

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
               recuperada tem correlação com a cotação.
            5. **Reposicionar a marca para o público geral**, não apenas o digital.
            """
        )


# ======================================================================
# Helpers internos
# ======================================================================

def _df_dre_por_granularidade(repositorio, guia, granularidade, ano):
    """
    Devolve um DataFrame (indicadores × períodos) da guia escolhida,
    agregado conforme a granularidade. Cada coluna é um período
    ('1T18', '1S18' ou '2018').
    """
    if repositorio.loader_dre is None:
        return pd.DataFrame()
    try:
        df_bruto = repositorio.loader_dre.get_sheet_df(guia)
    except KeyError:
        return pd.DataFrame()

    # Para cada indicador, agrega a série conforme a granularidade
    colunas = {}
    for indicador in df_bruto.index:
        serie_agregada = repositorio.serie_dre_por_granularidade(
            guia, indicador, granularidade, ano)
        if not serie_agregada.empty:
            colunas[indicador] = serie_agregada

    if not colunas:
        return pd.DataFrame()
    return pd.DataFrame(colunas).T


def _montar_scorecard(repositorio):
    """Monta o scorecard com indicadores-chave e variação vs. período anterior."""
    linhas = []

    # Receita (trimestral bruta)
    serie = repositorio.serie_dre_bruta("1. Indicadores", "Receita Líquida Total")
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
    serie = repositorio.serie_dre_bruta("1. Indicadores", "Margem EBITDA")
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


# ======================================================================
# Páginas acadêmicas (ao final do menu)
# ======================================================================

OBJETIVO_PROJETO = (
    "Analisar a evolução financeira, operacional e reputacional do Magazine Luiza "
    "entre 2021 e 2026, através de informações disponíveis no próprio site da "
    "empresa como também em outros sites. Criação de insights e dashboards que "
    "permitam acompanhar não somente as variáveis financeiras e operacionais como "
    "também investimentos realizados, valores de ações na bolsa, indicadores "
    "sociais, reputacionais e ações de marketing."
)

FONTES = ["DRE", "Cotações", "Reclame Aqui", "Google Trends"]


class PaginaInicio:
    """Tela acadêmica: objetivo do projeto e visão geral das fontes de dados."""

    def render(self, repositorio):
        st.title("Início — Objetivo e Fontes")
        st.markdown(f"> {OBJETIVO_PROJETO}")

        st.markdown("### Fontes de dados do projeto")
        colunas = st.columns(4)
        descricoes = {
            "DRE": ("📊", "Planilha de resultados trimestrais (RESULTADO_2T26_POR.xlsx)"),
            "Cotações": ("📈", "Histórico diário da ação na bolsa"),
            "Reclame Aqui": ("🗣️", "Reputação e reclamações — 4 unidades de negócio"),
            "Google Trends": ("🔎", "Interesse de busca pela marca (série mensal + ano a ano)"),
        }
        for coluna, fonte in zip(colunas, FONTES):
            icone, descricao = descricoes[fonte]
            with coluna:
                st.markdown(f"**{icone} {fonte}**")
                st.caption(descricao)
                if fonte in repositorio.erros:
                    st.error("Não carregada")
                else:
                    st.success("Carregada")

        st.info(
            "Use o menu à esquerda para navegar entre os atos executivos ou "
            "conferir como os dados foram carregados e higienizados."
        )


class PaginaCargaHigienizacao:
    """Tela acadêmica: status de carga e o que a limpeza ajustou."""

    def render(self, repositorio):
        st.title("Carga e higienização dos dados")

        if repositorio.erros:
            st.warning(
                "Uma ou mais fontes não puderam ser carregadas — veja os detalhes "
                "na fonte correspondente abaixo."
            )

        self._secao_dre(repositorio)
        self._secao_cotacao(repositorio)
        self._secao_reclame_aqui(repositorio)
        self._secao_google_trends(repositorio)

    def _secao_dre(self, repositorio):
        st.markdown("## Planilha de resultados (DRE)")
        if "DRE" in repositorio.erros:
            st.error(f"Falha ao carregar: {repositorio.erros['DRE']}")
            return
        loader = repositorio.loader_dre
        guias = loader.listar_guias()
        st.write(f"**{len(guias)} guias carregadas.**")
        with st.expander("Ver guias e o que a higienização ajustou em cada uma"):
            for relatorio in repositorio.relatorios_limpeza_dre:
                mudou = (relatorio["cabecalhos_renomeados"]
                         or relatorio["colunas_removidas"]
                         or relatorio.get("tracos_convertidos")
                         or relatorio["valores_zerados"])
                marcador = "🧹" if mudou else "✓"
                st.markdown(f"**{marcador} {relatorio['guia']}**")
                if relatorio["cabecalhos_renomeados"]:
                    st.caption(f"{len(relatorio['cabecalhos_renomeados'])} cabeçalho(s) corrigido(s)")
                if relatorio["colunas_removidas"]:
                    st.caption(f"{len(relatorio['colunas_removidas'])} coluna(s) vazia(s) removida(s)")
                if relatorio["valores_zerados"]:
                    st.caption(f"{len(relatorio['valores_zerados'])} indicador(es) com valores zerados")

    def _secao_cotacao(self, repositorio):
        st.markdown("## Cotação da ação")
        if "Cotações" in repositorio.erros:
            st.error(f"Falha ao carregar: {repositorio.erros['Cotações']}")
            return
        df = repositorio.cotacao.df
        st.write(f"**{len(df)} pregões carregados**, de {df.index.min().date()} "
                 f"a {df.index.max().date()}.")
        with st.expander("Ver amostra dos dados"):
            st.dataframe(df.tail(5))

    def _secao_reclame_aqui(self, repositorio):
        st.markdown("## Reclame Aqui")
        if "Reclame Aqui" in repositorio.erros:
            st.error(f"Falha ao carregar: {repositorio.erros['Reclame Aqui']}")
            return
        ra = repositorio.reclame_aqui
        empresas = ra.listar_empresas()
        st.write(f"**{len(empresas)} empresas encontradas:** {', '.join(empresas)}")
        with st.expander("Ver categorias disponíveis por empresa"):
            for empresa in empresas:
                st.caption(f"{empresa}: {', '.join(ra.listar_categorias(empresa))}")

    def _secao_google_trends(self, repositorio):
        st.markdown("## Google Trends")
        trends = getattr(repositorio, "trends", None)
        if trends is None:
            st.warning("Google Trends (série mensal) não carregado.")
        else:
            if trends.usando_backup:
                st.warning("⚠ Consulta ao vivo indisponível agora — exibindo a "
                           "última leitura salva em backup.")
            else:
                st.success("Série mensal obtida ao vivo (Google Trends).")
            st.write(f"**{len(trends.serie_temporal)} meses** carregados.")
            st.caption("A região agregada do loader live foi DESCONSIDERADA — "
                       "ela era uma 'foto' de um momento específico e ficava "
                       "inconsistente com o consolidado ano a ano.")

        st.markdown("### Interesse por região — ano a ano")
        ga_anual = getattr(repositorio, "ga_anual", None)
        if ga_anual is None or ga_anual.df.empty:
            st.info("Sem dados consolidados por região/ano.")
            return

        anos = ga_anual.anos_disponiveis()
        regioes = ga_anual.regioes_disponiveis()
        st.write(
            f"**{len(ga_anual.df)} linhas** consolidadas, cobrindo "
            f"**{len(anos)} ano(s)** ({anos[0]}–{anos[-1]}) e "
            f"**{len(regioes)} região(ões)**."
        )
        st.caption(
            "Anos passados são lidos do backup consolidado "
            "(`GA_porRegiao_ano_a_ano.csv`); apenas o ano corrente "
            f"({anos[-1]}) é reconsultado ao vivo."
        )
        with st.expander("Ver amostra do consolidado"):
            st.dataframe(ga_anual.df.head(20))
        with st.expander("Ver região agregada (derivada do consolidado)"):
            serie = repositorio.trends_regiao_agregada()
            if not serie.empty:
                st.dataframe(serie.sort_values(ascending=False))
            else:
                st.info("Sem dados.")