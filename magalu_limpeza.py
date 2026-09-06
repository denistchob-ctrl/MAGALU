

"""
magalu_limpeza.py
===================
Bloco independente de limpeza/higienização dos dados carregados pelo
"magalu_loader.py" (MagaluDataLoader). Pensado para ser chamado logo após
a carga da planilha, dentro da rotina "main":

    from magalu_loader import MagaluDataLoader
    from magalu_limpeza import limpar_loader

    loader = MagaluDataLoader("RESULTADO_2T26_POR.xlsx")
    relatorios = limpar_loader(loader)   # limpa loader.dados "in place"

O que esse módulo faz, hoje:
------------------------------
1. Remove o complemento "REAPRESENTADO" de qualquer cabeçalho de período,
   mantendo apenas o rótulo do período em si.
   Ex.: "3T23\\nReapresentado"          -> "3T23"
        "3T23 Ajustado\\nReapresentado" -> "3T23 Ajustado"
        "set/23\\nReapresentado"        -> "set/23"
   A busca é feita por padrão de texto (case-insensitive, ignorando
   quebras de linha/espaços extras) e não por uma lista fixa de trimestres
   — se uma versão futura da planilha trouxer outro período reapresentado,
   a limpeza já cobre o caso automaticamente.

2. Normaliza cabeçalhos que vêm como "mês/ano" (ex.: "mar/22", "dez/22")
   para o mesmo formato de data completa usado nas demais colunas da guia,
   assumindo o dia 01. Ex.: "mar/22" -> "01/03/2022".
   Aplica-se a QUALQUER guia (não só Balanço Patrimonial e Capital de Giro
   Ajustado), então cobre automaticamente o mesmo problema se aparecer em
   outra aba no futuro.

3. Remove colunas totalmente vazias (sem nenhum valor em toda a guia) —
   normalmente são colunas "separadoras" que aparecem entre blocos da
   planilha original (ex.: entre os trimestres e os totais anuais).

4. Zera (substitui NaN/"(vazio)" por 0) os indicadores configurados em
   CONFIG_ZERAR_VAZIOS, quando o "vazio" na planilha original significa
   "não existia esse valor no período" (ex.: uma linha de despesa que só
   passou a existir a partir de determinado trimestre, ou uma carteira de
   crédito que só existe a partir de certa data). Isso é intencionalmente
   configurável por guia/indicador (veja CONFIG_ZERAR_VAZIOS logo abaixo),
   porque zerar um valor ausente só faz sentido quando "ausente = zero" —
   não deve ser aplicado indiscriminadamente em toda a planilha.

Como o módulo foi construído para crescer: novas regras de limpeza podem
ser adicionadas como novas funções "_regra_xxx(df, relatorio, nome_guia)"
e registradas na lista REGRAS_DE_LIMPEZA, sem precisar mexer no restante
do fluxo.
"""

import re
import numpy as np
import pandas as pd


# ----------------------------------------------------------------------
# Configuração: quais indicadores devem ter seus valores vazios (NaN)
# substituídos por zero.
#
#   - chave   = nome exato da guia (o mesmo retornado por loader.listar_guias())
#   - valor   = lista de substrings (case-insensitive) que identificam os
#               indicadores a zerar dentro daquela guia, OU None para zerar
#               TODOS os indicadores restantes da guia.
#
# Adicione novas entradas aqui conforme for encontrando outros casos ao
# revisar os .txt gerados pelo magalu_export_txt.py.
# ----------------------------------------------------------------------
CONFIG_ZERAR_VAZIOS = {
    "2.1 Ajustes Não Recorrentes": None # zera qualquer indicador com valor vazio nesta guia
    ,"4. Balanço Patrimonial": None  # zera qualquer indicador com valor vazio nesta guia
    ,"7. Fluxo de Caixa Gerencial": None  # zera qualquer indicador com valor vazio nesta guia
    ,"8. Fluxo de Caixa Ajustado": None  # zera qualquer indicador com valor vazio nesta guia
    ,"12. Vendas e Lojas por Canal": None  # zera qualquer indicador com valor vazio nesta guia
}

