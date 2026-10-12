"""
analises_eventos.py
====================
Motor analítico do modelo v3 ("Eventos Estratégicos × Indicadores").

Responsabilidades:
  1. Entregar TODAS as séries em base trimestral com índice `pd.Period('Q')`,
     para que indicadores do DRE, cotação (MGLU3), Selic e Google Trends possam
     ser alinhados no mesmo eixo (classe FonteSeries).
  2. Ajustar a cotação por desdobramentos/grupamento (ajustar_cotacao).
  3. Conferir cada hipótese direcional de um evento contra os dados:
     média antes × depois, e classificar em COERENTE / CONTRÁRIA / INCONCLUSIVA
     (avaliar_evento / avaliar_todos).
  4. Correlação por defasagem com faixa de referência (correlacao_por_defasagem).

Princípio: o app NUNCA diz que "provou" algo. Ele verifica se a direção dos
dados é coerente com o fato real documentado e mostra, com a mesma ênfase,
quando é contrária.
"""

import re
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from config_indicadores import INDICADORES, INDICADORES_PERCENTUAIS
from eventos_estrategicos import (
    INDICADORES_V3, PERCENTUAIS_V3, EVENTOS_ACAO,
    unidade_serie, rotulo_serie,
)
from formatos import formata_moeda, formata_pct, formata_numero, formata_variacao
from analises import correlacao_pearson

RE_TRI = re.compile(r"^\s*(\d)T(\d{2})\s*$")

COERENTE, CONTRARIA, INCONCLUSIVO, SEM_DADOS = "coerente", "contraria", "inconclusivo", "sem_dados"
ICONE_VEREDITO = {COERENTE: "✅", CONTRARIA: "❌", INCONCLUSIVO: "➖", SEM_DADOS: "⚠"}
TEXTO_VEREDITO = {
    COERENTE: "Coerente", CONTRARIA: "Contrária",
    INCONCLUSIVO: "Inconclusiva", SEM_DADOS: "Sem dados",
}

LIMIAR_RELATIVO = 0.05    # variação mínima (5%) para valores em nível
LIMIAR_PP = 0.005         # variação mínima (0,5 p.p.) para percentuais


# ======================================================================
# 1. Rótulos / períodos
# ======================================================================
def rotulo_para_period(rotulo) -> Optional[pd.Period]:
    """'3T21' -> Period('2021Q3'). Outros formatos -> None."""
    if rotulo is None:
        return None
    m = RE_TRI.match(str(rotulo))
    if not m:
        return None
    return pd.Period(f"{2000 + int(m.group(2))}Q{int(m.group(1))}", freq="Q")


def period_para_rotulo(p: pd.Period) -> str:
    return f"{p.quarter}T{p.year % 100:02d}"


def period_para_data(p: pd.Period) -> pd.Timestamp:
    """Meio do trimestre — posição de plotagem (barras ficam centradas no trimestre)."""
    return p.start_time + pd.Timedelta(days=45)


def para_datas(serie: pd.Series) -> pd.Series:
    """Converte índice Period('Q') em Timestamps (meio do trimestre) para plotagem."""
    if serie is None or serie.empty:
        return pd.Series(dtype=float)
    if isinstance(serie.index, pd.PeriodIndex):
        novo = pd.Series(serie.values, index=[period_para_data(p) for p in serie.index])
        novo.index = pd.DatetimeIndex(novo.index)
        return novo
    return serie


def limpar_serie_trimestral(serie) -> pd.Series:
    """Qualquer série do repositório -> Series numérica com PeriodIndex trimestral,
    ordenada, sem duplicatas e sem NaN. Rótulos que não são 'nTaa' são descartados."""
    if serie is None:
        return pd.Series(dtype=float)
    if isinstance(serie, pd.DataFrame):
        serie = serie.apply(pd.to_numeric, errors="coerce").sum(axis=0)
    if len(serie) == 0:
        return pd.Series(dtype=float)
    s = pd.to_numeric(serie, errors="coerce")
    periodos, valores = [], []
    for rot, v in s.items():
        p = rotulo_para_period(rot)
        if p is None or pd.isna(v):
            continue
        periodos.append(p)
        valores.append(float(v))
    if not periodos:
        return pd.Series(dtype=float)
    out = pd.Series(valores, index=pd.PeriodIndex(periodos, freq="Q"))
    out = out[~out.index.duplicated(keep="first")].sort_index()
    return out


