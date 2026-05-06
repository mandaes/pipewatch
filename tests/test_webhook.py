"""Tests for pipewatch.webhook."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import urllib.error

import pytest

from pipewatch.alert_rules import AlertEvent
from pipewatch.job_status import JobState
from pipewatch.webhook import WebhookConfig, WebhookNotifier, build_webhook_notifier


def make_event(job: str = "etl_load", state: JobState = JobState.FAILED) -> AlertEvent:
    return AlertEvent(
        job_name=job,
        state=state,
        rule_name="fail_rule",
        triggered_at=datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc),
    )


class TestWebhookConfig:
    def test_to_dict_contains_required_keys(self):
        cfg = WebhookConfig(url="http://example.com/hook")
        d = cfg.to_dict()
        assert d["url"] == "http://example.com/hook"
        assert d["method"] == "POST"
        assert "Content-Type" in d["headers"]
        assert d["timeout_seconds"] == 10

    def test_custom_method_preserved(self):
        cfg = WebhookConfig(url="http://x.io", method="PUT")
        assert cfg.to_dict()["method"] == "PUT"


class TestWebhookNotifier:
    def _make_notifier(self, url: str = "http://hook.test/alert") -> WebhookNotifier:
        return WebhookNotifier(config=WebhookConfig(url=url))

    def test_send_empty_events_does_not_call_urlopen(self):
        notifier = self._make_notifier()
        with patch("urllib.request.urlopen") as mock_open:
            notifier.send([])
            mock_open.assert_not_called()

    def test_send_posts_json_payload(self):
        notifier = self._make_notifier()
        events = [make_event()]
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
            notifier.send(events)
            assert mock_open.called
            req = mock_open.call_args[0][0]
            body = json.loads(req.data.decode())
            assert isinstance(body, list)
            assert body[0]["job_name"] == "etl_load"

    def test_send_sets_last_error_on_failure(self):
        notifier = self._make_notifier()
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("connection refused"),
        ):
            with pytest.raises(urllib.error.URLError):
                notifier.send([make_event()])
        assert notifier.last_error is not None
        assert "connection refused" in notifier.last_error

    def test_last_error_cleared_on_success(self):
        notifier = self._make_notifier()
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("boom"),
        ):
            with pytest.raises(urllib.error.URLError):
                notifier.send([make_event()])
        with patch("urllib.request.urlopen", return_value=mock_resp):
            notifier.send([make_event()])
        assert notifier.last_error is None


class TestBuildWebhookNotifier:
    def test_builds_from_minimal_dict(self):
        n = build_webhook_notifier({"url": "http://a.b/c"})
        assert n.config.url == "http://a.b/c"
        assert n.config.method == "POST"

    def test_builds_with_overrides(self):
        n = build_webhook_notifier(
            {"url": "http://a.b/c", "method": "PUT", "timeout_seconds": 5}
        )
        assert n.config.method == "PUT"
        assert n.config.timeout_seconds == 5
