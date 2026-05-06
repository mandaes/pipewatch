"""Tests for pipewatch.cli_webhook."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from pipewatch.cli_webhook import parse_args, main


class TestParseArgs:
    def test_ping_defaults(self):
        args = parse_args(["ping", "http://hook.test/"])
        assert args.command == "ping"
        assert args.url == "http://hook.test/"
        assert args.job == "test_job"
        assert args.state == "failed"
        assert args.timeout == 10

    def test_ping_custom_job_and_state(self):
        args = parse_args(["ping", "http://x.io", "--job", "my_job", "--state", "stale"])
        assert args.job == "my_job"
        assert args.state == "stale"

    def test_show_config_command(self):
        cfg = json.dumps({"url": "http://a.b/c"})
        args = parse_args(["show-config", cfg])
        assert args.command == "show-config"

    def test_missing_command_raises(self):
        with pytest.raises(SystemExit):
            parse_args([])


class TestMainPing:
    def test_successful_ping_exits_zero(self, capsys):
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            with pytest.raises(SystemExit) as exc_info:
                main(["ping", "http://hook.test/"])
        assert exc_info.value.code == 0
        out = capsys.readouterr().out
        assert "OK" in out

    def test_failed_ping_exits_one(self, capsys):
        import urllib.error
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("refused"),
        ):
            with pytest.raises(SystemExit) as exc_info:
                main(["ping", "http://hook.test/"])
        assert exc_info.value.code == 1
        err = capsys.readouterr().err
        assert "ERROR" in err


class TestMainShowConfig:
    def test_valid_json_prints_config(self, capsys):
        cfg = json.dumps({"url": "http://a.b/c", "method": "PUT"})
        with pytest.raises(SystemExit) as exc_info:
            main(["show-config", cfg])
        assert exc_info.value.code == 0
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed["url"] == "http://a.b/c"
        assert parsed["method"] == "PUT"

    def test_invalid_json_exits_one(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["show-config", "{not valid json"])
        assert exc_info.value.code == 1
        err = capsys.readouterr().err
        assert "Invalid JSON" in err
