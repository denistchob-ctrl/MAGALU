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

Estratégia de atualização
--------------------------
Anos passados são ESTÁTICOS: uma vez gravados no consolidado, não são
reconsultados. Apenas o ANO CORRENTE é reconsultado ao vivo a cada
execução (parâmetro `apenas_ano_corrente_ao_vivo`, padrão True). O
consolidado é salvo em <pasta_backup>/GA_porRegiao_ano_a_ano.csv e,
a partir dele, dois derivados são gerados automaticamente:

    - GA_porRegiao_agregada.csv          (Região, Quantidade) — soma de
                                          todos os anos por região.
    - GA_serie_temporal_anualizada.csv    (Ano, Quantidade) — soma por ano.

Esses derivados substituem o antigo 'ultimaLeituraGAporRegiao.csv' do
loader live, que era uma "foto" de um momento específico e ficava
inconsistente com o consolidado ano a ano.

Como usar
---------
    from magalu_google_trends_anual import GoogleTrendsPorRegiaoAnual

    ga = GoogleTrendsPorRegiaoAnual(ano_inicio=2021, ano_fim=2026)
    ga.df                          # DataFrame consolidado: Ano, Região, Quantidade
    ga.df_por_ano(2024)            # Series (índice = região) só do ano de 2024
    ga.matriz_ano_regiao()         # DataFrame pivotado: índice = Ano, colunas = Região
    ga.regiao_agregada()           # DataFrame Região, Quantidade (soma dos anos)
    ga.serie_temporal_anualizada() # DataFrame Ano, Quantidade (soma por ano)

Observações importantes
-----------------------
1. Cada ano é uma consulta INDEPENDENTE ao Google Trends. Os valores de
   cada ano são normalizados DENTRO daquele ano (0 a 100), então NÃO são
   diretamente comparáveis entre anos em termos absolutos — apenas a
   ORDEM/ranking das regiões dentro de cada ano é comparável. Isso é uma
   limitação da própria API do Google Trends, não do código.

2. Para reduzir o risco de bloqueio (HTTP 403/429), o script faz uma pausa
   entre as consultas (parâmetro `pausa_entre_anos`, padrão 30s).

