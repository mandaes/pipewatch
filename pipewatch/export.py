"""Export pipeline status and history to JSON or CSV formats."""
from __future__ import annotations

import csv
import io
import json
from typing import List

from pipewatch.history_reporter import all_jobs_report
from pipewatch.history import HistoryStore
from pipewatch.job_status import JobStatus


def statuses_to_json(statuses: List[JobStatus], indent: int = 2) -> str:
    """Serialise a list of JobStatus objects to a JSON string."""
    return json.dumps([s.to_dict() for s in statuses], indent=indent, default=str)


def statuses_to_csv(statuses: List[JobStatus]) -> str:
    """Serialise a list of JobStatus objects to CSV."""
    if not statuses:
        return ""
    buf = io.StringIO()
    rows = [s.to_dict() for s in statuses]
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def history_report_to_json(store: HistoryStore, limit: int = 50, indent: int = 2) -> str:
    """Serialise all-jobs history report to a JSON string."""
    report = all_jobs_report(store, limit=limit)
    return json.dumps(report, indent=indent, default=str)


def history_report_to_csv(store: HistoryStore, limit: int = 50) -> str:
    """Serialise all-jobs history report to CSV."""
    report = all_jobs_report(store, limit=limit)
    if not report:
        return ""
    buf = io.StringIO()
    # Flatten state_counts into top-level columns
    flat_rows = []
    for row in report:
        flat = {k: v for k, v in row.items() if k != "state_counts"}
        flat.update({f"state_{k}": v for k, v in row.get("state_counts", {}).items()})
        flat_rows.append(flat)
    writer = csv.DictWriter(buf, fieldnames=list(flat_rows[0].keys()), extrasaction="ignore")
    writer.writeheader()
    writer.writerows(flat_rows)
    return buf.getvalue()
