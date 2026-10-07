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
