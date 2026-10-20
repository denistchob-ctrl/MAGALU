"""
paginas_executivas_v3.py
=========================
Modelo v3 do dashboard executivo — "Eventos Estratégicos × Indicadores".

Ideia central: em vez de só mostrar que o lucro caiu ou o EBITDA subiu, cruzar
os indicadores do projeto com EVENTOS REAIS documentados (com fonte) e
verificar, de forma transparente, se a direção dos dados é coerente com a
narrativa — mostrando também onde NÃO é.

Páginas:
  1. Linha do Tempo Estratégica     (timeline + modelo conceitual + fontes)
  2. Eventos × Indicadores          (escolha um evento; veja antes × depois)
  3. Transformação Digital          (Casos 1 e 2: pandemia, KaBuM!, investimentos)
  4. Juros, Lucro e Virada          (Casos 3 e 5: Selic, 4T23, reversão em 2026)
  5. Marketplace e Margem           (Caso 4)
  6. Marca e Reputação              (Casos 6 e 7: Google Trends e Reclame Aqui)

Convive com v1/v2 sem alterá-los. Depende de: eventos_estrategicos,
magalu_macro, analises_eventos, graficos_executivos_v3 (+ módulos existentes).
"""

import re
from datetime import date

import numpy as np
import pandas as pd
import streamlit as st

from config_indicadores import CORES, ANO_INICIAL, ANO_FINAL, MIN_OBSERVACOES_CORRELACAO
from eventos_estrategicos import (
    EVENTOS, EVENTOS_POR_ID, EVENTOS_ACAO, Evento, black_fridays, eventos_no_intervalo,
    rotulo_serie, unidade_serie, tabela_eventos, NOTAS_SERIE,
)
from magalu_macro import SelicLoader
from analises_eventos import (
    FonteSeries, avaliar_evento, avaliar_todos, tabela_para_exibicao, frase_leitura,
    placar, janelas_avaliacao, correlacao_por_defasagem, r_critico, variacao_aa,
    formatar_valor, period_para_rotulo, period_para_data,
    COERENTE, CONTRARIA, INCONCLUSIVO, SEM_DADOS, ICONE_VEREDITO, TEXTO_VEREDITO,
    normalizar_fracao,
)
from analises import correlacao_pearson
import graficos_executivos_v3 as g3
import graficos_executivos_v2 as g2

STATUS_TXT = {"verificado": "✅ fonte verificada",
              "conhecimento_publico": "🟡 data de conhecimento público — conferir fonte oficial",
              "a_confirmar": "🔴 a confirmar"}

# ----------------------------------------------------------------------
# Escape de "$": o Streamlit interpreta $...$ como fórmula LaTeX em qualquer
# texto Markdown, o que corrompe valores como "R$ 6,6 bi ... R$ 6,7 bi".
# Todo texto exibido passa por estes wrappers, que escapam o "$" (R$ -> R\$).
# É seguro com textos que já estavam escapados (não duplica a barra).
# ----------------------------------------------------------------------
def _esc(texto):
    if not isinstance(texto, str):
        return texto
    return texto.replace("\\$", "$").replace("$", "\\$")


def _markdown(texto, *args, **kwargs):
    return st.markdown(_esc(texto), *args, **kwargs)


def _caption(texto, *args, **kwargs):
    return st.caption(_esc(texto), *args, **kwargs)


def _info(texto, *args, **kwargs):
    return st.info(_esc(texto), *args, **kwargs)


def _warning(texto, *args, **kwargs):
    return st.warning(_esc(texto), *args, **kwargs)


def _success(texto, *args, **kwargs):
    return st.success(_esc(texto), *args, **kwargs)


CHAVES_COM_SINAL = {"lucro_liquido", "lucro_liquido_ajustado", "resultado_financeiro",
                    "fluxo_caixa_operacional", "fluxo_caixa_financiamento", "fluxo_caixa_investimento",
                    "luizacred_lucro"}


# ======================================================================
# Contexto (cache) e helpers comuns
# ======================================================================
class ContextoV3:
    def __init__(self, selic, fonte):
        self.selic = selic
        self.fonte = fonte


@st.cache_resource(show_spinner="Preparando a camada de eventos: Selic, cotação ajustada...")
def obter_contexto_v3(_repositorio):
    selic = SelicLoader()
    return ContextoV3(selic, FonteSeries(_repositorio, selic))


def _controles(prefixo, repositorio):
    """Controles de sidebar comuns. Devolve (ctx, ano_ini, ano_fim, mostrar_rotulos)."""
    ctx = obter_contexto_v3(repositorio)
    ano_ini, ano_fim = st.sidebar.slider(
        "Período exibido", ANO_INICIAL, ANO_FINAL, (ANO_INICIAL, ANO_FINAL), key=f"{prefixo}_anos")
    mostrar = st.sidebar.checkbox("Mostrar rótulos dos eventos", value=True, key=f"{prefixo}_rot")
    return ctx, ano_ini, ano_fim, mostrar


def _evs(ids, ano_ini, ano_fim):
    return eventos_no_intervalo([EVENTOS_POR_ID[i] for i in ids if i in EVENTOS_POR_ID], ano_ini, ano_fim)


def _spec(fonte, chave, eixo=1, tipo=None, cor=None, nome=None, **kw):
    """Especificação padrão de série para g3.serie_com_eventos."""
    un = unidade_serie(chave)
    tipo = tipo or ("barra" if un == "moeda" else "linha")
    fmt = {"moeda": "num", "pct": "pct", "preco": "preco", "indice": "indice", "num": "num"}.get(un, "num")
    d = dict(nome=nome or rotulo_serie(chave), serie=fonte.trimestral(chave), tipo=tipo, eixo=eixo, fmt=fmt)
    if cor:
        d["cor"] = cor
    if tipo == "barra" and chave in CHAVES_COM_SINAL:
        d["cor_sinal"] = True
    d.update(kw)
    return d


def _avisar_faltantes(fonte, chaves):
    faltam = [rotulo_serie(c) for c in chaves if not fonte.disponivel(c)]
    if faltam:
        _warning("⚠ Séries indisponíveis nos dados carregados (os gráficos que dependem delas "
                   "aparecem parciais): " + ", ".join(faltam) + ".")
    return faltam


def _secao_insights(fatos, associacoes, hipoteses):
    _markdown("### Insights")
    if fatos:
        _markdown("**Fatos observados nos dados:**")
        for f in fatos:
            _markdown(f"- {f}")
    if associacoes:
        _markdown("**Associações (coerência com o evento real — não é causalidade):**")
        for a in associacoes:
            _markdown(f"- {a}")
    if hipoteses:
        _markdown("**Hipóteses (requerem investigação adicional):**")
        for h in hipoteses:
            _markdown(f"- {h}")


def _como_interpretar(texto):
    with st.expander("Como interpretar"):
        _markdown(texto)


