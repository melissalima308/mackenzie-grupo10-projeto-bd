-- 04 - Hipotese H1: atraso na entrega x nota do cliente
--
-- A CTE pedidos_entregues calcula o atraso como diferenca continua em dias
-- entre a entrega e a data estimada, com hora. As faixas usam os limites
-- superiores diretamente sobre esse valor continuo, o que equivale a
-- arredondar o atraso para cima: ceil(d) entre 1 e 3 e o mesmo que
-- 0 < d <= 3. E assim que o Python classifica, e os dois resultados batem.
--
-- A CTE notas agrega as avaliacoes por pedido, porque existem pedidos com
-- mais de uma avaliacao registrada.
WITH pedidos_entregues AS (
    SELECT
        order_id,
        julianday(order_delivered_customer_date)
      - julianday(order_estimated_delivery_date) AS atraso
    FROM orders
    WHERE order_status = 'delivered'
      AND order_delivered_customer_date IS NOT NULL
      AND order_estimated_delivery_date IS NOT NULL
),
notas AS (
    SELECT order_id, AVG(review_score) AS nota
    FROM order_reviews
    GROUP BY order_id
),
classificado AS (
    SELECT
        p.order_id,
        p.atraso,
        n.nota,
        CASE
            WHEN p.atraso <= 0  THEN '1. No prazo'
            WHEN p.atraso <= 3  THEN '2. 1 a 3 dias'
            WHEN p.atraso <= 7  THEN '3. 4 a 7 dias'
            WHEN p.atraso <= 14 THEN '4. 8 a 14 dias'
            ELSE                     '5. Mais de 14 dias'
        END AS faixa_atraso
    FROM pedidos_entregues p
    JOIN notas n ON n.order_id = p.order_id
)
SELECT
    faixa_atraso,
    COUNT(*)                                                        AS pedidos,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)              AS pct_pedidos,
    ROUND(AVG(nota), 2)                                             AS nota_media,
    -- ROUND(nota) porque um pedido pode ter mais de uma avaliacao e a media
    -- resulta em valor quebrado. O mesmo arredondamento e aplicado no Python.
    ROUND(100.0 * SUM(CASE WHEN ROUND(nota) <= 2 THEN 1 ELSE 0 END)
          / COUNT(*), 2)                                            AS pct_nota_1_ou_2,
    ROUND(100.0 * SUM(CASE WHEN ROUND(nota) >= 4 THEN 1 ELSE 0 END)
          / COUNT(*), 2)                                            AS pct_nota_4_ou_5
FROM classificado
GROUP BY faixa_atraso
ORDER BY faixa_atraso;
