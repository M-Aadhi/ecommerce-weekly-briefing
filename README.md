# Ecommerce Weekly Briefing

A small working prototype that automates the weekly ecommerce reporting job. It combines
**store sales** (Shopify-style orders) with **advertising results** (Meta and Google Ads),
calculates the weekly KPIs, compares them with last week, flags problems, and writes a short
management briefing. It can also post that briefing to **Slack**. It runs every Monday on
**GitHub Actions**, or whenever you start it by hand.

> All data in `data/` is **fake sample data** made by `scripts/generate_sample_data.py`.
> It contains no real customers.

## The business problem

Each week an ecommerce owner has to:

1. download sales from the store and results from each ad platform,
2. work out revenue, orders, average order value, ad spend and ROAS,
3. compare with last week,
4. spot what went wrong,
5. write an update for the team.

That takes an hour or more, and it's easy to miss things. This project does all five steps
automatically, in seconds, the same way every week.

## What the briefing looks like

Generated from the sample data (full file: [`examples/sample_briefing.md`](examples/sample_briefing.md)):

```
Weekly Ecommerce Briefing
Period: October 5–11, 2026 (compared with September 28 – October 4, 2026)

Performance
- Revenue: $25,464, down 12.1% vs. last week
- Orders: 304, down 10.3% vs. last week
- Average Order Value: $83.76, down 2.0% vs. last week
- Ad Spend: $4,235, up 12.4% vs. last week
- ROAS: 3.42, down from 4.37 (target 3.5)

Issues Detected
- 🔴 Meta spend rose 21.6% while its attributed revenue fell 27.0%.
- 🔴 Refund value rose 31.6% week over week ($1,154 → $1,519).
- 🟠 Overall ROAS is 3.42, down from 4.37, below the target of 3.5.
...

Suggested Review
- Review Meta campaigns responsible for the increase in spend.
- Check which products and reasons are driving the increase in refunds.
...
```

Every number is calculated from the CSV files. Nothing is hard-coded.

## How it works

```
data/shopify_orders.csv ─┐
                         ├─► validate ─► weekly KPIs ─► compare weeks ─► detect issues ─► briefing
data/ad_performance.csv ─┘                                                                ├─► output/weekly_briefing_<date>.md
                                                                                          └─► Slack (optional)
```

| Step | File | What it does |
|---|---|---|
| 1–3 Load and validate | `src/data_loader.py` | Reads both CSVs and checks that the files exist, aren't empty, and have every required column. Drops rows with invalid dates and treats blank or non-numeric values as 0, logging a warning for each. Also warns when `net_sales` doesn't equal gross − discount − refund. |
| 4–5 KPIs and comparison | `src/metrics.py` | Works out the current and previous week, then calculates the KPIs for each and the % change. Division by zero gives "n/a" instead of an error. |
| 6 Exceptions | `src/anomaly_detection.py` | Simple rules with thresholds taken from `config.yaml`. |
| 7–8 Briefing | `src/briefing.py` | Writes the Markdown briefing: summary, issues, suggested actions and a KPI table. |
| 9 Slack | `src/slack_notifier.py` | Posts the briefing if `SLACK_WEBHOOK_URL` is set. If posting fails, it logs an error and the run still finishes. |
| Orchestration | `src/main.py` | Runs the steps in order. It saves the briefing **before** trying Slack, so a Slack failure never loses the report. |
| 10 Automation | `.github/workflows/weekly_briefing.yml` | Runs every Monday, and also on demand with the **Run workflow** button. |

## KPIs

| KPI | Definition |
|---|---|
| Revenue | Sum of `net_sales` (gross − discounts − refunds) |
| Orders | Sum of `orders` |
| Average order value | Revenue ÷ orders |
| Refunds / Discounts | Sum of `refund` / `discount` |
| Ad spend | Sum of `spend` (all platforms) |
| Attributed revenue | Sum of `attributed_revenue` reported by the ad platforms |
| ROAS | Attributed revenue ÷ ad spend |
| Clicks / Conversions | Sums from the ad data |
| Conversion rate | Conversions ÷ clicks |
| Cost per conversion | Ad spend ÷ conversions |

