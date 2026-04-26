"""Notification backends for pipewatch alerts."""

import sys
from abc import ABC, abstractmethod
from typing import List
from pipewatch.alert_rules import AlertEvent


class BaseNotifier(ABC):
    """Abstract base class for alert notifiers."""

    @abstractmethod
    def send(self, events: List[AlertEvent]) -> None:
        """Send notifications for the given alert events."""
        ...


class StdoutNotifier(BaseNotifier):
    """Writes alert events to stdout (useful for CLI and testing)."""

    def __init__(self, prefix: str = "[ALERT]"):
        self.prefix = prefix

    def send(self, events: List[AlertEvent]) -> None:
        for event in events:
            print(f"{self.prefix} {event.message}", file=sys.stdout)


class LogFileNotifier(BaseNotifier):
    """Appends alert events to a log file."""

    def __init__(self, filepath: str):
        self.filepath = filepath

    def send(self, events: List[AlertEvent]) -> None:
        with open(self.filepath, "a") as f:
            for event in events:
                f.write(f"[ALERT] {event.message}\n")


class MultiNotifier(BaseNotifier):
    """Fans out alerts to multiple notifiers."""

    def __init__(self, notifiers: List[BaseNotifier]):
        self.notifiers = notifiers

    def send(self, events: List[AlertEvent]) -> None:
        for notifier in self.notifiers:
            notifier.send(events)


def build_notifier(config: dict) -> BaseNotifier:
    """Factory: build a notifier from a config dict."""
    kind = config.get("type", "stdout")
    if kind == "stdout":
        return StdoutNotifier(prefix=config.get("prefix", "[ALERT]"))
    if kind == "logfile":
        return LogFileNotifier(filepath=config["filepath"])
    raise ValueError(f"Unknown notifier type: {kind!r}")
