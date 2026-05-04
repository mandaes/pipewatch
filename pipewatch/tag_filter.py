"""Tag-based filtering for job statuses and history entries."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Optional

from pipewatch.job_status import JobStatus


@dataclass
class TagFilter:
    """Filter that matches jobs possessing all required tags."""

    required: List[str] = field(default_factory=list)
    excluded: List[str] = field(default_factory=list)

    def matches_tags(self, tags: Iterable[str]) -> bool:
        """Return True if *tags* satisfies required/excluded constraints."""
        tag_set = set(tags)
        for req in self.required:
            if req not in tag_set:
                return False
        for exc in self.excluded:
            if exc in tag_set:
                return False
        return True

    def filter_statuses(
        self, statuses: Iterable[JobStatus]
    ) -> List[JobStatus]:
        """Return statuses whose tags satisfy this filter."""
        return [
            s for s in statuses if self.matches_tags(s.tags)
        ]

    def to_dict(self) -> dict:
        return {"required": list(self.required), "excluded": list(self.excluded)}


def parse_tag_filter(
    required: Optional[List[str]] = None,
    excluded: Optional[List[str]] = None,
) -> TagFilter:
    """Convenience constructor accepting optional lists."""
    return TagFilter(
        required=list(required or []),
        excluded=list(excluded or []),
    )
