-- 02 - Sazonalidade: pedidos e receita por mes de compra
-- Alimenta o Grafico 1 do trabalho.
SELECT
    substr(o.order_purchase_timestamp, 1, 7)            AS ano_mes,
    COUNT(DISTINCT o.order_id)                          AS pedidos,
    ROUND(SUM(i.price), 2)                              AS receita,
    ROUND(SUM(i.price) / COUNT(DISTINCT o.order_id), 2) AS ticket_medio
FROM orders o
LEFT JOIN order_items i ON i.order_id = o.order_id
GROUP BY ano_mes
ORDER BY ano_mes;
