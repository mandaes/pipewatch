"""Utilities for loading and validating threshold rule configs from YAML/JSON."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    import yaml as _yaml
    _HAS_YAML = True
except ImportError:  # pragma: no cover
    _HAS_YAML = False

from pipewatch.threshold import ThresholdOp, ThresholdRule

_REQUIRED_KEYS = {"job", "metric", "op", "value"}
_VALID_OPS = {op.value for op in ThresholdOp}


class ThresholdConfigError(ValueError):
    """Raised when a threshold rule config is invalid."""


def _validate_item(item: Any, index: int) -> None:
    if not isinstance(item, dict):
        raise ThresholdConfigError(f"Rule #{index} is not a mapping: {item!r}")
    missing = _REQUIRED_KEYS - item.keys()
    if missing:
        raise ThresholdConfigError(
            f"Rule #{index} missing required keys: {sorted(missing)}"
        )
    if item["op"] not in _VALID_OPS:
        raise ThresholdConfigError(
            f"Rule #{index} has unknown op {item['op']!r}. "
            f"Valid ops: {sorted(_VALID_OPS)}"
        )
    if not isinstance(item["value"], (int, float)):
        raise ThresholdConfigError(
            f"Rule #{index} 'value' must be numeric, got {type(item['value']).__name__}"
        )


def _item_to_rule(item: dict) -> ThresholdRule:
    return ThresholdRule(
        job=item["job"],
        metric=item["metric"],
        op=ThresholdOp(item["op"]),
        value=float(item["value"]),
        severity=item.get("severity", "warning"),
        description=item.get("description", ""),
    )


def load_rules_from_dict(data: list[Any]) -> list[ThresholdRule]:
    """Parse and validate a list of raw rule dicts."""
    if not isinstance(data, list):
        raise ThresholdConfigError("Top-level structure must be a list of rules.")
    rules = []
    for i, item in enumerate(data):
        _validate_item(item, i)
        rules.append(_item_to_rule(item))
    return rules


def load_rules_from_file(path: str | Path) -> list[ThresholdRule]:
    """Load threshold rules from a JSON or YAML file."""
    p = Path(path)
    text = p.read_text()
    if p.suffix in (".yaml", ".yml"):
        if not _HAS_YAML:  # pragma: no cover
            raise ImportError("PyYAML is required to load YAML threshold configs.")
        data = _yaml.safe_load(text)
    else:
        data = json.loads(text)
    return load_rules_from_dict(data)
