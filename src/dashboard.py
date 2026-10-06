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

from . import config

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

    dados["gerado_em"] = datetime.now().strftime("%d/%m/%Y às %H:%M")
    return dados


# ----------------------------------------------------------------------
# HTML
# ----------------------------------------------------------------------
CSS = """
:root {
  --azul: #1F4E79;
  --teal: #2E8B8B;
  --vermelho: #CE0E2D;
  --verde: #2E7D32;
  --ambar: #E8A33D;
  --texto: #1A1D21;
  --suave: #5A6472;
  --borda: #E3E6EA;
  --fundo: #F5F7FA;
  --cartao: #FFFFFF;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
               "Helvetica Neue", Arial, sans-serif;
  background: var(--fundo);
  color: var(--texto);
  line-height: 1.55;
}
header {
  background: linear-gradient(135deg, #1F4E79 0%, #2E8B8B 100%);
  color: #fff;
  padding: 32px 28px 26px;
}
header h1 { margin: 0 0 6px; font-size: 25px; letter-spacing: -0.3px; }
header p { margin: 0; opacity: 0.9; font-size: 14px; }
header .meta { margin-top: 14px; font-size: 12.5px; opacity: 0.82; }
.conteudo { max-width: 1280px; margin: 0 auto; padding: 0 20px 56px; }
nav {
  display: flex; gap: 6px; flex-wrap: wrap;
  background: var(--cartao); border-bottom: 1px solid var(--borda);
  padding: 0 20px; position: sticky; top: 0; z-index: 20;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
nav button {
  background: none; border: none; border-bottom: 3px solid transparent;
  padding: 14px 16px; font-size: 14px; font-weight: 600; color: var(--suave);
  cursor: pointer; font-family: inherit;
}
nav button:hover { color: var(--azul); }
nav button.ativo { color: var(--azul); border-bottom-color: var(--azul); }
.aba { display: none; }
.aba.ativa { display: block; }
.kpis {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 14px; margin: 24px 0 8px;
}
.kpi {
  background: var(--cartao); border: 1px solid var(--borda);
  border-radius: 10px; padding: 16px 18px;
}
.kpi .rotulo {
  font-size: 11.5px; text-transform: uppercase; letter-spacing: 0.6px;
  color: var(--suave); font-weight: 600;
}
.kpi .valor { font-size: 26px; font-weight: 700; margin-top: 6px; color: var(--azul); }
.kpi .nota { font-size: 12px; color: var(--suave); margin-top: 2px; }
.cartao {
  background: var(--cartao); border: 1px solid var(--borda);
  border-radius: 10px; padding: 18px 20px 10px; margin-top: 18px;
}
.cartao h3 { margin: 0 0 2px; font-size: 16px; }
.cartao .sub { margin: 0 0 10px; font-size: 13px; color: var(--suave); }
.grade2 { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
@media (max-width: 900px) { .grade2 { grid-template-columns: 1fr; } }
.grafico { width: 100%; height: 360px; }
.grafico.alto { height: 440px; }
.achado {
  border-left: 4px solid var(--azul); background: #EEF4F9;
  padding: 14px 18px; border-radius: 0 8px 8px 0; margin-top: 18px;
  font-size: 14.5px;
}
.achado.alerta { border-left-color: var(--vermelho); background: #FDEEF0; }
.achado strong { color: var(--azul); }
.achado.alerta strong { color: var(--vermelho); }
table { width: 100%; border-collapse: collapse; font-size: 13.5px; }
th, td { padding: 9px 12px; text-align: left; border-bottom: 1px solid var(--borda); }
th { background: #F0F3F7; font-weight: 600; font-size: 12.5px;
     text-transform: uppercase; letter-spacing: 0.4px; color: var(--suave); }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
.tag { display: inline-block; padding: 2px 9px; border-radius: 20px;
       font-size: 11.5px; font-weight: 600; }
.tag.ok { background: #E3F2E5; color: var(--verde); }
.tag.atencao { background: #FDEEF0; color: var(--vermelho); }
footer { text-align: center; padding: 28px 20px 40px; color: var(--suave);
         font-size: 12.5px; }
footer a { color: var(--azul); }
"""


