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

## 2. One seller is reliably late, and the next few are not
Seller **7** (Produce, Milwaukee) delivers on time
only **64.4%** of the time across 87 orders. Even the top of its
95% confidence interval (53.9% to 73.6%) is under the 85% target, so this is
not bad luck.

The next lowest sellers (86.6% to 87.4% on time) look worrying in a ranked
list, but they are not clearly below target: 15 sellers are **too close to call**, because their
intervals still include 85%. Their low rank may just be chance, and chasing them would mean
chasing noise. Only 1 of 40 sellers is reliably below target (`seller_flags.csv`).
Recommendation: review seller 7's promised delivery windows, flag its late orders
before the buyer has to ask, and recheck the "too close to call" sellers once they have more orders.

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
