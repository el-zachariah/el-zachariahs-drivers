"""Runtime profile loading helpers.

Profiles bind abstract workflow roles to concrete actors/adapters. The engine can
load and validate these bindings without knowing a specific council, transport,
or tool implementation.
"""

from __future__ import annotations

import json
from pathlib import Path

from el_zachariahs_drivers.models import RuntimeProfile, WorkflowRole


def load_runtime_profile(path: str | Path) -> RuntimeProfile:
    """Load a JSON runtime profile fixture or adapter-generated profile."""
    payload = json.loads(Path(path).read_text())
    return RuntimeProfile.model_validate(payload)


def require_bound_roles(profile: RuntimeProfile, roles: set[WorkflowRole]) -> None:
    """Raise if the profile does not bind every required role."""
    bound_roles = {binding.role for binding in profile.role_bindings}
    missing = roles - bound_roles
    if missing:
        missing_names = ", ".join(sorted(role.value for role in missing))
        raise ValueError(f"runtime profile is missing required role binding(s): {missing_names}")
