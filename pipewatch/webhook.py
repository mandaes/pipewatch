"""Webhook notifier for sending alert events to HTTP endpoints."""

from __future__ import annotations

import json
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import List, Optional

from pipewatch.alert_rules import AlertEvent
from pipewatch.notifier import BaseNotifier


@dataclass
class WebhookConfig:
    url: str
    method: str = "POST"
    headers: dict = field(default_factory=lambda: {"Content-Type": "application/json"})
    timeout_seconds: int = 10

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "method": self.method,
            "headers": self.headers,
            "timeout_seconds": self.timeout_seconds,
        }


@dataclass
class WebhookNotifier(BaseNotifier):
    config: WebhookConfig
    _last_error: Optional[str] = field(default=None, init=False, repr=False)

    def send(self, events: List[AlertEvent]) -> None:
        if not events:
            return
        payload = json.dumps([e.to_dict() for e in events]).encode("utf-8")
        req = urllib.request.Request(
            url=self.config.url,
            data=payload,
            method=self.config.method,
            headers=self.config.headers,
        )
        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout_seconds):
                pass
            self._last_error = None
        except urllib.error.URLError as exc:
            self._last_error = str(exc)
            raise

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error


def build_webhook_notifier(cfg: dict) -> WebhookNotifier:
    """Construct a WebhookNotifier from a plain config dict."""
    wc = WebhookConfig(
        url=cfg["url"],
        method=cfg.get("method", "POST"),
        headers=cfg.get("headers", {"Content-Type": "application/json"}),
        timeout_seconds=cfg.get("timeout_seconds", 10),
    )
    return WebhookNotifier(config=wc)
