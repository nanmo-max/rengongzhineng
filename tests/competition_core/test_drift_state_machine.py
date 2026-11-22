from __future__ import annotations

import math

import pytest


def test_known_horizon_alpha_spending_never_exceeds_run_budget() -> None:
    from brace_formal.drift_state import AlphaSpending

    spending = AlphaSpending(alpha_run=0.05, horizon=10)
    allocations = [spending.alpha_for_look(index) for index in range(1, 11)]

    assert all(math.isclose(value, 0.005) for value in allocations)
    assert math.isclose(sum(allocations), 0.05)
    with pytest.raises(ValueError, match="horizon"):
        spending.alpha_for_look(11)


def test_open_horizon_alpha_spending_has_bounded_prefix_sum() -> None:
    from brace_formal.drift_state import AlphaSpending

    spending = AlphaSpending(alpha_run=0.05)
    allocations = [spending.alpha_for_look(index) for index in range(1, 10_001)]

    assert all(value > 0.0 for value in allocations)
    assert sum(allocations) < 0.05
    assert math.isclose(sum(allocations), 0.05 * (1.0 - 1.0 / 10_001.0))


def _machine():
    from brace_formal.drift_state import ReferenceStateMachine, StateMachineConfig

    return ReferenceStateMachine(
        StateMachineConfig(
            calibration_min_windows=3,
            confirmation_windows=2,
            recovery_windows=2,
            rebase_min_windows=3,
            stable_delay_windows=1,
        )
    )


def _calibrated_state():
    from brace_formal.drift_state import DriftState, Observation

    machine = _machine()
    state = DriftState.initial(alpha_run=0.05)
    for window_id in ("cal-1", "cal-2", "cal-3"):
        state = machine.observe(state, window_id, Observation.STABLE)
    return machine, state


def test_warning_confirmation_and_recovery_cannot_pollute_active_reference() -> None:
    from brace_formal.drift_state import Observation, ReferenceStatus

    machine, state = _calibrated_state()
    original = state.active_reference_ids
    assert state.status is ReferenceStatus.STABLE

    state = machine.observe(state, "warn-1", Observation.WARNING)
    assert state.status is ReferenceStatus.WARNING
    state = machine.observe(state, "warn-2", Observation.WARNING)
    assert state.status is ReferenceStatus.CONFIRMED
    state = machine.observe(state, "recover-1", Observation.STABLE)
    assert state.status is ReferenceStatus.RECOVERY
    state = machine.observe(state, "recover-2", Observation.STABLE)

    assert state.status is ReferenceStatus.STABLE
    assert state.active_reference_ids == original
    assert not set(("warn-1", "warn-2", "recover-1", "recover-2")).intersection(
        state.active_reference_ids
    )


def test_repeated_transient_warnings_remain_outside_reference_pool() -> None:
    from brace_formal.drift_state import Observation, ReferenceStatus

    machine, state = _calibrated_state()
    transient_ids: list[str] = []
    for episode in range(3):
        warning = f"transient-{episode}"
        transient_ids.append(warning)
        state = machine.observe(state, warning, Observation.WARNING)
        state = machine.observe(state, f"recovery-{episode}-1", Observation.STABLE)
        state = machine.observe(state, f"recovery-{episode}-2", Observation.STABLE)
        assert state.status is ReferenceStatus.STABLE

    assert not set(transient_ids).intersection(state.active_reference_ids)


def test_persistent_new_regime_atomically_replaces_reference_epoch() -> None:
    from brace_formal.drift_state import Observation, ReferenceStatus

    machine, state = _calibrated_state()
    state = machine.observe(state, "warn-1", Observation.WARNING)
    state = machine.observe(state, "warn-2", Observation.WARNING)
    assert state.status is ReferenceStatus.CONFIRMED

    state = machine.observe(state, "new-1", Observation.CONFIRMED, candidate_stable=True)
    assert state.status is ReferenceStatus.REBASE_PENDING
    state = machine.observe(state, "new-2", Observation.CONFIRMED, candidate_stable=True)
    state = machine.observe(state, "new-3", Observation.CONFIRMED, candidate_stable=True)

    assert state.status is ReferenceStatus.STABLE_NEW_BASELINE
    assert state.reference_epoch == 2
    assert state.active_reference_ids == ("new-1", "new-2", "new-3")
    assert "warn-1" not in state.active_reference_ids
    assert "warn-2" not in state.active_reference_ids


def test_data_quality_failure_is_rejected_without_changing_reference() -> None:
    from brace_formal.drift_state import Observation

    machine, state = _calibrated_state()
    original = state.active_reference_ids

    state = machine.observe(
        state,
        "broken-input",
        Observation.WARNING,
        data_quality_ok=False,
    )

    assert state.active_reference_ids == original
    assert state.rejected_window_ids[-1] == "broken-input"


def test_state_round_trip_and_duplicate_window_fail_closed() -> None:
    from brace_formal.drift_state import DriftState, Observation

    machine, state = _calibrated_state()
    restored = DriftState.from_dict(state.as_dict())

    assert restored == state
    with pytest.raises(ValueError, match="already observed"):
        machine.observe(restored, "cal-3", Observation.STABLE)


def test_corrupted_state_cannot_place_one_window_in_multiple_reference_pools() -> None:
    from brace_formal.drift_state import DriftState

    _, state = _calibrated_state()
    payload = state.as_dict()
    payload["candidate_reference_ids"] = [state.active_reference_ids[0]]

    with pytest.raises(ValueError, match="reference pools overlap"):
        DriftState.from_dict(payload)
