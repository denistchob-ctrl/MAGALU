"""
paginas_executivas_v4.py
==========================
Versão final (v4) do dashboard executivo. Consolida e mescla:
  1. Linha do Tempo Estratégica
  2. Eventos × Indicadores
  3. Juros, Lucro e Virada
  4. Investimentos, Digital e Mercado (v3 Digital + v2 Investimentos)
  5. Omnichannel e Marketplace (v2 Omnichannel + v3 Marketplace)
  6. Cliente, Marca e Reputação (v2)
  + Páginas acadêmicas (Início, Carga e Higienização)
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go  # <-- Necessário para os gráficos de projeção

import os

from config_indicadores import CORES, MIN_OBSERVACOES_CORRELACAO
from formatos import formata_moeda, formata_pct
from validacoes import mensagem_sem_dados
from analises import correlacao_pearson, base_100
import graficos_executivos_v2 as g2
import graficos_executivos_v3 as g3
from eventos_estrategicos import EVENTOS_POR_ID
from analises_eventos import (
    FonteSeries, COERENTE, CONTRARIA, INCONCLUSIVO, SEM_DADOS, ICONE_VEREDITO, TEXTO_VEREDITO,
    period_para_data, period_para_rotulo  # <-- ADICIONADO AQUI
)

import warnings
from statsmodels.tsa.statespace.sarimax import SARIMAX
from prophet import Prophet

warnings.filterwarnings("ignore")

# --- Importações da v3 ---
from paginas_executivas_v3 import (
    PaginaV3Timeline, 
    PaginaV3EventosIndicadores,
    PaginaV3Juros,
    _controles,
    _evs,
    _tabela_avaliacao,
    _frases_numeros,
    _frases_associacao,
    _secao_insights,
    _como_interpretar,
    _bloco_fontes,
    _avisar_faltantes,
    _spec,
    _cobertura,
    _deslocar_futuro,
)

# --- Importações da v2 ---
from paginas_executivas_v2 import (
    PaginaV2Cliente,
)

# --- Importações da v1 (acadêmico) ---
from paginas_executivas import PaginaInicio, PaginaCargaHigienizacao


# ======================================================================
# Página 0 — Abertura
# ======================================================================

class PaginaAbertura:
    def render(self, repositorio):
        # Tenta carregar o logo local
        try:
            st.image("logo.png", width=400)
        except:
            pass
        
        st.title("Dashboard Executivo — Magazine Luiza")
        
        st.markdown(
            """
            Esta apresentação foi desenvolvida para responder a uma pergunta central da diretoria:
            **Como o desempenho financeiro, a transformação dos canais, os investimentos, 
            a percepção do consumidor e o comportamento do mercado evoluíram juntos no Magalu?**
            """
        )

        # Estilo CSS para os cartões azuis
        st.markdown("""
        <style>
        .card-item {
            background-color: #0086FF;
            color: white !important;
            border-radius: 12px;
            padding: 15px;
            margin-bottom: 15px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            transition: transform 0.2s;
            height: 100%; /* Garante que todos os cartões na mesma linha tenham a mesma altura */
            box-sizing: border-box;
        }
        .card-item:hover {
            transform: translateY(-3px);
            box-shadow: 0 6px 12px rgba(0,0,0,0.15);
        }
        .card-title {
            font-weight: bold;
            font-size: 1.05em;
            margin-bottom: 5px;
            color: white !important;
        }
        .card-desc {
            font-size: 0.85em;
            color: #f0f0f0 !important;
            margin: 0;
            line-height: 1.3;
        }
        .card-desc em {
            color: #ffeb3b !important; /* Amarelo para o contexto */
            font-style: normal;
            font-weight: bold;
        }
        .section-header {
            color: #333;
            font-size: 1.3em;
            font-weight: bold;
            margin-bottom: 15px;
            border-bottom: 2px solid #0086FF;
            padding-bottom: 5px;
        }
        </style>
        """, unsafe_allow_html=True)

        # Layout principal: 75% para Executivo, 25% para Acadêmico
        col_esq, col_dir = st.columns([3, 1])

        with col_esq:
            st.markdown('<div class="section-header">Análise Executiva (7 Blocos)</div>', unsafe_allow_html=True)
            
            # Definição dos cartões
            cards = [
                ("1. Linha do Tempo", "Contexto.", "Eventos externos e decisões internas que marcaram o período."),
                ("2. Eventos × Indicadores", "Diagnóstico.", "Ferramenta interativa para testar hipóteses sobre cada evento."),
                ("3. Juros e Lucro", "Rentabilidade.", "Impacto da Selic no resultado final vs. operação (EBITDA)."),
                ("4. Investimentos e Mercado", "Retorno.", "Aportes em tech/logística e a reação da bolsa (MGLU3)."),
                ("5. Omnichannel", "Crescimento.", "Mix de canais (1P vs 3P) e busca por margens maiores."),
                ("6. Marca e Reputação", "Percepção.", "Interesse de busca (Trends) e saúde reputacional (RA)."),
                ("7. Projeções Preditivas", "Futuro.", "Modelos SARIMAX e Prophet para vendas e buscas.")
            ]

            # Divide os cartões em duas colunas internas
            sub_col1, sub_col2 = st.columns(2)
            
            for i, (title, context, desc) in enumerate(cards):
                # Alterna entre a coluna 1 e 2
                col_alvo = sub_col1 if i % 2 == 0 else sub_col2
                
                with col_alvo:
                    html = f"""
                    <div class="card-item">
                        <div class="card-title">{title}</div>
                        <div class="card-desc"><em>{context}</em> {desc}</div>
                    </div>
                    """
                    st.markdown(html, unsafe_allow_html=True)

        with col_dir:
            st.markdown('<div class="section-header" style="border-color: #7F8C8D;">Apoio Acadêmico</div>', unsafe_allow_html=True)
            
            # Cartões Acadêmicos
            cards_academicos = [
                ("Objetivo do Projeto", "Fontes e Escopo", "Detalhes sobre a origem e coleta de dados."),
                ("Carga e Higienização", "Transparência", "Como os dados foram limpos e preparados.")
            ]
            
            for title, subtitle, desc in cards_academicos:
                html = f"""
                <div class="card-item" style="background-color: #5D6D7E;">
                    <div class="card-title">{title}</div>
                    <div class="card-desc"><em>{subtitle}.</em> {desc}</div>
                </div>
                """
                st.markdown(html, unsafe_allow_html=True)

# ======================================================================
# PÁGINA 4 — INVESTIMENTOS, DIGITAL E MERCADO
# ======================================================================
class PaginaV4InvestimentosDigitalMercado:
    def render(self, repositorio):
        st.title("Investimentos, Digital e Mercado")
        st.caption("Como os investimentos em tecnologia e logística impulsionaram o digital e "
                   "como o mercado reagiu a essa transformação?")

        ctx, ano_ini, ano_fim, mostrar = _controles("v4_inv", repositorio)
        fonte = ctx.fonte
        evs = _evs(["covid", "aquisicoes", "kabum", "followon", "aporte_2024", "virada_4t23"], ano_ini, ano_fim)
        
        _avisar_faltantes(fonte, ["vendas_ecommerce_1p", "vendas_marketplace_3p", "participacao_ecommerce",
                                  "invest_tecnologia", "invest_total", "invest_logistica", "ebitda", "mglu3"])

        # --- 1. O avanço do digital e o investimento em tecnologia
        st.header("1. A transformação digital e os investimentos")
        st.subheader("Investimento em tecnologia × participação do e-commerce")
        fig = g3.serie_com_eventos(
            [_spec(fonte, "invest_tecnologia", cor=CORES["invest"]),
             _spec(fonte, "participacao_ecommerce", eixo=2, cor=CORES["primaria"], largura=3)],
            evs, "Investimento em tecnologia × participação do e-commerce",
            y1_titulo="R$ milhões", y2_titulo="Participação (%)", fmt_y2="pct",
            ano_ini=ano_ini, ano_fim=ano_fim, mostrar_rotulos=mostrar)
        st.plotly_chart(fig, width="stretch", key="v4_inv_tec")

        st.subheader("Mix do e-commerce (1P × marketplace 3P) e participação nas vendas totais")
        fig = g3.serie_com_eventos(
            [_spec(fonte, "vendas_ecommerce_1p", cor=CORES["secundaria"]),
             _spec(fonte, "vendas_marketplace_3p", cor=CORES["acento"]),
             _spec(fonte, "participacao_ecommerce", eixo=2, cor=CORES["primaria"], largura=3)],
            evs, "E-commerce 1P + Marketplace 3P × participação do e-commerce",
            y1_titulo="R$ milhões", y2_titulo="Participação (%)", fmt_y2="pct",
            ano_ini=ano_ini, ano_fim=ano_fim, mostrar_rotulos=mostrar, empilhar=True)
        st.plotly_chart(fig, width="stretch", key="v4_inv_mix")

        # --- 2. Investimentos vs EBITDA e Base 100
        st.header("2. O retorno dos investimentos e a percepção do mercado")
        
        st.subheader("Investimentos por categoria × EBITDA")
        df_inv = pd.DataFrame({
            "Tecnologia": fonte.trimestral("invest_tecnologia"),
            "Logística": fonte.trimestral("invest_logistica"),
            "Lojas Físicas": fonte.trimestral("invest_lojas"),
        })
        serie_ebitda = fonte.trimestral("ebitda")
        if not df_inv.dropna(how="all").empty:
            fig = g3.serie_com_eventos(
                [dict(nome=c, serie=df_inv[c].dropna(), tipo="barra", eixo=1, fmt="num", cor=CORES["invest"] if c=="Tecnologia" else (CORES["secundaria"] if c=="Logística" else CORES["acento"]))
                 for c in df_inv.columns] + 
                [_spec(fonte, "ebitda", eixo=2, cor=CORES["acento"], largura=3)],
                evs, "Investimentos por categoria × EBITDA",
                y1_titulo="R$ milhões", y2_titulo="EBITDA (R$)", fmt_y2="num",
                ano_ini=ano_ini, ano_fim=ano_fim, mostrar_rotulos=mostrar, empilhar=True
            )
            st.plotly_chart(fig, width="stretch", key="v4_inv_ebitda")
            
        st.subheader("Base 100 — desempenho operacional × percepção de mercado")
        st.caption("Usa 2018 como período inicial quando disponível. Permite comparar trajetórias de escalas diferentes.")
        series_base = {
            "Receita": fonte.anual("receita_liquida"),
            "EBITDA": fonte.anual("ebitda"),
            "Lucro": fonte.anual("lucro_liquido"),
            "Vendas Totais": fonte.anual("vendas_totais"),
        }
        if not fonte.trimestral("mglu3").empty:
            series_base["MGLU3"] = fonte.anual("mglu3")

        df_base = pd.DataFrame({
            k: base_100(v) for k, v in series_base.items()
            if v is not None and not v.empty
        })
        if not df_base.empty:
            # Gráfico via g2
            st.plotly_chart(g2.invest_mercado_base100(df_base), width="stretch", key="v4_inv_base100")

        st.subheader("Cotação MGLU3 × Volume negociado")
        # 1. Pegamos as séries e removemos nulos
        serie_mglu3 = fonte.trimestral("mglu3").dropna()
        serie_vol = repositorio.cotacao.get_serie("Volume_Financeiro") if repositorio.cotacao else pd.Series(dtype=float)
        serie_vol = serie_vol.dropna()
        
        if not serie_mglu3.empty and not serie_vol.empty:
            # 2. O segredo está aqui: converter o PeriodIndex para DatetimeIndex usando .to_timestamp()
            if isinstance(serie_mglu3.index, pd.PeriodIndex):
                serie_mglu3.index = serie_mglu3.index.to_timestamp()
            elif not isinstance(serie_mglu3.index, pd.DatetimeIndex):
                serie_mglu3.index = pd.to_datetime(serie_mglu3.index)
                
            # O volume já vem como DatetimeIndex do loader, mas garantimos por segurança
            if not isinstance(serie_vol.index, pd.DatetimeIndex):
                serie_vol.index = pd.to_datetime(serie_vol.index)
            
            # 3. Plotamos o gráfico
            st.plotly_chart(
                g2.invest_mercado_cotacao_volume(serie_mglu3, serie_vol),
                width="stretch", key="v4_inv_cotacao"
            )
        else:
            st.info("Dados de cotação ou volume indisponíveis para este período.")


        # Avaliações e insights
        n = st.sidebar.slider("Janela de comparação (trimestres)", 2, 8, 4, key="v4_inv_n")
        df_kabum = _tabela_avaliacao(fonte, EVENTOS_POR_ID["kabum"], n, "Aquisição da KaBuM! — antes × depois")
        df_aporte = _tabela_avaliacao(fonte, EVENTOS_POR_ID["aporte_2024"], n, "Aporte R$ 1,25 bi — antes × depois")

        _bloco_fontes(evs)
        _secao_insights(
            fatos=[_cobertura(fonte, "participacao_ecommerce"), _cobertura(fonte, "invest_total")] + _frases_numeros(df_kabum)[:3],
            associacoes=_frases_associacao(df_kabum) + _frases_associacao(df_aporte),
            hipoteses=["O descolamento entre fundamentos (Receita, EBITDA) e cotação pode refletir mudanças na percepção de risco do mercado — requer análise de múltiplos."])
        _como_interpretar(
            "Esta página une **o que a empresa fez** (investimentos) com **o que o mercado achou** (cotação e Base 100). "
            "A análise de tecnologia x e-commerce mostra se o investimento acompanhou a transformação digital. "
            "A Base 100 permite ver se o preço da ação está seguindo os fundamentos.")


# ======================================================================
# PÁGINA 5 — OMNICHANNEL E MARKETPLACE
# ======================================================================
class PaginaV4OmnichannelMarketplace:
    def render(self, repositorio):
        st.title("Omnichannel e Marketplace")
        st.caption("Como mudou o motor de crescimento do Magalu e qual foi o papel do marketplace "
                   "na rentabilidade?")

        ctx, ano_ini, ano_fim, mostrar = _controles("v4_omni", repositorio)
        fonte = ctx.fonte
        n = st.sidebar.slider("Janela de comparação (trimestres)", 2, 8, 4, key="v4_omni_n")
        evs = _evs(["marketplace", "virada_4t23", "reversao_2t26", "covid"], ano_ini, ano_fim)
        _avisar_faltantes(fonte, ["vendas_lojas_fisicas", "vendas_ecommerce_1p", "vendas_marketplace_3p", "vendas_totais", "share_3p", "margem_ebitda"])

        # --- 1. O Mix de Canais
        st.header("1. O mix de canais")
        st.subheader("Lojas Físicas × E-commerce 1P × Marketplace 3P")
        fig = g3.serie_com_eventos(
            [_spec(fonte, "vendas_lojas_fisicas", cor=CORES["secundaria"]),
             _spec(fonte, "vendas_ecommerce_1p", cor=CORES["invest"]),
             _spec(fonte, "vendas_marketplace_3p", cor=CORES["acento"]),
             _spec(fonte, "participacao_ecommerce", eixo=2, cor=CORES["primaria"], largura=3)],
            evs, "Mix de canais e participação do e-commerce",
            y1_titulo="R$ milhões", y2_titulo="Participação E-commerce (%)", fmt_y2="pct",
            ano_ini=ano_ini, ano_fim=ano_fim, mostrar_rotulos=mostrar, empilhar=True)
        st.plotly_chart(fig, width="stretch", key="v4_omni_mix")

        st.subheader("Receita por loja × Receita por m²")
        serie_vendas_lf = fonte.trimestral("vendas_lojas_fisicas")
        serie_n_lojas = fonte.trimestral("numero_lojas")
        serie_area = fonte.trimestral("area_vendas")

        rec_loja = (serie_vendas_lf / serie_n_lojas.replace(0, np.nan)).dropna() if not serie_vendas_lf.empty else pd.Series(dtype=float)
        rec_m2 = (serie_vendas_lf / serie_area.replace(0, np.nan)).dropna() if not serie_vendas_lf.empty else pd.Series(dtype=float)
        
        if not rec_loja.empty or not rec_m2.empty:
            st.plotly_chart(
                g2.omni_receita_por_loja_e_m2(rec_loja, rec_m2),
                width="stretch", key="v4_omni_loja_m2"
            )

        # --- 2. O Marketplace e a Margem
        st.header("2. Marketplace, margem e rentabilidade")
        st.subheader("Marketplace 3P e sua participação nas vendas totais")
        fig = g3.serie_com_eventos(
            [_spec(fonte, "vendas_marketplace_3p", cor=CORES["acento"]),
             _spec(fonte, "share_3p", eixo=2, cor=CORES["primaria"], largura=3)],
            evs, "Marketplace 3P (R$) × participação nas vendas totais",
            y1_titulo="R$ milhões", y2_titulo="% das vendas totais", fmt_y2="pct",
            ano_ini=ano_ini, ano_fim=ano_fim, mostrar_rotulos=mostrar)
        st.plotly_chart(fig, width="stretch", key="v4_omni_3p")

        st.subheader("Participação do marketplace × margens")
        fig = g3.serie_com_eventos(
            [_spec(fonte, "share_3p", cor=CORES["acento"], largura=3),
             _spec(fonte, "margem_bruta", cor=CORES["secundaria"]),
             _spec(fonte, "margem_ebitda", cor=CORES["positivo"], largura=3)],
            evs, "Participação do marketplace × margem bruta × margem EBITDA",
            y1_titulo="%", fmt_y1="pct", ano_ini=ano_ini, ano_fim=ano_fim, mostrar_rotulos=mostrar)
        st.plotly_chart(fig, width="stretch", key="v4_omni_margens")

        df_mk = _tabela_avaliacao(fonte, EVENTOS_POR_ID["marketplace"], n, "Marketplace 2023–24 — durante × antes")
        df_rev = _tabela_avaliacao(fonte, EVENTOS_POR_ID["reversao_2t26"], n, "2T26 — contra o 2T25")

        _bloco_fontes(evs)
        _secao_insights(
            fatos=[_cobertura(fonte, "vendas_marketplace_3p")] + _frases_numeros(df_mk)[:4],
            associacoes=_frases_associacao(df_mk) + _frases_associacao(df_rev),
            hipoteses=["O ganho de margem pode vir de mix (mais marketplace, que não carrega estoque), de "
                       "monetização (ads, fintech, fulfillment) ou de disciplina de despesas.",
                       "Em 2026 o marketplace recua (-12,6% a/a no 2T26 segundo a divulgação) enquanto a margem se "
                       "mantém: pode indicar que o motor de margem migrou para lojas físicas e crédito."])
        _como_interpretar(
            "Esta página cruza **canais** e **rentabilidade**. A área empilhada mostra para onde a empresa está "
            "vendendo. Os gráficos de margem mostram se o marketplace (que exige menos estoque) está ajudando a "
            "empresa a lucrar mais ou apenas a vender mais.")


# --- As páginas 1, 2, 3 e 6 são importadas ou reaproveitadas ---
# PaginaV3Timeline, PaginaV3EventosIndicadores, PaginaV3Juros e PaginaV2Cliente

# ======================================================================
# PÁGINA 7 — PROJEÇÕES
# ======================================================================
class PaginaV4Projecoes:
    def render(self, repositorio):
        st.title("Projeções Preditivas")
        st.caption("Modelos estatísticos para antecipar tendências de vendas e interesse de marca.")

        st.info(
            "⚠ **Nota metodológica:** As projeções abaixo usam modelos estatísticos baseados no histórico. "
            "A faixa sombreada representa o intervalo de confiança. Eventos externos não previstos "
            "podem alterar significativamente o resultado real."
        )

        ctx, ano_ini, ano_fim, mostrar = _controles("v4_proj", repositorio)
        fonte = ctx.fonte

        col1, col2 = st.columns(2)

        # --- 1. Projeção de Vendas (SARIMAX) ---
        with col1:
            st.subheader("1. Projeção de Vendas Totais")
            st.caption("Modelo SARIMAX — Sazonalidade Anual. Próximos 4 trimestres.")
            
            serie_vendas = fonte.trimestral("vendas_totais").dropna()
            
            if len(serie_vendas) > 8:
                try:
                    modelo = SARIMAX(serie_vendas, 
                                     order=(1, 1, 1), 
                                     seasonal_order=(1, 1, 0, 4),
                                     enforce_stationarity=False, 
                                     enforce_invertibility=False)
                    resultado = modelo.fit(disp=False)
                    
                    previsao = resultado.get_forecast(steps=4)
                    prev_media = previsao.predicted_mean
                    prev_ci = previsao.conf_int()
                    
                    idx_futuro = pd.period_range(start=serie_vendas.index[-1] + 1, periods=4, freq="Q")
                    datas_x = [period_para_data(p) for p in serie_vendas.index]
                    datas_prev = [period_para_data(p) for p in idx_futuro]
                    
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=datas_x, y=serie_vendas.values, mode='lines+markers', name='Histórico', line=dict(color=CORES["secundaria"])))
                    fig.add_trace(go.Scatter(x=datas_prev, y=prev_media.values, mode='lines+markers', name='Projeção', line=dict(color=CORES["acento"], dash='dash')))
                    
                    fig.add_trace(go.Scatter(
                        x=datas_prev + datas_prev[::-1],
                        y=list(prev_ci.iloc[:, 1]) + list(prev_ci.iloc[:, 0])[::-1],
                        fill='toself',
                        fillcolor='rgba(241, 143, 1, 0.2)',
                        line=dict(color='rgba(255,255,255,0)'),
                        hoverinfo="skip",
                        showlegend=False
                    ))
                    
                    fig.update_layout(title="Projeção de Vendas (R$ milhões)", template="plotly_white", height=400,
                                      legend=dict(orientation="h", yanchor="bottom", y=1.02))
                    st.plotly_chart(fig, width="stretch")
                    
                    proximo_tri = idx_futuro[0]
                    valor_previsto = prev_media.iloc[0]
                    st.success(f"**Mensagem Executiva:** Se o padrão sazonal e a tendência recente se mantiverem, as vendas devem ficar em torno de **R$ {valor_previsto:,.1f} milhões** no {period_para_rotulo(proximo_tri)}.")
                    
                except Exception as e:
                    st.error(f"Erro no modelo SARIMAX: {e}")
            else:
                st.warning("Dados históricos insuficientes para treinar o modelo SARIMAX.")

        # --- 2. Projeção do Google Trends (Prophet) ---
        with col2:
            st.subheader("2. Projeção do Interesse de Busca")
            st.caption("Modelo Prophet — Próximos 6 meses (Google Trends).")
            
            trends_m = fonte.trends_mensal()
            
            # Fallback para backup
            if trends_m.empty:
                try:
                    caminho_backup = os.path.join("BD", "ultimaLeituraGA.csv")
                    if os.path.exists(caminho_backup):
                        df_bkp = pd.read_csv(caminho_backup)
                        df_bkp['Data'] = pd.to_datetime(df_bkp['Data'])
                        trends_m = df_bkp.set_index('Data')['Quantidade'].sort_index()
                        st.info("ℹ️ Utilizando dados de backup para a projeção (API indisponível).")
                except Exception as e:
                    st.warning(f"Erro ao tentar ler o backup: {e}")
            
            if len(trends_m) > 12:
                try:
                    # 1. Prepara dados para o Prophet
                    df_prophet = trends_m.reset_index()
                    df_prophet.columns = ['ds', 'y']
                    df_prophet['ds'] = pd.to_datetime(df_prophet['ds']).dt.tz_localize(None)
                    df_prophet['y'] = pd.to_numeric(df_prophet['y'], errors='coerce')
                    df_prophet = df_prophet.dropna(subset=['ds', 'y'])
                    
                    # Remove duplicatas de datas (o Prophet quebra se houver)
                    df_prophet = df_prophet.drop_duplicates(subset=['ds'], keep='last').sort_values('ds')

                    # 2. Treina o modelo
                    m = Prophet(yearly_seasonality=True, weekly_seasonality=False, daily_seasonality=False)
                    m.fit(df_prophet)
                    
                    # 3. Previsão para os próximos 6 meses
                    futuro = m.make_future_dataframe(periods=6, freq='ME') # 'ME' para Month End
                    forecast = m.predict(futuro)
                    
                    # 4. Separa os dados para exibição
                    # Filtra o histórico para mostrar apenas os últimos 36 meses (3 anos) -> evita esmagar a projeção
                    limite_historico = df_prophet['ds'].max() - pd.DateOffset(months=36)
                    historico_plot = df_prophet[df_prophet['ds'] >= limite_historico]
                    
                    # Filtra a projeção apenas para o futuro
                    futuro_plot = forecast[forecast['ds'] > df_prophet['ds'].max()]
                    
                    fig = go.Figure()
                    
                    # Linha histórica
                    fig.add_trace(go.Scatter(
                        x=historico_plot['ds'], 
                        y=historico_plot['y'], 
                        mode='lines', 
                        name='Histórico', 
                        line=dict(color=CORES["trends"], width=2)
                    ))
                    
                    # Ponto de conexão e Linha de Projeção
                    ultimo_real = pd.DataFrame({'ds': [df_prophet['ds'].iloc[-1]], 'y': [df_prophet['y'].iloc[-1]]})
                    proj_plot = pd.concat([ultimo_real, futuro_plot[['ds', 'yhat']].rename(columns={'yhat': 'y'})])
                    
                    fig.add_trace(go.Scatter(
                        x=proj_plot['ds'], 
                        y=proj_plot['y'], 
                        mode='lines+markers', 
                        name='Projeção', 
                        line=dict(color=CORES["negativo"], width=3, dash='dash')
                    ))
                    
                    # Faixa de confiança
                    fig.add_trace(go.Scatter(
                        x=futuro_plot['ds'].tolist() + futuro_plot['ds'].tolist()[::-1],
                        y=futuro_plot['yhat_upper'].tolist() + futuro_plot['yhat_lower'].tolist()[::-1],
                        fill='toself',
                        fillcolor='rgba(192, 57, 43, 0.15)',
                        line=dict(color='rgba(255,255,255,0)'),
                        hoverinfo="skip",
                        showlegend=False
                    ))
                    
                    fig.update_layout(
                        title="Projeção de Interesse de Busca (0-100)", 
                        template="plotly_white", 
                        height=400,
                        legend=dict(orientation="h", yanchor="bottom", y=1.02),
                        hovermode="x unified"
                    )
                    
                    # 5. Força o eixo X a mostrar um zoom na janela de interesse (últimos 24 meses do histórico + projeção)
                    limite_x_inicio = df_prophet['ds'].max() - pd.DateOffset(months=24)
                    limite_x_fim = futuro_plot['ds'].max() + pd.DateOffset(months=1)
                    fig.update_xaxes(range=[limite_x_inicio, limite_x_fim])
                    
                    st.plotly_chart(fig, width="stretch")
                    
                    # Mensagem Executiva
                    ultimo_valor = futuro_plot['yhat'].iloc[-1]
                    st.error(f"**Mensagem Executiva:** A tendência de queda (ou estabilização em {ultimo_valor:.0f}) no interesse de busca deve continuar, a menos que haja uma ação de marketing significativa.")
                    
                except Exception as e:
                    st.error(f"Erro no modelo Prophet: {e}")
            else:
                st.warning(f"Dados insuficientes para treinar o Prophet. A série tem apenas {len(trends_m)} pontos.")


        _como_interpretar(
            "As projeções não são 'bolas de cristal'. Elas usam o comportamento passado (sazonalidade e tendência) "
            "para desenhar um cenário provável. A área sombreada mostra a margem de erro esperada. "
            "Quanto mais distante no futuro, maior a incerteza."
        )