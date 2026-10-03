import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

PASTA_DADOS = "dados"
PASTA_SAIDA = "saida_eda"
os.makedirs(PASTA_SAIDA, exist_ok=True)

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


def titulo(texto):
    print("\n" + "=" * 70)
    print(texto)
    print("=" * 70)


def salvar_fig(nome):
    plt.tight_layout()
    plt.savefig(os.path.join(PASTA_SAIDA, nome), dpi=150)
    plt.close()


# ----------------------------------------------------------------------
# 1) Carga e visão geral das tabelas
# ----------------------------------------------------------------------
titulo("1. VISÃO GERAL DAS TABELAS")

dfs = {
    nome: pd.read_csv(os.path.join(PASTA_DADOS, arquivo))
    for nome, arquivo in ARQUIVOS.items()
}

resumo = pd.DataFrame(
    {
        "arquivo": [ARQUIVOS[n] for n in dfs],
        "linhas": [d.shape[0] for d in dfs.values()],
        "colunas": [d.shape[1] for d in dfs.values()],
        "valores_nulos": [int(d.isna().sum().sum()) for d in dfs.values()],
        "linhas_duplicadas": [int(d.duplicated().sum()) for d in dfs.values()],
    },
    index=list(dfs.keys()),
)
print(resumo.to_string())
resumo.to_csv(os.path.join(PASTA_SAIDA, "01_resumo_tabelas.csv"))

titulo("1.1 COLUNAS COM VALORES NULOS (quantidade e % da tabela)")
linhas_nulos = []
for nome, d in dfs.items():
    nulos = d.isna().sum()
    for coluna, qtd in nulos[nulos > 0].items():
        linhas_nulos.append(
            {
                "tabela": nome,
                "coluna": coluna,
                "nulos": int(qtd),
                "percentual": round(100 * qtd / len(d), 2),
            }
        )
tabela_nulos = pd.DataFrame(linhas_nulos)
print(tabela_nulos.to_string(index=False))
tabela_nulos.to_csv(os.path.join(PASTA_SAIDA, "02_nulos_por_coluna.csv"), index=False)

titulo("1.2 TIPOS DE DADOS POR TABELA")
for nome, d in dfs.items():
    print(f"\n--- {nome} ---")
    print(d.dtypes.to_string())

# ----------------------------------------------------------------------
# 2) Números-chave (para conferir com o texto da Etapa 1)
# ----------------------------------------------------------------------
titulo("2. NÚMEROS-CHAVE")

orders = dfs["orders"].copy()
items = dfs["items"]
payments = dfs["payments"]
reviews = dfs["reviews"]
customers = dfs["customers"]
sellers = dfs["sellers"]
products = dfs["products"]
translation = dfs["translation"]

colunas_data = [
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
]
for c in colunas_data:
    orders[c] = pd.to_datetime(orders[c])

print(f"Pedidos (order_id únicos):              {orders['order_id'].nunique():,}")
print(f"Clientes (customer_id únicos):          {customers['customer_id'].nunique():,}")
print(
    f"Clientes (customer_unique_id únicos):   "
    f"{customers['customer_unique_id'].nunique():,}"
)
print(f"Vendedores (seller_id únicos):          {sellers['seller_id'].nunique():,}")
print(f"Produtos (product_id únicos):           {products['product_id'].nunique():,}")
print(f"Soma de price (itens):                  R$ {items['price'].sum():,.2f}")
print(f"Soma de freight_value:                  R$ {items['freight_value'].sum():,.2f}")
print(f"Soma de payment_value:                  R$ {payments['payment_value'].sum():,.2f}")

entregues_ids = orders.loc[orders["order_status"] == "delivered", "order_id"]
receita_entregues = items.loc[items["order_id"].isin(entregues_ids), "price"].sum()
print(f"Soma de price (só pedidos 'delivered'): R$ {receita_entregues:,.2f}")

# ----------------------------------------------------------------------
# 3) Pedidos: período, status e sazonalidade
# ----------------------------------------------------------------------
titulo("3. PEDIDOS: PERÍODO, STATUS E SAZONALIDADE")

print(
    "Período das compras: "
    f"{orders['order_purchase_timestamp'].min()} até "
    f"{orders['order_purchase_timestamp'].max()}"
)

status = orders["order_status"].value_counts()
status_pct = (100 * status / status.sum()).round(2)
tabela_status = pd.DataFrame({"pedidos": status, "percentual": status_pct})
print("\nStatus dos pedidos:")
print(tabela_status.to_string())
tabela_status.to_csv(os.path.join(PASTA_SAIDA, "03_status_pedidos.csv"))

por_mes = orders.groupby(orders["order_purchase_timestamp"].dt.to_period("M")).size()
por_mes.index = por_mes.index.astype(str)
print("\nPedidos por mês:")
print(por_mes.to_string())
por_mes.to_csv(os.path.join(PASTA_SAIDA, "04_pedidos_por_mes.csv"), header=["pedidos"])

