from el_zachariahs_drivers.models import Blocker, DriverActor, ProgressSignal
from el_zachariahs_drivers.policies.escalation import escalation_owner
from el_zachariahs_drivers.policies.progress import has_material_progress


def test_material_progress_excludes_no_change():
    assert not has_material_progress([ProgressSignal.NO_CHANGE])
    assert has_material_progress([ProgressSignal.NO_CHANGE, ProgressSignal.STATE_ADVANCED])


def test_escalation_routes_developer_process_to_el_le():
    blocker = Blocker(
        reason="review dispatch stuck", owner=DriverActor.EL_ZACHARIAH, category="process"
    )
    assert escalation_owner(blocker) == DriverActor.EL_LE


def test_escalation_routes_resource_gate_to_zo_el():
    blocker = Blocker(
        reason="authorize paid proof packet", owner=DriverActor.EL_ZACHARIAH, category="resource"
    )
    assert escalation_owner(blocker) == DriverActor.ZO_EL
