"""
inventario_dados.py
====================
Gera um "inventário" do que existe em cada fonte de dados do projeto MAGALU,
SEM os valores numéricos: apenas quais itens (indicadores/colunas/séries)
existem e quais períodos cada item cobre.

Fontes inventariadas:
  1. DRE (planilha RESULTADO_2T26_POR.xlsx) — todas as guias, formato WIDE.
  2. Cotações da ação — formato LONG + resumo.
  3. Reclame Aqui — formato LONG.
  4. Google Trends:
       a) série mensal agregada (loader live, backup 'ultimaLeituraGA.csv')
       b) região ANO A ANO (loader anual, consolidado
          'GA_porRegiao_ano_a_ano.csv')
       c) região AGREGADA (derivada do consolidado — soma de todos os anos
          por região; SUBSTITUI o antigo 'ultimaLeituraGAporRegiao.csv')
     Nenhuma das visões sobrescreve a outra — cada uma tem seu próprio
     arquivo de backup e seu próprio propósito.

Saída (pasta "inventario/"):
  - inventario_dre.csv                          (WIDE)
  - inventario_cotacao.csv                      (LONG)
  - inventario_cotacao_resumo.csv               (resumo)
  - inventario_reclame_aqui.csv                 (LONG)
  - inventario_google_trends_temporal.csv       (LONG: mensal)
  - inventario_google_trends_regional_anual.csv (LONG: Ano × Região)
  - inventario_google_trends_regional_agregada.csv (LONG: Região agregada)
  - inventario_google_trends_ano_regiao_wide.csv   (WIDE, opcional)

Uso:
    python inventario_dados.py
"""

import os
import re

import numpy as np
import pandas as pd

from magalu_loader import MagaluDataLoader
from magalu_limpeza import limpar_loader
from magalu_fontes_externas import CotacaoAcaoLoader, ReclameAquiLoader
from magalu_google_trends_live import GoogleTrendsPyTrendsLoader
from magalu_google_trends_anual import GoogleTrendsPorRegiaoAnual

PASTA_SAIDA = "inventario"
NOME_PLANILHA_DRE = "RESULTADO_2T26_POR.xlsx"

# Janela de análise do projeto — usada pelo loader anual do Google Trends.
ANO_INICIAL = 2021
ANO_FINAL = 2026


# ----------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------

def _rotulo_coluna(coluna):
    """Achata um rótulo de coluna (str, número, ou tupla de MultiIndex) numa
    string única, legível, para caber numa célula de CSV."""
    if isinstance(coluna, tuple):
        partes = [str(p) for p in coluna if p is not None and str(p) != 'nan']
        return " | ".join(partes) if partes else "(sem rótulo)"
    if coluna is None or (isinstance(coluna, float) and np.isnan(coluna)):
        return "(sem rótulo)"
    return str(coluna)


def _tem_dado(valor):
    """True se a célula tem valor (não é NaN/None)."""
    if valor is None:
        return False
    if isinstance(valor, float) and np.isnan(valor):
        return False
    return True


def _garantir_pasta(caminho):
    os.makedirs(caminho, exist_ok=True)


# ----------------------------------------------------------------------
# 1) DRE — formato WIDE
# ----------------------------------------------------------------------

def _inventario_dre_wide(df, nome_guia):
    """Para uma guia do DRE, devolve um DataFrame com:
       colunas = ['guia', 'indicador', <periodo1>, <periodo2>, ...]
       cada célula de período = 'X' se houver valor, '' se não.
    """
    periodos = [_rotulo_coluna(c) for c in df.columns]

    linhas = []
    for indicador in df.index:
        serie = df.loc[indicador]
        if isinstance(serie, pd.DataFrame):
            serie = serie.iloc[0]

        linha = {'guia': nome_guia, 'indicador': str(indicador)}
        for periodo, valor in zip(periodos, serie.tolist()):
            linha[periodo] = 'X' if _tem_dado(valor) else ''
        linhas.append(linha)

    return pd.DataFrame(linhas)


