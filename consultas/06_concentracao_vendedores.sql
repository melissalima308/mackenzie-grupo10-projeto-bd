-- 06 - Concentracao de receita entre vendedores
-- Usa funcao de janela para montar a curva acumulada. Requer SQLite 3.25
-- ou superior, disponivel em qualquer Python 3.8+.
WITH receita_vendedor AS (
    SELECT seller_id, SUM(price) AS receita
    FROM order_items
    GROUP BY seller_id
),
ordenado AS (
    SELECT
        seller_id,
        receita,
        ROW_NUMBER() OVER (ORDER BY receita DESC)                AS posicao,
        SUM(receita) OVER (ORDER BY receita DESC
                           ROWS BETWEEN UNBOUNDED PRECEDING
                                    AND CURRENT ROW)             AS receita_acumulada,
        (SELECT SUM(receita) FROM receita_vendedor)              AS receita_total,
        (SELECT COUNT(*)     FROM receita_vendedor)              AS total_vendedores
    FROM receita_vendedor
)
SELECT
    posicao,
    seller_id,
    ROUND(receita, 2)                                            AS receita,
    ROUND(100.0 * posicao / total_vendedores, 2)                 AS pct_vendedores,
    ROUND(100.0 * receita_acumulada / receita_total, 2)          AS pct_receita_acumulada
FROM ordenado
ORDER BY posicao;