def normalizar_fracao(serie: pd.Series) -> pd.Series:
    """Se uma série percentual vier em escala 0–100, converte para fração (0–1)."""
    if serie is None or serie.empty:
        return serie
    if serie.abs().max() > 1.5:
        return serie / 100.0
    return serie


def eh_percentual(chave: str) -> bool:
    return chave in INDICADORES_PERCENTUAIS or chave in PERCENTUAIS_V3


def agregar_anual(serie_q: pd.Series, percentual=False) -> pd.Series:
    """Agrega série trimestral em anual (soma ou média). Só anos COMPLETOS (4 trimestres).
    Use apenas para fluxos (receita, lucro...) — não para estoques (nº de lojas)."""
    if serie_q is None or serie_q.empty:
        return pd.Series(dtype=float)
    por_ano = serie_q.groupby(serie_q.index.year)
    cont = por_ano.count()
    agg = por_ano.mean() if percentual else por_ano.sum()
    return agg[cont >= 4]


# ======================================================================
# 2. Ajuste da cotação (desdobramentos / grupamento)
# ======================================================================
def ajustar_cotacao(serie_fech: pd.Series, eventos_acao=None, tolerancia=0.35):
    """Ajusta o preço histórico a splits/grupamentos, SOMENTE se a série vier sem ajuste.

    Para cada evento, compara o 1º pregão depois da data-ex com o último antes:
    se a razão é próxima do fator do evento (ex.: ~1/8), a série NÃO está ajustada
    e os preços anteriores são multiplicados pelo fator. Se a razão é ~1, a série
    já está ajustada e nada é feito.

    Retorna (serie_ajustada, relatorio: list[str])."""
    eventos_acao = eventos_acao or EVENTOS_ACAO
    relatorio = []
    if serie_fech is None or serie_fech.empty:
        return pd.Series(dtype=float), ["Cotação indisponível."]

    s = serie_fech.dropna().sort_index().astype(float)
    s.index = pd.to_datetime(s.index)
    adj = s.copy()

    for ev in eventos_acao:
        d = pd.Timestamp(ev["data"])
        f = ev["fator"]
        antes, depois = s[s.index < d], s[s.index >= d]
        if antes.empty or depois.empty:
            relatorio.append(f"{ev['descricao']} ({d:%d/%m/%Y}): fora do período da cotação — ignorado.")
            continue
        if (depois.index[0] - d).days > 7 or (d - antes.index[-1]).days > 10:
            relatorio.append(f"{ev['descricao']} ({d:%d/%m/%Y}): sem pregões próximos à data — ignorado.")
            continue
        razao = depois.iloc[0] / antes.iloc[-1]
        if f * (1 - tolerancia) <= razao <= f * (1 + tolerancia):
            adj[adj.index < d] = adj[adj.index < d] * f
            relatorio.append(
                f"{ev['descricao']} ({d:%d/%m/%Y}): série SEM ajuste (razão {razao:.3f}) → ajustada pelo fator {f:g}.")
        else:
            relatorio.append(
                f"{ev['descricao']} ({d:%d/%m/%Y}): série já ajustada (razão {razao:.3f}) → nada a fazer.")
    return adj, relatorio