def _javascript(dados_json: str) -> str:
    return (
        "const D = "
        + dados_json
        + """;

const AZUL = '#1F4E79', TEAL = '#2E8B8B', VERM = '#CE0E2D',
      VERDE = '#2E7D32', AMBAR = '#E8A33D', CINZA = '#8A8F98';
const SEQ = [AZUL, TEAL, VERM, AMBAR, '#6B4C9A', VERDE, '#5B7C99', '#B5651D'];

const LAYOUT = {
  font: { family: 'inherit', size: 12, color: '#1A1D21' },
  paper_bgcolor: 'rgba(0,0,0,0)',
  plot_bgcolor: 'rgba(0,0,0,0)',
  margin: { l: 60, r: 24, t: 16, b: 56 },
  xaxis: { gridcolor: '#E3E6EA', zerolinecolor: '#E3E6EA' },
  yaxis: { gridcolor: '#E3E6EA', zerolinecolor: '#E3E6EA' },
  hoverlabel: { bgcolor: '#fff', bordercolor: '#E3E6EA' },
  legend: { orientation: 'h', y: -0.2 }
};
const CONFIG = { responsive: true, displayModeBar: false, locale: 'pt-br' };

function layout(extra) { return Object.assign({}, LAYOUT, extra || {}); }
function desenhar(id, traces, extra) {
  Plotly.newPlot(id, traces, layout(extra), CONFIG);
}
function moeda(v) {
  return 'R$ ' + v.toLocaleString('pt-BR', { minimumFractionDigits: 2,
                                             maximumFractionDigits: 2 });
}

// ---------------------------------------------------------------- Visão geral
desenhar('g_sazonalidade', [{
  x: D.sazonalidade.meses, y: D.sazonalidade.pedidos,
  type: 'scatter', mode: 'lines+markers', name: 'Pedidos',
  line: { color: AZUL, width: 2.5 }, marker: { size: 5 },
  fill: 'tozeroy', fillcolor: 'rgba(31,78,121,0.08)',
  hovertemplate: '%{x}<br><b>%{y:,} pedidos</b><extra></extra>'
}], { yaxis: { title: 'Pedidos', gridcolor: '#E3E6EA' },
      xaxis: { tickangle: -45, gridcolor: '#E3E6EA' } });

desenhar('g_status', [{
  x: D.status.rotulos, y: D.status.percentual, type: 'bar',
  marker: { color: D.status.rotulos.map(s => s === 'delivered' ? VERDE : CINZA) },
  text: D.status.percentual.map(v => v.toFixed(2) + '%'),
  textposition: 'outside',
  hovertemplate: '%{x}<br><b>%{y}%</b><extra></extra>'
}], { yaxis: { title: '% dos pedidos', type: 'log', gridcolor: '#E3E6EA' } });

desenhar('g_notas', [{
  x: D.notas.rotulos, y: D.notas.avaliacoes, type: 'bar',
  marker: { color: [VERM, VERM, CINZA, TEAL, VERDE] },
  text: D.notas.percentual.map(v => v.toFixed(1) + '%'),
  textposition: 'outside',
  hovertemplate: '%{x}<br><b>%{y:,} avaliações</b><extra></extra>'
}], { yaxis: { title: 'Avaliações', gridcolor: '#E3E6EA' } });

desenhar('g_pagamentos', [
  { x: D.pagamentos.rotulos, y: D.pagamentos.pct_registros, type: 'bar',
    name: '% dos registros', marker: { color: AZUL } },
  { x: D.pagamentos.rotulos, y: D.pagamentos.pct_valor, type: 'bar',
    name: '% do valor', marker: { color: TEAL } }
], { barmode: 'group', yaxis: { title: 'Percentual', gridcolor: '#E3E6EA' } });

// ------------------------------------------------------------------ Logística
desenhar('g_histograma', [{
  x: D.histograma_entrega.x, y: D.histograma_entrega.y, type: 'bar',
  marker: { color: AZUL }, width: D.histograma_entrega.largura * 0.9,
  hovertemplate: '%{x:.0f} dias<br><b>%{y:,} pedidos</b><extra></extra>'
}], { xaxis: { title: 'Dias entre a compra e a entrega', gridcolor: '#E3E6EA' },
      yaxis: { title: 'Pedidos', gridcolor: '#E3E6EA' } });

desenhar('g_prazo', [
  { x: D.logistica_mensal.meses, y: D.logistica_mensal.prazo_estimado,
    type: 'scatter', mode: 'lines', name: 'Prazo estimado',
    line: { color: CINZA, width: 2, dash: 'dot' } },
  { x: D.logistica_mensal.meses, y: D.logistica_mensal.tempo_real,
    type: 'scatter', mode: 'lines+markers', name: 'Tempo real',
    line: { color: AZUL, width: 2.5 }, marker: { size: 5 } }
], { yaxis: { title: 'Dias', gridcolor: '#E3E6EA' },
     xaxis: { tickangle: -45, gridcolor: '#E3E6EA' } });

desenhar('g_pct_atraso', [{
  x: D.logistica_mensal.meses, y: D.logistica_mensal.pct_atraso,
  type: 'bar', marker: { color: D.logistica_mensal.pct_atraso.map(
      v => v > 10 ? VERM : TEAL) },
  hovertemplate: '%{x}<br><b>%{y:.2f}% atrasados</b><extra></extra>'
}], { yaxis: { title: '% de entregas atrasadas', gridcolor: '#E3E6EA' },
      xaxis: { tickangle: -45, gridcolor: '#E3E6EA' } });

// ------------------------------------------------------------------------ H1
desenhar('g_h1_faixa', [{
  x: D.h1.faixas, y: D.h1.nota_media, type: 'bar',
  marker: { color: [VERDE, TEAL, CINZA, AMBAR, VERM] },
  text: D.h1.nota_media.map(v => v.toFixed(2)), textposition: 'outside',
  customdata: D.h1.pedidos,
  hovertemplate: '%{x}<br>Nota média <b>%{y:.2f}</b>' +
                 '<br>%{customdata:,} pedidos<extra></extra>'
}], { yaxis: { title: 'Nota média', range: [0, 5.4], gridcolor: '#E3E6EA' } });

desenhar('g_h1_composicao',
  Object.keys(D.h1_composicao.series).map((nome, i) => ({
    x: D.h1_composicao.faixas, y: D.h1_composicao.series[nome],
    type: 'bar', name: nome,
    marker: { color: [VERM, '#E57373', CINZA, TEAL, VERDE][i] || SEQ[i] },
    hovertemplate: '%{x}<br>' + nome + ': <b>%{y:.1f}%</b><extra></extra>'
  })),
  { barmode: 'stack', yaxis: { title: '% das avaliações', gridcolor: '#E3E6EA' } });

desenhar('g_h1_dia', [{
  x: D.h1_por_dia.dias, y: D.h1_por_dia.nota,
  type: 'scatter', mode: 'lines+markers',
  line: { color: AZUL, width: 2.5 }, marker: { size: 5 },
  customdata: D.h1_por_dia.pedidos,
  hovertemplate: '%{x} dias<br>Nota média <b>%{y:.2f}</b>' +
                 '<br>%{customdata:,} pedidos<extra></extra>'
}], { xaxis: { title: 'Dias de atraso (negativo = entrega adiantada)',
               gridcolor: '#E3E6EA' },
      yaxis: { title: 'Nota média', gridcolor: '#E3E6EA' },
      shapes: [{ type: 'line', x0: 0, x1: 0, yref: 'paper', y0: 0, y1: 1,
                 line: { color: VERM, width: 1.5, dash: 'dash' } }] });

desenhar('g_h1_ruim', [{
  x: D.h1.faixas, y: D.h1.pct_ruim, type: 'bar',
  marker: { color: VERM },
  text: D.h1.pct_ruim.map(v => v.toFixed(1) + '%'), textposition: 'outside',
  hovertemplate: '%{x}<br><b>%{y:.2f}%</b> com nota 1 ou 2<extra></extra>'
}], { yaxis: { title: '% com nota 1 ou 2', gridcolor: '#E3E6EA' } });

// ------------------------------------------------------------------------ H2
desenhar('g_h2_receita', [{
  y: D.h2.top_receita.categorias.slice().reverse(),
  x: D.h2.top_receita.receita.slice().reverse(),
  type: 'bar', orientation: 'h', marker: { color: AZUL },
  hovertemplate: '%{y}<br><b>%{x:,.0f}</b> em receita<extra></extra>'
}], { margin: { l: 170, r: 24, t: 16, b: 50 },
      xaxis: { title: 'Receita (R$)', gridcolor: '#E3E6EA' } });

desenhar('g_h2_pedidos', [{
  y: D.h2.top_pedidos.categorias.slice().reverse(),
  x: D.h2.top_pedidos.pedidos.slice().reverse(),
  type: 'bar', orientation: 'h', marker: { color: TEAL },
  hovertemplate: '%{y}<br><b>%{x:,}</b> pedidos<extra></extra>'
}], { margin: { l: 170, r: 24, t: 16, b: 50 },
      xaxis: { title: 'Pedidos', gridcolor: '#E3E6EA' } });

const QUADRANTES = {
  'Sustenta o faturamento': VERDE,
  'Risco: muita receita, nota baixa': VERM,
  'Potencial de crescimento': TEAL,
  'Baixa prioridade': CINZA
};
const disp = D.h2.dispersao;
const tracesDisp = Object.keys(QUADRANTES).map(q => {
  const idx = disp.quadrante.map((v, i) => v === q ? i : -1).filter(i => i >= 0);
  return {
    x: idx.map(i => disp.receita[i]),
    y: idx.map(i => disp.nota[i]),
    text: idx.map(i => disp.categorias[i]),
    customdata: idx.map(i => [disp.pedidos[i], disp.pct_atraso[i]]),
    mode: 'markers', type: 'scatter', name: q,
    marker: { color: QUADRANTES[q], size: idx.map(i => disp.pedidos[i]),
              sizemode: 'area',
              sizeref: 2 * Math.max.apply(null, disp.pedidos) / (38 ** 2),
              sizemin: 5, opacity: 0.72,
              line: { color: '#fff', width: 1 } },
    hovertemplate: '<b>%{text}</b><br>Receita %{x:,.0f}<br>Nota %{y:.2f}' +
                   '<br>%{customdata[0]:,} pedidos' +
                   '<br>%{customdata[1]:.1f}% atrasados<extra></extra>'
  };
});
desenhar('g_h2_dispersao', tracesDisp, {
  xaxis: { title: 'Receita em R$, escala logarítmica', type: 'log',
           gridcolor: '#E3E6EA' },
  yaxis: { title: 'Nota média', gridcolor: '#E3E6EA' },
  margin: { l: 60, r: 24, t: 16, b: 70 }
});

desenhar('g_h2_pareto', [{
  x: D.h2.pareto.posicao, y: D.h2.pareto.acumulado,
  type: 'scatter', mode: 'lines', line: { color: AZUL, width: 2.5 },
  fill: 'tozeroy', fillcolor: 'rgba(31,78,121,0.08)',
  text: D.h2.pareto.categorias,
  hovertemplate: '%{x}ª categoria (%{text})<br>' +
                 '<b>%{y:.1f}%</b> da receita acumulada<extra></extra>'
}], { xaxis: { title: 'Categorias ordenadas por receita', gridcolor: '#E3E6EA' },
      yaxis: { title: '% acumulado da receita', gridcolor: '#E3E6EA' },
      shapes: [{ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: 80, y1: 80,
                 line: { color: VERM, width: 1.5, dash: 'dash' } }] });

// ------------------------------------------------------------------ Geografia
desenhar('g_geografia', [
  { x: D.geografia.uf, y: D.geografia.pct_clientes, type: 'bar',
    name: '% dos clientes', marker: { color: AZUL } },
  { x: D.geografia.uf, y: D.geografia.pct_vendedores, type: 'bar',
    name: '% dos vendedores', marker: { color: AMBAR } }
], { barmode: 'group', yaxis: { title: 'Percentual', gridcolor: '#E3E6EA' } });

desenhar('g_concentracao', [
  { x: D.concentracao.pct_vendedores, y: D.concentracao.pct_receita,
    type: 'scatter', mode: 'lines', name: 'Distribuição real',
    line: { color: AZUL, width: 2.5 },
    fill: 'tozeroy', fillcolor: 'rgba(31,78,121,0.08)',
    hovertemplate: '%{x:.1f}% dos vendedores<br>' +
                   '<b>%{y:.1f}% da receita</b><extra></extra>' },
  { x: [0, 100], y: [0, 100], type: 'scatter', mode: 'lines',
    name: 'Distribuição igualitária',
    line: { color: CINZA, width: 1.5, dash: 'dash' }, hoverinfo: 'skip' }
], { xaxis: { title: '% acumulado de vendedores', gridcolor: '#E3E6EA' },
     yaxis: { title: '% acumulado da receita', gridcolor: '#E3E6EA' } });

// ----------------------------------------------------------------------- Abas
document.querySelectorAll('nav button').forEach(botao => {
  botao.addEventListener('click', () => {
    document.querySelectorAll('nav button').forEach(b => b.classList.remove('ativo'));
    document.querySelectorAll('.aba').forEach(a => a.classList.remove('ativa'));
    botao.classList.add('ativo');
    document.getElementById(botao.dataset.aba).classList.add('ativa');
    window.scrollTo({ top: 0, behavior: 'smooth' });
    document.querySelectorAll('#' + botao.dataset.aba + ' .grafico')
      .forEach(g => Plotly.Plots.resize(g));
  });
});
"""
    )


