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
                                    granularidade="trimestral", ano=None,
                                    chave_indicador=None):
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

        if granularidade == "trimestral":
            return self._filtrar_trimestres_por_ano(serie, ano)

        return self._agregar_serie(serie, granularidade, ano,
                                   chave_indicador=chave_indicador)

    def _filtrar_trimestres_por_ano(self, serie, ano):
        """..."""
        if serie is None:
            return pd.Series(dtype=float)

        # Se veio DataFrame (índice duplicado), colapsa em uma Series
        if isinstance(serie, pd.DataFrame):
            serie = serie.apply(pd.to_numeric, errors="coerce").sum(axis=0)

        if serie.empty:
            return serie

        mascara_trimestre = serie.index.map(
            lambda c: bool(PADRAO_TRIMESTRE_ANO.match(str(c)))
        )
        serie = serie[mascara_trimestre]

        if ano is not None:
            sufixo = f"{ano % 100:02d}"
            serie = serie[
                [c for c in serie.index
                 if PADRAO_TRIMESTRE_ANO.match(str(c))
                 and PADRAO_TRIMESTRE_ANO.match(str(c)).group(2) == sufixo]
            ]

        return serie

    def _agregar_serie(self, serie, granularidade, ano, chave_indicador=None):
        """
        Agrega a série trimestral em semestral ou anual.

        Estratégia (por ordem de prioridade):
          1. Se a série JÁ CONTÉM o rótulo do período agregado (ex.: '2024'
             para anual, '1S24' para semestral), usa esse valor DIRETAMENTE.
             Isso preserva o número oficial divulgado pela empresa —
             especialmente importante para percentuais (margens, participações),
             onde a média dos trimestres pode distorcer.
          2. Se o rótulo não existe, CALCULA:
             - MÉDIA para indicadores percentuais (lista em
               config_indicadores.INDICADORES_PERCENTUAIS);
             - SOMA para os demais.
        """
        from config_indicadores import INDICADORES_PERCENTUAIS

        if granularidade not in ("semestral", "anual"):
            raise ValueError(
                f"Granularidade inválida: '{granularidade}'. "
                f"Use 'trimestral', 'semestral' ou 'anual'."
            )

        # --- Normalização inicial -------------------------------------
        # Se a série vier com índice duplicado (indicador aparece mais de
        # uma vez na guia), colapsa em uma única linha antes de processar.
        if isinstance(serie, pd.DataFrame):
            serie = serie.apply(pd.to_numeric, errors="coerce").sum(axis=0)
        else:
            if serie.index.has_duplicates:
                serie = serie.groupby(level=0).sum()

        eh_percentual = chave_indicador in INDICADORES_PERCENTUAIS

        # --- 1) Coleta trimestres e rótulos agregados existentes ------
        # Guardamos os valores trimestrais para eventual recálculo e
        # também os rótulos agregados já presentes na série.
        trimestres = []       # (ano_completo, tri, valor)
        rotulos_anuais = {}   # '2024' -> valor
        rotulos_semestrais = {}  # '1S24' -> valor

        for rotulo, valor in serie.items():
            texto = str(rotulo)
            if pd.isna(valor):
                continue

            # Rótulo de trimestre: '1T18'
            m_tri = PADRAO_TRIMESTRE_ANO.match(texto)
            if m_tri:
                tri = int(m_tri.group(1))
                ano_2d = int(m_tri.group(2))
                ano_completo = 2000 + ano_2d
                trimestres.append((ano_completo, tri, float(valor)))
                continue

            # Rótulo de ano: '2018'
            m_ano = re.match(r'^(\d{4})$', texto)
            if m_ano:
                rotulos_anuais[int(m_ano.group(1))] = float(valor)
                continue

            # Rótulo de semestre: '1S18'
            m_sem = re.match(r'^(\d)S(\d{2})$', texto)
            if m_sem:
                sem = int(m_sem.group(1))
                ano_2d = int(m_sem.group(2))
                rotulos_semestrais[(2000 + ano_2d, sem)] = float(valor)
                continue

        # --- Filtro por ano, se pedido ---------------------------------
        if ano is not None:
            trimestres = [t for t in trimestres if t[0] == ano]

        # --- 2) Monta o resultado, período por período ----------------
        agrupado = {}

        if granularidade == "anual":
            # Conjunto de anos a cobrir: os que têm trimestre OU os que já
            # têm valor anual direto na série.
            anos_disponiveis = sorted(
                {t[0] for t in trimestres} | set(rotulos_anuais.keys())
            )
            if ano is not None:
                anos_disponiveis = [a for a in anos_disponiveis if a == ano]

            for a in anos_disponiveis:
                chave = str(a)

                # (1) Se o valor anual já existe na série, usa direto.
                if a in rotulos_anuais:
                    agrupado[chave] = rotulos_anuais[a]
                    continue

                # (2) Senão, calcula a partir dos trimestres daquele ano.
                vals = [v for (aa, _tri, v) in trimestres if aa == a]
                if not vals:
                    continue
                agrupado[chave] = (
                    sum(vals) / len(vals) if eh_percentual else sum(vals)
                )

        else:  # semestral
            # Conjunto de (ano, semestre) a cobrir.
            chaves_sem = set()
            for (aa, tri, _v) in trimestres:
                chaves_sem.add((aa, 1 if tri <= 2 else 2))
            chaves_sem |= set(rotulos_semestrais.keys())

            if ano is not None:
                chaves_sem = {k for k in chaves_sem if k[0] == ano}

            for (a, sem) in sorted(chaves_sem):
                chave = f"{sem}S{a % 100:02d}"

                # (1) Se o valor semestral já existe, usa direto.
                if (a, sem) in rotulos_semestrais:
                    agrupado[chave] = rotulos_semestrais[(a, sem)]
                    continue

                # (2) Senão, agrega os dois trimestres correspondentes.
                if sem == 1:
                    vals = [v for (aa, tri, v) in trimestres
                            if aa == a and tri in (1, 2)]
                else:
                    vals = [v for (aa, tri, v) in trimestres
                            if aa == a and tri in (3, 4)]
                if not vals:
                    continue
                agrupado[chave] = (
                    sum(vals) / len(vals) if eh_percentual else sum(vals)
                )

        if not agrupado:
            return pd.Series(dtype=float)

        # --- 3) Ordena cronologicamente ---------------------------------
        if granularidade == "anual":
            chaves_ordenadas = sorted(agrupado.keys(), key=lambda s: int(s))
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