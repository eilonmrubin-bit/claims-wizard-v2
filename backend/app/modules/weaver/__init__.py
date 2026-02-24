"""Weaver module - weaves input axes into effective periods and daily records."""

from .orchestrator import run_weaver, WeaverResult

__all__ = ["run_weaver", "WeaverResult"]
