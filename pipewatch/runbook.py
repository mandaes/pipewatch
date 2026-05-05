"""Runbook links: associate alert rules with remediation URLs or notes."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RunbookEntry:
    """A runbook entry ties a job name (or wildcard '*') to a URL and optional notes."""

    job_name: str  # exact job name or '*' for any job
    url: str
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "job_name": self.job_name,
            "url": self.url,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RunbookEntry":
        return cls(
            job_name=data["job_name"],
            url=data["url"],
            notes=data.get("notes", ""),
        )


@dataclass
class RunbookStore:
    """In-memory store of runbook entries, queryable by job name."""

    entries: list[RunbookEntry] = field(default_factory=list)

    def add(self, entry: RunbookEntry) -> None:
        self.entries.append(entry)

    def lookup(self, job_name: str) -> Optional[RunbookEntry]:
        """Return the most specific matching entry for *job_name*.

        Exact matches take priority over wildcard entries.
        """
        exact = [e for e in self.entries if e.job_name == job_name]
        if exact:
            return exact[-1]
        wildcards = [e for e in self.entries if e.job_name == "*"]
        return wildcards[-1] if wildcards else None

    def all_entries(self) -> list[dict]:
        return [e.to_dict() for e in self.entries]

    @classmethod
    def from_list(cls, data: list[dict]) -> "RunbookStore":
        store = cls()
        for item in data:
            store.add(RunbookEntry.from_dict(item))
        return store
