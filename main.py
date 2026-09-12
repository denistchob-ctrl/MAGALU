from magalu_loader import MagaluDataLoader
from magalu_limpeza import limpar_loader
from magalu_export_txt import exportar_guias_para_txt, exportar_tudo_em_um_arquivo
from magalu_fontes_externas import (
    CotacaoAcaoLoader,
    ReclameAquiLoader,
)
from magalu_google_trends_live import GoogleTrendsPyTrendsLoader

modo_debug = True

# ----------------------------------------------------------------------
# 1) Planilha de resultados trimestrais (RESULTADO_2T26_POR.xlsx)
#    Procurada automaticamente dentro da pasta "BD".
# ----------------------------------------------------------------------
print("Carregando planilha de resultados trimestrais...")
loader = MagaluDataLoader("RESULTADO_2T26_POR.xlsx")
relatorios = limpar_loader(loader)   # limpa loader.dados, loader.colunas e loader.arrays "in place"

if modo_debug:
    loader.listar_guias()                          # todas as guias
    loader.listar_indicadores("1. Indicadores")     # linhas disponíveis numa guia
    loader.get_series("1. Indicadores", "EBITDA")   # array (Series) indexado por trimestre
    loader.get_array("1. Indicadores", "EBITDA")    # só o numpy array, sem rótulos
    loader.get_sheet_df("4. Balanço Patrimonial")   # DataFrame completo da guia
    loader.buscar_indicador("margem")               # busca indicador em todas as guias de uma vez

    # (opcional) gera os .txt de conferência já com os dados limpos
    # exportar_guias_para_txt(loader, pasta_saida="saida_txt")
    # exportar_tudo_em_um_arquivo(loader, caminho_saida="saida_txt/00_TODAS_AS_GUIAS.txt")

# ----------------------------------------------------------------------
# 2) Cotação da ação (Histórico_de_Cotações_...xlsx)
# ----------------------------------------------------------------------
print("Carregando histórico de cotações da ação...")
cotacao = CotacaoAcaoLoader()
if modo_debug:
    cotacao.df                                  # DataFrame diário completo (índice = Data)
    cotacao.get_serie("Fechamento")             # Series só com o fechamento
    cotacao.get_serie("Volume_Financeiro")      # Series só com o volume financeiro negociado

# ----------------------------------------------------------------------
# 3) Google Trends (Google_Trends_-_MAGAZINE_LUIZA_e_MAGALU_-_*.csv)
# ----------------------------------------------------------------------
# Personalizando termos, período e geografia:
print("Carregando dados do Google Trends...")
trends = GoogleTrendsPyTrendsLoader(
    termos=["Magazine Luiza"],
    geo="BR",
    timeframe="all",     # 'all' = todo o histórico disponível (desde 2004)
)
if modo_debug:
    trends.serie_temporal        # DataFrame ['Ano', 'Data', 'Quantidade']
    trends.por_regiao            # DataFrame ['Região', 'Quantidade']
    trends.get_serie_temporal()  # Series indexada por data
    gtregiao = trends.get_por_regiao()                        # Series indexada por região, com o total agregado
    print("Top 10 regiões com mais interesse:")
    print(gtregiao.sort_values(ascending=False).head(10))   # top 10 regiões com mais interesse

# ----------------------------------------------------------------------
# 4) Reclame Aqui (RA-<empresa>-<categoria>.csv)
#    Empresas descobertas automaticamente na pasta BD: consorcio, fisica,
#    online, luizacred (grafias "luizcred"/"luizacred" são unificadas).
# ----------------------------------------------------------------------
print("Carregando dados do Reclame Aqui...")
ra = ReclameAquiLoader()
if modo_debug:
    empresas = ra.listar_empresas()                  # ex.: ['consorcio', 'fisica', 'luizacred', 'online']
    print("Empresas com dados no Reclame Aqui:")
    print(empresas)
    ra.listar_categorias("online")        # ex.: ['categorias', 'desempenho', 'problemas', 'produtos']
    ra.categorias("fisica")               # DataFrame: categoria x quantidade de reclamações
    ra.problemas("fisica")                # DataFrame: problema x quantidade de reclamações
    ra.produtos("fisica")                 # DataFrame: produto/serviço x quantidade de reclamações
    ra.desempenho("fisica")               # DataFrame: métricas anuais de reputação/atendimento
    desempenho = ra.get("luizacred", "desempenho")     # forma equivalente e genérica de acessar qualquer empresa/categoria
    print("Desempenho da Luizacred:")
    print(desempenho)
