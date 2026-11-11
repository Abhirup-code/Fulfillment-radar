import pytest

from src.analyze import load_csvs, main
from src.validate import check


def data():
    return [t.copy() for t in load_csvs()]


def test_the_generated_data_is_clean():
    assert check(*data()) == []


@pytest.mark.parametrize(
    "break_it, message",
    [
        (lambda s, b, o: o.loc.__setitem__((1, "order_id"), o.order_id[0]), "1 duplicate order ids"),
        (lambda s, b, o: o.loc.__setitem__((0, "amount"), -5.0), "1 orders with an amount that is zero"),
        (lambda s, b, o: o.loc.__setitem__((0, "quantity"), 0), "1 orders with a quantity below 1"),
        (lambda s, b, o: o.loc.__setitem__((0, "status"), "lost"), "1 orders with a status other than"),
        (lambda s, b, o: o.loc.__setitem__((0, "promised_days"), 0), "1 orders promised in under 1 day"),
        (lambda s, b, o: o.loc.__setitem__((0, "buyer_id"), 99999), "1 orders from an unknown buyer"),
        (lambda s, b, o: o.loc.__setitem__((0, "seller_id"), 99999), "1 orders from an unknown seller"),
        (
            lambda s, b, o: o.loc.__setitem__((0, "order_date"), "not a date"),
            "1 orders with a missing or unreadable",
        ),
        (
            lambda s, b, o: o.loc.__setitem__((0, "order_date"), "2020-01-01"),
            "1 orders placed before the buyer",
        ),
        (lambda s, b, o: s.loc.__setitem__((1, "seller_id"), s.seller_id[0]), "1 duplicate seller ids"),
        (lambda s, b, o: b.loc.__setitem__((1, "buyer_id"), b.buyer_id[0]), "1 duplicate buyer ids"),
    ],
)
def test_each_problem_is_caught_and_counted(break_it, message):
    s, b, o = data()
    break_it(s, b, o)
    assert any(p.startswith(message) for p in check(s, b, o)), check(s, b, o)


def test_delivery_times_must_match_the_status():
    s, b, o = data()
    cancelled = o.index[o.status == "cancelled"][0]
    delivered = o.index[o.status == "delivered"][0]
    o.loc[cancelled, "actual_days"] = 2
    o.loc[delivered, "actual_days"] = None
    problems = check(s, b, o)
    assert "1 cancelled orders with a delivery time" in problems
    assert "1 delivered or disputed orders with no delivery time" in problems


def test_missing_columns_stop_the_other_checks():
    s, b, o = data()
    assert check(s, b, o.drop(columns=["amount"])) == ["orders is missing columns: amount"]


def test_bad_data_stops_the_report(tmp_path, monkeypatch):
    s, b, o = data()
    o.loc[0, "amount"] = -1
    monkeypatch.setattr("src.analyze.load_csvs", lambda: [s, b, o])
    with pytest.raises(SystemExit, match="no reports were written"):
        main()
