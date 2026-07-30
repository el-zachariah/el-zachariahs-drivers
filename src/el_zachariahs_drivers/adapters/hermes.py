"""Hermes adapter boundary.

This module will eventually translate driver activities into Hermes operations:
Kanban cards, profile dispatch, GitHub CLI calls through profile-local wrappers,
and final user reports. Keep it thin so Temporal/LangGraph patterns remain clear.
"""

from __future__ import annotations


def placeholder() -> str:
    return "hermes-adapter-boundary"
