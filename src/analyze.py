"""Load the CSVs into SQLite, run the KPI queries, and write tables, charts and findings."""
import re
import sqlite3
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]


def build_db(data_dir=ROOT / "data"):
    con = sqlite3.connect(":memory:")
    con.executescript((ROOT / "sql" / "schema.sql").read_text())
    for t in ("sellers", "buyers", "orders"):
        pd.read_csv(Path(data_dir) / f"{t}.csv").to_sql(t, con, if_exists="append", index=False)
    return con


def load_queries():
    text = (ROOT / "sql" / "kpis.sql").read_text()
    out = {}
    for block in re.split(r"-- name: ", text)[1:]:
        name, sql = block.split("\n", 1)
        out[name.strip()] = sql.strip()
    return out


def run_all(con):
    return {name: pd.read_sql_query(sql, con) for name, sql in load_queries().items()}


def charts(r, outdir):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    m = r["monthly_kpis"]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(m["month"], m["gmv"], color="#2b6cb0")
    ax.set_title("Monthly GMV (synthetic data)")
    ax.set_ylabel("GMV ($)")
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout(); fig.savefig(outdir / "monthly_gmv.png", dpi=130); plt.close(fig)

    c = r["cancellation_rate_by_month"]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(c["month"], c["cancel_rate_pct"], marker="o", color="#c53030")
    ax.set_title("Cancellation rate by month (%)")
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout(); fig.savefig(outdir / "cancellation_rate.png", dpi=130); plt.close(fig)

    cat = r["category_performance"]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(cat["category"], cat["gmv"], color="#2f855a")
    ax.set_title("GMV by category")
    ax.set_ylabel("GMV ($)")
    ax.tick_params(axis="x", rotation=30)
    fig.tight_layout(); fig.savefig(outdir / "category_gmv.png", dpi=130); plt.close(fig)

    rv = r["repeat_vs_one_time"]
    fig, axes = plt.subplots(1, 2, figsize=(8, 4))
    axes[0].bar(rv["segment"], rv["buyers"], color=["#718096", "#2b6cb0"])
    axes[0].set_title("Buyers")
    axes[1].bar(rv["segment"], rv["total_spend"], color=["#718096", "#2b6cb0"])
    axes[1].set_title("Total spend ($)")
    fig.suptitle("Repeat vs one-time buyers")
    fig.tight_layout(); fig.savefig(outdir / "repeat_vs_one_time.png", dpi=130); plt.close(fig)

    s = r["seller_on_time"].head(10)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.barh(s["seller_id"].astype(str), s["on_time_pct"], color="#dd6b20")
    ax.set_title("Lowest on-time delivery rate by seller (%)")
    ax.set_ylabel("Seller ID")
    ax.invert_yaxis()
    fig.tight_layout(); fig.savefig(outdir / "seller_on_time.png", dpi=130); plt.close(fig)


def findings(r):
    m, c, s = r["monthly_kpis"], r["cancellation_rate_by_month"], r["seller_on_time"]
    rv = r["repeat_vs_one_time"].set_index("segment")
    worst = s.iloc[0]
    peak = c.loc[c["cancel_rate_pct"].idxmax()]
    typical = c.loc[c["month"] != peak["month"], "cancel_rate_pct"].median()
    rep, one = rv.loc["repeat"], rv.loc["one-time"]
    share = 100 * rep["total_spend"] / (rep["total_spend"] + one["total_spend"])
    best_month = m.loc[m["gmv"].idxmax()]
    cat = r["category_performance"].iloc[0]
    return f"""# Findings

These findings come from **synthetic** data with a few patterns built in on purpose.
They show the method, not real business results.

## 1. Cancellations spiked in {peak['month']}
The cancellation rate hit **{peak['cancel_rate_pct']}%** in {peak['month']}, against a typical
month of about **{typical}%**. In a real business I would next check whether the spike
came from one seller, one region, or one product category, and whether it lines up
with a stock-out, a pricing change, or a delivery problem.

## 2. One seller drags down delivery performance
Seller **{int(worst['seller_id'])}** ({worst['category']}, {worst['region']}) delivers on time
only **{worst['on_time_pct']}%** of the time across {int(worst['delivered_orders'])} orders.
Recommendation: review this seller's promised delivery windows, and flag late orders
before the buyer has to ask.

## 3. Repeat buyers carry the revenue
Repeat buyers are {int(rep['buyers'])} of {int(rep['buyers'] + one['buyers'])} buyers but account for
**{share:.0f}%** of spend (average ${rep['avg_spend']:,.0f} against ${one['avg_spend']:,.0f} for one-time buyers).
Recommendation: put effort into getting a second order from new buyers.

## 4. Revenue overview
Best month for GMV was **{best_month['month']}** (${best_month['gmv']:,.0f}). The top category by GMV
was **{cat['category']}** (${cat['gmv']:,.0f}).

## Assumptions
- GMV and AOV exclude cancelled orders.
- On-time means delivered within the promised number of days.
- A repeat buyer has two or more non-cancelled orders.
"""


def main():
    con = build_db()
    r = run_all(con)
    out = ROOT / "reports"
    out.mkdir(exist_ok=True)
    for k, v in r.items():
        v.to_csv(out / f"{k}.csv", index=False)
    charts(r, out / "charts")
    (out / "FINDINGS.md").write_text(findings(r))
    print("wrote reports/")


if __name__ == "__main__":
    main()
