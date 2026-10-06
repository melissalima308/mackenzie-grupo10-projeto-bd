"""
Hipotese H2 - Categoria de produto e desempenho dos pedidos.

Pergunta: o desempenho dos pedidos varia conforme a categoria do produto,
considerando volume de pedidos, receita gerada e avaliacao media?

Metodo:
  1. Juntar itens, produtos e traducao de categoria.
  2. Calcular por categoria: pedidos, itens, receita, preco medio, ticket
     medio, frete medio, participacao na receita, nota media e percentual
     de entregas atrasadas.
  3. Restringir as comparacoes de nota as categorias com pelo menos
     config.MINIMO_PEDIDOS_CATEGORIA pedidos, para nao ranquear categoria
     com volume irrelevante.
  4. Montar a curva de Pareto da receita por categoria.
  5. Classificar as categorias em quadrantes cruzando receita e nota, o que
     separa o que sustenta o faturamento do que gera risco de insatisfacao.

Observacao sobre receita: a receita de uma categoria e a soma do campo
price dos itens daquela categoria. O frete fica fora, porque nao e receita
do produto. Um pedido com itens de categorias diferentes contribui para
cada uma delas na proporcao dos seus itens, e por isso a soma de pedidos
das categorias e maior que o total de pedidos do dataset.
"""

from __future__ import annotations

import pandas as pd

from . import config, formato, graficos, tratamento


def _salvar_tabela(df: pd.DataFrame, nome: str, indice: bool = True) -> None:
    config.garantir_pastas()
    df.to_csv(config.PASTA_TABELAS / nome, index=indice, encoding="utf-8-sig")