def _bloco_fontes(eventos, titulo="📰 Contexto do mundo real (com fontes)"):
    with st.expander(titulo):
        if not eventos:
            _caption("Nenhum evento do catálogo no período selecionado.")
        for ev in sorted(eventos, key=lambda e: e.data_inicio):
            origem = "externo" if ev.origem == "externo" else "interno"
            _markdown(f"**{ev.nome}** — {ev.data_exibicao} · _{ev.categoria}, evento {origem}_")
            _markdown(ev.descricao)
            if ev.fontes:
                _markdown("Fontes: " + " · ".join(f"[{t}]({u})" for t, u in ev.fontes))
            _caption(STATUS_TXT[ev.status])
            _markdown("---")


def _tabela_avaliacao(fonte, ev, n, titulo=None):
    """Mostra a tabela antes × depois de um evento e devolve o DataFrame bruto."""
    df = avaliar_evento(fonte, ev, n)
    if titulo:
        _markdown(f"**{titulo}**")
    if df.empty:
        _caption("Este evento é apresentado como contexto (sem hipótese direcional testável).")
        return df
    st.dataframe(tabela_para_exibicao(df), hide_index=True, width="stretch")
    return df


def _frases_numeros(df):
    """Frases só com os números (antes → depois), sem veredito — para 'Fatos'."""
    out = []
    for _, r in df.iterrows():
        if r["Veredito"] == SEM_DADOS:
            continue
        out.append(f"{r['Indicador']}: {formatar_valor(r['chave'], r['antes'])} ({r['Janela antes']}) → "
                   f"{formatar_valor(r['chave'], r['depois'])} ({r['Janela depois']}), {r['Variação']}.")
    return out


def _frases_associacao(df):
    return [frase_leitura(r) for r in df.to_dict("records") if r["Veredito"] != SEM_DADOS]


def _deslocar_futuro(s, k):
    """Valor em t = s(t+k), com calendário trimestral contínuo."""
    if s is None or s.empty or k == 0:
        return s
    full = s.reindex(pd.period_range(s.index.min(), s.index.max(), freq="Q"))
    return full.shift(-k).dropna()


def _cobertura(fonte, chave):
    s = fonte.trimestral(chave)
    if s.empty:
        return f"{rotulo_serie(chave)}: indisponível."
    return (f"{rotulo_serie(chave)}: {period_para_rotulo(s.index.min())} a "
            f"{period_para_rotulo(s.index.max())} ({len(s)} trimestres).")


# ======================================================================
# PÁGINA 1 — LINHA DO TEMPO ESTRATÉGICA
# ======================================================================
class PaginaV3Timeline:
    def render(self, repositorio):
        st.title("Linha do Tempo Estratégica do Magalu")
        _caption("Quais eventos estratégicos e de mercado ajudam a explicar os movimentos "
                   "observados nos indicadores?")

        ano_ini, ano_fim = st.sidebar.slider(
            "Período exibido", ANO_INICIAL, ANO_FINAL, (ANO_INICIAL, ANO_FINAL), key="v3_tl_anos")
        origens = st.sidebar.multiselect(
            "Origem dos eventos", ["externo", "interno"], default=["externo", "interno"], key="v3_tl_orig")

        eventos = [e for e in eventos_no_intervalo(EVENTOS, ano_ini, ano_fim) if e.origem in origens]

        _info("**Regra de leitura:** eventos dão **contexto**, não provam causa. "
                "Laranja = evento externo (mercado/economia); azul = evento interno (decisão da empresa). "
                "Cada evento tem fonte e um status de verificação.")

        st.plotly_chart(g3.timeline_estrategica(eventos, ano_ini, ano_fim), width="stretch")

        st.subheader("Do evento à percepção do mercado")
        _caption("Estrutura de análise usada em todas as páginas.")
        st.graphviz_chart(g3.modelo_conceitual_dot())

        st.subheader("Eventos catalogados")
        df = tabela_eventos()
        df = df[df["Evento"].isin([e.nome for e in eventos])]
        st.dataframe(df, hide_index=True, width="stretch")

        n_conf = sum(1 for e in eventos if e.status != "verificado")
        if n_conf:
            _warning(f"🟡 {n_conf} evento(s) têm data de conhecimento público, mas ainda sem link de "
                       f"fonte oficial neste catálogo. Confira antes de apresentar.")

        _bloco_fontes(eventos)

        ctx = obter_contexto_v3(repositorio)
        with st.expander("🛠 Qualidade dos dados desta camada"):
            avisos = list(dict.fromkeys(ctx.fonte.avisos_dados))
            for a in ctx.fonte.relatorio_ajuste:
                _markdown(f"- Cotação: {a}")
            _markdown(f"- Selic: fonte **{ctx.selic.fonte}**.")
            for a in avisos:
                _markdown(f"- {a}")
            if not avisos:
                _caption("Nenhum aviso de duplicidade/indicador ausente.")

        with st.expander("🔎 Auditoria factual — correções em relação ao roteiro inicial (leia antes da reunião)",
                         expanded=True):
            _markdown(
                "- **Retorno ao lucro:** o roteiro original marcava *2024*. As fontes mostram que o "
                "ponto de virada foi o **4T23** (1º lucro ajustado em dois anos; divulgado em 18/03/2024). "
                "O ano de 2023 como um todo ainda foi de prejuízo ajustado (R$ 550,1 mi).\n"
                "- **A história não termina na recuperação:** em 2025 a Selic chegou a 15% e, no **2T26**, "
                "o resultado voltou ao prejuízo (R$ 72,5 mi contábil; R$ 50,4 mi ajustado), com e-commerce "
                "e marketplace em queda e lojas físicas crescendo. A narrativa \"marketplace como motor de "
                "recuperação\" precisa ser apresentada com esse contraponto.\n"
                "- **Cotação MGLU3:** a ação passou por desdobramentos (1:8 em 08/2019, 1:4 em 10/2020) e por "
                "um grupamento 10:1 (27/05/2024). Séries sem ajuste geram saltos falsos e distorcem o Base 100 "
                "— a apresentação atual detecta e corrige automaticamente (veja a página 4).\n"
                "- **Frase não verificada:** o roteiro cita que \"cada ponto percentual de queda da Selic teria "
                "impacto relevante\" na economia financeira. Não foi localizada uma fonte oficial, não a utilize "
                "sem confirmar no release de resultados.")

        _secao_insights(
            fatos=[f"O catálogo reúne {len(EVENTOS)} eventos "
                   f"({sum(e.origem == 'externo' for e in EVENTOS)} externos e "
                   f"{sum(e.origem == 'interno' for e in EVENTOS)} internos), cada um com data e fonte."],
            associacoes=["Eventos externos (pandemia, Selic) e internos (aquisições, capital) ocorrem "
                         "sobrepostos no tempo — a página 'Eventos × Indicadores' testa cada hipótese isoladamente."],
            hipoteses=["A combinação de expansão por aquisições (2020–21) e juros altos (2022–23) pode "
                       "explicar a pressão sobre o lucro; requer decomposição do resultado financeiro."],
        )
        _como_interpretar(
            "A linha do tempo organiza o **contexto**. Para cada evento, as demais páginas mostram os "
            "indicadores antes e depois e classificam a hipótese como coerente, contrária ou inconclusiva. "
            "Coincidência temporal não é causalidade: vários eventos acontecem ao mesmo tempo.")


