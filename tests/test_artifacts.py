"""G4: đối chiếu toàn miền hữu hạn, thực thi cô lập và kiểm tra sơ đồ thật."""

import ast
import csv
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import runpy
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest

from run import main
from smartlock.artifacts import audit_generated, build_artifacts, generate_python
from smartlock.kripke import load_g2_model
from smartlock.model import EVENTS

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def outputs(tmp_path_factory):
    base = tmp_path_factory.mktemp("g4")
    results, generated = base / "results", base / "generated"
    before = {}
    for version in ("v0", "v1"):
        folder = results / version
        folder.mkdir(parents=True)
        for name in ("model.json", "verification.json"):
            contents = (ROOT / "results" / version / name).read_bytes()
            (folder / name).write_bytes(contents)
            before[version, name] = contents
    summary = build_artifacts(results, generated)
    return results, generated, summary, before


@pytest.fixture(params=("v0", "v1"))
def generated(outputs, request):
    results, folder, summary, _ = outputs
    version = request.param
    program = folder / version / "smart_lock.py"
    namespace = runpy.run_path(str(program), run_name="generated_test")
    return load_g2_model(results / version / "model.json"), program, namespace, summary["versions"][version]


def follow(runtime, events, *, admin=False):
    current = runtime["INITIAL_STATE"]
    for event in events:
        current = runtime["step"](current, event, admin_authenticated=admin)
    return current


def test_generated_initial_values_labels_and_source_hash_match_g2(generated, outputs):
    model, program, runtime, _ = generated
    assert runtime["INITIAL_STATE"] == "s0"
    assert runtime["state_values"]("s0") == asdict(model.states["s0"])
    assert runtime["SOURCE_MODEL_SHA256"] == hashlib.sha256((outputs[0] / model.version / "model.json").read_bytes()).hexdigest()
    assert len(runtime["STATE_FIELDS"]) == 6
    assert set(runtime["STATES"]) == set(model.states)
    assert program.is_file()


def test_exhaustive_states_events_admin_contexts_match_guard_actions_and_all_edges(generated):
    model, program, _, record = generated
    audit = audit_generated(model, program)
    assert audit["status"] == "PASS"
    assert audit["cases_checked"] == len(model.states) * len(EVENTS) * 2
    assert audit["accepted_cases"] + audit["rejected_cases"] == audit["cases_checked"]
    assert audit["distinct_edges_matched"] == len(model.transitions)
    assert audit["generated_sha256"] == record["generated_checks"]["generated_sha256"]


def test_generated_source_only_imports_standard_library_and_no_business_rules(generated):
    _, program, _, _ = generated
    tree = ast.parse(program.read_text(encoding="utf-8"))
    imports = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    assert imports == {"argparse", "json"}
    assert not any(isinstance(node, ast.ImportFrom) for node in ast.walk(tree))


def test_generated_file_runs_alone_with_isolated_python_and_no_site_packages(generated, tmp_path):
    _, program, _, _ = generated
    copied = tmp_path / "smart_lock.py"
    copied.write_bytes(program.read_bytes())
    result = subprocess.run([sys.executable, "-I", "-S", str(copied), "--events", "password_ok", "open_door"],
                            cwd=tmp_path, capture_output=True, text=True, encoding="utf-8", timeout=15)
    assert result.returncode == 0, result.stderr
    assert '"door_open": true' in result.stdout
    assert 'step 2 --open_door-->' in result.stdout
    assert list(tmp_path.iterdir()) == [copied]


@pytest.mark.parametrize("event", ["unknown", "", "__reset__"])
def test_generated_unknown_events_are_explicitly_rejected(generated, event):
    _, _, runtime, _ = generated
    with pytest.raises(runtime["InvalidEvent"]):
        runtime["step"]("s0", event)


@pytest.mark.parametrize("state", ["s999", None, []])
def test_generated_invalid_state_is_explicitly_rejected(generated, state):
    _, _, runtime, _ = generated
    with pytest.raises(runtime["InvalidState"]):
        runtime["step"](state, "password_ok")


@pytest.mark.parametrize("value", [1, "yes", None])
def test_generated_admin_input_is_strict_boolean(generated, value):
    _, _, runtime, _ = generated
    with pytest.raises(ValueError):
        runtime["step"]("s0", "admin_reset", admin_authenticated=value)