def _kpi(rotulo: str, valor: str, nota: str = "") -> str:
    extra = f'<div class="nota">{nota}</div>' if nota else ""
    return (
        f'<div class="kpi"><div class="rotulo">{rotulo}</div>'
        f'<div class="valor">{valor}</div>{extra}</div>'
    )


def _grafico(id_elemento: str, titulo: str, subtitulo: str, alto: bool = False) -> str:
    classe = "grafico alto" if alto else "grafico"
    return (
        f'<div class="cartao"><h3>{titulo}</h3><p class="sub">{subtitulo}</p>'
        f'<div id="{id_elemento}" class="{classe}"></div></div>'
    )


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
    k = dados["kpis"]
    log = dados["logistica_resumo"]
    h1 = dados["h1"]
    h2 = dados["h2"]

    def milhar(v) -> str:
        return f"{v:,.0f}".replace(",", ".")

    def reais(v) -> str:
        texto = f"{v:,.2f}"
        return "R$ " + texto.replace(",", "X").replace(".", ",").replace("X", ".")

    # Tabela do modelo de dados
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
        f"<td class='num'>{c['pct_receita']:.2f}%</td></tr>"
        for c in dados["concentracao"]["cortes"]
    )

    linhas_faixa = "".join(
        f"<tr><td>{h1['faixas'][i]}</td>"
        f"<td class='num'>{milhar(h1['pedidos'][i])}</td>"
        f"<td class='num'>{h1['pct_pedidos'][i]:.2f}%</td>"
        f"<td class='num'>{h1['nota_media'][i]:.2f}</td>"
        f"<td class='num'>{h1['pct_ruim'][i]:.2f}%</td>"
        f"<td class='num'>{h1['pct_boa'][i]:.2f}%</td></tr>"
        for i in range(len(h1["faixas"]))
    )

    kruskal = ""
    if "kruskal_p" in h1["testes"]:
        p = h1["testes"]["kruskal_p"]
        p_texto = "p < 0,001" if p < 0.001 else f"p = {p:.4f}".replace(".", ",")
        kruskal = (
            f" O teste de Kruskal-Wallis entre as cinco faixas resulta em "
            f"H = {h1['testes']['kruskal_h']:,.0f} e {p_texto}, o que indica que "
            f"as diferenças entre as faixas não são fruto do acaso."
        )

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Dashboard Olist | Projeto Aplicado 1 - Grupo 10</title>
<script src="{PLOTLY_CDN}"></script>
<style>{CSS}</style>
</head>
<body>

