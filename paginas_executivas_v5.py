"""
paginas_executivas_v5.py
========================
Versão final unificada (v5) do dashboard executivo.
"""

import os
import re
import warnings
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from prophet import Prophet
from statsmodels.tsa.statespace.sarimax import SARIMAX

from config_indicadores import CORES, ANO_INICIAL, ANO_FINAL, MIN_OBSERVACOES_CORRELACAO
from eventos_estrategicos import (
    EVENTOS, EVENTOS_POR_ID, EVENTOS_ACAO, black_fridays, eventos_no_intervalo,
    rotulo_serie, unidade_serie, tabela_eventos, NOTAS_SERIE,
)
from magalu_macro import SelicLoader
from analises_eventos import (
    FonteSeries, avaliar_evento, avaliar_todos, tabela_para_exibicao, frase_leitura,
    placar, janelas_avaliacao, correlacao_por_defasagem, r_critico, variacao_aa,
    formatar_valor, period_para_rotulo, period_para_data,
    COERENTE, CONTRARIA, INCONCLUSIVO, SEM_DADOS, ICONE_VEREDITO, TEXTO_VEREDITO,
)
from analises import correlacao_pearson, base_100
from formatos import formata_moeda, formata_pct
from validacoes import mensagem_sem_dados

import graficos_v5 as g5

warnings.filterwarnings("ignore")

STATUS_TXT = {
    "verificado": "✅ fonte verificada",
    "conhecimento_publico": "🟡 data de conhecimento público — conferir fonte oficial",
    "a_confirmar": "🔴 a confirmar"
}
CHAVES_COM_SINAL = {"lucro_liquido", "lucro_liquido_ajustado", "resultado_financeiro", "fluxo_caixa_operacional", "fluxo_caixa_financiamento", "fluxo_caixa_investimento", "luizacred_lucro"}

# ----------------------------------------------------------------------
# Helpers comuns e Contexto
# ----------------------------------------------------------------------
def _esc(texto):
    return texto.replace("\\$", "$").replace("$", "\\$") if isinstance(texto, str) else texto

def _markdown(texto, *args, **kwargs): return st.markdown(_esc(texto), *args, **kwargs)
def _caption(texto, *args, **kwargs): return st.caption(_esc(texto), *args, **kwargs)
def _info(texto, *args, **kwargs): return st.info(_esc(texto), *args, **kwargs)
def _warning(texto, *args, **kwargs): return st.warning(_esc(texto), *args, **kwargs)
def _success(texto, *args, **kwargs): return st.success(_esc(texto), *args, **kwargs)

class ContextoV5:
    def __init__(self, selic, fonte):
        self.selic = selic
        self.fonte = fonte

@st.cache_resource(show_spinner="Preparando a camada de eventos: Selic, cotação ajustada...")
def _obter_selic(): return SelicLoader()

def obter_contexto_v5(repositorio):
    selic = _obter_selic()
    return ContextoV5(selic, FonteSeries(repositorio, selic))

def _controles(prefixo, repositorio):
    ctx = obter_contexto_v5(repositorio)
    ano_ini, ano_fim = st.sidebar.slider("Período exibido", ANO_INICIAL, ANO_FINAL, (ANO_INICIAL, ANO_FINAL), key=f"{prefixo}_anos")
    mostrar = st.sidebar.checkbox("Mostrar rótulos dos eventos", value=True, key=f"{prefixo}_rot")
    return ctx, ano_ini, ano_fim, mostrar

def _evs(ids, ano_ini, ano_fim): return eventos_no_intervalo([EVENTOS_POR_ID[i] for i in ids if i in EVENTOS_POR_ID], ano_ini, ano_fim)

def _spec(fonte, chave, eixo=1, tipo=None, cor=None, nome=None, **kw):
    un = unidade_serie(chave)
    tipo = tipo or ("barra" if un == "moeda" else "linha")
    fmt = {"moeda": "num", "pct": "pct", "preco": "preco", "indice": "indice", "num": "num"}.get(un, "num")
    d = dict(nome=nome or rotulo_serie(chave), serie=fonte.trimestral(chave), tipo=tipo, eixo=eixo, fmt=fmt)
    if cor: d["cor"] = cor
    if tipo == "barra" and chave in CHAVES_COM_SINAL: d["cor_sinal"] = True
    d.update(kw)
    return d

def _avisar_faltantes(fonte, chaves):
    faltam = [rotulo_serie(c) for c in chaves if not fonte.disponivel(c)]
    if faltam: _warning("⚠ Séries indisponíveis nos dados carregados: " + ", ".join(faltam) + ".")

def _secao_insights(fatos, associacoes, hipoteses):
    _markdown("### Insights")
    if fatos:
        _markdown("**Fatos observados:**")
        for f in fatos: _markdown(f"- {f}")
    if associacoes:
        _markdown("**Associações:**")
        for a in associacoes: _markdown(f"- {a}")
    if hipoteses:
        _markdown("**Hipóteses (requerem investigação):**")
        for h in hipoteses: _markdown(f"- {h}")

def _como_interpretar(texto):
    with st.expander("Como interpretar"): _markdown(texto)

def _bloco_fontes(eventos, titulo="📰 Contexto do mundo real (com fontes)"):
    with st.expander(titulo):
        if not eventos: _caption("Nenhum evento no período selecionado.")
        for ev in sorted(eventos, key=lambda e: e.data_inicio):
            _markdown(f"**{ev.nome}** — {ev.data_exibicao} · _{ev.categoria}, evento {ev.origem}_")
            _markdown(ev.descricao)
            if ev.fontes: _markdown("Fontes: " + " · ".join(f"[{t}]({u})" for t, u in ev.fontes))
            _caption(STATUS_TXT[ev.status]); _markdown("---")

def _tabela_avaliacao(fonte, ev, n, titulo=None):
    df = avaliar_evento(fonte, ev, n)
    if titulo: _markdown(f"**{titulo}**")
    if df.empty:
        _caption("Este evento é contexto (sem hipótese direcional).")
        return df
    st.dataframe(tabela_para_exibicao(df), hide_index=True, width="stretch")
    return df

def _frases_numeros(df):
    return [f"{r['Indicador']}: {formatar_valor(r['chave'], r['antes'])} → {formatar_valor(r['chave'], r['depois'])}" for _, r in df.iterrows() if r["Veredito"] != SEM_DADOS]
def _frases_associacao(df): return [frase_leitura(r) for r in df.to_dict("records") if r["Veredito"] != SEM_DADOS]
def _deslocar_futuro(s, k):
    if s is None or s.empty or k == 0: return s
    return s.reindex(pd.period_range(s.index.min(), s.index.max(), freq="Q")).shift(-k).dropna()
