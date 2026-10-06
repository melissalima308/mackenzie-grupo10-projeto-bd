-- 03 - Desempenho logistico dos pedidos entregues
--
-- Criterio de atraso adotado no projeto: comparacao por data e hora. O campo
-- order_estimated_delivery_date registra apenas a data, sempre com hora
-- 00:00:00, o que equivale a dizer que o prazo vence a meia-noite. Uma
-- entrega feita as 14h do proprio dia estimado conta como atraso.
--
-- CAST AS INTEGER nas medias de tempo trunca a fracao de dia, o mesmo que o
-- pandas faz em Timedelta.dt.days. Sem o CAST a media sobe de 12,09 para
-- 12,56 e as duas camadas do projeto deixam de bater.
SELECT
    COUNT(*) AS pedidos_entregues,
    ROUND(AVG(CAST(julianday(order_delivered_customer_date)
                 - julianday(order_purchase_timestamp) AS INTEGER)), 2) AS tempo_entrega_medio,
    ROUND(AVG(CAST(julianday(order_estimated_delivery_date)
                 - julianday(order_purchase_timestamp) AS INTEGER)), 2) AS prazo_estimado_medio,
    -- Criterio adotado
    ROUND(100.0 * SUM(
        CASE WHEN julianday(order_delivered_customer_date)
                > julianday(order_estimated_delivery_date)
             THEN 1 ELSE 0 END) / COUNT(*), 2)                          AS pct_atrasado,
    -- Analise de sensibilidade: comparacao por dia de calendario
    ROUND(100.0 * SUM(
        CASE WHEN julianday(date(order_delivered_customer_date))
                > julianday(date(order_estimated_delivery_date))
             THEN 1 ELSE 0 END) / COUNT(*), 2)                          AS pct_atrasado_por_dia
FROM orders
WHERE order_status = 'delivered'
  AND order_delivered_customer_date IS NOT NULL
  AND order_estimated_delivery_date IS NOT NULL;