# ======================================================================
# 3. Fonte unificada de séries trimestrais
# ======================================================================
class FonteSeries:
    """Entrega qualquer série do projeto em base trimestral (PeriodIndex).

    Chaves aceitas: as de config_indicadores.INDICADORES, as de
    eventos_estrategicos.INDICADORES_V3 e as especiais:
        'mglu3', 'selic', 'trends', 'share_3p', 'resfin_sobre_receita'.
    """

    def __init__(self, repositorio, selic=None):
        self.repo = repositorio
        self.selic = selic
        self._cache = {}
        self.avisos_dados = []          # transparência: duplicatas, séries ausentes etc.
        self.fech_ajustada = pd.Series(dtype=float)
        self.relatorio_ajuste = []
        self._preparar_cotacao()

    # --- preparação -----------------------------------------------------
    def _preparar_cotacao(self):
        cot = getattr(self.repo, "cotacao", None)
        if cot is None:
            self.relatorio_ajuste = ["Cotação não carregada."]
            return
        try:
            fech = cot.get_serie("Fechamento")
            self.fech_ajustada, self.relatorio_ajuste = ajustar_cotacao(fech)
        except Exception as e:  # noqa: BLE001
            self.relatorio_ajuste = [f"Falha ao preparar a cotação: {e}"]

    # --- DRE ------------------------------------------------------------
    def _resolver_rotulo(self, guia, indicador):
        """Resolve o rótulo real do indicador na guia. O loader prefixa a SEÇÃO quando o
        mesmo nome aparece 2x na guia (ex.: 'Marketplace (3P)'), então tenta o nome exato
        e, se falhar, os rótulos '… | indicador' (escolhe o de maior magnitude)."""
        loader = getattr(self.repo, "loader_dre", None)
        if loader is None:
            return None
        try:
            df = loader.get_sheet_df(guia)
        except KeyError:
            return None
        if indicador in df.index:
            return indicador
        candidatos = [i for i in df.index if str(i).endswith(f"| {indicador}")]
        if not candidatos:
            return None
        if len(candidatos) == 1:
            return candidatos[0]
        magnitudes = {}
        for c in candidatos:
            linha = df.loc[c]
            if isinstance(linha, pd.DataFrame):
                linha = linha.iloc[0]
            magnitudes[c] = pd.to_numeric(linha, errors="coerce").abs().median()
        return max(magnitudes, key=lambda k: (0 if pd.isna(magnitudes[k]) else magnitudes[k]))

    def _linha_dre(self, guia, rotulo, chave):
        """Linha do DRE como Series. Se o rótulo se repete na guia (ex.: 'Marketplace (3P)'
        aparece como VENDA na abertura de vendas e como DEDUÇÃO, com sinal negativo, na
        abertura da receita bruta), usa a 1ª ocorrência e registra um aviso. NÃO soma as
        duplicatas: somar vendas + dedução zera a série."""
        df = self.repo.loader_dre.get_sheet_df(guia)
        linha = df.loc[rotulo]
        if isinstance(linha, pd.DataFrame):
            self.avisos_dados.append(
                f"'{rotulo}' (guia '{guia}') aparece {len(linha)}x; usada a 1ª ocorrência "
                f"para '{chave}' (evita somar venda + dedução).")
            linha = linha.iloc[0]
        return linha

    def _dre(self, chave):
        mapa = {**INDICADORES, **INDICADORES_V3}
        if chave not in mapa:
            return pd.Series(dtype=float)
        guia, indicador = mapa[chave]
        rotulo = self._resolver_rotulo(guia, indicador)
        if rotulo is None:
            self.avisos_dados.append(f"Indicador '{indicador}' não encontrado na guia '{guia}' (chave '{chave}').")
            return pd.Series(dtype=float)
        s = limpar_serie_trimestral(self._linha_dre(guia, rotulo, chave))
        if eh_percentual(chave):
            s = normalizar_fracao(s)
        return s

    # --- demais fontes ----------------------------------------------------
    def _mglu3(self):
        if self.fech_ajustada.empty:
            return pd.Series(dtype=float)
        s = self.fech_ajustada.groupby(self.fech_ajustada.index.to_period("Q")).last()
        s.index = pd.PeriodIndex(s.index, freq="Q")
        return s

    def _selic(self):
        return self.selic.trimestral() if self.selic is not None else pd.Series(dtype=float)

    def trends_mensal(self):
        tr = getattr(self.repo, "trends", None)
        if tr is None or tr.serie_temporal is None or tr.serie_temporal.empty:
            return pd.Series(dtype=float)
        df = tr.serie_temporal
        s = df.set_index("Data")["Quantidade"].astype(float)
        s.index = pd.to_datetime(s.index)
        return s.sort_index()

    def _trends(self):
        s = self.trends_mensal()
        if s.empty:
            return s
        q = s.groupby(s.index.to_period("Q")).mean()
        q.index = pd.PeriodIndex(q.index, freq="Q")
        return q

    # --- API ------------------------------------------------------------
    def trimestral(self, chave) -> pd.Series:
        if chave in self._cache:
            return self._cache[chave]
        if chave == "mglu3":
            s = self._mglu3()
        elif chave == "selic":
            s = self._selic()
        elif chave == "trends":
            s = self._trends()
        elif chave == "share_3p":
            a, b = self.trimestral("vendas_marketplace_3p"), self.trimestral("vendas_totais")
            s = (a / b.replace(0, np.nan)).dropna() if not a.empty and not b.empty else pd.Series(dtype=float)
        elif chave == "resfin_sobre_receita":
            a, b = self.trimestral("resultado_financeiro"), self.trimestral("receita_liquida")
            s = (a / b.replace(0, np.nan)).dropna() if not a.empty and not b.empty else pd.Series(dtype=float)
        else:
            s = self._dre(chave)
        self._cache[chave] = s
        return s

    def disponivel(self, chave) -> bool:
        return not self.trimestral(chave).empty

    def anual(self, chave) -> pd.Series:
        s = self.trimestral(chave)
        return agregar_anual(s, percentual=(unidade_serie(chave) == "pct"))


