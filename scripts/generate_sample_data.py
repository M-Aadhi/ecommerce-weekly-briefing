"""Generate the fake sample CSVs in data/ (no real customer data).

Two full weeks (Mon 2026-09-28 to Sun 2026-10-11). The second week is built to
show typical problems: fewer orders, higher refunds, and Meta spend rising while
its attributed revenue falls. Re-running with the same seed gives identical files.

    python scripts/generate_sample_data.py
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ORDER_SEED = 42
AD_SEED = 7
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
PREV_START = date(2026, 9, 28)
CUR_START = date(2026, 10, 5)

# Per-week settings: daily order counts, avg basket, discount share, refund probability
WEEKS = {
    PREV_START: {"daily_orders": [44, 46, 47, 49, 53, 52, 48], "basket": 86.0, "discount_rate": 0.06, "refund_p": 0.04},
    CUR_START: {"daily_orders": [41, 42, 43, 45, 47, 45, 41], "basket": 84.0, "discount_rate": 0.08, "refund_p": 0.075},
}

# Per-week, per-campaign daily spend and efficiency
CAMPAIGNS = {
    "Meta": ["Prospecting - Broad", "Retargeting - Cart Abandoners"],
    "Google Ads": ["Search - Brand", "Shopping - All Products"],
}
AD_PLAN = {
    PREV_START: {
        "Meta": {"spend": (190, 120), "cpc": (1.05, 0.80), "cvr": (0.026, 0.055), "value": (82.0, 88.0)},
        "Google Ads": {"spend": (60, 170), "cpc": (0.55, 0.95), "cvr": (0.080, 0.032), "value": (90.0, 85.0)},
    },
    CUR_START: {
        "Meta": {"spend": (245, 130), "cpc": (1.35, 0.88), "cvr": (0.016, 0.044), "value": (80.0, 86.0)},
        "Google Ads": {"spend": (61, 172), "cpc": (0.56, 0.97), "cvr": (0.078, 0.031), "value": (89.0, 84.0)},
    },
}


def make_orders(rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    order_no = 10001
    customers = [f"CUST-{n:05d}" for n in range(1, 701)]
    for week_start, plan in WEEKS.items():
        for day_offset, n_orders in enumerate(plan["daily_orders"]):
            day = week_start + timedelta(days=day_offset)
            for _ in range(n_orders):
                gross = round(float(np.clip(rng.lognormal(np.log(plan["basket"]), 0.45), 12, 480)), 2)
                discount = round(gross * plan["discount_rate"] * rng.uniform(0, 2), 2) if rng.random() < 0.45 else 0.0
                refund = round((gross - discount) * rng.choice([0.5, 1.0]), 2) if rng.random() < plan["refund_p"] else 0.0
                rows.append({
                    "order_id": f"#{order_no}",
                    "order_date": day.isoformat(),
                    "customer_id": rng.choice(customers),
                    "gross_sales": gross,
                    "discount": discount,
                    "refund": refund,
                    "net_sales": round(gross - discount - refund, 2),
                    "orders": 1,
                })
                order_no += 1
    return pd.DataFrame(rows)


def make_ads(rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    for week_start, platforms in AD_PLAN.items():
        for day_offset in range(7):
            day = week_start + timedelta(days=day_offset)
            for platform, plan in platforms.items():
                for i, campaign in enumerate(CAMPAIGNS[platform]):
                    spend = round(plan["spend"][i] * rng.uniform(0.9, 1.1), 2)
                    clicks = max(1, int(spend / (plan["cpc"][i] * rng.uniform(0.92, 1.08))))
                    impressions = int(clicks / rng.uniform(0.009, 0.016))
                    conversions = int(rng.binomial(clicks, plan["cvr"][i]))
                    revenue = round(conversions * plan["value"][i] * rng.uniform(0.9, 1.1), 2)
                    rows.append({
                        "date": day.isoformat(),
                        "platform": platform,
                        "campaign": campaign,
                        "spend": spend,
                        "impressions": impressions,
                        "clicks": clicks,
                        "conversions": conversions,
                        "attributed_revenue": revenue,
                    })
    return pd.DataFrame(rows)


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    orders = make_orders(np.random.default_rng(ORDER_SEED))
    ads = make_ads(np.random.default_rng(AD_SEED))
    orders.to_csv(DATA_DIR / "shopify_orders.csv", index=False)
    ads.to_csv(DATA_DIR / "ad_performance.csv", index=False)
    print(f"wrote {len(orders)} orders and {len(ads)} ad rows to {DATA_DIR}")


if __name__ == "__main__":
    main()
