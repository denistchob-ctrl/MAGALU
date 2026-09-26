"""
repositorio_dados.py
=======================
Fachada única de acesso às 4 fontes de dados do projeto, para a interface
Streamlit. Não substitui nem duplica os módulos existentes — apenas os
orquestra: quem lê e higieniza os arquivos continua sendo magalu_loader,
magalu_limpeza, magalu_fontes_externas, magalu_google_trends_live e
magalu_google_trends_anual.

Uso básico:
-----------
    from repositorio_dados import obter_repositorio

    repo = obter_repositorio()   # cacheado pelo Streamlit; só carrega 1x por sessão
    repo.anos_disponiveis()
    repo.serie_dre_por_ano("1. Indicadores", "EBITDA", 2023)
    repo.cotacao_por_ano(2023)
    repo.trends_por_ano(2023)
    repo.trends_regiao_por_ano(2023)
    repo.trends_regiao_agregada()
    repo.desempenho_ra_por_ano("fisica", 2023)

Sobre a região do Google Trends:
---------------------------------
A região agregada NÃO vem mais do loader live
('ultimaLeituraGAporRegiao.csv') — ela é derivada do consolidado anual
(GA_porRegiao_agregada.csv), que é sempre consistente com o ano a ano.

Tratamento de erro:
--------------------
Cada fonte é carregada isoladamente: se uma falhar (ex.: arquivo ausente,
Google Trends bloqueado e sem backup), as demais continuam disponíveis.
repo.erros é um dict {nome_da_fonte: mensagem} com o que não pôde ser
carregado, para a página de "Carga e Higienização" exibir com transparência.
"""

import re

import streamlit as st
import pandas as pd

from magalu_loader import MagaluDataLoader
from magalu_limpeza import limpar_loader
from magalu_fontes_externas import CotacaoAcaoLoader, ReclameAquiLoader
from magalu_google_trends_live import GoogleTrendsPyTrendsLoader
from magalu_google_trends_anual import GoogleTrendsPorRegiaoAnual

PADRAO_TRIMESTRE_ANO = re.compile(r'^(\d)T(\d{2})$')

# Janela de análise do projeto (ver texto de objetivo da tela inicial).
ANO_INICIAL = 2021
ANO_FINAL = 2026


