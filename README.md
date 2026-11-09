# Projeto Aplicado 1 · Grupo 10 · Olist

Análise do **Brazilian E-Commerce Public Dataset by Olist** para a disciplina Projeto Aplicado 1 do curso de Banco de Dados da Universidade Presbiteriana Mackenzie.

**Dashboard publicado:** https://melissalima308.github.io/mackenzie-grupo10-projeto-bd/

## Integrantes

| Nome | RA |
| --- | --- |
| Beatriz Resende Silva | 10775947 |
| Mayara Laury Gonçalves de França | 10763877 |
| Melissa Menchão Lima do Nascimento | 10764865 |
| Otavio Prates dos Santos | 10775492 |

## Pergunta do projeto

O que explica a satisfação do cliente em um marketplace brasileiro, e onde ela pesa mais na receita? O trabalho investiga duas hipóteses:

- **H1, atraso e satisfação.** Quanto maior o atraso em relação à data estimada, menor a nota do cliente?
- **H2, categoria e desempenho.** O desempenho dos pedidos varia por categoria de produto, considerando volume, receita e nota média?

## Principais resultados

- 99.441 pedidos entre set/2016 e out/2018; 97% entregues; entrega média de 12 dias contra prazo estimado de 23.
- Pedidos no prazo têm nota média 4,29; pedidos atrasados, 2,57. A nota se mantém até o 1º dia de atraso e cai para 2,68 no 4º dia.
- A partir de 8 dias de atraso, 78% das avaliações são 1 ou 2.
- Por estado, quanto maior o percentual de atraso, menor a nota (Spearman = -0,82 entre os 27 estados). Em AL, 23% dos pedidos atrasam; em SP, 6%.
- 10 categorias concentram 62% da receita, e 12 categorias de receita alta ficam abaixo da nota mediana, somando cerca de 45% da receita analisada.

## Estrutura do repositório

```
executar.py            Orquestrador: roda o pipeline completo com um comando
requirements.txt       Dependências Python
src/
  config.py            Caminhos, parâmetros de análise e cores (único lugar com caminhos)
  carga.py             Leitura dos 9 CSV, conversão de datas e checagem de integridade
  tratamento.py        Colunas derivadas: tempo de entrega, atraso, faixas, receita
  banco.py             Criação do banco SQLite com chaves primárias e estrangeiras
  eda.py               Análise exploratória (seções 4.1 a 4.6 do relatório)
  h1_atraso.py         Hipótese H1: atraso x nota, por faixa, por dia e por estado
  h2_categoria.py      Hipótese H2: desempenho por categoria, Pareto e quadrantes
  graficos.py          Funções de gráfico com o padrão visual do projeto
  formato.py           Formatação de números no padrão brasileiro
  dashboard.py         Geração do painel HTML interativo
consultas/             Consultas SQL que reproduzem as análises direto no banco
saida/figuras/         Gráficos gerados (PNG)
saida/tabelas/         Tabelas de resultado (CSV)
docs/index.html        Cópia do dashboard publicada pelo GitHub Pages
```

## Como executar

1. Instale o Python 3.10 ou superior e as dependências:

   ```
   pip install -r requirements.txt
   ```

2. Baixe o dataset no Kaggle (https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) e coloque os nove arquivos CSV em uma pasta `dados/` na raiz do projeto. Os CSV não ficam no repositório porque somam cerca de 120 MB, acima do limite do GitHub. Uma cópia também está no [Google Drive do grupo](https://drive.google.com/drive/folders/1MKTJIdSudSztkEanov0-Ho-6dPtU_HsR?usp=sharing).

3. Rode o pipeline:

   ```
   python executar.py
   ```

   O processo leva menos de um minuto e gera o banco `saida/olist.db`, as figuras, as tabelas e o dashboard. Opções úteis:

   ```
   python executar.py --sem-banco        não recria o SQLite
   python executar.py --so-dashboard     gera só o painel, sem imprimir as análises
   python executar.py --dados CAMINHO    usa outra pasta de CSV
   ```

## Decisões de método

- **Critério de atraso.** A data estimada vem sempre com hora 00:00, então o atraso é calculado por data e hora, tratando o prazo como vencido à meia-noite. Resulta em 8,11% de entregas atrasadas; por dia de calendário seriam 6,77%. O critério pode ser trocado em `src/config.py` (`CRITERIO_ATRASO`).
- **Nota por pedido.** Quando um pedido tem mais de uma avaliação, usa-se a média.
- **Correlação de Spearman** em vez de Pearson, porque a nota é ordinal (1 a 5) e o atraso tem distribuição assimétrica.
- **Categorias com pelo menos 100 pedidos** entram nas comparações de nota da H2, para evitar médias instáveis.
- **Quadrantes da H2** usam a mediana de receita e de nota das categorias como corte.

## Tabelas de resultado

| Arquivo | Conteúdo |
| --- | --- |
| `01` a `14` | Estrutura, qualidade e análise exploratória |
| `20_h1_nota_por_faixa_atraso.csv` | Nota média e perfil de notas por faixa de atraso |
| `21_h1_distribuicao_notas_por_faixa.csv` | Percentual de cada nota por faixa |
| `22_h1_nota_por_dia_atraso.csv` | Nota média por dia de atraso (-30 a +30) |
| `23_h1_testes_estatisticos.csv` | Spearman e Kruskal-Wallis da H1 |
| `24_h1_atraso_por_uf.csv` | Percentual de atraso, nota e tempo de entrega por estado |
| `30` a `35` | Desempenho por categoria, rankings, Pareto e quadrantes da H2 |

## Fonte e licença dos dados

OLIST. *Brazilian E-Commerce Public Dataset by Olist*. Kaggle, licença CC BY-NC-SA 4.0. Uso permitido para fins educacionais e de pesquisa, com atribuição da fonte.
