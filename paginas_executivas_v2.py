"""
paginas_executivas_v2.py
==========================
Modelo v2 do dashboard executivo — 5 páginas temáticas + 2 acadêmicas.
Convive com paginas_executivas.py (v1) sem sobrescrever nada.

Estrutura de cada página:
  1. Título + pergunta executiva.
  2. Filtros no sidebar.
  3. KPIs (cards).
  4. Gráficos.
  5. Insights (fato / associação / hipótese).
  6. Como interpretar.
"""

import pandas as pd
import numpy as np
import streamlit as st

from config_indicadores import INDICADORES, CORES, MIN_OBSERVACOES_CORRELACAO
from formatos import formata_moeda, formata_pct, formata_variacao
from validacoes import indicador_disponivel, serie_tem_dados, mensagem_sem_dados
from analises import (
    variacao_ultimo_vs_anterior, base_100,
    correlacao_pearson, correlacao_defasada,
    receita_por_loja, receita_por_m2,
)
import graficos_executivos_v2 as g2

OPCAO_TODOS = "Todos"


# ======================================================================
# Helpers de filtro (reaproveitados do paginas_executivas.py)
# ======================================================================

def _seletor_ano(repositorio, key):
    anos = repositorio.anos_disponiveis()
    opcoes = [OPCAO_TODOS] + [str(a) for a in anos]
    escolha = st.sidebar.selectbox("Ano", opcoes, index=0, key=key)
    return None if escolha == OPCAO_TODOS else int(escolha)


def _seletor_granularidade(key):
    escolha = st.sidebar.radio(
        "Granularidade",
        ["Anual", "Semestral", "Trimestral"],
        index=0, key=key,
        help="Evita misturar no mesmo gráfico períodos diferentes.",
    )
    return escolha.lower()


def _seletor_unidade_ra(key):
    return st.sidebar.selectbox(
        "Unidade de negócio (Reclame Aqui)",
        ["online", "fisica", "luizacred", "consorcio"],
        key=key,
    )


def _serie(repositorio, chave, gran, ano):
    """Busca uma série do DRE a partir da chave em INDICADORES."""
    if chave not in INDICADORES:
        return pd.Series(dtype=float)
    guia, indicador = INDICADORES[chave]
    return repositorio.serie_dre_por_granularidade(guia, indicador, gran, ano)


def _kpi(label, valor_str, variacao=None):
    """Card de KPI."""
    delta = None
    if variacao is not None and not (isinstance(variacao, float) and np.isnan(variacao)):
        delta = f"{variacao*100:+.1f}%"
    st.metric(label=label, value=valor_str, delta=delta)


def _secao_insights(fatos, associacoes, hipoteses):
    """Renderiza as 3 categorias de insight, se houver conteúdo."""
    st.markdown("### Insights")
    if fatos:
        st.markdown("**Fatos observados:**")
        for f in fatos:
            st.markdown(f"- {f}")
    if associacoes:
        st.markdown("**Associações:**")
        for a in associacoes:
            st.markdown(f"- {a}")
    if hipoteses:
        st.markdown("**Hipóteses (requerem investigação adicional):**")
        for h in hipoteses:
            st.markdown(f"- {h}")


def _secao_como_interpretar(texto):
    with st.expander("Como interpretar"):
        st.markdown(texto)


# ======================================================================
# PÁGINA 1 — VISÃO EXECUTIVA
# ======================================================================

