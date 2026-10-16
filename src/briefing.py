"""Turn the weekly report and detected issues into a management briefing."""
from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Optional

from .anomaly_detection import Issue
from .metrics import Period, WeeklyReport


def format_period(period: Period) -> str:
    start, end = period.start, period.end
    if start.year != end.year:
        return f"{start:%B} {start.day}, {start.year} – {end:%B} {end.day}, {end.year}"
    if start.month != end.month:
        return f"{start:%B} {start.day} – {end:%B} {end.day}, {end.year}"
    return f"{start:%B} {start.day}–{end.day}, {end.year}"


def money(value: Optional[float], symbol: str = "$", decimals: int = 0) -> str:
    if value is None:
        return "n/a"
    return f"{symbol}{value:,.{decimals}f}"


def change_phrase(change: Optional[float]) -> str:
    if change is None:
        return "no prior-week comparison"
    if abs(change) < 0.05:
        return "flat vs. last week"
    return f"{'up' if change > 0 else 'down'} {abs(change):.1f}% vs. last week"


def _ratio(value: Optional[float]) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def _pct_cell(change: Optional[float]) -> str:
    return "n/a" if change is None else f"{change:+.1f}%"


def render_briefing(report: WeeklyReport, issues: list[Issue], currency: str = "$",
                    min_roas: Optional[float] = None, generated_at: Optional[datetime] = None) -> str:
    cur, prev, chg = report.current, report.previous, report.changes
    generated_at = generated_at or datetime.now(timezone.utc)

    roas_line = f"**ROAS:** {_ratio(cur['roas'])}"
    if prev["roas"] is not None:
        roas_line += f", {'up' if (cur['roas'] or 0) > prev['roas'] else 'down'} from {prev['roas']:.2f}"
    if min_roas is not None:
        roas_line += f" (target {min_roas:.1f})"

    lines = [
        "# Weekly Ecommerce Briefing",
        "",
        f"**Period:** {format_period(report.current_period)} "
        f"(compared with {format_period(report.previous_period)})",
        "",
        "## Performance",
        "",
        f"- **Revenue:** {money(cur['revenue'], currency)}, {change_phrase(chg['revenue'])}",
        f"- **Orders:** {cur['orders']:,.0f}, {change_phrase(chg['orders'])}",
        f"- **Average Order Value:** {money(cur['aov'], currency, 2)}, {change_phrase(chg['aov'])}",
        f"- **Refunds:** {money(cur['refunds'], currency)}, {change_phrase(chg['refunds'])}",
        f"- **Discounts:** {money(cur['discounts'], currency)}, {change_phrase(chg['discounts'])}",
        "",
        f"- **Ad Spend:** {money(cur['ad_spend'], currency)}, {change_phrase(chg['ad_spend'])}",
        f"- **Attributed Revenue:** {money(cur['attributed_revenue'], currency)}, "
        f"{change_phrase(chg['attributed_revenue'])}",
        f"- {roas_line}",
        f"- **Clicks:** {cur['clicks']:,.0f} · **Conversions:** {cur['conversions']:,.0f} · "
        f"**Cost per Conversion:** {money(cur['cost_per_conversion'], currency, 2)} "
        f"({change_phrase(chg['cost_per_conversion'])})",
        "",
    ]

    if report.platforms:
        lines += ["## Advertising by Platform", ""]
        for platform, data in report.platforms.items():
            p, pc = data["current"], data["changes"]
            lines.append(
                f"- **{platform}:** spend {money(p['ad_spend'], currency)} ({_pct_cell(pc['ad_spend'])}), "
                f"attributed revenue {money(p['attributed_revenue'], currency)} "
                f"({_pct_cell(pc['attributed_revenue'])}), ROAS {_ratio(p['roas'])}")
        lines.append("")

    lines += ["## Issues Detected", ""]
    if issues:
        lines += [f"- {'🔴' if i.severity == 'high' else '🟠'} {i.message}" for i in issues]
    else:
        lines.append("- ✅ No issues detected. All KPIs are within the configured thresholds.")
    lines.append("")

    suggestions = list(dict.fromkeys(i.suggestion for i in issues))
    lines += ["## Suggested Review", ""]
    lines += [f"- {s}" for s in suggestions] or ["- No action needed this week. Keep monitoring."]
    lines.append("")

    if report.warnings:
        lines += ["## Data Notes", ""] + [f"- ⚠️ {w}" for w in report.warnings] + [""]

    lines += [
        "## KPI Table",
        "",
        "| KPI | This week | Last week | Change |",
        "|---|---:|---:|---:|",
    ]
    table = [
        ("Revenue (net sales)", "revenue", lambda v: money(v, currency)),
        ("Orders", "orders", lambda v: f"{v:,.0f}"),
        ("Average order value", "aov", lambda v: money(v, currency, 2)),
        ("Refunds", "refunds", lambda v: money(v, currency)),
        ("Discounts", "discounts", lambda v: money(v, currency)),
        ("Ad spend", "ad_spend", lambda v: money(v, currency)),
        ("Attributed revenue", "attributed_revenue", lambda v: money(v, currency)),
        ("ROAS", "roas", _ratio),
        ("Clicks", "clicks", lambda v: f"{v:,.0f}"),
        ("Conversions", "conversions", lambda v: f"{v:,.0f}"),
        ("Conversion rate", "conversion_rate", lambda v: "n/a" if v is None else f"{v:.2f}%"),
        ("Cost per conversion", "cost_per_conversion", lambda v: money(v, currency, 2)),
    ]
    for label, key, fmt in table:
        lines.append(f"| {label} | {fmt(cur[key])} | {fmt(prev[key])} | {_pct_cell(chg[key])} |")

    lines += [
        "",
        f"_Generated automatically on {generated_at:%Y-%m-%d %H:%M} UTC. Revenue = net sales "
        f"(gross − discounts − refunds). ROAS = ad-attributed revenue ÷ ad spend. "
        f"Thresholds are set in config.yaml._",
        "",
    ]
    return "\n".join(lines)


def to_slack_mrkdwn(markdown: str) -> str:
    """Convert the Markdown briefing to Slack mrkdwn (bold, headings; drop the table)."""
    text = markdown.split("\n## KPI Table", 1)[0].rstrip() + "\n"
    text = re.sub(r"^#{1,6} (.+)$", r"*\1*", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)
    text = re.sub(r"^- ", "• ", text, flags=re.MULTILINE)
    return text


def output_filename(period_end: date) -> str:
    return f"weekly_briefing_{period_end.isoformat()}.md"