def _chave_ordenacao_periodo(rotulo):
    """Devolve uma chave para ordenar cronologicamente rótulos de período do
    tipo '1T18', '01/03/2022' ou '1T18 | Valor'."""
    texto = str(rotulo)

    m = re.match(r'^\s*(\d)T(\d{2})', texto)
    if m:
        return (0, int(m.group(2)), int(m.group(1)), texto)

    m = re.match(r'^\s*(\d{2})/(\d{2})/(\d{4})', texto)
    if m:
        return (0, int(m.group(3)), int(m.group(2)), int(m.group(1)), texto)

    return (1, 0, 0, 0, texto)


def gerar_inventario_dre(loader, pasta_saida=PASTA_SAIDA):
    """Gera um único CSV wide com TODAS as guias do DRE empilhadas."""
    _garantir_pasta(pasta_saida)
    frames = []
    for nome_guia in loader.listar_guias():
        df = loader.get_sheet_df(nome_guia)
        frames.append(_inventario_dre_wide(df, nome_guia))

    inventario = pd.concat(frames, ignore_index=True, sort=False)

    colunas_fixas = ['guia', 'indicador']
    colunas_periodo = [c for c in inventario.columns if c not in colunas_fixas]
    colunas_periodo_ordenadas = sorted(
        colunas_periodo,
        key=lambda c: _chave_ordenacao_periodo(c),
    )
    inventario = inventario[colunas_fixas + colunas_periodo_ordenadas]

    caminho = os.path.join(pasta_saida, "inventario_dre.csv")
    inventario.to_csv(caminho, index=False, encoding='utf-8-sig', sep=';')
    print(f"[DRE] {len(inventario)} indicadores x {len(colunas_periodo)} períodos -> {caminho}")
    return caminho


# ----------------------------------------------------------------------
# 2) Cotações
# ----------------------------------------------------------------------

def gerar_inventario_cotacao(cotacao, pasta_saida=PASTA_SAIDA):
    """Gera dois arquivos: long (coluna; data) e resumo (por coluna)."""
    _garantir_pasta(pasta_saida)
    df = cotacao.df

    linhas = []
    for coluna in df.columns:
        serie = df[coluna]
        for data, valor in serie.items():
            if _tem_dado(valor):
                linhas.append({
                    'coluna': coluna,
                    'data': data.strftime('%d/%m/%Y'),
                    'fonte': 'Cotações',
                })
    caminho_long = os.path.join(pasta_saida, "inventario_cotacao.csv")
    pd.DataFrame(linhas).to_csv(caminho_long, index=False, encoding='utf-8-sig', sep=';')

    resumo = []
    for coluna in df.columns:
        serie = df[coluna].dropna()
        if serie.empty:
            resumo.append({'coluna': coluna, 'primeiro': '', 'ultimo': '', 'n_pregões': 0})
        else:
            resumo.append({
                'coluna': coluna,
                'primeiro': serie.index.min().strftime('%d/%m/%Y'),
                'ultimo': serie.index.max().strftime('%d/%m/%Y'),
                'n_pregões': len(serie),
            })
    caminho_resumo = os.path.join(pasta_saida, "inventario_cotacao_resumo.csv")
    pd.DataFrame(resumo).to_csv(caminho_resumo, index=False, encoding='utf-8-sig', sep=';')

    print(f"[Cotações] {df.shape[1]} colunas, {df.shape[0]} pregões -> "
          f"{caminho_long} e {caminho_resumo}")
    return caminho_long, caminho_resumo


# ----------------------------------------------------------------------
# 3) Reclame Aqui
# ----------------------------------------------------------------------

def _inventario_ra_categoria_simples(df, empresa, categoria):
    """Para 'categorias', 'problemas' e 'produtos': uma linha por rótulo."""
    if df.empty:
        return []
    coluna_label = df.columns[0]
    linhas = []
    for valor in df[coluna_label].dropna().unique():
        linhas.append({
            'empresa': empresa,
            'categoria': categoria,
            'item': str(valor),
            'periodo': '(sem período — lista simples)',
            'fonte': 'Reclame Aqui',
        })
    return linhas