<header>
  <h1>E-commerce brasileiro: o caso Olist</h1>
  <p>Projeto Aplicado 1 &middot; Grupo 10 &middot; Curso de Banco de Dados &middot;
     Universidade Presbiteriana Mackenzie</p>
  <div class="meta">
    Base: Brazilian E-Commerce Public Dataset by Olist (Kaggle, CC BY-NC-SA 4.0) &middot;
    Período de {k['periodo_inicio']} a {k['periodo_fim']} &middot;
    Gerado em {dados['gerado_em']}
  </div>
</header>

<nav>
  <button class="ativo" data-aba="aba-geral">Visão geral</button>
  <button data-aba="aba-logistica">Logística</button>
  <button data-aba="aba-h1">H1 &middot; Atraso e satisfação</button>
  <button data-aba="aba-h2">H2 &middot; Categorias</button>
  <button data-aba="aba-geografia">Geografia e concentração</button>
  <button data-aba="aba-modelo">Modelo de dados</button>
</nav>

<div class="conteudo">

<!-- ================================================== VISÃO GERAL -->
<section id="aba-geral" class="aba ativa">
  <div class="kpis">
    {_kpi("Pedidos", milhar(k['pedidos']), f"{k['pct_entregues']:.2f}% entregues")}
    {_kpi("Clientes únicos", milhar(k['clientes_unicos']), "em 99.441 identificadores")}
    {_kpi("Vendedores", milhar(k['vendedores']), f"{milhar(k['produtos'])} produtos")}
    {_kpi("Receita de produtos", reais(k['receita_itens']), f"frete à parte: {reais(k['frete_total'])}")}
    {_kpi("Ticket médio", reais(k['ticket_medio']), f"mediana {reais(k['ticket_mediano'])}")}
    {_kpi("Nota média", f"{k['nota_media']:.2f}".replace('.', ','), f"{milhar(k['avaliacoes'])} avaliações")}
  </div>

  {_grafico("g_sazonalidade", "Pedidos por mês",
            "Setembro de 2016 a outubro de 2018. As pontas da série são incompletas: 2016 tem apenas 329 pedidos e setembro e outubro de 2018 somam 20.")}

  <div class="achado">
    O período consistente para análise vai de <strong>janeiro de 2017 a agosto de
    2018</strong>. O pico de novembro de 2017 coincide com a Black Friday, e o
    volume se estabiliza entre 6 mil e 7,3 mil pedidos mensais em 2018.
  </div>

  <div class="grade2">
    {_grafico("g_status", "Status dos pedidos",
              "Escala logarítmica, porque 97% dos pedidos estão em um único status.")}
    {_grafico("g_notas", "Distribuição das notas",
              "Notas de 1 a 5 atribuídas na pesquisa enviada após a entrega.")}
  </div>

  {_grafico("g_pagamentos", "Formas de pagamento",
            "Participação de cada forma no número de registros e no valor total pago.")}

  <div class="achado">
    O cartão de crédito responde por <strong>{dados['pagamentos']['pct_registros'][0]:.1f}%
    dos registros e {dados['pagamentos']['pct_valor'][0]:.1f}% do valor</strong>, com média de
    {dados['pagamentos']['parcelas'][0]:.2f} parcelas. As demais formas são sempre à vista.
  </div>
