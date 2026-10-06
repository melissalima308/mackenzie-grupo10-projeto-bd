"""
Funcoes padronizadas de grafico, em matplotlib.

Estas figuras sao as que entram no relatorio escrito, em PNG. Os graficos
interativos do dashboard sao gerados separadamente, em dashboard.py.

Manter a geracao de figura isolada aqui evita que cada analise invente seu
proprio estilo e garante que as oito figuras do trabalho saiam com a mesma
paleta, o mesmo tamanho de fonte e o mesmo tratamento de grade.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # backend sem janela, obrigatorio para rodar em script
import matplotlib.pyplot as plt

from . import config

ESTILO = {
    "figure.facecolor": config.CORES["fundo"],
    "axes.facecolor": config.CORES["fundo"],
    "axes.edgecolor": config.CORES["grade"],
    "axes.labelcolor": config.CORES["texto"],
    "axes.titlesize": 12,
    "axes.titleweight": "bold",
    "axes.labelsize": 10,
    "axes.grid": True,
    "grid.color": config.CORES["grade"],
    "grid.linewidth": 0.8,
    "text.color": config.CORES["texto"],
    "xtick.color": config.CORES["texto"],
    "ytick.color": config.CORES["texto"],
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.frameon": False,
    "legend.fontsize": 9,
    "font.size": 10,
}


def aplicar_estilo() -> None:
    """Aplica o estilo do projeto ao matplotlib. Chamar uma vez no inicio."""
    plt.rcParams.update(ESTILO)


def _remover_bordas(eixo) -> None:
    for lado in ("top", "right"):
        eixo.spines[lado].set_visible(False)


def nova_figura(largura: float = 9, altura: float = 4.5):
    figura, eixo = plt.subplots(figsize=(largura, altura))
    _remover_bordas(eixo)
    eixo.set_axisbelow(True)
    return figura, eixo


def salvar(nome_arquivo: str, pasta: Path | None = None) -> Path:
    """Salva a figura corrente e fecha, devolvendo o caminho gerado."""
    pasta = Path(pasta) if pasta is not None else config.PASTA_FIGURAS
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / nome_arquivo
    plt.tight_layout()
    plt.savefig(caminho, dpi=config.DPI_FIGURA, bbox_inches="tight")
    plt.close()
    return caminho


# ----------------------------------------------------------------------
# Graficos de uso geral
# ----------------------------------------------------------------------
def linha(x, y, titulo: str, rotulo_y: str, rotulo_x: str = "", marcador: str = "o"):
    figura, eixo = nova_figura(11, 4.5)
    eixo.plot(x, y, marker=marcador, color=config.CORES["primaria"], linewidth=2, markersize=4)
    eixo.set_title(titulo)
    eixo.set_ylabel(rotulo_y)
    if rotulo_x:
        eixo.set_xlabel(rotulo_x)
    eixo.tick_params(axis="x", rotation=90)
    eixo.grid(axis="x", visible=False)
    return figura, eixo


def barras(
    categorias,
    valores,
    titulo: str,
    rotulo_y: str,
    cor: str | list | None = None,
    rotacao: int = 0,
    formato_rotulo: str | None = None,
):
    figura, eixo = nova_figura(8, 4.5)
    barras_ = eixo.bar(
        [str(c) for c in categorias],
        valores,
        color=cor or config.CORES["primaria"],
        width=0.65,
    )
    eixo.set_title(titulo)
    eixo.set_ylabel(rotulo_y)
    eixo.tick_params(axis="x", rotation=rotacao)
    eixo.grid(axis="x", visible=False)

    if formato_rotulo:
        for barra, valor in zip(barras_, valores):
            eixo.annotate(
                formato_rotulo.format(valor),
                (barra.get_x() + barra.get_width() / 2, barra.get_height()),
                ha="center",
                va="bottom",
                fontsize=9,
                xytext=(0, 2),
                textcoords="offset points",
            )
    return figura, eixo


def barras_horizontais(categorias, valores, titulo: str, rotulo_x: str):
    figura, eixo = nova_figura(8.5, 5)
    eixo.barh([str(c) for c in categorias], valores, color=config.CORES["primaria"], height=0.65)
    eixo.set_title(titulo)
    eixo.set_xlabel(rotulo_x)
    eixo.grid(axis="y", visible=False)
    return figura, eixo


def barras_agrupadas(
    categorias,
    series: dict[str, list],
    titulo: str,
    rotulo_y: str,
):
    figura, eixo = nova_figura(10, 4.5)
    quantidade = len(series)
    largura = 0.8 / quantidade
    posicoes = range(len(categorias))

    for indice, (nome, valores) in enumerate(series.items()):
        deslocamento = (indice - (quantidade - 1) / 2) * largura
        eixo.bar(
            [p + deslocamento for p in posicoes],
            valores,
            width=largura,
            label=nome,
            color=config.SEQUENCIA_CORES[indice % len(config.SEQUENCIA_CORES)],
        )

    eixo.set_xticks(list(posicoes))
    eixo.set_xticklabels([str(c) for c in categorias])
    eixo.set_title(titulo)
    eixo.set_ylabel(rotulo_y)
    eixo.legend()
    eixo.grid(axis="x", visible=False)
    return figura, eixo


def histograma(valores, titulo: str, rotulo_x: str, rotulo_y: str, bins: int = 40):
    figura, eixo = nova_figura(8, 4.5)
    eixo.hist(valores, bins=bins, color=config.CORES["primaria"], edgecolor="white", linewidth=0.5)
    eixo.set_title(titulo)
    eixo.set_xlabel(rotulo_x)
    eixo.set_ylabel(rotulo_y)
    eixo.grid(axis="x", visible=False)
    return figura, eixo