Each KPI is shown for this week and last week, with the % change. Ad results are also split
by platform.

**Which week is reported:** by default, the Monday-to-Sunday week that contains the latest
date in the data, compared with the 7 days before it. You can change the first day of the
week (`report.week_start`), report a specific week (`report.week_end` or `--week-end`), or pick
a week when starting a manual run on GitHub.

## Exception rules (`config.yaml`)

| Rule | Flags when | Default |
|---|---|---|
| Revenue drop | Revenue falls more than X% | 10% |
| Orders drop | Orders fall more than X% | 10% |
| Spend up, revenue down | Total ad spend rises more than X% while revenue falls. Also checked per platform, using that platform's attributed revenue. | 10% |
| ROAS below target | Overall or per-platform ROAS is under the target | 3.5 |
| Refund increase | Refund value rises more than X% | 10% |
| Discount increase | Discounts rise more than X% | 20% |
| Conversion decline | Conversion rate falls more than X%, **or** cost per conversion rises more than Y% | 15% / 15% |

🔴 means the change is at least twice the threshold (or ROAS is below 75% of the target).
🟠 means it crossed the threshold. Change the numbers in `config.yaml`; no code change is needed.

## Run it locally

```bash
pip install -r requirements.txt
python -m src.main
```

This prints the briefing and saves it to `output/weekly_briefing_2026-10-11.md`, with a copy at
`output/latest_briefing.md`.

Options:

```bash
python -m src.main --week-end 2026-10-04   # report a specific week
python -m src.main --no-slack              # never post to Slack
python -m src.main --config other.yaml     # use another config
python -m pytest -q                        # run the tests
python scripts/generate_sample_data.py     # recreate the sample CSVs
```

If something is wrong with the input (for example a missing file or a missing column), the
program logs a clear error and exits with code 1.

## Slack (optional)

1. In Slack, create an **Incoming Webhook** for the channel you want
   (api.slack.com → Your apps → Incoming Webhooks).
2. **Locally:** `export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."`, then run
   the program.
3. **GitHub Actions:** go to the repo → **Settings → Secrets and variables → Actions → New
   repository secret**, name it `SLACK_WEBHOOK_URL`, and paste the URL.

Never commit the webhook URL. If it isn't set, the run still succeeds and simply saves the
briefing. The URL is never written to the logs.

## GitHub Actions

`.github/workflows/weekly_briefing.yml`:

- **Schedule:** every Monday at 13:00 UTC (8 AM US Central). Edit the `cron` line to change it.
- **Manual:** **Actions → Weekly ecommerce briefing → Run workflow**, optionally with a week end date.
- **Steps:** installs Python 3.12 and the requirements, runs the tests, generates the
  briefing, shows it on the run's **Summary** page, and uploads it as a `weekly-briefing`
  artifact.
- Slack uses the `SLACK_WEBHOOK_URL` secret only if it exists.

## Using real data

Replace the two CSVs with your own exports, keeping the same column names:

- `data/shopify_orders.csv`: `order_id, order_date, customer_id, gross_sales, discount, refund, net_sales, orders`
- `data/ad_performance.csv`: `date, platform, campaign, spend, impressions, clicks, conversions, attributed_revenue`

In production, the next step would be to fetch these files automatically, using the Shopify
Admin API and the Meta and Google Ads reporting APIs, before the report runs. The rest of the
pipeline stays the same.

Note that the sample data covers only Sep 28 – Oct 11, 2026. Until real data is connected,
scheduled runs will keep reporting that same week.

## Project structure

```
├── config.yaml                  thresholds, paths, week settings
├── data/                        fake sample CSVs
├── examples/sample_briefing.md  example output
├── output/                      generated briefings (git-ignored)
├── scripts/generate_sample_data.py
├── src/
│   ├── main.py                  entry point: python -m src.main
│   ├── data_loader.py
│   ├── metrics.py
│   ├── anomaly_detection.py
│   ├── briefing.py
│   └── slack_notifier.py
├── tests/                       pytest tests (KPIs, rules, loading, Slack, end-to-end)
└── .github/workflows/weekly_briefing.yml
```
