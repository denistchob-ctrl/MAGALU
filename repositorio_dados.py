"""
repositorio_dados.py
=======================
Fachada única de acesso às fontes de dados do projeto, para a interface
Streamlit. Não substitui nem duplica os módulos existentes — apenas os
orquestra: quem lê e higieniza os arquivos continua sendo magalu_loader,
magalu_limpeza, magalu_fontes_externas, magalu_google_trends_live e
magalu_google_trends_anual.

Sobre a granularidade do DRE:
------------------------------
A planilha de resultados tem informações trimestrais (colunas '1T18',
'2T18', ...) e também colunas anuais/semestrais (dependendo da guia).
Para evitar misturar no mesmo gráfico valores que representam períodos
diferentes (o que gera "repetição" visual), o método
`serie_dre_por_granularidade()` agrega os dados conforme a granularidade
escolhida pelo usuário:

    - 'trimestral': devolve os trimestres como estão (1T18, 2T18, ...).
    - 'semestral' : soma os trimestres 2 a 2 (1S18, 2S18, ...).
    - 'anual'     : soma os 4 trimestres de cada ano (2018, 2019, ...).

Uso básico:
-----------
    from repositorio_dados import obter_repositorio

    repo = obter_repositorio()
    repo.anos_disponiveis()
    repo.serie_dre_por_granularidade("1. Indicadores", "EBITDA", "anual")
    repo.serie_dre_por_granularidade("1. Indicadores", "EBITDA", "trimestral", ano=2023)

Tratamento de erro:
--------------------
Cada fonte é carregada isoladamente: se uma falhar (ex.: arquivo ausente,
Google Trends bloqueado e sem backup), as demais continuam disponíveis.
repo.erros é um dict {nome_da_fonte: mensagem} para exibição transparente.
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

# Janela de análise do projeto (ver texto de objetivo da tela inicial). ajuste novo
ANO_INICIAL = 2018
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

        self.erros = {}

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
        """Loader live: usado apenas para a série mensal. A região agregada
        dele é DESCONSIDERADA — a região passa a vir do consolidado anual."""
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
    # Consulta — DRE com suporte a granularidade
    # ------------------------------------------------------------------
    def anos_disponiveis(self):
        """Anos do filtro lateral (janela de análise do projeto: 2021-2026)."""
        return list(range(ANO_INICIAL, ANO_FINAL + 1))

    def serie_dre_bruta(self, guia, indicador):
        """Série trimestral bruta, sem agregação — como está na planilha."""
        if self.loader_dre is None:
            return pd.Series(dtype=float)
        try:
            return self.loader_dre.get_series(guia, indicador)
        except KeyError:
            return pd.Series(dtype=float)

    def serie_dre_por_granularidade(self, guia, indicador,
                                    granularidade="trimestral", ano=None):
        """
        Devolve a série do DRE agregada conforme a granularidade escolhida,
        evitando misturar no mesmo gráfico trimestres, semestres e anos
        (o que gera "repetição" visual).

        Parâmetros:
            granularidade: 'trimestral', 'semestral' ou 'anual'.
            ano: se informado, filtra apenas aquele ano. Se None, devolve
                 o histórico completo (com todos os períodos disponíveis).

        Retorna uma pandas Series indexada por rótulos consistentes:
            'trimestral' -> '1T18', '2T18', ...
            'semestral'  -> '1S18', '2S18', ...
            'anual'      -> '2018', '2019', ...
        """
        serie = self.serie_dre_bruta(guia, indicador)
        if serie.empty:
            return serie

        # Se a granularidade pedida é a bruta, apenas filtra por ano (se houver)
        if granularidade == "trimestral":
            return self._filtrar_trimestres_por_ano(serie, ano)

        return self._agregar_serie(serie, granularidade, ano)

    def _filtrar_trimestres_por_ano(self, serie, ano):
        """
        Filtra a série para conter APENAS rótulos de trimestre (ex.: '1T18'),
        descartando qualquer outro rótulo (anos como '2018', semestres como
        '1S18', datas etc.) que eventualmente coexistam na mesma guia.

        Se 'ano' for informado, filtra também por aquele ano.
        """
        if serie is None or serie.empty:
            return serie

        # 1) Mantém apenas rótulos que casam com o padrão de trimestre
        mascara_trimestre = serie.index.map(
            lambda c: bool(PADRAO_TRIMESTRE_ANO.match(str(c)))
        )
        serie = serie[mascara_trimestre]

        # 2) Se um ano específico foi pedido, filtra por ele
        if ano is not None:
            sufixo = f"{ano % 100:02d}"
            serie = serie[
                [c for c in serie.index
                if PADRAO_TRIMESTRE_ANO.match(str(c))
                and PADRAO_TRIMESTRE_ANO.match(str(c)).group(2) == sufixo]
            ]

        return serie

    def _agregar_serie(self, serie, granularidade, ano):
        """Agrega a série trimestral em semestral ou anual."""
        if granularidade not in ("semestral", "anual"):
            raise ValueError(
                f"Granularidade inválida: '{granularidade}'. "
                f"Use 'trimestral', 'semestral' ou 'anual'."
            )

        # 1) Converte cada rótulo trimestral em (ano, trimestre)
        dados = []
        for rotulo, valor in serie.items():
            m = PADRAO_TRIMESTRE_ANO.match(str(rotulo))
            if not m:
                continue
            tri = int(m.group(1))
            ano_2d = int(m.group(2))
            ano_completo = 2000 + ano_2d
            if ano is not None and ano_completo != ano:
                continue
            if pd.isna(valor):
                valor = 0.0
            dados.append((ano_completo, tri, valor))

        if not dados:
            return pd.Series(dtype=float)

        # 2) Agrupa conforme a granularidade
        agrupado = {}
        for ano_completo, tri, valor in dados:
            if granularidade == "anual":
                chave = str(ano_completo)
            else:  # semestral
                semestre = 1 if tri <= 2 else 2
                chave = f"{semestre}S{ano_completo % 100:02d}"
            agrupado[chave] = agrupado.get(chave, 0.0) + valor

        # 3) Ordena cronologicamente
        if granularidade == "anual":
            chaves_ordenadas = sorted(agrupado.keys())
        else:
            chaves_ordenadas = sorted(
                agrupado.keys(),
                key=lambda s: (int(s[2:]) if len(s) > 2 else 0, int(s[0])),
            )

        return pd.Series({k: agrupado[k] for k in chaves_ordenadas})

    # ------------------------------------------------------------------
    # Cotações
    # ------------------------------------------------------------------
    def cotacao_por_ano(self, ano, coluna="Fechamento"):
        if self.cotacao is None:
            return pd.Series(dtype=float)
        serie = self.cotacao.get_serie(coluna)
        if ano is None:
            return serie
        return serie[serie.index.year == ano]

    # ------------------------------------------------------------------
    # Google Trends
    # ------------------------------------------------------------------
    def trends_por_ano(self, ano):
        if self.trends is None or self.trends.serie_temporal.empty:
            return pd.DataFrame(columns=['Ano', 'Data', 'Quantidade'])
        df = self.trends.serie_temporal
        if ano is None:
            return df
        return df[df['Ano'] == ano]

    def trends_regiao_por_ano(self, ano):
        if self.ga_anual is None or self.ga_anual.df.empty:
            return pd.Series(dtype=float)
        try:
            return self.ga_anual.df_por_ano(ano).sort_values(ascending=False)
        except ValueError:
            return pd.Series(dtype=float)

    def trends_regiao_agregada(self, como="soma"):
        if self.ga_anual is None or self.ga_anual.df.empty:
            return pd.Series(dtype=float)
        df = self.ga_anual.regiao_agregada(como=como)
        return df.set_index("Região")["Quantidade"]

    def trends_regiao_matriz(self):
        if self.ga_anual is None or self.ga_anual.df.empty:
            return pd.DataFrame()
        return self.ga_anual.matriz_ano_regiao()

    # ------------------------------------------------------------------
    # Reclame Aqui
    # ------------------------------------------------------------------
    def desempenho_ra_por_ano(self, empresa, ano):
        if self.reclame_aqui is None:
            return pd.DataFrame()
        df = self.reclame_aqui.desempenho(empresa)
        if ano is None:
            return df
        chave_ano = str(ano)
        if chave_ano in df.index:
            return df.loc[[chave_ano]]
        return df


@st.cache_resource(show_spinner="Carregando dados do projeto...")
def obter_repositorio(usar_google_trends_ao_vivo=True):
    """Ponto único de acesso ao RepositorioDados a partir do app Streamlit."""
    return RepositorioDados(
        usar_google_trends_ao_vivo=usar_google_trends_ao_vivo
    ).carregar_tudo()