def _cobertura(fonte, chave):
    s = fonte.trimestral(chave)
    return f"{rotulo_serie(chave)}: {period_para_rotulo(s.index.min())} a {period_para_rotulo(s.index.max())} ({len(s)} trimestres)." if not s.empty else f"{rotulo_serie(chave)}: indisponível."

# ======================================================================
# PÁGINA 0 — Abertura
# ======================================================================
class PaginaAbertura:
    def render(self, repositorio):
        try: st.image("logo.png", width=400)
        except: pass
        st.title("Dashboard Executivo — Magazine Luiza")
        st.markdown("Esta apresentação foi desenvolvida para responder a uma pergunta central da diretoria: **Como o desempenho financeiro, a transformação dos canais, os investimentos, a percepção do consumidor e o comportamento do mercado evoluíram juntos no Magalu?**")
        st.markdown("""
        <style>
        .card-item { background-color: #0086FF; color: white !important; border-radius: 12px; padding: 15px; margin-bottom: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); transition: transform 0.2s; height: 100%; box-sizing: border-box; }
        .card-item:hover { transform: translateY(-3px); box-shadow: 0 6px 12px rgba(0,0,0,0.15); }
        .card-title { font-weight: bold; font-size: 1.05em; margin-bottom: 5px; color: white !important; }
        .card-desc { font-size: 0.85em; color: #f0f0f0 !important; margin: 0; line-height: 1.3; }
        .card-desc em { color: #ffeb3b !important; font-style: normal; font-weight: bold; }
        .section-header { color: #333; font-size: 1.3em; font-weight: bold; margin-bottom: 15px; border-bottom: 2px solid #0086FF; padding-bottom: 5px; }
        </style>
        """, unsafe_allow_html=True)

        col_esq, col_dir = st.columns([3, 1])
        with col_esq:
            st.markdown('<div class="section-header">Análise Executiva (7 Blocos)</div>', unsafe_allow_html=True)
            cards = [
                ("1. Linha do Tempo", "Contexto.", "Eventos externos e decisões internas."),
                ("2. Eventos × Indicadores", "Diagnóstico.", "Ferramenta interativa para testar hipóteses."),
                ("3. Juros e Lucro", "Rentabilidade.", "Impacto da Selic no resultado final vs. EBITDA."),
                ("4. Investimentos e Mercado", "Retorno.", "Aportes em tech/logística e reação da bolsa."),
                ("5. Omnichannel", "Crescimento.", "Mix de canais e busca por margens maiores."),
                ("6. Marca e Reputação", "Percepção.", "Interesse de busca e saúde reputacional (RA)."),
                ("7. Projeções Preditivas", "Futuro.", "Modelos SARIMAX e Prophet.")
            ]
            sub_col1, sub_col2 = st.columns(2)
            for i, (title, context, desc) in enumerate(cards):
                with (sub_col1 if i % 2 == 0 else sub_col2):
                    st.markdown(f'<div class="card-item"><div class="card-title">{title}</div><div class="card-desc"><em>{context}</em> {desc}</div></div>', unsafe_allow_html=True)
        with col_dir:
            st.markdown('<div class="section-header" style="border-color: #7F8C8D;">Apoio Acadêmico</div>', unsafe_allow_html=True)
            for title, subtitle, desc in [("Objetivo do Projeto", "Fontes", "Origem dos dados."), ("Carga", "Transparência", "Limpeza dos dados.")]:
                st.markdown(f'<div class="card-item" style="background-color: #5D6D7E;"><div class="card-title">{title}</div><div class="card-desc"><em>{subtitle}.</em> {desc}</div></div>', unsafe_allow_html=True)

# ======================================================================
# PÁGINA 1 — LINHA DO TEMPO
# ======================================================================
class PaginaV5Timeline:
    def render(self, repositorio):
        st.title("1 - Linha do Tempo Estratégica do Magalu")
        _caption("Quais eventos estratégicos e de mercado ajudam a explicar os movimentos observados nos indicadores?")
        ano_ini, ano_fim = st.sidebar.slider("Período", ANO_INICIAL, ANO_FINAL, (ANO_INICIAL, ANO_FINAL), key="v5_tl_anos")
        origens = st.sidebar.multiselect("Origem", ["externo", "interno"], default=["externo", "interno"], key="v5_tl_orig")
        eventos = [e for e in eventos_no_intervalo(EVENTOS, ano_ini, ano_fim) if e.origem in origens]

        _info("**Regra de leitura:** eventos dão **contexto**, não provam causa. Laranja = evento externo; azul = interno. Cada evento tem fonte e status de verificação.")
        st.plotly_chart(g5.timeline_estrategica(eventos, ano_ini, ano_fim), width="stretch")

        st.subheader("Do evento à percepção do mercado")
        st.graphviz_chart(g5.modelo_conceitual_dot())

        st.subheader("Eventos catalogados")
        df = tabela_eventos()
        st.dataframe(df[df["Evento"].isin([e.nome for e in eventos])], hide_index=True, width="stretch")

        _bloco_fontes(eventos)
        
        with st.expander("🛠 Qualidade dos dados e Auditoria Factual", expanded=False):
            ctx = obter_contexto_v5(repositorio)
            for a in ctx.fonte.relatorio_ajuste: _markdown(f"- Cotação: {a}")
            _markdown(f"- Selic: fonte **{ctx.selic.fonte}**.")
            _markdown("- **Retorno ao lucro:** ocorreu no 4T23 (1º lucro ajustado em 2 anos), e não em 2024. O ano de 2023 ainda foi de prejuízo ajustado.")
            _markdown("- **A história não termina na recuperação:** em 2025 a Selic chegou a 15% e no 2T26 o resultado voltou ao prejuízo.")
            _markdown("- **Cotação MGLU3:** a ação passou por desdobramentos (1:8 em 08/2019, 1:4 em 10/2020) e grupamento 10:1 (27/05/2024). A apresentação atual detecta e corrige.")

        _secao_insights(
            fatos=[f"O catálogo reúne {len(EVENTOS)} eventos, cada um com data e fonte."],
            associacoes=["Eventos externos (pandemia, Selic) e internos (aquisições) ocorrem sobrepostos no tempo."],
            hipoteses=["A combinação de expansão por aquisições (2020–21) e juros altos (2022–23) pode explicar a pressão sobre o lucro."]
        )
        _como_interpretar("A linha do tempo organiza o contexto. Para cada evento, as demais páginas mostram os indicadores antes e depois e classificam a hipótese como coerente, contrária ou inconclusiva.")

