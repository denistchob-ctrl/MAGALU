"""
formatos.py
============
Formatação pt-BR de valores monetários, percentuais e datas.
"""

def formata_moeda(valor, casas=1):
    """Formata valor em R$ com sufixo mi/bi, conforme a escala.
    Ex.: 1_200_000 -> 'R$ 1,2 mi'; 3_500_000_000 -> 'R$ 3,5 bi'."""
    if valor is None or (isinstance(valor, float) and valor != valor):
        return "—"
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return "—"

    abs_v = abs(v)
    if abs_v >= 1_000_000_000:
        return f"R$ {v / 1_000_000_000:,.{casas}f} bi".replace(",", "X").replace(".", ",").replace("X", ".")
    if abs_v >= 1_000_000:
        return f"R$ {v / 1_000_000:,.{casas}f} mi".replace(",", "X").replace(".", ",").replace("X", ".")
    if abs_v >= 1_000:
        return f"R$ {v / 1_000:,.{casas}f} mil".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def formata_pct(valor, casas=1, ja_e_fracao=True):
    """Formata percentual. Se ja_e_fracao=True, multiplica por 100.
    Ex.: 0.124 -> '12,4%'."""
    if valor is None or (isinstance(valor, float) and valor != valor):
        return "—"
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return "—"
    if ja_e_fracao:
        v *= 100
    return f"{v:,.{casas}f}%".replace(",", "X").replace(".", ",").replace("X", ".")


def formata_variacao(valor):
    """Formata variação com sinal. Ex.: 0.124 -> '+12,4%'."""
    if valor is None or (isinstance(valor, float) and valor != valor):
        return "—"
    try:
        v = float(valor) * 100
    except (TypeError, ValueError):
        return "—"
    sinal = "+" if v > 0 else ""
    return f"{sinal}{v:,.1f}%".replace(",", "X").replace(".", ",").replace("X", ".")


def formata_numero(valor, casas=0):
    """Formata número com separador de milhar pt-BR."""
    if valor is None or (isinstance(valor, float) and valor != valor):
        return "—"
    try:
        return f"{float(valor):,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "—"


def formata_data(data, formato="%d/%m/%Y"):
    """Formata data como pt-BR."""
    if data is None:
        return "—"
    try:
        return data.strftime(formato)
    except AttributeError:
        return str(data)