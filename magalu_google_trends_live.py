"""
magalu_google_trends_live.py
===============================
Carrega o interesse de busca da marca DIRETAMENTE da API do Google Trends,
via biblioteca pytrends — em vez de ler de um CSV exportado manualmente
(como faz GoogleTrendsLoader em magalu_fontes_externas.py). Assim a consulta
reflete o momento em que o código é executado, sem precisar gerar e subir
um novo arquivo toda vez.

A classe GoogleTrendsPyTrendsLoader tem a MESMA interface pública do
GoogleTrendsLoader baseado em CSV, para que o resto do projeto (dashboards,
notebooks, etc.) possa usar uma fonte ou outra sem mudar uma linha:

    trends.serie_temporal      # DataFrame ['Ano', 'Time', 'Quantidade']
    trends.por_regiao          # DataFrame ['Region', 'Quantidade']
    trends.get_serie_temporal()  # Series indexada por data
    trends.get_por_regiao()      # Series indexada por região

Instalação:
-----------
    pip install pytrends --break-system-packages

Uso básico:
-----------
    from magalu_google_trends_live import GoogleTrendsPyTrendsLoader

    trends = GoogleTrendsPyTrendsLoader()          # termos e período padrão
    trends.serie_temporal
    trends.get_serie_temporal()

    # Personalizando termos, período e geografia:
    trends = GoogleTrendsPyTrendsLoader(
        termos=["Magazine Luiza", "MAGALU"],
        geo="BR",
        timeframe="all",     # 'all' = todo o histórico disponível (desde 2004)
    )

Consolidação dos termos pesquisados:
--------------------------------------
Assim como na fonte via CSV, se mais de um termo for pesquisado (padrão:
"Magazine Luiza" e "MAGALU"), os valores de cada termo são SOMADOS em uma
única coluna 'Quantidade', tanto na série temporal quanto no detalhamento
por região — para medir o interesse total pela marca, e não comparar um
termo com o outro.

Limitações importantes (leia antes de usar em produção):
------------------------------------------------------------
1. Precisa de acesso à internet no momento da execução (faz requisição
   para trends.google.com). Sem internet, a consulta falha com uma
   exceção clara.

2. O Google aplica bloqueio anti-automação (erro HTTP 403) com bastante
   frequência para requisições vindas de IPs de datacenter/nuvem — é uma
   limitação conhecida do pytrends, não um bug deste código. Por isso:
   - o construtor já tenta novamente algumas vezes, com espera entre
     tentativas (parâmetros `tentativas` e `espera_entre_tentativas`);
   - se mesmo assim falhar, considere: rodar a partir de uma rede
     doméstica/residencial em vez de nuvem, aumentar o intervalo entre
     execuções (o Google também limita por taxa de requisições), ou usar
     um proxy (parâmetro `proxies`, repassado direto para o pytrends).

3. Os valores são índices RELATIVOS (0 a 100), normalizados pelo próprio
   Google para o período/termos consultados — não é contagem absoluta de
   buscas, e o valor "100" de uma consulta feita hoje não é diretamente
   comparável ao "100" de uma consulta feita em outro momento (o Google
   pode reprocessar a normalização). Para uma série histórica ESTÁVEL ao
   longo do tempo (não sujeita a mudar a cada nova consulta), prefira a
   fonte via CSV (GoogleTrendsLoader).
"""

import time

import pandas as pd

try:
    from pytrends.request import TrendReq
    from pytrends.exceptions import ResponseError, TooManyRequestsError
except ImportError as _erro_importacao:
    TrendReq = None
    ResponseError = TooManyRequestsError = Exception
    _ERRO_IMPORTACAO_PYTRENDS = _erro_importacao
else:
    _ERRO_IMPORTACAO_PYTRENDS = None


