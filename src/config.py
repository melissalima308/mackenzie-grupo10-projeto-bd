"""
Configuracao central do projeto.

Projeto Aplicado 1 - Grupo 10 - Universidade Presbiteriana Mackenzie
Dataset: Brazilian E-Commerce Public Dataset by Olist (Kaggle, CC BY-NC-SA 4.0)

Todos os caminhos e parametros de analise ficam aqui. Nenhum outro modulo
deve conter caminho de arquivo escrito na mao.
"""

from __future__ import annotations

import os
from pathlib import Path

# ----------------------------------------------------------------------
# Caminhos
# ----------------------------------------------------------------------
# Raiz do projeto (a pasta que contem src/, dados/, saida/).
RAIZ = Path(__file__).resolve().parent.parent

# A pasta de dados pode ser sobrescrita pela variavel de ambiente
# OLIST_DADOS, o que facilita rodar o pipeline apontando para outro lugar
# sem alterar o codigo.
PASTA_DADOS = Path(os.environ.get("OLIST_DADOS", RAIZ / "dados"))

PASTA_SAIDA = Path(os.environ.get("OLIST_SAIDA", RAIZ / "saida"))
PASTA_FIGURAS = PASTA_SAIDA / "figuras"
PASTA_TABELAS = PASTA_SAIDA / "tabelas"
PASTA_CONSULTAS = RAIZ / "consultas"

CAMINHO_BANCO = PASTA_SAIDA / "olist.db"
CAMINHO_DASHBOARD = PASTA_SAIDA / "dashboard.html"

# O GitHub Pages publica a pasta docs/ da branch principal. Uma copia do
# dashboard e gravada em docs/index.html para que a URL publicada fique na
# raiz do site, sem caminho de arquivo.
PASTA_DOCS = RAIZ / "docs"
CAMINHO_PAGES = PASTA_DOCS / "index.html"

# ----------------------------------------------------------------------
# Arquivos do dataset
# ----------------------------------------------------------------------
ARQUIVOS = {
    "orders": "olist_orders_dataset.csv",
    "items": "olist_order_items_dataset.csv",
    "payments": "olist_order_payments_dataset.csv",
    "reviews": "olist_order_reviews_dataset.csv",
    "customers": "olist_customers_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "products": "olist_products_dataset.csv",
    "geolocation": "olist_geolocation_dataset.csv",
    "translation": "product_category_name_translation.csv",
}

# Colunas de data por tabela, convertidas na carga.
COLUNAS_DATA = {
    "orders": [
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ],
    "items": ["shipping_limit_date"],
    "reviews": ["review_creation_date", "review_answer_timestamp"],
}

# ----------------------------------------------------------------------
# Parametros de analise
# ----------------------------------------------------------------------
# Criterio de atraso adotado no trabalho.
#
# "timestamp" -> compara data e hora completas. Como
#                order_estimated_delivery_date vem sempre com hora 00:00:00,
#                qualquer entrega feita no proprio dia estimado, depois da
#                meia-noite, entra como atrasada. Resulta em 8,11% de
#                entregas atrasadas. E o criterio adotado no relatorio.
# "dia"       -> compara apenas a data de calendario. Resulta em 6,77%.
#
# A diferenca entre os dois e de 1.292 pedidos. Trocar o valor abaixo refaz
# todo o pipeline com o outro criterio, inclusive as faixas da hipotese H1.
CRITERIO_ATRASO = "timestamp"

# Rotulos usados nos textos gerados automaticamente.
NOMES_CRITERIO = {
    "timestamp": "comparação por data e hora",
    "dia": "comparação por dia de calendário",
}


def criterio_alternativo(criterio: str | None = None) -> str:
    """Devolve o criterio que nao foi adotado, usado na analise de sensibilidade."""
    atual = criterio or CRITERIO_ATRASO
    return "dia" if atual == "timestamp" else "timestamp"

# Faixas de atraso usadas na hipotese H1. O limite superior e inclusivo.
FAIXAS_ATRASO = [
    ("No prazo", -10**6, 0),
    ("1 a 3 dias", 1, 3),
    ("4 a 7 dias", 4, 7),
    ("8 a 14 dias", 8, 14),
    ("Mais de 14 dias", 15, 10**6),
]
ORDEM_FAIXAS = [nome for nome, _, _ in FAIXAS_ATRASO]

# Minimo de pedidos para uma categoria entrar nas comparacoes de nota media
# da hipotese H2. Evita que categoria com 3 pedidos apareca no topo do ranking.
MINIMO_PEDIDOS_CATEGORIA = 100

# Corte usado nos histogramas de tempo de entrega, em dias. Existem casos
# extremos de ate 209 dias que achatam o grafico inteiro.
CORTE_HISTOGRAMA_DIAS = 60

# Status que representa pedido efetivamente concluido.
STATUS_ENTREGUE = "delivered"

# ----------------------------------------------------------------------
# Identidade visual dos graficos
# ----------------------------------------------------------------------
CORES = {
    "primaria": "#1F4E79",
    "secundaria": "#2E8B8B",
    "destaque": "#CE0E2D",
    "positivo": "#2E7D32",
    "negativo": "#C62828",
    "neutro": "#8A8F98",
    "fundo": "#FFFFFF",
    "grade": "#E3E6EA",
    "texto": "#1A1D21",
}

SEQUENCIA_CORES = [
    "#1F4E79",
    "#2E8B8B",
    "#CE0E2D",
    "#E8A33D",
    "#6B4C9A",
    "#2E7D32",
    "#5B7C99",
    "#B5651D",
    "#8A8F98",
    "#4A6572",
]

DPI_FIGURA = 150


def garantir_pastas() -> None:
    """Cria as pastas de saida caso ainda nao existam."""
    for pasta in (PASTA_SAIDA, PASTA_FIGURAS, PASTA_TABELAS, PASTA_DOCS):
        pasta.mkdir(parents=True, exist_ok=True)
