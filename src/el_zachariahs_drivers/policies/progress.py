"""Material-progress policy.

A driver run is only useful if it changes durable state or produces new evidence.
Repeated observation of the same state is not progress.
"""

from __future__ import annotations

from collections.abc import Iterable

from el_zachariahs_drivers.models import ProgressSignal

MATERIAL_PROGRESS_SIGNALS = frozenset(
    {
        ProgressSignal.PR_HEAD_CHANGED,
        ProgressSignal.TEST_EVIDENCE_CREATED,
        ProgressSignal.PROOF_EVIDENCE_CREATED,
        ProgressSignal.REVIEW_REQUESTED,
        ProgressSignal.REVIEW_COMPLETED,
        ProgressSignal.BLOCKER_ESCALATED,
        ProgressSignal.STATE_ADVANCED,
    }
)


def has_material_progress(signals: Iterable[ProgressSignal]) -> bool:
    """Return True if this run produced at least one durable progress signal."""
    return any(signal in MATERIAL_PROGRESS_SIGNALS for signal in signals)