# ======================================================================
# 4. Formatação de valores por unidade
# ======================================================================
def formatar_valor(chave, valor) -> str:
    if valor is None or (isinstance(valor, float) and np.isnan(valor)):
        return "—"
    un = unidade_serie(chave)
    if un == "moeda":                       # planilha em R$ milhões
        return formata_moeda(valor * 1_000_000)
    if un == "pct":
        return formata_pct(valor, casas=1)
    if un == "preco":
        return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return formata_numero(valor, 1)


# ======================================================================
# 5. Avaliação de eventos
# ======================================================================
@dataclass
class Janelas:
    antes: tuple          # (Period, Period)
    depois: tuple         # (Period, Period)
    ref: pd.Period


def _periodo_do_evento(ev) -> pd.Period:
    if ev.trimestre_ref:
        p = rotulo_para_period(ev.trimestre_ref)
        if p is not None:
            return p
    return pd.Period(ev.data_inicio, freq="Q")


def janelas_avaliacao(ev, modo="medio", n=4) -> Janelas:
    if ev.eh_periodo:
        q_ini, q_fim = pd.Period(ev.data_inicio, freq="Q"), pd.Period(ev.data_fim, freq="Q")
        return Janelas((q_ini - n, q_ini - 1), (q_ini, q_fim), q_ini)
    ref = _periodo_do_evento(ev)
    if modo == "pico":
        return Janelas((ref - n, ref - 1), (ref, ref), ref)
    if modo == "aa":
        return Janelas((ref - 4, ref - 4), (ref, ref), ref)
    if ev.incluir_trimestre_no_depois:
        return Janelas((ref - n, ref - 1), (ref, ref + n - 1), ref)
    return Janelas((ref - n, ref - 1), (ref + 1, ref + n), ref)


def _recorte(s: pd.Series, janela) -> pd.Series:
    ini, fim = janela
    return s[(s.index >= ini) & (s.index <= fim)].dropna()


def _fmt_janela(janela, serie_idx=None) -> str:
    ini, fim = janela
    if ini == fim:
        return period_para_rotulo(ini)
    return f"{period_para_rotulo(ini)}–{period_para_rotulo(fim)}"


