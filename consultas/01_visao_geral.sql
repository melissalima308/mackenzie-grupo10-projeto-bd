-- 01 - Visao geral do dataset
-- Numeros-chave do modelo, usados na secao 3.1 e 4.1 do trabalho.
SELECT 'pedidos'            AS metrica, COUNT(*) AS valor FROM orders
UNION ALL
SELECT 'clientes (customer_id)',        COUNT(*) FROM customers
UNION ALL
SELECT 'clientes unicos',               COUNT(DISTINCT customer_unique_id) FROM customers
UNION ALL
SELECT 'vendedores',                    COUNT(*) FROM sellers
UNION ALL
SELECT 'produtos',                      COUNT(*) FROM products
UNION ALL
SELECT 'itens vendidos',                COUNT(*) FROM order_items
UNION ALL
SELECT 'registros de pagamento',        COUNT(*) FROM order_payments
UNION ALL
SELECT 'avaliacoes',                    COUNT(*) FROM order_reviews
UNION ALL
SELECT 'linhas de geolocalizacao',      COUNT(*) FROM geolocation;
