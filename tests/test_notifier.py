"""Tests for pipewatch.notifier."""

import os
import tempfile
import pytest
from pipewatch.job_status import JobState
from pipewatch.alert_rules import AlertEvent
from pipewatch.notifier import StdoutNotifier, LogFileNotifier, MultiNotifier, build_notifier


def make_event(job_name="etl_job", state=JobState.FAILED, message="Job failed") -> AlertEvent:
    return AlertEvent(
        rule_name="test_rule",
        job_name=job_name,
        state=state,
        message=message,
        consecutive_failures=1,
    )


class TestStdoutNotifier:
    def test_sends_to_stdout(self, capsys):
        notifier = StdoutNotifier()
        notifier.send([make_event()])
        captured = capsys.readouterr()
        assert "[ALERT]" in captured.out
        assert "Job failed" in captured.out

    def test_custom_prefix(self, capsys):
        notifier = StdoutNotifier(prefix="[WARN]")
        notifier.send([make_event()])
        captured = capsys.readouterr()
        assert "[WARN]" in captured.out

    def test_no_output_for_empty_events(self, capsys):
        notifier = StdoutNotifier()
        notifier.send([])
        captured = capsys.readouterr()
        assert captured.out == ""


class TestLogFileNotifier:
    def test_writes_to_file(self):
        with tempfile.NamedTemporaryFile(mode="r", suffix=".log", delete=False) as f:
            path = f.name
        try:
            notifier = LogFileNotifier(filepath=path)
            notifier.send([make_event(message="pipeline stale")])
            with open(path) as f:
                content = f.read()
            assert "pipeline stale" in content
            assert "[ALERT]" in content
        finally:
            os.unlink(path)

    def test_appends_multiple_events(self):
        with tempfile.NamedTemporaryFile(mode="r", suffix=".log", delete=False) as f:
            path = f.name
        try:
            notifier = LogFileNotifier(filepath=path)
            notifier.send([make_event(message="first"), make_event(message="second")])
            with open(path) as f:
                lines = f.readlines()
            assert len(lines) == 2
        finally:
            os.unlink(path)


class TestMultiNotifier:
    def test_fans_out_to_all_notifiers(self, capsys):
        n1 = StdoutNotifier(prefix="[N1]")
        n2 = StdoutNotifier(prefix="[N2]")
        multi = MultiNotifier([n1, n2])
        multi.send([make_event(message="fan out test")])
        captured = capsys.readouterr()
        assert "[N1]" in captured.out
        assert "[N2]" in captured.out


class TestBuildNotifier:
    def test_builds_stdout_notifier(self):
        n = build_notifier({"type": "stdout"})
        assert isinstance(n, StdoutNotifier)

    def test_builds_logfile_notifier(self):
        n = build_notifier({"type": "logfile", "filepath": "/tmp/test.log"})
        assert isinstance(n, LogFileNotifier)

    def test_raises_on_unknown_type(self):
        with pytest.raises(ValueError, match="Unknown notifier type"):
            build_notifier({"type": "slack"})