</section>

<!-- ================================================== LOGÍSTICA -->
<section id="aba-logistica" class="aba">
  <div class="kpis">
    {_kpi("Tempo médio de entrega", f"{log['tempo_medio']:.2f} dias".replace('.', ','), f"mediana de {log['tempo_mediano']:.0f} dias")}
    {_kpi("Prazo estimado médio", f"{log['prazo_medio']:.2f} dias".replace('.', ','), f"folga média de {log['folga_media']:.1f} dias".replace('.', ','))}
    {_kpi("Entregas atrasadas", f"{log['pct_atraso']:.2f}%".replace('.', ','), log['criterio_adotado'])}
    {_kpi("Pior caso registrado", f"{log['tempo_maximo']:.0f} dias", "entre a compra e a entrega")}
  </div>

  {_grafico("g_histograma", "Distribuição do tempo de entrega",
            f"Dias entre a compra e a entrega ao cliente, truncado em {config.CORTE_HISTOGRAMA_DIAS} dias para não achatar o gráfico com os casos extremos.")}

  <div class="achado alerta">
    <strong>Nota metodológica sobre o critério de atraso.</strong> O campo
    <code>order_estimated_delivery_date</code> registra apenas a data, sempre com
    hora 00:00:00, enquanto <code>order_delivered_customer_date</code> registra
    data e hora. O projeto adota a {log['criterio_adotado']}, que trata a data
    estimada como prazo que vence à meia-noite e resulta em
    <strong>{log['pct_atraso']:.2f}% de entregas atrasadas</strong>. Pela
    {log['criterio_alternativo']}, o índice seria de
    {log['pct_atraso_alternativo']:.2f}%. A escolha reclassifica
    {log['pedidos_divergentes']:,} pedidos, entregues no próprio dia estimado
    depois da meia-noite, e o critério adotado é o mais conservador dos dois.
  </div>

  {_grafico("g_prazo", "Tempo real contra prazo estimado, por mês",
            "A distância entre as duas linhas é a folga que a plataforma embute na promessa de entrega.")}

  <div class="achado">
    A Olist promete prazos consistentemente maiores que o tempo real de entrega,
    com folga média de <strong>{log['folga_media']:.1f} dias</strong>. A estratégia
    protege o índice de pontualidade, mas custa conversão: um prazo anunciado de 23
    dias afasta comprador que receberia em 12.
  </div>

  {_grafico("g_pct_atraso", "Percentual de entregas atrasadas por mês",
            "Barras acima de 10% destacadas em vermelho.")}
