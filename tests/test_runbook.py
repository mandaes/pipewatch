"""Tests for pipewatch.runbook and pipewatch.cli_runbook."""
from __future__ import annotations

import json
import pytest

from pipewatch.runbook import RunbookEntry, RunbookStore
from pipewatch.cli_runbook import main, parse_args


# ---------------------------------------------------------------------------
# RunbookEntry
# ---------------------------------------------------------------------------

class TestRunbookEntry:
    def test_to_dict_contains_required_keys(self):
        e = RunbookEntry(job_name="etl_load", url="https://wiki/etl_load", notes="check logs")
        d = e.to_dict()
        assert d["job_name"] == "etl_load"
        assert d["url"] == "https://wiki/etl_load"
        assert d["notes"] == "check logs"

    def test_from_dict_roundtrip(self):
        original = RunbookEntry(job_name="job_a", url="https://example.com", notes="")
        restored = RunbookEntry.from_dict(original.to_dict())
        assert restored.job_name == original.job_name
        assert restored.url == original.url

    def test_notes_defaults_to_empty_string(self):
        e = RunbookEntry.from_dict({"job_name": "x", "url": "http://x"})
        assert e.notes == ""


# ---------------------------------------------------------------------------
# RunbookStore
# ---------------------------------------------------------------------------

class TestRunbookStore:
    def test_lookup_exact_match(self):
        store = RunbookStore()
        store.add(RunbookEntry("*", "https://default"))
        store.add(RunbookEntry("my_job", "https://specific"))
        entry = store.lookup("my_job")
        assert entry is not None
        assert entry.url == "https://specific"

    def test_lookup_falls_back_to_wildcard(self):
        store = RunbookStore()
        store.add(RunbookEntry("*", "https://fallback"))
        entry = store.lookup("unknown_job")
        assert entry is not None
        assert entry.url == "https://fallback"

    def test_lookup_returns_none_when_no_match(self):
        store = RunbookStore()
        assert store.lookup("missing") is None

    def test_from_list_roundtrip(self):
        data = [
            {"job_name": "a", "url": "http://a", "notes": ""},
            {"job_name": "*", "url": "http://default", "notes": "fallback"},
        ]
        store = RunbookStore.from_list(data)
        assert len(store.entries) == 2
        assert store.all_entries() == data


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

class TestCliRunbook:
    def test_parse_args_defaults(self):
        args = parse_args(["list"])
        assert args.command == "list"
        assert args.runbook_file == "runbook.json"

    def test_list_empty(self, capsys):
        main(["--runbook-file", "/dev/null", "list"])
        captured = capsys.readouterr()
        # /dev/null is not valid JSON; store will be empty via missing file fallback
        # We just check it doesn't crash — actual output depends on OS.

    def test_add_and_lookup(self, tmp_path, capsys):
        rb_file = str(tmp_path / "rb.json")
        main(["--runbook-file", rb_file, "add", "etl_job", "https://wiki/etl", "--notes", "check s3"])
        main(["--runbook-file", rb_file, "lookup", "etl_job"])
        out = capsys.readouterr().out
        assert "https://wiki/etl" in out
        assert "check s3" in out

    def test_lookup_missing_exits_nonzero(self, tmp_path):
        rb_file = str(tmp_path / "rb.json")
        with pytest.raises(SystemExit) as exc_info:
            main(["--runbook-file", rb_file, "lookup", "ghost_job"])
        assert exc_info.value.code == 1

    def test_add_persists_to_file(self, tmp_path):
        rb_file = str(tmp_path / "rb.json")
        main(["--runbook-file", rb_file, "add", "job_x", "https://x"])
        with open(rb_file) as fh:
            data = json.load(fh)
        assert any(e["job_name"] == "job_x" for e in data)
