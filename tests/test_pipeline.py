import shutil
from pathlib import Path

import pytest
import requests

from src.data_loader import DataValidationError, load_ads, load_orders
from src.main import main, run
from src.slack_notifier import post_to_slack

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def project(tmp_path):
    """A copy of the config and sample data in a temp folder."""
    shutil.copy(ROOT / "config.yaml", tmp_path / "config.yaml")
    shutil.copytree(ROOT / "data", tmp_path / "data")
    return tmp_path


def test_end_to_end_writes_briefing(project, monkeypatch):
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    path = run(project / "config.yaml")
    text = path.read_text(encoding="utf-8")
    assert path.name == "weekly_briefing_2026-10-11.md"
    assert (project / "output" / "latest_briefing.md").exists()
    assert "Weekly Ecommerce Briefing" in text
    assert "October 5–11, 2026" in text
    assert "## Issues Detected" in text


def test_missing_file_returns_error_code(project):
    (project / "data" / "shopify_orders.csv").unlink()
    assert main(["--config", str(project / "config.yaml"), "--no-slack"]) == 1


def test_missing_columns(tmp_path):
    bad = tmp_path / "orders.csv"
    bad.write_text("order_id,order_date\n1,2026-10-05\n", encoding="utf-8")
    with pytest.raises(DataValidationError, match="missing required columns"):
        load_orders(bad)


def test_empty_files(tmp_path):
    empty = tmp_path / "empty.csv"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(DataValidationError, match="empty"):
        load_ads(empty)
    header_only = tmp_path / "header.csv"
    header_only.write_text("date,platform,campaign,spend,impressions,clicks,conversions,attributed_revenue\n",
                           encoding="utf-8")
    with pytest.raises(DataValidationError, match="no rows"):
        load_ads(header_only)


def test_bad_values_are_cleaned(tmp_path):
    f = tmp_path / "ads.csv"
    f.write_text("date,platform,campaign,spend,impressions,clicks,conversions,attributed_revenue\n"
                 "2026-10-05,Meta,c,abc,10,1,0,0\nnot-a-date,Meta,c,5,10,1,0,0\n", encoding="utf-8")
    df = load_ads(f)
    assert len(df) == 1 and df["spend"].iloc[0] == 0


def test_slack_skipped_without_url():
    assert post_to_slack("hi", None) is False


def test_slack_failure_does_not_raise(monkeypatch):
    def boom(*args, **kwargs):
        raise requests.ConnectionError("down")
    monkeypatch.setattr(requests, "post", boom)
    assert post_to_slack("hi", "https://hooks.slack.com/services/T/B/X") is False


def test_slack_failure_keeps_briefing(project, monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/T/B/X")

    class Resp:
        status_code = 500
        text = "server error"
    monkeypatch.setattr(requests, "post", lambda *a, **k: Resp())
    path = run(project / "config.yaml")
    assert path.exists()


def test_slack_success(monkeypatch):
    sent = {}

    class Resp:
        status_code = 200
        text = "ok"

    def fake_post(url, json, timeout):
        sent.update(json)
        return Resp()
    monkeypatch.setattr(requests, "post", fake_post)
    assert post_to_slack("*Weekly*", "https://hooks.slack.com/services/T/B/X") is True
    assert sent["text"] == "*Weekly*"
