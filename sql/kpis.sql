-- name: monthly_kpis
-- Gross merchandise value (GMV), orders, and average order value (AOV) per month.
-- Cancelled orders are excluded from GMV and AOV.
SELECT substr(order_date, 1, 7) AS month,
       COUNT(*) AS orders,
       ROUND(SUM(amount), 2) AS gmv,
       ROUND(AVG(amount), 2) AS aov
FROM orders
WHERE status != 'cancelled'
GROUP BY month
ORDER BY month;

-- name: cancellation_rate_by_month
SELECT substr(order_date, 1, 7) AS month,
       COUNT(*) AS orders,
       SUM(status = 'cancelled') AS cancelled,
       ROUND(100.0 * SUM(status = 'cancelled') / COUNT(*), 1) AS cancel_rate_pct
FROM orders
GROUP BY month
ORDER BY month;

-- name: seller_on_time
-- On-time = delivered within the promised number of days.
SELECT o.seller_id, s.category, s.region,
       COUNT(*) AS delivered_orders,
       ROUND(100.0 * SUM(o.actual_days <= o.promised_days) / COUNT(*), 1) AS on_time_pct,
       ROUND(SUM(o.amount), 2) AS gmv
FROM orders o JOIN sellers s USING (seller_id)
WHERE o.status != 'cancelled'
GROUP BY o.seller_id
HAVING delivered_orders >= 30
ORDER BY on_time_pct ASC;

-- name: repeat_vs_one_time
-- A repeat buyer has 2 or more non-cancelled orders.
WITH per_buyer AS (
  SELECT buyer_id, COUNT(*) AS n, SUM(amount) AS spend
  FROM orders WHERE status != 'cancelled' GROUP BY buyer_id
)
SELECT CASE WHEN n >= 2 THEN 'repeat' ELSE 'one-time' END AS segment,
       COUNT(*) AS buyers,
       ROUND(AVG(n), 2) AS avg_orders,
       ROUND(AVG(spend), 2) AS avg_spend,
       ROUND(SUM(spend), 2) AS total_spend
FROM per_buyer GROUP BY segment;

-- name: category_performance
SELECT s.category,
       COUNT(*) AS orders,
       ROUND(SUM(o.amount), 2) AS gmv,
       ROUND(AVG(o.amount), 2) AS aov
FROM orders o JOIN sellers s USING (seller_id)
WHERE o.status != 'cancelled'
GROUP BY s.category
ORDER BY gmv DESC;

-- name: top_buyers
SELECT buyer_id, COUNT(*) AS orders, ROUND(SUM(amount), 2) AS spend
FROM orders WHERE status != 'cancelled'
GROUP BY buyer_id ORDER BY spend DESC LIMIT 10;