def test_generated_password_success_clears_consecutive_failures(generated):
    _, _, runtime, _ = generated
    current = follow(runtime, ["password_bad", "password_bad", "password_ok", "open_door", "close_door", "password_bad"])
    values = runtime["state_values"](current)
    assert values["failed_attempts"] == 1 and values["phase"] == "normal"


def test_generated_third_bad_password_locks_and_blocks_login(generated):
    _, _, runtime, _ = generated
    state = "s0"
    for number in (1, 2, 3):
        state = runtime["step"](state, "password_bad")
        values = runtime["state_values"](state)
        assert values["failed_attempts"] == number
        assert values["phase"] == ("locked_out" if number == 3 else "normal")
    for event in ("password_ok", "password_bad", "open_door"):
        with pytest.raises(runtime["InvalidEvent"]):
            runtime["step"](state, event)


def test_generated_door_alarm_and_authorized_recovery(generated):
    _, _, runtime, _ = generated
    alarmed = follow(runtime, ["password_ok", "open_door", "tamper"])
    values = runtime["state_values"](alarmed)
    assert values["alarm"] and not values["door_open"] and not values["authenticated"]
    with pytest.raises(runtime["InvalidEvent"]):
        runtime["step"](alarmed, "open_door")
    with pytest.raises(runtime["InvalidEvent"]):
        runtime["step"](alarmed, "admin_reset")
    resetting = runtime["step"](alarmed, "admin_reset", admin_authenticated=True)
    assert runtime["state_values"](resetting)["admin_authorized"] is True
    assert runtime["step"](resetting, "reset_complete") == "s0"


def test_generated_user_authentication_does_not_grant_admin_rights(generated):
    _, _, runtime, _ = generated
    authed = runtime["step"]("s0", "password_ok")
    with pytest.raises(runtime["InvalidEvent"]):
        runtime["step"](authed, "admin_reset", admin_authenticated=False)


def test_every_bfs_path_is_reproduced_step_by_step_by_generated_program(generated):
    model, _, runtime, _ = generated
    for target in model.states:
        current = runtime["INITIAL_STATE"]
        for edge in model.path_to(target):
            current = runtime["step"](current, edge.event, admin_authenticated=edge.event == "admin_reset")
            assert current == edge.target
            assert runtime["state_values"](current) == asdict(model.states[edge.target])
        assert current == target


def test_generated_v0_replays_both_g3_faults_and_v1_prevents_them(generated, outputs):
    model, _, runtime, _ = generated
    if model.version == "v0":
        report = json.loads((outputs[0] / "v0/verification.json").read_text(encoding="utf-8"))
        for pid in ("P1", "P5"):
            current = "s0"
            rows = report["ctl"][pid]["counterexample"]["steps"]
            for row in rows[1:]:
                current = runtime["step"](current, row["incoming_event"], admin_authenticated=row["admin_authenticated"])
                assert current == row["state_id"]
                assert runtime["state_values"](current) == row["state"]
        assert runtime["step"](current, "reset_retry") == current
    else:
        with pytest.raises(runtime["InvalidEvent"]):
            runtime["step"]("s0", "open_door")
        for sid, state in model.states.items():
            if state.phase == "resetting":
                assert [event for (source, event) in runtime["TRANSITIONS"] if source == sid] == ["reset_complete"]
                with pytest.raises(runtime["InvalidEvent"]):
                    runtime["step"](sid, "reset_retry")
                with pytest.raises(runtime["InvalidEvent"]):
                    runtime["step"](sid, "wait")
                assert runtime["step"](sid, "reset_complete") == "s0"


def test_generator_detects_nondeterminism_before_writing_any_program(tmp_path):
    data = json.loads((ROOT / "results/v1/model.json").read_text(encoding="utf-8"))
    edge = data["transitions"][0]
    data["transitions"].append({**edge, "target": "s0"})
    path, destination = tmp_path / "model.json", tmp_path / "smart_lock.py"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="Nondeterministic"):
        generate_python(path, destination)
    assert not destination.exists()


def test_generator_rejects_edges_with_missing_target(tmp_path):
    data = json.loads((ROOT / "results/v1/model.json").read_text(encoding="utf-8"))
    data["transitions"][0]["target"] = "s999"
    path = tmp_path / "model.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        generate_python(path, tmp_path / "program.py")


