from datetime import date

import pytest

from src.metrics import ad_kpis, build_report, order_kpis, pct_change, resolve_weeks, safe_divide
from tests.helpers import ads_frame, orders_frame


def test_safe_divide_handles_zero_and_none():
    assert safe_divide(10, 4) == 2.5
    assert safe_divide(10, 0) is None
    assert safe_divide(10, None) is None
    assert safe_divide(10, float("nan")) is None


def test_pct_change():
    assert pct_change(110, 100) == pytest.approx(10.0)
    assert pct_change(90, 100) == pytest.approx(-10.0)
    assert pct_change(5, 0) is None
    assert pct_change(None, 100) is None


def test_order_kpis():
    df = orders_frame([("2026-10-05", 100, 10, 0), ("2026-10-06", 60, 0, 20)])
    k = order_kpis(df)
    assert k["revenue"] == 130          # (100-10) + (60-20)
    assert k["orders"] == 2
    assert k["aov"] == 65
    assert k["refunds"] == 20
    assert k["discounts"] == 10


def test_order_kpis_empty_week_has_no_aov():
    df = orders_frame([("2026-10-05", 100, 0, 0)]).iloc[0:0]
    k = order_kpis(df)
    assert k["revenue"] == 0 and k["orders"] == 0 and k["aov"] is None


def test_ad_kpis():
    df = ads_frame([("2026-10-05", "Meta", 100, 200, 4, 400), ("2026-10-05", "Google Ads", 50, 100, 1, 50)])
    k = ad_kpis(df)
    assert k["ad_spend"] == 150
    assert k["attributed_revenue"] == 450
    assert k["roas"] == 3.0
    assert k["cost_per_conversion"] == 30
    assert k["conversion_rate"] == pytest.approx(5 / 300 * 100)


def test_ad_kpis_zero_spend_and_conversions():
    k = ad_kpis(ads_frame([("2026-10-05", "Meta", 0, 0, 0, 0)]))
    assert k["roas"] is None
    assert k["cost_per_conversion"] is None
    assert k["conversion_rate"] is None


def test_resolve_weeks_from_latest_date():
    cur, prev = resolve_weeks(date(2026, 10, 9))  # a Friday
    assert (cur.start, cur.end) == (date(2026, 10, 5), date(2026, 10, 11))
    assert (prev.start, prev.end) == (date(2026, 9, 28), date(2026, 10, 4))


def test_resolve_weeks_with_explicit_end_and_sunday_start():
    cur, _ = resolve_weeks(date(2026, 10, 9), week_end=date(2026, 10, 4))
    assert (cur.start, cur.end) == (date(2026, 9, 28), date(2026, 10, 4))
    cur, _ = resolve_weeks(date(2026, 10, 9), week_start="sunday")
    assert cur.start == date(2026, 10, 4)


def test_build_report_week_over_week():
    orders = orders_frame([("2026-09-29", 100, 0, 0), ("2026-09-30", 100, 0, 0),
                           ("2026-10-06", 90, 0, 0)])
    ads = ads_frame([("2026-09-29", "Meta", 50, 100, 2, 200), ("2026-10-06", "Meta", 60, 100, 1, 120)])
    report = build_report(orders, ads)
    assert report.current["revenue"] == 90 and report.previous["revenue"] == 200
    assert report.changes["revenue"] == pytest.approx(-55.0)
    assert report.changes["orders"] == pytest.approx(-50.0)
    assert report.current["roas"] == 2.0 and report.previous["roas"] == 4.0
    assert report.platforms["Meta"]["changes"]["ad_spend"] == pytest.approx(20.0)


def test_build_report_warns_when_previous_week_missing():
    orders = orders_frame([("2026-10-06", 90, 0, 0)])
    ads = ads_frame([("2026-10-06", "Meta", 60, 100, 1, 120)])
    report = build_report(orders, ads)
    assert report.changes["revenue"] is None
    assert any("previous week" in w for w in report.warnings)