# ----------------------------------------------------------------------
# Configuração: quais indicadores têm células preenchidas literalmente com
# o texto "-" (traço) em vez do número zero — erro de formatação/exportação
# da planilha de origem. Mesma lógica de chave/valor do CONFIG_ZERAR_VAZIOS
# acima (lista de substrings, ou None para a guia inteira).
#
# Obs.: NÃO coloquei aqui, por padrão, guias como "15. DRE Proforma" (onde
# "-" aparece em indicadores de margem, ex.: Margem Bruta da Seguradora em
# 4T23) porque nesses casos o traço normalmente significa "não aplicável"
# (ex.: divisão por receita zero), e não necessariamente "o valor é zero".
# Avalie caso a caso antes de incluir esse tipo de indicador aqui.
# ----------------------------------------------------------------------
CONFIG_TRACO_PARA_ZERO = {
    "5. Capital de Giro Ajustado": ["repasses e outros depósitos"]
    , "15. DRE Proforma": ["margem bruta", "margem ebitda", "margem líquida"]
}


# Palavra-chave que identifica um período que foi reapresentado.
# (case-insensitive; cobre variações com espaço(s) e/ou quebra(s) de linha antes dela)
PADRAO_REAPRESENTADO = re.compile(r'\s*reapresentad[oa]\s*', flags=re.IGNORECASE)

# Cabeçalho no formato "mês/ano" abreviado em português, ex.: "mar/22", "dez/22"
MESES_PT = {
    'jan': 1, 'fev': 2, 'mar': 3, 'abr': 4, 'mai': 5, 'jun': 6,
    'jul': 7, 'ago': 8, 'set': 9, 'out': 10, 'nov': 11, 'dez': 12,
}
PADRAO_MES_ANO = re.compile(r'^\s*([a-zA-ZçÇ]{3})/(\d{2})\s*$')


# ----------------------------------------------------------------------
# Utilidades gerais
# ----------------------------------------------------------------------

def _rotulos_diferentes(antigo, novo):
    """Compara dois rótulos de coluna tratando NaN/None como iguais entre si
    (evita falso positivo do tipo 'nan -> nan' no relatório)."""
    def _vazio(x):
        return x is None or (isinstance(x, float) and np.isnan(x))

    if isinstance(antigo, tuple) or isinstance(novo, tuple):
        antigo_t = antigo if isinstance(antigo, tuple) else (antigo,)
        novo_t = novo if isinstance(novo, tuple) else (novo,)
        if len(antigo_t) != len(novo_t):
            return True
        return any(_rotulos_diferentes(a, n) for a, n in zip(antigo_t, novo_t))

    if _vazio(antigo) and _vazio(novo):
        return False
    return antigo != novo


def _aplicar_em_rotulo(coluna, funcao_texto):
    """Aplica 'funcao_texto' a um rótulo de coluna, incluindo colunas MultiIndex
    (aplica em cada parte da tupla que for string)."""
    if isinstance(coluna, tuple):
        return tuple(
            funcao_texto(parte) if isinstance(parte, str) else parte
            for parte in coluna
        )
    if isinstance(coluna, str):
        return funcao_texto(coluna)
    return coluna


def _renomear_colunas(df, relatorio, funcao_texto):
    """Percorre as colunas de df, aplica 'funcao_texto' a cada rótulo e
    registra no relatório o que mudou. Devolve o df com as colunas renomeadas."""
    novas_colunas = []
    for coluna in df.columns:
        nova = _aplicar_em_rotulo(coluna, funcao_texto)
        if _rotulos_diferentes(coluna, nova):
            relatorio['cabecalhos_renomeados'].append((coluna, nova))
        novas_colunas.append(nova)
    df = df.copy()
    df.columns = pd.Index(novas_colunas) if not isinstance(df.columns, pd.MultiIndex) \
        else pd.MultiIndex.from_tuples(novas_colunas, names=df.columns.names)
    return df


# ----------------------------------------------------------------------
# Regras de limpeza individuais
# Cada regra tem a assinatura (df, relatorio, nome_guia) -> df
# ----------------------------------------------------------------------

def _texto_sem_reapresentado(texto):
    novo = PADRAO_REAPRESENTADO.sub(' ', texto)
    novo = re.sub(r'\s+', ' ', novo).strip()
    return novo if novo else texto  # nunca devolve string vazia


def _regra_remover_reapresentado(df, relatorio, nome_guia):
    """Limpa o complemento 'REAPRESENTADO' dos cabeçalhos de período."""
    return _renomear_colunas(df, relatorio, _texto_sem_reapresentado)


