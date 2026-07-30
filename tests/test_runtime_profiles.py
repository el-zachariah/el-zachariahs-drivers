from pathlib import Path

import pytest

from el_zachariahs_drivers.models import WorkflowRole
from el_zachariahs_drivers.runtime_profiles import load_runtime_profile, require_bound_roles


PROFILE_DIR = Path(__file__).parents[1] / "examples" / "profiles"
REQUIRED_ROLES = set(WorkflowRole)


def test_el_zachariah_runtime_profile_binds_required_roles():
    profile = load_runtime_profile(PROFILE_DIR / "el_zachariah.json")
    require_bound_roles(profile, REQUIRED_ROLES)
    assert profile.actor_for(WorkflowRole.PROCESS_STEWARD) == "el-le"
    assert profile.actor_for(WorkflowRole.REVIEWER) == "el-micaiah"


def test_neutral_runtime_profile_proves_engine_is_not_hardcoded_to_council_names():
    profile = load_runtime_profile(PROFILE_DIR / "neutral_local.json")
    require_bound_roles(profile, REQUIRED_ROLES)
    actors = {binding.actor for binding in profile.role_bindings}
    assert "el-zachariah" not in actors
    assert "zo-el" not in actors
    assert profile.actor_for(WorkflowRole.DEVELOPER) == "implementation-worker"


def test_missing_required_role_is_rejected():
    profile = load_runtime_profile(PROFILE_DIR / "neutral_local.json")
    profile.role_bindings = [
        binding for binding in profile.role_bindings if binding.role != WorkflowRole.REVIEWER
    ]
    with pytest.raises(ValueError, match="reviewer"):
        require_bound_roles(profile, REQUIRED_ROLES)
