"""
magalu_google_trends_anual.py
===============================
Módulo COMPLEMENTAR ao magalu_google_trends_live.py.

Motivação
---------
A consulta padrão de "interesse por região" do Google Trends
(interest_by_region) NÃO aceita granularidade temporal: ela sempre devolve
um único valor agregado por região para TODO o período consultado
(timeframe). Isso significa que, ao usar timeframe="all", você obtém o
interesse médio de cada estado entre 2004 e hoje — sem saber como esse
interesse evoluiu ano a ano.

Este módulo resolve essa limitação fazendo UMA CONSULTA POR ANO e
consolidando os resultados em uma única tabela com colunas:

    Ano | Região | Quantidade

Assim é possível plotar, por exemplo:
    - a evolução do interesse em São Paulo ao longo dos anos;
    - um heatmap Ano x Região;
    - comparações regionais dentro de um mesmo ano.

Como usar
---------
    from magalu_google_trends_anual import GoogleTrendsPorRegiaoAnual

    ga = GoogleTrendsPorRegiaoAnual(ano_inicio=2015, ano_fim=2026)
    ga.df                 # DataFrame consolidado: Ano, Região, Quantidade
    ga.df_por_ano(2024)   # Series (índice = região) só do ano de 2024
    ga.matriz_ano_regiao()# DataFrame pivotado: índice = Ano, colunas = Região

Observações importantes
-----------------------
1. Cada ano é uma consulta INDEPENDENTE ao Google Trends. Os valores de
   cada ano são normalizados DENTRO daquele ano (0 a 100), então NÃO são
   diretamente comparáveis entre anos em termos absolutos — apenas a
   ORDEM/ranking das regiões dentro de cada ano é comparável. Isso é uma
   limitação da própria API do Google Trends, não do código.

2. Para reduzir o risco de bloqueio (HTTP 403/429), o script faz uma pausa
   entre as consultas (parâmetro `pausa_entre_anos`, padrão 15s).

3. Aproveita a infraestrutura de retentativas e backup do
   GoogleTrendsPyTrendsLoader: cada ano consultado com sucesso gera um
   backup próprio em disco (útil para retomar uma execução interrompida).
   Se a consulta de um ano falhar, o script tenta ler o backup daquele ano;
   se não houver backup, pula o ano e continua (não derruba a execução).

4. O resultado consolidado também é salvo em CSV em
   <pasta_backup>/GA_porRegiao_ano_a_ano.csv — pronto para ser carregado
   pelo restante do projeto (dashboards, notebooks, etc.).

Exemplo de integração com o main.py
------------------------------------
    from magalu_google_trends_anual import GoogleTrendsPorRegiaoAnual

    ga_anual = GoogleTrendsPorRegiaoAnual(ano_inicio=2015, ano_fim=2026)
    ga_anual.df                      # DataFrame consolidado
    ga_anual.matriz_ano_regiao()     # pivot Ano x Região
    ga_anual.df_por_ano(2024)        # Series de um ano específico
"""

import os
import time

import pandas as pd

from magalu_google_trends_live import (
    GoogleTrendsPyTrendsLoader,
    PASTA_DADOS_PADRAO,
)


