from el_zachariahs_drivers.models import DriverActor, ProgressSignal
from el_zachariahs_drivers.policies.progress import has_material_progress


def test_el_le_actor_binding_uses_canonical_profile_name():
    assert DriverActor.EL_LE == "el-le"


def test_task_terminal_signals_declared_and_material():
    assert has_material_progress([ProgressSignal.TASK_FAILED])
    assert has_material_progress([ProgressSignal.TASK_CANCELLED])