class PaginaV2VisaoExecutiva:
    def render(self, repositorio):
        st.title("Visão Executiva")
        st.caption("Como os principais indicadores de desempenho do Magalu "
                   "evoluíram ao longo do período?")

        ano = _seletor_ano(repositorio, key="v2_exec_ano")
        gran = _seletor_granularidade(key="v2_exec_gran")

        # --- KPIs ---
        st.subheader("Indicadores-chave")

        indicadores_kpi = [
            ("Receita Líquida", "receita_liquida", True),
            ("EBITDA", "ebitda", True),
            ("Margem EBITDA", "margem_ebitda", False),
            ("Lucro Líquido", "lucro_liquido", True),
            ("Vendas Totais", "vendas_totais", True),
            ("Participação E-commerce", "participacao_ecommerce", False),
        ]

        # Linha 1: 4 primeiros KPIs
        linha1 = st.columns(4)
        for i, (label, chave, is_moeda) in enumerate(indicadores_kpi[:4]):
            with linha1[i]:
                serie = _serie(repositorio, chave, gran, None)
                if serie.empty:
                    _kpi(label, "—", None)
                    continue
                atual = serie.dropna().iloc[-1] if not serie.dropna().empty else None
                var = variacao_ultimo_vs_anterior(serie)
                if atual is None:
                    _kpi(label, "—", None)
                else:
                    valor_str = formata_moeda(atual) if is_moeda else formata_pct(atual)
                    _kpi(label, valor_str, var)

        # Linha 2: 2 KPIs restantes + MGLU3
        linha2 = st.columns(4)
        for i, (label, chave, is_moeda) in enumerate(indicadores_kpi[4:6]):
            with linha2[i]:
                serie = _serie(repositorio, chave, gran, None)
                if serie.empty:
                    _kpi(label, "—", None)
                    continue
                atual = serie.dropna().iloc[-1] if not serie.dropna().empty else None
                var = variacao_ultimo_vs_anterior(serie)
                if atual is None:
                    _kpi(label, "—", None)
                else:
                    valor_str = formata_moeda(atual) if is_moeda else formata_pct(atual)
                    _kpi(label, valor_str, var)

        # MGLU3 na mesma linha, coluna 3
        with linha2[2]:
            if repositorio.cotacao is not None:
                serie_fech = repositorio.cotacao.get_serie("Fechamento")
                if not serie_fech.empty:
                    atual = serie_fech.iloc[-1]
                    var = variacao_ultimo_vs_anterior(serie_fech.tail(60))
                    _kpi("MGLU3 (últ. fechamento)", f"R$ {atual:.2f}", var)
                else:
                    _kpi("MGLU3 (últ. fechamento)", "—", None)
            else:
                _kpi("MGLU3 (últ. fechamento)", "—", None)

        # Cotação MGLU3
        col_cot = st.columns(4)[2]
        with col_cot:
            if repositorio.cotacao is not None:
                serie_fech = repositorio.cotacao.get_serie("Fechamento")
                if not serie_fech.empty:
                    atual = serie_fech.iloc[-1]
                    var = variacao_ultimo_vs_anterior(serie_fech.tail(60))
                    _kpi("MGLU3 (últ. fechamento)", f"R$ {atual:.2f}", var)

        # --- Gráfico temporal com indicadores selecionáveis ---
        st.subheader("Evolução dos indicadores")
        opcoes = [label for label, _, _ in indicadores_kpi]
        selecionados = st.multiselect(
            "Indicadores para comparar",
            opcoes,
            default=["Receita Líquida", "EBITDA", "Lucro Líquido"],
        )

        mapa = {label: chave for label, chave, _ in indicadores_kpi}
        dados = {}
        for label in selecionados:
            s = _serie(repositorio, mapa[label], gran, ano)
            if not s.empty:
                dados[label] = s

        if dados:
            df_graf = pd.DataFrame(dados)
            fig = g2.visao_executiva_evolucao(df_graf)
            st.plotly_chart(fig, width="stretch")
        else:
            st.info(mensagem_sem_dados("Nenhum indicador selecionado com dados"))

        # --- Insights ---
        _secao_insights(
            fatos=[
                "Os indicadores selecionados foram extraídos da guia '1. Indicadores' da planilha.",
                "A janela de análise cobre 2018–2025 (anual) e 1S2018–1S2026 (semestral).",
            ],
            associacoes=[
                "Receita e EBITDA apresentam associação positiva histórica — investigar "
                "se a margem se mantém estável ou comprime com o crescimento.",
            ],
            hipoteses=[
                "A queda recente do interesse de busca pode estar associada à "
                "compressão de margem; requer cruzamento com dados de marketing.",
            ],
        )

        _secao_como_interpretar(
            "Esta página é um **retrato** — mostra a evolução dos principais "
            "indicadores no período. Não afirma causalidade. Cards comparam o "
            "último período disponível contra o anterior. Gráficos permitem "
            "visualizar tendências e inflexões."
        )


