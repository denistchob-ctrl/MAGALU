from magalu_loader import MagaluDataLoader

loader = MagaluDataLoader("RESULTADO_2T26_POR.xlsx")

loader.listar_guias()                          # todas as 16 guias
loader.listar_indicadores("1. Indicadores")     # linhas disponíveis numa guia
loader.get_series("1. Indicadores", "EBITDA")   # array (Series) indexado por trimestre
loader.get_array("1. Indicadores", "EBITDA")    # só o numpy array, sem rótulos
loader.get_sheet_df("4. Balanço Patrimonial")   # DataFrame completo da guia
loader.buscar_indicador("margem")               # busca indicador em todas as guias de uma vez