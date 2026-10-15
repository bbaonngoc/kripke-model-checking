"""G3: solver thật cho SAT/UNSAT; UNKNOWN/ERROR có tests giả lập ghi rõ.

Không thay đổi model.py hoặc thêm mô hình nghiệp vụ khác để ép kết quả.
"""

from copy import deepcopy
import json

import pytest
import z3

from run import main
from smartlock import bmc, ctl
from smartlock.kripke import build_model, load_g2_model, make_trace, replay_trace, write_model
from smartlock.model import EVENTS, State


@pytest.fixture(scope="module", params=["v0", "v1"])
def verified(request):
    model = build_model(request.param)
    explicit = ctl.check_ctl(model)
    bounded = {pid: bmc.check_safety_bmc(model, pid) for pid in ctl.SAFETY_PROPERTIES}
    return model, explicit, bounded


@pytest.mark.parametrize("pid", list(ctl.FORMULAS))
def test_five_ctl_results_before_and_after_fix(verified, pid):
    model, explicit, _ = verified
    expected = not (model.version == "v0" and pid in ("P1", "P5"))
    result = explicit[pid]
    assert result["holds"] is expected
    assert result["status"] == ("HOLDS" if expected else "VIOLATED")
    assert result["antecedent_states"]  # Không kết luận đúng do tiền đề unreachable.
    assert set(explicit) == {"P1", "P2", "P3", "P4", "P5"}


@pytest.mark.parametrize("pid", ctl.SAFETY_PROPERTIES)
def test_real_bmc_agrees_with_explicit_safety_check(verified, pid):
    model, explicit, bounded = verified
    result = bounded[pid]
    assert result["holds"] == explicit[pid]["holds"]
    assert result["completeness_threshold"] == 5
    assert all(query["solver_called"] for query in result["checks"])
    assert all("(check-sat)" in query["smt2"] for query in result["checks"])
    if model.version == "v0" and pid == "P1":
        assert result["checked_bounds"] == [0, 1]
        assert [q["status"] for q in result["checks"]] == ["UNSAT", "SAT"]
        assert result["shortest_counterexample"] is True
        trace = result["counterexample"]
        assert len(trace["steps"]) == 2 and trace["violation_step"] == 1
        assert trace["steps"][1]["incoming_event"] == "open_door"
        assert trace["steps"][1]["state"]["authenticated"] is False
        assert ctl.validate_counterexample(model, trace, pid)
    else:
        assert result["checked_bounds"] == list(range(6))
        assert result["last_solver_status"] == "UNSAT"
        assert result["counterexample"] is None


@pytest.mark.parametrize("pid,state,expected", [
    ("P1", State(), False),
    ("P1", State(door_open=True), True),
    ("P1", State(door_open=True, authenticated=True), False),
    ("P1", State(door_open=True, authenticated=True, phase="locked_out", failed_attempts=3), True),
    ("P2", State(phase="locked_out", failed_attempts=2), True),
    ("P2", State(phase="locked_out", failed_attempts=3), False),
    ("P2", State(failed_attempts=3), False),  # Công thức chỉ là một chiều.
    ("P3", State(alarm=True, door_open=True), True),
    ("P3", State(alarm=True), False),
    ("P4", State(phase="resetting"), True),
    ("P4", State(phase="resetting", admin_authorized=True), False),
])
def test_bad_predicates_read_real_state_values(pid, state, expected):
    assert ctl.bad_state(state, pid) is expected


def test_p5_cannot_be_misclassified_as_a_safety_bad_state():
    with pytest.raises(ValueError, match="P5"):
        ctl.bad_state(State(phase="resetting"), "P5")
    result = bmc.check_bound(build_model("v0"), "P5", 1)
    assert result["status"] == "ERROR"
    assert result["solver_called"] is False and result["solver_status"] is None