# ======================================================================
# PÁGINA 2 — CRESCIMENTO E RENTABILIDADE
# ======================================================================

class PaginaV2Crescimento:
    def render(self, repositorio):
        st.title("Crescimento e Rentabilidade")
        st.caption("O crescimento do Magalu está sendo convertido em "
                   "rentabilidade e geração de caixa?")

        ano = _seletor_ano(repositorio, key="v2_cresc_ano")
        gran = _seletor_granularidade(key="v2_cresc_gran")

        # --- Receita × EBITDA ---
        st.subheader("Receita × EBITDA")
        serie_rec = _serie(repositorio, "receita_liquida", gran, ano)
        serie_ebitda = _serie(repositorio, "ebitda", gran, ano)
        st.plotly_chart(
            g2.cresc_rent_receita_ebitda(serie_rec, serie_ebitda),
            width="stretch",
        )

        # --- Receita × Lucro Líquido ---
        st.subheader("Receita × Lucro Líquido")
        serie_lucro = _serie(repositorio, "lucro_liquido", gran, ano)
        st.plotly_chart(
            g2.cresc_rent_receita_lucro(serie_rec, serie_lucro),
            width="stretch",
        )

        # --- Crescimento × Margens ---
        st.subheader("Crescimento × Margens")
        serie_cresc = _serie(repositorio, "receita_liquida", gran, None).pct_change()
        serie_m_ebitda = _serie(repositorio, "margem_ebitda", gran, ano)
        serie_m_liquida = _serie(repositorio, "margem_liquida", gran, ano)
        st.plotly_chart(
            g2.cresc_rent_crescimento_margens(serie_cresc, serie_m_ebitda, serie_m_liquida),
            width="stretch",
        )

        # --- EBITDA × FCO ---
        st.subheader("EBITDA × Fluxo de Caixa Operacional")
        serie_fco = _serie(repositorio, "fluxo_caixa_operacional", gran, ano)
        st.plotly_chart(
            g2.cresc_rent_ebitda_fco(serie_ebitda, serie_fco),
            width="stretch",
        )

        _secao_insights(
            fatos=[
                "Receita Líquida, EBITDA e Lucro Líquido são fatos diretamente "
                "observados na guia '1. Indicadores'.",
                "O Fluxo de Caixa Operacional vem da guia '7. Fluxo de Caixa Gerencial'.",
            ],
            associacoes=[
                "Receita e EBITDA historicamente caminham juntos; a margem "
                "EBITDA, porém, tem se comprimido nos últimos períodos.",
            ],
            hipoteses=[
                "A compressão de margem pode estar associada ao aumento do "
                "mix de e-commerce (menor margem que lojas físicas) ou a "
                "investimentos em logística/tecnologia. Requer análise do Ato 4.",
            ],
        )

        _secao_como_interpretar(
            "Esta página cruza **crescimento (Receita)** com **rentabilidade "
            "(EBITDA, Lucro) e **geração de caixa (FCO)**. Um negócio pode "
            "crescer em receita e, ao mesmo tempo, perder margem — o que exige "
            "atenção. As margens vêm diretamente da planilha (não são recalculadas)."
        )


# ======================================================================
# PÁGINA 3 — OMNICHANNEL
# ======================================================================

