"""Generate a synthetic B2B marketplace dataset (buyers, sellers, orders, deliveries).

The data is SYNTHETIC. It has a few patterns built in on purpose (a seller with late
deliveries, a cancellation spike, repeat buyers who spend more) so the analysis has
something real to find. Nothing here comes from any real company.
"""
import argparse
import numpy as np
import pandas as pd

CATEGORIES = ["Produce", "Dairy", "Meat", "Bakery", "Dry Goods", "Beverages", "Packaging"]
REGIONS = ["Chicago", "Milwaukee", "Indianapolis", "Detroit"]
BASE_PRICE = {"Produce": 38, "Dairy": 52, "Meat": 110, "Bakery": 44,
              "Dry Goods": 60, "Beverages": 70, "Packaging": 35}


def generate(seed=42, n_sellers=40, n_buyers=1200, n_orders=4000):
    rng = np.random.default_rng(seed)

    sellers = pd.DataFrame({
        "seller_id": np.arange(1, n_sellers + 1),
        "category": rng.choice(CATEGORIES, n_sellers),
        "region": rng.choice(REGIONS, n_sellers),
    })
    # Planted pattern 1: seller 7 is chronically late.
    sellers["base_late_rate"] = 0.08
    sellers.loc[sellers.seller_id == 7, "base_late_rate"] = 0.45

    buyers = pd.DataFrame({
        "buyer_id": np.arange(1, n_buyers + 1),
        "region": rng.choice(REGIONS, n_buyers, p=[0.45, 0.2, 0.2, 0.15]),
        "signup_date": pd.to_datetime("2025-01-01")
        + pd.to_timedelta(rng.integers(0, 330, n_buyers), unit="D"),
    })
    # Planted pattern 2: ~30% of buyers are "loyal" and order more, with bigger baskets.
    buyers["loyal"] = rng.random(n_buyers) < 0.30

    # Order propensity is heavy-tailed: most buyers order rarely, a few order a lot.
    weights = (rng.pareto(2.0, n_buyers) + 0.2) * np.where(buyers.loyal, 6.0, 1.0)
    weights = weights / weights.sum()

    rows = []
    for oid in range(1, n_orders + 1):
        b = buyers.iloc[rng.choice(n_buyers, p=weights)]
        s = sellers.iloc[rng.integers(0, n_sellers)]
        earliest = b.signup_date
        span = (pd.Timestamp("2025-12-31") - earliest).days
        if span <= 0:
            continue
        # Mild seasonality: more orders in Q4.
        day = int(rng.triangular(0, span * 0.8, span))
        order_date = earliest + pd.Timedelta(days=day)
        base = BASE_PRICE[s.category]
        qty = max(1, int(rng.normal(8 if b.loyal else 5, 3)))
        amount = round(base * qty * rng.uniform(0.85, 1.25), 2)

        # Planted pattern 3: cancellation spike in August 2025.
        cancel_p = 0.04
        if order_date.year == 2025 and order_date.month == 8:
            cancel_p = 0.16
        status = "cancelled" if rng.random() < cancel_p else (
            "disputed" if rng.random() < 0.03 else "delivered")

        promised = int(rng.integers(1, 4))
        late = rng.random() < s.base_late_rate
        actual = promised + (int(rng.integers(1, 4)) if late else 0)
        if status == "cancelled":
            actual = np.nan
        rows.append((oid, b.buyer_id, s.seller_id, order_date.date().isoformat(),
                     qty, amount, status, promised, actual))

    orders = pd.DataFrame(rows, columns=[
        "order_id", "buyer_id", "seller_id", "order_date", "quantity",
        "amount", "status", "promised_days", "actual_days"])
    return sellers.drop(columns=["base_late_rate"]), buyers.drop(columns=["loyal"]), orders


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    s, b, o = generate(a.seed)
    s.to_csv(f"{a.out}/sellers.csv", index=False)
    b.to_csv(f"{a.out}/buyers.csv", index=False)
    o.to_csv(f"{a.out}/orders.csv", index=False)
    print(f"sellers={len(s)} buyers={len(b)} orders={len(o)}")
