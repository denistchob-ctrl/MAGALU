# MAGALU
## PI MAGALU Dashboard

Rotina rodando em: https://pi3-magalu.streamlit.app/

## Dados obtidos de:
* Site MAGALU Institucional
* Reclame Aqui
* Google Trends (via API pytrends)

## Estrutura Básica do Projeto

### Módulo Principal (main.py)
* Leitura do Arquivo XLSX com conteúdo do Resultado Financeiro do Conglomerado MAGALU
* Leitura dos dados do Reclame Aqui (arquivos CSV segmentados em 4 empresas)
    * Dados segmentados pelas 4 empresas (física, online, LuizaCred e Consórcio)
    * e também por Desempenho, Problemas, Categorias e Produtos ou Serviços
* Leitura dos dados dos Valores das Ações do MAGALU
* Leitura dos dados do Google Trends (termo "Magazine Luiza")
    * **Série mensal** via API direto do Google Trends.
        * Em caso positivo de leitura, um backup é gerado (`BD/ultimaLeituraGA.csv`).
        * Caso a API falhe por 3 vezes, o backup é utilizado.
    * **Interesse por região, ano a ano**, via `magalu_google_trends_anual.py`:
        * Cada ano é uma consulta independente (a API não permite quebra
          temporal em `interest_by_region`).
        * Anos passados são considerados ESTÁTICOS e ficam no consolidado
          `BD/GA_porRegiao_ano_a_ano.csv`.
        * Apenas o **ano corrente** é reconsultado ao vivo a cada execução.
        * Derivados gerados automaticamente:
            * `BD/GA_porRegiao_agregada.csv` — soma de todos os anos por região.
            * `BD/GA_serie_temporal_anualizada.csv` — soma por ano.
        * **Importante:** a região agregada do loader live
          (`ultimaLeituraGAporRegiao.csv`) foi DESCONSIDERADA. A fonte única
          de verdade para região é o consolidado ano a ano, para evitar
          inconsistências entre a "foto" antiga e os dados por ano.
    * Tradução dos nomes dos estados que o Google Trends exportou em inglês.

### Limpeza dos Dados
* Valores nulos substituídos por zero (configurável por guia)
* Linhas nulas eliminadas
* Colunas inteiramente vazias eliminadas
* Títulos com quebras de linha consertados
* Colunas com título de data parcial complementadas com `01/`
* Conteúdos que são percentuais na planilha original importados como fração (valor / 100)
* Remoção do sufixo "REAPRESENTADO" dos cabeçalhos de período
* Conversão de células com `"-"` (traço) para `0` em indicadores configurados

### Inventário de Dados
* `inventario_dados.py` gera um inventário (sem valores) do que existe em
  cada fonte, útil para conferir a extração e identificar lacunas.
* Saídas em `inventario/`:
    * `inventario_dre.csv` (WIDE)
    * `inventario_cotacao.csv` + `inventario_cotacao_resumo.csv`
    * `inventario_reclame_aqui.csv`
    * `inventario_google_trends_temporal.csv`
    * `inventario_google_trends_regional_anual.csv`
    * `inventario_google_trends_regional_agregada.csv`
    * `inventario_google_trends_ano_regiao_wide.csv`

### Próximos Passos
* Decidir melhores informações a serem exibidas no dashboard
* Verificar a possibilidade de cruzamento de dados entre as fontes
* Verificar a possibilidade de o usuário escolher as informações a serem exibidas
* Verificar a possibilidade de implementar uma análise preditiva ao projeto