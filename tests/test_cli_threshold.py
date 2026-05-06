"""Tests for pipewatch.cli_threshold."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pipewatch.cli_threshold import _load_rules, _render_text, parse_args
from pipewatch.threshold import ThresholdOp, ThresholdRule, ThresholdViolation


# ---------------------------------------------------------------------------
# parse_args
# ---------------------------------------------------------------------------

class TestParseArgs:
    def test_defaults(self, tmp_path):
        rules_file = tmp_path / "rules.json"
        rules_file.write_text("[]")
        args = parse_args(["--rules", str(rules_file)])
        assert args.metrics == "metrics.json"
        assert args.fmt == "text"
        assert args.severity is None

    def test_json_format(self, tmp_path):
        rules_file = tmp_path / "rules.json"
        rules_file.write_text("[]")
        args = parse_args(["--rules", str(rules_file), "--format", "json"])
        assert args.fmt == "json"

    def test_severity_filter(self, tmp_path):
        rules_file = tmp_path / "rules.json"
        rules_file.write_text("[]")
        args = parse_args(["--rules", str(rules_file), "--severity", "critical"])
        assert args.severity == "critical"


# ---------------------------------------------------------------------------
# _load_rules
# ---------------------------------------------------------------------------

class TestLoadRules:
    def test_loads_single_rule(self, tmp_path):
        data = [{"job": "etl", "metric": "duration_s", "op": "gt", "value": 30}]
        f = tmp_path / "rules.json"
        f.write_text(json.dumps(data))
        rules = _load_rules(str(f))
        assert len(rules) == 1
        assert rules[0].op == ThresholdOp.GT
        assert rules[0].value == 30.0

    def test_default_severity_is_warning(self, tmp_path):
        data = [{"job": "etl", "metric": "m", "op": "lt", "value": 1}]
        f = tmp_path / "rules.json"
        f.write_text(json.dumps(data))
        rules = _load_rules(str(f))
        assert rules[0].severity == "warning"

    def test_empty_file_returns_empty_list(self, tmp_path):
        f = tmp_path / "rules.json"
        f.write_text("[]")
        assert _load_rules(str(f)) == []


# ---------------------------------------------------------------------------
# _render_text
# ---------------------------------------------------------------------------

def _make_violation(severity="warning") -> ThresholdViolation:
    rule = ThresholdRule(
        job="etl", metric="duration_s",
        op=ThresholdOp.GT, value=10.0, severity=severity,
    )
    return ThresholdViolation(rule=rule, actual=99.0)


class TestRenderText:
    def test_no_violations_returns_no_violations_message(self):
        assert _render_text([], None) == "No threshold violations."

    def test_renders_violation_message(self):
        v = _make_violation("critical")
        out = _render_text([v], None)
        assert "etl" in out
        assert "CRITICAL" in out

    def test_severity_filter_hides_other_levels(self):
        warn = _make_violation("warning")
        crit = _make_violation("critical")
        out = _render_text([warn, crit], "critical")
        assert "CRITICAL" in out
        assert "WARNING" not in out

    def test_severity_filter_all_hidden_shows_no_violations(self):
        v = _make_violation("warning")
        out = _render_text([v], "critical")
        assert out == "No threshold violations."
