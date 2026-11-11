"""Load the CSVs into SQLite, run the KPI queries, and write tables, charts and findings."""
import math
import re
import sqlite3
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.validate import check

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
    r = {name: pd.read_sql_query(sql, con) for name, sql in load_queries().items()}
    r["seller_flags"] = seller_flags(r["seller_on_time"])
    return r


MIN_COHORT = 20  # smaller cohorts swing too much to compare
ON_TIME_TARGET = 85.0  # the on-time rate a seller is expected to hold, in percent


def wilson(successes, n, z=1.96):
    """95% Wilson score interval for a rate, in percent. It stays sensible for small samples,
    where the plain +/- formula breaks down."""
    if n == 0:
        return 0.0, 100.0
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return round(100 * (centre - half), 1), round(100 * (centre + half), 1)


def seller_flags(seller_on_time, target=ON_TIME_TARGET):
    """Which sellers are below the on-time target for sure, and which only look low by chance.

    A seller is flagged only when even the top of its 95% interval is under the target.
    """
    out = seller_on_time[["seller_id", "category", "region", "delivered_orders", "on_time_pct"]].copy()
    bounds = [wilson(round(r.on_time_pct * r.delivered_orders / 100), r.delivered_orders)
              for r in out.itertuples()]
    out["ci_low_pct"] = [b[0] for b in bounds]
    out["ci_high_pct"] = [b[1] for b in bounds]
    out["status"] = [
        "below target" if hi < target else "meets target" if lo >= target else "too close to call"
        for lo, hi in bounds
    ]
    return out


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

    d = r["cancellation_drilldown"]
    d = d[d["dimension"] == "category"]
    x = range(len(d))
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar([i - 0.2 for i in x], d["other_cancel_pct"], width=0.4, color="#718096", label="Rest of the year")
    ax.bar([i + 0.2 for i in x], d["peak_cancel_pct"], width=0.4, color="#c53030", label=d["peak_month"].iloc[0])
    ax.set_xticks(list(x), d["value"], rotation=30)
    ax.set_title("Cancellation rate by category: the spike month vs the rest (%)")
    ax.legend()
    fig.tight_layout(); fig.savefig(outdir / "cancellation_drilldown.png", dpi=130); plt.close(fig)

    h = r["cohort_retention"].pivot(index="cohort", columns="months_after", values="retention_pct")
    sizes = r["cohort_retention"].drop_duplicates("cohort").set_index("cohort")["cohort_buyers"]
    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(h.values, cmap="Blues", vmin=0, vmax=100, aspect="auto")
    ax.set_xticks(range(len(h.columns)), [f"+{c} mo" for c in h.columns])
    ax.set_yticks(range(len(h.index)), [f"{c} ({sizes[c]})" for c in h.index])
    for (i, j), v in np.ndenumerate(h.values):
        if not np.isnan(v):
            ax.text(j, i, f"{v:.0f}%", ha="center", va="center", color="white" if v > 55 else "black", fontsize=9)
    ax.set_title("Buyers ordering again, by first-order month")
    ax.set_ylabel("Cohort (buyers)")
    fig.colorbar(im, ax=ax, label="%")
    fig.tight_layout(); fig.savefig(outdir / "cohort_retention.png", dpi=130); plt.close(fig)

    s = r["seller_on_time"].head(10)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.barh(s["seller_id"].astype(str), s["on_time_pct"], color="#dd6b20")
    ax.set_title("Lowest on-time delivery rate by seller (%)")
    ax.set_ylabel("Seller ID")
    ax.invert_yaxis()
    fig.tight_layout(); fig.savefig(outdir / "seller_on_time.png", dpi=130); plt.close(fig)


