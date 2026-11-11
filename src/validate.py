"""Data quality checks that run before any KPI is computed.

A dashboard built on bad rows is worse than no dashboard, so the analysis stops with a clear
list of problems instead of quietly producing wrong numbers.
"""

import pandas as pd

STATUSES = {"delivered", "cancelled", "disputed"}
COLUMNS = {
    "sellers": ["seller_id", "category", "region"],
    "buyers": ["buyer_id", "region", "signup_date"],
    "orders": [
        "order_id",
        "buyer_id",
        "seller_id",
        "order_date",
        "quantity",
        "amount",
        "status",
        "promised_days",
        "actual_days",
    ],
}


def check(sellers: pd.DataFrame, buyers: pd.DataFrame, orders: pd.DataFrame) -> list[str]:
    """Every problem found, as a sentence. An empty list means the data is fit to analyze."""
    tables = {"sellers": sellers, "buyers": buyers, "orders": orders}
    problems = []
    for name, cols in COLUMNS.items():
        missing = [c for c in cols if c not in tables[name].columns]
        if missing:
            problems.append(f"{name} is missing columns: {', '.join(missing)}")
    if problems:
        return problems  # the checks below need these columns

    def bad(mask, what):
        n = int(mask.sum())
        if n:
            problems.append(f"{n} {what}")

    o = orders
    bad(o.order_id.duplicated(), "duplicate order ids")
    bad(sellers.seller_id.duplicated(), "duplicate seller ids")
    bad(buyers.buyer_id.duplicated(), "duplicate buyer ids")
    bad(~(o.amount > 0), "orders with an amount that is zero, negative, or missing")
    bad(~(o.quantity >= 1), "orders with a quantity below 1")
    bad(~o.status.isin(STATUSES), f"orders with a status other than {', '.join(sorted(STATUSES))}")
    bad(~(o.promised_days >= 1), "orders promised in under 1 day")
    cancelled = o.status == "cancelled"
    bad(cancelled & o.actual_days.notna(), "cancelled orders with a delivery time")
    bad(
        ~cancelled & o.status.isin(STATUSES) & o.actual_days.isna(),
        "delivered or disputed orders with no delivery time",
    )
    bad(~o.buyer_id.isin(buyers.buyer_id), "orders from an unknown buyer")
    bad(~o.seller_id.isin(sellers.seller_id), "orders from an unknown seller")

    dates = pd.to_datetime(o.order_date, errors="coerce", format="%Y-%m-%d")
    bad(dates.isna(), "orders with a missing or unreadable date")
    # drop_duplicates: a duplicated buyer is reported above and must not crash this lookup
    first_signup = buyers.drop_duplicates("buyer_id").set_index("buyer_id").signup_date
    signup = pd.to_datetime(o.buyer_id.map(first_signup), errors="coerce")
    bad(dates < signup, "orders placed before the buyer signed up")
    return problems
