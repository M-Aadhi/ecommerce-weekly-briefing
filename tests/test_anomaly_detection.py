from src.anomaly_detection import detect_issues
from src.metrics import build_report
from tests.helpers import ads_frame, orders_frame


def rules(issues):
    return {i.rule for i in issues}


def make_report(prev_orders, cur_orders, prev_ads, cur_ads):
    orders = orders_frame([("2026-09-29", *o) for o in prev_orders] + [("2026-10-06", *o) for o in cur_orders])
    ads = ads_frame([("2026-09-29", *a) for a in prev_ads] + [("2026-10-06", *a) for a in cur_ads])
    return build_report(orders, ads)


def test_no_issues_when_stable():
    report = make_report([(100, 0, 0)] * 10, [(100, 0, 0)] * 10,
                         [("Meta", 100, 100, 5, 500)], [("Meta", 100, 100, 5, 500)])
    assert detect_issues(report) == []


def test_flags_revenue_orders_spend_roas_and_platform():
    report = make_report([(100, 0, 0)] * 10, [(100, 0, 0)] * 8,
                         [("Meta", 100, 100, 5, 500)], [("Meta", 130, 100, 4, 390)])
    found = rules(detect_issues(report))
    assert {"revenue_drop", "orders_drop", "spend_up_revenue_down",
            "platform_spend_up_revenue_down", "roas_below_target"} <= found


def test_flags_refunds_discounts_and_conversion_decline():
    report = make_report([(100, 5, 10)] * 10, [(100, 8, 20)] * 10,
                         [("Meta", 100, 100, 10, 1000)], [("Meta", 100, 100, 6, 1000)])
    found = rules(detect_issues(report))
    assert {"refund_increase", "discount_increase", "conversion_decline"} <= found


def test_thresholds_are_configurable():
    report = make_report([(100, 0, 0)] * 10, [(100, 0, 0)] * 9,
                         [("Meta", 100, 100, 5, 500)], [("Meta", 100, 100, 5, 500)])
    assert "revenue_drop" not in rules(detect_issues(report))
    assert "revenue_drop" in rules(detect_issues(report, {"revenue_drop_pct": 5}))
    assert "roas_below_target" in rules(detect_issues(report, {"min_roas": 6}))


def test_missing_previous_week_does_not_crash():
    orders = orders_frame([("2026-10-06", 100, 0, 0)])
    ads = ads_frame([("2026-10-06", "Meta", 0, 0, 0, 0)])
    assert detect_issues(build_report(orders, ads)) == []
