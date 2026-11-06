"""Local resource measurements with no platform-specific scoring claims."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter, process_time
from types import TracebackType

import psutil


@dataclass(frozen=True)
class ResourceUsage:
    wall_seconds: float
    cpu_seconds: float
    rss_before_bytes: int
    rss_after_bytes: int
    peak_rss_bytes: int


class ResourceTracker:
    """Measure process resources at operation boundaries."""

    def __init__(self) -> None:
        self._process = psutil.Process()
        self._wall_start = 0.0
        self._cpu_start = 0.0
        self._rss_before = 0
        self.usage: ResourceUsage | None = None

    def __enter__(self) -> ResourceTracker:
        self._rss_before = self._process.memory_info().rss
        self._wall_start = perf_counter()
        self._cpu_start = process_time()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        rss_after = self._process.memory_info().rss
        self.usage = ResourceUsage(
            wall_seconds=perf_counter() - self._wall_start,
            cpu_seconds=process_time() - self._cpu_start,
            rss_before_bytes=self._rss_before,
            rss_after_bytes=rss_after,
            peak_rss_bytes=max(self._rss_before, rss_after),
        )
