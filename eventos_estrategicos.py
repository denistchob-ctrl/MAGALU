"""
eventos_estrategicos.py
========================
Catálogo da "Linha do Tempo Estratégica do Magalu" (modelo v3).

Cada evento do mundo real (mercado, macroeconomia, estratégia, financeiro,
resultado) é um objeto `Evento` com:
  - data (pontual) ou período (início/fim);
  - categoria e origem (externo × interno à empresa);
  - descrição e fontes (links) — para você poder citar na reunião;
  - `destaques`: indicadores que a página destaca ao selecionar o evento;
  - `expectativas`: hipóteses DIRECIONAIS testáveis contra os seus dados
    (ex.: "após a pandemia, a participação do e-commerce deveria subir").
    O app confere cada uma e mostra COERENTE / CONTRÁRIA / INCONCLUSIVA —
    inclusive quando os dados contrariam a narrativa.

STATUS DA FONTE de cada evento:
  "verificado"            -> fatos conferidos em fontes web (links em `fontes`).
  "conhecimento_publico"  -> data amplamente conhecida; inclua uma fonte
                             oficial antes de apresentar.
  "a_confirmar"           -> NÃO usar na reunião sem checar.

Para ajustar a narrativa, edite SOMENTE este arquivo.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List, Optional, Tuple

import pandas as pd

# ----------------------------------------------------------------------
# Indicadores EXTRAS (existem na planilha, mas não estão em
# config_indicadores.INDICADORES). Mesmo formato: (guia, indicador).
# ----------------------------------------------------------------------
INDICADORES_V3 = {
    "resultado_financeiro":    ("9. Resultado Financeiro", "Resultado Financeiro Líquido"),
    "despesas_financeiras":    ("9. Resultado Financeiro", "Despesas Financeiras"),
    "juros_emprestimos":       ("9. Resultado Financeiro", "Juros de Empréstimos e Financiamentos"),
    "aumento_capital_privado": ("7. Fluxo de Caixa Gerencial", "Aumento de Capital Privado"),
    "emissao_acoes":           ("7. Fluxo de Caixa Gerencial", "Recursos provenientes da emissão de ações"),
    "luizacred_carteira":      ("13. Luizacred - DRE", "Carteira de Crédito"),
    "margem_ebitda_ajustado":  ("1. Indicadores", "Margem EBITDA Ajustado"),
}

# Séries que são fração (0–1) e NÃO devem ser somadas ao agregar.
PERCENTUAIS_V3 = {
    "margem_ebitda_ajustado", "share_3p", "resfin_sobre_receita", "selic",
}

# Séries especiais (calculadas / de outras fontes que não o DRE)
SERIES_ESPECIAIS = {"mglu3", "selic", "trends", "share_3p", "resfin_sobre_receita"}

# Rótulo amigável e tipo de unidade: "moeda" (R$ milhões), "pct" (fração),
# "preco" (R$ por ação), "indice" (0–100).
META_SERIES = {
    "receita_liquida":        ("Receita Líquida", "moeda"),
    "receita_bruta":          ("Receita Bruta", "moeda"),
    "ebitda":                 ("EBITDA", "moeda"),
    "ebitda_ajustado":        ("EBITDA Ajustado", "moeda"),
    "lucro_liquido":          ("Lucro Líquido", "moeda"),
    "lucro_liquido_ajustado": ("Lucro Líquido Ajustado", "moeda"),
    "margem_bruta":           ("Margem Bruta", "pct"),
    "margem_ebitda":          ("Margem EBITDA", "pct"),
    "margem_ebitda_ajustado": ("Margem EBITDA Ajustada", "pct"),
    "margem_liquida":         ("Margem Líquida", "pct"),
    "vendas_totais":          ("Vendas Totais (c/ marketplace)", "moeda"),
    "participacao_ecommerce": ("Participação do E-commerce", "pct"),
    "numero_lojas":           ("Nº de lojas", "num"),
    "vendas_ecommerce_total": ("Vendas E-commerce (1P+3P)", "moeda"),
    "vendas_ecommerce_1p":    ("E-commerce 1P", "moeda"),
    "vendas_marketplace_3p":  ("Marketplace 3P", "moeda"),
    "vendas_lojas_fisicas":   ("Vendas Lojas Físicas", "moeda"),
    "invest_tecnologia":      ("Investimento em Tecnologia", "moeda"),
    "invest_logistica":       ("Investimento em Logística", "moeda"),
    "invest_lojas":           ("Investimento em Lojas", "moeda"),
    "invest_total":           ("Investimentos Totais", "moeda"),
    "fluxo_caixa_operacional":("Fluxo de Caixa Operacional", "moeda"),
    "fluxo_caixa_financiamento": ("Fluxo de Caixa de Financiamento", "moeda"),
    "fluxo_caixa_investimento":  ("Fluxo de Caixa de Investimento", "moeda"),
    "luizacred_faturamento":  ("Faturamento Luizacred", "moeda"),
    "luizacred_lucro":        ("Lucro Luizacred", "moeda"),
    "luizacred_carteira":     ("Carteira de Crédito Luizacred", "moeda"),
    "resultado_financeiro":   ("Resultado Financeiro Líquido", "moeda"),
    "despesas_financeiras":   ("Despesas Financeiras", "moeda"),
    "juros_emprestimos":      ("Juros de Empréstimos", "moeda"),
    "aumento_capital_privado":("Aumento de Capital Privado", "moeda"),
    "emissao_acoes":          ("Recursos da Emissão de Ações", "moeda"),
    # especiais
    "mglu3":                  ("MGLU3 (fechamento ajustado)", "preco"),
    "selic":                  ("Selic (meta, fim do trimestre)", "pct"),
    "trends":                 ("Interesse de busca (Google Trends)", "indice"),
    "share_3p":               ("Marketplace 3P / Vendas Totais", "pct"),
    "resfin_sobre_receita":   ("Resultado Financeiro / Receita Líquida", "pct"),
}

CATEGORIAS = ["Mercado", "Macroeconomia", "Estratégia", "Financeiro", "Operação", "Resultado"]
ORIGENS = ("externo", "interno")


# ----------------------------------------------------------------------
# Estruturas
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Expectativa:
    """Hipótese direcional testável contra os dados.

    modo:
      "medio"   -> média dos N trimestres DEPOIS × média dos N ANTES (pontual)
      "periodo" -> média dentro do período do evento × N trimestres antes do início
      "pico"    -> valor do trimestre do evento × média dos N trimestres antes
      "aa"      -> trimestre do evento × mesmo trimestre do ano anterior
    """
    chave: str
    direcao: str            # "alta" | "queda"
    modo: str = "medio"
    comentario: str = ""


@dataclass(frozen=True)
class Evento:
    id: str
    nome: str
    rotulo_curto: str
    data_inicio: date
    categoria: str
    origem: str
    descricao: str
    data_fim: Optional[date] = None
    o_que_olhar: str = ""
    trimestre_ref: Optional[str] = None      # ex.: "4T23" (âncora da análise)
    incluir_trimestre_no_depois: bool = False
    destaques: Tuple[str, ...] = ()
    expectativas: Tuple[Expectativa, ...] = ()
    fontes: Tuple[Tuple[str, str], ...] = ()
    status: str = "verificado"
    texto_pos: str = "top center"            # posição do rótulo na linha do tempo

    @property
    def eh_periodo(self) -> bool:
        return self.data_fim is not None

    @property
    def ano(self) -> int:
        return self.data_inicio.year

    @property
    def data_exibicao(self) -> str:
        if self.eh_periodo:
            return f"{self.data_inicio:%d/%m/%Y} → {self.data_fim:%d/%m/%Y}"
        return f"{self.data_inicio:%d/%m/%Y}"


# ----------------------------------------------------------------------
# Catálogo
# ----------------------------------------------------------------------
EVENTOS: List[Evento] = [
    Evento(
        id="covid",
        nome="Pandemia de Covid-19 acelera o varejo online",
        rotulo_curto="Pandemia",
        data_inicio=date(2020, 3, 11),
        categoria="Mercado", origem="externo",
        descricao=(
            "A OMS declarou a Covid-19 como pandemia em 11/03/2020. Comunicados da época "
            "associam o salto das vendas online em 2020 aos novos hábitos de consumo "
            "estimulados pela pandemia (caso da KaBuM!, por exemplo)."
        ),
        o_que_olhar="Participação do e-commerce, vendas online (1P e marketplace) e interesse de busca.",
        destaques=("participacao_ecommerce", "vendas_ecommerce_total", "vendas_ecommerce_1p",
                   "vendas_marketplace_3p", "vendas_lojas_fisicas", "trends"),
        expectativas=(
            Expectativa("participacao_ecommerce", "alta"),
            Expectativa("vendas_ecommerce_total", "alta"),
            Expectativa("vendas_marketplace_3p", "alta"),
            Expectativa("trends", "alta"),
        ),
        fontes=(
            ("Jovem Pan — pandemia declarada pela OMS em 11/03/2020",
             "https://jovempan.com.br/noticias/pandemia-da-covid-19-completa-5-anos-nesta-terca/"),
            ("Canaltech — KaBuM!: vendas de 2020 impulsionadas pela pandemia",
             "https://canaltech.com.br/negocios/magazine-luiza-compra-kabum-189883/"),
        ),
        status="verificado",
    ),
    Evento(
        id="aquisicoes",
        nome="Onda de aquisições (21 empresas em ~1,5 ano até jul/2021)",
        rotulo_curto="Aquisições",
        data_inicio=date(2020, 1, 1), data_fim=date(2021, 7, 15),
        categoria="Estratégia", origem="interno",
        descricao=(
            "Segundo a Reuters, na data do anúncio da KaBuM! o Magalu já havia adquirido 21 "
            "empresas em um ano e meio, ampliando o ecossistema digital (conteúdo, fintech, "
            "categorias novas). O recorte de datas é aproximado."
        ),
        o_que_olhar="Investimento em tecnologia, vendas 1P/marketplace e fluxo de caixa de investimento.",
        destaques=("invest_tecnologia", "fluxo_caixa_investimento", "vendas_ecommerce_total", "receita_liquida"),
        expectativas=(),   # contexto: sem teste direcional
        fontes=(
            ("Reuters/IstoÉ Dinheiro — 21 empresas adquiridas em um ano e meio",
             "https://www.istoedinheiro.com.br/magazine-luiza-anuncia-oferta/"),
        ),
        status="verificado",
        texto_pos="bottom center",
    ),
    Evento(
        id="kabum",
        nome="Aquisição da KaBuM! (maior da história do Magalu)",
        rotulo_curto="KaBuM!",
        data_inicio=date(2021, 7, 15),
        categoria="Estratégia", origem="interno", trimestre_ref="3T21",
        descricao=(
            "Anunciada em 15/07/2021: R$ 1 bilhão à vista e o restante em ações, com valor total "
            "estimado em cerca de R$ 3,5 bilhões e parcela final condicionada a metas (jan/2024). "
            "A KaBuM! tinha receita bruta de R$ 3,4 bi nos 12 meses anteriores e lucro líquido de "
            "R$ 312 milhões."
        ),
        o_que_olhar="E-commerce 1P (onde a KaBuM! é consolidada), participação digital, receita e tecnologia.",
        destaques=("vendas_ecommerce_1p", "participacao_ecommerce", "receita_liquida",
                   "invest_tecnologia", "vendas_totais", "mglu3"),
        expectativas=(
            Expectativa("vendas_ecommerce_1p", "alta"),
            Expectativa("receita_liquida", "alta"),
            Expectativa("participacao_ecommerce", "alta"),
            Expectativa("invest_tecnologia", "alta"),
        ),
        fontes=(
            ("Canaltech — Magazine Luiza anuncia a compra do KaBuM!",
             "https://canaltech.com.br/negocios/magazine-luiza-compra-kabum-189883/"),
            ("Correio Braziliense/Agência Estado — maior aquisição da história",
             "https://www.correiobraziliense.com.br/economia/2021/07/4937781-magalu-compra-kabum--na-maior-aquisicao-da-historia-da-companhia.html"),
            ("TecMundo — contrato de mais de R$ 3,5 bi em três parcelas",
             "https://www.tecmundo.com.br/mercado/221114-magazine-luiza-compra-kabum-maior-commerce-games-brasil.htm"),
        ),
        status="verificado",
    ),
    Evento(
        id="followon",
        nome="Follow-on (oferta de ações de até ~R$ 4,6 bi)",
        rotulo_curto="Follow-on",
        data_inicio=date(2021, 7, 22),
        categoria="Financeiro", origem="interno", trimestre_ref="3T21",
        descricao=(
            "Anunciado junto com a KaBuM! em 15/07/2021, com precificação prevista para 22/07/2021 "
            "e valor de até R$ 4,586 bilhões (base + lote adicional, ao preço de fechamento da véspera). "
            "A captação reforça o caixa para a expansão e aquisições."
        ),
        o_que_olhar="Fluxo de caixa de financiamento e recursos de emissão de ações no 3T21.",
        destaques=("emissao_acoes", "fluxo_caixa_financiamento", "invest_total", "mglu3"),
        expectativas=(
            Expectativa("emissao_acoes", "alta", modo="pico"),
            Expectativa("fluxo_caixa_financiamento", "alta", modo="pico"),
        ),
        fontes=(
            ("Reuters/IstoÉ Dinheiro — oferta de ações de R$ 4,6 bi",
             "https://www.istoedinheiro.com.br/magazine-luiza-anuncia-oferta/"),
            ("Mercado & Consumo — cronograma do bookbuilding",
             "https://mercadoeconsumo.com.br/15/07/2021/noticias-varejo/magalu-compra-kabum-plataforma-de-tecnologia-e-games/amp/"),
        ),
        status="verificado",
        texto_pos="bottom center",
    ),
    Evento(
        id="juros_altos",
        nome="Juros elevados (Selic ≥ 11,75%, pico de 13,75%) e sequência de prejuízos",
        rotulo_curto="Juros altos",
        data_inicio=date(2022, 3, 16), data_fim=date(2023, 12, 31),
        categoria="Macroeconomia", origem="externo",
        descricao=(
            "A Selic chegou a 13,75% em ago/2022 e ali ficou até o início dos cortes. No Magalu, o "
            "prejuízo líquido ajustado de 2023 foi de R$ 550,1 mi (R$ 372,1 mi em 2022), mesmo com "
            "melhora operacional; a empresa destacou a redução de 20% das despesas financeiras, que "
            "ainda pesavam ~4% da receita líquida. O último lucro ajustado antes do 4T23 havia sido "
            "no 3T21."
        ),
        o_que_olhar="Resultado financeiro, lucro e margem líquida (rentabilidade final) versus vendas e EBITDA (operação).",
        destaques=("resultado_financeiro", "lucro_liquido", "margem_liquida", "fluxo_caixa_operacional",
                   "mglu3", "selic", "vendas_totais"),
        expectativas=(
            Expectativa("resfin_sobre_receita", "queda", modo="periodo",
                        comentario="Peso das despesas financeiras líquidas sobre a receita"),
            Expectativa("lucro_liquido", "queda", modo="periodo"),
            Expectativa("margem_liquida", "queda", modo="periodo"),
            Expectativa("vendas_totais", "alta", modo="periodo",
                        comentario="Crescimento de vendas apesar da rentabilidade pressionada"),
        ),
        fontes=(
            ("Suno — prejuízo ajustado de 2023 (R$ 550 mi) e Ebitda",
             "https://www.suno.com.br/noticias/magazine-luiza-mglu3-analistas-mantem-recomendacao-neutra-va/"),
            ("Guia do Investidor — despesas financeiras 20% menores (4% da receita)",
             "https://guiadoinvestidor.com.br/?p=250919"),
            ("Mais Retorno — fim do ciclo de altas em 13,75% (ago/2022)",
             "https://maisretorno.com/portal/taxa-selic-especialistas-esperam-juros-1375-ate-meados-2023"),
        ),
        status="verificado",
    ),
    Evento(
        id="selic_cortes_2023",
        nome="Selic começa a cair (13,75% → 13,25%)",
        rotulo_curto="Início dos cortes",
        data_inicio=date(2023, 8, 2),
        categoria="Macroeconomia", origem="externo", trimestre_ref="3T23",
        descricao=(
            "Início do ciclo de afrouxamento monetário em ago/2023, que levou a Selic a 10,50% em "
            "mai/2024 (antes de voltar a subir no 2º semestre de 2024). Data e valores: conhecimento "
            "público do calendário do Copom — cite a ata oficial do BCB."
        ),
        o_que_olhar="Resultado financeiro líquido dos trimestres seguintes.",
        destaques=("resultado_financeiro", "selic", "margem_liquida", "mglu3"),
        expectativas=(
            Expectativa("resfin_sobre_receita", "alta", modo="medio",
                        comentario="Menor peso financeiro líquido após os cortes"),
        ),
        fontes=(),
        status="conhecimento_publico",
        texto_pos="bottom center",
    ),
    Evento(
        id="aporte_2024",
        nome="Aumento de capital de R$ 1,25 bi (homologado em fev/2024)",
        rotulo_curto="Aporte R$ 1,25 bi",
        data_inicio=date(2024, 2, 22),
        categoria="Financeiro", origem="interno", trimestre_ref="1T24",
        descricao=(
            "Aprovado em jan/2024 e homologado em 22/02/2024: os controladores subscreveram 66% do total "
            "e o mercado o restante. Recursos destinados a acelerar investimentos em tecnologia "
            "(Luizalabs, UX, Ads, Fintech, Fulfillment, Magalu Cloud)."
        ),
        o_que_olhar="Aumento de capital no fluxo de caixa e investimento em tecnologia nos trimestres seguintes.",
        destaques=("aumento_capital_privado", "invest_tecnologia", "fluxo_caixa_financiamento", "mglu3"),
        expectativas=(
            Expectativa("aumento_capital_privado", "alta", modo="pico"),
            Expectativa("invest_tecnologia", "alta", modo="medio"),
        ),
        fontes=(
            ("Suno — homologação do aumento de capital",
             "https://www.suno.com.br/noticias/magazine-luiza-mglu3-homologa-aumento-capital-gpj/amp/"),
            ("Guia do Investidor — destino dos recursos (tecnologia)",
             "https://guiadoinvestidor.com.br/?p=250919"),
        ),
        status="verificado",
        texto_pos="bottom center",
    ),
    Evento(
        id="virada_4t23",
        nome="Ponto de virada: 4T23 volta ao lucro (1º lucro ajustado em 2 anos)",
        rotulo_curto="Virada 4T23",
        data_inicio=date(2024, 3, 18),
        categoria="Resultado", origem="interno", trimestre_ref="4T23",
        incluir_trimestre_no_depois=True,
        descricao=(
            "Divulgado em 18/03/2024: lucro líquido ajustado de R$ 101,5 mi no 4T23 (prejuízo de R$ 15,2 mi "
            "no 4T22), EBITDA ajustado de R$ 756,5 mi (+12,3% a/a) e margem EBITDA ajustada de 7,2%. "
            "ATENÇÃO: o retorno ao lucro ocorreu no 4T23 (Black Friday mais rentável da história), e não "
            "em 2024 como sugeria a primeira versão do roteiro; o ano de 2023 como um todo foi de prejuízo."
        ),
        o_que_olhar="Lucro, margem EBITDA e geração de caixa antes × depois do 4T23.",
        destaques=("lucro_liquido_ajustado", "lucro_liquido", "ebitda", "margem_ebitda",
                   "fluxo_caixa_operacional", "margem_liquida", "mglu3"),
        expectativas=(
            Expectativa("lucro_liquido_ajustado", "alta"),
            Expectativa("ebitda", "alta"),
            Expectativa("margem_ebitda", "alta"),
            Expectativa("fluxo_caixa_operacional", "alta"),
        ),
        fontes=(
            ("Mercado & Consumo — 4T23: lucro ajustado de R$ 101,5 mi",
             "https://mercadoeconsumo.com.br/19/03/2024/noticias/magazine-luiza-reverte-prejuizo-e-tem-lucro-liquido-ajustado-de-r-1015-mi-no-4o-trimestre/amp/"),
            ("Finance News — resultado do 4T23 e vendas por canal",
             "https://financenews.com.br/2024/03/magazine-luiza-mglu3-reverte-prejuizo-e-tem-lucro-no-4t23/"),
            ("Suno — 1º lucro ajustado em dois anos",
             "https://www.suno.com.br/noticias/magazine-luiza-mglu3-analistas-mantem-recomendacao-neutra-va/"),
        ),
        status="verificado",
    ),
    Evento(
        id="marketplace",
        nome="Marketplace como vetor de margem (2023–2024)",
        rotulo_curto="Marketplace",
        data_inicio=date(2023, 1, 1), data_fim=date(2024, 12, 31),
        categoria="Operação", origem="interno",
        descricao=(
            "A companhia atribuiu a alta do EBITDA do 4T23 principalmente ao aumento da margem de "
            "contribuição dos canais, especialmente do marketplace. Em quatro anos (até 2023) o marketplace "
            "cresceu em média 45% ao ano, segundo a empresa. O recorte 2023–2024 é uma janela de análise."
        ),
        o_que_olhar="Marketplace 3P, sua participação nas vendas totais e as margens bruta e EBITDA.",
        destaques=("vendas_marketplace_3p", "share_3p", "margem_ebitda", "margem_bruta", "vendas_totais"),
        expectativas=(
            Expectativa("vendas_marketplace_3p", "alta", modo="periodo"),
            Expectativa("share_3p", "alta", modo="periodo"),
            Expectativa("margem_ebitda", "alta", modo="periodo"),
            Expectativa("margem_bruta", "alta", modo="periodo"),
        ),
        fontes=(
            ("Guia do Investidor — Ebitda do 4T23 beneficiado pelo marketplace",
             "https://guiadoinvestidor.com.br/?p=250919"),
            ("Finance News — marketplace: crescimento médio de 45% ao ano em 4 anos",
             "https://financenews.com.br/2024/03/magazine-luiza-mglu3-reverte-prejuizo-e-tem-lucro-no-4t23/"),
        ),
        status="verificado",
        texto_pos="bottom center",
    ),
    Evento(
        id="selic_15",
        nome="Selic em 15% (jun/2025 → mar/2026)",
        rotulo_curto="Selic 15%",
        data_inicio=date(2025, 6, 18), data_fim=date(2026, 3, 18),
        categoria="Macroeconomia", origem="externo",
        descricao=(
            "A Selic chegou a 15% em 2025 e ficou nesse patamar até começar a cair em mar/2026 "
            "(14,75% em 18/03/2026). Datas do ciclo anterior a 2026: conhecimento público do "
            "calendário do Copom."
        ),
        o_que_olhar="Resultado financeiro líquido versus o desempenho operacional (EBITDA).",
        destaques=("resultado_financeiro", "selic", "ebitda", "margem_ebitda", "lucro_liquido"),
        expectativas=(
            Expectativa("resfin_sobre_receita", "queda", modo="periodo"),
        ),
        fontes=(
            ("Melhor Investimento — histórico da Selic em 2026",
             "https://melhorinvestimento.net/noticias/copom-decisao-selic-setembro-2026"),
        ),
        status="verificado",
    ),
    Evento(
        id="selic_cortes_2026",
        nome="Selic volta a cair (15% → 13,75% até set/2026)",
        rotulo_curto="Cortes 2026",
        data_inicio=date(2026, 3, 18),
        categoria="Macroeconomia", origem="externo", trimestre_ref="1T26",
        descricao=(
            "Cinco cortes consecutivos de 0,25 p.p. desde mar/2026 (14,75% → 14,50% → 14,25% → "
            "14,00% → 13,75% em 16/09/2026). Evento recente: ainda há poucos trimestres de dados."
        ),
        o_que_olhar="Resultado financeiro dos próximos trimestres.",
        destaques=("resultado_financeiro", "selic", "margem_liquida"),
        expectativas=(),
        fontes=(
            ("Melhor Investimento — Copom de 16/09/2026 e histórico de cortes",
             "https://melhorinvestimento.net/noticias/copom-decisao-selic-setembro-2026"),
        ),
        status="verificado",
        texto_pos="bottom center",
    ),
    Evento(
        id="reversao_2t26",
        nome="2T26: lojas físicas crescem, e-commerce recua e o resultado volta ao prejuízo",
        rotulo_curto="2T26",
        data_inicio=date(2026, 8, 6),
        categoria="Resultado", origem="interno", trimestre_ref="2T26",
        descricao=(
            "Divulgado em 06/08/2026: prejuízo líquido de R$ 72,5 mi (ajustado: R$ 50,4 mi); vendas totais "
            "de R$ 14,5 bi (-5,1% a/a); lojas físicas +10,3% e e-commerce -11,9% (marketplace -12,6%), "
            "movimento que a empresa liga à preservação de rentabilidade. EBITDA ajustado de R$ 708,8 mi "
            "(margem de 8,0%). O resultado financeiro líquido ficou negativo em R$ 572,3 mi. "
            "Este evento limita a narrativa 'marketplace como motor de recuperação': em 2026 ele recua."
        ),
        o_que_olhar="Vendas por canal, margem EBITDA e resultado financeiro no 2T26 contra o 2T25.",
        destaques=("vendas_lojas_fisicas", "vendas_ecommerce_total", "vendas_marketplace_3p",
                   "margem_ebitda", "lucro_liquido", "resultado_financeiro"),
        expectativas=(
            Expectativa("vendas_lojas_fisicas", "alta", modo="aa"),
            Expectativa("vendas_ecommerce_total", "queda", modo="aa"),
            Expectativa("vendas_marketplace_3p", "queda", modo="aa"),
            Expectativa("lucro_liquido", "queda", modo="aa"),
        ),
        fontes=(
            ("BPMoney — 2T26: prejuízo ajustado de R$ 50,4 mi, lojas +10,3%, e-commerce -11,9%",
             "https://bpmoney.com.br/negocios/empresas/magazine-luiza-prejuizo-50-milhoes-2t26/"),
            ("Money Times — prejuízo de R$ 72,5 mi no 2T26",
             "https://www.moneytimes.com.br/magazine-luiza-mglu3-tem-prejuizo-de-r-725-milhoes-no-2t26-estamos-fazendo-tudo-para-voltar-a-dar-lucro-sem-depender-dos-juros-diz-cfo-lmrs/"),
            ("Visão Invest — EBITDA ajustado e vendas por canal no 2T26",
             "https://visnoinvest.com.br/news/14628/magazine-luiza-mglu3-registra-ebitda-de-r-7088-mi-no-2t26"),
        ),
        status="verificado",
    ),
]

EVENTOS_POR_ID = {e.id: e for e in EVENTOS}


# ----------------------------------------------------------------------
# Eventos TÉCNICOS da ação (afetam a série de preços — não são narrativa).
# fator = preço_depois / preço_antes esperado no dia ex.
# ----------------------------------------------------------------------
EVENTOS_ACAO = [
    {"data": date(2019, 8, 5),  "fator": 1 / 8,  "descricao": "Desdobramento 1:8",
     "fonte": "https://www.suno.com.br/acoes/mglu3"},
    {"data": date(2020, 10, 14), "fator": 1 / 4, "descricao": "Desdobramento 1:4",
     "fonte": "https://trademap.com.br/agencia/mercados/blog-noticia-magazine-luiza-aprova-desdobramento-de-acoes-na-proporcao-de-1-para-4"},
    {"data": date(2024, 5, 27), "fator": 10.0,   "descricao": "Grupamento 10:1",
     "fonte": "https://www.moneytimes.com.br/magazine-luiza-mglu3-aprova-grupamento-de-acoes-na-proporcao-de-10-para-1/"},
]


# ----------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------
def black_fridays(ano_ini: int, ano_fim: int) -> List[date]:
    """Black Friday = sexta-feira seguinte ao Thanksgiving (4ª quinta de novembro)."""
    datas = []
    for ano in range(ano_ini, ano_fim + 1):
        d = date(ano, 11, 1)
        quintas = [d + timedelta(days=i) for i in range(30)
                   if (d + timedelta(days=i)).weekday() == 3 and (d + timedelta(days=i)).month == 11]
        datas.append(quintas[3] + timedelta(days=1))
    return datas


def eventos_no_intervalo(eventos, ano_ini: int, ano_fim: int):
    """Eventos que tocam o intervalo [ano_ini, ano_fim]."""
    ini, fim = date(ano_ini, 1, 1), date(ano_fim, 12, 31)
    saida = []
    for e in eventos:
        e_fim = e.data_fim or e.data_inicio
        if e.data_inicio <= fim and e_fim >= ini:
            saida.append(e)
    return saida


def rotulo_serie(chave: str) -> str:
    if chave in META_SERIES:
        return META_SERIES[chave][0]
    return chave


def unidade_serie(chave: str) -> str:
    if chave in META_SERIES:
        return META_SERIES[chave][1]
    return "num"


def tabela_eventos() -> pd.DataFrame:
    """Tabela de eventos para exibição."""
    linhas = []
    for e in sorted(EVENTOS, key=lambda x: x.data_inicio):
        linhas.append({
            "Data": e.data_exibicao,
            "Evento": e.nome,
            "Categoria": e.categoria,
            "Origem": e.origem.capitalize(),
            "Fonte": {"verificado": "✅ verificada",
                      "conhecimento_publico": "🟡 conferir fonte oficial",
                      "a_confirmar": "🔴 a confirmar"}[e.status],
        })
    return pd.DataFrame(linhas)