class RepositorioDados:
    """Carrega e disponibiliza as fontes de dados do projeto (DRE, Cotações,
    Reclame Aqui e Google Trends), já higienizadas, para as páginas do app."""

    NOME_PLANILHA_DRE = "RESULTADO_2T26_POR.xlsx"

    def __init__(self, usar_google_trends_ao_vivo=True):
        self.usar_google_trends_ao_vivo = usar_google_trends_ao_vivo

        self.loader_dre = None
        self.relatorios_limpeza_dre = []
        self.cotacao = None
        self.reclame_aqui = None
        self.trends = None          # loader live (série mensal)
        self.ga_anual = None        # loader anual (consolidado Ano × Região)

        self.erros = {}  # nome da fonte -> mensagem de erro

    # ------------------------------------------------------------------
    # Carregamento
    # ------------------------------------------------------------------
    def carregar_tudo(self):
        self._carregar_dre()
        self._carregar_cotacao()
        self._carregar_reclame_aqui()
        self._carregar_google_trends()
        self._carregar_google_trends_anual()
        return self

    def _carregar_dre(self):
        try:
            self.loader_dre = MagaluDataLoader(self.NOME_PLANILHA_DRE)
            self.relatorios_limpeza_dre = limpar_loader(self.loader_dre, verbose=False)
        except Exception as erro:
            self.erros['DRE'] = str(erro)

    def _carregar_cotacao(self):
        try:
            self.cotacao = CotacaoAcaoLoader()
        except Exception as erro:
            self.erros['Cotações'] = str(erro)

    def _carregar_reclame_aqui(self):
        try:
            self.reclame_aqui = ReclameAquiLoader()
        except Exception as erro:
            self.erros['Reclame Aqui'] = str(erro)

    def _carregar_google_trends(self):
        """
        Carrega o loader live do Google Trends. ATENÇÃO:
          - A série mensal (trends.serie_temporal) continua sendo usada
            normalmente (é a única fonte com granularidade mensal).
          - A região agregada (trends.por_regiao) é IGNORADA a partir de
            agora — a região passa a vir do consolidado anual via
            trends_regiao_agregada(). Isso evita a inconsistência entre
            a 'foto' antiga e o consolidado ano a ano.
        """
        try:
            self.trends = GoogleTrendsPyTrendsLoader(termos=["Magazine Luiza"])
        except Exception as erro:
            self.erros['Google Trends'] = str(erro)

    def _carregar_google_trends_anual(self):
        try:
            self.ga_anual = GoogleTrendsPorRegiaoAnual(
                ano_inicio=ANO_INICIAL,
                ano_fim=ANO_FINAL,
                termos=["Magazine Luiza"],
                geo="BR",
                apenas_ano_corrente_ao_vivo=True,
                pausa_entre_anos=15,
            )
        except Exception as erro:
            self.erros['Google Trends (anual)'] = str(erro)

    # ------------------------------------------------------------------
    # Consulta — usadas pelas páginas do app
    # ------------------------------------------------------------------
    def anos_disponiveis(self):
        """Anos do filtro lateral (janela de análise do projeto: 2021-2026)."""
        return list(range(ANO_INICIAL, ANO_FINAL + 1))

    def serie_dre_por_ano(self, guia, indicador, ano):
        """Valores trimestrais (1T.., 2T.., 3T.., 4T..) de um indicador da
        planilha de resultados, filtrados para um ano específico."""
        if self.loader_dre is None:
            return pd.Series(dtype=float)
        serie = self.loader_dre.get_series(guia, indicador)
        sufixo_ano = f"{ano % 100:02d}"
        colunas_ano = [
            c for c in serie.index
            if PADRAO_TRIMESTRE_ANO.match(str(c))
            and PADRAO_TRIMESTRE_ANO.match(str(c)).group(2) == sufixo_ano
        ]
        return serie[colunas_ano]

    def cotacao_por_ano(self, ano, coluna="Fechamento"):
        """Série diária de uma coluna da cotação (Fechamento, Abertura, ...),
        filtrada para um ano específico."""
        if self.cotacao is None:
            return pd.Series(dtype=float)
        serie = self.cotacao.get_serie(coluna)
        return serie[serie.index.year == ano]

    def trends_por_ano(self, ano):
        """DataFrame mensal do Google Trends (Ano, Data, Quantidade), filtrado
        para um ano específico."""
        if self.trends is None or self.trends.serie_temporal.empty:
            return pd.DataFrame(columns=['Ano', 'Data', 'Quantidade'])
        df = self.trends.serie_temporal
        return df[df['Ano'] == ano]

    def trends_regiao_por_ano(self, ano):
        """Series (índice = Região) com o interesse por região em um ano."""
        if self.ga_anual is None or self.ga_anual.df.empty:
            return pd.Series(dtype=float)
        try:
            return self.ga_anual.df_por_ano(ano).sort_values(ascending=False)
        except ValueError:
            return pd.Series(dtype=float)

    def trends_regiao_agregada(self, como="soma"):
        """
        Series (índice = Região) com o interesse agregado de TODOS os anos
        do consolidado. Substitui o antigo 'ultimaLeituraGAporRegiao.csv'
        do loader live, que era uma foto de um momento específico e podia
        ficar inconsistente com o consolidado ano a ano.
        """
        if self.ga_anual is None or self.ga_anual.df.empty:
            return pd.Series(dtype=float)
        df = self.ga_anual.regiao_agregada(como=como)
        return df.set_index("Região")["Quantidade"]

    def trends_serie_anualizada(self):
        """Series (índice = Ano) com a soma das quantidades por ano."""
        if self.ga_anual is None or self.ga_anual.df.empty:
            return pd.Series(dtype=float)
        df = self.ga_anual.serie_temporal_anualizada()
        return df.set_index("Ano")["Quantidade"]

    def trends_regiao_matriz(self):
        """DataFrame pivotado Ano x Região (para heatmap)."""
        if self.ga_anual is None or self.ga_anual.df.empty:
            return pd.DataFrame()
        return self.ga_anual.matriz_ano_regiao()

    def desempenho_ra_por_ano(self, empresa, ano):
        """Linha de desempenho (Reclame Aqui) de uma empresa para um ano
        específico. Se aquele ano não existir no relatório (ex.: RA só
        reporta 2024/2025/2026/Geral), devolve o relatório completo da
        empresa, para a página decidir como exibir."""
        if self.reclame_aqui is None:
            return pd.DataFrame()
        df = self.reclame_aqui.desempenho(empresa)
        chave_ano = str(ano)
        if chave_ano in df.index:
            return df.loc[[chave_ano]]
        return df


@st.cache_resource(show_spinner="Carregando dados do projeto...")
def obter_repositorio(usar_google_trends_ao_vivo=True):
    """Ponto único de acesso ao RepositorioDados a partir do app Streamlit.
    Cacheado: as fontes só são carregadas uma vez por sessão do app,
    não a cada interação/rerun."""
    return RepositorioDados(
        usar_google_trends_ao_vivo=usar_google_trends_ao_vivo
    ).carregar_tudo()