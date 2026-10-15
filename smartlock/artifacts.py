"""G4 riêng cho Smart Lock: sinh Python từ bảng G2, đối chiếu và vẽ hình."""

from collections import defaultdict
import csv
from dataclasses import asdict, fields
import hashlib
import json
import os
from pathlib import Path
import runpy
import shutil
import struct
import subprocess
import sys
import textwrap
import xml.etree.ElementTree as ET

from .ctl import FORMULAS, validate_counterexample
from .kripke import SmartLockModel, load_g2_model
from .model import EVENTS, InvalidEvent, State, labels, step

STATE_FIELDS = tuple(field.name for field in fields(State))

# Chỉ là bộ tra bảng và CLI. Không sao chép guard/action của năm chức năng.
RUNTIME = '''

class InvalidEvent(ValueError):
    """Event bị từ chối; state của bên gọi không bị thay đổi."""


class InvalidState(ValueError):
    """State ID không thuộc mô hình reachable được nhúng."""


def state_values(state):
    if type(state) is not str or state not in STATES:
        raise InvalidState(f"Unknown state: {state!r}")
    return dict(zip(STATE_FIELDS, STATES[state]))


def step(state, event, *, admin_authenticated=False):
    if type(admin_authenticated) is not bool:
        raise ValueError("admin_authenticated must be bool")
    state_values(state)
    if type(event) is not str:
        raise InvalidEvent(f"Unknown event: {event!r}")
    required = EVENT_INPUTS.get(event, {})
    if required.get("admin_authenticated", False) and not admin_authenticated:
        raise InvalidEvent("Admin verification is required")
    try:
        return TRANSITIONS[(state, event)]
    except KeyError:
        raise InvalidEvent(f"Event {event!r} is not enabled at {state}") from None


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generated Smart Lock " + VERSION)
    parser.add_argument("--events", nargs="*", default=[])
    parser.add_argument("--admin-authenticated", action="store_true")
    args = parser.parse_args(argv)
    current = INITIAL_STATE
    print(f"step 0 {current}: " + json.dumps(state_values(current)))
    for index, event in enumerate(args.events, 1):
        try:
            current = step(current, event, admin_authenticated=args.admin_authenticated)
        except InvalidEvent as error:
            print(f"step {index}: REJECTED {error}")
            return 1
        print(f"step {index} --{event}--> {current}: " + json.dumps(state_values(current)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def generate_python(model_path: Path, destination: Path) -> None:
    """Chuyển states/labels/initial/event assumptions/transitions JSON thành literal Python."""
    data = json.loads(model_path.read_text(encoding="utf-8"))
    states = {row["id"]: tuple(row[name] for name in STATE_FIELDS) for row in data["states"]}
    if len(states) != len(data["states"]) or len(data["initial_states"]) != 1:
        raise ValueError("Smart Lock cần state ID duy nhất và đúng một initial")
    for values in states.values():
        State(**dict(zip(STATE_FIELDS, values)))  # Kiểm tra miền, không kiểm tra invariant.
    if data["initial_states"][0] not in states:
        raise ValueError("Initial không thuộc states")
    table = {}
    for edge in data["transitions"]:
        pair = edge["source"], edge["event"]
        target = edge["target"]
        if pair[0] not in states or target not in states or pair[1] not in EVENTS:
            raise ValueError(f"Cạnh có state/event không hợp lệ: {edge}")
        if pair in table and table[pair] != target:
            raise ValueError(f"Nondeterministic transition {pair}: {table[pair]} / {target}")
        table[pair] = target
    state_labels = {row["id"]: tuple(row["labels"]) for row in data["states"]}
    source = (
        '# Generated from G2 model.json. Do not edit; regenerate with run.py --artifacts.\n'
        'import argparse\nimport json\n\n'
        f'VERSION = {data["version"]!r}\n'
        f'SOURCE_MODEL_SHA256 = {hashlib.sha256(model_path.read_bytes()).hexdigest()!r}\n'
        f'STATE_FIELDS = {STATE_FIELDS!r}\nEVENTS = {EVENTS!r}\n'
        f'INITIAL_STATE = {data["initial_states"][0]!r}\n'
        f'EVENT_INPUTS = {data["event_assumptions"]!r}\n\n'
    )
    for name, mapping in (("STATES", states), ("LABELS", state_labels), ("TRANSITIONS", table)):
        source += name + ' = {\n' + ''.join(f'    {key!r}: {value!r},\n' for key, value in mapping.items()) + '}\n\n'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(source + RUNTIME, encoding="utf-8", newline="\n")


def audit_generated(model: SmartLockModel, program: Path) -> dict:
    """Đối chiếu mọi state × 9 event × hai kết quả quyền với guard/action G2."""
    runtime = runpy.run_path(str(program.resolve()), run_name="generated_smart_lock")
    if runtime["INITIAL_STATE"] not in model.graph.initial:
        raise ValueError("Generated initial không khớp G2")
    if set(runtime["STATES"]) != set(model.states) or tuple(runtime["EVENTS"]) != EVENTS:
        raise ValueError("Tập state/event của mã sinh không khớp G2")
    for sid, state in model.states.items():
        if (runtime["state_values"](sid) != asdict(state)
                or set(runtime["LABELS"][sid]) != labels(state)):
            raise ValueError(f"Dữ liệu/labels mã sinh không khớp tại {sid}")
    ids = {state: sid for sid, state in model.states.items()}
    expected_edges = {(e.source, e.event, e.target) for e in model.transitions}
    embedded_edges = {(source, event, target) for (source, event), target in runtime["TRANSITIONS"].items()}
    if embedded_edges != expected_edges:
        raise ValueError("Bảng nhúng có cạnh thiếu/thừa so với G2")
    matched = set()
    accepted = rejected = 0
    for sid, state in model.states.items():
        for event in EVENTS:
            for authorized in (False, True):
                try:
                    expected = ids[step(state, event, model.version, admin_authenticated=authorized)]
                except InvalidEvent:
                    expected = None
                try:
                    actual = runtime["step"](sid, event, admin_authenticated=authorized)
                except runtime["InvalidEvent"]:
                    actual = None
                if actual != expected:
                    raise ValueError(f"Mã sinh khác G2: {(sid, event, authorized)}: {actual} != {expected}")
                if expected is None:
                    rejected += 1
                else:
                    accepted += 1
                    matched.add((sid, event, actual))
    if matched != expected_edges:
        raise ValueError("Tập cạnh thực hiện của mã sinh không bằng toàn bộ cạnh G2")
    command = [sys.executable, "-I", "-S", str(program.resolve()), "--events", "password_ok", "open_door"]
    isolated = subprocess.run(command, cwd=program.parent, capture_output=True, text=True,
                              encoding="utf-8", timeout=15)
    if isolated.returncode != 0:
        raise ValueError(f"Chương trình sinh không chạy độc lập: {isolated.stderr}")
    return {
        "status": "PASS", "states_checked": len(model.states), "event_count": len(EVENTS),
        "admin_contexts": [False, True], "cases_checked": accepted + rejected,
        "accepted_cases": accepted, "rejected_cases": rejected,
        "distinct_edges_matched": len(matched), "initial_and_state_values_match": True,
        "generated_sha256": hashlib.sha256(program.read_bytes()).hexdigest(),
        "standalone_execution": {"command": command, "returncode": isolated.returncode,
                                 "stdout": isolated.stdout, "stderr": isolated.stderr},
    }


def _part(version: str, edges: list, state_ids: list[str] | None = None) -> dict:
    """Mỗi phần sơ đồ giữ nguyên ID và cạnh thật, chỉ chọn lát cắt để đọc."""
    records = [asdict(edge) if not isinstance(edge, dict) else edge for edge in edges]
    selected = set(state_ids or []) | {"s0"}
    for edge in records:
        selected.update((edge["source"], edge["target"]))
    return {"version": version, "state_ids": sorted(selected, key=lambda sid: int(sid[1:])),
            "edges": records}


def diagram_views(models: dict, reports: dict) -> list[dict]:
    """Hai graph đầy đủ, ba lát cắt chức năng và hai CE từ chính dữ liệu G2/G3."""
    views = []
    for version, model in models.items():
        stats = model.statistics()
        views.append({"name": f"kripke_{version}", "compact": True,
                      "title": f"Smart Lock {version}: full reachable Kripke",
                      "note": f"S={stats['states']}; event edges={stats['event_transitions']}; R pairs={stats['relation_pairs']}. Node values: state_legend.csv",
                      "parts": [_part(version, model.transitions, list(model.states))]})
    model = models["v1"]
    auth = [e for e in model.transitions if e.event in ("password_ok", "password_bad")]
    views.append({"name": "authentication_lockout", "title": "Authentication + Account Lockout (v1)",
                  "note": "Event slice from integrated G2 model; omitted events remain in full Kripke.",
                  "parts": [_part("v1", auth)]})
    door_ids = {sid for sid, s in model.states.items() if s.failed_attempts == 0 and s.phase == "normal"}
    door = [e for e in model.transitions if e.source in door_ids and e.target in door_ids
            and e.event in ("password_ok", "open_door", "close_door", "tamper")]
    views.append({"name": "door_alarm", "title": "Door Control + Alarm (v1)",
                  "note": "G2 slice: normal phase, failed_attempts=0; password_ok provides authentication context.",
                  "parts": [_part("v1", door)]})
    recovery = []
    for version, model in models.items():
        locked_alarm = next(sid for sid, s in model.states.items() if s.phase == "locked_out" and s.alarm)
        admin = next(e for e in model.transitions if e.source == locked_alarm and e.event == "admin_reset")
        edges = model.path_to(locked_alarm) + [admin] + [e for e in model.transitions if e.source == admin.target]
        recovery.append(_part(version, edges))
    views.append({"name": "admin_recovery", "title": "Admin Recovery: lockout + alarm example",
                  "note": "Two real G2 paths. admin_reset requires admin_authenticated=True. Red loop is BUG-02.",
                  "parts": recovery})
    for pid in ("P1", "P5"):
        trace = reports["v0"]["ctl"][pid]["counterexample"]
        validate_counterexample(models["v0"], trace, pid)
        rows = trace["steps"]
        edges = [{"source": a["state_id"], "event": b["incoming_event"], "target": b["state_id"],
                  "role": "cycle" if trace["kind"] == "lasso" and i >= trace["loop_start"] else "prefix"}
                 for i, (a, b) in enumerate(zip(rows, rows[1:]))]
        views.append({"name": f"counterexample_{pid.lower()}_v0", "title": f"Counterexample {pid} (v0)",
                      "note": "Red = violating edge." if pid == "P1" else
                      f"Blue = finite prefix; red = cycle repeated forever. reset_step={trace['reset_step']}, loop_start={trace['loop_start']}.",
                      "parts": [_part("v0", edges)]})
    return views


def dot_text(view: dict, models: dict, reports: dict) -> str:
    """DOT chỉ chứa cạnh đã trích; gộp event chung hai đầu để bớt dày hình."""
    quote = lambda value: json.dumps(value, ensure_ascii=False)
    compact = view.get("compact", False)
    heading = view["title"] + "\n" + textwrap.fill(view["note"], width=72)
    if not compact:
        heading += "\nA=authenticated D=door B=alarm U=admin"
    heading += "\nN=normal L=locked_out R=resetting; red=P1/P5 evidence"
    direction = "LR" if compact else "TB"
    lines = ['digraph SmartLock {',
             f'graph [rankdir={direction}, bgcolor="white", fontname="Arial", fontsize=15, labelloc=t, label={quote(heading)}, nodesep=0.45, ranksep=0.8, pad=0.2];',
             'node [shape=box, style="rounded,filled", fillcolor="white", color="#475569", fontname="Arial", fontsize=12];',
             'edge [fontname="Arial", fontsize=11, color="#64748b", arrowsize=0.7];']
    for part in view["parts"]:
        version = part["version"]
        model, report = models[version], reports[version]
        bad1 = set(report["ctl"]["P1"]["violating_states"])
        bad5 = set(report["ctl"]["P5"]["violating_states"])
        key = lambda sid: quote(version + "_" + sid)
        lines.append(f'subgraph cluster_{version} {{ label={quote(version)}; color="#cbd5e1";')
        for sid in part["state_ids"]:
            state = model.states[sid]
            phase = {"normal": "N", "locked_out": "L", "resetting": "R"}[state.phase]
            label = f"{sid}  {phase} f={state.failed_attempts}"
            if not compact:
                label += f"\nA={int(state.authenticated)} D={int(state.door_open)} B={int(state.alarm)} U={int(state.admin_authorized)}"
            bug = sid in bad1 or sid in bad5
            lines.append(f'{key(sid)} [label={quote(label)}, peripheries={2 if sid in model.graph.initial else 1}, '
                         f'color="{"#b91c1c" if bug else "#475569"}", fillcolor="{"#fff1f2" if bug else "white"}"];')
        lines += [f'start_{version} [shape=point, width=0.08, label=""];',
                  f'start_{version} -> {key("s0")} [label="initial", color="#334155"];']
        pairs = defaultdict(list)
        for edge in part["edges"]:
            pairs[edge["source"], edge["target"]].append(edge)
        for (source, target), edges in pairs.items():
            cycle = any(e.get("role") == "cycle" for e in edges)
            bug = (cycle or any(e["event"] == "open_door" and target in bad1 for e in edges)
                   or source == target and source in bad5 and any(e["event"] == "reset_retry" for e in edges))
            prefix = any(e.get("role") == "prefix" for e in edges) and not bug
            color = "#b91c1c" if bug else "#1d4ed8" if prefix else "#64748b"
            label = '\n'.join(e["event"] + (" [cycle]" if e.get("role") == "cycle" else "") for e in edges)
            font_color = color if bug or prefix else "#334155"
            lines.append(f'{key(source)} -> {key(target)} [label={quote(label)}, color="{color}", fontcolor="{font_color}", '
                         f'penwidth={2.2 if bug or prefix else 1}];')
        lines.append('}')
    return '\n'.join(lines + ['}']) + '\n'


def resolve_dot(explicit: Path | None = None) -> str:
    """Nhận dot chỉ định, PATH hoặc portable trong tmp; không tự cài toàn máy."""
    portable = sorted((Path(__file__).resolve().parents[1] / "tmp/graphviz").glob("*/bin/dot.exe"))
    candidate = explicit or os.environ.get("GRAPHVIZ_DOT") or shutil.which("dot") or (portable[0] if portable else None)
    if candidate is None or not Path(candidate).is_file():
        raise FileNotFoundError("Cần Graphviz dot: dùng --dot <đường_dẫn_dot> hoặc GRAPHVIZ_DOT/PATH")
    return str(Path(candidate).resolve())


def render_view(view: dict, models: dict, reports: dict, folder: Path, dot: str) -> dict:
    """Xuất DOT/SVG/PNG và kiểm tra SVG XML + header/kích thước PNG."""
    folder.mkdir(parents=True, exist_ok=True)
    base = folder / view["name"]
    source = base.with_suffix(".dot")
    source.write_text(dot_text(view, models, reports), encoding="utf-8", newline="\n")
    warnings = []
    for format_name in ("svg", "png"):
        result = subprocess.run([dot, f"-T{format_name}", "-Gdpi=120", str(source), "-o", str(base.with_suffix('.' + format_name))],
                                capture_output=True, text=True, encoding="utf-8", timeout=30, check=True)
        if result.stderr.strip():
            warnings.append(result.stderr.strip())
    root = ET.parse(base.with_suffix(".svg")).getroot()
    png = base.with_suffix(".png").read_bytes()
    if not root.tag.endswith("svg") or "viewBox" not in root.attrib or png[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError(f"Ảnh sơ đồ không hợp lệ: {base}")
    width, height = struct.unpack(">II", png[16:24])
    if not width or not height:
        raise ValueError("Ảnh PNG rỗng")
    return {**view, "svg": str(base.with_suffix('.svg')), "png": str(base.with_suffix('.png')),
            "dot": str(source), "png_size": [width, height], "render_warnings": warnings}


def build_artifacts(results_dir: Path, generated_dir: Path, dot_path: Path | None = None) -> dict:
    """G4: đọc kết quả thật G2/G3, sinh mã/ảnh và tổng hợp; không chạy lại BMC."""
    models, reports, snapshots = {}, {}, {}
    for version in ("v0", "v1"):
        path = results_dir / version / "model.json"
        models[version] = load_g2_model(path)
        report = json.loads(path.with_name("verification.json").read_text(encoding="utf-8"))
        source_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        if (models[version].version != version or report["version"] != version
                or report["source_model_sha256"] != source_hash
                or report["g2_statistics"] != models[version].statistics()
                or set(report["ctl"]) != set(FORMULAS)):
            raise ValueError(f"Kết quả G3 không khớp snapshot G2: {version}")
        for pid, result in report["ctl"].items():
            if result["formula"] != FORMULAS[pid]:
                raise ValueError("Công thức trong bằng chứng G3 không khớp")
            if result["counterexample"]:
                validate_counterexample(models[version], result["counterexample"], pid)
        reports[version] = report
        snapshots[version] = path
    dot = resolve_dot(dot_path)
    folder = results_dir / "g4"
    folder.mkdir(parents=True, exist_ok=True)
    versions, rows = {}, []
    for version, model in models.items():
        program = generated_dir / version / "smart_lock.py"
        generate_python(snapshots[version], program)
        audit = audit_generated(model, program)
        versions[version] = {"g2_statistics": model.statistics(), "g3_solver_outcomes": reports[version]["solver_outcomes"],
                             "source_model_sha256": reports[version]["source_model_sha256"],
                             "source_verification_sha256": hashlib.sha256(snapshots[version].with_name('verification.json').read_bytes()).hexdigest(),
                             "program": str(program), "generated_checks": audit}
        for pid, checked in reports[version]["ctl"].items():
            bounded = reports[version]["bmc"].get(pid)
            trace = checked["counterexample"]
            versions[version].setdefault("properties", {})[pid] = {
                "formula": checked["formula"], "method": checked["method"] + (" + bmc_z3" if bounded else ""),
                "ctl_status": checked["status"], "bmc_status": bounded["status"] if bounded else "NOT_APPLICABLE",
                "checked_bounds": bounded["checked_bounds"] if bounded else [], "counterexample": trace,
            }
            result = versions[version]["properties"][pid]
            trace_text = '' if trace is None else ' '.join(
                row['state_id'] if i == 0 else f"--{row['incoming_event']}--> {row['state_id']}"
                for i, row in enumerate(trace['steps']))
            if trace and trace["kind"] == "lasso":
                trace_text += f"; loop_start={trace['loop_start']}"
            rows.append({"version": version, "property": pid, "formula": result["formula"],
                         **model.statistics(), "method": result["method"], "ctl_status": result["ctl_status"],
                         "bmc_status": result["bmc_status"], "bounds": ';'.join(map(str, result["checked_bounds"])),
                         "counterexample": trace_text, "generated_audit": audit["status"],
                         "cases_checked": audit["cases_checked"], "distinct_edges_matched": audit["distinct_edges_matched"],
                         "accepted_cases": audit["accepted_cases"], "rejected_cases": audit["rejected_cases"]})
        print(f"{version}: generated {program}; audit {audit['status']}; cases={audit['cases_checked']}, "
              f"accepted={audit['accepted_cases']}, rejected={audit['rejected_cases']}, edges={audit['distinct_edges_matched']}")
    with (folder / "state_legend.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["version", "state_id", *STATE_FIELDS, "labels"])
        writer.writeheader()
        for version, model in models.items():
            writer.writerows({"version": version, "state_id": sid, **asdict(state), "labels": ';'.join(sorted(labels(state)))}
                             for sid, state in model.states.items())
    diagrams = [render_view(view, models, reports, folder / "diagrams", dot) for view in diagram_views(models, reports)]
    for diagram in diagrams:
        print(f"Diagram {diagram['name']}: SVG + PNG {diagram['png_size']}; warnings={len(diagram['render_warnings'])}")
    summary = {"stage": "G4", "versions": versions, "diagrams": diagrams,
               "graphviz_version": subprocess.run([dot, "-V"], capture_output=True, text=True, check=True).stderr.strip()}
    (folder / "experiment_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding="utf-8")
    with (folder / "experiment_summary.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print("G4 complete: G2/G3 evidence reused; no new CTL/BMC run or G5 PDF.")
    return summary
