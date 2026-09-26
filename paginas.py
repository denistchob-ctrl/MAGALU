"""
paginas.py
============
Páginas do app Streamlit, uma classe por página, cada uma com um método
render(). Mantém a apresentação separada do acesso a dados
(repositorio_dados.py) e da construção dos gráficos (graficos.py).
"""

import streamlit as st

from graficos import FabricaGraficos

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
    """Tela inicial: objetivo do projeto e visão geral das fontes de dados."""

    def render(self, repositorio):
        st.title("Evolução do Magazine Luiza")
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
            "Use o menu à esquerda para conferir como os dados foram carregados e "
            "higienizados, ou para ir direto ao dashboard."
        )


class PaginaCargaHigienizacao:
    """Mostra o status de carga de cada fonte e o que a rotina de limpeza
    (magalu_limpeza) ajustou nos dados da planilha de resultados."""

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

        # --- Série mensal (loader live) ---
        trends = getattr(repositorio, "trends", None)
        if trends is None:
            st.warning("Google Trends (série mensal) não carregado.")
        else:
            if trends.usando_backup:
                st.warning("⚠ Consulta ao vivo indisponível agora — exibindo a "
                           "última leitura salva em backup.")
            else:
                st.success("Série mensal obtida ao vivo (Google Trends).")
            st.write(f"**{len(trends.serie_temporal)} meses** carregados "
                     f"(granularidade mensal).")
            st.caption("A região agregada do loader live foi DESCONSIDERADA — "
                       "ela era uma 'foto' de um momento específico e ficava "
                       "inconsistente com o consolidado ano a ano.")

        # --- Consolidado ano a ano (fonte única de verdade p/ região) ---
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


class PaginaDashboard:
    """Dashboard principal: gráfico(s) da fonte selecionada, filtrados pelo
    ano escolhido no menu lateral."""

    def render(self, repositorio, ano, fonte):
        st.title("Dashboard")
        st.caption(f"Fonte: {fonte} · Ano: {ano}")

        if fonte in repositorio.erros:
            st.error(f"Esta fonte não pôde ser carregada: {repositorio.erros[fonte]}")
            return

        if fonte == "DRE":
            self._dashboard_dre(repositorio, ano)
        elif fonte == "Cotações":
            self._dashboard_cotacao(repositorio, ano)
        elif fonte == "Reclame Aqui":
            self._dashboard_reclame_aqui(repositorio, ano)
        elif fonte == "Google Trends":
            self._dashboard_trends(repositorio, ano)

    def _dashboard_dre(self, repositorio, ano):
        indicador = st.selectbox(
            "Indicador",
            ["EBITDA", "Receita Líquida Total", "Lucro Líquido", "Margem EBITDA"],
        )
        serie = repositorio.serie_dre_por_ano("1. Indicadores", indicador, ano)
        fig = FabricaGraficos.dre_trimestral(serie, indicador, ano)
        st.plotly_chart(fig, width='stretch')
        with st.expander("Ver valores"):
            st.dataframe(serie)

    def _dashboard_cotacao(self, repositorio, ano):
        coluna = st.selectbox("Métrica", ["Fechamento", "Abertura", "Volume_Financeiro"])
        serie = repositorio.cotacao_por_ano(ano, coluna)
        fig = FabricaGraficos.cotacao_diaria(serie, ano, coluna)
        st.plotly_chart(fig, width='stretch')

    def _dashboard_reclame_aqui(self, repositorio, ano):
        empresas = repositorio.reclame_aqui.listar_empresas()
        empresa = st.selectbox("Empresa", empresas)

        df_desempenho = repositorio.desempenho_ra_por_ano(empresa, ano)
        fig = FabricaGraficos.reclame_aqui_desempenho(df_desempenho, empresa, ano)
        st.plotly_chart(fig, width='stretch')

        df_problemas = repositorio.reclame_aqui.problemas(empresa)
        fig2 = FabricaGraficos.reclame_aqui_top_problemas(df_problemas, empresa)
        st.plotly_chart(fig2, width='stretch')

    def _dashboard_trends(self, repositorio, ano):
        st.subheader("Google Trends — interesse de busca")

        # 1) Série mensal do ano
        df = repositorio.trends_por_ano(ano)
        fig = FabricaGraficos.google_trends_mensal(df, ano)
        st.plotly_chart(fig, width='stretch')

        if repositorio.trends and repositorio.trends.usando_backup:
            st.caption("⚠ Série mensal vinda do backup (consulta ao vivo indisponível).")

        # 2) Ranking por região no ano
        st.markdown("---")
        serie_regiao = repositorio.trends_regiao_por_ano(ano)
        if not serie_regiao.empty:
            fig2 = FabricaGraficos.google_trends_regiao_barras(serie_regiao, ano)
            st.plotly_chart(fig2, width='stretch')
        else:
            st.info(f"Sem dados de interesse por região para {ano}.")

        # 3) Heatmap Ano × Região
        st.markdown("---")
        matriz = repositorio.trends_regiao_matriz()
        if not matriz.empty:
            fig3 = FabricaGraficos.google_trends_heatmap_ano_regiao(matriz)
            st.plotly_chart(fig3, width='stretch')
        else:
            st.info("Sem dados consolidados por ano/região.")

        # 4) Ranking agregado histórico (substitui o antigo 'ultimaLeituraGAporRegiao')
        st.markdown("---")
        serie_agregada = repositorio.trends_regiao_agregada()
        if not serie_agregada.empty:
            fig4 = FabricaGraficos.google_trends_regiao_agregada(serie_agregada)
            st.plotly_chart(fig4, width='stretch')
        else:
            st.info("Sem dados agregados por região.")