# ======================================================================
# PÁGINA 2 — EVENTOS × INDICADORES
# ======================================================================
class PaginaV3EventosIndicadores:
    def render(self, repositorio):
        st.title("Eventos × Indicadores")
        _caption("Escolha um evento: o painel destaca os indicadores ligados a ele e confere, com os "
                   "seus dados, se a hipótese direcional se sustenta.")

        ctx, ano_ini, ano_fim, mostrar = _controles("v3_ei", repositorio)
        n = st.sidebar.slider("Janela de comparação (trimestres)", 2, 8, 4, key="v3_ei_n",
                              help="Média dos N trimestres antes × depois do evento. "
                                   "Use múltiplos de 4 para neutralizar a sazonalidade (Black Friday no 4T).")
        fonte = ctx.fonte

        ordenados = sorted(EVENTOS, key=lambda e: e.data_inicio)
        rotulos = {f"{e.data_inicio.year} · {e.nome}": e for e in ordenados}
        escolha = st.selectbox("Evento", list(rotulos.keys()), index=list(rotulos.values()).index(EVENTOS_POR_ID["kabum"]),
                               key="v3_ei_evento")
        ev = rotulos[escolha]

        # --- cabeçalho do evento
        c1, c2, c3 = st.columns(3)
        c1.metric("Data", ev.data_exibicao)
        c2.metric("Categoria", ev.categoria)
        c3.metric("Origem", ev.origem.capitalize())
        _markdown(ev.descricao)
        if ev.o_que_olhar:
            _markdown(f"**O que olhar nos dados:** {ev.o_que_olhar}")
        _caption(STATUS_TXT[ev.status])
        if ev.fontes:
            _markdown("Fontes: " + " · ".join(f"[{t}]({u})" for t, u in ev.fontes))

        # --- avaliação
        st.subheader("O que aconteceu nos dados?")
        df = _tabela_avaliacao(fonte, ev, n)
        if not df.empty:
            for fr in _frases_associacao(df):
                _markdown(f"- {fr}")
            _caption(f"Limiares: variação ≥ {5}% (valores) ou ≥ 0,5 p.p. (percentuais) para sair de "
                       f"'inconclusiva'. Janela: até {n} trimestres antes/depois.")

        # --- gráficos dos indicadores destacados (small multiples)
        st.subheader("Indicadores destacados")
        _caption("Faixa cinza = período 'antes'; faixa verde = período 'depois'. "
                   "Linha/faixa colorida = evento.")
        disponiveis = [c for c in ev.destaques if fonte.disponivel(c)]
        faltam = [rotulo_serie(c) for c in ev.destaques if not fonte.disponivel(c)]
        if faltam:
            _warning("Séries indisponíveis: " + ", ".join(faltam))

        colunas = st.columns(2)
        for i, chave in enumerate(disponiveis):
            exp = next((e for e in ev.expectativas if e.chave == chave), None)
            j = janelas_avaliacao(ev, exp.modo if exp else "medio", n)
            faixas = [
                dict(x0=j.antes[0].start_time, x1=j.antes[1].end_time, rotulo="antes", cor="#7F8C8D"),
                dict(x0=j.depois[0].start_time, x1=j.depois[1].end_time, rotulo="depois", cor=CORES["positivo"]),
            ]
            un = unidade_serie(chave)
            titulo_y = {"moeda": "R$ milhões", "pct": "%", "preco": "R$ por ação", "indice": "índice"}.get(un, "")
            spec = _spec(fonte, chave, **({"degrau": True} if chave == "selic" else {}))
            fig = g3.serie_com_eventos(
                [spec], [ev], rotulo_serie(chave), y1_titulo=titulo_y, fmt_y1=spec["fmt"],
                faixas=faixas, ano_ini=ano_ini, ano_fim=ano_fim, mostrar_rotulos=mostrar, altura=340)
            with colunas[i % 2]:
                st.plotly_chart(fig, width="stretch", key=f"v3_ei_{ev.id}_{chave}")
                if chave in NOTAS_SERIE:
                    _caption(NOTAS_SERIE[chave])

        _bloco_fontes([ev], titulo="📰 Detalhe e fontes do evento")

        # --- placar global
        _markdown("---")
        st.subheader("Placar de coerência — todos os eventos")
        df_todos = avaliar_todos(fonte, EVENTOS, n)
        p = placar(df_todos)
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("✅ Coerentes", p[COERENTE])
        k2.metric("❌ Contrárias", p[CONTRARIA])
        k3.metric("➖ Inconclusivas", p[INCONCLUSIVO])
        k4.metric("⚠ Sem dados", p[SEM_DADOS])
        decididas = p[COERENTE] + p[CONTRARIA]
        if decididas:
            _markdown(f"Entre as hipóteses com direção definida, **{p[COERENTE] / decididas:.0%}** "
                        f"({p[COERENTE]} de {decididas}) foram coerentes com os fatos documentados.")
        if not df_todos.empty:
            st.plotly_chart(g3.placar_coerencia(df_todos), width="stretch", key="v3_ei_placar")
            contr = df_todos[df_todos["Veredito"] == CONTRARIA]
            if not contr.empty:
                _markdown("**Onde os dados NÃO confirmam a narrativa** (mostrar estes pontos com "
                            "transparência fortalece a credibilidade da apresentação):")
                for r in contr.to_dict("records"):
                    _markdown(f"- _{r['Evento']}_ → {frase_leitura(r)}")
            with st.expander("Ver todas as hipóteses testadas"):
                mostrar_df = df_todos[["Evento", "Indicador", "Hipótese", "Janela antes", "Janela depois",
                                       "Variação", "Veredito", "Nota"]].copy()
                mostrar_df["Veredito"] = mostrar_df["Veredito"].map(
                    lambda v: f"{ICONE_VEREDITO[v]} {TEXTO_VEREDITO[v]}")
                st.dataframe(mostrar_df, hide_index=True, width="stretch")

        _como_interpretar(
            "O teste é **direcional e simples**: compara a média de N trimestres antes com a de N depois "
            "(ou o período do evento, quando é uma faixa de tempo). **Coerente** significa que a direção "
            "observada bate com a hipótese e a variação supera o limiar; **contrária** significa o oposto; "
            "**inconclusiva**, variação pequena. Limitações: não controla outros eventos simultâneos, "
            "efeito-base nem sazonalidade além da janela; com poucos trimestres o resultado é frágil. "
            "Hipóteses foram definidas **antes** de olhar os dados, a partir do roteiro de eventos.")


