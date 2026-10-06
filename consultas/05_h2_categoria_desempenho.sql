-- 05 - Hipotese H2: desempenho por categoria de produto
-- Usa a traducao para ingles quando existe e cai para o nome em portugues
-- quando falta, mantendo os 610 produtos sem categoria sob 'sem_categoria'.
WITH itens AS (
    SELECT
        i.order_id,
        i.price,
        i.freight_value,
        COALESCE(t.product_category_name_english,
                 p.product_category_name,
                 'sem_categoria') AS categoria
    FROM order_items i
    LEFT JOIN products p ON p.product_id = i.product_id
    LEFT JOIN product_category_translation t
           ON t.product_category_name = p.product_category_name
),
notas AS (
    SELECT order_id, AVG(review_score) AS nota
    FROM order_reviews
    GROUP BY order_id
),
pedido_categoria AS (
    SELECT DISTINCT order_id, categoria FROM itens
),
nota_categoria AS (
    SELECT pc.categoria, ROUND(AVG(n.nota), 2) AS nota_media
    FROM pedido_categoria pc
    JOIN notas n ON n.order_id = pc.order_id
    GROUP BY pc.categoria
)
SELECT
    it.categoria,
    COUNT(DISTINCT it.order_id)                                  AS pedidos,
    COUNT(*)                                                     AS itens,
    ROUND(SUM(it.price), 2)                                      AS receita,
    ROUND(AVG(it.price), 2)                                      AS preco_medio,
    ROUND(AVG(it.freight_value), 2)                              AS frete_medio,
    ROUND(SUM(it.price) / COUNT(DISTINCT it.order_id), 2)        AS ticket_medio,
    nc.nota_media
FROM itens it
LEFT JOIN nota_categoria nc ON nc.categoria = it.categoria
GROUP BY it.categoria
HAVING pedidos >= 100
ORDER BY receita DESC;