# ======================================================================
# PÁGINA 2 — EVENTOS × INDICADORES
# ======================================================================
class PaginaV5EventosIndicadores:
    def render(self, repositorio):
        st.title("2 - Eventos × Indicadores")
        _caption("Escolha um evento: o painel destaca os indicadores ligados a ele e confere, com os seus dados, se a hipótese direcional se sustenta.")
        ctx, ano_ini, ano_fim, mostrar = _controles("v5_ei", repositorio)
        n = st.sidebar.slider("Janela (trimestres)", 2, 8, 4, key="v5_ei_n")
        fonte = ctx.fonte

        ordenados = sorted(EVENTOS, key=lambda e: e.data_inicio)
        rotulos = {f"{e.data_inicio.year} · {e.nome}": e for e in ordenados}
        ev = rotulos[st.selectbox("Evento", list(rotulos.keys()), index=list(rotulos.values()).index(EVENTOS_POR_ID["kabum"]), key="v5_ei_evento")]

        c1, c2, c3 = st.columns(3)
        c1.metric("Data", ev.data_exibicao); c2.metric("Categoria", ev.categoria); c3.metric("Origem", ev.origem.capitalize())
        _markdown(ev.descricao)
        if ev.o_que_olhar: _markdown(f"**O que olhar:** {ev.o_que_olhar}")
        _caption(STATUS_TXT[ev.status])
        if ev.fontes: _markdown("Fontes: " + " · ".join(f"[{t}]({u})" for t, u in ev.fontes))

        st.subheader("O que aconteceu nos dados?")
        df = _tabela_avaliacao(fonte, ev, n)
        if not df.empty:
            for fr in _frases_associacao(df): _markdown(f"- {fr}")
            _caption(f"Limiares: variação ≥ 5% (valores) ou ≥ 0,5 p.p. (percentuais).")

        st.subheader("Indicadores destacados")
        disponiveis = [c for c in ev.destaques if fonte.disponivel(c)]
        _avisar_faltantes(fonte, ev.destaques)
        
        colunas = st.columns(2)
        for i, chave in enumerate(disponiveis):
            exp = next((e for e in ev.expectativas if e.chave == chave), None)
            j = janelas_avaliacao(ev, exp.modo if exp else "medio", n)
            faixas = [dict(x0=j.antes[0].start_time, x1=j.antes[1].end_time, rotulo="antes", cor="#7F8C8D"), dict(x0=j.depois[0].start_time, x1=j.depois[1].end_time, rotulo="depois", cor=CORES["positivo"])]
            spec = _spec(fonte, chave, **({"degrau": True} if chave == "selic" else {}))
            fig = g5.serie_com_eventos([spec], [ev], rotulo_serie(chave), y1_titulo={"moeda": "R$ milhões", "pct": "%", "preco": "R$", "indice": "índice"}.get(spec["fmt"], ""), fmt_y1=spec["fmt"], faixas=faixas, ano_ini=ano_ini, ano_fim=ano_fim, mostrar_rotulos=mostrar, altura=340)
            with colunas[i % 2]:
                st.plotly_chart(fig, width="stretch", key=f"v5_ei_{ev.id}_{chave}")
                if chave in NOTAS_SERIE: _caption(NOTAS_SERIE[chave])

        _bloco_fontes([ev], titulo="📰 Detalhe e fontes do evento")
        _markdown("---")
        
        st.subheader("Placar de coerência — todos os eventos")
        df_todos = avaliar_todos(fonte, EVENTOS, n)
        p = placar(df_todos)
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("✅ Coerentes", p[COERENTE]); k2.metric("❌ Contrárias", p[CONTRARIA]); k3.metric("➖ Inconclusivas", p[INCONCLUSIVO]); k4.metric("⚠ Sem dados", p[SEM_DADOS])
        
        if not df_todos.empty:
            st.plotly_chart(g5.placar_coerencia(df_todos), width="stretch", key="v5_ei_placar")
            contr = df_todos[df_todos["Veredito"] == CONTRARIA]
            if not contr.empty:
                _markdown("**Onde os dados NÃO confirmam a narrativa:**")
                for r in contr.to_dict("records"): _markdown(f"- _{r['Evento']}_ → {frase_leitura(r)}")
            with st.expander("Ver todas as hipóteses testadas"):
                mostrar_df = df_todos[["Evento", "Indicador", "Hipótese", "Janela antes", "Janela depois", "Variação", "Veredito", "Nota"]].copy()
                mostrar_df["Veredito"] = mostrar_df["Veredito"].map(lambda v: f"{ICONE_VEREDITO[v]} {TEXTO_VEREDITO[v]}")
                st.dataframe(mostrar_df, hide_index=True, width="stretch")

        _como_interpretar("O teste compara a média de N trimestres antes com a de N depois. **Coerente** significa que a direção bate com a hipótese e supera o limiar. Limitações: não controla outros eventos simultâneos.")