def avaliar_expectativa(fonte: FonteSeries, ev, exp, n=4) -> dict:
    chave = exp.chave
    serie = fonte.trimestral(chave)
    un = unidade_serie(chave)
    modo = "periodo" if ev.eh_periodo else exp.modo
    jan = janelas_avaliacao(ev, modo, n)

    linha = {
        "chave": chave, "Indicador": rotulo_serie(chave), "Hipótese": exp.direcao,
        "modo": modo, "Janela antes": _fmt_janela(jan.antes), "Janela depois": _fmt_janela(jan.depois),
        "comentario": exp.comentario,
        "antes": np.nan, "depois": np.nan, "delta": np.nan,
        "n_antes": 0, "n_depois": 0, "Veredito": SEM_DADOS, "Variação": "—", "Nota": "",
    }
    if serie.empty:
        linha["Nota"] = "Série indisponível nos dados carregados."
        return linha

    a, d = _recorte(serie, jan.antes), _recorte(serie, jan.depois)
    linha["n_antes"], linha["n_depois"] = len(a), len(d)
    pontual = modo in ("pico", "aa")
    min_a, min_d = 1, (1 if pontual else 2)
    if len(a) < min_a or len(d) < min_d:
        linha["Nota"] = (f"Observações insuficientes (antes={len(a)}, depois={len(d)}). "
                         f"O evento é recente ou fora da cobertura da série.")
        return linha

    antes, depois = float(a.mean()), float(d.mean())
    delta = depois - antes
    linha.update(antes=antes, depois=depois, delta=delta)

    if un == "pct":
        passa = abs(delta) >= LIMIAR_PP
        linha["Variação"] = f"{delta * 100:+.1f}".replace(".", ",") + " p.p."
    else:
        ref = max(abs(antes), abs(depois))
        passa = ref > 0 and abs(delta) / ref >= LIMIAR_RELATIVO
        if antes > 0 and depois >= 0:
            linha["Variação"] = formata_variacao(delta / antes)
        else:
            linha["Variação"] = "Δ " + formatar_valor(chave, delta)
            linha["Nota"] = "Base ≤ 0 ou mudança de sinal: variação % não é informativa; veja os valores."

    if not passa:
        linha["Veredito"] = INCONCLUSIVO
        linha["Nota"] = (linha["Nota"] + " " if linha["Nota"] else "") + "Variação pequena (abaixo do limiar de relevância)."
    else:
        subiu = delta > 0
        esperado_alta = exp.direcao == "alta"
        linha["Veredito"] = COERENTE if subiu == esperado_alta else CONTRARIA

    if not pontual and (len(a) < n or (not ev.eh_periodo and len(d) < n)):
        linha["Nota"] = (linha["Nota"] + " " if linha["Nota"] else "") + (
            f"Janela parcial (antes={len(a)}T, depois={len(d)}T).")
    return linha


def avaliar_evento(fonte: FonteSeries, ev, n=4) -> pd.DataFrame:
    linhas = [avaliar_expectativa(fonte, ev, e, n) for e in ev.expectativas]
    return pd.DataFrame(linhas)


def avaliar_todos(fonte: FonteSeries, eventos, n=4) -> pd.DataFrame:
    partes = []
    for ev in eventos:
        df = avaliar_evento(fonte, ev, n)
        if df.empty:
            continue
        df.insert(0, "Evento", ev.nome)
        df.insert(1, "id_evento", ev.id)
        partes.append(df)
    return pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()


def tabela_para_exibicao(df: pd.DataFrame) -> pd.DataFrame:
    """Formata o resultado de avaliar_evento para st.dataframe."""
    if df.empty:
        return df
    linhas = []
    for _, r in df.iterrows():
        linhas.append({
            "Indicador": r["Indicador"],
            "Hipótese": "↑ alta" if r["Hipótese"] == "alta" else "↓ queda",
            f"Antes ({r['Janela antes']})": formatar_valor(r["chave"], r["antes"]),
            f"Depois ({r['Janela depois']})": formatar_valor(r["chave"], r["depois"]),
            "Variação": r["Variação"],
            "Veredito": f"{ICONE_VEREDITO[r['Veredito']]} {TEXTO_VEREDITO[r['Veredito']]}",
            "Observação": r["Nota"],
        })
    out = pd.DataFrame(linhas)
    # nomes de coluna das janelas variam por linha -> padroniza
    out.columns = ["Indicador", "Hipótese", "Antes", "Depois", "Variação", "Veredito", "Observação"]
    return out


