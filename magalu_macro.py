"""
magalu_macro.py
================
Camada macroeconômica do modelo v3: Selic (meta definida pelo Copom).

Estratégia de carga (mesma filosofia dos loaders de Google Trends do projeto —
nunca derruba o app):

  1. AO VIVO: API pública do Banco Central (SGS, série 432 — Meta Selic).
     Se funcionar, grava um backup em BD/Selic_BCB_backup.csv.
  2. BACKUP LOCAL: lê BD/Selic_BCB_backup.csv (última carga bem-sucedida).
  3. TABELA EMBUTIDA: valores de referência de fim de trimestre (abaixo),
     usados só se 1 e 2 falharem. CONFIRA com a série oficial do BCB antes
     de apresentar — o atributo `fonte` informa de onde vieram os dados e a
     página v3 exibe isso de forma transparente.

Uso:
    selic = SelicLoader()
    selic.fonte            # 'BCB (ao vivo)' | 'Backup local' | 'Tabela embutida'
    selic.serie_diaria     # Series (% a.a.) indexada por data
    selic.trimestral()     # Series (fração, ex.: 0.1375) indexada por pd.Period('2023Q3')
"""

import json
import os
import urllib.request
from datetime import date

import pandas as pd

PASTA_DADOS_PADRAO = "BD"
NOME_BACKUP = "Selic_BCB_backup.csv"

URL_BCB = ("https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados"
           "?formato=json&dataInicial={ini}&dataFinal={fim}")

# Meta Selic (% a.a.) vigente ao FIM de cada trimestre — referência embutida.
# Fontes: calendário de decisões do Copom (BCB). Para 2026, conforme noticiado
# (15,00% → 14,75% em 18/03 → 14,25% em 17/06 → 13,75% em 16/09/2026).
SELIC_FIM_TRIMESTRE = {
    (2018, 1): 6.50, (2018, 2): 6.50, (2018, 3): 6.50, (2018, 4): 6.50,
    (2019, 1): 6.50, (2019, 2): 6.50, (2019, 3): 5.50, (2019, 4): 4.50,
    (2020, 1): 3.75, (2020, 2): 2.25, (2020, 3): 2.00, (2020, 4): 2.00,
    (2021, 1): 2.75, (2021, 2): 4.25, (2021, 3): 6.25, (2021, 4): 9.25,
    (2022, 1): 11.75, (2022, 2): 13.25, (2022, 3): 13.75, (2022, 4): 13.75,
    (2023, 1): 13.75, (2023, 2): 13.75, (2023, 3): 12.75, (2023, 4): 11.75,
    (2024, 1): 10.75, (2024, 2): 10.50, (2024, 3): 10.75, (2024, 4): 12.25,
    (2025, 1): 14.25, (2025, 2): 15.00, (2025, 3): 15.00, (2025, 4): 15.00,
    (2026, 1): 14.75, (2026, 2): 14.25, (2026, 3): 13.75,
}


class SelicLoader:
    def __init__(self, pasta_dados=PASTA_DADOS_PADRAO, usar_ao_vivo=True, ano_inicial=2018):
        self.pasta_dados = pasta_dados
        self.ano_inicial = ano_inicial
        self.caminho_backup = os.path.join(pasta_dados, NOME_BACKUP)
        self.serie_diaria = pd.Series(dtype=float)
        self.fonte = ""
        self.erros = []
        self._carregar(usar_ao_vivo)

    # ------------------------------------------------------------------
    def _carregar(self, usar_ao_vivo):
        if usar_ao_vivo and self._tentar_bcb():
            return
        if self._tentar_backup():
            return
        self._usar_tabela_embutida()

    def _tentar_bcb(self):
        try:
            hoje = date.today()
            url = URL_BCB.format(ini=f"01/01/{self.ano_inicial}", fim=hoje.strftime("%d/%m/%Y"))
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                dados = json.loads(resp.read().decode("utf-8"))
            if not dados:
                raise ValueError("Resposta vazia do BCB.")
            df = pd.DataFrame(dados)
            df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y")
            df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
            serie = df.dropna().set_index("data")["valor"].sort_index()
            if serie.empty:
                raise ValueError("Série do BCB sem valores numéricos.")
            self.serie_diaria = serie
            self.fonte = "BCB (ao vivo)"
            try:
                os.makedirs(self.pasta_dados, exist_ok=True)
                serie.rename("valor").to_csv(self.caminho_backup, index_label="data")
            except OSError as e:
                self.erros.append(f"Não foi possível gravar o backup da Selic: {e}")
            return True
        except Exception as e:  # noqa: BLE001 — qualquer falha cai no próximo nível
            self.erros.append(f"BCB indisponível: {e}")
            return False

    def _tentar_backup(self):
        try:
            if not os.path.exists(self.caminho_backup):
                return False
            df = pd.read_csv(self.caminho_backup, parse_dates=["data"])
            serie = df.set_index("data")["valor"].astype(float).sort_index()
            if serie.empty:
                return False
            self.serie_diaria = serie
            self.fonte = "Backup local (última carga do BCB)"
            return True
        except Exception as e:  # noqa: BLE001
            self.erros.append(f"Backup da Selic ilegível: {e}")
            return False

    def _usar_tabela_embutida(self):
        pontos = {}
        for (ano, tri), valor in SELIC_FIM_TRIMESTRE.items():
            fim = pd.Period(f"{ano}Q{tri}").end_time.normalize()
            pontos[fim] = valor
        self.serie_diaria = pd.Series(pontos).sort_index()
        self.fonte = "Tabela embutida (conferir com o BCB antes de apresentar)"

    # ------------------------------------------------------------------
    def trimestral(self):
        """Selic de FIM de trimestre, como fração (0.1375), indexada por Period('Q')."""
        if self.serie_diaria.empty:
            return pd.Series(dtype=float)
        s = self.serie_diaria.copy()
        s.index = s.index.to_period("Q")
        s = s.groupby(level=0).last() / 100.0
        return s
