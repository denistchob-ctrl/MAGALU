"""
magalu_export_txt.py
=====================
Módulo complementar ao "magalu_loader.py". Gera, para CADA guia da planilha
de resultados do Magazine Luiza, um arquivo .txt legível com todo o conteúdo
capturado pelo carregador — útil para conferir visualmente se a extração
ficou correta e identificar necessidade de limpeza/higienização dos dados
(valores None/NaN, rótulos estranhos, colunas fora do esperado etc.).

Cada indicador (série) da guia é listado sequencialmente no formato:

    Indicador: <nome do indicador>
        <período 1>: <valor 1>
        <período 2>: <valor 2>
        ...

Uso básico:
-----------
    from magalu_loader import MagaluDataLoader
    from magalu_export_txt import exportar_guias_para_txt

    loader = MagaluDataLoader("RESULTADO_2T26_POR.xlsx")
    exportar_guias_para_txt(loader, pasta_saida="saida_txt")

Isso cria um arquivo .txt por guia dentro de "saida_txt/", por exemplo:
    saida_txt/01_1._Indicadores.txt
    saida_txt/04_4._Balanço_Patrimonial.txt
    ...

Também é possível gerar um único arquivo consolidado com todas as guias,
usando exportar_tudo_em_um_arquivo().
"""

import os
import re
import numpy as np
import pandas as pd

from magalu_loader import MagaluDataLoader


def _nome_arquivo_seguro(nome_guia, prefixo_numero=None):
    """Transforma o nome da guia num nome de arquivo seguro (sem espaços/acentos problemáticos)."""
    nome = nome_guia.strip()
    nome = re.sub(r'[\\/*?:"<>|]', '', nome)   # remove caracteres inválidos em nome de arquivo
    nome = nome.replace(' ', '_')
    if prefixo_numero is not None:
        return f"{prefixo_numero:02d}_{nome}.txt"
    return f"{nome}.txt"


def _formatar_valor(v):
    """Formata um valor para exibição no .txt, deixando explícito quando está vazio/ausente.

    IMPORTANTE: números aparecem no Excel ora como float (ex.: 3490.0), ora como
    int (ex.: 3490), dependendo de como a célula foi digitada/exportada na
    planilha de origem. Os dois casos precisam do MESMO formato de milhar/decimal
    aqui, senão o mesmo indicador aparece com aparência inconsistente ao longo
    da série (ex.: "4.422,5440" ao lado de "3490"), mesmo os valores estando
    corretos e na mesma escala (R$ milhões)."""
    if v is None:
        return "(vazio)"
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, float) and np.isnan(v):
        return "(vazio)"
    if isinstance(v, (int, float, np.integer, np.floating)):
        return f"{float(v):,.4f}".replace(',', '#').replace('.', ',').replace('#', '.')
    return str(v)


def _formatar_coluna(coluna):
    """Formata o rótulo de uma coluna, incluindo o caso de colunas MultiIndex (tuplas)."""
    if isinstance(coluna, tuple):
        partes = [str(c) for c in coluna if c is not None and str(c) != 'nan']
        return " / ".join(partes) if partes else "(sem rótulo)"
    if coluna is None or (isinstance(coluna, float) and np.isnan(coluna)):
        return "(sem rótulo)"
    return str(coluna)


def _linhas_da_guia(nome_guia, df):
    """Gera a lista de linhas de texto que descrevem uma guia (cabeçalho + indicadores)."""
    linhas = []
    linhas.append("=" * 100)
    linhas.append(f"GUIA: {nome_guia}")
    linhas.append("=" * 100)
    linhas.append(f"Quantidade de indicadores (linhas): {df.shape[0]}")
    linhas.append(f"Quantidade de colunas/períodos: {df.shape[1]}")
    linhas.append("")

    colunas_formatadas = [_formatar_coluna(c) for c in df.columns]

    for indicador in df.index:
        linhas.append("-" * 100)
        linhas.append(f"Indicador: {indicador}")
        linhas.append("-" * 100)

        serie = df.loc[indicador]
        # Se houver indicadores com o mesmo nome (não deveria, já é desambiguado no loader),
        # .loc pode devolver um DataFrame em vez de Series -- tratamos os dois casos.
        if isinstance(serie, pd.DataFrame):
            for _, linha_serie in serie.iterrows():
                for col_txt, valor in zip(colunas_formatadas, linha_serie.tolist()):
                    linhas.append(f"    {col_txt}: {_formatar_valor(valor)}")
        else:
            valores = serie.tolist()
            for col_txt, valor in zip(colunas_formatadas, valores):
                linhas.append(f"    {col_txt}: {_formatar_valor(valor)}")
        linhas.append("")

    linhas.append("")
    return linhas


def exportar_guias_para_txt(loader: MagaluDataLoader, pasta_saida="saida_txt"):
    """
    Gera um arquivo .txt para cada guia carregada pelo MagaluDataLoader.
    Retorna a lista de caminhos dos arquivos gerados.
    """
    os.makedirs(pasta_saida, exist_ok=True)
    arquivos_gerados = []

    for i, nome_guia in enumerate(loader.listar_guias(), start=1):
        df = loader.get_sheet_df(nome_guia)
        linhas = _linhas_da_guia(nome_guia, df)

        caminho = os.path.join(pasta_saida, _nome_arquivo_seguro(nome_guia, prefixo_numero=i))
        with open(caminho, "w", encoding="utf-8") as f:
            f.write("\n".join(linhas))

        arquivos_gerados.append(caminho)
        print(f"Gerado: {caminho}")

    return arquivos_gerados


def exportar_tudo_em_um_arquivo(loader: MagaluDataLoader, caminho_saida="saida_txt/00_TODAS_AS_GUIAS.txt"):
    """
    Gera um único arquivo .txt consolidado, com todas as guias uma após a outra.
    Útil para fazer uma busca (Ctrl+F) por um indicador em todo o conteúdo de uma vez.
    """
    os.makedirs(os.path.dirname(caminho_saida) or ".", exist_ok=True)
    with open(caminho_saida, "w", encoding="utf-8") as f:
        for nome_guia in loader.listar_guias():
            df = loader.get_sheet_df(nome_guia)
            linhas = _linhas_da_guia(nome_guia, df)
            f.write("\n".join(linhas))
            f.write("\n\n")
    print(f"Gerado arquivo consolidado: {caminho_saida}")
    return caminho_saida


if __name__ == "__main__":
    caminho_planilha = "RESULTADO_2T26_POR.xlsx"
    loader = MagaluDataLoader(caminho_planilha)

    # Um .txt por guia
    exportar_guias_para_txt(loader, pasta_saida="saida_txt")

    # (Opcional) um único .txt com tudo junto
    exportar_tudo_em_um_arquivo(loader, caminho_saida="saida_txt/00_TODAS_AS_GUIAS.txt")
