"""Label management for pipeline jobs.

Labels are arbitrary key-value string pairs attached to a JobStatus,
enabling richer filtering and grouping beyond the existing tag system.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from pipewatch.job_status import JobStatus


@dataclass
class LabelSelector:
    """Selects jobs whose labels match all required key-value pairs."""

    required: Dict[str, str] = field(default_factory=dict)
    excluded_keys: List[str] = field(default_factory=list)

    def matches(self, labels: Dict[str, str]) -> bool:
        """Return True when *labels* satisfies this selector."""
        for key, value in self.required.items():
            if labels.get(key) != value:
                return False
        for key in self.excluded_keys:
            if key in labels:
                return False
        return True

    def to_dict(self) -> dict:
        return {
            "required": dict(self.required),
            "excluded_keys": list(self.excluded_keys),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LabelSelector":
        return cls(
            required=dict(data.get("required", {})),
            excluded_keys=list(data.get("excluded_keys", [])),
        )


def filter_by_labels(
    statuses: List[JobStatus],
    selector: LabelSelector,
) -> List[JobStatus]:
    """Return the subset of *statuses* whose labels satisfy *selector*."""
    return [
        s for s in statuses
        if selector.matches(getattr(s, "labels", {}) or {})
    ]


def parse_label_selector(raw: Optional[str]) -> LabelSelector:
    """Parse a compact selector string such as ``env=prod,!debug``.

    Tokens:
      - ``key=value``  → required label
      - ``!key``       → excluded key
    """
    if not raw:
        return LabelSelector()
    required: Dict[str, str] = {}
    excluded: List[str] = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        if token.startswith("!"):
            excluded.append(token[1:])
        elif "=" in token:
            key, _, value = token.partition("=")
            required[key.strip()] = value.strip()
        else:
            raise ValueError(f"Invalid label selector token: {token!r}")
    return LabelSelector(required=required, excluded_keys=excluded)