# ======================================================================
# PÁGINA 3 — TRANSFORMAÇÃO DIGITAL (Casos 1 e 2)
# ======================================================================
class PaginaV3Digital:
    def render(self, repositorio):
        st.title("Transformação Digital e Investimentos")
        _caption("O avanço dos canais digitais acompanhou a pandemia e a expansão do ecossistema? "
                   "E os investimentos de 2021 pesaram no curto prazo e geraram resultado depois?")

        ctx, ano_ini, ano_fim, mostrar = _controles("v3_dg", repositorio)
        fonte = ctx.fonte
        evs = _evs(["covid", "aquisicoes", "kabum", "followon"], ano_ini, ano_fim)
        _avisar_faltantes(fonte, ["vendas_ecommerce_1p", "vendas_marketplace_3p", "participacao_ecommerce",
                                  "invest_tecnologia", "invest_total", "ebitda"])

        # --- Caso 1
        st.header("Caso 1 · A transformação digital")
        st.subheader("Mix do e-commerce (1P × marketplace 3P) e participação nas vendas totais")
        fig = g3.serie_com_eventos(
            [_spec(fonte, "vendas_ecommerce_1p", cor=CORES["secundaria"]),
             _spec(fonte, "vendas_marketplace_3p", cor=CORES["acento"]),
             _spec(fonte, "participacao_ecommerce", eixo=2, cor=CORES["primaria"], largura=3)],
            evs, "E-commerce 1P + Marketplace 3P × participação do e-commerce",
            y1_titulo="R$ milhões", y2_titulo="Participação (%)", fmt_y2="pct",
            ano_ini=ano_ini, ano_fim=ano_fim, mostrar_rotulos=mostrar, empilhar=True)
        st.plotly_chart(fig, width="stretch", key="v3_dg_mix")

        st.subheader("Investimento em tecnologia × participação do e-commerce")
        fig = g3.serie_com_eventos(
            [_spec(fonte, "invest_tecnologia", cor=CORES["invest"]),
             _spec(fonte, "participacao_ecommerce", eixo=2, cor=CORES["primaria"], largura=3)],
            evs, "Investimento em tecnologia × participação do e-commerce",
            y1_titulo="R$ milhões", y2_titulo="Participação (%)", fmt_y2="pct",
            ano_ini=ano_ini, ano_fim=ano_fim, mostrar_rotulos=mostrar)
        st.plotly_chart(fig, width="stretch", key="v3_dg_tec")

        n = st.sidebar.slider("Janela de comparação (trimestres)", 2, 8, 4, key="v3_dg_n")
        df_covid = _tabela_avaliacao(fonte, EVENTOS_POR_ID["covid"], n, "Pandemia — antes × depois")
        df_kabum = _tabela_avaliacao(fonte, EVENTOS_POR_ID["kabum"], n, "Aquisição da KaBuM! — antes × depois")

        # --- Caso 2
        st.header("Caso 2 · A explosão de investimentos de 2021")
        _markdown("**Pergunta:** os investimentos pesaram no curto prazo e geraram resultado operacional depois?")
        k = st.slider("EBITDA 'futuro': deslocar quantos trimestres à frente?", 0, 8, 4, key="v3_dg_k")
        s_inv, s_ebitda = fonte.trimestral("invest_total"), fonte.trimestral("ebitda")
        fig = g3.serie_com_eventos(
            [_spec(fonte, "invest_total", cor=CORES["invest"], nome="Investimentos totais (t)"),
             dict(nome=f"EBITDA em t+{k}T (plotado em t)", serie=_deslocar_futuro(s_ebitda, k), tipo="linha",
                  eixo=1, fmt="num", cor=CORES["acento"], largura=3),
             _spec(fonte, "participacao_ecommerce", eixo=2, cor=CORES["primaria"], dash="dot")],
            evs, "Investimentos totais × EBITDA futuro × participação do e-commerce",
            y1_titulo="R$ milhões", y2_titulo="Participação (%)", fmt_y2="pct",
            ano_ini=ano_ini, ano_fim=ano_fim, mostrar_rotulos=mostrar)
        st.plotly_chart(fig, width="stretch", key="v3_dg_inv")

        st.subheader("Em que defasagem a associação é mais forte?")
        transf = st.radio("Base da correlação", ["Variação a/a (recomendado)", "Níveis"], horizontal=True,
                          key="v3_dg_transf")
        modo = "aa" if transf.startswith("Variação") else "nivel"
        corr = correlacao_por_defasagem(s_inv, s_ebitda, range(0, 9), modo)
        n_med = int(corr["n"].median()) if not corr.empty else 0
        st.plotly_chart(
            g3.barras_defasagem(corr, "Investimentos totais (t) × EBITDA (t+k)", r_critico(n_med)),
            width="stretch", key="v3_dg_lag")
        melhor = None
        if not corr.empty and corr["r"].notna().any():
            validos = corr[corr["n"] >= MIN_OBSERVACOES_CORRELACAO].dropna(subset=["r"])
            if not validos.empty:
                melhor = validos.loc[validos["r"].abs().idxmax()]
        if modo == "nivel":
            _caption("⚠ Em níveis, duas séries que apenas crescem ao longo do tempo parecem correlacionadas "
                       "(correlação espúria). Prefira a variação a/a.")

        _bloco_fontes(evs)

        fatos = [_cobertura(fonte, "participacao_ecommerce"), _cobertura(fonte, "invest_total")]
        fatos += _frases_numeros(df_covid) + _frases_numeros(df_kabum)
        assoc = _frases_associacao(df_covid) + _frases_associacao(df_kabum)
        if melhor is not None:
            assoc.append(f"Investimentos totais × EBITDA: maior |r| em k = {int(melhor['defasagem'])} trimestre(s), "
                         f"r = {melhor['r']:.2f} (n = {int(melhor['n'])}, base: {transf.lower()}). "
                         f"Associação temporal, não causalidade.")
        _secao_insights(
            fatos=fatos, associacoes=assoc,
            hipoteses=["O avanço digital pode ter sido impulsionado simultaneamente pela pandemia (demanda) e pelas "
                       "aquisições (oferta/categorias); separar os dois efeitos exige dados por empresa adquirida.",
                       "Investimentos pesados em 2021 podem ter reduzido a rentabilidade de curto prazo e preparado "
                       "o EBITDA dos anos seguintes — mas o ciclo de juros (2022–23) é um fator de confusão relevante."])
        _como_interpretar(
            "Esta página compara **o que a empresa fez** (aquisições, capital, investimento) com **o que os "
            "indicadores mostraram**. Barras empilhadas = canais; a linha azul mostra a participação do e-commerce. "
            "O deslocamento do EBITDA responde 'o investimento de hoje aparece no EBITDA de t+k?'. "
            "O gráfico de defasagens mostra r para cada k; a linha tracejada é uma referência aproximada de "
            "significância — com séries temporais, a autocorrelação a torna otimista.")