plt.figure(figsize=(11, 4.5))
plt.plot(por_mes.index, por_mes.values, marker="o")
plt.xticks(rotation=90)
plt.title("Pedidos por mês (2016-2018)")
plt.ylabel("Quantidade de pedidos")
plt.grid(alpha=0.3)
salvar_fig("grafico_01_pedidos_por_mes.png")

# ----------------------------------------------------------------------
# 4) Logística: tempo de entrega e atrasos
# ----------------------------------------------------------------------
titulo("4. LOGÍSTICA: TEMPO DE ENTREGA E ATRASOS")

entregues = orders[
    (orders["order_status"] == "delivered")
    & orders["order_delivered_customer_date"].notna()
].copy()
entregues["tempo_entrega_dias"] = (
    entregues["order_delivered_customer_date"] - entregues["order_purchase_timestamp"]
).dt.days
entregues["prazo_estimado_dias"] = (
    entregues["order_estimated_delivery_date"] - entregues["order_purchase_timestamp"]
).dt.days
entregues["atrasado"] = (
    entregues["order_delivered_customer_date"] > entregues["order_estimated_delivery_date"]
)

print(f"Pedidos entregues analisados: {len(entregues):,}")
print("\nTempo real de entrega (dias):")
print(entregues["tempo_entrega_dias"].describe().round(2).to_string())
print("\nPrazo estimado (dias):")
print(entregues["prazo_estimado_dias"].describe().round(2).to_string())
print(f"\nPedidos entregues com atraso: {100 * entregues['atrasado'].mean():.2f}%")

plt.figure(figsize=(8, 4.5))
entregues["tempo_entrega_dias"].clip(upper=60).plot(kind="hist", bins=40)
plt.title("Distribuição do tempo de entrega (dias, truncado em 60)")
plt.xlabel("Dias entre compra e entrega")
plt.ylabel("Pedidos")
salvar_fig("grafico_02_tempo_entrega.png")

# ----------------------------------------------------------------------
# 5) Satisfação: avaliações e relação com atraso
# ----------------------------------------------------------------------
titulo("5. SATISFAÇÃO DO CLIENTE")

notas = reviews["review_score"].value_counts().sort_index()
tabela_notas = pd.DataFrame(
    {"avaliacoes": notas, "percentual": (100 * notas / notas.sum()).round(2)}
)
print("Distribuição das notas:")
print(tabela_notas.to_string())
print(f"\nNota média geral: {reviews['review_score'].mean():.2f}")
tabela_notas.to_csv(os.path.join(PASTA_SAIDA, "05_distribuicao_notas.csv"))

plt.figure(figsize=(6, 4))
plt.bar(tabela_notas.index.astype(str), tabela_notas["avaliacoes"])
plt.title("Distribuição das notas de avaliação")
plt.xlabel("Nota")
plt.ylabel("Avaliações")
salvar_fig("grafico_03_notas.png")

nota_por_pedido = reviews.groupby("order_id")["review_score"].mean().rename("nota")
entregues = entregues.merge(nota_por_pedido, on="order_id", how="left")

print("\nNota média por situação de entrega:")
media_atraso = entregues.groupby("atrasado")["nota"].mean().round(2)
media_atraso.index = media_atraso.index.map({False: "no prazo", True: "atrasado"})
print(media_atraso.to_string())

corr = entregues[["tempo_entrega_dias", "nota"]].corr(method="spearman").iloc[0, 1]
print(f"\nCorrelação de Spearman (tempo de entrega x nota): {corr:.3f}")

plt.figure(figsize=(5, 4))
plt.bar(media_atraso.index, media_atraso.values, color=["tab:green", "tab:red"])
plt.title("Nota média: no prazo x atrasado")
plt.ylabel("Nota média")
plt.ylim(0, 5)
salvar_fig("grafico_04_nota_atraso.png")

# ----------------------------------------------------------------------
# 6) Pagamentos
# ----------------------------------------------------------------------
titulo("6. PAGAMENTOS")

pg_tipo = (
    payments.groupby("payment_type")
    .agg(
        pagamentos=("order_id", "count"),
        valor_total=("payment_value", "sum"),
        valor_medio=("payment_value", "mean"),
        parcelas_medias=("payment_installments", "mean"),
    )
    .sort_values("pagamentos", ascending=False)
    .round(2)
)
print(pg_tipo.to_string())
pg_tipo.to_csv(os.path.join(PASTA_SAIDA, "06_pagamentos_por_tipo.csv"))

ticket_pedido = payments.groupby("order_id")["payment_value"].sum()
print("\nTicket por pedido (soma dos pagamentos):")
print(ticket_pedido.describe().round(2).to_string())

plt.figure(figsize=(6, 4))
plt.bar(pg_tipo.index, pg_tipo["pagamentos"])
plt.xticks(rotation=20)
plt.title("Pagamentos por forma de pagamento")
plt.ylabel("Quantidade")
salvar_fig("grafico_05_pagamentos.png")

# ----------------------------------------------------------------------
# 7) Preços, frete e categorias
# ----------------------------------------------------------------------
titulo("7. PREÇOS, FRETE E CATEGORIAS")

print("Preço dos itens:")
print(items["price"].describe().round(2).to_string())
print("\nValor do frete:")
print(items["freight_value"].describe().round(2).to_string())

