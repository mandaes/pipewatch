"""Tests for pipewatch.cli_export."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from pipewatch.cli_export import main, parse_args


class TestParseArgs:
    def test_defaults(self):
        args = parse_args([])
        assert args.format == "json"
        assert args.source == "status"
        assert args.config == "pipewatch.yml"

    def test_csv_format(self):
        args = parse_args(["--format", "csv"])
        assert args.format == "csv"

    def test_history_source(self):
        args = parse_args(["--source", "history"])
        assert args.source == "history"


class TestMainExport:
    def _mock_status(self, job_id="job1"):
        s = MagicMock()
        s.to_dict.return_value = {"job_id": job_id, "state": "success"}
        return s

    @patch("pipewatch.cli_export.build_statuses")
    @patch("pipewatch.cli_export.load_config")
    def test_status_json_output(self, mock_cfg, mock_build, capsys):
        mock_cfg.return_value = {}
        mock_build.return_value = [self._mock_status()]
        main(["--source", "status", "--format", "json"])
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed[0]["job_id"] == "job1"

    @patch("pipewatch.cli_export.build_statuses")
    @patch("pipewatch.cli_export.load_config")
    def test_status_csv_output(self, mock_cfg, mock_build, capsys):
        mock_cfg.return_value = {}
        mock_build.return_value = [self._mock_status()]
        main(["--source", "status", "--format", "csv"])
        captured = capsys.readouterr()
        assert "job_id" in captured.out
        assert "job1" in captured.out

    @patch("pipewatch.cli_export.HistoryStore")
    @patch("pipewatch.cli_export.load_config")
    def test_history_json_output(self, mock_cfg, mock_store_cls, capsys):
        mock_cfg.return_value = {}
        store = MagicMock()
        store.all_job_ids.return_value = []
        mock_store_cls.return_value = store
        main(["--source", "history", "--format", "json"])
        captured = capsys.readouterr()
        assert json.loads(captured.out) == []

    @patch("pipewatch.cli_export.HistoryStore")
    @patch("pipewatch.cli_export.load_config")
    def test_history_csv_empty(self, mock_cfg, mock_store_cls, capsys):
        mock_cfg.return_value = {}
        store = MagicMock()
        store.all_job_ids.return_value = []
        mock_store_cls.return_value = store
        main(["--source", "history", "--format", "csv"])
        captured = capsys.readouterr()
        assert captured.out.strip() == ""