# ======================================================================
# PÁGINA 4 — JUROS, LUCRO E VIRADA (Casos 3 e 5)
# ======================================================================
class PaginaV3Juros:
    def render(self, repositorio):
        st.title("Juros, Lucro e a Virada")
        _caption("Apesar do crescimento de vendas, a rentabilidade ficou pressionada pelos juros? "
                   "A recuperação de 2023–24 se sustentou?")

        ctx, ano_ini, ano_fim, mostrar = _controles("v3_jr", repositorio)
        fonte = ctx.fonte
        tipo_lucro = st.sidebar.radio("Lucro exibido", ["Ajustado", "Contábil"], key="v3_jr_lucro")
        chave_lucro = "lucro_liquido_ajustado" if tipo_lucro == "Ajustado" else "lucro_liquido"
        n = st.sidebar.slider("Janela de comparação (trimestres)", 2, 8, 4, key="v3_jr_n")

        evs = _evs(["juros_altos", "selic_cortes_2023", "virada_4t23", "selic_15", "selic_cortes_2026",
                    "reversao_2t26"], ano_ini, ano_fim)
        _avisar_faltantes(fonte, [chave_lucro, "margem_ebitda", "margem_liquida", "resultado_financeiro",
                                  "fluxo_caixa_operacional", "mglu3", "selic"])
        _caption(f"Fonte da Selic: **{ctx.selic.fonte}**.")
        if ctx.selic.fonte.startswith("Tabela"):
            _warning("A Selic veio da tabela embutida (BCB indisponível e sem backup local). ")
                       # "Confira os valores com a série oficial antes de apresentar.")

        # --- Caso 3
        st.header("Caso 3 · A crise dos juros")
        st.subheader("Selic × lucro líquido")
        fig = g3.serie_com_eventos(
            [_spec(fonte, chave_lucro, nome=f"Lucro líquido ({tipo_lucro.lower()})"),
             _spec(fonte, "selic", eixo=2, cor=CORES["negativo"], degrau=True, fmt="pct2", largura=3)],
            evs, f"Selic (meta, fim do trimestre) × lucro líquido {tipo_lucro.lower()}",
            y1_titulo="R$ milhões", y2_titulo="Selic (% a.a.)", fmt_y2="pct2",
            ano_ini=ano_ini, ano_fim=ano_fim, mostrar_rotulos=mostrar)
        st.plotly_chart(fig, width="stretch", key="v3_jr_selic_lucro")

        st.subheader("Operação × resultado final: onde os juros 'absorvem' a margem")
        fig = g3.serie_com_eventos(
            [_spec(fonte, "margem_ebitda", cor=CORES["positivo"], largura=3),
             _spec(fonte, "margem_liquida", cor=CORES["primaria"], largura=3),
             _spec(fonte, "resfin_sobre_receita", cor=CORES["negativo"], dash="dot"),
             _spec(fonte, "selic", eixo=2, cor=CORES["neutro"], degrau=True, fmt="pct2", dash="dash", largura=1.8)],
            evs, "Margem EBITDA × margem líquida × resultado financeiro / receita",
            y1_titulo="% da receita líquida", fmt_y1="pct", y2_titulo="Selic (% a.a.)", fmt_y2="pct2",
            ano_ini=ano_ini, ano_fim=ano_fim, mostrar_rotulos=mostrar)
        st.plotly_chart(fig, width="stretch", key="v3_jr_margens")
        _caption("Se a margem EBITDA (operação) melhora enquanto a margem líquida não acompanha, a diferença "
                   "está abaixo do EBITDA — em grande parte, no resultado financeiro.")

        st.subheader("Selic e peso financeiro: existe associação?")
        transf = st.radio("Base da correlação", ["Níveis", "Variação a/a"], horizontal=True, key="v3_jr_transf")
        modo = "nivel" if transf == "Níveis" else "aa"
        corr = correlacao_por_defasagem(fonte.trimestral("selic"), fonte.trimestral("resfin_sobre_receita"),
                                        range(-2, 5), modo)
        n_med = int(corr["n"].median()) if not corr.empty else 0
        st.plotly_chart(g3.barras_defasagem(corr, "Selic (t) × resultado financeiro / receita (t+k)",
                                            r_critico(n_med)), width="stretch", key="v3_jr_lag")

        st.subheader("Fluxo de caixa operacional × cotação MGLU3")
        fig = g3.serie_com_eventos(
            [_spec(fonte, "fluxo_caixa_operacional", cor=CORES["secundaria"]),
             _spec(fonte, "mglu3", eixo=2, cor=CORES["mercado"], fmt="preco", largura=3,
                   nome="MGLU3 (fech. ajustado, fim do trimestre)")],
            evs, "Fluxo de caixa operacional × MGLU3 (ajustada por desdobramentos/grupamento)",
            y1_titulo="R$ milhões", y2_titulo="R$ por ação (ajustado)", fmt_y2="preco",
            ano_ini=ano_ini, ano_fim=ano_fim, mostrar_rotulos=mostrar)
        st.plotly_chart(fig, width="stretch", key="v3_jr_fco_mglu")
        with st.expander("🛠 Ajuste da cotação por desdobramentos e grupamento (transparência)"):
            for linha in fonte.relatorio_ajuste:
                _markdown(f"- {linha}")
            _caption("Eventos técnicos considerados: " + "; ".join(
                f"{e['descricao']} em {e['data']:%d/%m/%Y}" for e in EVENTOS_ACAO) +
                ". O mesmo cuidado vale para o Base 100, se a série vier sem ajuste, o MGLU3 apareceria distorcido.")

        # --- Caso 5
        st.header("Caso 5 · Retorno ao lucro (e o que veio depois)")
        self._painel_virada(fonte, n)

        df_juros = _tabela_avaliacao(fonte, EVENTOS_POR_ID["juros_altos"], n, "Juros elevados (2022–23) — durante × antes")
        df_virada = _tabela_avaliacao(fonte, EVENTOS_POR_ID["virada_4t23"], n, "Virada do 4T23 — antes × depois")
        df_rev = _tabela_avaliacao(fonte, EVENTOS_POR_ID["reversao_2t26"], n, "2T26 — contra o 2T25")

        _bloco_fontes(evs)

        _secao_insights(
            fatos=[_cobertura(fonte, chave_lucro), _cobertura(fonte, "resultado_financeiro")]
                  + _frases_numeros(df_juros)[:3] + _frases_numeros(df_virada)[:3],
            associacoes=_frases_associacao(df_juros) + _frases_associacao(df_virada) + _frases_associacao(df_rev),
            hipoteses=["Parte relevante da pressão sobre o lucro em 2022–23 pode vir das despesas financeiras "
                       "(juros sobre dívida e antecipação de recebíveis), e não da operação; requer abrir o "
                       "resultado financeiro por componente (guia '9. Resultado Financeiro').",
                       "O recuo de e-commerce/marketplace em 2026 é apresentado pela empresa como escolha por "
                       "rentabilidade; é preciso verificar se a margem EBITDA se sustenta sem o volume digital."])
        _como_interpretar(
            "Compare **linhas de operação** (margem EBITDA) com **resultado final** (margem líquida). "
            "O 'resultado financeiro / receita' mede quanto dos juros pesa sobre cada real vendido. "
            "O painel do Caso 5 confere, nos SEUS dados, se o primeiro trimestre de lucro ajustado após a "
            "sequência de prejuízos coincide com o 4T23 documentado pela empresa.")

    # ------------------------------------------------------------------
    def _painel_virada(self, fonte, n):
        lucro_aj = fonte.trimestral("lucro_liquido_ajustado")
        if not lucro_aj.empty:
            primeiro = lucro_aj[(lucro_aj.index >= pd.Period("2022Q1")) & (lucro_aj > 0)]
            ultimo_antes = lucro_aj[(lucro_aj.index < pd.Period("2022Q1")) & (lucro_aj > 0)]
            c1, c2 = st.columns(2)
            with c1:
                if not ultimo_antes.empty:
                    q = period_para_rotulo(ultimo_antes.index[-1])
                    ok = "✅" if q == "3T21" else "⚠"
                    st.metric("Último lucro ajustado antes da sequência de prejuízos", q)
                    _caption(f"{ok} Documentado: 3T21.")
            with c2:
                if not primeiro.empty:
                    q = period_para_rotulo(primeiro.index[0])
                    ok = "✅" if q == "4T23" else "⚠"
                    st.metric("Primeiro lucro ajustado após a sequência", q)
                    _caption(f"{ok} Documentado: 4T23 (divulgado em 18/03/2024).")
                else:
                    _info("Nenhum trimestre com lucro ajustado positivo a partir de 2022 nos dados carregados.")
            _caption("Se algum quadro mostrar ⚠, a planilha pode ter sido reapresentada ou os dados diferem da "
                       "divulgação original, base desse projeto.")
        else:
            _info("Lucro líquido ajustado indisponível nos dados carregados.")

        # tabela anual
        chaves = [("lucro_liquido", "Lucro líquido"), ("lucro_liquido_ajustado", "Lucro líquido ajustado"),
                  ("ebitda", "EBITDA"), ("fluxo_caixa_operacional", "Fluxo de caixa operacional"),
                  ("resultado_financeiro", "Resultado financeiro líquido")]
        anual = {rot: fonte.anual(ch) for ch, rot in chaves}
        rec = fonte.anual("receita_liquida")
        eb = fonte.anual("ebitda")
        anos = sorted(set().union(*[set(s.index) for s in anual.values() if not s.empty]))
        anos = [a for a in anos if a >= 2021]
        if anos:
            linhas = []
            for (ch, rot) in chaves:
                s = anual[rot]
                linhas.append({"Indicador": rot, **{str(a): formatar_valor(ch, s.get(a)) if a in s.index else "—" for a in anos}})
            if not rec.empty and not eb.empty:
                linhas.append({"Indicador": "Margem EBITDA (EBITDA / receita líquida)",
                               **{str(a): (formatar_valor("margem_ebitda", eb[a] / rec[a])
                                           if a in eb.index and a in rec.index and rec[a] else "—") for a in anos}})
            _markdown("**Anos completos (soma dos 4 trimestres):**")
            st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch")
        ult = fonte.trimestral("lucro_liquido")
        if not ult.empty:
            q = ult.index[-1]
            _caption(f"Último trimestre disponível na planilha: {period_para_rotulo(q)} "
                       f"(lucro líquido contábil: {formatar_valor('lucro_liquido', ult.iloc[-1])}). "
                       f"Anos incompletos não entram na tabela anual.")


