from magalu_loader import MagaluDataLoader
from magalu_limpeza import limpar_loader
from magalu_export_txt import exportar_guias_para_txt, exportar_tudo_em_um_arquivo
from magalu_fontes_externas import (
    CotacaoAcaoLoader,
    GoogleTrendsLoader,
    ReclameAquiLoader,
)

# ----------------------------------------------------------------------
# 1) Planilha de resultados trimestrais (RESULTADO_2T26_POR.xlsx)
#    Procurada automaticamente dentro da pasta "BD".
# ----------------------------------------------------------------------
loader = MagaluDataLoader("RESULTADO_2T26_POR.xlsx")
relatorios = limpar_loader(loader)   # limpa loader.dados, loader.colunas e loader.arrays "in place"

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
cotacao = CotacaoAcaoLoader()
cotacao.df                                  # DataFrame diário completo (índice = Data)
cotacao.get_serie("Fechamento")             # Series só com o fechamento
cotacao.get_serie("Volume_Financeiro")      # Series só com o volume financeiro negociado

print("Cotação -> shape:", cotacao.df.shape)
print(cotacao.df.tail(3))
print()

# ----------------------------------------------------------------------
# 3) Google Trends (Google_Trends_-_MAGAZINE_LUIZA_e_MAGALU_-_*.csv)
# ----------------------------------------------------------------------
trends = GoogleTrendsLoader()
trends.serie_temporal                          # todos os anos disponíveis, já consolidados (Ano, Time, Quantidade)
trends.por_regiao                              # todas as regiões/anos disponíveis, já consolidados (Ano, Region, Quantidade)
trends.get_serie_temporal()                    # Series indexada por data, com o total consolidado
trends.get_por_regiao()                # Series indexada por região, só do ano de 2019

print("Google Trends (série temporal) -> shape:", trends.serie_temporal.shape)
print(trends.get_serie_temporal().tail(3))
print()
print("Google Trends (por região) -> shape:", trends.por_regiao.shape)
print(trends.get_por_regiao().head(30))
print()

# ----------------------------------------------------------------------
# 4) Reclame Aqui (RA-<empresa>-<categoria>.csv)
#    Empresas descobertas automaticamente na pasta BD: consorcio, fisica,
#    online, luizacred (grafias "luizcred"/"luizacred" são unificadas).
# ----------------------------------------------------------------------
ra = ReclameAquiLoader()
ra.listar_empresas()                  # ex.: ['consorcio', 'fisica', 'luizacred', 'online']
ra.listar_categorias("online")        # ex.: ['categorias', 'desempenho', 'problemas', 'produtos']
ra.categorias("fisica")               # DataFrame: categoria x quantidade de reclamações
ra.problemas("fisica")                # DataFrame: problema x quantidade de reclamações
ra.produtos("fisica")                 # DataFrame: produto/serviço x quantidade de reclamações
ra.desempenho("fisica")               # DataFrame: métricas anuais de reputação/atendimento
ra.get("luizacred", "desempenho")     # forma equivalente e genérica de acessar qualquer empresa/categoria

print("Reclame Aqui - empresas encontradas:", ra.listar_empresas())
for empresa in ra.listar_empresas():
    print(f"  {empresa}: {ra.listar_categorias(empresa)}")
print()
print("Reclame Aqui - categorias (fisica):")
print(ra.categorias("fisica").head(3))
print()
print("Reclame Aqui - desempenho (luizacred):")
print(ra.desempenho("luizacred"))