def frase_leitura(r: dict) -> str:
    """Frase em português com os números reais de uma linha de avaliação."""
    if r["Veredito"] == SEM_DADOS:
        return f"**{r['Indicador']}**: dados insuficientes para avaliar ({r['Nota']})"
    verbo = {"alta": "alta", "queda": "queda"}[r["Hipótese"]]
    leitura = {
        COERENTE: "os dados são coerentes com essa hipótese",
        CONTRARIA: "os dados caminharam em sentido CONTRÁRIO",
        INCONCLUSIVO: "a variação foi pequena demais para concluir",
    }[r["Veredito"]]
    return (f"**{r['Indicador']}**: {formatar_valor(r['chave'], r['antes'])} "
            f"({r['Janela antes']}) → {formatar_valor(r['chave'], r['depois'])} "
            f"({r['Janela depois']}), {r['Variação']}. Hipótese de {verbo}: {leitura}.")


def placar(df_todos: pd.DataFrame) -> dict:
    if df_todos is None or df_todos.empty:
        return {COERENTE: 0, CONTRARIA: 0, INCONCLUSIVO: 0, SEM_DADOS: 0, "total": 0}
    cont = df_todos["Veredito"].value_counts().to_dict()
    out = {k: int(cont.get(k, 0)) for k in (COERENTE, CONTRARIA, INCONCLUSIVO, SEM_DADOS)}
    out["total"] = int(sum(out.values()))
    return out


# ======================================================================
# 6. Correlação por defasagem
# ======================================================================
_T_CRIT_95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306,
              9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131,
              16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086, 21: 2.080, 22: 2.074,
              23: 2.069, 24: 2.064, 25: 2.060, 26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042}


def r_critico(n: int) -> float:
    """|r| mínimo para significância bilateral a 5% (teste t, n observações).
    Referência APROXIMADA: séries temporais têm autocorrelação, que infla a significância."""
    gl = n - 2
    if gl < 1:
        return float("nan")
    t = _T_CRIT_95.get(gl, 2.0)
    return float(t / np.sqrt(gl + t ** 2))


def variacao_aa(serie: pd.Series) -> pd.Series:
    """Variação a/a robusta a bases ≤ 0 (usa |base| no denominador)."""
    if serie is None or serie.empty:
        return pd.Series(dtype=float)
    full = serie.reindex(pd.period_range(serie.index.min(), serie.index.max(), freq="Q"))
    base = full.shift(4)
    out = (full - base) / base.abs().replace(0, np.nan)
    return out.replace([np.inf, -np.inf], np.nan)


def correlacao_por_defasagem(x: pd.Series, y: pd.Series, defasagens=range(-4, 5), transformacao="nivel"):
    """Correlação entre X(t) e Y(t+k), k em `defasagens` (k>0: X antecede Y).

    transformacao: 'nivel' ou 'aa' (variação a/a — reduz tendência e sazonalidade e
    evita correlação espúria entre séries que apenas crescem juntas).
    Retorna DataFrame [defasagem, r, n]."""
    if x is None or y is None or x.empty or y.empty:
        return pd.DataFrame(columns=["defasagem", "r", "n"])
    if transformacao == "aa":
        x, y = variacao_aa(x), variacao_aa(y)
    ini, fim = min(x.index.min(), y.index.min()), max(x.index.max(), y.index.max())
    full = pd.period_range(ini, fim, freq="Q")
    x, y = x.reindex(full), y.reindex(full)
    linhas = []
    for k in defasagens:
        r, n, _ = correlacao_pearson(x, y.shift(-k))
        linhas.append({"defasagem": k, "r": r, "n": n})
    return pd.DataFrame(linhas)
