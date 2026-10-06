"""
Orquestrador do pipeline.

Roda todas as etapas em sequencia:
    carga -> validacao -> banco SQLite -> EDA -> H1 -> H2 -> dashboard

Uso:
    python executar.py                  pipeline completo
    python executar.py --sem-banco      pula a criacao do SQLite
    python executar.py --so-dashboard   nao recria as figuras do relatorio
    python executar.py --dados CAMINHO  aponta para outra pasta de CSV

Projeto Aplicado 1 - Grupo 10 - Universidade Presbiteriana Mackenzie
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from src import banco, carga, config, dashboard, eda, h1_atraso, h2_categoria


def titulo(texto: str) -> None:
    print("\n" + "=" * 72)
    print(texto)
    print("=" * 72)


def main() -> int:
    analisador = argparse.ArgumentParser(
        description="Pipeline de análise do dataset da Olist - Grupo 10"
    )
    analisador.add_argument(
        "--dados",
        type=Path,
        default=None,
        help="pasta com os nove arquivos CSV (padrão: ./dados)",
    )
    analisador.add_argument(
        "--sem-banco",
        action="store_true",
        help="não cria o banco SQLite",
    )
    analisador.add_argument(
        "--so-dashboard",
        action="store_true",
        help="roda as análises em silêncio e gera apenas o dashboard",
    )
    argumentos = analisador.parse_args()

    verbose = not argumentos.so_dashboard
    inicio = time.time()
    config.garantir_pastas()

    pasta_dados = argumentos.dados or config.PASTA_DADOS

    # ------------------------------------------------------------------
    titulo("1. CARGA DOS DADOS")
    print(f"Pasta de dados: {pasta_dados}")
    try:
        tabelas = carga.carregar_tabelas(pasta_dados)
    except FileNotFoundError as erro:
        print(f"\nERRO: {erro}")
        return 1

    for nome, df in tabelas.items():
        print(f"  {nome:<12} {len(df):>9,} linhas  x {df.shape[1]:>2} colunas")

    # ------------------------------------------------------------------
    titulo("2. VALIDAÇÃO DA ESTRUTURA")
    unicidade = carga.verificar_unicidade(tabelas)
    integridade = carga.validar_integridade(tabelas)
    print("Chaves candidatas:")
    print(unicidade.to_string(index=False))
    print("\nIntegridade referencial:")
    print(integridade.to_string(index=False))

    orfaos = int(integridade["orfaos"].sum())
    if orfaos:
        print(f"\nATENÇÃO: {orfaos:,} registros órfãos encontrados.")
    else:
        print("\nNenhum registro órfão. O modelo relacional fecha.")

    # ------------------------------------------------------------------
    if not argumentos.sem_banco:
        titulo("3. BANCO DE DADOS RELACIONAL (SQLite)")
        caminho_banco = banco.criar_banco(tabelas)
        print(f"Banco criado em: {caminho_banco}")
        print(f"Tamanho: {caminho_banco.stat().st_size / 1024 / 1024:.1f} MB\n")
        print(banco.contagem_tabelas().to_string(index=False))

        violacoes = banco.conferir_chaves_estrangeiras()
        if violacoes.empty:
            print("\nPRAGMA foreign_key_check: nenhuma violação.")
        else:
            print(f"\nATENÇÃO: {len(violacoes)} violações de chave estrangeira.")

        print("\nConsultas disponíveis em consultas/:")
        for arquivo in sorted(config.PASTA_CONSULTAS.glob("*.sql")):
            print(f"  {arquivo.name}")
    else:
        titulo("3. BANCO DE DADOS RELACIONAL (pulado)")

    # ------------------------------------------------------------------
    titulo("4. ANÁLISE EXPLORATÓRIA")
    resultado_eda = eda.executar(tabelas, verbose=verbose)

    titulo("5. HIPÓTESE H1")
    resultado_h1 = h1_atraso.executar(tabelas, verbose=verbose)

    titulo("6. HIPÓTESE H2")
    resultado_h2 = h2_categoria.executar(tabelas, verbose=verbose)

    # ------------------------------------------------------------------
    titulo("7. DASHBOARD")
    caminho_dashboard = dashboard.gerar(
        tabelas, resultado_eda, resultado_h1, resultado_h2
    )
    print(f"Dashboard gerado em: {caminho_dashboard}")
    print(f"Tamanho: {caminho_dashboard.stat().st_size / 1024:.0f} KB")

    # Copia para docs/index.html, que e a pasta publicada pelo GitHub Pages.
    config.PASTA_DOCS.mkdir(parents=True, exist_ok=True)
    config.CAMINHO_PAGES.write_text(
        caminho_dashboard.read_text(encoding="utf-8"), encoding="utf-8"
    )
    print(f"Cópia para o GitHub Pages: {config.CAMINHO_PAGES}")

    # ------------------------------------------------------------------
    figuras = sorted(config.PASTA_FIGURAS.glob("*.png"))
    tabelas_csv = sorted(config.PASTA_TABELAS.glob("*.csv"))

    titulo("CONCLUÍDO")
    print(f"Tempo total: {time.time() - inicio:.1f} segundos")
    print(f"Figuras geradas: {len(figuras)} em {config.PASTA_FIGURAS}")
    print(f"Tabelas geradas: {len(tabelas_csv)} em {config.PASTA_TABELAS}")
    print(f"Dashboard: {caminho_dashboard}")
    print("\nAbra o dashboard com duplo clique ou publique a pasta no GitHub Pages.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
