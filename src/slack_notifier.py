"""Optional Slack delivery through an incoming webhook."""
from __future__ import annotations

import logging
from typing import Optional

import requests

log = logging.getLogger(__name__)


def post_to_slack(text: str, webhook_url: Optional[str], timeout: float = 10.0) -> bool:
    """Post text to Slack. Returns True on success; never raises.

    The webhook URL is a secret, so it is never logged.
    """
    if not webhook_url:
        log.info("SLACK_WEBHOOK_URL not set; skipping Slack delivery")
        return False
    if not webhook_url.startswith("https://hooks.slack.com/"):
        log.warning("SLACK_WEBHOOK_URL does not look like a Slack incoming webhook; skipping")
        return False
    try:
        response = requests.post(webhook_url, json={"text": text}, timeout=timeout)
    except requests.RequestException as exc:
        log.error("Slack delivery failed: %s", type(exc).__name__)
        return False
    if response.status_code != 200:
        log.error("Slack delivery failed: HTTP %s %s", response.status_code, response.text[:200])
        return False
    log.info("Briefing posted to Slack")
    return True
