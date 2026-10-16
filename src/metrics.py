"""Weekly KPI calculations and week-over-week comparison."""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

import pandas as pd

log = logging.getLogger(__name__)

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def safe_divide(numerator: float, denominator: float) -> Optional[float]:
    """numerator / denominator, or None when the denominator is zero or missing."""
    if denominator is None or numerator is None:
        return None
    if isinstance(denominator, float) and math.isnan(denominator):
        return None
    if denominator == 0:
        return None
    return numerator / denominator


def pct_change(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    """Percentage change from previous to current (e.g. -8.4), or None if not computable."""
    if current is None or previous is None or previous == 0:
        return None
    return (current - previous) / abs(previous) * 100


@dataclass
class Period:
    start: date
    end: date

    def contains(self, dates: pd.Series) -> pd.Series:
        return (dates >= pd.Timestamp(self.start)) & (dates <= pd.Timestamp(self.end))


def resolve_weeks(latest: date, week_start: str = "monday", week_end: Optional[date] = None) -> tuple[Period, Period]:
    """Return (current, previous) 7-day periods.

    With week_end given, the current week is the 7 days ending on it. Otherwise it is
    the week (starting on `week_start`) that contains the latest date in the data.
    """
    if week_end is None:
        start_index = WEEKDAYS.index(week_start.lower())
        offset = (latest.weekday() - start_index) % 7
        cur_start = latest - timedelta(days=offset)
    else:
        cur_start = week_end - timedelta(days=6)
    current = Period(cur_start, cur_start + timedelta(days=6))
    previous = Period(cur_start - timedelta(days=7), cur_start - timedelta(days=1))
    return current, previous


def order_kpis(orders: pd.DataFrame) -> dict[str, Optional[float]]:
    revenue = float(orders["net_sales"].sum())
    count = float(orders["orders"].sum())
    return {
        "revenue": revenue,
        "gross_sales": float(orders["gross_sales"].sum()),
        "orders": count,
        "aov": safe_divide(revenue, count),
        "refunds": float(orders["refund"].sum()),
        "discounts": float(orders["discount"].sum()),
    }


def ad_kpis(ads: pd.DataFrame) -> dict[str, Optional[float]]:
    spend = float(ads["spend"].sum())
    attributed = float(ads["attributed_revenue"].sum())
    clicks = float(ads["clicks"].sum())
    conversions = float(ads["conversions"].sum())
    impressions = float(ads["impressions"].sum())
    return {
        "ad_spend": spend,
        "attributed_revenue": attributed,
        "roas": safe_divide(attributed, spend),
        "impressions": impressions,
        "clicks": clicks,
        "conversions": conversions,
        "cost_per_conversion": safe_divide(spend, conversions),
        "conversion_rate": safe_divide(conversions * 100, clicks),
    }


@dataclass
class WeeklyReport:
    current_period: Period
    previous_period: Period
    current: dict[str, Optional[float]]
    previous: dict[str, Optional[float]]
    changes: dict[str, Optional[float]]
    platforms: dict[str, dict[str, dict[str, Optional[float]]]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def _kpis_for(orders: pd.DataFrame, ads: pd.DataFrame, period: Period) -> dict[str, Optional[float]]:
    week_orders = orders[period.contains(orders["order_date"])]
    week_ads = ads[period.contains(ads["date"])]
    return {**order_kpis(week_orders), **ad_kpis(week_ads)}


def build_report(orders: pd.DataFrame, ads: pd.DataFrame, week_start: str = "monday",
                 week_end: Optional[date] = None) -> WeeklyReport:
    latest = max(orders["order_date"].max(), ads["date"].max()).date()
    current_period, previous_period = resolve_weeks(latest, week_start, week_end)
    log.info("Current week %s to %s, previous week %s to %s", current_period.start, current_period.end,
             previous_period.start, previous_period.end)

    current = _kpis_for(orders, ads, current_period)
    previous = _kpis_for(orders, ads, previous_period)
    changes = {key: pct_change(current[key], previous[key]) for key in current}

    warnings = []
    for label, period, kpis in (("current", current_period, current), ("previous", previous_period, previous)):
        if kpis["orders"] == 0:
            warnings.append(f"No orders found for the {label} week ({period.start} to {period.end}).")
        if kpis["ad_spend"] == 0:
            warnings.append(f"No advertising data found for the {label} week ({period.start} to {period.end}).")
    for days_label, df, col in (("orders", orders, "order_date"), ("ad", ads, "date")):
        days = df.loc[current_period.contains(df[col]), col].nunique()
        if 0 < days < 7:
            warnings.append(f"Current week has {days}/7 days of {days_label} data; comparisons may be skewed.")
    for warning in warnings:
        log.warning(warning)

    platforms: dict[str, dict[str, dict[str, Optional[float]]]] = {}
    for platform in sorted(ads["platform"].unique()):
        rows = ads[ads["platform"] == platform]
        cur = ad_kpis(rows[current_period.contains(rows["date"])])
        prev = ad_kpis(rows[previous_period.contains(rows["date"])])
        platforms[platform] = {
            "current": cur,
            "previous": prev,
            "changes": {key: pct_change(cur[key], prev[key]) for key in cur},
        }

    return WeeklyReport(current_period, previous_period, current, previous, changes, platforms, warnings)