def test_transition_smt_enumerates_exactly_the_g2_event_edges(verified):
    model, _, _ = verified
    source, event, target = z3.Ints("edge_source edge_event edge_target")
    solver = z3.Solver()
    solver.add(bmc.transition_constraint(model, source, event, target))
    ids = list(model.states)
    actual = set()
    while True:
        result = solver.check()
        if result == z3.unsat:
            break
        assert result == z3.sat
        witness = solver.model()
        a, e, b = [witness.eval(variable).as_long() for variable in (source, event, target)]
        assert 0 <= a < len(ids) and 0 <= b < len(ids) and 0 <= e < len(EVENTS)
        actual.add((ids[a], EVENTS[e], ids[b]))
        solver.add(z3.Or(source != a, event != e, target != b))
    assert actual == {(edge.source, edge.event, edge.target) for edge in model.transitions}


@pytest.mark.parametrize("bound", [0, 1, 5])
def test_path_encoding_includes_initial_and_domains(verified, bound):
    model, _, _ = verified
    states, events, constraints = bmc.encode_path(model, bound)
    assert len(states) == bound + 1 and len(events) == bound
    solver = z3.Solver()
    solver.add(*constraints)
    assert solver.check() == z3.sat
    solver.push()
    solver.add(states[0] != list(model.states).index("s0"))
    assert solver.check() == z3.unsat
    solver.pop()
    solver.add(states[-1] == len(model.states))
    assert solver.check() == z3.unsat


def test_unrolling_does_not_teleport_to_an_authenticated_open_state(verified):
    model, _, _ = verified
    target = next(sid for sid, s in model.states.items() if s.door_open and s.authenticated)
    for bound, expected in [(1, z3.unsat), (2, z3.sat)]:
        states, _, constraints = bmc.encode_path(model, bound)
        solver = z3.Solver()
        solver.add(*constraints, states[-1] == list(model.states).index(target))
        assert solver.check() == expected


def test_small_bound_unsat_does_not_claim_global_safety():
    model = build_model("v0")
    result = bmc.check_safety_bmc(model, "P1", max_bound=0)
    assert result["checks"][0]["solver_status"] == "UNSAT"
    assert result["status"] == "BOUNDED_NO_COUNTEREXAMPLE"
    assert result["holds"] is None
    assert ctl.check_ctl(model)["P1"]["holds"] is False


def test_safety_threshold_is_maximum_shortest_distance(verified):
    model, _, bounded = verified
    depths = ctl.reachable_depths(model)
    assert set(depths) == set(model.states)
    assert max(depths.values()) == max(len(model.graph.find_path(sid)) - 1 for sid in model.states) == 5
    assert 5 < len(model.states) - 1
    assert all(r["completeness_threshold"] == 5 for r in bounded.values())


class SimulatedUnknownSolver:
    """Chỉ dùng trong test phân loại; không ghi vào kết quả nghiệm thu Z3."""

    def __init__(self):
        self.inner = z3.Solver()

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def check(self):
        return z3.unknown

    def reason_unknown(self):
        return "simulated UNKNOWN for unit test"

    def model(self):
        raise AssertionError("Không được gọi model() khi UNKNOWN")


def test_simulated_unknown_stays_unknown_and_stops_shortest_search(monkeypatch):
    monkeypatch.setattr(bmc, "Solver", SimulatedUnknownSolver)
    result = bmc.check_safety_bmc(build_model("v0"), "P1")
    assert result["status"] == "INCONCLUSIVE" and result["holds"] is None
    assert result["checked_bounds"] == [0]
    query = result["checks"][0]
    assert query["status"] == query["solver_status"] == "UNKNOWN"
    assert query["reason"] == "simulated UNKNOWN for unit test"
    assert query["counterexample"] is None
    assert result["shortest_counterexample"] is False


def test_simulated_error_before_solver_call_is_not_unsat(monkeypatch):
    def broken_solver():
        raise RuntimeError("simulated constructor failure")
    monkeypatch.setattr(bmc, "Solver", broken_solver)
    result = bmc.check_bound(build_model("v1"), "P1", 0)
    assert result["status"] == "ERROR"
    assert result["solver_status"] is None and result["solver_called"] is False
    assert "simulated constructor failure" in result["reason"]