# ======================================================================
# PÁGINA 3 — JUROS, LUCRO E VIRADA
# ======================================================================
class PaginaV5Juros:
    def render(self, repositorio):
        st.title("3 - Juros, Lucro e a Virada")
        _caption("Apesar do crescimento de vendas, a rentabilidade ficou pressionada pelos juros? A recuperação de 2023–24 se sustentou?")
        ctx, ano_ini, ano_fim, mostrar = _controles("v5_jr", repositorio)
        fonte = ctx.fonte
        tipo_lucro = st.sidebar.radio("Lucro exibido", ["Ajustado", "Contábil"], key="v5_jr_lucro")
        chave_lucro = "lucro_liquido_ajustado" if tipo_lucro == "Ajustado" else "lucro_liquido"
        n = st.sidebar.slider("Janela (trimestres)", 2, 8, 4, key="v5_jr_n")
        evs = _evs(["juros_altos", "selic_cortes_2023", "virada_4t23", "selic_15", "selic_cortes_2026", "reversao_2t26"], ano_ini, ano_fim)
        
        _avisar_faltantes(fonte, [chave_lucro, "margem_ebitda", "margem_liquida", "resultado_financeiro", "fluxo_caixa_operacional", "mglu3", "selic"])
        _caption(f"Fonte da Selic: **{ctx.selic.fonte}**.")

        st.header("Caso 3 · A crise dos juros")
        st.subheader("Selic × lucro líquido")
        fig = g5.serie_com_eventos([_spec(fonte, chave_lucro, nome=f"Lucro líquido ({tipo_lucro.lower()})"), _spec(fonte, "selic", eixo=2, cor=CORES["negativo"], degrau=True, fmt="pct2", largura=3)], evs, "Selic × Lucro", y1_titulo="R$ milhões", y2_titulo="Selic (% a.a.)", fmt_y2="pct2", ano_ini=ano_ini, ano_fim=ano_fim, mostrar_rotulos=mostrar)
        st.plotly_chart(fig, width="stretch", key="v5_jr_selic_lucro")

        st.subheader("Operação × resultado final")
        fig = g5.serie_com_eventos([_spec(fonte, "margem_ebitda", cor=CORES["positivo"], largura=3), _spec(fonte, "margem_liquida", cor=CORES["primaria"], largura=3), _spec(fonte, "resfin_sobre_receita", cor=CORES["negativo"], dash="dot"), _spec(fonte, "selic", eixo=2, cor=CORES["neutro"], degrau=True, fmt="pct2", dash="dash", largura=1.8)], evs, "Margens × Resultado Financeiro", y1_titulo="%", fmt_y1="pct", y2_titulo="Selic (% a.a.)", fmt_y2="pct2", ano_ini=ano_ini, ano_fim=ano_fim, mostrar_rotulos=mostrar)
        st.plotly_chart(fig, width="stretch", key="v5_jr_margens")

        st.subheader("Selic e peso financeiro: associação?")
        transf = st.radio("Base", ["Níveis", "Variação a/a"], horizontal=True, key="v5_jr_transf")
        corr = correlacao_por_defasagem(fonte.trimestral("selic"), fonte.trimestral("resfin_sobre_receita"), range(-2, 5), "nivel" if transf == "Níveis" else "aa")
        st.plotly_chart(g5.barras_defasagem(corr, "Selic (t) × Res. Financeiro (t+k)", r_critico(int(corr["n"].median()) if not corr.empty else 0)), width="stretch", key="v5_jr_lag")

        st.subheader("Fluxo de caixa operacional × cotação MGLU3")
        fig = g5.serie_com_eventos([_spec(fonte, "fluxo_caixa_operacional", cor=CORES["secundaria"]), _spec(fonte, "mglu3", eixo=2, cor=CORES["mercado"], fmt="preco", largura=3, nome="MGLU3 (ajustada)")], evs, "FCO × MGLU3", y1_titulo="R$ milhões", y2_titulo="R$ (ajustado)", fmt_y2="preco", ano_ini=ano_ini, ano_fim=ano_fim, mostrar_rotulos=mostrar)
        st.plotly_chart(fig, width="stretch", key="v5_jr_fco_mglu")

        st.header("Caso 5 · Retorno ao lucro (e o que veio depois)")
        self._painel_virada(fonte, n)
        df_juros = _tabela_avaliacao(fonte, EVENTOS_POR_ID["juros_altos"], n, "Juros elevados — antes × depois")
        df_virada = _tabela_avaliacao(fonte, EVENTOS_POR_ID["virada_4t23"], n, "Virada do 4T23 — antes × depois")
        df_rev = _tabela_avaliacao(fonte, EVENTOS_POR_ID["reversao_2t26"], n, "2T26 — contra o 2T25")

        _bloco_fontes(evs)
        _secao_insights(
            fatos=[_cobertura(fonte, chave_lucro), _cobertura(fonte, "resultado_financeiro")] + _frases_numeros(df_juros)[:3],
            associacoes=_frases_associacao(df_juros) + _frases_associacao(df_virada),
            hipoteses=["Parte relevante da pressão sobre o lucro em 2022–23 pode vir das despesas financeiras, e não da operação."]
        )

    def _painel_virada(self, fonte, n):
        lucro_aj = fonte.trimestral("lucro_liquido_ajustado")
        if not lucro_aj.empty:
            primeiro = lucro_aj[(lucro_aj.index >= pd.Period("2022Q1")) & (lucro_aj > 0)]
            ultimo_antes = lucro_aj[(lucro_aj.index < pd.Period("2022Q1")) & (lucro_aj > 0)]
            c1, c2 = st.columns(2)
            if not ultimo_antes.empty: c1.metric("Último lucro antes da sequência", period_para_rotulo(ultimo_antes.index[-1]))
            if not primeiro.empty: c2.metric("Primeiro lucro após a sequência", period_para_rotulo(primeiro.index[0]))

        chaves = [("lucro_liquido", "Lucro líquido"), ("lucro_liquido_ajustado", "Lucro ajustado"), ("ebitda", "EBITDA"), ("fluxo_caixa_operacional", "Fluxo de caixa"), ("resultado_financeiro", "Res. Financeiro Líquido")]
        anual = {rot: fonte.anual(ch) for ch, rot in chaves}
        anos = sorted(set().union(*[set(s.index) for s in anual.values() if not s.empty]))
        anos = [a for a in anos if a >= 2021]
        
        if anos:
            linhas = []
            for (ch, rot) in chaves:
                s = anual[rot]
                linhas.append({"Indicador": rot, **{str(a): formatar_valor(ch, s.get(a)) if a in s.index else "—" for a in anos}})
            _markdown("**Anos completos (soma dos 4 trimestres):**")
            st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch")
            
        ult = fonte.trimestral("lucro_liquido")
        if not ult.empty: _caption(f"Último trimestre na planilha: {period_para_rotulo(ult.index[-1])}.")

