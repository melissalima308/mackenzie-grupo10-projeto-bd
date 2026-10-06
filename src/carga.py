"""
Camada de carga.

Responsabilidades:
  1. Ler os nove arquivos CSV do dataset da Olist.
  2. Converter as colunas de data para o tipo datetime.
  3. Produzir o retrato de estrutura e qualidade exigido pela secao 4.1 do
     trabalho (linhas, colunas, nulos, duplicadas).
  4. Verificar a integridade referencial antes de carregar o banco, porque
     o SQLite recusa a insercao se houver chave estrangeira orfa.

Nenhuma funcao deste modulo altera os dados. Limpeza e colunas derivadas
ficam em tratamento.py.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import config


def _caminho(nome_tabela: str, pasta: Path) -> Path:
    caminho = pasta / config.ARQUIVOS[nome_tabela]
    if not caminho.exists():
        raise FileNotFoundError(
            f"Arquivo nao encontrado: {caminho}\n"
            f"Baixe o dataset do Kaggle e coloque os nove CSV na pasta "
            f"'{pasta}', ou aponte a variavel de ambiente OLIST_DADOS "
            f"para a pasta correta."
        )
    return caminho


def carregar_tabelas(pasta: Path | None = None) -> dict[str, pd.DataFrame]:
    """Le os nove CSV e devolve um dicionario nome -> DataFrame.

    As colunas de data listadas em config.COLUNAS_DATA sao convertidas para
    datetime na propria leitura.
    """
    pasta = Path(pasta) if pasta is not None else config.PASTA_DADOS
    tabelas: dict[str, pd.DataFrame] = {}

    for nome in config.ARQUIVOS:
        df = pd.read_csv(_caminho(nome, pasta))
        for coluna in config.COLUNAS_DATA.get(nome, []):
            if coluna in df.columns:
                df[coluna] = pd.to_datetime(df[coluna], errors="coerce")
        tabelas[nome] = df

    return tabelas


def resumo_tabelas(tabelas: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Linhas, colunas, nulos e duplicadas de cada tabela."""
    return pd.DataFrame(
        {
            "arquivo": [config.ARQUIVOS[n] for n in tabelas],
            "linhas": [len(d) for d in tabelas.values()],
            "colunas": [d.shape[1] for d in tabelas.values()],
            "valores_nulos": [int(d.isna().sum().sum()) for d in tabelas.values()],
            "linhas_duplicadas": [int(d.duplicated().sum()) for d in tabelas.values()],
        },
        index=pd.Index(list(tabelas.keys()), name="tabela"),
    )


def nulos_por_coluna(tabelas: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Lista apenas as colunas que tem valor nulo, com quantidade e percentual."""
    linhas = []
    for nome, df in tabelas.items():
        nulos = df.isna().sum()
        for coluna, quantidade in nulos[nulos > 0].items():
            linhas.append(
                {
                    "tabela": nome,
                    "coluna": coluna,
                    "nulos": int(quantidade),
                    "percentual": round(100 * quantidade / len(df), 2),
                }
            )
    if not linhas:
        return pd.DataFrame(columns=["tabela", "coluna", "nulos", "percentual"])
    return pd.DataFrame(linhas).sort_values(
        ["tabela", "percentual"], ascending=[True, False], ignore_index=True
    )


def tipos_por_coluna(tabelas: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Dicionario de dados: tabela, coluna e tipo."""
    linhas = []
    for nome, df in tabelas.items():
        for coluna, tipo in df.dtypes.items():
            linhas.append({"tabela": nome, "coluna": coluna, "tipo": str(tipo)})
    return pd.DataFrame(linhas)


# ----------------------------------------------------------------------
# Integridade referencial
# ----------------------------------------------------------------------
# (tabela filha, coluna filha, tabela pai, coluna pai)
RELACIONAMENTOS = [
    ("orders", "customer_id", "customers", "customer_id"),
    ("items", "order_id", "orders", "order_id"),
    ("items", "product_id", "products", "product_id"),
    ("items", "seller_id", "sellers", "seller_id"),
    ("payments", "order_id", "orders", "order_id"),
    ("reviews", "order_id", "orders", "order_id"),
]


def validar_integridade(tabelas: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Conta registros orfaos em cada relacionamento do modelo.

    Um registro orfao e aquele cuja chave estrangeira nao existe na tabela
    pai. Se houver qualquer orfao, a carga do SQLite com PRAGMA
    foreign_keys = ON vai falhar, e e melhor descobrir isso aqui.
    """
    linhas = []
    for filha, col_filha, pai, col_pai in RELACIONAMENTOS:
        chaves_pai = set(tabelas[pai][col_pai].dropna())
        serie = tabelas[filha][col_filha]
        orfaos = int((~serie.isin(chaves_pai) & serie.notna()).sum())
        linhas.append(
            {
                "tabela_filha": filha,
                "coluna": col_filha,
                "tabela_pai": pai,
                "registros": len(serie),
                "orfaos": orfaos,
                "situacao": "ok" if orfaos == 0 else "ATENCAO",
            }
        )
    return pd.DataFrame(linhas)


def verificar_unicidade(tabelas: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Testa as chaves candidatas de cada tabela.

    Achado relevante para a modelagem: em olist_order_reviews nem review_id
    nem order_id sao unicos, o que obriga a chave primaria composta
    (review_id, order_id).
    """
    candidatas = [
        ("orders", ["order_id"]),
        ("customers", ["customer_id"]),
        ("sellers", ["seller_id"]),
        ("products", ["product_id"]),
        ("items", ["order_id", "order_item_id"]),
        ("payments", ["order_id", "payment_sequential"]),
        ("reviews", ["review_id"]),
        ("reviews", ["order_id"]),
        ("reviews", ["review_id", "order_id"]),
        ("translation", ["product_category_name"]),
    ]
    linhas = []
    for tabela, colunas in candidatas:
        df = tabelas[tabela]
        duplicadas = int(df.duplicated(colunas).sum())
        linhas.append(
            {
                "tabela": tabela,
                "chave_candidata": " + ".join(colunas),
                "linhas": len(df),
                "duplicadas": duplicadas,
                "serve_como_pk": "sim" if duplicadas == 0 else "nao",
            }
        )
    return pd.DataFrame(linhas)
