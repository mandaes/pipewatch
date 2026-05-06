"""Tests for pipewatch.threshold."""
from __future__ import annotations

import pytest

from pipewatch.threshold import (
    ThresholdOp,
    ThresholdRule,
    ThresholdViolation,
    evaluate_all,
    evaluate_threshold,
)


def make_rule(
    job="etl",
    metric="duration_s",
    op=ThresholdOp.GT,
    value=60.0,
    severity="warning",
) -> ThresholdRule:
    return ThresholdRule(job=job, metric=metric, op=op, value=value, severity=severity)


class TestEvaluateThreshold:
    def test_gt_violation(self):
        rule = make_rule(op=ThresholdOp.GT, value=60.0)
        v = evaluate_threshold(rule, 90.0)
        assert isinstance(v, ThresholdViolation)
        assert v.actual == 90.0

    def test_gt_no_violation(self):
        rule = make_rule(op=ThresholdOp.GT, value=60.0)
        assert evaluate_threshold(rule, 60.0) is None

    def test_gte_equal_triggers(self):
        rule = make_rule(op=ThresholdOp.GTE, value=50.0)
        assert evaluate_threshold(rule, 50.0) is not None

    def test_lt_violation(self):
        rule = make_rule(op=ThresholdOp.LT, value=10.0)
        assert evaluate_threshold(rule, 5.0) is not None

    def test_lte_no_violation(self):
        rule = make_rule(op=ThresholdOp.LTE, value=10.0)
        assert evaluate_threshold(rule, 11.0) is None

    def test_eq_match(self):
        rule = make_rule(op=ThresholdOp.EQ, value=42.0)
        assert evaluate_threshold(rule, 42.0) is not None

    def test_eq_no_match(self):
        rule = make_rule(op=ThresholdOp.EQ, value=42.0)
        assert evaluate_threshold(rule, 43.0) is None


class TestThresholdViolationToDict:
    def test_contains_required_keys(self):
        rule = make_rule(severity="critical")
        v = ThresholdViolation(rule=rule, actual=120.0)
        d = v.to_dict()
        for key in ("job", "metric", "op", "threshold", "actual", "severity", "message"):
            assert key in d

    def test_message_includes_job_and_metric(self):
        rule = make_rule(job="loader", metric="row_count")
        v = ThresholdViolation(rule=rule, actual=0.0)
        assert "loader" in v.message
        assert "row_count" in v.message

    def test_severity_uppercased_in_message(self):
        rule = make_rule(severity="critical")
        v = ThresholdViolation(rule=rule, actual=999.0)
        assert "CRITICAL" in v.message


class TestEvaluateAll:
    def test_returns_violation_for_matching_rule(self):
        rules = [make_rule(job="etl", metric="duration_s", op=ThresholdOp.GT, value=30.0)]
        samples = {"etl": {"duration_s": 90.0}}
        violations = evaluate_all(rules, samples)
        assert len(violations) == 1

    def test_skips_missing_metric(self):
        rules = [make_rule(job="etl", metric="missing_metric")]
        samples = {"etl": {"duration_s": 100.0}}
        assert evaluate_all(rules, samples) == []

    def test_skips_missing_job(self):
        rules = [make_rule(job="absent_job", metric="duration_s")]
        samples = {"etl": {"duration_s": 100.0}}
        assert evaluate_all(rules, samples) == []

    def test_multiple_rules_multiple_violations(self):
        rules = [
            make_rule(job="etl", metric="duration_s", op=ThresholdOp.GT, value=10.0),
            make_rule(job="etl", metric="error_rate", op=ThresholdOp.GTE, value=0.05),
        ]
        samples = {"etl": {"duration_s": 20.0, "error_rate": 0.1}}
        assert len(evaluate_all(rules, samples)) == 2

    def test_empty_rules_returns_empty(self):
        assert evaluate_all([], {"etl": {"duration_s": 100.0}}) == []