# ======================================================================
# PÁGINA 4 — INVESTIMENTOS, DIGITAL E MERCADO
# ======================================================================
class PaginaV5InvestimentosDigitalMercado:
    def render(self, repositorio):
        st.title("4 - Investimentos, Digital e Mercado")
        st.caption("Como os investimentos em tecnologia/logística impulsionaram o digital e como o mercado reagiu?")
        ctx, ano_ini, ano_fim, mostrar = _controles("v5_inv", repositorio)
        fonte = ctx.fonte
        evs = _evs(["covid", "aquisicoes", "kabum", "followon", "aporte_2024", "virada_4t23"], ano_ini, ano_fim)
        _avisar_faltantes(fonte, ["vendas_ecommerce_1p", "vendas_marketplace_3p", "participacao_ecommerce", "invest_tecnologia", "invest_total", "invest_logistica", "ebitda", "mglu3"])

        st.header("1. A transformação digital e os investimentos")
        st.plotly_chart(g5.serie_com_eventos([_spec(fonte, "invest_tecnologia", cor=CORES["invest"]), _spec(fonte, "participacao_ecommerce", eixo=2, cor=CORES["primaria"], largura=3)], evs, "Investimento em tecnologia × Participação E-commerce", y1_titulo="R$ milhões", y2_titulo="%", fmt_y2="pct", ano_ini=ano_ini, ano_fim=ano_fim, mostrar_rotulos=mostrar), width="stretch")

        st.plotly_chart(g5.serie_com_eventos([_spec(fonte, "vendas_ecommerce_1p", cor=CORES["secundaria"]), _spec(fonte, "vendas_marketplace_3p", cor=CORES["acento"]), _spec(fonte, "participacao_ecommerce", eixo=2, cor=CORES["primaria"], largura=3)], evs, "Mix E-commerce e Participação", y1_titulo="R$ milhões", y2_titulo="%", fmt_y2="pct", ano_ini=ano_ini, ano_fim=ano_fim, mostrar_rotulos=mostrar, empilhar=True), width="stretch")

        st.header("2. O retorno dos investimentos e a percepção do mercado")
        df_inv = pd.DataFrame({"Tecnologia": fonte.trimestral("invest_tecnologia"), "Logística": fonte.trimestral("invest_logistica"), "Lojas Físicas": fonte.trimestral("invest_lojas")})
        if not df_inv.dropna(how="all").empty:
            fig = g5.serie_com_eventos([dict(nome=c, serie=df_inv[c].dropna(), tipo="barra", eixo=1, fmt="num", cor=CORES["invest"] if c=="Tecnologia" else (CORES["secundaria"] if c=="Logística" else CORES["acento"])) for c in df_inv.columns] + [_spec(fonte, "ebitda", eixo=2, cor=CORES["acento"], largura=3)], evs, "Investimentos × EBITDA", y1_titulo="R$ milhões", y2_titulo="EBITDA", fmt_y2="num", ano_ini=ano_ini, ano_fim=ano_fim, mostrar_rotulos=mostrar, empilhar=True)
            st.plotly_chart(fig, width="stretch")

        st.subheader("Base 100 — desempenho operacional × percepção de mercado")
        series_base = {"Receita": fonte.anual("receita_liquida"), "EBITDA": fonte.anual("ebitda"), "Lucro": fonte.anual("lucro_liquido"), "Vendas Totais": fonte.anual("vendas_totais")}
        if not fonte.trimestral("mglu3").empty: series_base["MGLU3"] = fonte.anual("mglu3")
        df_base = pd.DataFrame({k: base_100(v) for k, v in series_base.items() if v is not None and not v.empty})
        if not df_base.empty: st.plotly_chart(g5.invest_mercado_base100(df_base), width="stretch")

        st.subheader("Cotação MGLU3 × Volume negociado")
        serie_mglu3 = fonte.trimestral("mglu3").dropna()
        serie_vol = repositorio.cotacao.get_serie("Volume_Financeiro").dropna() if repositorio.cotacao else pd.Series(dtype=float)
        if not serie_mglu3.empty and not serie_vol.empty:
            if isinstance(serie_mglu3.index, pd.PeriodIndex): serie_mglu3.index = serie_mglu3.index.to_timestamp()
            if not isinstance(serie_vol.index, pd.DatetimeIndex): serie_vol.index = pd.to_datetime(serie_vol.index)
            st.plotly_chart(g5.invest_mercado_cotacao_volume(serie_mglu3, serie_vol), width="stretch")

        n = st.sidebar.slider("Janela (trimestres)", 2, 8, 4, key="v5_inv_n")
        df_kabum = _tabela_avaliacao(fonte, EVENTOS_POR_ID["kabum"], n, "KaBuM! — antes × depois")
        df_aporte = _tabela_avaliacao(fonte, EVENTOS_POR_ID["aporte_2024"], n, "Aporte R$ 1,25 bi — antes × depois")

        _bloco_fontes(evs)
        _secao_insights(
            fatos=[_cobertura(fonte, "participacao_ecommerce"), _cobertura(fonte, "invest_total")] + _frases_numeros(df_kabum)[:3],
            associacoes=_frases_associacao(df_kabum) + _frases_associacao(df_aporte),
            hipoteses=["O descolamento entre fundamentos e cotação pode refletir mudanças na percepção de risco do mercado."]
        )

# ======================================================================
# PÁGINA 5 — OMNICHANNEL E MARKETPLACE
# ======================================================================
class PaginaV5OmnichannelMarketplace:
    def render(self, repositorio):
        st.title("5 - Omnichannel e Marketplace")
        st.caption("Como mudou o motor de crescimento do Magalu e qual foi o papel do marketplace na rentabilidade?")
        ctx, ano_ini, ano_fim, mostrar = _controles("v5_omni", repositorio)
        fonte = ctx.fonte
        n = st.sidebar.slider("Janela (trimestres)", 2, 8, 4, key="v5_omni_n")
        evs = _evs(["marketplace", "virada_4t23", "reversao_2t26", "covid"], ano_ini, ano_fim)
        _avisar_faltantes(fonte, ["vendas_lojas_fisicas", "vendas_ecommerce_1p", "vendas_marketplace_3p", "vendas_totais", "share_3p", "margem_ebitda"])

        st.header("1. O mix de canais")
        st.plotly_chart(g5.serie_com_eventos([_spec(fonte, "vendas_lojas_fisicas", cor=CORES["secundaria"]), _spec(fonte, "vendas_ecommerce_1p", cor=CORES["invest"]), _spec(fonte, "vendas_marketplace_3p", cor=CORES["acento"]), _spec(fonte, "participacao_ecommerce", eixo=2, cor=CORES["primaria"], largura=3)], evs, "Mix de canais", y1_titulo="R$ milhões", y2_titulo="%", fmt_y2="pct", ano_ini=ano_ini, ano_fim=ano_fim, mostrar_rotulos=mostrar, empilhar=True), width="stretch")

        st.subheader("Receita por loja × Receita por m²")
        rec_loja = (fonte.trimestral("vendas_lojas_fisicas") / fonte.trimestral("numero_lojas").replace(0, np.nan)).dropna()
        rec_m2 = (fonte.trimestral("vendas_lojas_fisicas") / fonte.trimestral("area_vendas").replace(0, np.nan)).dropna()
        if not rec_loja.empty or not rec_m2.empty: st.plotly_chart(g5.omni_receita_por_loja_e_m2(rec_loja, rec_m2), width="stretch")

        st.header("2. Marketplace, margem e rentabilidade")
        st.plotly_chart(g5.serie_com_eventos([_spec(fonte, "vendas_marketplace_3p", cor=CORES["acento"]), _spec(fonte, "share_3p", eixo=2, cor=CORES["primaria"], largura=3)], evs, "Marketplace 3P × Participação", y1_titulo="R$ milhões", y2_titulo="%", fmt_y2="pct", ano_ini=ano_ini, ano_fim=ano_fim, mostrar_rotulos=mostrar), width="stretch")
        st.plotly_chart(g5.serie_com_eventos([_spec(fonte, "share_3p", cor=CORES["acento"], largura=3), _spec(fonte, "margem_bruta", cor=CORES["secundaria"]), _spec(fonte, "margem_ebitda", cor=CORES["positivo"], largura=3)], evs, "Marketplace × Margens", y1_titulo="%", fmt_y1="pct", ano_ini=ano_ini, ano_fim=ano_fim, mostrar_rotulos=mostrar), width="stretch")

        df_mk = _tabela_avaliacao(fonte, EVENTOS_POR_ID["marketplace"], n, "Marketplace — durante × antes")
        df_rev = _tabela_avaliacao(fonte, EVENTOS_POR_ID["reversao_2t26"], n, "2T26 — contra o 2T25")

        _bloco_fontes(evs)
        _secao_insights(
            fatos=[_cobertura(fonte, "vendas_marketplace_3p")] + _frases_numeros(df_mk)[:4],
            associacoes=_frases_associacao(df_mk) + _frases_associacao(df_rev),
            hipoteses=["Em 2026 o marketplace recua enquanto a margem se mantém: pode indicar que o motor de margem migrou para lojas físicas e crédito."]
        )