def _texto_mes_ano_para_data(texto):
    m = PADRAO_MES_ANO.match(texto)
    if not m:
        return texto
    mes_abrev, ano_2digitos = m.group(1).lower(), m.group(2)
    if mes_abrev not in MESES_PT:
        return texto
    mes = MESES_PT[mes_abrev]
    ano = 2000 + int(ano_2digitos)
    return f"01/{mes:02d}/{ano}"


def _regra_normalizar_mes_ano(df, relatorio, nome_guia):
    """Converte cabeçalhos no formato 'mar/22' para o formato de data completa
    usado nas demais colunas da guia (ex.: '01/03/2022'), assumindo dia 01."""
    return _renomear_colunas(df, relatorio, _texto_mes_ano_para_data)


def _regra_remover_colunas_vazias(df, relatorio, nome_guia):
    """Remove colunas 100% vazias (normalmente colunas 'separadoras' sem rótulo).
    Trabalha por posição (iloc), não por rótulo, para funcionar mesmo quando há
    colunas com rótulos duplicados (ex.: várias colunas 'nan')."""
    mask_vazia = df.isna().all(axis=0)
    posicoes_vazias = [i for i, vazia in enumerate(mask_vazia.tolist()) if vazia]
    if posicoes_vazias:
        colunas_removidas = [df.columns[i] for i in posicoes_vazias]
        relatorio['colunas_removidas'].extend(colunas_removidas)
        posicoes_manter = [i for i in range(df.shape[1]) if i not in posicoes_vazias]
        df = df.iloc[:, posicoes_manter]
    return df


def _regra_converter_traco_para_zero(df, relatorio, nome_guia):
    """Substitui células cujo CONTEÚDO é literalmente o texto '-' por 0,
    nos indicadores configurados em CONFIG_TRACO_PARA_ZERO (erro comum de
    formatação/exportação de planilhas financeiras: usar '-' no lugar de 0)."""
    if nome_guia not in CONFIG_TRACO_PARA_ZERO:
        return df

    filtro_substrings = CONFIG_TRACO_PARA_ZERO[nome_guia]

    if filtro_substrings is None:
        indices_alvo = list(range(len(df.index)))
    else:
        filtro_lower = [s.lower() for s in filtro_substrings]
        indices_alvo = [
            i for i, rotulo in enumerate(df.index)
            if any(sub in str(rotulo).lower() for sub in filtro_lower)
        ]

    if not indices_alvo:
        return df

    df = df.copy()
    for i in indices_alvo:
        linha = df.iloc[i]
        mascara_traco = linha.apply(lambda v: isinstance(v, str) and v.strip() == '-')
        n_tracos = int(mascara_traco.sum())
        if n_tracos > 0:
            nova_linha = linha.copy()
            nova_linha[mascara_traco] = 0
            df.iloc[i] = nova_linha
            relatorio['tracos_convertidos'].append((df.index[i], n_tracos))
    return df


def _regra_zerar_vazios_configurados(df, relatorio, nome_guia):
    """Substitui NaN por 0 nos indicadores configurados em CONFIG_ZERAR_VAZIOS
    para a guia atual (veja a configuração no topo do arquivo)."""
    if nome_guia not in CONFIG_ZERAR_VAZIOS:
        return df

    filtro_substrings = CONFIG_ZERAR_VAZIOS[nome_guia]

    if filtro_substrings is None:
        indices_alvo = list(range(len(df.index)))
    else:
        filtro_lower = [s.lower() for s in filtro_substrings]
        indices_alvo = [
            i for i, rotulo in enumerate(df.index)
            if any(sub in str(rotulo).lower() for sub in filtro_lower)
        ]

    if not indices_alvo:
        return df

    df = df.copy()
    for i in indices_alvo:
        linha = df.iloc[i]
        n_vazios = int(linha.isna().sum())
        if n_vazios > 0:
            df.iloc[i] = linha.fillna(0)
            relatorio['valores_zerados'].append((df.index[i], n_vazios))
    return df


# Ordem em que as regras são aplicadas. Para adicionar uma nova regra de
# limpeza no futuro, basta escrever uma função no mesmo padrão
# (df, relatorio, nome_guia) -> df e incluí-la nesta lista.
REGRAS_DE_LIMPEZA = [
    _regra_remover_reapresentado,
    _regra_normalizar_mes_ano,
    _regra_converter_traco_para_zero,
    _regra_remover_colunas_vazias,
    _regra_zerar_vazios_configurados,
]