class PaginaV2Omnichannel:
    def render(self, repositorio):
        st.title("Omnichannel e Transformação Digital")
        st.caption("Como mudou o motor de crescimento do Magalu e qual foi o "
                   "papel dos canais digitais?")

        ano = _seletor_ano(repositorio, key="v2_omni_ano")
        gran = _seletor_granularidade(key="v2_omni_gran")

        # --- Mix de canais ---
        st.subheader("Mix de canais")
        df_mix = pd.DataFrame({
            "Lojas Físicas": _serie(repositorio, "vendas_lojas_fisicas", gran, ano),
            "E-commerce 1P": _serie(repositorio, "vendas_ecommerce_1p", gran, ano),
            "Marketplace 3P": _serie(repositorio, "vendas_marketplace_3p", gran, ano),
        })
        if not df_mix.dropna(how="all").empty:
            st.plotly_chart(g2.omni_mix_canais(df_mix), width="stretch")
        else:
            st.info(mensagem_sem_dados("Mix de canais indisponível"))

        # --- Investimento em Tecnologia × Participação E-commerce ---
        st.subheader("Investimento em Tecnologia × Participação do E-commerce")
        serie_inv_tec = _serie(repositorio, "invest_tecnologia", gran, ano)
        serie_part_ec = _serie(repositorio, "participacao_ecommerce", gran, ano)
        st.plotly_chart(
            g2.omni_investimento_tecnologia_vs_ecommerce(serie_inv_tec, serie_part_ec),
            width="stretch",
        )

        # --- Receita por loja e por m² ---
        st.subheader("Receita por loja × Receita por m²")
        serie_vendas_lf = _serie(repositorio, "vendas_lojas_fisicas", gran, ano)
        serie_n_lojas = _serie(repositorio, "numero_lojas", gran, ano)
        serie_area = _serie(repositorio, "area_vendas", gran, ano)

        rec_loja = receita_por_loja(serie_vendas_lf, serie_n_lojas)
        rec_m2 = receita_por_m2(serie_vendas_lf, serie_area)
        if not rec_loja.empty or not rec_m2.empty:
            st.plotly_chart(
                g2.omni_receita_por_loja_e_m2(rec_loja, rec_m2),
                width="stretch",
            )
        else:
            st.info(mensagem_sem_dados("Receita por loja/m² indisponível"))

        _secao_insights(
            fatos=[
                "A composição de canais mudou: e-commerce ganhou participação "
                "no total de vendas.",
                "Investimento em Tecnologia e Logística é reportado separadamente "
                "na guia '10.Investimentos'.",
            ],
            associacoes=[
                "Períodos com maior investimento em Tecnologia tendem a coincidir "
                "com aumento posterior da participação do e-commerce. Trata-se de "
                "ASSOCIAÇÃO TEMPORAL — não de causalidade comprovada.",
            ],
            hipoteses=[
                "A queda do crescimento das mesmas lojas físicas pode estar "
                "relacionada à migração de demanda para canais digitais; "
                "requer análise de elasticidade cruzada.",
            ],
        )

        _secao_como_interpretar(
            "Esta página analisa a **transformação do mix de canais**. A análise "
            "defasada (investimento t × e-commerce t+1) mostra **associação "
            "temporal**, não causalidade. Recomenda-se interpretar junto com "
            "a página de Investimentos e Mercado."
        )


# ======================================================================
# PÁGINA 4 — CLIENTE, MARCA E REPUTAÇÃO
# ======================================================================

