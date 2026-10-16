"""Simple, transparent rules that flag week-over-week problems.

Each rule compares a KPI with a threshold from config.yaml. Severity is "high"
when the change is at least twice the threshold, otherwise "medium".
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .metrics import WeeklyReport

DEFAULT_THRESHOLDS = {
    "revenue_drop_pct": 10.0,
    "orders_drop_pct": 10.0,
    "spend_increase_pct": 10.0,
    "min_roas": 3.5,
    "refund_increase_pct": 10.0,
    "discount_increase_pct": 20.0,
    "conversion_rate_drop_pct": 15.0,
    "cost_per_conversion_increase_pct": 15.0,
}


@dataclass
class Issue:
    rule: str
    severity: str
    message: str
    suggestion: str


def _severity(change: float, threshold: float) -> str:
    return "high" if threshold and abs(change) >= 2 * threshold else "medium"


def _dropped(change: Optional[float], threshold: float) -> bool:
    return change is not None and change < -threshold


def _rose(change: Optional[float], threshold: float) -> bool:
    return change is not None and change > threshold


def detect_issues(report: WeeklyReport, thresholds: Optional[dict] = None) -> list[Issue]:
    t = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    cur, prev, chg = report.current, report.previous, report.changes
    issues: list[Issue] = []

    if _dropped(chg["revenue"], t["revenue_drop_pct"]):
        issues.append(Issue(
            "revenue_drop", _severity(chg["revenue"], t["revenue_drop_pct"]),
            f"Revenue fell {abs(chg['revenue']):.1f}% week over week (threshold {t['revenue_drop_pct']:.0f}%).",
            "Check traffic, conversion rate and stock levels for top-selling products."))

    if _dropped(chg["orders"], t["orders_drop_pct"]):
        issues.append(Issue(
            "orders_drop", _severity(chg["orders"], t["orders_drop_pct"]),
            f"Orders fell {abs(chg['orders']):.1f}% ({prev['orders']:.0f} → {cur['orders']:.0f}).",
            "Review site traffic sources and checkout funnel for drop-offs."))

    if _rose(chg["ad_spend"], t["spend_increase_pct"]) and chg["revenue"] is not None and chg["revenue"] < 0:
        issues.append(Issue(
            "spend_up_revenue_down", _severity(chg["ad_spend"], t["spend_increase_pct"]),
            f"Total ad spend rose {chg['ad_spend']:.1f}% while store revenue fell {abs(chg['revenue']):.1f}%.",
            "Pause or cap the campaigns that grew spend without growing sales."))

    for platform, data in report.platforms.items():
        pchg = data["changes"]
        if _rose(pchg["ad_spend"], t["spend_increase_pct"]) and pchg["attributed_revenue"] is not None \
                and pchg["attributed_revenue"] < 0:
            issues.append(Issue(
                "platform_spend_up_revenue_down", _severity(pchg["ad_spend"], t["spend_increase_pct"]),
                f"{platform} spend rose {pchg['ad_spend']:.1f}% while its attributed revenue fell "
                f"{abs(pchg['attributed_revenue']):.1f}%.",
                f"Review {platform} campaigns responsible for the increase in spend."))

    roas = cur["roas"]
    if roas is not None and roas < t["min_roas"]:
        prev_roas = f", down from {prev['roas']:.2f}" if prev["roas"] is not None else ""
        issues.append(Issue(
            "roas_below_target", "high" if roas < t["min_roas"] * 0.75 else "medium",
            f"Overall ROAS is {roas:.2f}{prev_roas}, below the target of {t['min_roas']:.1f}.",
            "Shift budget toward the platforms and campaigns with ROAS above target."))
    for platform, data in report.platforms.items():
        p_roas = data["current"]["roas"]
        if p_roas is not None and p_roas < t["min_roas"] and (roas is None or roas >= t["min_roas"] or p_roas < roas):
            issues.append(Issue(
                "platform_roas_below_target", "medium",
                f"{platform} ROAS is {p_roas:.2f}, below the target of {t['min_roas']:.1f}.",
                f"Check {platform} audiences, creatives and bids."))

    if _rose(chg["refunds"], t["refund_increase_pct"]) and cur["refunds"] > 0:
        issues.append(Issue(
            "refund_increase", _severity(chg["refunds"], t["refund_increase_pct"]),
            f"Refund value rose {chg['refunds']:.1f}% week over week "
            f"(${prev['refunds']:,.0f} → ${cur['refunds']:,.0f}).",
            "Check which products and reasons are driving the increase in refunds."))

    if _rose(chg["discounts"], t["discount_increase_pct"]):
        issues.append(Issue(
            "discount_increase", _severity(chg["discounts"], t["discount_increase_pct"]),
            f"Discounts given rose {chg['discounts']:.1f}% while average order value changed "
            f"{chg['aov']:+.1f}%." if chg["aov"] is not None else
            f"Discounts given rose {chg['discounts']:.1f}%.",
            "Verify whether current promotions are lowering average order value and margin."))

    cr_drop = _dropped(chg["conversion_rate"], t["conversion_rate_drop_pct"])
    cpa_rise = _rose(chg["cost_per_conversion"], t["cost_per_conversion_increase_pct"])
    if cr_drop or cpa_rise:
        parts = []
        if chg["conversion_rate"] is not None:
            parts.append(f"ad conversion rate {chg['conversion_rate']:+.1f}%")
        if chg["cost_per_conversion"] is not None:
            parts.append(f"cost per conversion {chg['cost_per_conversion']:+.1f}%")
        worst = max(abs(chg["conversion_rate"] or 0) / t["conversion_rate_drop_pct"],
                    abs(chg["cost_per_conversion"] or 0) / t["cost_per_conversion_increase_pct"])
        issues.append(Issue(
            "conversion_decline", "high" if worst >= 2 else "medium",
            "Conversion performance declined: " + ", ".join(parts) + ".",
            "Review landing pages, offers and ad-to-site relevance for the weakest campaigns."))

    order = {"high": 0, "medium": 1}
    return sorted(issues, key=lambda issue: order.get(issue.severity, 2))