def _inventario_ra_desempenho(df, empresa):
    """'desempenho' é transposto: índice = período, colunas = métricas."""
    if df.empty:
        return []
    linhas = []
    for periodo in df.index:
        for metrica in df.columns:
            valor = df.loc[periodo, metrica]
            if _tem_dado(valor):
                linhas.append({
                    'empresa': empresa,
                    'categoria': 'desempenho',
                    'item': str(metrica),
                    'periodo': str(periodo),
                    'fonte': 'Reclame Aqui',
                })
    return linhas


def gerar_inventario_reclame_aqui(ra, pasta_saida=PASTA_SAIDA):
    _garantir_pasta(pasta_saida)
    linhas = []
    for empresa in ra.listar_empresas():
        for categoria in ra.listar_categorias(empresa):
            df = ra.get(empresa, categoria)
            if categoria == 'desempenho':
                linhas.extend(_inventario_ra_desempenho(df, empresa))
            else:
                linhas.extend(_inventario_ra_categoria_simples(df, empresa, categoria))

    inventario = pd.DataFrame(linhas)
    caminho = os.path.join(pasta_saida, "inventario_reclame_aqui.csv")
    inventario.to_csv(caminho, index=False, encoding='utf-8-sig', sep=';')
    print(f"[Reclame Aqui] {len(inventario)} linhas -> {caminho}")
    return caminho


# ----------------------------------------------------------------------
# 4) Google Trends
# ----------------------------------------------------------------------

def gerar_inventario_google_trends(trends, pasta_saida=PASTA_SAIDA):
    """
    Inventaria a série temporal MENSAL do loader live do Google Trends
    (backup 'ultimaLeituraGA.csv').

    A região NÃO é mais inventariada aqui — ela passa a vir do consolidado
    ano a ano (ver gerar_inventario_google_trends_regional_anual), porque
    o antigo 'ultimaLeituraGAporRegiao.csv' era uma 'foto' de um momento
    específico e ficava inconsistente com o consolidado.

    Saída:
      - inventario_google_trends_temporal.csv
    """
    _garantir_pasta(pasta_saida)

    linhas_temporal = []
    if not trends.serie_temporal.empty:
        for _, linha in trends.serie_temporal.iterrows():
            if _tem_dado(linha['Quantidade']):
                linhas_temporal.append({
                    'item': 'Magazine Luiza (interesse de busca mensal)',
                    'periodo': linha['Time'].strftime('%m/%Y'),
                    'fonte': 'Google Trends',
                })
    caminho_temporal = os.path.join(pasta_saida, "inventario_google_trends_temporal.csv")
    pd.DataFrame(linhas_temporal).to_csv(caminho_temporal, index=False,
                                         encoding='utf-8-sig', sep=';')

    print(f"[Google Trends] temporal (mensal): {len(linhas_temporal)} meses -> "
          f"{caminho_temporal}")
    return caminho_temporal


def gerar_inventario_google_trends_regional_anual(ga_anual, pasta_saida=PASTA_SAIDA):
    """
    Inventaria o Google Trends por região, em DUAS visões derivadas do
    consolidado ano a ano:

      - inventario_google_trends_regional_anual.csv
          Formato LONG: uma linha por (Ano, Região).

      - inventario_google_trends_regional_agregada.csv
          Formato LONG: uma linha por Região, com o total agregado de
          todos os anos do consolidado. Substitui o antigo inventário
          baseado em 'ultimaLeituraGAporRegiao.csv'.

    Saída (LONG):
        item; periodo; fonte
    """
    _garantir_pasta(pasta_saida)

    linhas_anual = []
    linhas_agregada = []

    if ga_anual is not None and not ga_anual.df.empty:
        # --- visão ano a ano ---
        for _, linha in ga_anual.df.iterrows():
            if _tem_dado(linha.get("Quantidade")):
                linhas_anual.append({
                    "item": str(linha["Região"]),
                    "periodo": str(int(linha["Ano"])),
                    "fonte": "Google Trends (ano a ano)",
                })

        # --- visão agregada (soma de todos os anos por região) ---
        df_agregada = ga_anual.regiao_agregada(como="soma")
        for _, linha in df_agregada.iterrows():
            if _tem_dado(linha.get("Quantidade")):
                linhas_agregada.append({
                    "item": str(linha["Região"]),
                    "periodo": "(agregado de todos os anos do consolidado)",
                    "fonte": "Google Trends (região agregada)",
                })

    caminho_anual = os.path.join(pasta_saida,
                                 "inventario_google_trends_regional_anual.csv")
    pd.DataFrame(linhas_anual).to_csv(caminho_anual, index=False,
                                      encoding='utf-8-sig', sep=';')

    caminho_agregada = os.path.join(pasta_saida,
                                    "inventario_google_trends_regional_agregada.csv")
    pd.DataFrame(linhas_agregada).to_csv(caminho_agregada, index=False,
                                         encoding='utf-8-sig', sep=';')

    n_anos = len({l["periodo"] for l in linhas_anual}) if linhas_anual else 0
    n_regioes = len({l["item"] for l in linhas_anual}) if linhas_anual else 0
    print(f"[Google Trends] região ano a ano: {len(linhas_anual)} linhas "
          f"({n_anos} ano(s) × {n_regioes} região(ões)) -> {caminho_anual}")
    print(f"[Google Trends] região agregada: {len(linhas_agregada)} linhas -> "
          f"{caminho_agregada}")

    return caminho_anual, caminho_agregada


