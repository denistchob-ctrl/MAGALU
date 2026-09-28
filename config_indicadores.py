"""
config_indicadores.py
======================
Dicionário central de todos os indicadores usados no dashboard. Cada
entrada mapeia um nome canônico (usado no código) para a tupla
(guia, indicador) real da planilha.

Se o nome de um indicador na planilha mudar, basta editar AQUI — todos os
gráficos e páginas passam a usar o nome novo automaticamente.

Também centraliza:
  - Limiares de validação (mínimo de observações para correlação, etc.).
  - Mapeamentos de unidades de negócio (Reclame Aqui).
  - Constantes da janela de análise.

Marcações "# AJUSTAR PARA O NOME REAL DA COLUNA" indicam pontos onde o
nome pode variar dependendo da versão da planilha.
"""

# ----------------------------------------------------------------------
# Janelas temporais
# ----------------------------------------------------------------------
ANO_INICIAL = 2018
ANO_FINAL = 2026

# ----------------------------------------------------------------------
# Indicadores do DRE — (guia, indicador)
# ----------------------------------------------------------------------
INDICADORES = {
    # --- 1. Indicadores (topo do DRE) ---
    "receita_liquida":        ("1. Indicadores", "Receita Líquida Total"),
    "receita_bruta":          ("1. Indicadores", "Receita Bruta Total"),
    "ebitda":                 ("1. Indicadores", "EBITDA"),
    "ebitda_ajustado":        ("1. Indicadores", "EBITDA Ajustado"),
    "lucro_liquido":          ("1. Indicadores", "Lucro Líquido"),
    "lucro_liquido_ajustado": ("1. Indicadores", "Lucro Líquido Ajustado"),
    "margem_bruta":           ("1. Indicadores", "Margem Bruta"),
    "margem_ebitda":          ("1. Indicadores", "Margem EBITDA"),
    "margem_liquida":         ("1. Indicadores", "Margem Líquida"),
    "vendas_totais":          ("1. Indicadores", "Vendas Totais (incluindo marketplace)"),
    "participacao_ecommerce": ("1. Indicadores", "Participação E-commerce Total nas Vendas Totais"),
    "numero_lojas":           ("1. Indicadores", "Quantidade de Lojas - Final do Período"),
    "area_vendas":            ("1. Indicadores", "Área de Vendas - Final do Período (M²)"),
    # "vendas_lojas_fisicas_crescimento" existe na planilha como CRESCIMENTO (%).
    # Para o valor absoluto das lojas físicas, usar a guia '12. Vendas e Lojas por Canal'.
    "vendas_lojas_fisicas_cresc_pct": ("1. Indicadores", "Crescimento nas Vendas Totais Lojas Físicas"),

    # --- 3. DRE Consolidado ---
    "custo_total":            ("3. DRE Consolidado", "Custo Total"),
    "despesas_operacionais":  ("3. DRE Consolidado", "Total de Despesas Operacionais"),

    # --- 7. Fluxo de Caixa Gerencial ---
    "fluxo_caixa_operacional":("7. Fluxo de Caixa Gerencial", "Fluxo de Caixa das Atividades Operacionais"),
    "fluxo_caixa_investimento":("7. Fluxo de Caixa Gerencial", "Fluxo de Caixa das Atividades de Investimentos"),
    "fluxo_caixa_financiamento":("7. Fluxo de Caixa Gerencial", "Fluxo de Caixa das Atividades de Financiamentos"),

    # --- 10. Investimentos ---
    "invest_tecnologia":      ("10.Investimentos", "Tecnologia"),
    "invest_logistica":       ("10.Investimentos", "Logística"),
    "invest_lojas":           ("10.Investimentos", "Lojas Físicas"),
    "invest_outros":          ("10.Investimentos", "Outros"),
    "invest_total":           ("10.Investimentos", "Total"),

    # --- 12. Vendas e Lojas por Canal ---
    "vendas_ecommerce_total": ("12. Vendas e Lojas por Canal", "Subtotal - E-commerce Total"),
    "vendas_ecommerce_1p":    ("12. Vendas e Lojas por Canal", "E-commerce Tradicional (1P)"),
    "vendas_marketplace_3p":  ("12. Vendas e Lojas por Canal", "Marketplace (3P)"),
    "vendas_lojas_fisicas":   ("12. Vendas e Lojas por Canal", "Subtotal - Lojas Físicas"),
    "vendas_totais_canal":    ("12. Vendas e Lojas por Canal", "Vendas Totais"),

    # --- 13. Luizacred ---
    "luizacred_faturamento":  ("13. Luizacred - DRE", "Faturamento Total Luizacred"),
    "luizacred_lucro":        ("13. Luizacred - DRE", "Lucro Líquido"),
}

# ----------------------------------------------------------------------
# Indicadores que são PERCENTUAIS/MARGENS — não podem ser somados ao
# agregar para semestral/anual. Ao agregar, usamos a MÉDIA.
#
# Se um indicador percentual não estiver aqui, ele será somado — o que
# produz valores absurdos (ex.: Participação E-commerce = 282%).
# ----------------------------------------------------------------------
INDICADORES_PERCENTUAIS = {
    "margem_bruta",
    "margem_ebitda",
    "margem_ebitda_ajustado",
    "margem_liquida",
    "margem_liquida_ajustada",
    "participacao_ecommerce",
    "vendas_lojas_fisicas_cresc_pct",
    # Crescimentos (%) também são percentuais:
    # ajuste conforme os indicadores que você mapear no dicionário INDICADORES
}

# ----------------------------------------------------------------------
# Unidades de negócio do Reclame Aqui
# ----------------------------------------------------------------------
UNIDADES_RA = ["online", "fisica", "luizacred", "consorcio"]

# ----------------------------------------------------------------------
# Limiares de validação
# ----------------------------------------------------------------------
MIN_OBSERVACOES_CORRELACAO = 5      # abaixo disso, avisar o usuário
MIN_OBSERVACOES_TENDENCIA  = 8      # abaixo disso, não plotar linha de tendência

# ----------------------------------------------------------------------
# Cores (identidade visual do dashboard)
# ----------------------------------------------------------------------
CORES = {
    "primaria":    "#1F4E79",   # azul escuro corporativo
    "secundaria":  "#2E86AB",   # azul médio
    "acento":      "#F18F01",   # laranja
    "positivo":    "#2E8B57",   # verde
    "negativo":    "#C0392B",   # vermelho
    "neutro":      "#7F8C8D",   # cinza
    "trends":      "#8C7AE6",   # roxo (Google Trends)
    "ra":          "#C98A4B",   # marrom (Reclame Aqui)
    "mercado":     "#1E6091",   # azul escuro (cotação)
    "volume":      "#7FA8C9",   # azul claro (volume)
    "invest":      "#45B8AC",   # verde-água (investimentos)
}