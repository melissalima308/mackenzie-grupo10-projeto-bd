# Projeto Aplicado 1 — Grupo 10

Análise do e-commerce brasileiro a partir do caso Olist, para a disciplina de
Projeto Aplicado 1 do curso de Banco de Dados da Universidade Presbiteriana
Mackenzie.

**Integrantes**

| Nome | RA |
| --- | --- |
| Beatriz Resende Silva | 10775947 |
| Mayara Laury Gonçalves de França | 10763877 |
| Melissa Menchão Lima do Nascimento | 10764865 |
| Otavio Prates dos Santos | 10775492 |

**Dataset:** Brazilian E-Commerce Public Dataset by Olist, publicado no Kaggle
sob licença CC BY-NC-SA 4.0.
<https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce>

---

## O que o projeto faz

O pipeline lê os nove arquivos CSV, valida a estrutura, carrega os dados em um
banco relacional SQLite com chaves e índices, executa a análise exploratória e
as duas hipóteses de investigação, e gera um dashboard interativo em HTML.

```
CSV  ->  validação  ->  SQLite  ->  EDA  ->  H1  ->  H2  ->  dashboard
```

Tudo roda com um comando e leva cerca de 20 segundos em uma máquina comum.

## Como executar

```bash
# 1. Baixe os nove CSV do Kaggle e coloque na pasta dados/
# 2. Instale as dependências
pip install -r requirements.txt

# 3. Rode o pipeline
python executar.py
```

Opções disponíveis:

```bash
python executar.py --dados /caminho/para/os/csv   # outra pasta de dados
python executar.py --sem-banco                    # pula a criação do SQLite
python executar.py --so-dashboard                 # saída resumida
```

O dashboard fica em `saida/dashboard.html` e abre com duplo clique em qualquer
navegador.

## Estrutura do repositório

```
.
├── executar.py              orquestrador do pipeline
├── requirements.txt
├── dados/                   os nove CSV (não versionados, ver .gitignore)
├── src/
│   ├── config.py            caminhos, parâmetros de análise e paleta
│   ├── carga.py             leitura, tipagem e validação de integridade
│   ├── banco.py             DDL e carga do SQLite
│   ├── tratamento.py        limpeza e colunas derivadas
│   ├── graficos.py          figuras do relatório, em matplotlib
│   ├── formato.py           formatação numérica em padrão brasileiro
│   ├── eda.py               análise exploratória (seção 4 do trabalho)
│   ├── h1_atraso.py         hipótese H1
│   ├── h2_categoria.py      hipótese H2
│   └── dashboard.py         gerador do HTML interativo
├── consultas/               oito consultas SQL comentadas
├── docs/
│   └── index.html           cópia do dashboard publicada pelo GitHub Pages
└── saida/
    ├── figuras/             14 PNG para o relatório escrito
    ├── tabelas/             23 CSV com os resultados
    ├── olist.db             banco SQLite (não versionado, 171 MB)
    └── dashboard.html       dashboard interativo
```

## Modelo relacional

O banco tem nove tabelas, com chaves primárias e estrangeiras declaradas e doze
índices. Três decisões de modelagem merecem registro.

**A tabela de avaliações não tem chave primária simples.** São 99.224 linhas
para 98.410 valores distintos de `review_id` e 98.673 de `order_id`. Nenhum dos
dois serve sozinho como chave. A primária adotada é composta:
`(review_id, order_id)`.

**A tabela de geolocalização não tem chave natural.** Cerca de 26% das linhas
são duplicadas integrais, porque o mesmo prefixo de CEP aparece com coordenadas
diferentes. A tabela ficou sem chave primária, com índice no prefixo.

**A tradução de categorias não cobre todas as categorias.** Dois nomes presentes
em `products` não existem no arquivo de tradução. Eles são inseridos na tabela
pai com tradução nula, para que a chave estrangeira feche sem perder o
relacionamento.

A validação roda antes da carga, em `carga.validar_integridade`, e depois da
carga, pelo `PRAGMA foreign_key_check`. Nenhum registro órfão foi encontrado em
nenhum dos seis relacionamentos.

## Decisões metodológicas

**Critério de atraso.** O campo `order_estimated_delivery_date` registra apenas
a data, sempre com hora 00:00:00, enquanto `order_delivered_customer_date`
registra data e hora. O projeto adota a comparação por data e hora, que trata a
data estimada como prazo que vence à meia-noite e resulta em **8,11% de entregas
atrasadas**. Pela comparação por dia de calendário, que consideraria no prazo
uma entrega feita às 14h do próprio dia estimado, o índice seria de 6,77%. A
escolha reclassifica 1.292 pedidos e é a mais conservadora das duas.

O critério é configurável em `config.CRITERIO_ATRASO`. Trocar o valor para
`"dia"` refaz todo o pipeline com o outro critério, incluindo as faixas da
hipótese H1 e os gráficos. A consulta `03_logistica.sql` devolve os dois índices
lado a lado.

