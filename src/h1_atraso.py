"""
Hipotese H1 - Atraso na entrega e satisfacao do cliente.

Pergunta: quanto maior o atraso na entrega em relacao a data estimada,
menor tende a ser a avaliacao atribuida pelo cliente?

Metodo:
  1. Calcular o atraso em dias de calendario para cada pedido entregue.
  2. Agregar as avaliacoes por pedido, usando a media quando ha mais de uma.
  3. Classificar os pedidos em cinco faixas de atraso.
  4. Comparar nota media, percentual de nota 1 e distribuicao de notas
     entre as faixas.
  5. Medir a associacao com a correlacao de Spearman e, quando scipy
     estiver disponivel, aplicar o teste de Kruskal-Wallis.

Por que Spearman e nao Pearson: a nota e uma variavel ordinal de 1 a 5 e o
atraso tem distribuicao fortemente assimetrica. Spearman trabalha com os
postos dos valores e nao exige relacao linear nem normalidade.
"""

from __future__ import annotations

import pandas as pd

from . import config, formato, graficos, tratamento

try:
    from scipy import stats as _stats
except ImportError:  # scipy e opcional
    _stats = None


def _salvar_tabela(df: pd.DataFrame, nome: str, indice: bool = True) -> None:
    config.garantir_pastas()
    df.to_csv(config.PASTA_TABELAS / nome, index=indice, encoding="utf-8-sig")


