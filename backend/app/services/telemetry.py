"""Lightweight in-process metrics with a Prometheus text exporter.

No third-party dependency is needed; counters and histograms are safe to use
from concurrent request threads.
"""

from __future__ import annotations

import re
import threading
from collections import defaultdict
from typing import Any

_BUCKETS = (5, 10, 25, 50, 100, 250, 500, 1000, 5000)
_INVALID_NAME = re.compile(r"[^a-zA-Z0-9_]")


def _safe_name(name: str) -> str:
    return "mediscan_" + _INVALID_NAME.sub("_", name).strip("_")


def _escape(value: Any) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _label_text(labels: tuple[tuple[str, str], ...]) -> str:
    if not labels:
        return ""
    return "{" + ",".join(f'{key}="{_escape(value)}"' for key, value in labels) + "}"


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[tuple[str, tuple[tuple[str, str], ...]], float] = defaultdict(float)
        self._histograms: dict[tuple[str, tuple[tuple[str, str], ...]], list[float]] = defaultdict(list)

    @staticmethod
    def _key(name: str, labels: dict[str, Any]) -> tuple[str, tuple[tuple[str, str], ...]]:
        return _safe_name(name), tuple(sorted((str(k), str(v)) for k, v in labels.items()))

    def inc(self, name: str, amount: float = 1.0, **labels: Any) -> None:
        with self._lock:
            self._counters[self._key(name, labels)] += float(amount)

    def observe(self, name: str, value: float, **labels: Any) -> None:
        with self._lock:
            self._histograms[self._key(name, labels)].append(float(value))

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "counters": {f"{name}{_label_text(labels)}": round(value, 3) for (name, labels), value in self._counters.items()},
                "histograms": {
                    f"{name}{_label_text(labels)}": {
                        "count": len(values),
                        "sum": round(sum(values), 3),
                        "min": round(min(values), 3) if values else 0.0,
                        "max": round(max(values), 3) if values else 0.0,
                    }
                    for (name, labels), values in self._histograms.items()
                },
            }

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()
            self._histograms.clear()

    def render_prometheus(self) -> str:
        lines: list[str] = []
        with self._lock:
            counters: dict[str, list[tuple[tuple[tuple[str, str], ...], float]]] = defaultdict(list)
            histograms: dict[str, list[tuple[tuple[tuple[str, str], ...], list[float]]]] = defaultdict(list)
            for (name, labels), value in self._counters.items():
                counters[name].append((labels, value))
            for (name, labels), values in self._histograms.items():
                histograms[name].append((labels, values))

        for name, entries in sorted(counters.items()):
            lines.append(f"# HELP {name} MediScan counter.")
            lines.append(f"# TYPE {name} counter")
            for labels, value in sorted(entries):
                lines.append(f"{name}{_label_text(labels)} {value:g}")

        for name, entries in sorted(histograms.items()):
            lines.append(f"# HELP {name} MediScan histogram.")
            lines.append(f"# TYPE {name} histogram")
            for labels, values in sorted(entries):
                total = len(values)
                for boundary in _BUCKETS:
                    count = sum(1 for value in values if value <= boundary)
                    bucket_labels = tuple(sorted((*labels, ("le", str(boundary)))))
                    lines.append(f"{name}_bucket{_label_text(bucket_labels)} {count}")
                inf_labels = tuple(sorted((*labels, ("le", "+Inf"))))
                lines.append(f"{name}_bucket{_label_text(inf_labels)} {total}")
                lines.append(f"{name}_sum{_label_text(labels)} {sum(values):g}")
                lines.append(f"{name}_count{_label_text(labels)} {total}")

        return "\n".join(lines) + "\n" if lines else ""


METRICS = MetricsRegistry()
