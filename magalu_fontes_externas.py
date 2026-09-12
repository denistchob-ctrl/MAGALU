"""
magalu_fontes_externas.py
===========================
Carregadores para as fontes de dados COMPLEMENTARES à planilha de resultados
(RESULTADO_2T26_POR.xlsx), usadas para enriquecer a análise de evolução do
Magazine Luiza: cotação da ação e reputação/reclamações (Reclame Aqui).

Todos os arquivos são procurados, por padrão, dentro da pasta "BD" (mesma
pasta usada pelo MagaluDataLoader) — basta soltar novos arquivos lá que os
carregadores já enxergam, sem precisar alterar código (veja o comentário de
cada classe para o padrão de nome de arquivo esperado).

Uso básico:
-----------
    from magalu_fontes_externas import (
        CotacaoAcaoLoader,
        ReclameAquiLoader,
    )

    cotacao = CotacaoAcaoLoader()
    cotacao.df                                  # DataFrame diário completo (índice = Data)
    cotacao.get_serie("Fechamento")              # pandas Series só com o fechamento

    ra = ReclameAquiLoader()
    ra.listar_empresas()                          # ['consorcio', 'fisica', 'luizacred', 'online']
    ra.listar_categorias("online")                # ['categorias', 'desempenho', 'problemas', 'produtos']
    ra.get("online", "desempenho")                # DataFrame daquela empresa/categoria
    ra.categorias("fisica") / ra.problemas("fisica") / ra.produtos("fisica") / ra.desempenho("fisica")


Localização flexível de arquivo (espaço x underscore):
--------------------------------------------------------
Os nomes "auto-explicativos" desses arquivos às vezes têm espaço e às vezes
underscore no lugar do espaço (isso já aconteceu na prática: o histórico de
cotações veio, num momento, com espaço, e
o código esperava underscore — e vice-versa). Por isso a localização de
arquivo aqui é tolerante a essa diferença (e também a maiúscula/minúscula e
a acentos): "Histórico_de_Cotações_...xlsx" e "Histórico de Cotações...xlsx"
são tratados como o mesmo arquivo. Veja _normalizar_nome_arquivo().

Arquivos esperados na pasta "BD":
------------------------------------------------------------------------
- Histórico de Cotações <...>.xlsx (ou com underscore no lugar do espaço)
    Aba "Historical", exportação típica do Investing.com, com colunas em
    formato brasileiro (texto com vírgula decimal, ponto de milhar, "%").

- RA-<empresa>-<categoria>.csv
    Exportações do Reclame Aqui, uma por empresa/categoria, ex.:
    RA-consorcio-categorias.csv, RA-fisica-desempenho.csv,
    RA-online-problemas.csv, RA-luizacred-produtos.csv, etc.
    <empresa> observadas até agora: consorcio, fisica, online, luizacred
    (esta última também aparece grafada "luizcred" em alguns arquivos —
    tratado como sinônimo, veja ALIAS_EMPRESA).
    <categoria> observadas até agora: categorias, problemas, produtos,
    desempenho.
    O carregador também descobre esses arquivos por padrão de nome (não por
    uma lista fixa de empresas/categorias), então novas empresas ou
    categorias que apareçam no futuro, seguindo o mesmo padrão de nome
    "RA-<empresa>-<categoria>.csv", já são carregadas automaticamente.
"""

import os
import re
import glob
import unicodedata

import numpy as np
import pandas as pd
import openpyxl


PASTA_DADOS_PADRAO = "BD"


# ----------------------------------------------------------------------
# Utilidades gerais
# ----------------------------------------------------------------------

def _caminho(nome_arquivo, pasta_dados):
    return os.path.join(pasta_dados, nome_arquivo)


def _normalizar_nome_arquivo(nome):
    """Normaliza um nome de arquivo para fins de COMPARAÇÃO (não usar o
    resultado para abrir arquivo nenhum): minúsculas, sem acento, e trata
    espaço/underscore/hífen como equivalentes. Assim, "Histórico_de_Cotações"
    e "Histórico de Cotações" batem como o mesmo nome."""
    nome = nome.lower()
    nome = unicodedata.normalize('NFKD', nome)
    nome = ''.join(ch for ch in nome if not unicodedata.combining(ch))
    nome = re.sub(r'[\s_]+', ' ', nome)
    return nome.strip()


