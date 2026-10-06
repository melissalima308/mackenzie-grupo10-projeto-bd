-- 08 - Formas de pagamento, valor e parcelamento
SELECT
    payment_type                                                   AS forma_pagamento,
    COUNT(*)                                                       AS registros,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM order_payments), 2) AS pct_registros,
    ROUND(SUM(payment_value), 2)                                   AS valor_total,
    ROUND(AVG(payment_value), 2)                                   AS valor_medio,
    ROUND(AVG(payment_installments), 2)                            AS parcelas_medias
FROM order_payments
GROUP BY payment_type
ORDER BY registros DESC;
