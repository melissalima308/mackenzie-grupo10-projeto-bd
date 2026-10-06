"""
Formatacao numerica no padrao brasileiro.

O Python formata numeros no padrao norte-americano: 1,234.56. Como o
trabalho e escrito em portugues e as conclusoes sao coladas direto no
relatorio e no dashboard, todo numero que aparece em texto passa por aqui.
"""

from __future__ import annotations


def numero(valor: float, casas: int = 0) -> str:
    """1234567.8 -> '1.234.568'  |  numero(1234.5, 2) -> '1.234,50'"""
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def moeda(valor: float) -> str:
    """1258681.34 -> 'R$ 1.258.681,34'"""
    return "R$ " + numero(valor, 2)


def decimal(valor: float, casas: int = 2) -> str:
    """4.29 -> '4,29'. Para valores pequenos, sem separador de milhar."""
    return f"{valor:.{casas}f}".replace(".", ",")


def percentual(valor: float, casas: int = 2) -> str:
    """8.11 -> '8,11%'"""
    return decimal(valor, casas) + "%"