# ======================================================================
# PÁGINA 6 — CLIENTE, MARCA E REPUTAÇÃO
# ======================================================================
class PaginaV5Cliente:
    def render(self, repositorio):
        st.title("6 - Cliente, Marca e Reputação")
        st.caption("A atenção à marca e a experiência percebida pelo consumidor evoluíram de maneira coerente com o desempenho?")
        ctx, ano_ini, ano_fim, mostrar = _controles("v5_cli", repositorio)
        fonte = ctx.fonte
        ano = st.sidebar.slider("Ano (Reclame Aqui)", ANO_INICIAL, ANO_FINAL, ANO_FINAL, key="v5_cli_ano")
        unidade = st.sidebar.selectbox("Unidade (RA)", ["online", "fisica", "luizacred", "consorcio"], key="v5_cli_uni")
        evs = _evs(["covid", "kabum", "followon", "virada_4t23", "reversao_2t26"], ano_ini, ano_fim)

        st.header("Caso 6 · Marca e interesse do consumidor")
        trends_m = fonte.trends_mensal()
        if not trends_m.empty:
            bf = st.checkbox("Marcar Black Friday", value=True, key="v5_cli_bf")
            fig = g5.serie_com_eventos([dict(nome="Google Trends (mensal)", serie=trends_m, tipo="linha", eixo=1, fmt="indice", cor=CORES["trends"], largura=2), _spec(fonte, "vendas_totais", eixo=2, cor=CORES["secundaria"], opacidade=0.35)], evs, "Google Trends × Vendas Totais", y1_titulo="Interesse", y2_titulo="Vendas", fmt_y2="num", ano_ini=ano_ini, ano_fim=ano_fim, mostrar_rotulos=mostrar, eventos_leves=black_fridays(ano_ini, ano_fim) if bf else None)
            st.plotly_chart(fig, width="stretch")
            
            corr = correlacao_por_defasagem(fonte.trimestral("trends"), fonte.trimestral("vendas_totais"), range(-4, 5), "aa")
            st.plotly_chart(g5.barras_defasagem(corr, "Trends(t) × Vendas(t+k)", r_critico(int(corr["n"].median()) if not corr.empty else 0)), width="stretch")
        else:
            _warning("Google Trends indisponível.")

        st.header("Caso 7 · Reputação do consumidor (Reclame Aqui)")
        _warning("**Limite dos dados:** O Reclame Aqui cobre apenas 2024, 2025 e 1S2026. Isso não permite testar eventos de 2020–2023 e impede correlações longas.")
        ra = getattr(repositorio, "reclame_aqui", None)
        if ra is None:
            _info("Reclame Aqui indisponível.")
        else:
            if unidade == "online":
                st.plotly_chart(g5.cliente_ra_vs_vendas_online(ra.desempenho(unidade), fonte.trimestral("vendas_ecommerce_total")), width="stretch")
            elif unidade == "fisica":
                st.plotly_chart(g5.cliente_ra_vs_vendas_fisica(ra.desempenho(unidade), fonte.trimestral("vendas_lojas_fisicas")), width="stretch")
            elif unidade == "luizacred":
                st.plotly_chart(g5.cliente_luizacred(ra.desempenho(unidade), fonte.trimestral("luizacred_faturamento"), fonte.trimestral("luizacred_lucro")), width="stretch")
            else:
                _info("Sem cruzamento específico para esta unidade.")

        _bloco_fontes(evs)
        _secao_insights(
            fatos=["Google Trends: série mensal; RA: 2024–1S2026."],
            associacoes=["A defasagem de maior correlação entre busca e vendas indica se o interesse antecede ou acompanha as vendas."],
            hipoteses=["Se a nota do RA se mantém enquanto as vendas crescem, a operação pode estar escalando sem degradar o atendimento."]
        )

