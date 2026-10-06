"""
Analise exploratoria de dados.

Reproduz a secao 4 do trabalho, item por item:
  4.1 Estrutura e qualidade dos dados
  4.2 Perfil dos pedidos e sazonalidade
  4.3 Desempenho logistico
  4.4 Satisfacao do cliente
  4.5 Pagamentos, precos e categorias
  4.6 Distribuicao geografica e concentracao de vendedores

Cada bloco grava as tabelas em saida/tabelas e as figuras em saida/figuras,
e devolve os resultados em memoria para o dashboard consumir sem recalcular.
"""

from __future__ import annotations

import pandas as pd

from . import carga, config, graficos, tratamento


def _salvar_tabela(df: pd.DataFrame, nome: str, indice: bool = True) -> None:
    config.garantir_pastas()
    df.to_csv(config.PASTA_TABELAS / nome, index=indice, encoding="utf-8-sig")


def executar(tabelas: dict[str, pd.DataFrame], verbose: bool = True) -> dict:
    """Roda a analise exploratoria completa e devolve os resultados."""
    graficos.aplicar_estilo()
    config.garantir_pastas()
    resultados: dict = {}

    def log(texto: str) -> None:
        if verbose:
            print(texto)

    orders = tabelas["orders"]
    items = tabelas["items"]
    payments = tabelas["payments"]
    reviews = tabelas["reviews"]
    customers = tabelas["customers"]
    sellers = tabelas["sellers"]
    products = tabelas["products"]
    translation = tabelas["translation"]

    # ------------------------------------------------------------------
    # 4.1 Estrutura e qualidade dos dados
    # ------------------------------------------------------------------
    log("\n[4.1] Estrutura e qualidade dos dados")

    resumo = carga.resumo_tabelas(tabelas)
    nulos = carga.nulos_por_coluna(tabelas)
    tipos = carga.tipos_por_coluna(tabelas)
    unicidade = carga.verificar_unicidade(tabelas)
    integridade = carga.validar_integridade(tabelas)

    _salvar_tabela(resumo, "01_resumo_tabelas.csv")
    _salvar_tabela(nulos, "02_nulos_por_coluna.csv", indice=False)
    _salvar_tabela(tipos, "03_dicionario_de_dados.csv", indice=False)
    _salvar_tabela(unicidade, "04_chaves_candidatas.csv", indice=False)
    _salvar_tabela(integridade, "05_integridade_referencial.csv", indice=False)

    log(resumo.to_string())
    log(f"\nRelacionamentos com registros orfaos: "
        f"{int((integridade['orfaos'] > 0).sum())}")

    resultados["resumo_tabelas"] = resumo
    resultados["nulos"] = nulos
    resultados["unicidade"] = unicidade
    resultados["integridade"] = integridade

    # ------------------------------------------------------------------
    # 4.2 Perfil dos pedidos e sazonalidade
    # ------------------------------------------------------------------
    log("\n[4.2] Perfil dos pedidos e sazonalidade")

    status = tratamento.status_pedidos(orders)
    por_mes = tratamento.pedidos_por_mes(orders)

    _salvar_tabela(status, "06_status_pedidos.csv")
    _salvar_tabela(por_mes, "07_pedidos_por_mes.csv", indice=False)

    graficos.linha(
        por_mes["ano_mes"],
        por_mes["pedidos"],
        "Gráfico 1 - Pedidos por mês (2016-2018)",
        "Quantidade de pedidos",
    )
    graficos.salvar("grafico_01_pedidos_por_mes.png")

    pico = por_mes.loc[por_mes["pedidos"].idxmax()]
    log(f"Período: {orders['order_purchase_timestamp'].min():%d/%m/%Y} a "
        f"{orders['order_purchase_timestamp'].max():%d/%m/%Y}")
    log(f"Pico mensal: {pico['ano_mes']} com {int(pico['pedidos']):,} pedidos")
    log(f"Pedidos entregues: {status.loc['delivered', 'percentual']}%")

    resultados["status_pedidos"] = status
    resultados["pedidos_por_mes"] = por_mes

    # ------------------------------------------------------------------
    # 4.3 Desempenho logistico
    # ------------------------------------------------------------------
    log("\n[4.3] Desempenho logístico")

    entregues = tratamento.preparar_pedidos(orders)

    logistica = pd.DataFrame(
        {
            "tempo_entrega_dias": entregues["tempo_entrega_dias"].describe(),
            "prazo_estimado_dias": entregues["prazo_estimado_dias"].describe(),
            "atraso_dias": entregues["atraso_dias"].describe(),
        }
    ).round(2)
    _salvar_tabela(logistica, "08_logistica_descritiva.csv")

    pct_atraso = round(100 * entregues["atrasado"].mean(), 2)

    # Sensibilidade: o mesmo calculo pelo criterio que nao foi adotado.
    criterio_alt = config.criterio_alternativo()
    entregues_alt = tratamento.preparar_pedidos(orders, criterio=criterio_alt)
    pct_atraso_alt = round(100 * entregues_alt["atrasado"].mean(), 2)
    divergentes = int(
        (entregues["atrasado"].to_numpy() != entregues_alt["atrasado"].to_numpy()).sum()
    )

    graficos.histograma(
        entregues["tempo_entrega_dias"].clip(upper=config.CORTE_HISTOGRAMA_DIAS),
        f"Gráfico 2 - Distribuição do tempo de entrega "
        f"(dias, truncado em {config.CORTE_HISTOGRAMA_DIAS})",
        "Dias entre a compra e a entrega",
        "Pedidos",
    )
    graficos.salvar("grafico_02_tempo_entrega.png")

    log(f"Pedidos entregues analisados: {len(entregues):,}")
    log(f"Tempo médio de entrega: {entregues['tempo_entrega_dias'].mean():.2f} dias "
        f"(mediana {entregues['tempo_entrega_dias'].median():.0f})")
    log(f"Prazo estimado médio: {entregues['prazo_estimado_dias'].mean():.2f} dias")
    log(f"Entregas atrasadas (critério adotado, "
        f"{config.NOMES_CRITERIO[config.CRITERIO_ATRASO]}): {pct_atraso}%")
    log(f"Entregas atrasadas (sensibilidade, "
        f"{config.NOMES_CRITERIO[criterio_alt]}): {pct_atraso_alt}%")
    log(f"Pedidos classificados de forma diferente pelos dois critérios: "
        f"{divergentes:,}")

    resultados["entregues"] = entregues
    resultados["logistica"] = logistica
    resultados["pct_atraso"] = pct_atraso
    resultados["pct_atraso_alternativo"] = pct_atraso_alt
    resultados["criterio_adotado"] = config.CRITERIO_ATRASO
    resultados["criterio_alternativo"] = criterio_alt
    resultados["pedidos_divergentes"] = divergentes

    # ------------------------------------------------------------------
    # 4.4 Satisfacao do cliente
    # ------------------------------------------------------------------
    log("\n[4.4] Satisfação do cliente")

    notas = tratamento.distribuicao_notas(reviews)
    nota_pedido = tratamento.nota_por_pedido(reviews)
    _salvar_tabela(notas, "09_distribuicao_notas.csv")

    graficos.barras(
        notas.index,
        notas["avaliacoes"],
        "Gráfico 3 - Distribuição das notas de avaliação",
        "Avaliações",
        cor=[
            config.CORES["negativo"],
            config.CORES["negativo"],
            config.CORES["neutro"],
            config.CORES["secundaria"],
            config.CORES["positivo"],
        ],
        formato_rotulo="{:,.0f}",
    )
    graficos.salvar("grafico_03_notas.png")

    entregues = entregues.merge(nota_pedido, on="order_id", how="left")
    media_situacao = entregues.groupby("atrasado")["nota"].mean().round(2)
    media_situacao.index = media_situacao.index.map(
        {False: "No prazo", True: "Atrasado"}
    )

    correlacao_tempo = (
        entregues[["tempo_entrega_dias", "nota"]].corr(method="spearman").iloc[0, 1]
    )

    graficos.barras(
        media_situacao.index,
        media_situacao.to_numpy(),
        "Gráfico 4 - Nota média: no prazo x atrasado",
        "Nota média",
        cor=[config.CORES["positivo"], config.CORES["negativo"]],
        formato_rotulo="{:.2f}",
    )
    graficos.salvar("grafico_04_nota_atraso.png")

    log(f"Nota média geral: {reviews['review_score'].mean():.2f}")
    log(f"Notas 4 e 5: {notas.loc[[4, 5], 'percentual'].sum():.2f}%")
    log(f"Notas 1 e 2: {notas.loc[[1, 2], 'percentual'].sum():.2f}%")
    log(f"Nota média no prazo x atrasado: {media_situacao.to_dict()}")
    log(f"Spearman (tempo de entrega x nota): {correlacao_tempo:.3f}")

    resultados["distribuicao_notas"] = notas
    resultados["nota_por_pedido"] = nota_pedido
    resultados["media_por_situacao"] = media_situacao
    resultados["correlacao_tempo_nota"] = round(float(correlacao_tempo), 3)

    # ------------------------------------------------------------------
    # 4.5 Pagamentos, precos e categorias
    # ------------------------------------------------------------------
    log("\n[4.5] Pagamentos, preços e categorias")

    pagamentos = tratamento.pagamentos_por_tipo(payments)
    _salvar_tabela(pagamentos, "10_pagamentos_por_tipo.csv")

    graficos.barras(
        pagamentos.index,
        pagamentos["registros"],
        "Gráfico 5 - Pagamentos por forma de pagamento",
        "Registros de pagamento",
        rotacao=15,
        formato_rotulo="{:,.0f}",
    )
    graficos.salvar("grafico_05_pagamentos.png")

    ticket = tratamento.ticket_por_pedido(payments)
    precos = pd.DataFrame(
        {
            "preco_item": items["price"].describe(),
            "frete_item": items["freight_value"].describe(),
            "ticket_pedido": ticket["valor_pago"].describe(),
        }
    ).round(2)
    _salvar_tabela(precos, "11_precos_descritiva.csv")

    itens_cat = tratamento.itens_com_categoria(items, products, translation)
    categorias = (
        itens_cat.groupby("categoria")
        .agg(
            pedidos=("order_id", "nunique"),
            itens=("order_item_id", "count"),
            receita=("price", "sum"),
            preco_medio=("price", "mean"),
            frete_medio=("freight_value", "mean"),
        )
        .round(2)
    )
    top_pedidos = categorias.sort_values("pedidos", ascending=False).head(10)
    _salvar_tabela(categorias.sort_values("receita", ascending=False), "12_categorias.csv")

    graficos.barras_horizontais(
        top_pedidos.index[::-1],
        top_pedidos["pedidos"][::-1],
        "Gráfico 6 - Top 10 categorias por número de pedidos",
        "Pedidos",
    )
    graficos.salvar("grafico_06_top_categorias.png")

    frete_pedido = items.groupby("order_id")["freight_value"].sum().rename("frete")
    frete_nota = nota_pedido.set_index("order_id").join(frete_pedido, how="inner")
    correlacao_frete = frete_nota[["frete", "nota"]].corr(method="spearman").iloc[0, 1]

    log(f"Ticket mediano por pedido: R$ {ticket['valor_pago'].median():,.2f}")
    log(f"Ticket médio por pedido: R$ {ticket['valor_pago'].mean():,.2f}")
    log(f"Spearman (frete x nota): {correlacao_frete:.3f}")

    resultados["pagamentos"] = pagamentos
    resultados["precos"] = precos
    resultados["itens_categoria"] = itens_cat
    resultados["categorias"] = categorias
    resultados["correlacao_frete_nota"] = round(float(correlacao_frete), 3)

    # ------------------------------------------------------------------
    # 4.6 Geografia e concentracao
    # ------------------------------------------------------------------
    log("\n[4.6] Distribuição geográfica e concentração de vendedores")

    geo = tratamento.distribuicao_geografica(customers, sellers)
    _salvar_tabela(geo, "13_clientes_vendedores_por_uf.csv")

    top_uf = geo.head(10)
    graficos.barras_agrupadas(
        top_uf.index,
        {
            "% clientes": top_uf["pct_clientes"].tolist(),
            "% vendedores": top_uf["pct_vendedores"].tolist(),
        },
        "Gráfico 7 - Top 10 estados: clientes x vendedores",
        "Percentual",
    )
    graficos.salvar("grafico_07_geografia.png")

    curva, cortes = tratamento.concentracao_vendedores(items)
    _salvar_tabela(cortes, "14_concentracao_vendedores.csv", indice=False)

    figura, eixo = graficos.nova_figura(7, 4.5)
    eixo.plot(
        curva["pct_vendedores"],
        curva["pct_receita"],
        color=config.CORES["primaria"],
        linewidth=2,
    )
    eixo.plot([0, 100], [0, 100], linestyle="--", color=config.CORES["neutro"], linewidth=1)
    eixo.set_title("Gráfico 8 - Concentração da receita entre vendedores")
    eixo.set_xlabel("Percentual acumulado de vendedores")
    eixo.set_ylabel("Percentual acumulado da receita")
    graficos.salvar("grafico_08_concentracao_vendedores.png")

    log(geo.head(5).to_string())
    log("\n" + cortes.to_string(index=False))

    resultados["geografia"] = geo
    resultados["curva_concentracao"] = curva
    resultados["cortes_concentracao"] = cortes

    # ------------------------------------------------------------------
    # Numeros-chave consolidados
    # ------------------------------------------------------------------
    resultados["kpis"] = {
        "pedidos": int(orders["order_id"].nunique()),
        "clientes_unicos": int(customers["customer_unique_id"].nunique()),
        "vendedores": int(sellers["seller_id"].nunique()),
        "produtos": int(products["product_id"].nunique()),
        "itens": int(len(items)),
        "avaliacoes": int(len(reviews)),
        "receita_itens": float(items["price"].sum()),
        "frete_total": float(items["freight_value"].sum()),
        "valor_pago": float(payments["payment_value"].sum()),
        "ticket_medio": float(ticket["valor_pago"].mean()),
        "ticket_mediano": float(ticket["valor_pago"].median()),
        "nota_media": float(reviews["review_score"].mean()),
        "tempo_entrega_medio": float(entregues["tempo_entrega_dias"].mean()),
        "prazo_estimado_medio": float(entregues["prazo_estimado_dias"].mean()),
        "pct_atraso": pct_atraso,
        "pct_entregues": float(
            resultados["status_pedidos"].loc["delivered", "percentual"]
        ),
        "periodo_inicio": orders["order_purchase_timestamp"].min().strftime("%d/%m/%Y"),
        "periodo_fim": orders["order_purchase_timestamp"].max().strftime("%d/%m/%Y"),
    }

    return resultados
