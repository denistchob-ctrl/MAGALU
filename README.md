# MAGALU
## PI MAGALU Dashboard

## Dados obtidos de:
* Site MAGALU Institucional
* Reclame Aqui

## Estrutura Básica do Projeto
### Módulo Principal (main.py)
* Leitura do Arquivo XLSX com conteúdo do Resultado Financeiro do Conglomerado MAGALU
* Leitura dos dados do Reclame Aqui (arquivos CSV segmentados em 4 empresas)
    * Dados segmentados pelas 4 empresas (física, online, LuizaCred e Consórcio)
    * e também por Desempenho, Problemas, Categorias e Produtos ou Serviços
* Leitura dos dados dos Valores das Ações do MAGALU
* Leitura dos dados do Google Trends com números das pesquisas no google para o termo MAGALU e Magazine Luiza
* Dados segmentados por data e por região do Brasil
    * Foi realizada a tradução dos nomes dos estados que o Google Trends exportou quando fez a segmentação por região
* Limpeza dos Dados
    * Valores nulos substituidos por zero
    * Linhas nulas eliminadas
    * Colunas em branco que eram inteiramente vazias foram eliminadas
    * Títulos com quebras de linha consertados
    * Colunas com título de data parcial complementada com 01/
    * Conteúdos que são percentuais na planilha original são importados como fração (valor / 100)





