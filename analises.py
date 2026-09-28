"""
analises.py
============
Funções analíticas reutilizáveis:
  - variação percentual;
  - Base 100;
  - correlação de Pearson;
  - correlação defasada;
  - indicadores derivados (receita por loja, por m²).
Todas as funções devolvem NaN/mensagens quando faltam dados — nunca
quebram o app.
"""

import numpy as np
import pandas as pd


def variacao_pct(serie):
    """Variação percentual período a período. NaN no primeiro período."""
    if serie is None or serie.empty:
        return pd.Series(dtype=float)
    return serie.pct_change()


def variacao_ultimo_vs_anterior(serie):
    """Variação percentual do último período contra o penúltimo."""
    if serie is None or len(serie.dropna()) < 2:
        return float("nan")
    s = serie.dropna()
    atual, anterior = s.iloc[-1], s.iloc[-2]
    if anterior == 0 or pd.isna(anterior):
        return float("nan")
    return (atual - anterior) / abs(anterior)


def base_100(serie, periodo_inicial=None):
    """Constrói índice Base 100. Se periodo_inicial=None, usa o primeiro
    período não nulo da série. Períodos com NaN continuam NaN."""
    if serie is None or serie.empty:
        return pd.Series(dtype=float)

    s = serie.dropna()
    if s.empty:
        return pd.Series(dtype=float)

    if periodo_inicial is None:
        periodo_inicial = s.index[0]
    if periodo_inicial not in s.index:
        return pd.Series(dtype=float)

    base = s.loc[periodo_inicial]
    if base == 0 or pd.isna(base):
        return pd.Series(dtype=float)

    return (serie / base) * 100


def correlacao_pearson(serie_x, serie_y):
    """Correlação de Pearson entre duas séries alinhadas por índice comum.
    Devolve (r, n, p_value_aprox) ou (nan, n, nan) se não calcular."""
    if serie_x is None or serie_y is None:
        return float("nan"), 0, float("nan")

    # Alinha pelos índices comuns
    df = pd.DataFrame({"x": serie_x, "y": serie_y}).dropna()
    n = len(df)
    if n < 3:
        return float("nan"), n, float("nan")

    x = df["x"].to_numpy()
    y = df["y"].to_numpy()
    if np.std(x) == 0 or np.std(y) == 0:
        return float("nan"), n, float("nan")

    r = float(np.corrcoef(x, y)[0, 1])

    # p-value aproximado (teste t de Student) — só para referência
    if n > 2 and abs(r) < 1:
        t = r * np.sqrt((n - 2) / (1 - r**2))
        # Aproximação: p ≈ 2 * (1 - CDF(|t|)). Sem scipy, devolvemos None.
        p = None
    else:
        p = None

    return r, n, p


def correlacao_defasada(serie_x, serie_y, defasagem=1):
    """Correlação X(t) vs Y(t+defasagem). Devolve (r, n, p)."""
    if serie_x is None or serie_y is None:
        return float("nan"), 0, float("nan")

    y_defasado = serie_y.shift(-defasagem)
    return correlacao_pearson(serie_x, y_defasado)


def receita_por_loja(receita_lojas_fisicas, numero_lojas):
    """Receita das lojas físicas / número de lojas. Séries alinhadas por índice."""
    if receita_lojas_fisicas is None or numero_lojas is None:
        return pd.Series(dtype=float)
    df = pd.DataFrame({
        "receita": receita_lojas_fisicas,
        "lojas": numero_lojas,
    }).dropna()
    if df.empty:
        return pd.Series(dtype=float)
    return df["receita"] / df["lojas"].replace(0, np.nan)


def receita_por_m2(receita_lojas_fisicas, area_vendas):
    """Receita das lojas físicas / área de vendas (m²)."""
    if receita_lojas_fisicas is None or area_vendas is None:
        return pd.Series(dtype=float)
    df = pd.DataFrame({
        "receita": receita_lojas_fisicas,
        "area": area_vendas,
    }).dropna()
    if df.empty:
        return pd.Series(dtype=float)
    return df["receita"] / df["area"].replace(0, np.nan)