# ======================================================================
# PÁGINA 7 — PROJEÇÕES
# ======================================================================
class PaginaV5Projecoes:
    def render(self, repositorio):
        st.title("7 - Projeções Preditivas")
        st.caption("Modelos estatísticos para antecipar tendências de vendas e interesse de marca.")
        st.info("⚠ **Nota metodológica:** As projeções usam modelos baseados no histórico. A faixa sombreada representa o intervalo de confiança.")
        ctx, ano_ini, ano_fim, mostrar = _controles("v5_proj", repositorio)
        fonte = ctx.fonte
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("1. Projeção de Vendas Totais")
            serie_vendas = fonte.trimestral("vendas_totais").dropna()
            if len(serie_vendas) > 8:
                try:
                    modelo = SARIMAX(serie_vendas, order=(1, 1, 1), seasonal_order=(1, 1, 0, 4), enforce_stationarity=False, enforce_invertibility=False)
                    resultado = modelo.fit(disp=False)
                    previsao = resultado.get_forecast(steps=4)
                    prev_media, prev_ci = previsao.predicted_mean, previsao.conf_int()
                    idx_futuro = pd.period_range(start=serie_vendas.index[-1] + 1, periods=4, freq="Q")
                    
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=[period_para_data(p) for p in serie_vendas.index], y=serie_vendas.values, mode='lines+markers', name='Histórico', line=dict(color=CORES["secundaria"])))
                    fig.add_trace(go.Scatter(x=[period_para_data(p) for p in idx_futuro], y=prev_media.values, mode='lines+markers', name='Projeção', line=dict(color=CORES["acento"], dash='dash')))
                    
                    datas_prev = [period_para_data(p) for p in idx_futuro]
                    fig.add_trace(go.Scatter(x=datas_prev + datas_prev[::-1], y=list(prev_ci.iloc[:, 1]) + list(prev_ci.iloc[:, 0])[::-1], fill='toself', fillcolor='rgba(241, 143, 1, 0.2)', line=dict(color='rgba(255,255,255,0)'), hoverinfo="skip", showlegend=False))
                    
                    fig.update_layout(title="Projeção de Vendas (R$ milhões)", template="plotly_white", height=400, legend=dict(orientation="h", yanchor="bottom", y=1.02))
                    st.plotly_chart(fig, width="stretch")
                    st.success(f"**Mensagem Executiva:** As vendas devem ficar em torno de **R$ {prev_media.iloc[0]:,.1f} milhões** no {period_para_rotulo(idx_futuro[0])}.")
                except Exception as e:
                    st.error(f"Erro no SARIMAX: {e}")
            else:
                st.warning("Dados históricos insuficientes para o SARIMAX.")

        with col2:
            st.subheader("2. Projeção do Interesse de Busca")
            trends_m = fonte.trends_mensal()
            if trends_m.empty:
                try:
                    caminho_backup = os.path.join("BD", "ultimaLeituraGA.csv")
                    if os.path.exists(caminho_backup):
                        df_bkp = pd.read_csv(caminho_backup)
                        df_bkp['Data'] = pd.to_datetime(df_bkp['Data'])
                        trends_m = df_bkp.set_index('Data')['Quantidade'].sort_index()
                        st.info("ℹ️ Utilizando dados de backup.")
                except Exception as e:
                    st.warning(f"Erro no backup: {e}")
            
            if len(trends_m) > 12:
                try:
                    df_prophet = trends_m.reset_index()
                    df_prophet.columns = ['ds', 'y']
                    df_prophet['ds'] = pd.to_datetime(df_prophet['ds']).dt.tz_localize(None)
                    df_prophet['y'] = pd.to_numeric(df_prophet['y'], errors='coerce')
                    df_prophet = df_prophet.dropna(subset=['ds', 'y']).drop_duplicates(subset=['ds'], keep='last').sort_values('ds')

                    m = Prophet(yearly_seasonality=True, weekly_seasonality=False, daily_seasonality=False)
                    m.fit(df_prophet)
                    futuro = m.make_future_dataframe(periods=6, freq='ME')
                    forecast = m.predict(futuro)
                    
                    limite_historico = df_prophet['ds'].max() - pd.DateOffset(months=36)
                    historico_plot = df_prophet[df_prophet['ds'] >= limite_historico]
                    futuro_plot = forecast[forecast['ds'] > df_prophet['ds'].max()]
                    
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=historico_plot['ds'], y=historico_plot['y'], mode='lines', name='Histórico', line=dict(color=CORES["trends"], width=2)))
                    proj_plot = pd.concat([pd.DataFrame({'ds': [df_prophet['ds'].iloc[-1]], 'y': [df_prophet['y'].iloc[-1]]}), futuro_plot[['ds', 'yhat']].rename(columns={'yhat': 'y'})])
                    fig.add_trace(go.Scatter(x=proj_plot['ds'], y=proj_plot['y'], mode='lines+markers', name='Projeção', line=dict(color=CORES["negativo"], width=3, dash='dash')))
                    fig.add_trace(go.Scatter(x=futuro_plot['ds'].tolist() + futuro_plot['ds'].tolist()[::-1], y=futuro_plot['yhat_upper'].tolist() + futuro_plot['yhat_lower'].tolist()[::-1], fill='toself', fillcolor='rgba(192, 57, 43, 0.15)', line=dict(color='rgba(255,255,255,0)'), hoverinfo="skip", showlegend=False))
                    
                    fig.update_layout(title="Projeção de Interesse de Busca (0-100)", template="plotly_white", height=400, legend=dict(orientation="h", yanchor="bottom", y=1.02), hovermode="x unified")
                    fig.update_xaxes(range=[df_prophet['ds'].max() - pd.DateOffset(months=24), futuro_plot['ds'].max() + pd.DateOffset(months=1)])
                    st.plotly_chart(fig, width="stretch")
                    
                    st.error(f"**Mensagem Executiva:** A tendência de queda (ou estabilização em {futuro_plot['yhat'].iloc[-1]:.0f}) no interesse de busca deve continuar, a menos que haja uma ação de marketing significativa.")
                except Exception as e:
                    st.error(f"Erro no Prophet: {e}")
            else:
                st.warning(f"Dados insuficientes para o Prophet ({len(trends_m)} pontos).")

        _como_interpretar("As projeções não são 'bolas de cristal'. Elas usam o comportamento passado (sazonalidade e tendência) para desenhar um cenário provável. A área sombreada mostra a margem de erro esperada.")

# ======================================================================
# Páginas acadêmicas (ao final do menu)
# ======================================================================

OBJETIVO_PROJETO = (
    "Analisar a evolução financeira, operacional e reputacional do Magazine Luiza "
    "entre 2018 e 2026, através de informações disponíveis no próprio site da "
    "empresa como também em outros sites. Criação de insights e dashboards que "
    "permitam acompanhar não somente as variáveis financeiras e operacionais como "
    "também investimentos realizados, valores de ações na bolsa, indicadores "
    "sociais, reputacionais e ações de marketing."
    "\nAlguns gráficos ou dados podem conter períodos menores ou maiores devido"
    "à limitação das pesquisas durante a extração dos dados"
)

FONTES = ["DRE", "Cotações", "Reclame Aqui", "Google Trends"]