def test_generated_bytes_are_reproducible_from_same_snapshot(generated, outputs, tmp_path):
    model, original, _, _ = generated
    destination = tmp_path / "again.py"
    generate_python(outputs[0] / model.version / "model.json", destination)
    assert destination.read_bytes() == original.read_bytes()


def test_audit_detects_extra_hidden_transition_even_outside_known_event_domain(generated, tmp_path):
    model, original, _, _ = generated
    modified = tmp_path / "modified.py"
    modified.write_text(original.read_text(encoding="utf-8") + '\nTRANSITIONS[("s0", "backdoor")] = "s0"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="nhúng"):
        audit_generated(model, modified)


def test_all_seven_views_use_real_integrated_states_and_edges(outputs):
    results, _, summary, _ = outputs
    assert {view["name"] for view in summary["diagrams"]} == {
        "kripke_v0", "kripke_v1", "authentication_lockout", "door_alarm", "admin_recovery",
        "counterexample_p1_v0", "counterexample_p5_v0",
    }
    for view in summary["diagrams"]:
        for part in view["parts"]:
            model = load_g2_model(results / part["version"] / "model.json")
            assert set(part["state_ids"]) <= set(model.states)
            assert "s0" in part["state_ids"]
            actual = {(e.source, e.event, e.target) for e in model.transitions}
            assert {(e["source"], e["event"], e["target"]) for e in part["edges"]} <= actual
            if view["name"].startswith("kripke_"):
                assert set(part["state_ids"]) == set(model.states)
                assert len(part["edges"]) == len(model.transitions)


def test_all_svg_nodes_and_event_labels_and_png_images_are_valid(outputs):
    for view in outputs[2]["diagrams"]:
        root = ET.parse(view["svg"]).getroot()
        nodes = {group.find("{http://www.w3.org/2000/svg}title").text
                 for group in root.iter("{http://www.w3.org/2000/svg}g") if group.attrib.get("class") == "node"}
        for part in view["parts"]:
            assert {part["version"] + '_' + sid for sid in part["state_ids"]} <= nodes
            assert 'start_' + part["version"] in nodes
        text = ' '.join(root.itertext())
        assert all(edge["event"] in text for part in view["parts"] for edge in part["edges"])
        png = Path(view["png"]).read_bytes()
        assert png[:8] == b'\x89PNG\r\n\x1a\n'
        assert list(struct.unpack(">II", png[16:24])) == view["png_size"]
        assert view["render_warnings"] == []


def test_p5_diagram_preserves_prefix_and_cycle_roles(outputs):
    view = next(v for v in outputs[2]["diagrams"] if v["name"] == "counterexample_p5_v0")
    edges = view["parts"][0]["edges"]
    assert [e["event"] for e in edges if e["role"] == "prefix"] == ["admin_reset"]
    cycle = [e for e in edges if e["role"] == "cycle"]
    assert len(cycle) == 1 and cycle[0]["source"] == cycle[0]["target"]
    assert cycle[0]["event"] == "reset_retry"


def test_summary_uses_existing_g2_g3_results_and_measured_generated_checks(outputs):
    results, _, summary, before = outputs
    with (results / "g4/experiment_summary.csv").open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 10
    for version, entry in summary["versions"].items():
        source = json.loads(before[version, "verification.json"].decode("utf-8"))
        assert entry["g2_statistics"] == source["g2_statistics"]
        assert entry["g3_solver_outcomes"] == source["solver_outcomes"]
        assert all(entry["properties"][pid]["ctl_status"] == result["status"] for pid, result in source["ctl"].items())
        for name in ("model.json", "verification.json"):
            assert (results / version / name).read_bytes() == before[version, name]
        for row in [row for row in rows if row["version"] == version]:
            assert int(row["cases_checked"]) == entry["generated_checks"]["cases_checked"]
            assert int(row["event_transitions"]) == source["g2_statistics"]["event_transitions"]


def test_cli_artifacts_keeps_stage_flags_explicit():
    with pytest.raises(SystemExit):
        main(["--artifacts", "--verify"])
    with pytest.raises(SystemExit):
        main(["--artifacts", "--version", "v1"])