class PaginaV2Cliente:
    def render(self, repositorio):
        st.title("Cliente, Marca e Reputação")
        st.caption("A atenção à marca e a experiência percebida pelo consumidor "
                   "evoluíram de maneira coerente com o desempenho dos negócios?")

        ano = _seletor_ano(repositorio, key="v2_cli_ano")
        gran = _seletor_granularidade(key="v2_cli_gran")
        unidade = _seletor_unidade_ra(key="v2_cli_unidade")

        # --- Google Trends × Vendas ---
        st.subheader("Google Trends × Vendas Totais")
        st.caption("Google Trends aqui é tratado como **interesse/atenção pela marca**, "
                   "não como reputação ou satisfação.")
        serie_trends = None
        if repositorio.trends is not None and not repositorio.trends.serie_temporal.empty:
            serie_trends = repositorio.trends.serie_temporal.set_index("Data")["Quantidade"]
        serie_vendas = _serie(repositorio, "vendas_totais", gran, ano)
        st.plotly_chart(
            g2.cliente_trends_vs_vendas(serie_trends, serie_vendas),
            width="stretch",
        )




        # # --- RA por unidade de negócio ---
        # st.subheader(f"Reclame Aqui — {unidade.capitalize()}")
        # df_ra = None
        # if repositorio.reclame_aqui is not None:
        #     try:
        #         df_ra = repositorio.reclame_aqui.desempenho(unidade)
        #     except KeyError:
        #         st.info(f"Unidade '{unidade}' não encontrada no Reclame Aqui.")
        #         df_ra = None

        # --- RA por unidade de negócio ---
        st.subheader(f"Reclame Aqui — {unidade.capitalize()}")

        df_ra = None
        if repositorio.reclame_aqui is not None:
            try:
                df_ra_full = repositorio.reclame_aqui.desempenho(unidade)
                # Remove a linha "Geral" (total consolidado, não é período)
                df_ra = df_ra_full[
                    ~df_ra_full.index.astype(str).str.lower().isin(["geral", "total"])
                ].copy()
                # Ordena cronologicamente: extrai o ano do índice e ordena
                def _chave_ordenacao(idx):
                    texto = str(idx)
                    # tenta achar um ano de 4 dígitos
                    import re as _re
                    m = _re.search(r'(\d{4})', texto)
                    return int(m.group(1)) if m else 9999
                df_ra = df_ra.loc[sorted(df_ra.index, key=_chave_ordenacao)]
            except KeyError:
                st.info(f"Unidade '{unidade}' não encontrada no Reclame Aqui.")
                df_ra = None

        # Para alinhar as barras de RA (rótulos '2024') com a linha de Vendas
        # (datas reais), convertemos os rótulos de RA em timestamps.
        if df_ra is not None and not df_ra.empty:
            import re as _re
            novos_indices = []
            for rotulo in df_ra.index:
                texto = str(rotulo)
                m = _re.match(r'^(\d{4})$', texto)
                if m:
                    novos_indices.append(pd.Timestamp(year=int(m.group(1)), month=1, day=1))
                else:
                    # Semestre: '1S2024' / '2S2024'
                    m = _re.match(r'^(\d)S(\d{4})$', texto)
                    if m:
                        sem = int(m.group(1)); ano_ = int(m.group(2))
                        mes = 1 if sem == 1 else 7
                        novos_indices.append(pd.Timestamp(year=ano_, month=mes, day=1))
                    else:
                        novos_indices.append(rotulo)
            df_ra = df_ra.copy()
            df_ra.index = novos_indices
            df_ra = df_ra.sort_index()

        if unidade == "online":
            serie_v = _serie(repositorio, "vendas_ecommerce_total", gran, ano)
            st.plotly_chart(
                g2.cliente_ra_vs_vendas_online(df_ra, serie_v),
                width="stretch",
            )
        elif unidade == "fisica":
            serie_v = _serie(repositorio, "vendas_lojas_fisicas", gran, ano)
            st.plotly_chart(
                g2.cliente_ra_vs_vendas_fisica(df_ra, serie_v),
                width="stretch",
            )
        elif unidade == "luizacred":
            serie_fat = _serie(repositorio, "luizacred_faturamento", gran, ano)
            serie_luc = _serie(repositorio, "luizacred_lucro", gran, ano)
            st.plotly_chart(
                g2.cliente_luizacred(df_ra, serie_fat, serie_luc),
                width="stretch",
            )
        else:
            st.info("Sem cruzamento específico definido para esta unidade. "
                    "Exibindo apenas a Nota Média.")

        _secao_insights(
            fatos=[
                "Google Trends mede atenção/interesse de busca — não mede "
                "satisfação nem reputação.",
                "Reclame Aqui é proxy de experiência percebida, com limitações: "
                "só cobre quem registra reclamação.",
            ],
            associacoes=[
                f"Para a unidade '{unidade}', a nota média do Reclame Aqui "
                f"apresentou comportamento {('estável' if df_ra is not None and not df_ra.empty else 'indisponível')} "
                f"no período analisado.",
            ],
            hipoteses=[
                "A queda do interesse de busca pode estar associada à perda de "
                "relevância de marca em segmentos específicos — requer pesquisa "
                "de mercado para confirmar.",
            ],
        )

        _secao_como_interpretar(
            "Esta página separa explicitamente três dimensões: **atenção** "
            "(Google Trends), **experiência percebida** (Reclame Aqui) e "
            "**desempenho** (Vendas). Não misturamos indicadores de unidades "
            "de negócio diferentes. As análises mostram associações, não causas."
        )


# ======================================================================
# PÁGINA 5 — INVESTIMENTOS E MERCADO
# ======================================================================

