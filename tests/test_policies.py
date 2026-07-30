from el_zachariahs_drivers.models import Blocker, DriverActor, ProgressSignal, RunOutcome
from el_zachariahs_drivers.policies.escalation import escalation_owner
from el_zachariahs_drivers.policies.progress import classify_run_outcome, has_material_progress


def test_material_progress_requires_real_signal():
    assert not has_material_progress([])
    assert has_material_progress([ProgressSignal.PLAN_CREATED])


def test_classify_run_without_signal_is_stalled_not_progress():
    assert classify_run_outcome([]) == RunOutcome.STALLED


def test_classify_run_controlled_wait_is_not_material_progress():
    signals = [ProgressSignal.RETRY_SCHEDULED]
    assert not has_material_progress(signals)
    assert classify_run_outcome(signals) == RunOutcome.CONTROLLED_WAIT


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