# Mesmo mapa de tradução usado em magalu_fontes_externas.GoogleTrendsLoader,
# para o caso (pouco provável, mas possível dependendo do parâmetro 'idioma')
# de a API devolver o nome da região em inglês.
MAPA_REGIOES_PT = {
    'Region': 'Região',
    'Federal District': 'Distrito Federal',
    'State of Acre': 'Acre',
    'State of Alagoas': 'Alagoas',
    'State of Amapá': 'Amapá',
    'State of Amazonas': 'Amazonas',
    'State of Bahia': 'Bahia',
    'State of Ceará': 'Ceará',
    'State of Espírito Santo': 'Espírito Santo',
    'State of Goiás': 'Goiás',
    'State of Maranhão': 'Maranhão',
    'State of Mato Grosso': 'Mato Grosso',
    'State of Mato Grosso do Sul': 'Mato Grosso do Sul',
    'State of Minas Gerais': 'Minas Gerais',
    'State of Paraná': 'Paraná',
    'State of Paraíba': 'Paraíba',
    'State of Pará': 'Pará',
    'State of Pernambuco': 'Pernambuco',
    'State of Piauí': 'Piauí',
    'State of Rio Grande do Norte': 'Rio Grande do Norte',
    'State of Rio Grande do Sul': 'Rio Grande do Sul',
    'State of Rio de Janeiro': 'Rio de Janeiro',
    'State of Rondônia': 'Rondônia',
    'State of Roraima': 'Roraima',
    'State of Santa Catarina': 'Santa Catarina',
    'State of Sergipe': 'Sergipe',
    'State of São Paulo': 'São Paulo',
    'State of Tocantins': 'Tocantins',
}


