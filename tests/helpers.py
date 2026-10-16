"""Small hand-made datasets with easy numbers for testing."""
import pandas as pd


def orders_frame(rows):
    """rows: list of (date, gross, discount, refund)."""
    return pd.DataFrame([
        {"order_id": f"#{i}", "order_date": pd.Timestamp(d), "customer_id": f"C{i}",
         "gross_sales": g, "discount": disc, "refund": ref, "net_sales": g - disc - ref, "orders": 1}
        for i, (d, g, disc, ref) in enumerate(rows)
    ])


def ads_frame(rows):
    """rows: list of (date, platform, spend, clicks, conversions, revenue)."""
    return pd.DataFrame([
        {"date": pd.Timestamp(d), "platform": p, "campaign": "c", "spend": s, "impressions": c * 50,
         "clicks": c, "conversions": conv, "attributed_revenue": r}
        for d, p, s, c, conv, r in rows
    ])
