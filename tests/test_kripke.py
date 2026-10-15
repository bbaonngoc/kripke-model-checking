"""Kiểm tra BFS, dữ liệu S/S0/R/L và tích hợp lớp KripkeStructure có sẵn."""

import json

import pytest

from run import main
import smartlock.kripke as kripke
from smartlock.model import INITIAL_STATE, VERSIONS, State, labels, step, successors


@pytest.fixture(scope="module", params=VERSIONS)
def model(request):
    return kripke.build_model(request.param)


def test_bfs_has_unique_states_and_only_reachable_states(model):
    assert model.graph.initial == {"s0"}
    assert model.states["s0"] == INITIAL_STATE
    assert len(model.states) == len(set(model.states.values()))
    assert model.graph.reachable_states() == set(model.states)
    assert 0 < len(model.states) < 192
    # Hợp lệ về miền nhưng không thể sinh từ logic của cả hai phiên bản.
    assert State(failed_attempts=3, phase="normal") not in model.states.values()


def test_bfs_really_expands_each_discovered_state_once(monkeypatch):
    expanded = []
    original = kripke.successors

    def observed_successors(state, version):
        expanded.append(state)
        yield from original(state, version)

    monkeypatch.setattr(kripke, "successors", observed_successors)
    generated = kripke.build_model("v1")
    assert expanded == list(generated.states.values())
    assert len(expanded) == len(set(expanded))
    assert expanded[0] == INITIAL_STATE


def test_every_enabled_transition_is_recorded_and_actions_match(model):
    for sid, state in model.states.items():
        outgoing = [edge for edge in model.transitions if edge.source == sid]
        assert outgoing  # Quan hệ total, không chèn cạnh giả sau BFS.
        assert {(edge.event, model.states[edge.target]) for edge in outgoing} == set(
            successors(state, model.version)
        )
        for edge in outgoing:
            assert step(state, edge.event, model.version,
                        admin_authenticated=(edge.event == "admin_reset")) == model.states[edge.target]


def test_labels_are_exactly_computed_from_all_six_values(model):
    for sid, state in model.states.items():
        assert model.graph.labels[sid] == labels(state)
    for proposition in ("door_open", "locked_out", "alarm", "resetting"):
        assert model.graph.states_with_label(proposition)


def test_bfs_paths_and_distances_match_independent_toolkit_paths(model):
    for sid in model.states:
        path = model.path_to(sid)
        assert len(path) == model.distances[sid]
        assert len(model.graph.find_path(sid)) - 1 == model.distances[sid]
        current = "s0"
        for edge in path:
            assert edge.source == current
            assert edge in model.transitions
            current = edge.target
        assert current == sid
    with pytest.raises(KeyError):
        model.path_to("missing")


def test_parallel_events_are_kept_even_when_relation_pair_is_the_same(model):
    alarm_id = next(sid for sid, s in model.states.items() if s.alarm and s.phase != "resetting")
    loops = {edge.event for edge in model.transitions
             if edge.source == alarm_id and edge.target == alarm_id}
    assert {"wait", "tamper"} <= loops
    stats = model.statistics()
    assert stats["event_transitions"] > stats["relation_pairs"]
    assert stats["relation_pairs"] == len({(e.source, e.target) for e in model.transitions})


def test_v1_resetting_has_no_self_loop():
    model = kripke.build_model("v1")
    for sid, state in model.states.items():
        if state.phase == "resetting":
            assert model.graph.transitions[sid] == {"s0"}
            assert [(e.event, e.target) for e in model.transitions if e.source == sid] == [
                ("reset_complete", "s0"),
            ]
    assert all(not s.door_open or s.authenticated for s in model.states.values())


def test_v0_preserves_both_intentional_faults_in_reachable_graph():
    model = kripke.build_model("v0")
    assert any(s.door_open and not s.authenticated for s in model.states.values())
    resetting_ids = {sid for sid, s in model.states.items() if s.phase == "resetting"}
    retry_ids = {e.source for e in model.transitions
                 if e.event == "reset_retry" and e.source == e.target}
    assert retry_ids == resetting_ids
    assert resetting_ids  # Không chấp nhận kiểm tra đúng rỗng.


def test_versions_only_change_the_two_approved_rules():
    v0, v1 = kripke.build_model("v0"), kripke.build_model("v1")
    for state in set(v0.states.values()) & set(v1.states.values()):
        before = dict(successors(state, "v0"))
        after = dict(successors(state, "v1"))
        assert set(after) <= set(before)
        assert set(before) - set(after) <= {"open_door", "reset_retry"}
        assert all(before[event] == target for event, target in after.items())


def test_structural_checks_and_basic_data_invariants(model):
    assert all(model.structural_checks().values())
    for check in model.basic_invariants().values():
        assert check["holds"]
        assert check["violating_states"] == []


def test_bfs_ids_and_exports_are_reproducible(model):
    assert kripke.build_model(model.version).to_dict() == model.to_dict()


def test_json_export_contains_complete_states_labels_events_and_relation(model, tmp_path):
    path = tmp_path / model.version / "model.json"
    kripke.write_model(model, path)
    exported = json.loads(path.read_text(encoding="utf-8"))
    assert exported["initial_states"] == ["s0"]
    assert exported["stage"] == "G2"
    assert exported["event_assumptions"]["admin_reset"]["admin_authenticated"] is True
    assert len(exported["states"]) == len(model.states)
    assert len(exported["transitions"]) == len(model.transitions)
    assert len(exported["relation"]) == model.statistics()["relation_pairs"]
    assert exported == model.to_dict()


def test_invalid_model_version_is_rejected():
    with pytest.raises(ValueError, match="Phiên bản"):
        kripke.build_model("v2")


def test_cli_exports_both_models_and_runs_no_verifier(tmp_path, capsys):
    assert main(["--output-dir", str(tmp_path)]) == 0
    assert (tmp_path / "v0/model.json").is_file()
    assert (tmp_path / "v1/model.json").is_file()
    assert "no CTL/BMC verification" in capsys.readouterr().out


def test_cli_can_simulate_a_valid_door_sequence(tmp_path, capsys):
    assert main(["--version", "v1", "--output-dir", str(tmp_path),
                 "--events", "password_ok", "open_door"]) == 0
    output = capsys.readouterr().out
    assert 'step 2 --open_door-->' in output
    assert '"door_open": true' in output


def test_cli_requires_explicit_admin_authentication(tmp_path, capsys):
    args = ["--version", "v1", "--output-dir", str(tmp_path),
            "--events", "admin_reset", "reset_complete"]
    assert main(args) == 1
    assert "REJECTED" in capsys.readouterr().out
    assert main(args + ["--admin-authenticated"]) == 0
    assert 'step 2 --reset_complete-->' in capsys.readouterr().out
