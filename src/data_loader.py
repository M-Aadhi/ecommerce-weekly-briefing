"""Load and validate the order and advertising CSV exports."""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

ORDER_COLUMNS = ["order_id", "order_date", "customer_id", "gross_sales", "discount", "refund", "net_sales", "orders"]
ORDER_NUMERIC = ["gross_sales", "discount", "refund", "net_sales", "orders"]

AD_COLUMNS = ["date", "platform", "campaign", "spend", "impressions", "clicks", "conversions", "attributed_revenue"]
AD_NUMERIC = ["spend", "impressions", "clicks", "conversions", "attributed_revenue"]


class DataValidationError(Exception):
    """Raised when an input file is missing, empty or malformed."""


def _load_csv(path: Path, name: str, required: list[str], date_col: str, numeric: list[str]) -> pd.DataFrame:
    path = Path(path)
    if not path.is_file():
        raise DataValidationError(f"{name} file not found: {path}")

    try:
        df = pd.read_csv(path)
    except pd.errors.EmptyDataError as exc:
        raise DataValidationError(f"{name} file is empty: {path}") from exc

    df.columns = [str(c).strip().lower() for c in df.columns]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise DataValidationError(f"{name} file {path} is missing required columns: {', '.join(missing)}")
    if df.empty:
        raise DataValidationError(f"{name} file has a header but no rows: {path}")

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    bad_dates = int(df[date_col].isna().sum())
    if bad_dates:
        log.warning("%s: dropping %d row(s) with an invalid %s", name, bad_dates, date_col)
        df = df.dropna(subset=[date_col])
    if df.empty:
        raise DataValidationError(f"{name} file has no rows with a valid {date_col}")
    df[date_col] = df[date_col].dt.normalize()

    for col in numeric:
        values = pd.to_numeric(df[col], errors="coerce")
        bad = int(values.isna().sum())
        if bad:
            log.warning("%s: %d non-numeric/blank value(s) in %s treated as 0", name, bad, col)
        df[col] = values.fillna(0.0)
        negative = int((df[col] < 0).sum())
        if negative:
            log.warning("%s: %d negative value(s) in %s", name, negative, col)

    log.info("Loaded %d %s rows from %s (%s to %s)", len(df), name, path,
             df[date_col].min().date(), df[date_col].max().date())
    return df


def load_orders(path: Path) -> pd.DataFrame:
    df = _load_csv(path, "orders", ORDER_COLUMNS, "order_date", ORDER_NUMERIC)
    expected = df["gross_sales"] - df["discount"] - df["refund"]
    mismatched = int(((df["net_sales"] - expected).abs() > 0.01).sum())
    if mismatched:
        log.warning("orders: %d row(s) where net_sales != gross_sales - discount - refund", mismatched)
    return df


def load_ads(path: Path) -> pd.DataFrame:
    df = _load_csv(path, "ad performance", AD_COLUMNS, "date", AD_NUMERIC)
    df["platform"] = df["platform"].fillna("Unknown").astype(str).str.strip()
    return df