class PaginaV2Investimentos:
    def render(self, repositorio):
        st.title("Investimentos e Mercado")
        st.caption("Os investimentos operacionais e a evolução dos fundamentos "
                   "foram acompanhados pela percepção de valor do mercado?")

        ano = _seletor_ano(repositorio, key="v2_inv_ano")
        gran = _seletor_granularidade(key="v2_inv_gran")

        # --- Investimentos × EBITDA ---
        st.subheader("Investimentos por categoria × EBITDA")
        df_inv = pd.DataFrame({
            "Tecnologia": _serie(repositorio, "invest_tecnologia", gran, ano),
            "Logística": _serie(repositorio, "invest_logistica", gran, ano),
            "Lojas Físicas": _serie(repositorio, "invest_lojas", gran, ano),
        })
        serie_ebitda = _serie(repositorio, "ebitda", gran, ano)
        if not df_inv.dropna(how="all").empty:
            st.plotly_chart(
                g2.invest_mercado_investimentos_vs_ebitda(df_inv, serie_ebitda),
                width="stretch",
            )
        else:
            st.info(mensagem_sem_dados("Investimentos indisponíveis"))

        # --- Base 100 ---
        st.subheader("Base 100 — desempenho operacional × mercado")
        st.caption("Usa 2018 como período inicial quando disponível.")

        series_base = {
            "Receita": _serie(repositorio, "receita_liquida", "anual", None),
            "EBITDA": _serie(repositorio, "ebitda", "anual", None),
            "Lucro": _serie(repositorio, "lucro_liquido", "anual", None),
            "Vendas Totais": _serie(repositorio, "vendas_totais", "anual", None),
        }

        if repositorio.cotacao is not None:
            fech = repositorio.cotacao.get_serie("Fechamento")
            if not fech.empty:
                # Agrega por ano SEM resample (evita o erro de 'Y' vs 'YE'):
                # pega o último fechamento de cada ano.
                fech_por_ano = fech.groupby(fech.index.year).last()
                fech_por_ano.index.name = "Ano"
                series_base["MGLU3"] = fech_por_ano

        df_base = pd.DataFrame({
            k: base_100(v) for k, v in series_base.items()
            if v is not None and not v.empty
        })
        if not df_base.empty:
            st.plotly_chart(g2.invest_mercado_base100(df_base), width="stretch")
        else:
            st.info(mensagem_sem_dados("Base 100 indisponível"))

        # --- Cotação × Volume ---
        st.subheader("Cotação MGLU3 × Volume negociado")
        if repositorio.cotacao is not None:
            fech = repositorio.cotacao.get_serie("Fechamento")
            vol = repositorio.cotacao.get_serie("Volume_Financeiro")
            if ano is not None:
                fech = fech[fech.index.year == ano]
                vol = vol[vol.index.year == ano]
            st.plotly_chart(
                g2.invest_mercado_cotacao_volume(fech, vol),
                width="stretch",
            )
        else:
            st.info(mensagem_sem_dados("Cotação indisponível"))

        _secao_insights(
            fatos=[
                "Investimentos são reportados por categoria (Tecnologia, "
                "Logística, Lojas, Outros) na guia '10.Investimentos'.",
                "Base 100 usa o primeiro período com dado de cada série.",
            ],
            associacoes=[
                "Possíveis aproximações ou descolamentos entre desempenho "
                "operacional (Receita, EBITDA, Lucro) e comportamento da ação "
                "(MGLU3) podem ser observados no gráfico Base 100.",
            ],
            hipoteses=[
                "O descolamento entre fundamentos e cotação pode refletir "
                "mudanças na percepção de risco do mercado — requer análise "
                "de múltiplos e comparação com pares do setor.",
            ],
        )

        _secao_como_interpretar(
            "Base 100 permite comparar trajetórias de séries com escalas "
            "diferentes (R$ e preço de ação). **Não** afirmamos que uma variável "
            "causou a outra — apenas mostramos se as trajetórias se aproximaram "
            "ou se descolaram no período."
        )


# ======================================================================
# PÁGINA 6 — RELAÇÕES ENTRE INDICADORES
# ======================================================================