def _encontrar_arquivo(pasta_dados, nome_esperado):
    """Localiza, dentro de pasta_dados, um arquivo cujo nome bate com
    nome_esperado — tentando primeiro o caminho exato e, se não existir,
    procurando por uma variação com espaço/underscore/acentuação diferente.
    Lança FileNotFoundError com uma mensagem clara se não encontrar nada."""
    caminho_exato = os.path.join(pasta_dados, nome_esperado)
    if os.path.exists(caminho_exato):
        return caminho_exato

    alvo_normalizado = _normalizar_nome_arquivo(nome_esperado)
    if os.path.isdir(pasta_dados):
        for nome_real in os.listdir(pasta_dados):
            if _normalizar_nome_arquivo(nome_real) == alvo_normalizado:
                return os.path.join(pasta_dados, nome_real)

    raise FileNotFoundError(
        f"Não encontrei o arquivo '{nome_esperado}' (nem uma variação com "
        f"espaço/underscore/acento diferente) dentro da pasta '{pasta_dados}'."
    )


def _listar_arquivos_por_prefixo(pasta_dados, prefixo, extensao):
    """Lista, dentro de pasta_dados, todos os arquivos com a extensão dada
    cujo nome COMEÇA com 'prefixo', tolerando diferença de espaço/underscore/
    acentuação entre o prefixo esperado e o nome real do arquivo."""
    if not os.path.isdir(pasta_dados):
        return []

    prefixo_normalizado = _normalizar_nome_arquivo(prefixo)
    encontrados = []
    for nome_real in os.listdir(pasta_dados):
        if not nome_real.lower().endswith(extensao.lower()):
            continue
        if _normalizar_nome_arquivo(nome_real).startswith(prefixo_normalizado):
            encontrados.append(os.path.join(pasta_dados, nome_real))

    return sorted(encontrados)


def _para_float_brasileiro(texto):
    """Converte um texto em formato numérico brasileiro (ex.: '1.234,56', '-1,14%',
    '3.230') para float. Valores vazios, None ou '-' viram NaN. Percentuais são
    devolvidos como fração (ex.: '-1,14%' -> -0.0114), para ficarem na mesma
    escala usada no restante do projeto (veja magalu_loader/magalu_limpeza)."""
    if texto is None:
        return np.nan
    if isinstance(texto, (int, float, np.integer, np.floating)):
        return float(texto)

    s = str(texto).strip()
    if s == '' or s == '-':
        return np.nan

    eh_percentual = s.endswith('%')
    if eh_percentual:
        s = s[:-1].strip()

    s = s.replace('.', '').replace(',', '.')  # milhar/decimal -> padrão internacional

    try:
        valor = float(s)
    except ValueError:
        return np.nan

    return valor / 100 if eh_percentual else valor