class GoogleTrendsPorRegiaoAnual:
    """
    Consulta o Google Trends ano a ano para obter o interesse por região
    quebrado por ano, algo que a consulta padrão (interest_by_region com
    timeframe='all') não oferece.

    Parâmetros principais:
        ano_inicio, ano_fim: intervalo de anos a consultar (inclusive).
        termos: lista de palavras-chave (padrão: 'Magazine Luiza').
        geo: código do país/região (padrão 'BR').
        pasta_backup: pasta onde salvar backups por ano e o CSV consolidado.
        pausa_entre_anos: segundos de espera entre uma consulta e outra
            (evita bloqueio por taxa de requisições).
        tentativas: repassado ao GoogleTrendsPyTrendsLoader (retentativas
            dentro de um mesmo ano).
        continuar_em_caso_de_falha: se True (padrão), pula o ano que falhar
            e segue para o próximo; se False, interrompe a execução.

    Resultado:
        self.df -> DataFrame com colunas ['Ano', 'Região', 'Quantidade'],
            uma linha por ano/região. Ordenado por Ano e Região.
    """

    def __init__(self, ano_inicio=2004, ano_fim=None,
                 termos=("Magazine Luiza",), geo="BR",
                 pasta_backup=PASTA_DADOS_PADRAO,
                 pausa_entre_anos=30, tentativas=3,
                 continuar_em_caso_de_falha=True,
                 nome_arquivo_consolidado="GA_porRegiao_ano_a_ano.csv"):

        if ano_fim is None:
            ano_fim = pd.Timestamp.today().year

        if ano_inicio > ano_fim:
            raise ValueError(
                f"ano_inicio ({ano_inicio}) não pode ser maior que "
                f"ano_fim ({ano_fim})."
            )

        self.ano_inicio = ano_inicio
        self.ano_fim = ano_fim
        self.termos = list(termos)
        self.geo = geo
        self.pasta_backup = pasta_backup
        self.pausa_entre_anos = pausa_entre_anos
        self.tentativas = tentativas
        self.continuar_em_caso_de_falha = continuar_em_caso_de_falha
        self.nome_arquivo_consolidado = nome_arquivo_consolidado

        # DataFrame consolidado final
        self.df = pd.DataFrame(columns=["Ano", "Região", "Quantidade"])

        self._executar()

    # ------------------------------------------------------------------
    # Execução principal
    # ------------------------------------------------------------------
    def _executar(self):
        """Percorre o intervalo de anos, consulta cada um e consolida."""
        os.makedirs(self.pasta_backup, exist_ok=True)

        anos = list(range(self.ano_inicio, self.ano_fim + 1))
        total = len(anos)
        resultados = []

        for i, ano in enumerate(anos, start=1):
            print(f"\n[GoogleTrendsPorRegiaoAnual] ({i}/{total}) Consultando ano {ano}...")

            df_ano = self._consultar_ano(ano)

            if df_ano is not None and not df_ano.empty:
                resultados.append(df_ano)
            else:
                print(f"[GoogleTrendsPorRegiaoAnual] Ano {ano} sem dados "
                      f"(consulta falhou e não havia backup).")
                if not self.continuar_em_caso_de_falha:
                    raise RuntimeError(
                        f"Consulta ao Google Trends falhou para o ano {ano} e "
                        f"'continuar_em_caso_de_falha=False'. Interrompendo."
                    )

            # Pausa entre anos (menos no último, para não atrasar o término)
            if i < total:
                print(f"[GoogleTrendsPorRegiaoAnual] Aguardando "
                      f"{self.pausa_entre_anos}s antes do próximo ano...")
                time.sleep(self.pausa_entre_anos)

        if resultados:
            self.df = (
                pd.concat(resultados, ignore_index=True)
                .sort_values(["Ano", "Região"])
                .reset_index(drop=True)
            )
            self._salvar_consolidado()
        else:
            print("[GoogleTrendsPorRegiaoAnual] Nenhum dado foi obtido em "
                  "nenhum ano. O DataFrame consolidado ficará vazio.")

    def _consultar_ano(self, ano):
        """Consulta um único ano e devolve um DataFrame ['Ano', 'Região',
        'Quantidade'], ou None se a consulta falhar sem backup disponível."""
        timeframe = f"{ano}-01-01 {ano}-12-31"

        try:
            loader = GoogleTrendsPyTrendsLoader(
                termos=self.termos,
                geo=self.geo,
                timeframe=timeframe,
                tentativas=self.tentativas,
                pasta_backup=self.pasta_backup,
                nome_backup_temporal=f"GA_{ano}.csv",
                nome_backup_regional=f"GA_{ano}_porRegiao.csv",
            )
        except RuntimeError as erro:
            print(f"[GoogleTrendsPorRegiaoAnual] Falha no ano {ano}: {erro}")
            return None

        if loader.usando_backup:
            print(f"[GoogleTrendsPorRegiaoAnual] Ano {ano} veio do BACKUP "
                  f"(consulta ao vivo falhou).")

        df = loader.por_regiao.copy()
        if df.empty:
            return None

        df.insert(0, "Ano", ano)
        # Garante a ordem das colunas
        df = df[["Ano", "Região", "Quantidade"]]
        return df

    # ------------------------------------------------------------------
    # Persistência
    # ------------------------------------------------------------------
    def _salvar_consolidado(self):
        caminho = os.path.join(self.pasta_backup, self.nome_arquivo_consolidado)
        try:
            self.df.to_csv(caminho, index=False, encoding="utf-8")
            print(f"\n[GoogleTrendsPorRegiaoAnual] Consolidado salvo em "
                  f"'{caminho}' ({len(self.df)} linhas).")
        except OSError as erro:
            print(f"[GoogleTrendsPorRegiaoAnual] Aviso: não foi possível "
                  f"salvar o consolidado ({erro}).")

    # ------------------------------------------------------------------
    # Consulta / visualização
    # ------------------------------------------------------------------
    def df_por_ano(self, ano):
        """Devolve uma Series (índice = Região) só do ano pedido."""
        df_ano = self.df[self.df["Ano"] == ano]
        if df_ano.empty:
            raise ValueError(f"Nenhum dado disponível para o ano {ano}.")
        return df_ano.set_index("Região")["Quantidade"]

    def matriz_ano_regiao(self):
        """Devolve um DataFrame pivotado: índice = Ano, colunas = Região,
        valores = Quantidade. Útil para heatmaps."""
        if self.df.empty:
            raise ValueError("Nenhum dado consolidado disponível.")
        return self.df.pivot(index="Ano", columns="Região", values="Quantidade")

    def anos_disponiveis(self):
        """Lista os anos presentes no DataFrame consolidado."""
        return sorted(self.df["Ano"].unique().tolist())

    def regioes_disponiveis(self):
        """Lista as regiões presentes no DataFrame consolidado."""
        return sorted(self.df["Região"].unique().tolist())


# ----------------------------------------------------------------------
# Execução direta: demonstração
# ----------------------------------------------------------------------
if __name__ == "__main__":
    # Consulta de 2015 a 2026 (ajuste conforme necessário)
    ga = GoogleTrendsPorRegiaoAnual(ano_inicio=2021, ano_fim=2026)

    print("\nAnos disponíveis:", ga.anos_disponiveis())
    print("Regiões disponíveis:", ga.regioes_disponiveis())

    print("\nPrimeiras linhas do consolidado:")
    print(ga.df.head(10))

    print("\nInteresse por região em 2024:")
    print(ga.df_por_ano(2024).sort_values(ascending=False).head(10))

    print("\nMatriz Ano x Região (primeiras colunas):")
    print(ga.matriz_ano_regiao().iloc[:, :5])