def test_simulated_error_during_check_is_separate_from_unknown(monkeypatch):
    class BrokenCheck(SimulatedUnknownSolver):
        def check(self):
            raise z3.Z3Exception("simulated check failure")
    monkeypatch.setattr(bmc, "Solver", BrokenCheck)
    result = bmc.check_bound(build_model("v1"), "P1", 0)
    assert result["status"] == "ERROR"
    assert result["solver_status"] is None and result["solver_called"] is True


def test_real_sat_followed_by_simulated_replay_failure_preserves_solver_status(monkeypatch):
    original = bmc.make_trace

    def damaged_trace(*args):
        trace = original(*args)
        trace["steps"][1]["incoming_event"] = "wait"
        return trace

    monkeypatch.setattr(bmc, "make_trace", damaged_trace)
    result = bmc.check_bound(build_model("v0"), "P1", 1)
    assert result["solver_status"] == "SAT" and result["solver_called"] is True
    assert result["status"] == "ERROR"
    assert result["counterexample"] is None and result["replay_validated"] is False


def test_even_empty_bad_set_makes_a_real_solver_call(monkeypatch):
    calls = []

    class ObservedSolver(SimulatedUnknownSolver):
        def check(self):
            calls.append(True)
            return self.inner.check()

    monkeypatch.setattr(bmc, "Solver", ObservedSolver)
    result = bmc.check_bound(build_model("v1"), "P2", 0)
    assert calls == [True]
    assert result["status"] == result["solver_status"] == "UNSAT"
    assert result["solver_called"]


@pytest.mark.parametrize("version,pid,bound,expected", [
    ("v0", "P1", 0, z3.unsat), ("v0", "P1", 1, z3.sat), ("v1", "P2", 0, z3.unsat),
])
def test_saved_smt_lib_can_be_loaded_and_solved_again(version, pid, bound, expected):
    query = bmc.check_bound(build_model(version), pid, bound)
    solver = z3.Solver()
    solver.from_string(query["smt2"])
    assert solver.check() == expected
    assert query["solver_status"] == str(expected).upper()


@pytest.mark.parametrize("bound", [-1, True, 1.5])
def test_invalid_bound_is_error_without_solver_result(bound):
    result = bmc.check_bound(build_model("v1"), "P1", bound)
    assert result["status"] == "ERROR"
    assert result["solver_status"] is None and result["solver_called"] is False


def test_af_fixed_point_uses_all_successors_not_only_one_path(verified):
    model, explicit, _ = verified
    result = explicit["P5"]
    reached, history = ctl.af_idle_fixed_point(model)
    reset_ids = {sid for sid, state in model.states.items() if state.phase == "resetting"}
    assert all("s0" in model.graph.transitions[sid] for sid in reset_ids)
    if model.version == "v0":
        assert reached == {"s0"}
        assert result["holds"] is False  # Có đường hoàn tất vẫn chưa đủ cho AF.
    else:
        assert reached == {"s0"} | reset_ids
        assert [len(z) for z in history] == [1, 9]
    assert all(set(a) <= set(b) for a, b in zip(history, history[1:]))


def test_lasso_contains_valid_prefix_and_nonempty_closed_cycle():
    model = build_model("v0")
    trace = ctl.check_ctl(model)["P5"]["counterexample"]
    rows = trace["steps"]
    assert [row["state_id"] for row in rows] == ["s0", "s5", "s5"]
    assert trace["reset_step"] == trace["loop_start"] == 1
    assert rows[0]["labels"] == ["idle"]  # idle được phép xuất hiện trước reset.
    assert ctl.validate_counterexample(model, trace, "P5")
    assert replay_trace(model, trace)