# ======================================================================
# PÁGINA 5 — MARKETPLACE E MARGEM (Caso 4)
# ======================================================================
class PaginaV3Marketplace:
    def render(self, repositorio):
        st.title("Marketplace e Margem")
        _caption("O marketplace passou a contribuir mais para a rentabilidade do que apenas para o crescimento?")

        ctx, ano_ini, ano_fim, mostrar = _controles("v3_mk", repositorio)
        fonte = ctx.fonte
        n = st.sidebar.slider("Janela de comparação (trimestres)", 2, 8, 4, key="v3_mk_n")
        evs = _evs(["marketplace", "virada_4t23", "reversao_2t26", "covid"], ano_ini, ano_fim)
        _avisar_faltantes(fonte, ["vendas_marketplace_3p", "vendas_totais", "margem_ebitda", "margem_bruta"])

        st.subheader("Marketplace 3P e sua participação nas vendas totais")
        fig = g3.serie_com_eventos(
            [_spec(fonte, "vendas_marketplace_3p", cor=CORES["acento"]),
             _spec(fonte, "share_3p", eixo=2, cor=CORES["primaria"], largura=3)],
            evs, "Marketplace 3P (R$) × participação nas vendas totais",
            y1_titulo="R$ milhões", y2_titulo="% das vendas totais", fmt_y2="pct",
            ano_ini=ano_ini, ano_fim=ano_fim, mostrar_rotulos=mostrar)
        st.plotly_chart(fig, width="stretch", key="v3_mk_3p")

        st.subheader("Participação do marketplace × margens")
        fig = g3.serie_com_eventos(
            [_spec(fonte, "share_3p", cor=CORES["acento"], largura=3),
             _spec(fonte, "margem_bruta", cor=CORES["secundaria"]),
             _spec(fonte, "margem_ebitda", cor=CORES["positivo"], largura=3)],
            evs, "Participação do marketplace × margem bruta × margem EBITDA",
            y1_titulo="%", fmt_y1="pct", ano_ini=ano_ini, ano_fim=ano_fim, mostrar_rotulos=mostrar)
        st.plotly_chart(fig, width="stretch", key="v3_mk_margens")

        st.subheader("Crescimento ou rentabilidade? Variação a/a do marketplace × variação a/a da margem EBITDA")
        cresc = variacao_aa(fonte.trimestral("vendas_marketplace_3p"))
        m = fonte.trimestral("margem_ebitda")
        dm = (m - m.shift(4)).dropna() if not m.empty else pd.Series(dtype=float)
        # shift(4) só vale com calendário contínuo
        if not m.empty:
            full = m.reindex(pd.period_range(m.index.min(), m.index.max(), freq="Q"))
            dm = (full - full.shift(4)).dropna()
        fig = g3.serie_com_eventos(
            [dict(nome="Crescimento a/a do marketplace 3P", serie=cresc.dropna(), tipo="barra", eixo=1,
                  fmt="pct", cor_sinal=True),
             dict(nome="Variação a/a da margem EBITDA (p.p.)", serie=dm, tipo="linha", eixo=2, fmt="pct2",
                  cor=CORES["primaria"], largura=3)],
            evs, "Crescimento do marketplace × ganho de margem EBITDA (a/a)",
            y1_titulo="Crescimento a/a", fmt_y1="pct", y2_titulo="Δ margem EBITDA (p.p.)", fmt_y2="pct2",
            ano_ini=ano_ini, ano_fim=ano_fim, mostrar_rotulos=mostrar)
        st.plotly_chart(fig, width="stretch", key="v3_mk_cresc_margem")

        st.subheader("Relação estatística")
        x, y = fonte.trimestral("share_3p"), fonte.trimestral("margem_ebitda")
        r, nobs, _ = correlacao_pearson(x, y)
        if nobs and nobs < MIN_OBSERVACOES_CORRELACAO:
            _warning(f"Apenas {nobs} observações em comum — resultado instável.")
        if not np.isnan(r):
            st.metric("Correlação (níveis): participação 3P × margem EBITDA", f"r = {r:.2f}", delta=f"n = {nobs}")
            st.plotly_chart(g2.relacoes_dispersao(x, y, "Participação 3P", "Margem EBITDA", r=r, n=nobs),
                            width="stretch", key="v3_mk_disp")
            _caption("⚠ Em níveis, duas séries com tendência parecem correlacionadas. Veja a defasagem em "
                       "variação a/a abaixo.")
        transf = st.radio("Base da correlação por defasagem", ["Variação a/a (recomendado)", "Níveis"],
                          horizontal=True, key="v3_mk_transf")
        corr = correlacao_por_defasagem(x, y, range(-2, 5), "aa" if transf.startswith("Variação") else "nivel")
        n_med = int(corr["n"].median()) if not corr.empty else 0
        st.plotly_chart(g3.barras_defasagem(corr, "Participação 3P (t) × margem EBITDA (t+k)", r_critico(n_med)),
                        width="stretch", key="v3_mk_lag")

        df_mk = _tabela_avaliacao(fonte, EVENTOS_POR_ID["marketplace"], n, "Marketplace 2023–24 — durante × antes")
        df_rev = _tabela_avaliacao(fonte, EVENTOS_POR_ID["reversao_2t26"], n, "2T26 — contra o 2T25")
        _bloco_fontes(evs)

        _secao_insights(
            fatos=[_cobertura(fonte, "vendas_marketplace_3p")] + _frases_numeros(df_mk)[:4],
            associacoes=_frases_associacao(df_mk) + _frases_associacao(df_rev),
            hipoteses=["O ganho de margem pode vir de mix (mais marketplace, que não carrega estoque), de "
                       "monetização (ads, fintech, fulfillment) ou de disciplina de despesas; os dados "
                       "disponíveis não separam esses efeitos.",
                       "Em 2026 o marketplace recua (-12,6% a/a no 2T26 segundo a divulgação) enquanto a margem se "
                       "mantém: pode indicar que o motor de margem migrou para lojas físicas e crédito."])
        _como_interpretar(
            "A pergunta é de **composição**: o marketplace ajuda mais a vender ou a lucrar? Compare as barras "
            "(crescimento) com a linha (ganho de margem). O 2T26 funciona como teste de estresse da narrativa: "
            "se o marketplace cai e a margem não cai, o vínculo causal é mais fraco do que o roteiro sugere.")