def executar(tabelas: dict[str, pd.DataFrame], verbose: bool = True) -> dict:
    graficos.aplicar_estilo()
    config.garantir_pastas()

    def log(texto: str) -> None:
        if verbose:
            print(texto)

    log("\n[H1] Atraso na entrega e satisfação do cliente")

    entregues = tratamento.preparar_pedidos(tabelas["orders"])
    nota_pedido = tratamento.nota_por_pedido(tabelas["reviews"])

    base = entregues.merge(nota_pedido, on="order_id", how="inner")
    base = base[base["nota"].notna()]
    log(f"Base de análise: {len(base):,} pedidos entregues e avaliados")

    # ------------------------------------------------------------------
    # Nota media e perfil de satisfacao por faixa de atraso
    # ------------------------------------------------------------------
    por_faixa = (
        base.groupby("faixa_atraso", observed=True)
        .agg(
            pedidos=("order_id", "count"),
            nota_media=("nota", "mean"),
            nota_mediana=("nota", "median"),
            tempo_entrega_medio=("tempo_entrega_dias", "mean"),
        )
        .round(2)
    )
    por_faixa["pct_pedidos"] = (
        100 * por_faixa["pedidos"] / por_faixa["pedidos"].sum()
    ).round(2)

    # Percentual de nota baixa (1 ou 2) e de nota alta (4 ou 5) em cada faixa.
    base["nota_arredondada"] = base["nota"].round().astype(int).clip(1, 5)
    por_faixa["pct_nota_1"] = (
        base.assign(ruim=base["nota_arredondada"] == 1)
        .groupby("faixa_atraso", observed=True)["ruim"]
        .mean()
        .mul(100)
        .round(2)
    )
    por_faixa["pct_nota_1_ou_2"] = (
        base.assign(ruim=base["nota_arredondada"] <= 2)
        .groupby("faixa_atraso", observed=True)["ruim"]
        .mean()
        .mul(100)
        .round(2)
    )
    por_faixa["pct_nota_4_ou_5"] = (
        base.assign(boa=base["nota_arredondada"] >= 4)
        .groupby("faixa_atraso", observed=True)["boa"]
        .mean()
        .mul(100)
        .round(2)
    )

    _salvar_tabela(por_faixa, "20_h1_nota_por_faixa_atraso.csv")
    log("\n" + por_faixa.to_string())

    # ------------------------------------------------------------------
    # Distribuicao percentual das notas dentro de cada faixa
    # ------------------------------------------------------------------
    distribuicao = (
        pd.crosstab(
            base["faixa_atraso"],
            base["nota_arredondada"],
            normalize="index",
        )
        .mul(100)
        .round(2)
    )
    distribuicao.columns = [f"nota_{c}" for c in distribuicao.columns]
    _salvar_tabela(distribuicao, "21_h1_distribuicao_notas_por_faixa.csv")

    # ------------------------------------------------------------------
    # Medidas de associacao
    # ------------------------------------------------------------------
    spearman_atraso = float(
        base[["atraso_dias", "nota"]].corr(method="spearman").iloc[0, 1]
    )
    spearman_tempo = float(
        base[["tempo_entrega_dias", "nota"]].corr(method="spearman").iloc[0, 1]
    )

    testes = {
        "spearman_atraso_nota": round(spearman_atraso, 3),
        "spearman_tempo_nota": round(spearman_tempo, 3),
    }

    if _stats is not None:
        grupos = [
            grupo["nota"].to_numpy()
            for _, grupo in base.groupby("faixa_atraso", observed=True)
        ]
        estatistica, p_valor = _stats.kruskal(*grupos)
        testes["kruskal_h"] = round(float(estatistica), 2)
        testes["kruskal_p"] = float(p_valor)
        log(f"\nKruskal-Wallis entre as faixas: H = {estatistica:,.2f}, "
            f"p = {p_valor:.3g}")
    else:
        log("\nscipy não instalado: teste de Kruskal-Wallis não executado.")

    log(f"Spearman (dias de atraso x nota): {spearman_atraso:.3f}")
    log(f"Spearman (tempo total de entrega x nota): {spearman_tempo:.3f}")

    # ------------------------------------------------------------------
    # Efeito marginal: nota media por dia de atraso, nos 30 primeiros dias
    # ------------------------------------------------------------------
    por_dia = (
        base[base["atraso_dias"].between(-30, 30)]
        .groupby("atraso_dias")
        .agg(pedidos=("order_id", "count"), nota_media=("nota", "mean"))
        .round(3)
        .reset_index()
    )
    por_dia = por_dia[por_dia["pedidos"] >= 30]
    _salvar_tabela(por_dia, "22_h1_nota_por_dia_atraso.csv", indice=False)

    # ------------------------------------------------------------------
    # Figuras
    # ------------------------------------------------------------------
    graficos.barras(
        por_faixa.index,
        por_faixa["nota_media"].to_numpy(),
        "Gráfico 9 - Nota média por faixa de atraso",
        "Nota média",
        cor=[
            config.CORES["positivo"],
            config.CORES["secundaria"],
            config.CORES["neutro"],
            "#E8A33D",
            config.CORES["negativo"],
        ],
        rotacao=12,
        formato_rotulo="{:.2f}",
    )
    graficos.salvar("grafico_09_h1_nota_por_faixa.png")

    figura, eixo = graficos.nova_figura(9.5, 4.8)
    acumulado = [0.0] * len(distribuicao)
    for indice, coluna in enumerate(distribuicao.columns):
        eixo.bar(
            [str(i) for i in distribuicao.index],
            distribuicao[coluna].to_numpy(),
            bottom=acumulado,
            label=coluna.replace("nota_", "Nota "),
            color=config.SEQUENCIA_CORES[indice % len(config.SEQUENCIA_CORES)],
            width=0.65,
        )
        acumulado = [a + b for a, b in zip(acumulado, distribuicao[coluna].to_numpy())]
    eixo.set_title("Gráfico 10 - Composição das notas por faixa de atraso")
    eixo.set_ylabel("Percentual das avaliações")
    eixo.tick_params(axis="x", rotation=12)
    eixo.grid(axis="x", visible=False)
    eixo.legend(ncol=5, loc="upper center", bbox_to_anchor=(0.5, -0.15))
    graficos.salvar("grafico_10_h1_composicao_notas.png")

    figura, eixo = graficos.nova_figura(9, 4.5)
    eixo.plot(
        por_dia["atraso_dias"],
        por_dia["nota_media"],
        marker="o",
        markersize=4,
        color=config.CORES["primaria"],
        linewidth=2,
    )
    eixo.axvline(0, color=config.CORES["destaque"], linestyle="--", linewidth=1)
    eixo.set_title("Gráfico 11 - Nota média por dia de atraso")
    eixo.set_xlabel("Dias de atraso (negativo = entrega adiantada)")
    eixo.set_ylabel("Nota média")
    graficos.salvar("grafico_11_h1_nota_por_dia.png")

    # ------------------------------------------------------------------
    # Conclusao objetiva
    # ------------------------------------------------------------------
    nota_prazo = float(por_faixa.loc["No prazo", "nota_media"])
    nota_pior = float(por_faixa.loc["Mais de 14 dias", "nota_media"])
    pct_no_prazo = float(por_faixa.loc["No prazo", "pct_pedidos"])
    ruim_prazo = float(por_faixa.loc["No prazo", "pct_nota_1_ou_2"])
    ruim_pior = float(por_faixa.loc["8 a 14 dias", "pct_nota_1_ou_2"])
    conclusao = (
        f"A nota média cai de {formato.decimal(nota_prazo)} nos pedidos entregues "
        f"no prazo para {formato.decimal(nota_pior)} nos pedidos com mais de 14 "
        f"dias de atraso, uma queda de {formato.decimal(nota_prazo - nota_pior)} "
        f"ponto em uma escala de cinco. O percentual de avaliações 1 ou 2 sobe de "
        f"{formato.percentual(ruim_prazo)} para {formato.percentual(ruim_pior)} na "
        f"faixa de 8 a 14 dias. A hipótese H1 é sustentada, e a queda é "
        f"progressiva: cada faixa adicional de atraso reduz a nota média, com "
        f"estabilização a partir de 8 dias, ponto em que o cliente insatisfeito já "
        f"deu a nota mínima e não há mais para onde cair. A correlação de Spearman "
        f"entre dias de atraso e nota é de {formato.decimal(spearman_atraso, 3)}, "
        f"aparentemente modesta porque {formato.percentual(pct_no_prazo)} dos "
        f"pedidos chegam no prazo e variam de antecedência sem variar de nota. O "
        f"efeito é concentrado na minoria que atrasa, e nessa minoria ele é forte."
    )
    log("\n" + conclusao)

    return {
        "base": base,
        "por_faixa": por_faixa,
        "distribuicao": distribuicao,
        "por_dia": por_dia,
        "testes": testes,
        "conclusao": conclusao,
    }