# ----------------------------------------------------------------------
# 1) Cotação da ação (MGLU3)
# ----------------------------------------------------------------------
class CotacaoAcaoLoader:
    """
    Carrega o histórico diário de cotações da ação (arquivo exportado no
    formato Investing.com: colunas DATA, ABE, MAX, MIN, FEC, MED, VAR%,
    # NEG, VOLFIN, QUANT, em formato numérico brasileiro).

    Resultado fica em self.df: DataFrame indexado por Data (datetime,
    ordenado do mais antigo para o mais recente), com colunas já numéricas:
        Abertura, Maxima, Minima, Fechamento, Medio, Variacao_Pct,
        Num_Negocios, Volume_Financeiro, Quantidade
    """

    COLUNAS_ORIGINAIS_PARA_FINAIS = {
        'ABE': 'Abertura',
        'MAX': 'Maxima',
        'MIN': 'Minima',
        'FEC': 'Fechamento',
        'MED': 'Medio',
        'VAR%': 'Variacao_Pct',
        '# NEG': 'Num_Negocios',
        'VOLFIN': 'Volume_Financeiro',
        'QUANT': 'Quantidade',
    }

    def __init__(self, nome_arquivo="Histórico de Cotações 01-01-2018 a 31-07-2026.xlsx",
                 pasta_dados=PASTA_DADOS_PADRAO, aba="Historical"):
        self.pasta_dados = pasta_dados
        self.caminho = _encontrar_arquivo(pasta_dados, nome_arquivo)
        self.aba = aba
        self.df = self._carregar()

    def _carregar(self):
        wb = openpyxl.load_workbook(self.caminho, data_only=True)
        ws = wb[self.aba]

        cabecalho = [str(c.value).strip() if c.value is not None else None for c in ws[1]]

        registros = []
        for linha in ws.iter_rows(min_row=2, values_only=True):
            valor_data = linha[0]
            if valor_data is None or str(valor_data).strip() == '':
                continue
            registro = dict(zip(cabecalho, linha))
            registros.append(registro)

        df = pd.DataFrame(registros)

        df['Data'] = pd.to_datetime(df['DATA'], format='%d/%m/%y', dayfirst=True)

        for col_original, col_final in self.COLUNAS_ORIGINAIS_PARA_FINAIS.items():
            if col_original in df.columns:
                df[col_final] = df[col_original].apply(_para_float_brasileiro)

        colunas_finais = ['Data'] + list(self.COLUNAS_ORIGINAIS_PARA_FINAIS.values())
        df = df[[c for c in colunas_finais if c in df.columns]]
        df = df.set_index('Data').sort_index()
        return df

    def get_serie(self, coluna="Fechamento"):
        """Devolve uma pandas Series (indexada por data) de uma das colunas
        (Abertura, Maxima, Minima, Fechamento, Medio, Variacao_Pct,
        Num_Negocios, Volume_Financeiro, Quantidade)."""
        if coluna not in self.df.columns:
            raise KeyError(f"Coluna '{coluna}' não encontrada. Disponíveis: {list(self.df.columns)}")
        return self.df[coluna]