</section>

<!-- ================================================== H1 -->
<section id="aba-h1" class="aba">
  <div class="cartao">
    <h3>H1 &middot; Atraso na entrega e satisfação do cliente</h3>
    <p class="sub">Quanto maior o atraso na entrega em relação à data estimada,
       menor tende a ser a avaliação atribuída pelo cliente?</p>
    <table>
      <thead><tr>
        <th>Faixa de atraso</th><th class="num">Pedidos</th>
        <th class="num">% do total</th><th class="num">Nota média</th>
        <th class="num">% nota 1 ou 2</th><th class="num">% nota 4 ou 5</th>
      </tr></thead>
      <tbody>{linhas_faixa}</tbody>
    </table>
  </div>

  <div class="grade2">
    {_grafico("g_h1_faixa", "Nota média por faixa de atraso",
              "A queda é progressiva, e não um degrau único entre no prazo e atrasado.")}
    {_grafico("g_h1_ruim", "Percentual de notas 1 ou 2 por faixa",
              "Proporção de clientes claramente insatisfeitos em cada faixa.")}
  </div>

  {_grafico("g_h1_composicao", "Composição das notas dentro de cada faixa",
            "Cada barra soma 100%. Mostra como o perfil de satisfação se inverte conforme o atraso cresce.", alto=True)}

  {_grafico("g_h1_dia", "Nota média por dia de atraso",
            "Apenas dias com pelo menos 30 pedidos, de 30 dias de antecipação a 30 de atraso. A linha vermelha marca a data estimada.")}

  <div class="achado">
    <strong>Conclusão.</strong> {h1['conclusao']}{kruskal}
  </div>