class GoogleTrendsPyTrendsLoader:
    """
    Consulta o Google Trends ao vivo (via pytrends) para os termos e período
    informados, e organiza o resultado na mesma estrutura usada pela fonte
    via CSV (GoogleTrendsLoader, em magalu_fontes_externas.py):

        self.serie_temporal -> DataFrame ['Ano', 'Time', 'Quantidade']
        self.por_regiao     -> DataFrame ['Region', 'Quantidade']

    Parâmetros principais:
        termos: lista de palavras-chave pesquisadas (somadas em 'Quantidade').
        geo: código do país/região (padrão 'BR' = Brasil inteiro).
        timeframe: período consultado no formato do pytrends
            (ex.: 'all' = todo o histórico; 'today 5-y' = últimos 5 anos).
        idioma: parâmetro 'hl' do pytrends (idioma da interface/nomes).
        tentativas / espera_entre_tentativas: controla a repetição
            automática em caso de falha temporária (ex.: erro 403/429).
        proxies: lista de proxies no formato aceito pelo pytrends, repassada
            direto para TrendReq (útil se o IP de execução for bloqueado).
    """

    def __init__(self, termos=("Magazine Luiza"), geo="BR", timeframe="all",
                 idioma="pt-BR", fuso_horario=180, tentativas=3,
                 espera_entre_tentativas=10, proxies=None):
        if TrendReq is None:
            raise ImportError(
                "A biblioteca 'pytrends' não está instalada. Instale com:\n"
                "    pip install pytrends --break-system-packages"
            ) from _ERRO_IMPORTACAO_PYTRENDS

        self.termos = list(termos)
        self.geo = geo
        self.timeframe = timeframe
        self.tentativas = tentativas
        self.espera_entre_tentativas = espera_entre_tentativas

        self._pytrends = TrendReq(hl=idioma, tz=fuso_horario, proxies=proxies or "")

        self.serie_temporal = pd.DataFrame()
        self.por_regiao = pd.DataFrame()
        self._carregar()

    # ------------------------------------------------------------------
    # Infraestrutura de consulta (retentativas / tradução)
    # ------------------------------------------------------------------
    def _com_novas_tentativas(self, descricao, func, *args, **kwargs):
        ultimo_erro = None
        for tentativa in range(1, self.tentativas + 1):
            try:
                return func(*args, **kwargs)
            except (ResponseError, TooManyRequestsError) as erro:
                ultimo_erro = erro
                if tentativa < self.tentativas:
                    print(f"[GoogleTrendsPyTrendsLoader] {descricao}: tentativa "
                          f"{tentativa}/{self.tentativas} falhou ({erro}); "
                          f"aguardando {self.espera_entre_tentativas}s...")
                    time.sleep(self.espera_entre_tentativas)

        raise RuntimeError(
            f"Falha ao consultar o Google Trends ({descricao}) após "
            f"{self.tentativas} tentativa(s). O Google costuma bloquear (HTTP 403/429) "
            f"requisições automatizadas vindas de IPs de nuvem/datacenter — tente "
            f"novamente a partir de outra rede, aumente o intervalo entre execuções, "
            f"ou informe um proxy (parâmetro 'proxies')."
        ) from ultimo_erro

    def _traduzir_regiao(self, nome_regiao):
        if nome_regiao in MAPA_REGIOES_PT:
            return MAPA_REGIOES_PT[nome_regiao]
        if nome_regiao.startswith('State of ') or nome_regiao == 'Federal District':
            print(f"[GoogleTrendsPyTrendsLoader] Aviso: região '{nome_regiao}' sem "
                  f"tradução cadastrada em MAPA_REGIOES_PT — mantendo o nome original.")
        return nome_regiao

    # ------------------------------------------------------------------
    # Carregamento
    # ------------------------------------------------------------------
    def _carregar(self):
        self._com_novas_tentativas(
            "build_payload",
            self._pytrends.build_payload,
            kw_list=self.termos, timeframe=self.timeframe, geo=self.geo,
        )

        self._carregar_serie_temporal()
        self._carregar_por_regiao()

    def _carregar_serie_temporal(self):
        df = self._com_novas_tentativas(
            "interest_over_time", self._pytrends.interest_over_time
        )
        if df is None or df.empty:
            return

        df = df.drop(columns=['isPartial'], errors='ignore')
        df = df.reset_index().rename(columns={'date': 'Data'})

        colunas_termos = [c for c in self.termos if c in df.columns]
        df['Quantidade'] = df[colunas_termos].sum(axis=1)
        df = df[['Data', 'Quantidade']]
        df.insert(0, 'Ano', df['Data'].dt.year)

        self.serie_temporal = df.sort_values('Data').reset_index(drop=True)

    def _carregar_por_regiao(self):
        df = self._com_novas_tentativas(
            "interest_by_region", self._pytrends.interest_by_region,
            resolution='REGION', inc_low_vol=True, inc_geo_code=False,
        )
        if df is None or df.empty:
            return

        df = df.reset_index()
        df = df.rename(columns={df.columns[0]: 'Região'})  # a primeira coluna é o nome da região, mas o pytrends não garante o nome exato

        colunas_termos = [c for c in self.termos if c in df.columns]
        df['Quantidade'] = df[colunas_termos].sum(axis=1)
        df = df[['Região', 'Quantidade']]
        df['Região'] = df['Região'].apply(self._traduzir_regiao)

        self.por_regiao = df.sort_values('Região').reset_index(drop=True)

    # ------------------------------------------------------------------
    # Consulta (mesma interface de GoogleTrendsLoader)
    # ------------------------------------------------------------------
    def get_serie_temporal(self):
        """Devolve uma pandas Series (índice = data) com o interesse de busca
        total (soma de todos os termos pesquisados)."""
        if self.serie_temporal.empty:
            raise ValueError("Nenhum dado de série temporal retornado pelo Google Trends.")
        return self.serie_temporal.set_index('Data')['Quantidade']

    def get_por_regiao(self):
        """Devolve uma pandas Series (índice = região) com o interesse de busca
        total agregado no período consultado."""
        if self.por_regiao.empty:
            raise ValueError("Nenhum dado de interesse por região retornado pelo Google Trends.")
        return self.por_regiao.set_index('Região')['Quantidade']


# ----------------------------------------------------------------------
# Execução direta: demonstração de consulta ao vivo
# ----------------------------------------------------------------------
if __name__ == "__main__":
    try:
        trends = GoogleTrendsPyTrendsLoader()
        print("Série temporal -> shape:", trends.serie_temporal.shape)
        print(trends.get_serie_temporal().tail(5))
        print()
        print("Por região -> shape:", trends.por_regiao.shape)
        print(trends.get_por_regiao().head(5))
    except RuntimeError as erro:
        print(f"Não foi possível consultar o Google Trends agora: {erro}")
