"""
Camada de banco de dados.

Constroi um banco relacional SQLite a partir dos nove CSV, com chaves
primarias, chaves estrangeiras e indices declarados. Atende a meta
especifica registrada no item 1.7 do trabalho: criar a estrutura de um
banco de dados relacional a partir dos arquivos CSV.

Observacoes de modelagem:
  - olist_order_reviews nao tem chave primaria simples. Nem review_id
    (98.410 unicos em 99.224 linhas) nem order_id (98.673 unicos) sao
    unicos. A PK adotada e composta: (review_id, order_id).
  - olist_geolocation nao tem chave natural. O prefixo de CEP se repete
    com varias coordenadas, e cerca de 26% das linhas sao duplicadas
    integrais. A tabela fica sem PK, com indice no prefixo de CEP.
  - products.product_category_name admite nulo (610 produtos sem
    categoria), por isso a FK para a tabela de traducao nao e obrigatoria.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from . import config

DDL = """
PRAGMA foreign_keys = OFF;

DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS order_payments;
DROP TABLE IF EXISTS order_reviews;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS sellers;
DROP TABLE IF EXISTS geolocation;
DROP TABLE IF EXISTS product_category_translation;

CREATE TABLE customers (
    customer_id               TEXT PRIMARY KEY,
    customer_unique_id        TEXT NOT NULL,
    customer_zip_code_prefix  INTEGER,
    customer_city             TEXT,
    customer_state            TEXT
);

CREATE TABLE sellers (
    seller_id                 TEXT PRIMARY KEY,
    seller_zip_code_prefix    INTEGER,
    seller_city               TEXT,
    seller_state              TEXT
);

CREATE TABLE product_category_translation (
    product_category_name          TEXT PRIMARY KEY,
    product_category_name_english  TEXT
);

CREATE TABLE products (
    product_id                  TEXT PRIMARY KEY,
    product_category_name       TEXT,
    product_name_lenght         REAL,
    product_description_lenght  REAL,
    product_photos_qty          REAL,
    product_weight_g            REAL,
    product_length_cm           REAL,
    product_height_cm           REAL,
    product_width_cm            REAL,
    FOREIGN KEY (product_category_name)
        REFERENCES product_category_translation (product_category_name)
);

CREATE TABLE orders (
    order_id                       TEXT PRIMARY KEY,
    customer_id                    TEXT NOT NULL,
    order_status                   TEXT NOT NULL,
    order_purchase_timestamp       TEXT,
    order_approved_at              TEXT,
    order_delivered_carrier_date   TEXT,
    order_delivered_customer_date  TEXT,
    order_estimated_delivery_date  TEXT,
    FOREIGN KEY (customer_id) REFERENCES customers (customer_id)
);

CREATE TABLE order_items (
    order_id             TEXT NOT NULL,
    order_item_id        INTEGER NOT NULL,
    product_id           TEXT NOT NULL,
    seller_id            TEXT NOT NULL,
    shipping_limit_date  TEXT,
    price                REAL NOT NULL,
    freight_value        REAL NOT NULL,
    PRIMARY KEY (order_id, order_item_id),
    FOREIGN KEY (order_id)   REFERENCES orders (order_id),
    FOREIGN KEY (product_id) REFERENCES products (product_id),
    FOREIGN KEY (seller_id)  REFERENCES sellers (seller_id)
);

CREATE TABLE order_payments (
    order_id             TEXT NOT NULL,
    payment_sequential   INTEGER NOT NULL,
    payment_type         TEXT,
    payment_installments INTEGER,
    payment_value        REAL,
    PRIMARY KEY (order_id, payment_sequential),
    FOREIGN KEY (order_id) REFERENCES orders (order_id)
);

CREATE TABLE order_reviews (
    review_id                TEXT NOT NULL,
    order_id                 TEXT NOT NULL,
    review_score             INTEGER NOT NULL,
    review_comment_title     TEXT,
    review_comment_message   TEXT,
    review_creation_date     TEXT,
    review_answer_timestamp  TEXT,
    PRIMARY KEY (review_id, order_id),
    FOREIGN KEY (order_id) REFERENCES orders (order_id)
);