def findings(r):
    m, c, s = r["monthly_kpis"], r["cancellation_rate_by_month"], r["seller_on_time"]
    d = r["cancellation_drilldown"]
    f = r["seller_flags"]
    target = ON_TIME_TARGET
    worst_flag = f.iloc[0]
    flagged = int((f["status"] == "below target").sum())
    close = int((f["status"] == "too close to call").sum())
    rv = r["repeat_vs_one_time"].set_index("segment")
    worst = s.iloc[0]
    peak = c.loc[c["cancel_rate_pct"].idxmax()]
    typical = c.loc[c["month"] != peak["month"], "cancel_rate_pct"].median()
    rep, one = rv.loc["repeat"], rv.loc["one-time"]
    cr = r["cohort_retention"]
    m1 = cr[(cr.months_after == 1) & (cr.cohort_buyers >= MIN_COHORT)]
    ret1 = 100 * m1.active_buyers.sum() / m1.cohort_buyers.sum()
    ret1_lo, ret1_hi = m1.retention_pct.min(), m1.retention_pct.max()
    aug1 = m1.set_index("cohort").loc["2025-08", "retention_pct"]
    jul1 = m1.set_index("cohort").loc["2025-07", "retention_pct"]
    share = 100 * rep["total_spend"] / (rep["total_spend"] + one["total_spend"])
    best_month = m.loc[m["gmv"].idxmax()]
    cat = r["category_performance"].iloc[0]
    return f"""# Findings

These findings come from **synthetic** data with a few patterns built in on purpose.
They show the method, not real business results.

## 1. Cancellations spiked in {peak['month']}
The cancellation rate hit **{peak['cancel_rate_pct']}%** in {peak['month']}, against a typical
month of about **{typical}%**.

**It was not one region or one category.** In {peak['month']} the rate rose in every buyer region,
every seller region, and every category, to between **{d['peak_cancel_pct'].min()}%** and
**{d['peak_cancel_pct'].max()}%**, while each of them stayed between {d['other_cancel_pct'].min()}% and
{d['other_cancel_pct'].max()}% the rest of the year (see `cancellation_drilldown.csv`). The smallest
groups swing the most, because a few orders move their rate a lot.
When everything moves together, the cause is usually marketplace-wide: a checkout or payment
problem, a policy or pricing change, or a stock-out across many sellers. That is where I would look next.

## 2. One seller is reliably late, and the next few are not
Seller **{int(worst['seller_id'])}** ({worst['category']}, {worst['region']}) delivers on time
only **{worst['on_time_pct']}%** of the time across {int(worst['delivered_orders'])} orders. Even the top of its
95% confidence interval ({worst_flag['ci_low_pct']}% to {worst_flag['ci_high_pct']}%) is under the {target:g}% target, so this is
not bad luck.

The next lowest sellers ({f.iloc[1]['on_time_pct']}% to {f.iloc[min(3, len(f) - 1)]['on_time_pct']}% on time) look worrying in a ranked
list, but they are not clearly below target: {close} sellers are **too close to call**, because their
intervals still include {target:g}%. Their low rank may just be chance, and chasing them would mean
chasing noise. Only {flagged} of {len(f)} sellers is reliably below target (`seller_flags.csv`).
Recommendation: review seller {int(worst['seller_id'])}'s promised delivery windows, flag its late orders
before the buyer has to ask, and recheck the "too close to call" sellers once they have more orders.

## 3. Repeat buyers carry the revenue
Repeat buyers are {int(rep['buyers'])} of {int(rep['buyers'] + one['buyers'])} buyers but account for
**{share:.0f}%** of spend (average ${rep['avg_spend']:,.0f} against ${one['avg_spend']:,.0f} for one-time buyers).
Recommendation: put effort into getting a second order from new buyers.

## 4. Most new buyers do not come back the next month
Across cohorts of at least {MIN_COHORT} buyers, **{ret1:.0f}%** of new buyers placed another order the
month after their first one (cohort range {ret1_lo}% to {ret1_hi}%, see `cohort_retention.csv`).
The August cohort, which started during the cancellation spike, came back at **{aug1}%**. That is
below average, but July's cohort ({jul1}%) was lower without any spike, so this data cannot show that the
spike drove new buyers away. Together with finding 3, the biggest lever is the second order.

## 5. Revenue overview
Best month for GMV was **{best_month['month']}** (${best_month['gmv']:,.0f}). The top category by GMV
was **{cat['category']}** (${cat['gmv']:,.0f}).

## Assumptions
- GMV and AOV exclude cancelled orders.
- On-time means delivered within the promised number of days.
- A repeat buyer has two or more non-cancelled orders.
"""


def load_csvs(data_dir=ROOT / "data"):
    return [pd.read_csv(Path(data_dir) / f"{t}.csv") for t in ("sellers", "buyers", "orders")]


def main(out=ROOT / "reports"):
    problems = check(*load_csvs())
    if problems:
        raise SystemExit("Data checks failed, so no reports were written:\n- " + "\n- ".join(problems))
    print("Data checks passed.")
    con = build_db()
    r = run_all(con)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for k, v in r.items():
        v.to_csv(out / f"{k}.csv", index=False)
    charts(r, out / "charts")
    (out / "FINDINGS.md").write_text(findings(r))
    print("wrote reports/")


if __name__ == "__main__":
    main()
