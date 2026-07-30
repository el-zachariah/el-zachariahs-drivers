from el_zachariahs_drivers.models import (
    Blocker,
    DriverActor,
    ProgressSignal,
    ResumeDecisionOption,
    ResumeTarget,
    RunOutcome,
    WorkflowRole,
)
from el_zachariahs_drivers.policies.escalation import escalation_owner
from el_zachariahs_drivers.policies.progress import classify_run_outcome, has_material_progress


def blocker(category: str = "process") -> Blocker:
    return Blocker(
        reason="review dispatch stuck",
        owner=DriverActor.EL_ZACHARIAH,
        owner_role=WorkflowRole.PROCESS_STEWARD,
        category=category,
        required_decision="diagnose dispatch and resume",
        resume_target=ResumeTarget(
            blocked_phase="REVIEW_WAIT",
            resume_phase_if_unblocked="REVIEW_REQUESTED",
            decision_options=[
                ResumeDecisionOption(
                    decision="dispatch fixed",
                    resulting_phase="REVIEW_REQUESTED",
                    notes="request review again",
                )
            ],
        ),
    )


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
    assert escalation_owner(blocker("process")) == DriverActor.EL_LE


def test_escalation_routes_resource_gate_to_zo_el():
    assert escalation_owner(blocker("resource")) == DriverActor.ZO_EL
