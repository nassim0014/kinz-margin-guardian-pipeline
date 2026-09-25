"""Guard against README claims outpacing what the code actually implements.

Regression test for docs/IMPROVEMENTS.md item 12: the README's top-line
description claimed the pipeline "triggers Slack/Email alerts", but
src/alert_manager.py has only ever implemented Slack delivery
(`send_slack_alert`) — there is no email-sending code anywhere in the repo
(grep confirms the only "email"/"smtp" hits are the API's login field and
Airflow's `email_on_failure`/`email_on_retry` defaults, both `False`). This
test reads the alert channels the README claims and the `send_<channel>_alert`
functions `alert_manager.py` actually defines, and fails if the README ever
claims a channel the code doesn't back up.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent


def _implemented_alert_channels() -> set[str]:
    """Channels alert_manager.py actually has a `send_<channel>_alert` for."""
    src = (REPO_ROOT / "src" / "alert_manager.py").read_text()
    return {name.lower() for name in re.findall(r"def send_(\w+)_alert\(", src)}


def _claimed_alert_channels() -> set[str]:
    """Channels the README's top-line description claims to trigger."""
    readme = (REPO_ROOT / "README.md").read_text()
    match = re.search(r"triggers ([\w/]+) alerts", readme)
    assert match, (
        "Expected the README's top-line description to state which alert "
        "channels it triggers (e.g. 'triggers Slack alerts')."
    )
    return {name.lower() for name in match.group(1).split("/")}


def test_readme_alert_claim_matches_implemented_channels():
    claimed = _claimed_alert_channels()
    implemented = _implemented_alert_channels()

    assert claimed <= implemented, (
        f"README claims alert channel(s) {sorted(claimed - implemented)} that "
        f"src/alert_manager.py does not implement (it only has "
        f"send_<channel>_alert for {sorted(implemented)}). This was exactly "
        f"the bug in docs/IMPROVEMENTS.md item 12: the README claimed "
        f"'Slack/Email alerts' while only Slack delivery existed."
    )


def test_no_email_sending_code_exists_yet():
    """Sanity check the other direction: if email alerting ever gets added,
    this test (not just the README) should be the thing that notices — so a
    future PR wiring up email doesn't need to remember to also update the
    README claim above.
    """
    src = (REPO_ROOT / "src" / "alert_manager.py").read_text()
    assert "def send_email_alert(" not in src, (
        "Email alerting now exists in src/alert_manager.py — update the "
        "README's top-line description to claim it, which will make "
        "test_readme_alert_claim_matches_implemented_channels pass again."
    )