# ======================================================================
# PÁGINA 6 — MARCA E REPUTAÇÃO (Casos 6 e 7)
# ======================================================================
def _parse_periodo_ra(rotulo):
    """Rótulo do Reclame Aqui -> (ano, semestre|None). 'Geral'/'Total' -> None."""
    t = str(rotulo).strip()
    if t.lower() in ("geral", "total", ""):
        return None
    m = re.match(r"^(\d{4})$", t)
    if m:
        return int(m.group(1)), None
    m = re.match(r"^(\d)S(\d{4})$", t)
    if m:
        return int(m.group(2)), int(m.group(1))
    m = re.match(r"^(\d)S(\d{2})$", t)
    if m:
        return 2000 + int(m.group(2)), int(m.group(1))
    m = re.match(r"^(\d{4})\D+(\d)", t)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None


def _soma_periodo(serie_q, ano, sem):
    qs = [1, 2, 3, 4] if sem is None else ([1, 2] if sem == 1 else [3, 4])
    idx = [pd.Period(f"{ano}Q{q}", freq="Q") for q in qs]
    v = serie_q.reindex(idx)
    return float(v.sum()) if v.notna().all() else None


UNIDADE_VENDAS = {"online": "vendas_ecommerce_total", "fisica": "vendas_lojas_fisicas",
                  "luizacred": "luizacred_faturamento"}
NOME_UNIDADE = {"online": "Loja Online", "fisica": "Loja Física", "luizacred": "Luizacred",
                "consorcio": "Consórcio"}


