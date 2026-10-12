from magalu_loader import MagaluDataLoader
from magalu_limpeza import limpar_loader
from magalu_export_txt import exportar_guias_para_txt, exportar_tudo_em_um_arquivo
from magalu_fontes_externas import (
    CotacaoAcaoLoader,
    ReclameAquiLoader,
)
from magalu_google_trends_live import GoogleTrendsPyTrendsLoader
from magalu_google_trends_anual import GoogleTrendsPorRegiaoAnual

modo_debug = True

# ----------------------------------------------------------------------
# 1) Planilha de resultados trimestrais (RESULTADO_2T26_POR.xlsx)
#    Procurada automaticamente dentro da pasta "BD".
# ----------------------------------------------------------------------
print("Carregando planilha de resultados trimestrais...")
loader = MagaluDataLoader("RESULTADO_2T26_POR.xlsx")
relatorios = limpar_loader(loader)   # limpa in place

if modo_debug:
    loader.listar_guias()
    loader.listar_indicadores("1. Indicadores")
    loader.get_series("1. Indicadores", "EBITDA")
    loader.get_array("1. Indicadores", "EBITDA")
    loader.get_sheet_df("4. Balanço Patrimonial")
    loader.buscar_indicador("margem")
    # exportar_guias_para_txt(loader, pasta_saida="saida_txt")
    # exportar_tudo_em_um_arquivo(loader, caminho_saida="saida_txt/00_TODAS_AS_GUIAS.txt")

# ----------------------------------------------------------------------
# 2) Cotação da ação
# ----------------------------------------------------------------------
print("Carregando histórico de cotações da ação...")
cotacao = CotacaoAcaoLoader()
if modo_debug:
    cotacao.df
    cotacao.get_serie("Fechamento")
    cotacao.get_serie("Volume_Financeiro")

# ----------------------------------------------------------------------
# 3) Google Trends (ao vivo via pytrends, com backup automático)
#    - Série mensal: backup em BD/ultimaLeituraGA.csv
#    - Região agregada do loader live é IGNORADA — a região passa a vir
#      do consolidado anual (ver bloco 3b).
# ----------------------------------------------------------------------
print("Carregando dados do Google Trends (série mensal)...")
trends = None
try:
    trends = GoogleTrendsPyTrendsLoader(
        termos=["Magazine Luiza"],
        geo="BR",
        timeframe="all",
    )
    if trends.usando_backup:
        print("⚠ Google Trends indisponível agora — usando a última leitura "
              "salva em backup (pode estar desatualizada).")
except RuntimeError as erro:
    print(f"⚠ Não foi possível obter dados do Google Trends (nem ao vivo, "
          f"nem backup): {erro}")

if modo_debug and trends is not None:
    trends.serie_temporal
    trends.get_serie_temporal()

# ----------------------------------------------------------------------
# 3b) Google Trends por região, ano a ano (fonte única de verdade p/ região)
#     Anos passados vêm do consolidado em disco (GA_porRegiao_ano_a_ano.csv);
#     apenas o ano corrente é reconsultado ao vivo no Google Trends.
#     Derivados gerados automaticamente:
#       - GA_porRegiao_agregada.csv
#       - GA_serie_temporal_anualizada.csv
# ----------------------------------------------------------------------
print("Carregando Google Trends por região, ano a ano...")
ga_anual = GoogleTrendsPorRegiaoAnual(
    ano_inicio=2004,
    ano_fim=2026,
    termos=["Magazine Luiza"],
    apenas_ano_corrente_ao_vivo=True,
    pausa_entre_anos=15,
)

if modo_debug:
    print("Anos disponíveis:", ga_anual.anos_disponiveis())
    print("Regiões disponíveis:", ga_anual.regioes_disponiveis())
    print("\nPrimeiras linhas do consolidado:")
    print(ga_anual.df.head(10))
    print("\nTop 10 regiões em 2024:")
    print(ga_anual.df_por_ano(2024).sort_values(ascending=False).head(10))
    print("\nRegião agregada (soma dos anos):")
    print(ga_anual.regiao_agregada().sort_values("Quantidade", ascending=False).head(10))
    print("\nSérie anualizada:")
    print(ga_anual.serie_temporal_anualizada())

# ----------------------------------------------------------------------
# 4) Reclame Aqui
# ----------------------------------------------------------------------
print("Carregando dados do Reclame Aqui...")
ra = ReclameAquiLoader()
if modo_debug:
    empresas = ra.listar_empresas()
    print("Empresas com dados no Reclame Aqui:")
    print(empresas)
    ra.listar_categorias("online")
    ra.categorias("fisica")
    ra.problemas("fisica")
    ra.produtos("fisica")
    ra.desempenho("fisica")
    desempenho = ra.get("luizacred", "desempenho")
    print("Desempenho da Luizacred:")
    print(desempenho)