**Nota por pedido.** Existem pedidos com mais de uma avaliação registrada. A
nota de um pedido é a média das notas das suas avaliações. Nas contagens por
faixa de nota, essa média é arredondada.

**Receita por categoria.** A receita é a soma do campo `price` dos itens, sem o
frete, que não é receita do produto. Um pedido com itens de categorias
diferentes conta para cada uma delas, e por isso a soma dos pedidos das
categorias é maior que o total de pedidos do dataset.

**Correlação de Spearman e não Pearson.** A nota é ordinal, de 1 a 5, e o tempo
de entrega tem distribuição fortemente assimétrica. Spearman trabalha com os
postos dos valores e não exige relação linear nem normalidade.

**Pequena divergência entre SQL e Python.** Nos percentuais de nota 1 ou 2 por
faixa há diferença de até 0,03 ponto percentual entre as duas camadas. A causa é
a regra de arredondamento: o SQLite arredonda 0,5 para cima e o NumPy arredonda
para o par mais próximo. Os demais números batem exatamente.

## Hipóteses investigadas

**H1 — Atraso na entrega e satisfação do cliente.** A nota média cai de 4,29 nos
pedidos entregues no prazo para 1,75 na faixa de 8 a 14 dias de atraso. O
percentual de avaliações 1 ou 2 sobe de 9,21% para 78,15% no mesmo intervalo. O
teste de Kruskal-Wallis entre as cinco faixas resulta em H igual a 10.127 e p
menor que 0,001. A hipótese é sustentada, com duas ressalvas registradas no
relatório: o efeito se estabiliza a partir de 8 dias, quando o cliente
insatisfeito já deu a nota mínima, e a correlação de Spearman geral é diluída
pelos 92% de pedidos entregues no prazo.

**H2 — Categoria e desempenho dos pedidos.** As lideranças não coincidem.
`bed_bath_table` lidera em volume, `health_beauty` em receita e
`books_general_interest` em nota média. Dezoito das 74 categorias respondem por
80% da receita. Doze categorias combinam receita alta com nota abaixo da
mediana, e são o ponto de atenção da plataforma.

## Consultas SQL

As oito consultas em `consultas/` reproduzem as análises principais diretamente
no banco, com CTE, funções de agregação, junções e função de janela. Podem ser
executadas em qualquer cliente SQLite ou pelo Python:

```python
from src import banco
banco.consultar_arquivo("04_h1_atraso_satisfacao.sql")
```

| Arquivo | O que responde |
| --- | --- |
| `01_visao_geral.sql` | números-chave de cada tabela |
| `02_pedidos_por_mes.sql` | sazonalidade de pedidos e receita |
| `03_logistica.sql` | tempo de entrega, prazo estimado e atraso |
| `04_h1_atraso_satisfacao.sql` | hipótese H1, por faixa de atraso |
| `05_h2_categoria_desempenho.sql` | hipótese H2, por categoria |
| `06_concentracao_vendedores.sql` | curva de concentração, com função de janela |
| `07_geografia.sql` | clientes e vendedores por unidade federativa |
| `08_pagamentos.sql` | formas de pagamento e parcelamento |

## Dashboard

O dashboard é um arquivo HTML único, com os dados agregados embutidos em JSON e
os gráficos desenhados pelo Plotly.js carregado do CDN. Tem seis abas: visão
geral, logística, H1, H2, geografia e modelo de dados.

O `executar.py` grava duas cópias idênticas: `saida/dashboard.html`, para uso
local, e `docs/index.html`, que é a pasta publicada pelo GitHub Pages.

Para publicar, vá em **Settings → Pages** no repositório, escolha **Deploy from a
branch**, selecione a branch `main` e a pasta `/docs`, e salve. Em poucos minutos
o dashboard fica no ar em:

```
https://melissalima308.github.io/mackenzie-grupo10-projeto-bd/
```

O endereço pode ser colocado no relatório e no README, e quem abrir vê o
dashboard sem baixar nada nem instalar nada.

Para uso offline, baixe `plotly.min.js` e substitua a tag de script no arquivo
gerado pelo caminho local.

## Observações sobre os dados

O banco SQLite gerado tem cerca de 171 MB e não é versionado, porque o limite de
arquivo do GitHub é de 100 MB. Os CSV também ficam fora do repositório, pelo
mesmo motivo. Ambos são reconstruídos pelo `executar.py` a partir do download do
Kaggle.

A cobertura temporal é desigual. As compras vão de setembro de 2016 a outubro de
2018, mas 2016 tem apenas 329 pedidos e setembro e outubro de 2018 somam 20. O
período consistente para análise vai de janeiro de 2017 a agosto de 2018, e
qualquer leitura de tendência deve considerar esse recorte.