class PaginaV3Marca:
    def render(self, repositorio):
        st.title("Marca e Reputação")
        _caption("O interesse pela marca antecede ou acompanha as vendas? E o crescimento da operação "
                   "ocorreu preservando a experiência do cliente?")

        ctx, ano_ini, ano_fim, mostrar = _controles("v3_mr", repositorio)
        fonte = ctx.fonte
        evs = _evs(["covid", "kabum", "followon", "virada_4t23", "reversao_2t26"], ano_ini, ano_fim)

        # ---------------- Caso 6
        st.header("Caso 6 · Marca e interesse do consumidor")
        _caption("Google Trends mede **atenção/interesse de busca** — não reputação nem satisfação.")
        trends_m = fonte.trends_mensal()
        vendas = fonte.trimestral("vendas_totais")
        if trends_m.empty:
            _warning("Google Trends indisponível nos dados carregados.")
        else:
            bf = st.checkbox("Marcar Black Friday", value=True, key="v3_mr_bf")
            fig = g3.serie_com_eventos(
                [dict(nome="Interesse de busca (Google Trends, mensal)", serie=trends_m, tipo="linha", eixo=1,
                      fmt="indice", cor=CORES["trends"], largura=2),
                 _spec(fonte, "vendas_totais", eixo=2, cor=CORES["secundaria"], opacidade=0.35)],
                evs, "Google Trends × vendas totais, com eventos de mercado e Black Friday",
                y1_titulo="Interesse (0–100)", y2_titulo="Vendas totais (R$ milhões)", fmt_y2="num",
                ano_ini=ano_ini, ano_fim=ano_fim, mostrar_rotulos=mostrar,
                eventos_leves=black_fridays(ano_ini, ano_fim) if bf else None)
            st.plotly_chart(fig, width="stretch", key="v3_mr_trends")
            _caption("Linhas pontilhadas cinza = Black Friday (4ª quinta de novembro + 1 dia).")

            transf = st.radio("Base da correlação", ["Variação a/a (recomendado)", "Níveis"], horizontal=True,
                              key="v3_mr_transf")
            modo = "aa" if transf.startswith("Variação") else "nivel"
            corr = correlacao_por_defasagem(fonte.trimestral("trends"), vendas, range(-4, 5), modo)
            n_med = int(corr["n"].median()) if not corr.empty else 0
            st.plotly_chart(
                g3.barras_defasagem(corr, "Interesse de busca (t) × vendas totais (t+k)", r_critico(n_med),
                                    "Defasagem (trimestres): Trends(t) × Vendas(t+k)   ·   k>0 = busca antecede vendas"),
                width="stretch", key="v3_mr_lag")
            melhor = None
            validos = corr[corr["n"] >= MIN_OBSERVACOES_CORRELACAO].dropna(subset=["r"]) if not corr.empty else corr
            if validos is not None and not validos.empty:
                melhor = validos.loc[validos["r"].abs().idxmax()]
            if melhor is not None:
                k = int(melhor["defasagem"])
                leitura = ("a busca ACOMPANHA as vendas (mesmo trimestre)" if k == 0 else
                           f"a busca ANTECEDE as vendas em {k} trimestre(s)" if k > 0 else
                           f"as vendas ANTECEDEM a busca em {abs(k)} trimestre(s)")
                _markdown(f"**Leitura:** maior |r| em k = {k} (r = {melhor['r']:.2f}, n = {int(melhor['n'])}): "
                            f"{leitura}. Associação temporal — o interesse também reage a campanhas e "
                            f"à própria sazonalidade de Black Friday/Natal.")

        # ---------------- Caso 7
        st.header("Caso 7 · Reputação do consumidor (Reclame Aqui)")
        _warning(
            "**Limite dos dados:** o Reclame Aqui do projeto cobre apenas **2024, 2025 e o 1º semestre de 2026** "
            "(≤ 3 pontos por unidade). Isso **não permite testar** os eventos de 2020–2023 e impede correlações. "
            "A página mostra um cruzamento **descritivo**: o crescimento da operação veio acompanhado de queda "
            "ou manutenção da nota?")
        ra = getattr(repositorio, "reclame_aqui", None)
        if ra is None:
            _info("Reclame Aqui indisponível nos dados carregados.")
        else:
            abas = st.tabs([NOME_UNIDADE[u] for u in ("online", "fisica", "luizacred")])
            for aba, unidade in zip(abas, ("online", "fisica", "luizacred")):
                with aba:
                    self._aba_ra(ra, fonte, unidade, evs, ano_ini, ano_fim, mostrar)

        _bloco_fontes(evs)
        _secao_insights(
            fatos=["Google Trends: série mensal; Reclame Aqui: apenas 2024, 2025 e 1S2026 (n ≤ 3 por unidade)."],
            associacoes=["A defasagem de maior correlação entre busca e vendas (acima) indica se o interesse "
                         "antecede ou acompanha as vendas — sempre como associação temporal."],
            hipoteses=["Se a nota do Reclame Aqui se mantém enquanto as vendas crescem, a operação pode estar "
                       "escalando sem degradar o atendimento; com 2–3 pontos isso é só um indício.",
                       "Para testar os eventos de 2020–2023 (pandemia, KaBuM!), seria preciso histórico mensal "
                       "do Reclame Aqui desde 2019."])
        _como_interpretar(
            "A pergunta não é 'o Reclame Aqui faz a empresa vender?', e sim **'o crescimento preservou a "
            "experiência do cliente?'**. O Trends mede atenção; o Reclame Aqui mede experiência de quem "
            "registrou reclamação (viés de seleção). Não se misturam unidades de negócio.")

    # ------------------------------------------------------------------
    def _aba_ra(self, ra, fonte, unidade, evs, ano_ini, ano_fim, mostrar):
        try:
            df = ra.desempenho(unidade)
        except KeyError:
            _info(f"Unidade '{unidade}' não encontrada no Reclame Aqui.")
            return
        if df is None or df.empty or "Nota Média" not in df.columns:
            _info("Sem coluna 'Nota Média' para esta unidade.")
            return

        linhas = []
        for rotulo, row in df.iterrows():
            per = _parse_periodo_ra(rotulo)
            if per is None:
                continue
            linhas.append((per, rotulo, row))
        linhas.sort(key=lambda t: (t[0][0], t[0][1] or 0))
        if not linhas:
            _info("Nenhum período reconhecido (apenas 'Geral').")
            return

        chave_vendas = UNIDADE_VENDAS.get(unidade)
        vendas_q = fonte.trimestral(chave_vendas) if chave_vendas else pd.Series(dtype=float)

        tabela, datas, notas = [], [], []
        nota_ant = None
        for (ano, sem), rotulo, row in linhas:
            nota = row.get("Nota Média")
            volt = row.get("Voltariam a fazer negócio") if "Voltariam a fazer negócio" in df.columns else None
            if volt is not None and not pd.isna(volt):
                volt = float(volt)
                volt = volt / 100.0 if volt > 1.5 else volt
            cresc = None
            if not vendas_q.empty:
                atual, antes = _soma_periodo(vendas_q, ano, sem), _soma_periodo(vendas_q, ano - 1, sem)
                if atual is not None and antes:
                    cresc = atual / antes - 1
            d_nota = None if (nota_ant is None or pd.isna(nota)) else float(nota) - nota_ant
            if cresc is None or d_nota is None:
                leitura = "—"
            elif cresc > 0 and d_nota >= -0.2:
                leitura = "Crescimento com experiência estável/melhor"
            elif cresc > 0:
                leitura = "⚠ Crescimento com piora da nota"
            elif d_nota >= 0:
                leitura = "Nota preservada sem crescimento"
            else:
                leitura = "⚠ Queda de vendas e de nota"
            tabela.append({
                "Período RA": str(rotulo), "Nota média": None if pd.isna(nota) else float(nota),
                "Δ nota vs período anterior": d_nota,
                "Voltariam a fazer negócio": None if volt is None or pd.isna(volt) else f"{volt:.0%}",
                f"Vendas ({rotulo_serie(chave_vendas)}) a/a" if chave_vendas else "Vendas a/a":
                    (f"{cresc:+.1%}" if cresc is not None else "—"),
                "Leitura": leitura,
            })
            if not pd.isna(nota):
                nota_ant = float(nota)
                mes = 1 if (sem in (None, 1)) else 7
                dur = 12 if sem is None else 6
                datas.append(pd.Timestamp(year=ano, month=mes, day=1) + pd.Timedelta(days=int(dur * 30.4 / 2)))
                notas.append(float(nota))

        st.dataframe(pd.DataFrame(tabela), hide_index=True, width="stretch")
        if len(notas) < 3:
            _caption(f"n = {len(notas)} ponto(s): suficiente apenas para descrever, não para inferir.")
        if notas and chave_vendas:
            fig = g3.serie_com_eventos(
                [dict(nome="Nota média (Reclame Aqui)", serie=pd.Series(notas, index=pd.DatetimeIndex(datas)),
                      tipo="linha", eixo=1, fmt="nota", cor=CORES["ra"], largura=3),
                 _spec(fonte, chave_vendas, eixo=2, cor=CORES["secundaria"], opacidade=0.35)],
                evs, f"Reclame Aqui ({NOME_UNIDADE[unidade]}) × {rotulo_serie(chave_vendas)}",
                y1_titulo="Nota (0–10)", y2_titulo="R$ milhões", fmt_y2="num", range_y1=[0, 10],
                ano_ini=ano_ini, ano_fim=ano_fim, mostrar_rotulos=mostrar, altura=420)
            st.plotly_chart(fig, width="stretch", key=f"v3_mr_ra_{unidade}")