CREATE TABLE geolocation (
    geolocation_zip_code_prefix INTEGER,
    geolocation_lat             REAL,
    geolocation_lng             REAL,
    geolocation_city            TEXT,
    geolocation_state           TEXT
);
"""

INDICES = """
CREATE INDEX idx_orders_customer   ON orders (customer_id);
CREATE INDEX idx_orders_status     ON orders (order_status);
CREATE INDEX idx_orders_compra     ON orders (order_purchase_timestamp);
CREATE INDEX idx_items_product     ON order_items (product_id);
CREATE INDEX idx_items_seller      ON order_items (seller_id);
CREATE INDEX idx_payments_tipo     ON order_payments (payment_type);
CREATE INDEX idx_reviews_order     ON order_reviews (order_id);
CREATE INDEX idx_reviews_score     ON order_reviews (review_score);
CREATE INDEX idx_customers_estado  ON customers (customer_state);
CREATE INDEX idx_sellers_estado    ON sellers (seller_state);
CREATE INDEX idx_products_categoria ON products (product_category_name);
CREATE INDEX idx_geo_cep           ON geolocation (geolocation_zip_code_prefix);
"""

# nome da tabela no banco -> chave do dicionario de DataFrames
MAPA_TABELAS = {
    "customers": "customers",
    "sellers": "sellers",
    "product_category_translation": "translation",
    "products": "products",
    "orders": "orders",
    "order_items": "items",
    "order_payments": "payments",
    "order_reviews": "reviews",
    "geolocation": "geolocation",
}


def _preparar_para_sql(df: pd.DataFrame) -> pd.DataFrame:
    """Converte colunas datetime para texto ISO, que e como o SQLite guarda data."""
    copia = df.copy()
    for coluna in copia.columns:
        if pd.api.types.is_datetime64_any_dtype(copia[coluna]):
            copia[coluna] = copia[coluna].dt.strftime("%Y-%m-%d %H:%M:%S")
    return copia


def criar_banco(
    tabelas: dict[str, pd.DataFrame], caminho: Path | None = None
) -> Path:
    """Cria o banco SQLite do zero e carrega as nove tabelas.

    As categorias de produto presentes em products mas ausentes da tabela de
    traducao sao inseridas na tabela pai com traducao nula, para que a chave
    estrangeira feche. Sao poucos casos e a alternativa seria perder o
    relacionamento.
    """
    caminho = Path(caminho) if caminho is not None else config.CAMINHO_BANCO
    caminho.parent.mkdir(parents=True, exist_ok=True)
    if caminho.exists():
        caminho.unlink()

    conexao = sqlite3.connect(caminho)
    try:
        conexao.executescript(DDL)

        # Completa a tabela de traducao com categorias que existem em
        # products mas nao foram traduzidas, preservando a FK.
        traducao = tabelas["translation"].copy()
        categorias_produto = (
            tabelas["products"]["product_category_name"].dropna().unique()
        )
        faltantes = sorted(
            set(categorias_produto) - set(traducao["product_category_name"])
        )
        if faltantes:
            traducao = pd.concat(
                [
                    traducao,
                    pd.DataFrame(
                        {
                            "product_category_name": faltantes,
                            "product_category_name_english": [None] * len(faltantes),
                        }
                    ),
                ],
                ignore_index=True,
            )

        dados = dict(tabelas)
        dados["translation"] = traducao

        for tabela_sql, chave in MAPA_TABELAS.items():
            _preparar_para_sql(dados[chave]).to_sql(
                tabela_sql, conexao, if_exists="append", index=False
            )

        conexao.executescript(INDICES)
        conexao.execute("PRAGMA foreign_keys = ON;")
        conexao.commit()
    finally:
        conexao.close()

    return caminho


def conferir_chaves_estrangeiras(caminho: Path | None = None) -> pd.DataFrame:
    """Roda PRAGMA foreign_key_check e devolve as violacoes encontradas.

    DataFrame vazio significa modelo integro.
    """
    caminho = Path(caminho) if caminho is not None else config.CAMINHO_BANCO
    conexao = sqlite3.connect(caminho)
    try:
        violacoes = conexao.execute("PRAGMA foreign_key_check;").fetchall()
    finally:
        conexao.close()
    return pd.DataFrame(
        violacoes, columns=["tabela", "rowid", "tabela_referenciada", "indice_fk"]
    )


def contagem_tabelas(caminho: Path | None = None) -> pd.DataFrame:
    """Contagem de linhas de cada tabela do banco, para conferencia da carga."""
    caminho = Path(caminho) if caminho is not None else config.CAMINHO_BANCO
    conexao = sqlite3.connect(caminho)
    try:
        linhas = [
            {
                "tabela": tabela,
                "linhas": conexao.execute(
                    f"SELECT COUNT(*) FROM {tabela}"
                ).fetchone()[0],
            }
            for tabela in MAPA_TABELAS
        ]
    finally:
        conexao.close()
    return pd.DataFrame(linhas)


def consultar(sql: str, caminho: Path | None = None) -> pd.DataFrame:
    """Executa um SELECT e devolve o resultado como DataFrame."""
    caminho = Path(caminho) if caminho is not None else config.CAMINHO_BANCO
    conexao = sqlite3.connect(caminho)
    try:
        return pd.read_sql_query(sql, conexao)
    finally:
        conexao.close()


def consultar_arquivo(nome_arquivo: str, caminho: Path | None = None) -> pd.DataFrame:
    """Executa uma consulta guardada na pasta consultas/."""
    sql = (config.PASTA_CONSULTAS / nome_arquivo).read_text(encoding="utf-8")
    return consultar(sql, caminho)