</section>

<!-- ================================================== H2 -->
<section id="aba-h2" class="aba">
  <div class="kpis">
    {_kpi("Categorias analisadas", str(h2['total_categorias']), f"{len(h2['dispersao']['categorias'])} com 100+ pedidos")}
    {_kpi("Concentração da receita", f"{h2['categorias_80']} categorias", "respondem por 80% do total")}
    {_kpi("Melhor nota média", f"{h2['melhor_nota']['nota']:.2f}".replace('.', ','), h2['melhor_nota']['categoria'])}
    {_kpi("Pior nota média", f"{h2['pior_nota']['nota']:.2f}".replace('.', ','), h2['pior_nota']['categoria'])}
  </div>

  <div class="grade2">
    {_grafico("g_h2_receita", "Top 10 categorias por receita",
              "Soma do preço dos itens, sem frete.")}
    {_grafico("g_h2_pedidos", "Top 10 categorias por número de pedidos",
              "Pedidos distintos que contêm ao menos um item da categoria.")}
  </div>

  <div class="achado">
    As lideranças não coincidem. A categoria que mais vende em volume não é a que
    mais fatura, e nenhuma das duas é a mais bem avaliada. Comparar categorias por
    um indicador só leva a decisão errada.
  </div>

  {_grafico("g_h2_dispersao", "Receita contra nota média, por categoria",
            "Apenas categorias com 100 pedidos ou mais. O tamanho do círculo representa o número de pedidos e a cor indica o quadrante. Receita em escala logarítmica.", alto=True)}

  {_grafico("g_h2_pareto", "Curva de Pareto da receita por categoria",
            "Percentual acumulado da receita conforme as categorias são somadas da maior para a menor.")}

  <div class="achado">
    <strong>Conclusão.</strong> {h2['conclusao']}
  </div>
</section>