# ----------------------------------------------------------------------
# 3) Reclame Aqui
# ----------------------------------------------------------------------
class ReclameAquiLoader:
    """
    Carrega TODOS os arquivos "RA-<empresa>-<categoria>.csv" encontrados na
    pasta de dados. Hoje existem 4 empresas (consorcio, fisica, online,
    luizacred) x 4 categorias (categorias, problemas, produtos, desempenho),
    mas a descoberta é automática por padrão de nome — se amanhã aparecer
    uma empresa ou categoria nova seguindo o mesmo padrão de nome de
    arquivo, ela já entra na carga sem precisar alterar este código.

    Resultado fica em self.dados: dict aninhado
        self.dados[empresa][categoria] -> DataFrame

    onde 'empresa' já vem normalizada (minúscula, sem inconsistências de
    grafia conhecidas — ex.: "luizcred" e "luizacred" caem na mesma chave
    "luizacred", veja ALIAS_EMPRESA) e 'categoria' também em minúsculas
    (categorias, problemas, produtos, desempenho).

    Métodos de conveniência: listar_empresas(), listar_categorias(empresa),
    get(empresa, categoria), e os atalhos categorias(empresa),
    problemas(empresa), produtos(empresa), desempenho(empresa).
    """

    # Grafias alternativas já observadas nos nomes de arquivo, mapeadas para
    # o nome "canônico" da empresa. Adicione aqui se aparecer outra variação.
    ALIAS_EMPRESA = {
        'luizcred': 'luizacred',
    }

    COLUNAS_PERCENTUAIS_OU_NUMERICAS_DESEMPENHO = [
        'Nota Média',
        'Reclamações Recebidas',
        'Reclamações Respondidas',
        'Aguardando Resposta',
        'Reclamações Resolvidas',
        'Voltariam a fazer negócio',
        'Reclamações Avaliadas',
        'Nota média do consumidor',
    ]

    def __init__(self, pasta_dados=PASTA_DADOS_PADRAO, prefixo="RA-"):
        self.pasta_dados = pasta_dados
        self.prefixo = prefixo
        self.dados = {}  # dados[empresa][categoria] -> DataFrame
        self._carregar()

    def _normalizar_empresa(self, nome_empresa):
        nome_empresa = nome_empresa.strip().lower()
        return self.ALIAS_EMPRESA.get(nome_empresa, nome_empresa)

    def _interpretar_nome_arquivo(self, nome_arquivo):
        """'RA-consorcio-categorias.csv' -> ('consorcio', 'categorias').
        Devolve (None, None) se o nome não seguir o padrão esperado."""
        base = os.path.splitext(nome_arquivo)[0]
        partes = base.split('-')
        if len(partes) < 3 or partes[0].upper() != 'RA':
            return None, None
        empresa = self._normalizar_empresa(partes[1])
        categoria = '-'.join(partes[2:]).strip().lower()
        return empresa, categoria

    def _ler_categoria_simples(self, caminho):
        return pd.read_csv(caminho, sep=';', encoding='utf-8')

    def _ler_desempenho(self, caminho):
        df = pd.read_csv(caminho, sep=';', encoding='utf-8', dtype=str)
        for coluna in self.COLUNAS_PERCENTUAIS_OU_NUMERICAS_DESEMPENHO:
            if coluna in df.columns:
                df[coluna] = df[coluna].apply(_para_float_brasileiro)
        if 'Desempenho' in df.columns:
            df = df.set_index('Desempenho')
        return df

    def _carregar(self):
        padrao = os.path.join(self.pasta_dados, f"{self.prefixo}*.csv")
        for caminho in sorted(glob.glob(padrao)):
            nome_arquivo = os.path.basename(caminho)
            empresa, categoria = self._interpretar_nome_arquivo(nome_arquivo)
            if empresa is None:
                continue

            if categoria == 'desempenho':
                df = self._ler_desempenho(caminho)
            else:
                df = self._ler_categoria_simples(caminho)

            self.dados.setdefault(empresa, {})[categoria] = df

    # ------------------------------------------------------------------
    # Consulta
    # ------------------------------------------------------------------
    def listar_empresas(self):
        """Lista as empresas/unidades encontradas (ex.: ['consorcio', 'fisica', 'luizacred', 'online'])."""
        return sorted(self.dados.keys())

    def listar_categorias(self, empresa):
        """Lista as categorias disponíveis para uma empresa (ex.: ['categorias', 'desempenho', 'problemas', 'produtos'])."""
        empresa = self._normalizar_empresa(empresa)
        self._validar_empresa(empresa)
        return sorted(self.dados[empresa].keys())

    def get(self, empresa, categoria):
        """Devolve o DataFrame de uma empresa/categoria específica."""
        empresa = self._normalizar_empresa(empresa)
        self._validar_empresa(empresa)
        categoria = categoria.strip().lower()
        if categoria not in self.dados[empresa]:
            raise KeyError(
                f"Categoria '{categoria}' não encontrada para a empresa '{empresa}'. "
                f"Disponíveis: {self.listar_categorias(empresa)}"
            )
        return self.dados[empresa][categoria]

    def categorias(self, empresa):
        return self.get(empresa, 'categorias')

    def problemas(self, empresa):
        return self.get(empresa, 'problemas')

    def produtos(self, empresa):
        return self.get(empresa, 'produtos')

    def desempenho(self, empresa):
        return self.get(empresa, 'desempenho')

    def _validar_empresa(self, empresa):
        if empresa not in self.dados:
            raise KeyError(f"Empresa '{empresa}' não encontrada. Disponíveis: {self.listar_empresas()}")


# ----------------------------------------------------------------------
# Execução direta: demonstração de carga das três fontes
# ----------------------------------------------------------------------
if __name__ == "__main__":
    cotacao = CotacaoAcaoLoader()
    print("Cotação -> shape:", cotacao.df.shape)
    print(cotacao.df.tail(3))
    print()

    ra = ReclameAquiLoader()
    print("Reclame Aqui - empresas encontradas:", ra.listar_empresas())
    for empresa in ra.listar_empresas():
        print(f"  {empresa}: {ra.listar_categorias(empresa)}")
    print()
    print("Reclame Aqui - categorias (fisica):")
    print(ra.categorias("fisica").head(3))
    print()
    print("Reclame Aqui - desempenho (luizacred):")
    print(ra.desempenho("luizacred"))
