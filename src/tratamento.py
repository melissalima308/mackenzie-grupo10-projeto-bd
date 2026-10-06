"""
Camada de tratamento.

Recebe as tabelas cruas da carga e devolve as bases derivadas que as
analises consomem. Toda regra de negocio do projeto mora aqui, para que
eda.py, h1_atraso.py e h2_categoria.py nao reimplementem o mesmo calculo
de formas diferentes.

Regras principais:
  - Pedido entregue e aquele com order_status = 'delivered' e data de
    entrega ao cliente preenchida.
  - Atraso e medido em dias de calendario (config.CRITERIO_ATRASO).
  - A nota de um pedido e a media das notas das avaliacoes daquele pedido,
    porque existem pedidos com mais de uma avaliacao.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config


# ----------------------------------------------------------------------
# Pedidos e logistica
# ----------------------------------------------------------------------
def preparar_pedidos(
    orders: pd.DataFrame, criterio: str | None = None
) -> pd.DataFrame:
    """Devolve apenas os pedidos entregues, com as metricas de logistica.

    Colunas acrescentadas:
      tempo_entrega_dias  dias entre a compra e a entrega ao cliente
      prazo_estimado_dias dias entre a compra e a data estimada de entrega
      atraso_dias         dias de atraso (negativo significa adiantamento)
      atrasado            booleano, atraso_dias > 0
      faixa_atraso        faixa categorica usada na hipotese H1
      ano_mes             competencia da compra, no formato AAAA-MM
    """
    criterio = criterio or config.CRITERIO_ATRASO

    entregues = orders[
        (orders["order_status"] == config.STATUS_ENTREGUE)
        & orders["order_delivered_customer_date"].notna()
        & orders["order_estimated_delivery_date"].notna()
    ].copy()

    compra = entregues["order_purchase_timestamp"]
    entrega = entregues["order_delivered_customer_date"]
    estimada = entregues["order_estimated_delivery_date"]

    entregues["tempo_entrega_dias"] = (entrega - compra).dt.days
    entregues["prazo_estimado_dias"] = (estimada - compra).dt.days

    if criterio == "dia":
        # Compara apenas a data. Uma entrega as 14h do dia estimado conta
        # como atraso zero, ou seja, dentro do prazo.
        entregues["atraso_dias"] = (
            entrega.dt.normalize() - estimada.dt.normalize()
        ).dt.days
    elif criterio == "timestamp":
        # Compara data e hora. Como a data estimada vem com hora 00:00:00, o
        # prazo vence a meia-noite e a entrega das 14h do dia estimado conta
        # como atraso. O arredondamento para cima e necessario: sem ele, uma
        # fracao de dia viraria zero e o criterio se confundiria com o
        # anterior.
        horas = (entrega - estimada).dt.total_seconds() / 86400
        entregues["atraso_dias"] = np.ceil(horas).astype(int)
    else:
        raise ValueError("criterio deve ser 'dia' ou 'timestamp'")

    entregues["atrasado"] = entregues["atraso_dias"] > 0
    entregues["faixa_atraso"] = classificar_faixa_atraso(entregues["atraso_dias"])
    entregues["ano_mes"] = compra.dt.strftime("%Y-%m")

    return entregues


def classificar_faixa_atraso(atraso_dias: pd.Series) -> pd.Series:
    """Converte dias de atraso nas faixas definidas em config.FAIXAS_ATRASO."""
    resultado = pd.Series(
        pd.NA, index=atraso_dias.index, dtype="object", name="faixa_atraso"
    )
    for nome, minimo, maximo in config.FAIXAS_ATRASO:
        mascara = atraso_dias.between(minimo, maximo)
        resultado[mascara] = nome
    return pd.Categorical(resultado, categories=config.ORDEM_FAIXAS, ordered=True)


def pedidos_por_mes(orders: pd.DataFrame) -> pd.DataFrame:
    """Serie mensal de pedidos, por data de compra."""
    serie = (
        orders["order_purchase_timestamp"]
        .dt.strftime("%Y-%m")
        .value_counts()
        .sort_index()
    )
    return serie.rename_axis("ano_mes").reset_index(name="pedidos")


def status_pedidos(orders: pd.DataFrame) -> pd.DataFrame:
    """Distribuicao dos pedidos por status, com percentual."""
    contagem = orders["order_status"].value_counts()
    return pd.DataFrame(
        {
            "pedidos": contagem,
            "percentual": (100 * contagem / contagem.sum()).round(2),
        }
    ).rename_axis("status")


# ----------------------------------------------------------------------
# Avaliacoes
# ----------------------------------------------------------------------
def nota_por_pedido(reviews: pd.DataFrame) -> pd.DataFrame:
    """Nota media e quantidade de avaliacoes por pedido."""
    return (
        reviews.groupby("order_id")
        .agg(nota=("review_score", "mean"), avaliacoes=("review_score", "size"))
        .reset_index()
    )


def distribuicao_notas(reviews: pd.DataFrame) -> pd.DataFrame:
    """Quantidade e percentual de avaliacoes por nota de 1 a 5."""
    contagem = reviews["review_score"].value_counts().sort_index()
    return pd.DataFrame(
        {
            "avaliacoes": contagem,
            "percentual": (100 * contagem / contagem.sum()).round(2),
        }
    ).rename_axis("nota")


# ----------------------------------------------------------------------
# Itens, categorias e receita
# ----------------------------------------------------------------------
def itens_com_categoria(
    items: pd.DataFrame, products: pd.DataFrame, translation: pd.DataFrame
) -> pd.DataFrame:
    """Junta itens, produtos e traducao, criando a coluna 'categoria'.

    A categoria usa o nome em ingles quando existe e cai para o nome em
    portugues quando a traducao falta. Itens cujo produto nao tem categoria
    recebem 'sem_categoria', para que nao sumam das somas de receita.
    """
    base = items.merge(
        products[["product_id", "product_category_name"]],
        on="product_id",
        how="left",
    ).merge(translation, on="product_category_name", how="left")

    base["categoria"] = (
        base["product_category_name_english"]
        .fillna(base["product_category_name"])
        .fillna("sem_categoria")
    )
    return base


def receita_por_pedido(items: pd.DataFrame) -> pd.DataFrame:
    """Receita de produto, frete e quantidade de itens, por pedido."""
    return (
        items.groupby("order_id")
        .agg(
            receita_produto=("price", "sum"),
            frete=("freight_value", "sum"),
            itens=("order_item_id", "count"),
        )
        .reset_index()
    )


def ticket_por_pedido(payments: pd.DataFrame) -> pd.DataFrame:
    """Valor total pago por pedido, somando todos os registros de pagamento."""
    return (
        payments.groupby("order_id")
        .agg(
            valor_pago=("payment_value", "sum"),
            registros_pagamento=("payment_sequential", "count"),
        )
        .reset_index()
    )


def pagamentos_por_tipo(payments: pd.DataFrame) -> pd.DataFrame:
    """Resumo por forma de pagamento: volume, valor e parcelamento."""
    resumo = (
        payments.groupby("payment_type")
        .agg(
            registros=("order_id", "count"),
            valor_total=("payment_value", "sum"),
            valor_medio=("payment_value", "mean"),
            parcelas_medias=("payment_installments", "mean"),
        )
        .sort_values("registros", ascending=False)
    )
    resumo["pct_registros"] = (100 * resumo["registros"] / resumo["registros"].sum()).round(2)
    resumo["pct_valor"] = (100 * resumo["valor_total"] / resumo["valor_total"].sum()).round(2)
    return resumo.round(2).rename_axis("forma_pagamento")


# ----------------------------------------------------------------------
# Geografia e concentracao
# ----------------------------------------------------------------------
def distribuicao_geografica(
    customers: pd.DataFrame, sellers: pd.DataFrame
) -> pd.DataFrame:
    """Clientes e vendedores por unidade federativa, em numero e percentual."""
    clientes = customers["customer_state"].value_counts()
    vendedores = sellers["seller_state"].value_counts()

    geo = pd.DataFrame({"clientes": clientes, "vendedores": vendedores})
    geo = geo.fillna(0).astype(int)
    geo["pct_clientes"] = (100 * geo["clientes"] / geo["clientes"].sum()).round(2)
    geo["pct_vendedores"] = (100 * geo["vendedores"] / geo["vendedores"].sum()).round(2)
    # Razao entre a participacao de clientes e a de vendedores. Acima de 1
    # indica estado que compra mais do que vende na plataforma.
    geo["razao_cliente_vendedor"] = (
        geo["pct_clientes"] / geo["pct_vendedores"].replace(0, np.nan)
    ).round(2)
    return geo.sort_values("clientes", ascending=False).rename_axis("uf")


def concentracao_vendedores(items: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Curva de Lorenz da receita por vendedor e os cortes de 1%, 10% e 20%.

    Devolve (curva, cortes). A curva vem reamostrada em 200 pontos para que
    o dashboard nao precise carregar 3.095 pares de coordenadas.
    """
    receita = items.groupby("seller_id")["price"].sum().sort_values(ascending=False)
    total = receita.sum()
    n = len(receita)

    acumulado = receita.cumsum() / total
    proporcao = np.arange(1, n + 1) / n

    passo = max(1, n // 200)
    indices = list(range(0, n, passo))
    if indices[-1] != n - 1:
        indices.append(n - 1)

    curva = pd.DataFrame(
        {
            "pct_vendedores": np.round(100 * proporcao[indices], 3),
            "pct_receita": np.round(100 * acumulado.to_numpy()[indices], 3),
        }
    )

    linhas = []
    for corte in (0.01, 0.05, 0.10, 0.20, 0.50):
        k = max(1, int(n * corte))
        linhas.append(
            {
                "corte": f"Top {int(corte * 100)}%",
                "vendedores": k,
                "pct_receita": round(100 * receita.head(k).sum() / total, 2),
            }
        )

    return curva, pd.DataFrame(linhas)
