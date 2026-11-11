# Findings

These findings come from **synthetic** data with a few patterns built in on purpose.
They show the method, not real business results.

## 1. Cancellations spiked in 2025-08
The cancellation rate hit **16.3%** in 2025-08, against a typical
month of about **2.8%**.

**It was not one region or one category.** In 2025-08 the rate rose in every buyer region,
every seller region, and every category, to between **10.7%** and
**25.0%**, while each of them stayed between 3.2% and
5.7% the rest of the year (see `cancellation_drilldown.csv`). The smallest
groups swing the most, because a few orders move their rate a lot.
When everything moves together, the cause is usually marketplace-wide: a checkout or payment
problem, a policy or pricing change, or a stock-out across many sellers. That is where I would look next.

## 2. One seller drags down delivery performance
Seller **7** (Produce, Milwaukee) delivers on time
only **64.4%** of the time across 87 orders.
Recommendation: review this seller's promised delivery windows, and flag late orders
before the buyer has to ask.

## 3. Repeat buyers carry the revenue
Repeat buyers are 508 of 778 buyers but account for
**94%** of spend (average $2,747 against $324 for one-time buyers).
Recommendation: put effort into getting a second order from new buyers.

## 4. Revenue overview
Best month for GMV was **2025-11** ($382,595). The top category by GMV
was **Beverages** ($467,862).

## Assumptions
- GMV and AOV exclude cancelled orders.
- On-time means delivered within the promised number of days.
- A repeat buyer has two or more non-cancelled orders.