class PaginaV2Relacoes:
    def render(self, repositorio):
        st.title("Relações entre Indicadores")
        st.caption("Ferramenta exploratória para investigar associações entre "
                   "variáveis.")

        st.warning(
            "⚠ **Uso responsável:** esta página calcula **correlação**, que "
            "mede associação — **não** causalidade. Sempre confira o número "
            "de observações (n) antes de tirar conclusões."
        )

        # Monta lista de séries disponíveis
        opcoes = {}
        for chave, (guia, indicador) in INDICADORES.items():
            opcoes[f"{chave} ({indicador})"] = chave
        if repositorio.trends is not None and not repositorio.trends.serie_temporal.empty:
            opcoes["Google Trends (mensal)"] = "__trends__"

        col1, col2, col3 = st.columns(3)
        with col1:
            var_x = st.selectbox("Variável X", list(opcoes.keys()), index=0, key="v2_rel_x")
        with col2:
            var_y = st.selectbox("Variável Y", list(opcoes.keys()), index=1, key="v2_rel_y")
        with col3:
            defasagem = st.number_input("Defasagem (períodos)", min_value=0, max_value=4,
                                        value=0, key="v2_rel_def")
            gran = _seletor_granularidade(key="v2_rel_gran")

        # Busca as séries
        def _buscar(chave):
            if chave == "__trends__":
                if repositorio.trends is None or repositorio.trends.serie_temporal.empty:
                    return pd.Series(dtype=float)
                return repositorio.trends.serie_temporal.set_index("Data")["Quantidade"]
            return _serie(repositorio, chave, gran, None)

        s_x = _buscar(opcoes[var_x])
        s_y = _buscar(opcoes[var_y])

        if s_x.empty or s_y.empty:
            st.info(mensagem_sem_dados("Uma das variáveis não tem dados disponíveis"))
            return

        # Correlação
        if defasagem > 0:
            r, n, _ = correlacao_defasada(s_x, s_y, defasagem=defasagem)
            rotulo_def = f" (X(t) vs Y(t+{defasagem}))"
        else:
            r, n, _ = correlacao_pearson(s_x, s_y)
            rotulo_def = ""

        if n < MIN_OBSERVACOES_CORRELACAO:
            st.warning(f"⚠ Apenas {n} observação(ões) em comum. "
                       f"Recomendado: ≥ {MIN_OBSERVACOES_CORRELACAO}. "
                       f"Resultado pode ser instável.")

        if not np.isnan(r):
            st.metric(f"Correlação de Pearson{rotulo_def}", f"r = {r:.3f}",
                      delta=f"n = {n}")
        else:
            st.info("Não foi possível calcular a correlação (variância zero ou "
                    "observações insuficientes).")

        # Dispersão
        fig = g2.relacoes_dispersao(s_x, s_y, var_x, var_y, r=r, n=n)
        st.plotly_chart(fig, width="stretch")

        _secao_insights(
            fatos=[
                f"Correlação calculada entre '{var_x}' e '{var_y}'"
                + (f" com defasagem de {defasagem} período(s)." if defasagem else "."),
                f"Número de observações usadas: {n}.",
            ],
            associacoes=[
                f"As variáveis apresentaram correlação r = {r:.3f}. "
                f"Lembrando: correlação mede associação, não causa."
                if not np.isnan(r) else
                "Não foi possível calcular correlação com os dados atuais.",
            ],
            hipoteses=[
                "Se a correlação for forte, vale investigar mecanismos "
                "causais com dados adicionais e/ou estudos qualitativos.",
            ],
        )

        _secao_como_interpretar(
            "Use esta página para **explorar** relações. Lembre-se:\n"
            "- **r** varia de -1 a +1. Perto de ±1 = relação linear forte.\n"
            "- **n** é o número de observações em comum.\n"
            "- Correlação **não** implica causalidade.\n"
            "- Defasagem testa se X antecede Y no tempo — ainda assim, não prova causa."
        )


# ======================================================================
# PÁGINAS ACADÊMICAS (reaproveitadas da v1)
# ======================================================================

from paginas_executivas import PaginaInicio, PaginaCargaHigienizacao  # noqa: E402