itens_cat = items.merge(
    products[["product_id", "product_category_name"]], on="product_id", how="left"
).merge(translation, on="product_category_name", how="left")
itens_cat["categoria"] = itens_cat["product_category_name_english"].fillna(
    itens_cat["product_category_name"]
)
print(f"\nItens sem categoria: {itens_cat['categoria'].isna().sum():,}")

cat = (
    itens_cat.groupby("categoria")
    .agg(
        pedidos=("order_id", "nunique"),
        receita=("price", "sum"),
        preco_medio=("price", "mean"),
    )
    .round(2)
)
top_pedidos = cat.sort_values("pedidos", ascending=False).head(10)
top_receita = cat.sort_values("receita", ascending=False).head(10)
print("\nTop 10 categorias por número de pedidos:")
print(top_pedidos.to_string())
print("\nTop 10 categorias por receita:")
print(top_receita.to_string())
top_pedidos.to_csv(os.path.join(PASTA_SAIDA, "07_top_categorias_pedidos.csv"))
top_receita.to_csv(os.path.join(PASTA_SAIDA, "08_top_categorias_receita.csv"))

plt.figure(figsize=(8, 5))
top_pedidos["pedidos"].sort_values().plot(kind="barh")
plt.title("Top 10 categorias por número de pedidos")
plt.xlabel("Pedidos")
salvar_fig("grafico_06_top_categorias.png")

# Nota média por categoria (categorias com pelo menos 100 pedidos)
base_cat_nota = (
    itens_cat[["order_id", "categoria"]]
    .drop_duplicates()
    .merge(nota_por_pedido, on="order_id", how="left")
)
nota_cat = (
    base_cat_nota.groupby("categoria")
    .agg(pedidos=("order_id", "nunique"), nota_media=("nota", "mean"))
    .query("pedidos >= 100")
    .sort_values("nota_media")
    .round(2)
)
print("\nCategorias com pior nota média (mín. 100 pedidos):")
print(nota_cat.head(5).to_string())
print("\nCategorias com melhor nota média (mín. 100 pedidos):")
print(nota_cat.tail(5).to_string())
nota_cat.to_csv(os.path.join(PASTA_SAIDA, "09_nota_media_por_categoria.csv"))

# Frete x nota
frete_pedido = items.groupby("order_id")["freight_value"].sum().rename("frete")
frete_nota = nota_por_pedido.to_frame().join(frete_pedido, how="inner")
corr_frete = frete_nota.corr(method="spearman").iloc[0, 1]
print(f"\nCorrelação de Spearman (frete x nota): {corr_frete:.3f}")

# ----------------------------------------------------------------------
# 8) Geografia
# ----------------------------------------------------------------------
titulo("8. DISTRIBUIÇÃO GEOGRÁFICA")

cli_uf = customers["customer_state"].value_counts()
sel_uf = sellers["seller_state"].value_counts()
geo = pd.DataFrame({"clientes": cli_uf, "vendedores": sel_uf}).fillna(0).astype(int)
geo["pct_clientes"] = (100 * geo["clientes"] / geo["clientes"].sum()).round(2)
geo["pct_vendedores"] = (100 * geo["vendedores"] / geo["vendedores"].sum()).round(2)
geo = geo.sort_values("clientes", ascending=False)
print(geo.head(10).to_string())
geo.to_csv(os.path.join(PASTA_SAIDA, "10_clientes_vendedores_por_uf.csv"))

top_uf = geo.head(10)
posicoes = range(len(top_uf))
plt.figure(figsize=(9, 4.5))
plt.bar([p - 0.2 for p in posicoes], top_uf["pct_clientes"], width=0.4, label="% clientes")
plt.bar([p + 0.2 for p in posicoes], top_uf["pct_vendedores"], width=0.4, label="% vendedores")
plt.xticks(list(posicoes), top_uf.index)
plt.title("Top 10 estados: clientes x vendedores (%)")
plt.legend()
salvar_fig("grafico_07_geografia.png")

# ----------------------------------------------------------------------
# 9) Concentração de vendedores
# ----------------------------------------------------------------------
titulo("9. CONCENTRAÇÃO DE RECEITA ENTRE VENDEDORES")

receita_seller = items.groupby("seller_id")["price"].sum().sort_values(ascending=False)
total = receita_seller.sum()
n = len(receita_seller)
for pct in (0.01, 0.10, 0.20):
    k = max(1, int(n * pct))
    parcela = 100 * receita_seller.head(k).sum() / total
    print(f"Top {int(pct * 100)}% dos vendedores ({k}) concentram {parcela:.2f}% da receita")

acumulado = receita_seller.cumsum() / total
plt.figure(figsize=(6, 4.5))
plt.plot([i / n for i in range(1, n + 1)], acumulado.values)
plt.title("Curva de concentração da receita (vendedores)")
plt.xlabel("Proporção acumulada de vendedores")
plt.ylabel("Proporção acumulada da receita")
plt.grid(alpha=0.3)
salvar_fig("grafico_08_concentracao_vendedores.png")

titulo("FIM - arquivos salvos em: " + os.path.abspath(PASTA_SAIDA))