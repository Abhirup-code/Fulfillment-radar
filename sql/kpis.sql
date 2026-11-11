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

-- name: cancellation_drilldown
-- Was the worst cancellation month caused by one region or category, or by everything at once?
-- Compares each group's cancellation rate in that month against the rest of the year.
WITH monthly AS (
  SELECT substr(order_date, 1, 7) AS month, AVG(status = 'cancelled') AS rate
  FROM orders GROUP BY month
),
peak AS (SELECT month FROM monthly ORDER BY rate DESC, month LIMIT 1),
tagged AS (
  SELECT CASE WHEN substr(o.order_date, 1, 7) = (SELECT month FROM peak) THEN 1 ELSE 0 END AS in_peak,
         o.status = 'cancelled' AS cancelled, s.category, s.region AS seller_region, b.region AS buyer_region
  FROM orders o JOIN sellers s USING (seller_id) JOIN buyers b USING (buyer_id)
),
grouped AS (
  SELECT 'buyer region' AS dimension, buyer_region AS value, in_peak, cancelled FROM tagged
  UNION ALL SELECT 'seller region', seller_region, in_peak, cancelled FROM tagged
  UNION ALL SELECT 'category', category, in_peak, cancelled FROM tagged
)
SELECT (SELECT month FROM peak) AS peak_month, dimension, value,
       SUM(in_peak) AS peak_orders,
       ROUND(100.0 * SUM(in_peak AND cancelled) / SUM(in_peak), 1) AS peak_cancel_pct,
       ROUND(100.0 * SUM(NOT in_peak AND cancelled) / SUM(NOT in_peak), 1) AS other_cancel_pct
FROM grouped
GROUP BY dimension, value
ORDER BY dimension, value;

-- name: cohort_retention
-- Buyers grouped by the month of their first non-cancelled order (their cohort), and the share of
-- each cohort that ordered again 1, 2, and 3 months later.
WITH o AS (
  SELECT buyer_id,
         CAST(substr(order_date, 1, 4) AS INTEGER) * 12 + CAST(substr(order_date, 6, 2) AS INTEGER) AS m
  FROM orders WHERE status != 'cancelled'
),
first AS (SELECT buyer_id, MIN(m) AS start FROM o GROUP BY buyer_id),
size AS (SELECT start, COUNT(*) AS cohort_buyers FROM first GROUP BY start),
active AS (
  SELECT f.start, o.m - f.start AS months_after, COUNT(DISTINCT o.buyer_id) AS active_buyers
  FROM o JOIN first f USING (buyer_id)
  WHERE o.m - f.start BETWEEN 1 AND 3
  GROUP BY f.start, months_after
),
grid AS (
  SELECT s.start, s.cohort_buyers, n.months_after
  FROM size s CROSS JOIN (SELECT 1 AS months_after UNION ALL SELECT 2 UNION ALL SELECT 3) n
  WHERE s.start + n.months_after <= (SELECT MAX(m) FROM o)
)
SELECT printf('%04d-%02d', (g.start - 1) / 12, (g.start - 1) % 12 + 1) AS cohort,
       g.cohort_buyers, g.months_after,
       COALESCE(a.active_buyers, 0) AS active_buyers,
       ROUND(100.0 * COALESCE(a.active_buyers, 0) / g.cohort_buyers, 1) AS retention_pct
FROM grid g LEFT JOIN active a ON a.start = g.start AND a.months_after = g.months_after
ORDER BY cohort, g.months_after;
