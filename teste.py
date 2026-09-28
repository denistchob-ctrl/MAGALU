from repositorio_dados import RepositorioDados
repo = RepositorioDados().carregar_tudo()

serie = repo.serie_dre_por_granularidade(
    "1. Indicadores", "Receita Líquida Total",
    "anual", None, chave_indicador="receita_liquida",
)
print(serie)