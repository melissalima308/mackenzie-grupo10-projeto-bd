-- 07 - Distribuicao geografica de clientes e vendedores por UF
WITH clientes AS (
    SELECT customer_state AS uf, COUNT(*) AS clientes
    FROM customers GROUP BY customer_state
),
vendedores AS (
    SELECT seller_state AS uf, COUNT(*) AS vendedores
    FROM sellers GROUP BY seller_state
)
SELECT
    c.uf,
    c.clientes,
    COALESCE(v.vendedores, 0)                                               AS vendedores,
    ROUND(100.0 * c.clientes / (SELECT SUM(clientes) FROM clientes), 2)      AS pct_clientes,
    ROUND(100.0 * COALESCE(v.vendedores, 0)
          / (SELECT SUM(vendedores) FROM vendedores), 2)                    AS pct_vendedores
FROM clientes c
LEFT JOIN vendedores v ON v.uf = c.uf
ORDER BY c.clientes DESC;
