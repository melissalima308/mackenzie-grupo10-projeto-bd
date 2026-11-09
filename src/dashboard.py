"""
Gerador do dashboard.

Produz um unico arquivo HTML autocontido em saida/dashboard.html. Os dados
agregados sao embutidos no proprio arquivo como JSON e os graficos sao
desenhados pelo Plotly.js carregado do CDN. Isso significa que o arquivo
abre com duplo clique em qualquer navegador, pode ser publicado no GitHub
Pages e nao exige que ninguem instale biblioteca na hora da apresentacao.

A unica dependencia externa em tempo de execucao e a conexao com o CDN do
Plotly. Para uso totalmente offline, baixe plotly.min.js e troque a tag de
script pelo caminho local.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from . import config, formato

PLOTLY_CDN = "https://cdn.plot.ly/plotly-2.35.2.min.js"


def _limpar(valor):
    """Converte tipos do numpy e do pandas para tipos nativos do Python."""
    if isinstance(valor, (np.integer,)):
        return int(valor)
    if isinstance(valor, (np.floating,)):
        return None if np.isnan(valor) else round(float(valor), 4)
    if isinstance(valor, (np.bool_,)):
        return bool(valor)
    if valor is None or (isinstance(valor, float) and np.isnan(valor)):
        return None
    return valor


def _lista(serie) -> list:
    return [_limpar(v) for v in list(serie)]


# ----------------------------------------------------------------------
# Montagem do pacote de dados
# ----------------------------------------------------------------------
def construir_dados(
    tabelas: dict[str, pd.DataFrame],
    resultado_eda: dict,
    resultado_h1: dict,
    resultado_h2: dict,
) -> dict:
    dados: dict = {}

    dados["kpis"] = {k: _limpar(v) for k, v in resultado_eda["kpis"].items()}

    # Sazonalidade ------------------------------------------------------
    por_mes = resultado_eda["pedidos_por_mes"]
    receita_mes = (
        tabelas["items"]
        .merge(
            tabelas["orders"][["order_id", "order_purchase_timestamp"]],
            on="order_id",
            how="left",
        )
        .assign(ano_mes=lambda d: d["order_purchase_timestamp"].dt.strftime("%Y-%m"))
        .groupby("ano_mes")["price"]
        .sum()
    )
    dados["sazonalidade"] = {
        "meses": _lista(por_mes["ano_mes"]),
        "pedidos": _lista(por_mes["pedidos"]),
        "receita": _lista(receita_mes.reindex(por_mes["ano_mes"]).fillna(0).round(2)),
    }

    # Status ------------------------------------------------------------
    status = resultado_eda["status_pedidos"]
    dados["status"] = {
        "rotulos": _lista(status.index),
        "pedidos": _lista(status["pedidos"]),
        "percentual": _lista(status["percentual"]),
    }

    # Notas e pagamentos ------------------------------------------------
    notas = resultado_eda["distribuicao_notas"]
    dados["notas"] = {
        "rotulos": [f"Nota {n}" for n in notas.index],
        "avaliacoes": _lista(notas["avaliacoes"]),
        "percentual": _lista(notas["percentual"]),
    }

    traducao_pagamento = {
        "credit_card": "Cartão de crédito",
        "boleto": "Boleto",
        "voucher": "Voucher",
        "debit_card": "Cartão de débito",
        "not_defined": "Não informado",
    }
    pagamentos = resultado_eda["pagamentos"]
    dados["pagamentos"] = {
        "rotulos": [traducao_pagamento.get(p, p) for p in pagamentos.index],
        "registros": _lista(pagamentos["registros"]),
        "pct_registros": _lista(pagamentos["pct_registros"]),
        "pct_valor": _lista(pagamentos["pct_valor"]),
        "valor_medio": _lista(pagamentos["valor_medio"]),
        "parcelas": _lista(pagamentos["parcelas_medias"]),
    }

    # Logistica ---------------------------------------------------------
    entregues = resultado_eda["entregues"]
    corte = config.CORTE_HISTOGRAMA_DIAS
    contagem, bordas = np.histogram(
        entregues["tempo_entrega_dias"].clip(upper=corte), bins=40
    )
    centros = (bordas[:-1] + bordas[1:]) / 2
    dados["histograma_entrega"] = {
        "x": [round(float(c), 2) for c in centros],
        "y": [int(c) for c in contagem],
        "largura": round(float(bordas[1] - bordas[0]), 3),
    }

    mensal = entregues.groupby("ano_mes").agg(
        tempo_real=("tempo_entrega_dias", "mean"),
        prazo_estimado=("prazo_estimado_dias", "mean"),
        pct_atraso=("atrasado", "mean"),
    )
    dados["logistica_mensal"] = {
        "meses": _lista(mensal.index),
        "tempo_real": _lista(mensal["tempo_real"].round(2)),
        "prazo_estimado": _lista(mensal["prazo_estimado"].round(2)),
        "pct_atraso": _lista((100 * mensal["pct_atraso"]).round(2)),
    }

    dados["logistica_resumo"] = {
        "tempo_medio": _limpar(entregues["tempo_entrega_dias"].mean()),
        "tempo_mediano": _limpar(entregues["tempo_entrega_dias"].median()),
        "prazo_medio": _limpar(entregues["prazo_estimado_dias"].mean()),
        "folga_media": _limpar(
            entregues["prazo_estimado_dias"].mean()
            - entregues["tempo_entrega_dias"].mean()
        ),
        "pct_atraso": _limpar(resultado_eda["pct_atraso"]),
        "pct_atraso_alternativo": _limpar(resultado_eda["pct_atraso_alternativo"]),
        "criterio_adotado": config.NOMES_CRITERIO[resultado_eda["criterio_adotado"]],
        "criterio_alternativo": config.NOMES_CRITERIO[
            resultado_eda["criterio_alternativo"]
        ],
        "pedidos_divergentes": _limpar(resultado_eda["pedidos_divergentes"]),
        "tempo_maximo": _limpar(entregues["tempo_entrega_dias"].max()),
    }

    # H1 ----------------------------------------------------------------
    faixa = resultado_h1["por_faixa"]
    dados["h1"] = {
        "faixas": [str(f) for f in faixa.index],
        "nota_media": _lista(faixa["nota_media"]),
        "pedidos": _lista(faixa["pedidos"]),
        "pct_pedidos": _lista(faixa["pct_pedidos"]),
        "pct_ruim": _lista(faixa["pct_nota_1_ou_2"]),
        "pct_boa": _lista(faixa["pct_nota_4_ou_5"]),
        "testes": {k: _limpar(v) for k, v in resultado_h1["testes"].items()},
        "conclusao": resultado_h1["conclusao"],
    }

    composicao = resultado_h1["distribuicao"]
    dados["h1_composicao"] = {
        "faixas": [str(f) for f in composicao.index],
        "series": {
            coluna.replace("nota_", "Nota "): _lista(composicao[coluna])
            for coluna in composicao.columns
        },
    }

    por_dia = resultado_h1["por_dia"]
    dados["h1_por_dia"] = {
        "dias": _lista(por_dia["atraso_dias"]),
        "nota": _lista(por_dia["nota_media"]),
        "pedidos": _lista(por_dia["pedidos"]),
    }

    # H2 ----------------------------------------------------------------
    top_receita = resultado_h2["top_receita"]
    top_pedidos = resultado_h2["top_pedidos"]
    relevantes = resultado_h2["relevantes"]
    pareto = resultado_h2["pareto"]

    dados["h2"] = {
        "top_receita": {
            "categorias": _lista(top_receita.index),
            "receita": _lista(top_receita["receita"]),
            "nota": _lista(top_receita["nota_media"]),
        },
        "top_pedidos": {
            "categorias": _lista(top_pedidos.index),
            "pedidos": _lista(top_pedidos["pedidos"]),
            "nota": _lista(top_pedidos["nota_media"]),
        },
        "dispersao": {
            "categorias": _lista(relevantes.index),
            "receita": _lista(relevantes["receita"]),
            "nota": _lista(relevantes["nota_media"]),
            "pedidos": _lista(relevantes["pedidos"]),
            "pct_atraso": _lista(relevantes["pct_atraso"]),
            "quadrante": _lista(relevantes["quadrante"]),
        },
        "pareto": {
            "posicao": _lista(pareto["posicao"]),
            "acumulado": _lista(pareto["pct_acumulado"]),
            "categorias": _lista(pareto.index),
        },
        "categorias_80": _limpar(resultado_h2["categorias_80"]),
        "total_categorias": int(len(resultado_h2["desempenho"])),
        "melhor_nota": {
            "categoria": str(resultado_h2["melhores_notas"].index[0]),
            "nota": _limpar(resultado_h2["melhores_notas"].iloc[0]["nota_media"]),
        },
        "pior_nota": {
            "categoria": str(resultado_h2["piores_notas"].index[0]),
            "nota": _limpar(resultado_h2["piores_notas"].iloc[0]["nota_media"]),
        },
        "conclusao": resultado_h2["conclusao"],
    }

    # Geografia e concentracao -----------------------------------------
    geo = resultado_eda["geografia"].head(12)
    dados["geografia"] = {
        "uf": _lista(geo.index),
        "pct_clientes": _lista(geo["pct_clientes"]),
        "pct_vendedores": _lista(geo["pct_vendedores"]),
        "clientes": _lista(geo["clientes"]),
        "vendedores": _lista(geo["vendedores"]),
    }

    curva = resultado_eda["curva_concentracao"]
    cortes = resultado_eda["cortes_concentracao"]
    dados["concentracao"] = {
        "pct_vendedores": _lista(curva["pct_vendedores"]),
        "pct_receita": _lista(curva["pct_receita"]),
        "cortes": cortes.to_dict(orient="records"),
    }

    # Modelo de dados ---------------------------------------------------
    resumo = resultado_eda["resumo_tabelas"]
    chaves = {
        "orders": "order_id",
        "items": "order_id + order_item_id",
        "payments": "order_id + payment_sequential",
        "reviews": "review_id + order_id",
        "customers": "customer_id",
        "sellers": "seller_id",
        "products": "product_id",
        "geolocation": "sem chave natural",
        "translation": "product_category_name",
    }
    dados["modelo"] = [
        {
            "tabela": nome,
            "arquivo": linha["arquivo"],
            "linhas": int(linha["linhas"]),
            "colunas": int(linha["colunas"]),
            "nulos": int(linha["valores_nulos"]),
            "duplicadas": int(linha["linhas_duplicadas"]),
            "chave_primaria": chaves.get(nome, ""),
        }
        for nome, linha in resumo.iterrows()
    ]

    dados["integridade"] = resultado_eda["integridade"].to_dict(orient="records")

    dados["correlacoes"] = {
        "tempo_nota": _limpar(resultado_eda["correlacao_tempo_nota"]),
        "frete_nota": _limpar(resultado_eda["correlacao_frete_nota"]),
        "atraso_nota": _limpar(resultado_h1["testes"]["spearman_atraso_nota"]),
    }

    # Atraso e nota por estado do cliente (complemento da H1)
    if "por_uf" in resultado_h1:
        por_uf = resultado_h1["por_uf"]
        dados["h1_uf"] = {
            "uf": _lista(por_uf.index),
            "pedidos": _lista(por_uf["pedidos"]),
            "pct_atraso": _lista(por_uf["pct_atraso"]),
            "nota_media": _lista(por_uf["nota_media"]),
            "tempo_entrega_medio": _lista(por_uf["tempo_entrega_medio"]),
        }

    dados["gerado_em"] = datetime.now().strftime("%d/%m/%Y às %H:%M")
    return dados


# ----------------------------------------------------------------------
# HTML
# ----------------------------------------------------------------------
# O layout segue a ordem do storytelling do projeto: contexto, logistica,
# H1, H2, estrutura geografica e, por ultimo, o apendice tecnico. Cada aba
# abre com a pergunta que ela responde e a resposta em uma frase.
CSS = """
:root {
  --azul: #1F4E79;
  --azul-claro: #E9F0F7;
  --teal: #2E8B8B;
  --vermelho: #C62835;
  --vermelho-claro: #FBECEE;
  --verde: #2E7D32;
  --verde-claro: #EAF4EB;
  --ambar: #D9822B;
  --texto: #1A1D21;
  --suave: #5A6472;
  --fraco: #8A93A0;
  --borda: #E3E6EA;
  --fundo: #F4F6F9;
  --cartao: #FFFFFF;
  --sombra: 0 1px 2px rgba(16, 24, 40, 0.04), 0 1px 3px rgba(16, 24, 40, 0.06);
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
               "Helvetica Neue", Arial, sans-serif;
  background: var(--fundo);
  color: var(--texto);
  line-height: 1.55;
  -webkit-font-smoothing: antialiased;
}
code { font-size: 0.92em; background: #EEF1F5; padding: 1px 5px; border-radius: 4px; }

/* ---------------------------------------------------------------- topo */
header { background: var(--azul); color: #fff; }
.topo { max-width: 1240px; margin: 0 auto; padding: 30px 24px 26px; }
.selo { font-size: 12px; letter-spacing: 0.8px; text-transform: uppercase;
        opacity: 0.75; font-weight: 600; }
header h1 { margin: 6px 0 8px; font-size: clamp(22px, 3vw, 30px);
            letter-spacing: -0.4px; line-height: 1.2; }
.tese { margin: 0; max-width: 780px; font-size: clamp(15px, 1.6vw, 17px);
        opacity: 0.92; }
.destaques { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px;
             margin-top: 22px; }
.destaque { background: rgba(255,255,255,0.09); border: 1px solid rgba(255,255,255,0.16);
            border-radius: 10px; padding: 12px 14px; }
.destaque .v { font-size: clamp(20px, 2.4vw, 26px); font-weight: 700;
               font-variant-numeric: tabular-nums; }
.destaque .r { font-size: 12.5px; opacity: 0.85; line-height: 1.4; }
.meta { margin-top: 16px; font-size: 12px; opacity: 0.7; }

/* ---------------------------------------------------------------- abas */
nav { position: sticky; top: 0; z-index: 20; background: var(--cartao);
      border-bottom: 1px solid var(--borda); box-shadow: var(--sombra); }
nav .trilho { max-width: 1240px; margin: 0 auto; padding: 0 16px; display: flex;
              gap: 2px; overflow-x: auto; scrollbar-width: none; }
nav .trilho::-webkit-scrollbar { display: none; }
nav button { flex: 0 0 auto; background: none; border: none; cursor: pointer;
             border-bottom: 3px solid transparent; padding: 14px 12px 12px;
             font: 600 14px/1.2 inherit; color: var(--suave); white-space: nowrap; }
nav button .n { display: inline-grid; place-items: center; width: 20px; height: 20px;
                margin-right: 7px; border-radius: 50%; font-size: 11px;
                background: #EEF1F5; color: var(--suave); }
nav button:hover { color: var(--azul); }
nav button.ativo { color: var(--azul); border-bottom-color: var(--azul); }
nav button.ativo .n { background: var(--azul); color: #fff; }

/* ------------------------------------------------------------ conteudo */
.conteudo { max-width: 1240px; margin: 0 auto; padding: 8px 24px 56px; }
.aba { display: none; }
.aba.ativa { display: block; animation: surgir 0.25s ease; }
@keyframes surgir { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; } }
.abertura { margin: 26px 0 6px; }
.abertura .pergunta { font-size: 13px; font-weight: 600; color: var(--suave);
                      text-transform: uppercase; letter-spacing: 0.6px; }
.abertura h2 { margin: 4px 0 0; font-size: clamp(19px, 2.2vw, 24px);
               letter-spacing: -0.3px; line-height: 1.3; max-width: 900px; }

.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
        gap: 12px; margin: 18px 0 4px; }
.kpi { background: var(--cartao); border: 1px solid var(--borda); border-radius: 10px;
       padding: 14px 16px; box-shadow: var(--sombra); min-width: 0; }
.kpi .rotulo { font-size: 11.5px; text-transform: uppercase; letter-spacing: 0.6px;
               color: var(--suave); font-weight: 600; }
.kpi .valor { font-size: clamp(21px, 2.2vw, 25px); font-weight: 700; margin-top: 4px;
              color: var(--azul); font-variant-numeric: tabular-nums; line-height: 1.25; }
.kpi .nota { font-size: 12px; color: var(--suave); margin-top: 3px; }
.kpi.ruim .valor { color: var(--vermelho); }
.kpi.bom .valor { color: var(--verde); }

.cartao { background: var(--cartao); border: 1px solid var(--borda); border-radius: 12px;
          padding: 18px 20px 12px; margin-top: 16px; box-shadow: var(--sombra); min-width: 0; }
.cartao h3 { margin: 0 0 2px; font-size: 15.5px; }
.cartao .sub { margin: 0 0 8px; font-size: 13px; color: var(--suave); }
.grade2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.grade2 > .cartao { margin-top: 16px; }
@media (max-width: 900px) {
  .grade2 { grid-template-columns: 1fr; gap: 0; }
  .destaques { grid-template-columns: 1fr 1fr; }
}
.grafico { width: 100%; height: 340px; }
.grafico.alto { height: 430px; }

.achado { display: flex; gap: 12px; align-items: flex-start; background: var(--azul-claro);
          border-radius: 10px; padding: 14px 18px; margin-top: 16px; font-size: 14.5px; }
.achado::before { content: "→"; font-weight: 700; color: var(--azul); }
.achado strong { color: var(--azul); }
.achado.alerta { background: var(--vermelho-claro); }
.achado.alerta::before { content: "!"; color: var(--vermelho); }
.achado.alerta strong { color: var(--vermelho); }
.achado.metodo { background: #F1F2F5; }
.achado.metodo::before { content: "i"; color: var(--suave); font-style: italic; }
.achado.metodo strong { color: var(--texto); }

.tabela { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 13.5px; }
th, td { padding: 9px 12px; text-align: left; border-bottom: 1px solid var(--borda); }
th { background: #F5F7FA; font-weight: 600; font-size: 12px; text-transform: uppercase;
     letter-spacing: 0.4px; color: var(--suave); white-space: nowrap; }
tbody tr:hover { background: #FAFBFC; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
.barra { display: inline-block; height: 8px; border-radius: 4px; vertical-align: middle;
         margin-right: 8px; background: var(--vermelho); opacity: 0.85; }
.tag { display: inline-block; padding: 2px 9px; border-radius: 20px;
       font-size: 11.5px; font-weight: 600; }
.tag.ok { background: var(--verde-claro); color: var(--verde); }
.tag.atencao { background: var(--vermelho-claro); color: var(--vermelho); }

.proxima { display: flex; justify-content: flex-end; margin-top: 22px; }
.proxima button { background: var(--cartao); border: 1px solid var(--borda);
                  border-radius: 8px; padding: 10px 16px; cursor: pointer;
                  font: 600 14px inherit; color: var(--azul); box-shadow: var(--sombra); }
.proxima button:hover { border-color: var(--azul); }

footer { text-align: center; padding: 28px 20px 40px; color: var(--suave);
         font-size: 12.5px; border-top: 1px solid var(--borda); }
footer a { color: var(--azul); }
@media (max-width: 560px) {
  .topo, .conteudo { padding-left: 16px; padding-right: 16px; }
  .cartao { padding: 14px 12px 8px; }
  .grafico { height: 300px; }
  .grafico.alto { height: 380px; }
}
"""


def _javascript(dados_json: str) -> str:
    return (
        "const D = "
        + dados_json
        + """;

const AZUL = '#1F4E79', TEAL = '#2E8B8B', VERM = '#C62835',
      VERDE = '#2E7D32', AMBAR = '#D9822B', CINZA = '#9AA3AF', GRADE = '#E9ECF0';
// Escala de gravidade usada em tudo que fala de atraso: do verde (no prazo)
// ao vinho (mais de 14 dias). Mesma cor = mesma faixa em todos os graficos.
const GRAVIDADE = ['#2E7D32', '#E0B03A', '#D9822B', '#C62835', '#7F1D2A'];
const NOTAS_COR = ['#C62835', '#E58A8F', '#B8BEC7', '#6FA8A8', '#2E8B8B'];
const MESES = ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez'];

function mes(am) { const [a, m] = am.split('-'); return MESES[+m - 1] + '/' + a.slice(2); }

const BASE = {
  font: { family: 'Inter, -apple-system, Segoe UI, Roboto, Arial, sans-serif',
          size: 12, color: '#1A1D21' },
  separators: ',.',
  paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
  margin: { l: 56, r: 20, t: 12, b: 52 },
  hoverlabel: { bgcolor: '#fff', bordercolor: '#D5DAE0', font: { size: 12.5 } },
  legend: { orientation: 'h', y: -0.18, x: 0 },
  bargap: 0.28
};
const EIXO = { gridcolor: GRADE, zerolinecolor: GRADE, linecolor: '#D5DAE0',
               automargin: true, title: { standoff: 10 } };
const CONFIG = { responsive: true, displayModeBar: false };

function eixo(extra) {
  const e = Object.assign({}, EIXO, extra || {});
  if (typeof e.title === 'string') e.title = { text: e.title, standoff: 10 };
  return e;
}
function desenhar(id, traces, extra) {
  extra = extra || {};
  const l = Object.assign({}, BASE, extra);
  l.xaxis = eixo(extra.xaxis); l.yaxis = eixo(extra.yaxis);
  Plotly.newPlot(id, traces, l, CONFIG);
}
const fmt = (v, c) => v.toLocaleString('pt-BR', { minimumFractionDigits: c || 0,
                                                maximumFractionDigits: c || 0 });

// Cada aba desenha seus graficos so na primeira vez em que fica visivel.
// Desenhar em aba oculta faz o Plotly calcular a largura errada.
const DESENHOS = {};

// ----------------------------------------------------------------- Contexto
DESENHOS['aba-geral'] = () => {
  const meses = D.sazonalidade.meses.map(mes);
  desenhar('g_sazonalidade', [{
    x: meses, y: D.sazonalidade.pedidos, type: 'scatter', mode: 'lines+markers',
    line: { color: AZUL, width: 2.5 },
    marker: { size: 5 }, fill: 'tozeroy', fillcolor: 'rgba(31,78,121,0.07)',
    hovertemplate: '%{x}<br><b>%{y:,.0f} pedidos</b><extra></extra>'
  }], { xaxis: { type: 'category', tickangle: -45, nticks: 14 },
        yaxis: { title: 'Pedidos', tickformat: ',.0f' },
        annotations: [{ x: 'nov/17', y: Math.max.apply(null, D.sazonalidade.pedidos),
          text: 'Black Friday', showarrow: true, arrowhead: 0, ax: -60, ay: -6,
          font: { size: 11.5, color: AZUL } }],
        shapes: [{ type: 'rect', xref: 'x', yref: 'paper',
          x0: meses.indexOf('jan/17') - 0.5, x1: meses.indexOf('ago/18') + 0.5,
          y0: 0, y1: 1, fillcolor: 'rgba(46,139,139,0.06)', line: { width: 0 } }] });

  desenhar('g_notas', [{
    x: D.notas.rotulos, y: D.notas.avaliacoes, type: 'bar',
    marker: { color: NOTAS_COR },
    text: D.notas.percentual.map(v => fmt(v, 1) + '%'), textposition: 'outside',
    cliponaxis: false,
    hovertemplate: '%{x}<br><b>%{y:,.0f} avaliações</b><extra></extra>'
  }], { yaxis: { title: 'Avaliações', tickformat: ',.0f' } });

  desenhar('g_status', [{
    y: D.status.rotulos.slice().reverse(), x: D.status.percentual.slice().reverse(),
    type: 'bar', orientation: 'h',
    marker: { color: D.status.rotulos.slice().reverse().map(
      s => s === 'delivered' ? VERDE : CINZA) },
    text: D.status.percentual.slice().reverse().map(v => fmt(v, 2) + '%'),
    textposition: 'outside', cliponaxis: false,
    hovertemplate: '%{y}<br><b>%{x:.2f}%</b><extra></extra>'
  }], { xaxis: { title: '% dos pedidos (escala logarítmica)', type: 'log' },
        margin: { l: 90, r: 50, t: 12, b: 52 } });

  desenhar('g_pagamentos', [
    { x: D.pagamentos.rotulos, y: D.pagamentos.pct_registros, type: 'bar',
      name: '% dos registros', marker: { color: AZUL },
      hovertemplate: '%{x}<br><b>%{y:.1f}%</b> dos registros<extra></extra>' },
    { x: D.pagamentos.rotulos, y: D.pagamentos.pct_valor, type: 'bar',
      name: '% do valor pago', marker: { color: TEAL },
      hovertemplate: '%{x}<br><b>%{y:.1f}%</b> do valor<extra></extra>' }
  ], { barmode: 'group', yaxis: { title: 'Percentual', ticksuffix: '%' } });
};

// ---------------------------------------------------------------- Logistica
DESENHOS['aba-logistica'] = () => {
  const meses = D.logistica_mensal.meses.map(mes);
  desenhar('g_prazo', [
    { x: meses, y: D.logistica_mensal.prazo_estimado, type: 'scatter',
      mode: 'lines', name: 'Prazo prometido',
      line: { color: CINZA, width: 2, dash: 'dot' },
      hovertemplate: '%{x}<br>Prometido: <b>%{y:.1f} dias</b><extra></extra>' },
    { x: meses, y: D.logistica_mensal.tempo_real, type: 'scatter',
      mode: 'lines+markers', name: 'Tempo real', fill: 'tonexty',
      fillcolor: 'rgba(46,139,139,0.10)',
      line: { color: AZUL, width: 2.5 }, marker: { size: 5 },
      hovertemplate: '%{x}<br>Real: <b>%{y:.1f} dias</b><extra></extra>' }
  ], { xaxis: { type: 'category', tickangle: -45, nticks: 14 },
       yaxis: { title: 'Dias desde a compra', rangemode: 'tozero' } });

  desenhar('g_histograma', [{
    x: D.histograma_entrega.x, y: D.histograma_entrega.y, type: 'bar',
    marker: { color: AZUL }, width: D.histograma_entrega.largura * 0.92,
    hovertemplate: 'cerca de %{x:.0f} dias<br><b>%{y:,.0f} pedidos</b><extra></extra>'
  }], { xaxis: { title: 'Dias entre a compra e a entrega' },
        yaxis: { title: 'Pedidos', tickformat: ',.0f' }, bargap: 0 });

  desenhar('g_pct_atraso', [{
    x: meses, y: D.logistica_mensal.pct_atraso, type: 'bar',
    marker: { color: D.logistica_mensal.pct_atraso.map(v => v > 10 ? VERM : '#9DB8CF') },
    hovertemplate: '%{x}<br><b>%{y:.1f}%</b> atrasados<extra></extra>'
  }], { xaxis: { type: 'category', tickangle: -45, nticks: 14 },
        yaxis: { title: '% de entregas atrasadas', ticksuffix: '%' },
        shapes: [{ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: 10, y1: 10,
                   line: { color: VERM, width: 1, dash: 'dot' } }] });
};

// ----------------------------------------------------------------------- H1
DESENHOS['aba-h1'] = () => {
  const dias = D.h1_por_dia.dias, nota = D.h1_por_dia.nota;
  desenhar('g_h1_dia', [{
    x: dias, y: nota, type: 'scatter', mode: 'lines+markers',
    line: { color: AZUL, width: 2.5 },
    marker: { size: 5, color: dias.map(d => d > 0 ? VERM : AZUL) },
    customdata: D.h1_por_dia.pedidos,
    hovertemplate: '%{x} dias<br>Nota média <b>%{y:.2f}</b>' +
                   '<br>%{customdata:,.0f} pedidos<extra></extra>'
  }], { xaxis: { title: 'Dias em relação ao prazo (negativo = antes)',
                 zeroline: false },
        yaxis: { title: 'Nota média', range: [1, 4.7] },
        shapes: [
          { type: 'rect', xref: 'x', yref: 'paper', x0: 1.5, x1: 4.5, y0: 0, y1: 1,
            fillcolor: 'rgba(198,40,53,0.08)', line: { width: 0 } },
          { type: 'line', x0: 0, x1: 0, yref: 'paper', y0: 0, y1: 1,
            line: { color: '#5A6472', width: 1.2, dash: 'dash' } }],
        annotations: [
          { x: 0, y: 4.62, text: 'prazo prometido', showarrow: false,
            xanchor: 'right', xshift: -6, font: { size: 11, color: '#5A6472' } },
          { x: 3, y: 4.62, text: '<b>ruptura</b>: 2º ao 4º dia', showarrow: false,
            xanchor: 'left', xshift: 4, font: { size: 11.5, color: VERM } }] });

  desenhar('g_h1_faixa', [{
    x: D.h1.faixas, y: D.h1.nota_media, type: 'bar', marker: { color: GRAVIDADE },
    text: D.h1.nota_media.map(v => fmt(v, 2)), textposition: 'outside',
    cliponaxis: false, customdata: D.h1.pedidos,
    hovertemplate: '%{x}<br>Nota média <b>%{y:.2f}</b>' +
                   '<br>%{customdata:,.0f} pedidos<extra></extra>'
  }], { yaxis: { title: 'Nota média', range: [0, 5.2] } });

  desenhar('g_h1_ruim', [{
    x: D.h1.faixas, y: D.h1.pct_ruim, type: 'bar', marker: { color: GRAVIDADE },
    text: D.h1.pct_ruim.map(v => fmt(v, 1) + '%'), textposition: 'outside',
    cliponaxis: false,
    hovertemplate: '%{x}<br><b>%{y:.1f}%</b> com nota 1 ou 2<extra></extra>'
  }], { yaxis: { title: '% com nota 1 ou 2', ticksuffix: '%', range: [0, 92] } });

  const nomes = Object.keys(D.h1_composicao.series);
  desenhar('g_h1_composicao', nomes.map((n, i) => ({
    y: D.h1_composicao.faixas.slice().reverse(),
    x: D.h1_composicao.series[n].slice().reverse(),
    type: 'bar', orientation: 'h', name: n, marker: { color: NOTAS_COR[i] },
    text: D.h1_composicao.series[n].slice().reverse().map(v => v >= 8 ? fmt(v, 0) + '%' : ''),
    textposition: 'inside', insidetextanchor: 'middle',
    textfont: { color: '#fff', size: 11 },
    hovertemplate: '%{y}<br>' + n + ': <b>%{x:.1f}%</b><extra></extra>'
  })), { barmode: 'stack', xaxis: { title: '% das avaliações', ticksuffix: '%',
         range: [0, 100] }, margin: { l: 110, r: 20, t: 12, b: 52 },
         legend: { orientation: 'h', y: -0.22, x: 0, traceorder: 'normal' } });
};

// ----------------------------------------------------------------------- H2
DESENHOS['aba-h2'] = () => {
  const QUADRANTES = {
    'Sustenta o faturamento': VERDE,
    'Atenção: receita alta, nota abaixo da mediana': VERM,
    'Potencial de crescimento': TEAL,
    'Baixa prioridade': CINZA
  };
  const disp = D.h2.dispersao;
  const mediana = arr => { const s = arr.slice().sort((a, b) => a - b), m = s.length >> 1;
                           return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
  const corteReceita = mediana(disp.receita), corteNota = mediana(disp.nota);
  const traces = Object.keys(QUADRANTES).map(q => {
    const idx = disp.quadrante.map((v, i) => v === q ? i : -1).filter(i => i >= 0);
    return {
      x: idx.map(i => disp.receita[i]), y: idx.map(i => disp.nota[i]),
      text: idx.map(i => disp.categorias[i]),
      customdata: idx.map(i => [disp.pedidos[i], disp.pct_atraso[i]]),
      mode: 'markers', type: 'scatter', name: q,
      marker: { color: QUADRANTES[q], size: idx.map(i => disp.pedidos[i]),
                sizemode: 'area', sizeref: 2 * Math.max.apply(null, disp.pedidos) / (36 ** 2),
                sizemin: 5, opacity: 0.75, line: { color: '#fff', width: 1 } },
      hovertemplate: '<b>%{text}</b><br>Receita R$ %{x:,.0f}<br>Nota %{y:.2f}' +
                     '<br>%{customdata[0]:,.0f} pedidos' +
                     '<br>%{customdata[1]:.1f}% atrasados<extra></extra>'
    };
  });
  const destaque = ['office_furniture', 'bed_bath_table', 'health_beauty', 'watches_gifts']
    .map(c => disp.categorias.indexOf(c)).filter(i => i >= 0)
    .map(i => ({ x: Math.log10(disp.receita[i]), y: disp.nota[i], text: disp.categorias[i],
                 showarrow: false, yshift: -14, font: { size: 10.5, color: '#3A424D' } }));
  desenhar('g_h2_dispersao', traces, {
    xaxis: { title: 'Receita (R$, escala logarítmica)', type: 'log' },
    yaxis: { title: 'Nota média' },
    legend: { orientation: 'h', y: -0.2, x: 0 },
    margin: { l: 56, r: 20, t: 12, b: 70 },
    shapes: [
      { type: 'line', xref: 'x', yref: 'paper', x0: corteReceita, x1: corteReceita,
        y0: 0, y1: 1, line: { color: '#B8BEC7', width: 1, dash: 'dot' } },
      { type: 'line', xref: 'paper', x0: 0, x1: 1, y0: corteNota, y1: corteNota,
        line: { color: '#B8BEC7', width: 1, dash: 'dot' } }],
    annotations: destaque
  });

  desenhar('g_h2_pareto', [{
    x: D.h2.pareto.posicao, y: D.h2.pareto.acumulado, type: 'scatter', mode: 'lines',
    line: { color: AZUL, width: 2.5 }, fill: 'tozeroy', fillcolor: 'rgba(31,78,121,0.07)',
    text: D.h2.pareto.categorias,
    hovertemplate: '%{x}ª categoria (%{text})<br><b>%{y:.1f}%</b> da receita acumulada<extra></extra>'
  }], { xaxis: { title: 'Categorias ordenadas por receita' },
        yaxis: { title: '% acumulado da receita', ticksuffix: '%', range: [0, 102] },
        shapes: [{ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: 80, y1: 80,
                   line: { color: VERM, width: 1.2, dash: 'dash' } },
                 { type: 'line', x0: D.h2.categorias_80, x1: D.h2.categorias_80,
                   yref: 'paper', y0: 0, y1: 1, line: { color: VERM, width: 1.2, dash: 'dash' } }],
        annotations: [{ x: D.h2.categorias_80, y: 80, text: D.h2.categorias_80 +
                        ' categorias = 80% da receita', showarrow: false, xanchor: 'left',
                        yanchor: 'top', xshift: 6, yshift: -4, font: { size: 11.5, color: VERM } }] });

  const barrasH = (id, cats, vals, nota, cor, rotulo, fmtx) => desenhar(id, [{
    y: cats.slice().reverse(), x: vals.slice().reverse(), type: 'bar', orientation: 'h',
    marker: { color: cor }, customdata: nota.slice().reverse(),
    hovertemplate: '%{y}<br><b>' + fmtx + '</b> ' + rotulo +
                   '<br>Nota média %{customdata:.2f}<extra></extra>'
  }], { margin: { l: 160, r: 20, t: 12, b: 50 },
        xaxis: { title: rotulo.charAt(0).toUpperCase() + rotulo.slice(1),
                 tickformat: ',.0f' } });
  barrasH('g_h2_receita', D.h2.top_receita.categorias, D.h2.top_receita.receita,
          D.h2.top_receita.nota, AZUL, 'receita (R$)', 'R$ %{x:,.0f}');
  barrasH('g_h2_pedidos', D.h2.top_pedidos.categorias, D.h2.top_pedidos.pedidos,
          D.h2.top_pedidos.nota, TEAL, 'pedidos', '%{x:,.0f}');
};

// ---------------------------------------------------------------- Geografia
DESENHOS['aba-geografia'] = () => {
  if (D.h1_uf && document.getElementById('g_uf')) {
    const u = D.h1_uf, maxp = Math.max.apply(null, u.pedidos);
    desenhar('g_uf', [{
      x: u.pct_atraso, y: u.nota_media, text: u.uf, type: 'scatter',
      mode: 'markers+text', textposition: 'top right',
      textfont: { size: 10.5, color: '#3A424D' },
      customdata: u.pedidos.map((p, i) => [p, u.tempo_entrega_medio[i]]),
      marker: { size: u.pedidos, sizemode: 'area', sizeref: 2 * maxp / (40 ** 2),
                sizemin: 6, color: u.pct_atraso,
                colorscale: [[0, '#2E8B8B'], [0.5, '#E0B03A'], [1, '#C62835']],
                opacity: 0.8, line: { color: '#fff', width: 1 } },
      hovertemplate: '<b>%{text}</b><br>%{x:.1f}% atrasados<br>Nota %{y:.2f}' +
                     '<br>Entrega média %{customdata[1]:.1f} dias' +
                     '<br>%{customdata[0]:,.0f} pedidos<extra></extra>'
    }], { xaxis: { title: '% de entregas atrasadas', ticksuffix: '%' },
          yaxis: { title: 'Nota média' } });
  }

  desenhar('g_geografia', [
    { x: D.geografia.uf, y: D.geografia.pct_clientes, type: 'bar',
      name: '% dos clientes', marker: { color: AZUL },
      hovertemplate: '%{x}<br><b>%{y:.1f}%</b> dos clientes<extra></extra>' },
    { x: D.geografia.uf, y: D.geografia.pct_vendedores, type: 'bar',
      name: '% dos vendedores', marker: { color: AMBAR },
      hovertemplate: '%{x}<br><b>%{y:.1f}%</b> dos vendedores<extra></extra>' }
  ], { barmode: 'group', yaxis: { title: 'Percentual', ticksuffix: '%' } });

  desenhar('g_concentracao', [
    { x: D.concentracao.pct_vendedores, y: D.concentracao.pct_receita, type: 'scatter',
      mode: 'lines', name: 'Distribuição real', line: { color: AZUL, width: 2.5 },
      fill: 'tozeroy', fillcolor: 'rgba(31,78,121,0.07)',
      hovertemplate: '%{x:.1f}% dos vendedores<br><b>%{y:.1f}% da receita</b><extra></extra>' },
    { x: [0, 100], y: [0, 100], type: 'scatter', mode: 'lines',
      name: 'Se todos vendessem igual', line: { color: CINZA, width: 1.5, dash: 'dash' },
      hoverinfo: 'skip' }
  ], { xaxis: { title: '% acumulado de vendedores', ticksuffix: '%' },
       yaxis: { title: '% acumulado da receita', ticksuffix: '%' } });
};

// ----------------------------------------------------------------------- Abas
const botoes = Array.from(document.querySelectorAll('nav button'));
const desenhadas = new Set();
function abrir(id, rolar) {
  if (!document.getElementById(id)) id = 'aba-geral';
  botoes.forEach(b => b.classList.toggle('ativo', b.dataset.aba === id));
  document.querySelectorAll('.aba').forEach(a => a.classList.toggle('ativa', a.id === id));
  if (!desenhadas.has(id) && DESENHOS[id]) { DESENHOS[id](); desenhadas.add(id); }
  else document.querySelectorAll('#' + id + ' .grafico').forEach(g => Plotly.Plots.resize(g));
  if (history.replaceState) history.replaceState(null, '', '#' + id.replace('aba-', ''));
  if (rolar) window.scrollTo({ top: document.querySelector('nav').offsetTop, behavior: 'smooth' });
}
botoes.forEach(b => b.addEventListener('click', () => abrir(b.dataset.aba, true)));
document.querySelectorAll('[data-ir]').forEach(b =>
  b.addEventListener('click', () => abrir(b.dataset.ir, true)));
abrir('aba-' + (location.hash.slice(1) || 'geral'), false);
"""
    )


def _kpi(rotulo: str, valor: str, nota: str = "", tom: str = "") -> str:
    extra = f'<div class="nota">{nota}</div>' if nota else ""
    classe = f"kpi {tom}".strip()
    return (
        f'<div class="{classe}"><div class="rotulo">{rotulo}</div>'
        f'<div class="valor">{valor}</div>{extra}</div>'
    )


def _grafico(id_elemento: str, titulo: str, subtitulo: str, alto: bool = False) -> str:
    classe = "grafico alto" if alto else "grafico"
    return (
        f'<div class="cartao"><h3>{titulo}</h3><p class="sub">{subtitulo}</p>'
        f'<div id="{id_elemento}" class="{classe}"></div></div>'
    )


def _abertura(pergunta: str, resposta: str) -> str:
    return (
        f'<div class="abertura"><div class="pergunta">{pergunta}</div>'
        f"<h2>{resposta}</h2></div>"
    )


def _proxima(aba: str, rotulo: str) -> str:
    return f'<div class="proxima"><button data-ir="{aba}">{rotulo} &rarr;</button></div>'


def _milhoes(valor: float) -> str:
    return "R$ " + formato.decimal(valor / 1e6, 2) + " mi"


def gerar(
    tabelas: dict[str, pd.DataFrame],
    resultado_eda: dict,
    resultado_h1: dict,
    resultado_h2: dict,
    caminho: Path | None = None,
) -> Path:
    """Monta o arquivo dashboard.html e devolve o caminho gerado."""
    caminho = Path(caminho) if caminho is not None else config.CAMINHO_DASHBOARD
    caminho.parent.mkdir(parents=True, exist_ok=True)

    dados = construir_dados(tabelas, resultado_eda, resultado_h1, resultado_h2)
    caminho.write_text(renderizar(dados), encoding="utf-8")
    return caminho


def renderizar(dados: dict) -> str:
    """Transforma o pacote de dados no HTML final.

    Separado de gerar() para que o layout possa ser refeito a partir do JSON
    embutido em um dashboard ja publicado, sem rodar o pipeline de novo.
    """
    k = dados["kpis"]
    log = dados["logistica_resumo"]
    h1 = dados["h1"]
    h2 = dados["h2"]
    uf = dados.get("h1_uf")

    milhar = formato.numero
    reais = formato.moeda
    dec = formato.decimal
    pct = formato.percentual

    # Valores usados no texto de abertura de cada aba
    nota_prazo = h1["nota_media"][0]
    nota_atraso_media = None
    pedidos_atrasados = sum(h1["pedidos"][1:])
    if pedidos_atrasados:
        nota_atraso_media = sum(
            n * p for n, p in zip(h1["nota_media"][1:], h1["pedidos"][1:])
        ) / pedidos_atrasados
    dia = dict(zip(dados["h1_por_dia"]["dias"], dados["h1_por_dia"]["nota"]))
    nota_dia1 = dia.get(1)
    nota_dia4 = dia.get(4)
    ruim_8mais = h1["pct_ruim"][3]

    # Tabelas ------------------------------------------------------------
    linhas_modelo = "".join(
        f"<tr><td><code>{m['tabela']}</code></td>"
        f"<td class='num'>{milhar(m['linhas'])}</td>"
        f"<td class='num'>{m['colunas']}</td>"
        f"<td class='num'>{milhar(m['nulos'])}</td>"
        f"<td class='num'>{milhar(m['duplicadas'])}</td>"
        f"<td>{m['chave_primaria']}</td></tr>"
        for m in dados["modelo"]
    )

    linhas_integridade = "".join(
        f"<tr><td><code>{i['tabela_filha']}.{i['coluna']}</code></td>"
        f"<td><code>{i['tabela_pai']}</code></td>"
        f"<td class='num'>{milhar(i['registros'])}</td>"
        f"<td class='num'>{milhar(i['orfaos'])}</td>"
        f"<td><span class='tag {'ok' if i['orfaos'] == 0 else 'atencao'}'>"
        f"{'íntegro' if i['orfaos'] == 0 else 'atenção'}</span></td></tr>"
        for i in dados["integridade"]
    )

    linhas_cortes = "".join(
        f"<tr><td>{c['corte']} dos vendedores</td>"
        f"<td class='num'>{milhar(c['vendedores'])}</td>"
        f"<td class='num'>{pct(c['pct_receita'])}</td></tr>"
        for c in dados["concentracao"]["cortes"]
    )

    maior_ruim = max(h1["pct_ruim"]) or 1
    linhas_faixa = "".join(
        f"<tr><td>{h1['faixas'][i]}</td>"
        f"<td class='num'>{milhar(h1['pedidos'][i])}</td>"
        f"<td class='num'>{pct(h1['pct_pedidos'][i])}</td>"
        f"<td class='num'><strong>{dec(h1['nota_media'][i])}</strong></td>"
        f"<td class='num'><span class='barra' style='width:{round(60 * h1['pct_ruim'][i] / maior_ruim)}px'></span>"
        f"{pct(h1['pct_ruim'][i])}</td>"
        f"<td class='num'>{pct(h1['pct_boa'][i])}</td></tr>"
        for i in range(len(h1["faixas"]))
    )

    kruskal = ""
    if "kruskal_p" in h1["testes"]:
        p = h1["testes"]["kruskal_p"]
        p_texto = "p < 0,001" if p < 0.001 else f"p = {p:.4f}".replace(".", ",")
        kruskal = (
            f" O teste de Kruskal-Wallis entre as cinco faixas resulta em "
            f"H = {milhar(h1['testes']['kruskal_h'])} e {p_texto}, o que indica que "
            f"as diferenças entre as faixas não são fruto do acaso."
        )

    # Bloco de estados, presente quando o pipeline gerou a analise por UF
    bloco_uf = ""
    destaque_uf = ""
    if uf:
        pior = max(range(len(uf["uf"])), key=lambda i: uf["pct_atraso"][i])
        sp = uf["uf"].index("SP") if "SP" in uf["uf"] else None
        comparacao = ""
        if sp is not None:
            comparacao = (
                f" Em {uf['uf'][pior]}, {pct(uf['pct_atraso'][pior], 0)} dos pedidos "
                f"chegam atrasados e a nota média é {dec(uf['nota_media'][pior])}; "
                f"em SP, onde estão os vendedores, são {pct(uf['pct_atraso'][sp], 0)} "
                f"e {dec(uf['nota_media'][sp])}."
            )
        spearman_uf = h1["testes"].get("spearman_uf_atraso_nota")
        texto_spearman = ""
        if spearman_uf is not None:
            texto_spearman = (
                f"(Spearman = <strong>{dec(spearman_uf, 2)}</strong> entre os "
                f"{len(uf['uf'])} estados)"
            )
        bloco_uf = f"""
  {_grafico("g_uf", "Atraso e nota média por estado do cliente",
            "Cada círculo é um estado, com tamanho proporcional ao número de pedidos. Quanto mais à direita, mais atraso.", alto=True)}
  <div class="achado alerta">
    <span>Quanto maior o atraso no estado, menor a nota
    {texto_spearman}.{comparacao}
    A distância até os vendedores aparece no atraso, e o atraso aparece na nota.</span>
  </div>"""
        destaque_uf = (
            f'<div class="destaque"><div class="v">{pct(uf["pct_atraso"][pior], 0)}</div>'
            f'<div class="r">dos pedidos atrasam em {uf["uf"][pior]}, contra '
            f'{pct(uf["pct_atraso"][sp], 0) if sp is not None else "-"} em SP</div></div>'
        )

    destaques = (
        f'<div class="destaque"><div class="v">{milhar(k["pedidos"])}</div>'
        f'<div class="r">pedidos entre {k["periodo_inicio"][3:]} e {k["periodo_fim"][3:]}</div></div>'
        f'<div class="destaque"><div class="v">{dec(nota_prazo)} &rarr; '
        f'{dec(nota_atraso_media) if nota_atraso_media else "-"}</div>'
        f'<div class="r">nota média no prazo contra pedidos atrasados</div></div>'
        f'<div class="destaque"><div class="v">{pct(ruim_8mais, 0)}</div>'
        f'<div class="r">de notas 1 ou 2 quando o atraso passa de uma semana</div></div>'
    )
    destaques += destaque_uf or (
        f'<div class="destaque"><div class="v">{h2["categorias_80"]}</div>'
        f'<div class="r">categorias concentram 80% da receita</div></div>'
    )

    linha_spearman_uf = ""
    if "spearman_uf_atraso_nota" in h1["testes"]:
        linha_spearman_uf = (
            "<tr><td>% de atraso e nota, entre estados</td>"
            f"<td class='num'>{dec(h1['testes']['spearman_uf_atraso_nota'], 3)}</td>"
            "<td>negativa e forte</td></tr>"
        )

    abertura_h1 = (
        f"A nota se mantém até o 1º dia de atraso ({dec(nota_dia1)}) e despenca a "
        f"partir do 4º ({dec(nota_dia4)})."
        if nota_dia1 is not None and nota_dia4 is not None
        else "Quanto maior o atraso, menor a nota."
    )

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Dashboard Olist | Projeto Aplicado 1 - Grupo 10</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap">
<script src="{PLOTLY_CDN}"></script>
<style>{CSS}</style>
</head>
<body>

<header>
  <div class="topo">
    <div class="selo">Projeto Aplicado 1 &middot; Grupo 10 &middot; Banco de Dados &middot; Mackenzie</div>
    <h1>O cliente da Olist tolera a espera, mas não a promessa quebrada</h1>
    <p class="tese">Análise de {milhar(k['pedidos'])} pedidos do e-commerce brasileiro: o atraso
      em relação ao prazo prometido é o que mais derruba a satisfação, e o efeito se
      concentra em poucas regiões, categorias e vendedores.</p>
    <div class="destaques">{destaques}</div>
    <div class="meta">Base: Brazilian E-Commerce Public Dataset by Olist (Kaggle, CC BY-NC-SA 4.0)
      &middot; Pedidos de {k['periodo_inicio']} a {k['periodo_fim']} &middot; Gerado em {dados['gerado_em']}</div>
  </div>
</header>

<nav><div class="trilho">
  <button data-aba="aba-geral"><span class="n">1</span>Contexto</button>
  <button data-aba="aba-logistica"><span class="n">2</span>Logística</button>
  <button data-aba="aba-h1"><span class="n">3</span>H1 &middot; Atraso e satisfação</button>
  <button data-aba="aba-h2"><span class="n">4</span>H2 &middot; Categorias</button>
  <button data-aba="aba-geografia"><span class="n">5</span>Geografia e concentração</button>
  <button data-aba="aba-modelo"><span class="n">i</span>Dados e método</button>
</div></nav>

<main class="conteudo">

<!-- ================================================== 1. CONTEXTO -->
<section id="aba-geral" class="aba">
  {_abertura("Como é o negócio analisado", "Um marketplace que cresceu ao longo de 2017 e entrega bem na maior parte do tempo.")}
  <div class="kpis">
    {_kpi("Pedidos", milhar(k['pedidos']), f"{pct(k['pct_entregues'])} entregues")}
    {_kpi("Clientes únicos", milhar(k['clientes_unicos']), f"em {milhar(k['pedidos'])} identificadores")}
    {_kpi("Vendedores", milhar(k['vendedores']), f"{milhar(k['produtos'])} produtos")}
    {_kpi("Receita de produtos", _milhoes(k['receita_itens']), f"frete à parte: {_milhoes(k['frete_total'])}")}
    {_kpi("Ticket médio", reais(k['ticket_medio']), f"mediana {reais(k['ticket_mediano'])}")}
    {_kpi("Nota média", dec(k['nota_media']), f"{milhar(k['avaliacoes'])} avaliações", "bom")}
  </div>

  {_grafico("g_sazonalidade", "Pedidos por mês",
            "A faixa sombreada marca o período consistente, de janeiro de 2017 a agosto de 2018. Fora dele a série é incompleta: 2016 tem 329 pedidos e setembro e outubro de 2018 somam 20.")}

  <div class="achado">
    <span>O volume cresce ao longo de 2017, tem pico em <strong>novembro (Black Friday)</strong>
    e se estabiliza entre 6 mil e 7,3 mil pedidos mensais em 2018.</span>
  </div>

  <div class="grade2">
    {_grafico("g_notas", "Distribuição das notas",
              "Notas de 1 a 5 da pesquisa enviada após a entrega.")}
    {_grafico("g_status", "Status dos pedidos",
              "Escala logarítmica, porque 97% dos pedidos estão em um único status.")}
  </div>

  {_grafico("g_pagamentos", "Formas de pagamento",
            "Participação de cada forma no número de registros e no valor total pago.")}

  <div class="achado">
    <span>O cartão de crédito responde por <strong>{pct(dados['pagamentos']['pct_registros'][0], 1)}
    dos registros e {pct(dados['pagamentos']['pct_valor'][0], 1)} do valor</strong>, com média de
    {dec(dados['pagamentos']['parcelas'][0])} parcelas. As demais formas são sempre à vista.</span>
  </div>
  {_proxima("aba-logistica", "Próximo: logística")}
</section>

<!-- ================================================== 2. LOGÍSTICA -->
<section id="aba-logistica" class="aba">
  {_abertura("A Olist cumpre o prazo que promete?",
             f"Na média, sim: promete {dec(log['prazo_medio'], 0)} dias e entrega em {dec(log['tempo_medio'], 0)}. Mas {pct(log['pct_atraso'])} dos pedidos ainda chegam atrasados.")}
  <div class="kpis">
    {_kpi("Tempo médio de entrega", f"{dec(log['tempo_medio'], 1)} dias", f"mediana de {dec(log['tempo_mediano'], 0)} dias")}
    {_kpi("Prazo prometido médio", f"{dec(log['prazo_medio'], 1)} dias", f"folga média de {dec(log['folga_media'], 1)} dias")}
    {_kpi("Entregas atrasadas", pct(log['pct_atraso']), log['criterio_adotado'], "ruim")}
    {_kpi("Pior caso registrado", f"{dec(log['tempo_maximo'], 0)} dias", "entre a compra e a entrega")}
  </div>

  {_grafico("g_prazo", "Prazo prometido contra tempo real, por mês",
            "A área entre as linhas é a folga que a plataforma embute na promessa de entrega.")}

  <div class="achado">
    <span>A folga média é de <strong>{dec(log['folga_media'], 1)} dias</strong>. Ela protege o
    índice de pontualidade, mas pode custar conversão: um prazo anunciado de
    {dec(log['prazo_medio'], 0)} dias afasta o comprador que receberia em {dec(log['tempo_medio'], 0)}.</span>
  </div>

  <div class="grade2">
    {_grafico("g_histograma", "Distribuição do tempo de entrega",
              f"Dias entre a compra e a entrega, truncado em {config.CORTE_HISTOGRAMA_DIAS} dias para não achatar o gráfico.")}
    {_grafico("g_pct_atraso", "Entregas atrasadas por mês",
              "Meses acima de 10% em vermelho. A linha pontilhada marca 10%.")}
  </div>

  <div class="achado metodo">
    <span><strong>Critério de atraso.</strong> O campo
    <code>order_estimated_delivery_date</code> registra apenas a data, sempre à 00:00, enquanto
    <code>order_delivered_customer_date</code> registra data e hora. O projeto adota a
    {log['criterio_adotado']}, que trata o prazo como vencido à meia-noite e resulta em
    {pct(log['pct_atraso'])} de atrasos. Pela {log['criterio_alternativo']}, seriam
    {pct(log['pct_atraso_alternativo'])}. A diferença é de {milhar(log['pedidos_divergentes'])}
    pedidos, e o critério adotado é o mais conservador.</span>
  </div>
  {_proxima("aba-h1", "Próximo: o efeito do atraso na nota")}
</section>

<!-- ================================================== 3. H1 -->
<section id="aba-h1" class="aba">
  {_abertura("H1 · Quanto maior o atraso, menor a nota do cliente?", abertura_h1)}

  {_grafico("g_h1_dia", "Nota média por dia em relação ao prazo",
            "Dias com pelo menos 30 pedidos, de 30 dias antes a 30 dias depois do prazo. Chegar muito antes quase não melhora a nota; chegar alguns dias depois a destrói.", alto=True)}

  <div class="grade2">
    {_grafico("g_h1_faixa", "Nota média por faixa de atraso",
              "A queda é progressiva, não um degrau único entre no prazo e atrasado.")}
    {_grafico("g_h1_ruim", "Clientes insatisfeitos por faixa",
              "Percentual de avaliações com nota 1 ou 2.")}
  </div>

  {_grafico("g_h1_composicao", "Como o perfil de notas se inverte",
            "Cada barra soma 100% das avaliações daquela faixa.")}

  <div class="cartao">
    <h3>Resumo por faixa de atraso</h3>
    <p class="sub">Pedidos entregues e avaliados, classificados pelo atraso em relação ao prazo prometido.</p>
    <div class="tabela"><table>
      <thead><tr>
        <th>Faixa de atraso</th><th class="num">Pedidos</th>
        <th class="num">% do total</th><th class="num">Nota média</th>
        <th class="num">% nota 1 ou 2</th><th class="num">% nota 4 ou 5</th>
      </tr></thead>
      <tbody>{linhas_faixa}</tbody>
    </table></div>
  </div>

  <div class="achado">
    <span><strong>Conclusão.</strong> {h1['conclusao']}{kruskal}</span>
  </div>
  {_proxima("aba-h2", "Próximo: onde isso pesa na receita")}
</section>

<!-- ================================================== 4. H2 -->
<section id="aba-h2" class="aba">
  {_abertura("H2 · O desempenho muda conforme a categoria?",
             f"Muda, e as lideranças não coincidem. {h2['categorias_80']} categorias fazem 80% da receita, e várias delas ficam abaixo da nota mediana.")}
  <div class="kpis">
    {_kpi("Categorias analisadas", str(h2['total_categorias']), f"{len(h2['dispersao']['categorias'])} com 100 ou mais pedidos")}
    {_kpi("Concentração da receita", f"{h2['categorias_80']} categorias", "respondem por 80% do total")}
    {_kpi("Melhor nota média", dec(h2['melhor_nota']['nota']), h2['melhor_nota']['categoria'], "bom")}
    {_kpi("Pior nota média", dec(h2['pior_nota']['nota']), h2['pior_nota']['categoria'], "ruim")}
  </div>

  {_grafico("g_h2_dispersao", "Receita contra nota média, por categoria",
            "Categorias com 100 pedidos ou mais. As linhas pontilhadas são as medianas de receita e de nota, que definem os quadrantes. O tamanho do círculo é o número de pedidos.", alto=True)}

  <div class="achado alerta">
    <span>O quadrante vermelho reúne categorias que <strong>faturam muito e ficam abaixo da nota
    mediana</strong>. É onde uma melhoria de entrega e de experiência protege mais receita.</span>
  </div>

  <div class="grade2">
    {_grafico("g_h2_receita", "Top 10 categorias por receita",
              "Soma do preço dos itens, sem frete.")}
    {_grafico("g_h2_pedidos", "Top 10 categorias por número de pedidos",
              "Pedidos distintos com ao menos um item da categoria.")}
  </div>

  {_grafico("g_h2_pareto", "Curva de Pareto da receita por categoria",
            "Percentual acumulado da receita, somando as categorias da maior para a menor.")}

  <div class="achado">
    <span><strong>Conclusão.</strong> {h2['conclusao']}</span>
  </div>
  {_proxima("aba-geografia", "Próximo: geografia e concentração")}
</section>

<!-- ================================================== 5. GEOGRAFIA -->
<section id="aba-geografia" class="aba">
  {_abertura("Por que o atraso não é igual para todos?",
             f"Vendedores e compradores estão em lugares diferentes. SP tem {pct(dados['geografia']['pct_vendedores'][0], 0)} dos vendedores e {pct(dados['geografia']['pct_clientes'][0], 0)} dos clientes.")}
  {bloco_uf}

  {_grafico("g_geografia", "Clientes e vendedores por estado",
            "Doze estados com mais clientes, em percentual do total de cada grupo.")}

  <div class="achado">
    <span>Os estados do Nordeste <strong>compram muito mais do que vendem</strong> na plataforma, o que
    aumenta a distância das entregas e dialoga com o ODS 10 discutido no trabalho.</span>
  </div>

  <div class="grade2">
    {_grafico("g_concentracao", "Concentração da receita entre vendedores",
              "Curva de Lorenz. Quanto mais longe da linha tracejada, mais concentrada.")}
    <div class="cartao">
      <h3>Cortes de concentração</h3>
      <p class="sub">Participação acumulada na receita de produtos.</p>
      <div class="tabela"><table>
        <thead><tr><th>Corte</th><th class="num">Vendedores</th>
          <th class="num">% da receita</th></tr></thead>
        <tbody>{linhas_cortes}</tbody>
      </table></div>
      <div class="achado" style="margin:14px 0 8px">
        <span>Poucos vendedores concentram a receita. Melhorar a entrega deles move a média da plataforma inteira.</span>
      </div>
    </div>
  </div>
  {_proxima("aba-modelo", "Ver dados e método")}
</section>

<!-- ================================================== DADOS E MÉTODO -->
<section id="aba-modelo" class="aba">
  {_abertura("Dados e método", "Nove arquivos CSV carregados em um banco SQLite com chaves primárias, estrangeiras e índices.")}
  <div class="cartao">
    <h3>Estrutura das tabelas</h3>
    <p class="sub">Linhas, colunas, valores nulos, duplicidades e chave primária adotada.</p>
    <div class="tabela"><table>
      <thead><tr><th>Tabela</th><th class="num">Linhas</th><th class="num">Colunas</th>
        <th class="num">Nulos</th><th class="num">Duplicadas</th>
        <th>Chave primária</th></tr></thead>
      <tbody>{linhas_modelo}</tbody>
    </table></div>
  </div>

  <div class="achado metodo">
    <span><strong>Decisão de modelagem.</strong> Em <code>order_reviews</code>, nem
    <code>review_id</code> nem <code>order_id</code> são únicos. São 99.224 linhas
    para 98.410 review_ids e 98.673 order_ids, o que obriga a chave composta
    <code>(review_id, order_id)</code>. A tabela <code>geolocation</code> não tem chave
    natural, e cerca de 26% das linhas são duplicadas integrais.</span>
  </div>

  <div class="grade2">
    <div class="cartao">
      <h3>Integridade referencial</h3>
      <p class="sub">Registros órfãos verificados antes da carga no banco.</p>
      <div class="tabela"><table>
        <thead><tr><th>Chave estrangeira</th><th>Referência</th>
          <th class="num">Registros</th><th class="num">Órfãos</th><th>Situação</th></tr></thead>
        <tbody>{linhas_integridade}</tbody>
      </table></div>
    </div>
    <div class="cartao">
      <h3>Correlações de Spearman</h3>
      <p class="sub">Adequada para a nota, que é ordinal, e para o tempo de entrega, que é assimétrico.
         O coeficiente do atraso parece modesto porque {milhar(h1['pct_pedidos'][0], 0)}% dos pedidos
         chegam no prazo e variam de antecedência sem variar de nota.</p>
      <div class="tabela"><table>
        <thead><tr><th>Par de variáveis</th><th class="num">Coeficiente</th><th>Leitura</th></tr></thead>
        <tbody>
          <tr><td>Tempo total de entrega e nota</td>
              <td class="num">{dec(dados['correlacoes']['tempo_nota'], 3)}</td>
              <td>negativa e moderada</td></tr>
          <tr><td>Dias de atraso e nota</td>
              <td class="num">{dec(dados['correlacoes']['atraso_nota'], 3)}</td>
              <td>negativa, diluída pelos pedidos no prazo</td></tr>
          <tr><td>Valor do frete e nota</td>
              <td class="num">{dec(dados['correlacoes']['frete_nota'], 3)}</td>
              <td>praticamente sem efeito</td></tr>
          {linha_spearman_uf}
        </tbody>
      </table></div>
    </div>
  </div>
</section>

</main>

<footer>
  Elaborado pelo Grupo 10 a partir do Brazilian E-Commerce Public Dataset by Olist,
  publicado no Kaggle sob licença CC BY-NC-SA 4.0.<br>
  Beatriz Resende Silva &middot; Mayara Laury Gonçalves de França &middot;
  Melissa Menchão Lima do Nascimento &middot; Otavio Prates dos Santos<br>
  <a href="https://github.com/melissalima308/mackenzie-grupo10-projeto-bd">Código no GitHub</a>
</footer>

<script>{_javascript(json.dumps(dados, ensure_ascii=False))}</script>
</body>
</html>
"""
