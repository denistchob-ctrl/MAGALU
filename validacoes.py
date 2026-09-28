"""
validacoes.py
==============
Funções de validação antes de gerar gráficos/análises:
  - existência do indicador na guia;
  - disponibilidade de período;
  - observações mínimas para correlação;
  - divisão por zero.
Devolve mensagens amigáveis (nunca quebra o app).
"""

import pandas as pd


def indicador_disponivel(repositorio, chave_indicador):
    """Verifica se o indicador existe na guia correspondente.
    Devolve (disponivel: bool, mensagem: str)."""
    from config_indicadores import INDICADORES
    if chave_indicador not in INDICADORES:
        return False, f"Indicador '{chave_indicador}' não está mapeado em config_indicadores.INDICADORES."
    guia, indicador = INDICADORES[chave_indicador]
    if repositorio.loader_dre is None:
        return False, "Planilha do DRE não carregada."
    try:
        indicadores = repositorio.loader_dre.listar_indicadores(guia)
    except KeyError:
        return False, f"Guia '{guia}' não encontrada."
    if indicador not in indicadores:
        return False, f"Indicador '{indicador}' não encontrado na guia '{guia}'."
    return True, ""


def serie_tem_dados(serie, minimo=1):
    """Verifica se a série tem pelo menos 'minimo' observações não nulas."""
    if serie is None or serie.empty:
        return False, "Série vazia."
    nao_nulos = serie.dropna()
    if len(nao_nulos) < minimo:
        return False, f"Série tem apenas {len(nao_nulos)} observação(ões) — mínimo exigido: {minimo}."
    return True, ""


def periodos_compativeis(serie_x, serie_y):
    """Verifica se duas séries compartilham períodos (para correlação)."""
    if serie_x is None or serie_y is None:
        return False, "Uma das séries está vazia."
    comuns = set(serie_x.index) & set(serie_y.index)
    if len(comuns) < 3:
        return False, (f"Apenas {len(comuns)} período(s) em comum entre as séries. "
                       f"Não é possível comparar com segurança.")
    return True, ""


def observacoes_suficientes(n, minimo):
    """Avisa se o número de observações é pequeno."""
    if n < minimo:
        return False, (f"Apenas {n} observação(ões). Recomendado: ≥ {minimo}. "
                       f"Resultado pode ser instável.")
    return True, ""


def taxa_segura(numerador, denominador):
    """Divisão segura — devolve NaN se denominador for 0/None/NaN."""
    if denominador is None or denominador == 0:
        return float("nan")
    if isinstance(denominador, float) and denominador != denominador:
        return float("nan")
    return numerador / denominador


def mensagem_sem_dados(motivo="Dados insuficientes"):
    """Mensagem padrão para exibir quando não há dados."""
    return f"⚠ {motivo}. Este gráfico não pôde ser gerado."