<!-- ================================================== GEOGRAFIA -->
<section id="aba-geografia" class="aba">
  {_grafico("g_geografia", "Clientes e vendedores por unidade federativa",
            "Doze estados com maior número de clientes, em percentual do total de cada grupo.", alto=True)}

  <div class="achado">
    São Paulo concentra <strong>{dados['geografia']['pct_clientes'][0]:.2f}% dos
    clientes e {dados['geografia']['pct_vendedores'][0]:.2f}% dos vendedores</strong>.
    A assimetria aparece nos estados do Nordeste, que compram muito mais do que
    vendem na plataforma, o que dialoga diretamente com o ODS 10 discutido no
    trabalho.
  </div>

  {_grafico("g_concentracao", "Concentração da receita entre vendedores",
            "Curva de Lorenz. A linha tracejada representa a distribuição em que todos os vendedores teriam a mesma receita.")}

  <div class="cartao">
    <h3>Cortes de concentração</h3>
    <p class="sub">Participação acumulada na receita de produto.</p>
    <table>
      <thead><tr><th>Corte</th><th class="num">Vendedores</th>
        <th class="num">% da receita</th></tr></thead>
      <tbody>{linhas_cortes}</tbody>
    </table>
  </div>
</section>

<!-- ================================================== MODELO -->
<section id="aba-modelo" class="aba">
  <div class="cartao">
    <h3>Estrutura das tabelas</h3>
    <p class="sub">Os nove arquivos CSV foram carregados em um banco SQLite com
       chaves primárias, chaves estrangeiras e índices declarados.</p>
    <table>
      <thead><tr><th>Tabela</th><th class="num">Linhas</th><th class="num">Colunas</th>
        <th class="num">Nulos</th><th class="num">Duplicadas</th>
        <th>Chave primária</th></tr></thead>
      <tbody>{linhas_modelo}</tbody>
    </table>
  </div>

  <div class="achado alerta">
    <strong>Decisão de modelagem.</strong> Em <code>order_reviews</code>, nem
    <code>review_id</code> nem <code>order_id</code> são únicos. São 99.224 linhas
    para 98.410 review_ids e 98.673 order_ids, o que obriga a chave primária
    composta <code>(review_id, order_id)</code>. A tabela
    <code>geolocation</code> não tem chave natural e cerca de 26% das linhas são
    duplicadas integrais, por repetirem o mesmo prefixo de CEP com coordenadas
    diferentes.
  </div>

  <div class="cartao">
    <h3>Integridade referencial</h3>
    <p class="sub">Verificação de registros órfãos antes da carga no banco.</p>
    <table>
      <thead><tr><th>Chave estrangeira</th><th>Tabela referenciada</th>
        <th class="num">Registros</th><th class="num">Órfãos</th>
        <th>Situação</th></tr></thead>
      <tbody>{linhas_integridade}</tbody>
    </table>
  </div>

  <div class="cartao">
    <h3>Correlações de Spearman</h3>
    <p class="sub">Medida de associação entre postos, apropriada para a nota, que é
       ordinal, e para o tempo de entrega, cuja distribuição é assimétrica.
       O coeficiente do atraso parece modesto porque a grande maioria dos pedidos
       chega no prazo e varia de antecedência sem variar de nota. O efeito está
       concentrado na minoria que atrasa, e nela é forte, como mostra a aba H1.</p>
    <table>
      <thead><tr><th>Par de variáveis</th><th class="num">Coeficiente</th>
        <th>Leitura</th></tr></thead>
      <tbody>
        <tr><td>Tempo total de entrega e nota</td>
            <td class="num">{str(round(dados['correlacoes']['tempo_nota'], 3)).replace('.', ',')}</td>
            <td>negativa e moderada, a mais forte das três</td></tr>
        <tr><td>Dias de atraso e nota</td>
            <td class="num">{str(round(dados['correlacoes']['atraso_nota'], 3)).replace('.', ',')}</td>
            <td>negativa, diluída pelos 93% entregues no prazo</td></tr>
        <tr><td>Valor do frete e nota</td>
            <td class="num">{str(round(dados['correlacoes']['frete_nota'], 3)).replace('.', ',')}</td>
            <td>negativa e fraca, praticamente sem efeito</td></tr>
      </tbody>
    </table>
  </div>
</section>

</div>

<footer>
  Elaborado pelo Grupo 10 a partir do Brazilian E-Commerce Public Dataset by Olist,
  publicado no Kaggle sob licença CC BY-NC-SA 4.0.<br>
  Beatriz Resende Silva &middot; Mayara Laury Gonçalves de França &middot;
  Melissa Menchão Lima do Nascimento &middot; Otavio Prates dos Santos
</footer>

<script>{_javascript(json.dumps(dados, ensure_ascii=False))}</script>
</body>
</html>
"""

    caminho.write_text(html, encoding="utf-8")
    return caminho
