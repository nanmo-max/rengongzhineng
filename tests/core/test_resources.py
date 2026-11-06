from __future__ import annotations


def test_resource_tracker_records_nonnegative_usage() -> None:
    from brace_msi.resources import ResourceTracker

    with ResourceTracker() as tracker:
        _ = sum(index * index for index in range(1000))

    usage = tracker.usage
    assert usage.wall_seconds >= 0
    assert usage.cpu_seconds >= 0
    assert usage.peak_rss_bytes >= usage.rss_before_bytes
    assert usage.peak_rss_bytes >= usage.rss_after_bytes
