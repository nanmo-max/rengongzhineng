"""Read-only proxy-data adapters for local BRACE-MSI experiments."""

from .types import BatchData, TaskStream
from .xjtu import load_xjtu_stream

__all__ = ["BatchData", "TaskStream", "load_xjtu_stream"]