class PaginaInicio:
    """Apresentação dos Dados: objetivo do projeto e visão geral das fontes de dados."""

    def render(self, repositorio):
        st.title("Início — Objetivo e Fontes")
        st.markdown(f"> {OBJETIVO_PROJETO}")

        st.markdown("### Fontes de dados do projeto")
        colunas = st.columns(4)
        descricoes = {
            "DRE": ("📊", "Planilha de resultados trimestrais (RESULTADO_2T26_POR.xlsx)"),
            "Cotações": ("📈", "Histórico diário da ação na bolsa"),
            "Reclame Aqui": ("🗣️", "Reputação e reclamações — 4 unidades de negócio"),
            "Google Trends": ("🔎", "Interesse de busca pela marca (série mensal + ano a ano)"),
        }
        for coluna, fonte in zip(colunas, FONTES):
            icone, descricao = descricoes[fonte]
            with coluna:
                st.markdown(f"**{icone} {fonte}**")
                st.caption(descricao)
                if fonte in repositorio.erros:
                    st.error("Não carregada")
                else:
                    st.success("Carregada")

        st.info(
            "Use o menu à esquerda para navegar entre os atos executivos ou "
            "conferir como os dados foram carregados e higienizados."
        )

        st.markdown("### Nomenclaturas importantes que devem ser conhecidas:")
        st.info(
            "O Magalu opera com dois modelos de venda: 1P (First Party) e 3P (Third Party). "
            " \n1P (First Party): Significa 'Primeira Parte'. É o modelo de venda direta. "
            " \nO Magalu compra o estoque do fabricante (ou produz, no caso das marcas próprias como a Época), "
            " vende para o cliente final e é o responsável por toda a operação (faturamento, emissão de nota, "
            " logística e atendimento). Neste projeto isso aparece como 'E-commerce Tradicional (1P)'."
        )
        st.info(
            "\n3P (Third Party): Significa 'Terceira Parte'. É o modelo de Marketplace. "
            " \nO Magalu atua apenas como 'shopping virtual'. Ele coloca a plataforma, o tráfego "
            " e o sistema de pagamentos à disposição de lojistas parceiros (os sellers)."
            " \nA venda, a nota fiscal e a entrega são de responsabilidade do lojista."
            " \nO Magalu ganha uma comissão (take rate). Neste projeto isso aparece como 'Marketplace (3P)'."
            ""
        )
        st.info(
            " \nO termo EBITDA significa 'Earnings Before Interest, Taxes, Depreciation and Amortization' ou "
            " o 'Lucro Antes de Juros, Impostos, Depreciação e Amortização'."
            " \nUm indicador que mede a performance operacional de uma empresa sem considerar efeitos financeiros," 
            " tributários e contábeis. Ele mostra quanto o negócio gera de resultado apenas com suas atividades principais."
            ""
        )


class PaginaCargaHigienizacao:
    """Tela acadêmica: status de carga e o que a limpeza ajustou."""

    def render(self, repositorio):
        st.title("Carga e higienização dos dados")

        if repositorio.erros:
            st.warning(
                "Uma ou mais fontes não puderam ser carregadas — veja os detalhes "
                "na fonte correspondente abaixo."
            )

        self._secao_dre(repositorio)
        self._secao_cotacao(repositorio)
        self._secao_reclame_aqui(repositorio)
        self._secao_google_trends(repositorio)

    def _secao_dre(self, repositorio):
        st.markdown("## Planilha de resultados (DRE)")
        if "DRE" in repositorio.erros:
            st.error(f"Falha ao carregar: {repositorio.erros['DRE']}")
            return
        loader = repositorio.loader_dre
        guias = loader.listar_guias()
        st.write(f"**{len(guias)} guias carregadas.**")
        with st.expander("Ver guias e o que a higienização ajustou em cada uma"):
            for relatorio in repositorio.relatorios_limpeza_dre:
                mudou = (relatorio["cabecalhos_renomeados"]
                         or relatorio["colunas_removidas"]
                         or relatorio.get("tracos_convertidos")
                         or relatorio["valores_zerados"])
                marcador = "🧹" if mudou else "✓"
                st.markdown(f"**{marcador} {relatorio['guia']}**")
                if relatorio["cabecalhos_renomeados"]:
                    st.caption(f"{len(relatorio['cabecalhos_renomeados'])} cabeçalho(s) corrigido(s)")
                if relatorio["colunas_removidas"]:
                    st.caption(f"{len(relatorio['colunas_removidas'])} coluna(s) vazia(s) removida(s)")
                if relatorio["valores_zerados"]:
                    st.caption(f"{len(relatorio['valores_zerados'])} indicador(es) com valores zerados")

    def _secao_cotacao(self, repositorio):
        st.markdown("## Cotação da ação")
        if "Cotações" in repositorio.erros:
            st.error(f"Falha ao carregar: {repositorio.erros['Cotações']}")
            return
        df = repositorio.cotacao.df
        st.write(f"**{len(df)} pregões carregados**, de {df.index.min().date()} "
                 f"a {df.index.max().date()}.")
        with st.expander("Ver amostra dos dados"):
            st.dataframe(df.tail(5))

    def _secao_reclame_aqui(self, repositorio):
        st.markdown("## Reclame Aqui")
        if "Reclame Aqui" in repositorio.erros:
            st.error(f"Falha ao carregar: {repositorio.erros['Reclame Aqui']}")
            return
        ra = repositorio.reclame_aqui
        empresas = ra.listar_empresas()
        st.write(f"**{len(empresas)} empresas encontradas:** {', '.join(empresas)}")
        with st.expander("Ver categorias disponíveis por empresa"):
            for empresa in empresas:
                st.caption(f"{empresa}: {', '.join(ra.listar_categorias(empresa))}")

    def _secao_google_trends(self, repositorio):
        st.markdown("## Google Trends")
        trends = getattr(repositorio, "trends", None)
        if trends is None:
            st.warning("Google Trends (série mensal) não carregado.")
        else:
            if trends.usando_backup:
                st.warning("⚠ Consulta ao vivo indisponível agora — exibindo a "
                           "última leitura salva em backup.")
            else:
                st.success("Série mensal obtida ao vivo (Google Trends).")
            st.write(f"**{len(trends.serie_temporal)} meses** carregados.")
            st.caption("A região agregada do loader live foi DESCONSIDERADA — "
                       "ela era uma 'foto' de um momento específico e ficava "
                       "inconsistente com o consolidado ano a ano.")

        st.markdown("### Interesse por região — ano a ano")
        ga_anual = getattr(repositorio, "ga_anual", None)
        if ga_anual is None or ga_anual.df.empty:
            st.info("Sem dados consolidados por região/ano.")
            return

        anos = ga_anual.anos_disponiveis()
        regioes = ga_anual.regioes_disponiveis()
        st.write(
            f"**{len(ga_anual.df)} linhas** consolidadas, cobrindo "
            f"**{len(anos)} ano(s)** ({anos[0]}–{anos[-1]}) e "
            f"**{len(regioes)} região(ões)**."
        )
        st.caption(
            "Anos passados são lidos do backup consolidado "
            "(`GA_porRegiao_ano_a_ano.csv`); apenas o ano corrente "
            f"({anos[-1]}) é reconsultado ao vivo."
        )
        with st.expander("Ver amostra do consolidado"):
            st.dataframe(ga_anual.df.head(20))
        with st.expander("Ver região agregada (derivada do consolidado)"):
            serie = repositorio.trends_regiao_agregada()
            if not serie.empty:
                st.dataframe(serie.sort_values(ascending=False))
            else:
                st.info("Sem dados.")

