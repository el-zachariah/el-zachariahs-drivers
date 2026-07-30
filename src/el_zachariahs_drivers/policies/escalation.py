"""Escalation policy for developer/process vs human-authority blockers."""

from __future__ import annotations

from el_zachariahs_drivers.models import Blocker, DriverActor


def escalation_owner(blocker: Blocker) -> DriverActor:
    """Route blockers to the right owner.

    Developer/process judgment should go to El-Le/default first. Human authority,
    resource, product, merge, dogfood, and credential gates go to zo-el.
    """
    if blocker.category in {"developer", "process", "external"}:
        return DriverActor.EL_LE
    return DriverActor.ZO_EL