def executar(tabelas: dict[str, pd.DataFrame], verbose: bool = True) -> dict:
    graficos.aplicar_estilo()
    config.garantir_pastas()

    def log(texto: str) -> None:
        if verbose:
            print(texto)

    log("\n[H2] Categoria de produto e desempenho dos pedidos")

    itens_cat = tratamento.itens_com_categoria(
        tabelas["items"], tabelas["products"], tabelas["translation"]
    )
    nota_pedido = tratamento.nota_por_pedido(tabelas["reviews"])
    entregues = tratamento.preparar_pedidos(tabelas["orders"])

    # ------------------------------------------------------------------
    # Indicadores por categoria
    # ------------------------------------------------------------------
    desempenho = itens_cat.groupby("categoria").agg(
        pedidos=("order_id", "nunique"),
        itens=("order_item_id", "count"),
        receita=("price", "sum"),
        preco_medio=("price", "mean"),
        preco_mediano=("price", "median"),
        frete_medio=("freight_value", "mean"),
    )
    desempenho["ticket_medio"] = desempenho["receita"] / desempenho["pedidos"]
    desempenho["pct_receita"] = (
        100 * desempenho["receita"] / desempenho["receita"].sum()
    )
    desempenho["frete_sobre_preco"] = (
        100 * desempenho["frete_medio"] / desempenho["preco_medio"]
    )

    # Nota media por categoria, com o pedido contado uma vez por categoria.
    pedido_categoria = itens_cat[["order_id", "categoria"]].drop_duplicates()
    notas = (
        pedido_categoria.merge(nota_pedido, on="order_id", how="inner")
        .groupby("categoria")
        .agg(
            avaliacoes=("nota", "size"),
            nota_media=("nota", "mean"),
            pct_nota_baixa=("nota", lambda s: 100 * (s <= 2).mean()),
        )
    )
    desempenho = desempenho.join(notas)

    # Percentual de entregas atrasadas por categoria.
    atraso = (
        pedido_categoria.merge(
            entregues[["order_id", "atrasado", "tempo_entrega_dias"]],
            on="order_id",
            how="inner",
        )
        .groupby("categoria")
        .agg(
            pct_atraso=("atrasado", lambda s: 100 * s.mean()),
            tempo_entrega_medio=("tempo_entrega_dias", "mean"),
        )
    )
    desempenho = desempenho.join(atraso).round(2)
    desempenho = desempenho.sort_values("receita", ascending=False)

    _salvar_tabela(desempenho, "30_h2_desempenho_por_categoria.csv")
    log(f"Categorias analisadas: {len(desempenho)}")

    # ------------------------------------------------------------------
    # Rankings
    # ------------------------------------------------------------------
    relevantes = desempenho[
        desempenho["pedidos"] >= config.MINIMO_PEDIDOS_CATEGORIA
    ].copy()

    top_pedidos = desempenho.sort_values("pedidos", ascending=False).head(10)
    top_receita = desempenho.sort_values("receita", ascending=False).head(10)
    melhores_notas = relevantes.sort_values("nota_media", ascending=False).head(10)
    piores_notas = relevantes.sort_values("nota_media").head(10)

    _salvar_tabela(top_pedidos, "31_h2_top10_pedidos.csv")
    _salvar_tabela(top_receita, "32_h2_top10_receita.csv")
    _salvar_tabela(piores_notas, "33_h2_piores_notas.csv")

    log(f"\nCategorias com ao menos {config.MINIMO_PEDIDOS_CATEGORIA} pedidos: "
        f"{len(relevantes)}")
    log("\nTop 5 por receita:")
    log(top_receita[["pedidos", "receita", "nota_media"]].head().to_string())
    log("\nPiores 5 notas médias:")
    log(piores_notas[["pedidos", "receita", "nota_media"]].head().to_string())

    # ------------------------------------------------------------------
    # Pareto da receita
    # ------------------------------------------------------------------
    pareto = desempenho[["receita", "pct_receita"]].copy()
    pareto["pct_acumulado"] = pareto["pct_receita"].cumsum().round(2)
    pareto["posicao"] = range(1, len(pareto) + 1)
    _salvar_tabela(pareto, "34_h2_pareto_receita.csv")

    categorias_80 = int((pareto["pct_acumulado"] <= 80).sum()) + 1
    log(f"\n{categorias_80} categorias de {len(pareto)} concentram 80% da receita")

    # ------------------------------------------------------------------
    # Quadrantes: receita contra nota
    # ------------------------------------------------------------------
    corte_receita = relevantes["receita"].median()
    corte_nota = relevantes["nota_media"].median()

    def _quadrante(linha: pd.Series) -> str:
        alta_receita = linha["receita"] >= corte_receita
        alta_nota = linha["nota_media"] >= corte_nota
        if alta_receita and alta_nota:
            return "Sustenta o faturamento"
        if alta_receita and not alta_nota:
            return "Risco: muita receita, nota baixa"
        if not alta_receita and alta_nota:
            return "Potencial de crescimento"
        return "Baixa prioridade"

    relevantes["quadrante"] = relevantes.apply(_quadrante, axis=1)
    _salvar_tabela(
        relevantes[["pedidos", "receita", "nota_media", "pct_atraso", "quadrante"]],
        "35_h2_quadrantes.csv",
    )

    resumo_quadrantes = (
        relevantes.groupby("quadrante")
        .agg(
            categorias=("receita", "size"),
            receita=("receita", "sum"),
            nota_media=("nota_media", "mean"),
        )
        .round(2)
        .sort_values("receita", ascending=False)
    )
    log("\n" + resumo_quadrantes.to_string())

    # ------------------------------------------------------------------
    # Figuras
    # ------------------------------------------------------------------
    graficos.barras_horizontais(
        top_receita.index[::-1],
        (top_receita["receita"] / 1000)[::-1],
        "Gráfico 12 - Top 10 categorias por receita",
        "Receita (R$ mil)",
    )
    graficos.salvar("grafico_12_h2_top_receita.png")

    figura, eixo = graficos.nova_figura(9, 5)
    eixo.scatter(
        relevantes["receita"] / 1000,
        relevantes["nota_media"],
        s=(relevantes["pedidos"] / relevantes["pedidos"].max() * 400) + 20,
        alpha=0.6,
        color=config.CORES["primaria"],
        edgecolor="white",
        linewidth=0.8,
    )
    eixo.axhline(corte_nota, color=config.CORES["neutro"], linestyle="--", linewidth=1)
    eixo.axvline(
        corte_receita / 1000, color=config.CORES["neutro"], linestyle="--", linewidth=1
    )
    for nome, linha in relevantes.nlargest(8, "receita").iterrows():
        eixo.annotate(
            nome,
            (linha["receita"] / 1000, linha["nota_media"]),
            fontsize=8,
            xytext=(5, 4),
            textcoords="offset points",
        )
    eixo.set_xscale("log")
    eixo.set_title("Gráfico 13 - Receita x nota média por categoria")
    eixo.set_xlabel("Receita em R$ mil, escala logarítmica")
    eixo.set_ylabel("Nota média")
    graficos.salvar("grafico_13_h2_receita_x_nota.png")

    figura, eixo = graficos.nova_figura(9, 4.5)
    eixo.plot(
        pareto["posicao"],
        pareto["pct_acumulado"],
        color=config.CORES["primaria"],
        linewidth=2,
    )
    eixo.axhline(80, color=config.CORES["destaque"], linestyle="--", linewidth=1)
    eixo.set_title("Gráfico 14 - Curva de Pareto da receita por categoria")
    eixo.set_xlabel("Categorias ordenadas por receita")
    eixo.set_ylabel("Percentual acumulado da receita")
    graficos.salvar("grafico_14_h2_pareto.png")

    # ------------------------------------------------------------------
    # Conclusao objetiva
    # ------------------------------------------------------------------
    lider_pedidos = top_pedidos.index[0]
    lider_receita = top_receita.index[0]
    pior_nota = piores_notas.index[0]
    melhor_nota = melhores_notas.index[0]

    receita_risco = float(
        resumo_quadrantes.loc["Risco: muita receita, nota baixa", "receita"]
    )
    pct_risco = 100 * receita_risco / desempenho["receita"].sum()
    conclusao = (
        f"O desempenho varia conforme o indicador escolhido, e as lideranças não "
        f"coincidem. Em volume lidera {lider_pedidos}, com "
        f"{formato.numero(top_pedidos.iloc[0]['pedidos'])} pedidos. Em receita "
        f"lidera {lider_receita}, com "
        f"{formato.moeda(top_receita.iloc[0]['receita'])}. Em satisfação, entre as "
        f"categorias com ao menos {config.MINIMO_PEDIDOS_CATEGORIA} pedidos, a "
        f"melhor nota é de {melhor_nota} "
        f"({formato.decimal(melhores_notas.iloc[0]['nota_media'])}) e a pior é de "
        f"{pior_nota} ({formato.decimal(piores_notas.iloc[0]['nota_media'])}). "
        f"A receita é concentrada: {categorias_80} das {len(desempenho)} categorias "
        f"respondem por 80% do total. O cruzamento entre receita e nota revela o "
        f"ponto de atenção: {int(resumo_quadrantes.loc['Risco: muita receita, nota baixa', 'categorias'])} "
        f"categorias somam {formato.moeda(receita_risco)}, ou "
        f"{formato.percentual(pct_risco)} da receita, com nota média abaixo da "
        f"mediana. É onde a plataforma mais tem a perder se a insatisfação virar "
        f"abandono. A hipótese H2 é sustentada."
    )
    log("\n" + conclusao)

    return {
        "desempenho": desempenho,
        "relevantes": relevantes,
        "top_pedidos": top_pedidos,
        "top_receita": top_receita,
        "melhores_notas": melhores_notas,
        "piores_notas": piores_notas,
        "pareto": pareto,
        "quadrantes": resumo_quadrantes,
        "categorias_80": categorias_80,
        "conclusao": conclusao,
    }
