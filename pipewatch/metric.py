"""Lightweight metric tracking for pipeline jobs (counters and gauges)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class MetricSample:
    job: str
    name: str
    value: float
    recorded_at: datetime = field(default_factory=_utcnow)

    def to_dict(self) -> dict:
        return {
            "job": self.job,
            "name": self.name,
            "value": self.value,
            "recorded_at": self.recorded_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MetricSample":
        return cls(
            job=data["job"],
            name=data["name"],
            value=float(data["value"]),
            recorded_at=datetime.fromisoformat(data["recorded_at"]),
        )


@dataclass
class MetricStore:
    path: str
    _samples: List[MetricSample] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        self._samples = self._load()

    def _load(self) -> List[MetricSample]:
        if not os.path.exists(self.path):
            return []
        with open(self.path, "r") as fh:
            raw = json.load(fh)
        return [MetricSample.from_dict(d) for d in raw]

    def _save(self) -> None:
        with open(self.path, "w") as fh:
            json.dump([s.to_dict() for s in self._samples], fh, indent=2)

    def record(self, job: str, name: str, value: float) -> MetricSample:
        sample = MetricSample(job=job, name=name, value=value)
        self._samples.append(sample)
        self._save()
        return sample

    def latest(self, job: str, name: str) -> Optional[MetricSample]:
        matches = [s for s in self._samples if s.job == job and s.name == name]
        return matches[-1] if matches else None

    def history(self, job: str, name: str) -> List[MetricSample]:
        return [s for s in self._samples if s.job == job and s.name == name]

    def all_samples(self) -> List[MetricSample]:
        return list(self._samples)

    def job_names(self) -> List[str]:
        return sorted({s.job for s in self._samples})

    def metric_names(self, job: Optional[str] = None) -> List[str]:
        samples = self._samples if job is None else [s for s in self._samples if s.job == job]
        return sorted({s.name for s in samples})

    def summary(self, job: str, name: str) -> Dict[str, Optional[float]]:
        values = [s.value for s in self.history(job, name)]
        if not values:
            return {"count": 0, "min": None, "max": None, "mean": None, "latest": None}
        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "mean": sum(values) / len(values),
            "latest": values[-1],
        }
