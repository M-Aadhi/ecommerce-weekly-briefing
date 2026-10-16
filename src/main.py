"""Weekly ecommerce briefing: load data, compute KPIs, flag issues, write and send the briefing.

    python -m src.main [--config config.yaml] [--week-end 2026-10-11] [--no-slack]
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date
from pathlib import Path
from typing import Optional

import yaml

from .anomaly_detection import DEFAULT_THRESHOLDS, detect_issues
from .briefing import output_filename, render_briefing, to_slack_mrkdwn
from .data_loader import DataValidationError, load_ads, load_orders
from .metrics import WEEKDAYS, build_report
from .slack_notifier import post_to_slack

ROOT = Path(__file__).resolve().parents[1]
log = logging.getLogger("briefing")


def load_config(path: Path) -> dict:
    if not path.is_file():
        raise DataValidationError(f"config file not found: {path}")
    with path.open(encoding="utf-8") as fh:
        config = yaml.safe_load(fh) or {}
    report = config.get("report") or {}
    week_start = str(report.get("week_start", "monday")).lower()
    if week_start not in WEEKDAYS:
        raise DataValidationError(f"report.week_start must be a weekday name, got {week_start!r}")
    return config


def _parse_date(value) -> Optional[date]:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise DataValidationError(f"invalid week_end date {value!r}; use YYYY-MM-DD") from exc


def run(config_path: Path, week_end: Optional[str] = None, send_slack: bool = True) -> Path:
    config = load_config(config_path)
    base = config_path.parent
    data_cfg = config.get("data") or {}
    report_cfg = config.get("report") or {}

    orders = load_orders(base / data_cfg.get("orders_file", "data/shopify_orders.csv"))
    ads = load_ads(base / data_cfg.get("ads_file", "data/ad_performance.csv"))

    report = build_report(orders, ads, report_cfg.get("week_start", "monday"),
                          _parse_date(week_end or report_cfg.get("week_end")))
    thresholds = {**DEFAULT_THRESHOLDS, **(config.get("thresholds") or {})}
    issues = detect_issues(report, thresholds)
    log.info("Detected %d issue(s)", len(issues))

    briefing = render_briefing(report, issues, config.get("currency_symbol", "$"), thresholds["min_roas"])
    out_dir = base / config.get("output_dir", "output")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / output_filename(report.current_period.end)
    out_path.write_text(briefing, encoding="utf-8")
    (out_dir / "latest_briefing.md").write_text(briefing, encoding="utf-8")
    log.info("Briefing saved to %s", out_path)

    if send_slack and (config.get("slack") or {}).get("enabled", True):
        post_to_slack(to_slack_mrkdwn(briefing), os.environ.get("SLACK_WEBHOOK_URL"))
    else:
        log.info("Slack delivery disabled")
    return out_path


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the weekly ecommerce briefing.")
    parser.add_argument("--config", default=str(ROOT / "config.yaml"), help="path to config.yaml")
    parser.add_argument("--week-end", help="last day of the week to report (YYYY-MM-DD)")
    parser.add_argument("--no-slack", action="store_true", help="do not post to Slack")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    try:
        path = run(Path(args.config).resolve(), args.week_end, send_slack=not args.no_slack)
    except DataValidationError as exc:
        log.error("%s", exc)
        return 1
    print(path.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