# ----------------------------------------------------------------------
# Funções públicas
# ----------------------------------------------------------------------

def limpar_dataframe(df, nome_guia=None):
    """
    Aplica todas as regras de limpeza a um único DataFrame (uma guia) e
    devolve (df_limpo, relatorio), onde relatorio é um dicionário com o
    que foi alterado, por exemplo:

        {
          'guia': '1. Indicadores',
          'cabecalhos_renomeados': [('3T23\\nReapresentado', '3T23')],
          'colunas_removidas': [nan],
          'tracos_convertidos': [('(-) Repasses e Outros Depósitos', 2)],
          'valores_zerados': [('Despesas reestruturação e integração', 12)],
        }
    """
    relatorio = {
        'guia': nome_guia,
        'cabecalhos_renomeados': [],
        'colunas_removidas': [],
        'tracos_convertidos': [],
        'valores_zerados': [],
    }
    df_limpo = df
    for regra in REGRAS_DE_LIMPEZA:
        df_limpo = regra(df_limpo, relatorio, nome_guia)
    return df_limpo, relatorio


def limpar_loader(loader, verbose=True):
    """
    Aplica a limpeza em TODAS as guias já carregadas por um MagaluDataLoader,
    atualizando "in place" loader.dados, loader.colunas e loader.arrays.

    Retorna uma lista de relatórios (um por guia) para você conferir o que
    foi ajustado.
    """
    relatorios = []

    for nome_guia in loader.listar_guias():
        df_original = loader.dados[nome_guia]
        df_limpo, relatorio = limpar_dataframe(df_original, nome_guia=nome_guia)

        loader.dados[nome_guia] = df_limpo
        loader.colunas[nome_guia] = list(df_limpo.columns)
        # construído por posição (iloc) para funcionar mesmo com rótulos de
        # indicador duplicados dentro da mesma guia
        loader.arrays[nome_guia] = {
            df_limpo.index[i]: df_limpo.iloc[i].to_numpy()
            for i in range(len(df_limpo.index))
        }

        relatorios.append(relatorio)

        houve_mudanca = (relatorio['cabecalhos_renomeados']
                          or relatorio['colunas_removidas']
                          or relatorio['tracos_convertidos']
                          or relatorio['valores_zerados'])
        if verbose and houve_mudanca:
            print(f"[limpeza] Guia '{nome_guia}':")
            for antigo, novo in relatorio['cabecalhos_renomeados']:
                print(f"    cabeçalho renomeado: {antigo!r}  ->  {novo!r}")
            if relatorio['colunas_removidas']:
                print(f"    {len(relatorio['colunas_removidas'])} coluna(s) vazia(s) removida(s)")
            for indicador, n in relatorio['tracos_convertidos']:
                print(f"    '{indicador}': {n} traço(s) '-' convertido(s) para 0")
            for indicador, n in relatorio['valores_zerados']:
                print(f"    '{indicador}': {n} valor(es) vazio(s) zerado(s)")

    return relatorios


# ----------------------------------------------------------------------
# Execução direta: demonstração da limpeza
# ----------------------------------------------------------------------
if __name__ == "__main__":
    from magalu_loader import MagaluDataLoader

    loader = MagaluDataLoader("RESULTADO_2T26_POR.xlsx")
    print(f"Antes da limpeza -> '4. Balanço Patrimonial' tem "
          f"{loader.dados['4. Balanço Patrimonial'].shape[1]} colunas")

    relatorios = limpar_loader(loader)

    print(f"Depois da limpeza -> '4. Balanço Patrimonial' tem "
          f"{loader.dados['4. Balanço Patrimonial'].shape[1]} colunas")
    print()
    print("Resumo geral:")
    for r in relatorios:
        if r['cabecalhos_renomeados'] or r['colunas_removidas'] or r['valores_zerados']:
            print(f" - {r['guia']}: {len(r['cabecalhos_renomeados'])} cabeçalho(s) ajustado(s), "
                  f"{len(r['colunas_removidas'])} coluna(s) vazia(s) removida(s), "
                  f"{len(r['valores_zerados'])} indicador(es) zerado(s)")
