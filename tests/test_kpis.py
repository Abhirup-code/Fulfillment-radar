import pandas as pd

from src.analyze import build_db, run_all
from src.generate_data import generate


def test_data_is_deterministic():
    a = generate(seed=1, n_orders=300)[2]
    b = generate(seed=1, n_orders=300)[2]
    pd.testing.assert_frame_equal(a, b)


def test_no_orphan_foreign_keys():
    con = build_db()
    orphans = con.execute("""SELECT COUNT(*) FROM orders o
        LEFT JOIN buyers b USING (buyer_id) LEFT JOIN sellers s USING (seller_id)
        WHERE b.buyer_id IS NULL OR s.seller_id IS NULL""").fetchone()[0]
    assert orphans == 0


def test_order_ids_unique_and_amounts_positive():
    o = pd.read_csv("data/orders.csv")
    assert o.order_id.is_unique and (o.amount > 0).all()


def test_gmv_reconciles_with_raw_data():
    con = build_db()
    r = run_all(con)
    raw = pd.read_csv("data/orders.csv")
    expected = round(raw.loc[raw.status != "cancelled", "amount"].sum(), 2)
    assert round(r["monthly_kpis"]["gmv"].sum(), 2) == expected


def test_cancellation_spike_is_detected():
    r = run_all(build_db())
    c = r["cancellation_rate_by_month"].set_index("month")["cancel_rate_pct"]
    assert c.idxmax() == "2025-08"


def test_late_seller_is_lowest_on_time():
    r = run_all(build_db())
    assert int(r["seller_on_time"].iloc[0]["seller_id"]) == 7


def test_repeat_buyers_spend_more():
    r = run_all(build_db()).get("repeat_vs_one_time").set_index("segment")
    assert r.loc["repeat", "avg_spend"] > r.loc["one-time", "avg_spend"]


def test_the_spike_drilldown_finds_it_everywhere_not_in_one_group():
    d = run_all(build_db())["cancellation_drilldown"]
    assert set(d["peak_month"]) == {"2025-08"}
    assert set(d["dimension"]) == {"buyer region", "seller region", "category"}
    # The planted spike is marketplace-wide, so every group at least doubles.
    assert (d["peak_cancel_pct"] > 2 * d["other_cancel_pct"]).all(), d


def test_the_drilldown_covers_every_order_once_per_dimension():
    con = build_db()
    d = run_all(con)["cancellation_drilldown"]
    peak_orders = con.execute("SELECT COUNT(*) FROM orders WHERE order_date LIKE '2025-08%'").fetchone()[0]
    assert (d.groupby("dimension")["peak_orders"].sum() == peak_orders).all()


def test_wilson_interval_matches_known_values():
    from src.analyze import wilson

    assert wilson(50, 100) == (40.4, 59.6)
    assert wilson(0, 0) == (0.0, 100.0)
    lo, hi = wilson(10, 10)
    assert hi == 100.0 and lo < 100


def test_only_the_planted_late_seller_is_flagged():
    f = run_all(build_db())["seller_flags"]
    assert f.loc[f.status == "below target", "seller_id"].tolist() == [7]
    # The next lowest seller looks low but its interval still reaches the target.
    assert f.iloc[1]["status"] == "too close to call"
    assert (f.ci_low_pct <= f.on_time_pct).all() and (f.on_time_pct <= f.ci_high_pct).all()


def test_the_report_builds_end_to_end(tmp_path):
    from src.analyze import main

    out = tmp_path / "reports"
    main(out)
    text = (out / "FINDINGS.md").read_text()
    assert "Seller **7**" in text and "too close to call" in text
    assert (out / "seller_flags.csv").exists()
    assert len(list((out / "charts").glob("*.png"))) == 7


def test_every_buyer_with_an_order_is_in_exactly_one_cohort():
    con = build_db()
    cr = run_all(con)["cohort_retention"]
    buyers = con.execute(
        "SELECT COUNT(DISTINCT buyer_id) FROM orders WHERE status != 'cancelled'"
    ).fetchone()[0]
    sizes = cr.drop_duplicates("cohort")["cohort_buyers"].sum()
    # Buyers whose first order is in the final month have no later month to measure, so no row.
    last = con.execute("""SELECT COUNT(*) FROM (SELECT buyer_id, MIN(substr(order_date,1,7)) AS c
        FROM orders WHERE status != 'cancelled' GROUP BY buyer_id) WHERE c = '2025-12'""").fetchone()[0]
    assert sizes + last == buyers
    assert cr.retention_pct.between(0, 100).all()


def test_month_one_retention_matches_a_pandas_recount():
    cr = run_all(build_db())["cohort_retention"].set_index(["cohort", "months_after"])
    o = pd.read_csv("data/orders.csv")
    o = o[o.status != "cancelled"].assign(month=lambda d: pd.PeriodIndex(d.order_date, freq="M"))
    first = o.groupby("buyer_id").month.min()
    sept = first[first == pd.Period("2025-09", "M")].index
    came_back = o[o.buyer_id.isin(sept) & (o.month == pd.Period("2025-10", "M"))].buyer_id.nunique()
    assert cr.loc[("2025-09", 1), "active_buyers"] == came_back
    assert cr.loc[("2025-09", 1), "cohort_buyers"] == len(sept)