@pytest.mark.parametrize("damage", ["state", "labels", "event", "violation_step", "property"])
def test_damaged_finite_counterexample_is_rejected(damage):
    model = build_model("v0")
    trace = deepcopy(ctl.check_ctl(model)["P1"]["counterexample"])
    if damage == "state":
        trace["steps"][1]["state"]["door_open"] = False
    elif damage == "labels":
        trace["steps"][1]["labels"] = []
    elif damage == "event":
        trace["steps"][1]["incoming_event"] = "password_ok"
    elif damage == "violation_step":
        trace["violation_step"] = 0
    else:
        trace["property"] = "P2"
    with pytest.raises(ValueError):
        ctl.validate_counterexample(model, trace, "P1")


@pytest.mark.parametrize("damage", ["admin", "loop", "reset", "kind"])
def test_damaged_lasso_is_rejected(damage):
    model = build_model("v0")
    trace = deepcopy(ctl.check_ctl(model)["P5"]["counterexample"])
    if damage == "admin":
        trace["steps"][1]["admin_authenticated"] = False
    elif damage == "loop":
        trace["loop_start"] = len(trace["steps"]) - 1
    elif damage == "reset":
        trace["reset_step"] = 0
    else:
        trace["kind"] = "finite"
    with pytest.raises(ValueError):
        ctl.validate_counterexample(model, trace, "P5")


def test_valid_path_without_a_violation_is_not_a_counterexample():
    model = build_model("v1")
    trace = make_trace(model, ["s0", "s1"], ["password_ok"], "P1")
    trace["violation_step"] = 1
    assert replay_trace(model, trace)
    with pytest.raises(ValueError):
        ctl.validate_counterexample(model, trace, "P1")


def test_lasso_that_completes_reset_is_not_a_p5_violation():
    model = build_model("v0")
    trace = make_trace(model, ["s0", "s5", "s0", "s5"],
                       ["admin_reset", "reset_complete", "admin_reset"], "P5")
    trace.update(kind="lasso", reset_step=1, loop_start=1)
    assert replay_trace(model, trace)
    with pytest.raises(ValueError, match="idle"):
        ctl.validate_counterexample(model, trace, "P5")


def test_p5_rejects_deadlock_instead_of_vacuous_all_successors():
    model = build_model("v1")
    model.graph.transitions["s4"].clear()
    with pytest.raises(ValueError, match="total"):
        ctl.af_idle_fixed_point(model)


def test_incomplete_g2_graph_cannot_produce_a_global_safety_claim():
    model = build_model("v1")
    model.transitions.pop()
    result = bmc.check_bound(model, "P1", 0)
    assert result["status"] == "ERROR" and result["solver_called"] is False
    with pytest.raises(ValueError):
        ctl.check_ctl(model)


def test_loading_g2_snapshot_detects_stale_or_tampered_labels(tmp_path):
    model = build_model("v1")
    path = tmp_path / "model.json"
    write_model(model, path)
    assert load_g2_model(path).to_dict() == model.to_dict()
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    snapshot["states"][0]["labels"] = []
    path.write_text(json.dumps(snapshot), encoding="utf-8")
    with pytest.raises(ValueError, match="Snapshot G2"):
        load_g2_model(path)


def test_verification_cli_preserves_g2_and_records_every_actual_query(tmp_path, capsys):
    before = {}
    for version in ("v0", "v1"):
        path = tmp_path / version / "model.json"
        write_model(build_model(version), path)
        before[version] = path.read_bytes()
    assert main(["--verify", "--output-dir", str(tmp_path)]) == 0
    reports = []
    for version in ("v0", "v1"):
        assert (tmp_path / version / "model.json").read_bytes() == before[version]
        reports.append(json.loads((tmp_path / version / "verification.json").read_text(encoding="utf-8")))
    assert sum(r["solver_calls"] for r in reports) == 44
    assert sum(r["solver_outcomes"]["SAT"] for r in reports) == 1
    assert sum(r["solver_outcomes"]["UNSAT"] for r in reports) == 43
    assert all(all(r["safety_methods_agree"].values()) for r in reports)
    assert (tmp_path / "comparison.csv").is_file()
    assert "Z3 not used" in capsys.readouterr().out