def gerar_inventario_google_trends_matriz_wide(ga_anual, pasta_saida=PASTA_SAIDA):
    """Gera uma visão WIDE do consolidado ano × região, com 'X' onde há dado.
    Uma linha por ano; colunas = regiões. Útil para conferência visual."""
    _garantir_pasta(pasta_saida)

    if ga_anual is None or ga_anual.df.empty:
        print("[Google Trends anual WIDE] Sem dados — nada a gerar.")
        return None

    matriz = ga_anual.df.pivot(index="Ano", columns="Região", values="Quantidade")
    matriz_x = matriz.notna().replace({True: "X", False: ""})
    matriz_x.index = matriz_x.index.astype(int)
    matriz_x = matriz_x.sort_index()

    caminho = os.path.join(pasta_saida,
                           "inventario_google_trends_ano_regiao_wide.csv")
    matriz_x.to_csv(caminho, encoding='utf-8-sig', sep=';')
    print(f"[Google Trends anual WIDE] {matriz_x.shape[0]} ano(s) × "
          f"{matriz_x.shape[1]} região(ões) -> {caminho}")
    return caminho


# ----------------------------------------------------------------------
# main
# ----------------------------------------------------------------------

def main():
    _garantir_pasta(PASTA_SAIDA)

    print("Carregando DRE...")
    loader = MagaluDataLoader(NOME_PLANILHA_DRE)
    limpar_loader(loader, verbose=False)
    gerar_inventario_dre(loader)

    print("Carregando Cotações...")
    try:
        cotacao = CotacaoAcaoLoader()
        gerar_inventario_cotacao(cotacao)
    except Exception as e:
        print(f"  [!] Cotações indisponíveis: {e}")

    print("Carregando Reclame Aqui...")
    try:
        ra = ReclameAquiLoader()
        gerar_inventario_reclame_aqui(ra)
    except Exception as e:
        print(f"  [!] Reclame Aqui indisponível: {e}")

    print("Carregando Google Trends (série mensal)...")
    try:
        trends = GoogleTrendsPyTrendsLoader(termos=["Magazine Luiza"])
        gerar_inventario_google_trends(trends)
    except Exception as e:
        print(f"  [!] Google Trends indisponível: {e}")

    print("Carregando Google Trends (região ano a ano)...")
    try:
        ga_anual = GoogleTrendsPorRegiaoAnual(
            ano_inicio=ANO_INICIAL,
            ano_fim=ANO_FINAL,
            termos=["Magazine Luiza"],
            apenas_ano_corrente_ao_vivo=True,
            pausa_entre_anos=15,
        )
        gerar_inventario_google_trends_regional_anual(ga_anual)
        gerar_inventario_google_trends_matriz_wide(ga_anual)
    except Exception as e:
        print(f"  [!] Google Trends (ano a ano) indisponível: {e}")

    print("\nPronto. Arquivos em:", os.path.abspath(PASTA_SAIDA))


if __name__ == "__main__":
    main()