3. Aproveita a infraestrutura de retentativas e backup do
   GoogleTrendsPyTrendsLoader: cada ano consultado com sucesso gera um
   backup próprio em disco (útil para retomar uma execução interrompida).
   Se a consulta de um ano falhar, o script tenta ler o backup daquele ano;
   se não houver backup, pula o ano e continua (não derruba a execução).
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
        pasta_backup: pasta onde salvar backups por ano, o consolidado e
            os derivados.
        pausa_entre_anos: segundos de espera entre uma consulta e outra
            (evita bloqueio por taxa de requisições).
        tentativas: repassado ao GoogleTrendsPyTrendsLoader (retentativas
            dentro de um mesmo ano).
        continuar_em_caso_de_falha: se True (padrão), pula o ano que falhar
            e segue para o próximo; se False, interrompe a execução.
        apenas_ano_corrente_ao_vivo: se True (padrão), apenas o ano corrente
            (ano_fim) é reconsultado ao vivo; os anos passados vêm do
            consolidado em disco. Se False, todos os anos do intervalo são
            reconsultados (útil para reconstruir o consolidado do zero).

    Resultado:
        self.df -> DataFrame com colunas ['Ano', 'Região', 'Quantidade'],
            uma linha por ano/região. Ordenado por Ano e Região.
    """

    def __init__(self, ano_inicio=2004, ano_fim=None,
                 termos=("Magazine Luiza",), geo="BR",
                 pasta_backup=PASTA_DADOS_PADRAO,
                 pausa_entre_anos=30, tentativas=3,
                 continuar_em_caso_de_falha=True,
                 apenas_ano_corrente_ao_vivo=True,
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
        self.apenas_ano_corrente_ao_vivo = apenas_ano_corrente_ao_vivo
        self.nome_arquivo_consolidado = nome_arquivo_consolidado

        # DataFrame consolidado final
        self.df = pd.DataFrame(columns=["Ano", "Região", "Quantidade"])

        self._executar()

    # ------------------------------------------------------------------
    # Execução principal
    # ------------------------------------------------------------------
    def _executar(self):
        """
        Estratégia:
          1. Carrega o consolidado existente (se houver) — anos passados são
             considerados ESTÁTICOS e não são reconsultados.
          2. Faz consulta ao vivo apenas para o ano corrente (ano_fim), que
             ainda pode mudar.
          3. Junta tudo, ordena e regrava o consolidado + derivados.
        """
        os.makedirs(self.pasta_backup, exist_ok=True)

        # 1) Carrega o que já existe em disco
        self.df = self._carregar_consolidado_existente()
        anos_ja_presentes = (
            set(self.df["Ano"].unique().tolist()) if not self.df.empty else set()
        )

        # 2) Define quais anos vão à API ao vivo
        if self.apenas_ano_corrente_ao_vivo:
            anos_a_consultar = [self.ano_fim]
        else:
            anos_a_consultar = list(range(self.ano_inicio, self.ano_fim + 1))

        # Remove do consolidado os anos que serão reconsultados (para não duplicar)
        if anos_a_consultar:
            self.df = (
                self.df[~self.df["Ano"].isin(anos_a_consultar)]
                .reset_index(drop=True)
            )

        total = len(anos_a_consultar)
        resultados = []

        for i, ano in enumerate(anos_a_consultar, start=1):
            # Se não é o modo "ano corrente" e o ano já está no consolidado,
            # nem consulta (preserva o dado estático).
            if (not self.apenas_ano_corrente_ao_vivo) and ano in anos_ja_presentes \
                    and ano != self.ano_fim:
                print(f"[GoogleTrendsPorRegiaoAnual] ({i}/{total}) Ano {ano} "
                      f"já está no consolidado — pulando consulta ao vivo.")
                continue

            print(f"\n[GoogleTrendsPorRegiaoAnual] ({i}/{total}) Consultando "
                  f"ano {ano}...")
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

            if i < total and self.pausa_entre_anos > 0:
                print(f"[GoogleTrendsPorRegiaoAnual] Aguardando "
                      f"{self.pausa_entre_anos}s antes do próximo ano...")
                time.sleep(self.pausa_entre_anos)

        # 3) Junta tudo
        if resultados:
            self.df = (
                pd.concat([self.df] + resultados, ignore_index=True)
                .drop_duplicates(subset=["Ano", "Região"], keep="last")
                .sort_values(["Ano", "Região"])
                .reset_index(drop=True)
            )
            self._salvar_consolidado()
        else:
            if self.df.empty:
                print("[GoogleTrendsPorRegiaoAnual] Nenhum dado novo foi obtido "
                      "e não havia consolidado em disco. O DataFrame ficará vazio.")
            else:
                print(f"[GoogleTrendsPorRegiaoAnual] Nenhuma consulta ao vivo "
                      f"necessária — usando o consolidado existente "
                      f"({len(self.df)} linhas).")

    def _carregar_consolidado_existente(self):
        """Lê o CSV consolidado (GA_porRegiao_ano_a_ano.csv), se existir."""
        caminho = os.path.join(self.pasta_backup, self.nome_arquivo_consolidado)
        if not os.path.exists(caminho):
            return pd.DataFrame(columns=["Ano", "Região", "Quantidade"])
        try:
            df = pd.read_csv(caminho, encoding="utf-8")
            df["Ano"] = df["Ano"].astype(int)
            df["Quantidade"] = pd.to_numeric(df["Quantidade"], errors="coerce")
            df = df.dropna(subset=["Ano", "Região", "Quantidade"])
            print(f"[GoogleTrendsPorRegiaoAnual] Consolidado existente carregado: "
                  f"'{caminho}' ({len(df)} linhas, anos "
                  f"{sorted(df['Ano'].unique().tolist())}).")
            return df
        except Exception as erro:
            print(f"[GoogleTrendsPorRegiaoAnual] Aviso: falha ao ler o "
                  f"consolidado '{caminho}' ({erro}). Ignorando.")
            return pd.DataFrame(columns=["Ano", "Região", "Quantidade"])

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

        # Grava também os derivados (região agregada e série anualizada)
        self._salvar_derivados()

    def _salvar_derivados(self):
        """
        Grava os derivados do consolidado em disco:
          - GA_porRegiao_agregada.csv        (Região, Quantidade)
          - GA_serie_temporal_anualizada.csv (Ano, Quantidade)
        Esses arquivos são a NOVA fonte para o repositório/dashboards —
        em vez de ler o antigo 'ultimaLeituraGAporRegiao.csv', que era
        uma foto de um momento diferente.
        """
        try:
            caminho_regiao = os.path.join(self.pasta_backup,
                                          "GA_porRegiao_agregada.csv")
            self.regiao_agregada().to_csv(caminho_regiao, index=False,
                                          encoding="utf-8")

            caminho_anual = os.path.join(self.pasta_backup,
                                         "GA_serie_temporal_anualizada.csv")
            self.serie_temporal_anualizada().to_csv(caminho_anual, index=False,
                                                    encoding="utf-8")

            print(f"[GoogleTrendsPorRegiaoAnual] Derivados salvos: "
                  f"'{caminho_regiao}' e '{caminho_anual}'.")
        except OSError as erro:
            print(f"[GoogleTrendsPorRegiaoAnual] Aviso: falha ao salvar "
                  f"derivados ({erro}).")

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

    def regiao_agregada(self, como="soma"):
        """
        Devolve um DataFrame ['Região', 'Quantidade'] agregando TODOS os anos
        do consolidado, para substituir o antigo arquivo
        'ultimaLeituraGAporRegiao.csv' (que era uma foto de um momento
        específico e ficava inconsistente com o consolidado ano a ano).

        Parâmetro 'como':
            'soma'  -> soma das quantidades de todos os anos (padrão).
            'media' -> média das quantidades entre os anos disponíveis.

        Observação: como cada ano é normalizado pelo Google dentro do próprio
        ano (0–100), a soma/média entre anos NÃO tem significado absoluto —
        serve apenas como um ranking relativo de regiões. Para análise séria,
        prefira o consolidado ano a ano.
        """
        if self.df.empty:
            return pd.DataFrame(columns=["Região", "Quantidade"])

        if como == "soma":
            agg = self.df.groupby("Região", as_index=False)["Quantidade"].sum()
        elif como == "media":
            agg = self.df.groupby("Região", as_index=False)["Quantidade"].mean()
        else:
            raise ValueError(f"'como' deve ser 'soma' ou 'media'; recebi '{como}'.")

        return agg.sort_values("Região").reset_index(drop=True)

    def serie_temporal_anualizada(self):
        """
        Devolve um DataFrame ['Ano', 'Quantidade'] com a soma das quantidades
        por ano, útil para gráficos anuais (barras por ano).
        """
        if self.df.empty:
            return pd.DataFrame(columns=["Ano", "Quantidade"])
        agg = self.df.groupby("Ano", as_index=False)["Quantidade"].sum()
        return agg.sort_values("Ano").reset_index(drop=True)

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
    ga = GoogleTrendsPorRegiaoAnual(ano_inicio=2021, ano_fim=2026)

    print("\nAnos disponíveis:", ga.anos_disponiveis())
    print("Regiões disponíveis:", ga.regioes_disponiveis())

    print("\nPrimeiras linhas do consolidado:")
    print(ga.df.head(10))

    print("\nInteresse por região em 2024:")
    print(ga.df_por_ano(2024).sort_values(ascending=False).head(10))

    print("\nRegião agregada (soma de todos os anos):")
    print(ga.regiao_agregada().sort_values("Quantidade", ascending=False).head(10))

    print("\nSérie anualizada (soma por ano):")
    print(ga.serie_temporal_anualizada())