"""BFS sinh Kripke từ guard/action, giữ tên sự kiện và xuất dữ liệu G2."""

from collections import deque
from dataclasses import asdict, dataclass
import importlib.util
import json
from pathlib import Path

from .model import INITIAL_STATE, VERSIONS, State, Version, labels, step, successors


def _load_toolkit():
    """Tái sử dụng lớp được cung cấp, không sửa hoặc sao chép toolkit."""
    path = (
        Path(__file__).resolve().parents[1]
        / "toolkit/softsec-toolkit/ch1_models/kripke.py"
    )
    spec = importlib.util.spec_from_file_location("softsec_kripke", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Không nạp được KripkeStructure từ {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.KripkeStructure


KripkeStructure = _load_toolkit()


@dataclass(frozen=True)
class Transition:
    source: str
    event: str
    target: str


@dataclass
class SmartLockModel:
    version: Version
    states: dict[str, State]
    graph: KripkeStructure
    transitions: list[Transition]
    distances: dict[str, int]
    parents: dict[str, Transition | None]

    def path_to(self, target: str) -> list[Transition]:
        """Đường đi BFS từ s0 để giải thích cách state được khám phá."""
        if target not in self.states:
            raise KeyError(target)
        path = []
        edge = self.parents[target]
        while edge is not None:
            path.append(edge)
            edge = self.parents[edge.source]
        return list(reversed(path))

    def statistics(self) -> dict[str, int]:
        return {
            "states": len(self.states),
            "reachable_states": len(self.graph.reachable_states()),
            "event_transitions": len(self.transitions),
            "relation_pairs": sum(len(targets) for targets in self.graph.transitions.values()),
            "max_bfs_depth": max(self.distances.values()),
        }

    def structural_checks(self) -> dict[str, bool]:
        """Kiểm tra dữ liệu đồ thị G2; chưa diễn giải CTL hoặc gọi solver."""
        ids = set(self.states)
        actual = set(self.transitions)
        expected = {
            (source, event, target)
            for source, state in self.states.items()
            for event, target in successors(state, self.version)
        }
        recorded = {
            (edge.source, edge.event, self.states[edge.target])
            for edge in self.transitions
        }
        relation = {
            (source, target)
            for source, targets in self.graph.transitions.items()
            for target in targets
        }
        return {
            "unique_state_values": len(set(self.states.values())) == len(ids),
            "initial_state_matches": self.graph.initial == {"s0"}
            and self.states["s0"] == INITIAL_STATE,
            "toolkit_states_match": self.graph.states == ids,
            "all_states_reachable": self.graph.reachable_states() == ids,
            "total_relation": all(self.graph.transitions.get(sid) for sid in ids),
            "labels_match_values": set(self.graph.labels) == ids and all(
                self.graph.labels[sid] == labels(state)
                for sid, state in self.states.items()
            ),
            "unique_event_transitions": len(actual) == len(self.transitions),
            "deterministic_per_event": len({
                (edge.source, edge.event) for edge in self.transitions
            }) == len(self.transitions),
            "guards_and_actions_match": recorded == expected,
            "relation_matches_event_edges": relation == {
                (edge.source, edge.target) for edge in self.transitions
            },
            "bfs_paths_match_depths": all(
                len(self.path_to(sid)) == self.distances[sid] for sid in ids
            ),
        }

    def basic_invariants(self) -> dict[str, dict]:
        """Bốn kiểm tra nhất quán dữ liệu; không lọc state khi sinh BFS."""
        violations = {
            "failed_attempts_in_range": [sid for sid, s in self.states.items()
                                         if not 0 <= s.failed_attempts <= 3],
            "locked_out_has_three_failures": [sid for sid, s in self.states.items()
                                               if s.phase == "locked_out" and s.failed_attempts != 3],
            "alarm_keeps_door_closed": [sid for sid, s in self.states.items()
                                         if s.alarm and s.door_open],
            "reset_has_admin_authorization": [sid for sid, s in self.states.items()
                                               if s.phase == "resetting" and not s.admin_authorized],
        }
        return {
            name: {"holds": not states, "violating_states": states}
            for name, states in violations.items()
        }

    def to_dict(self) -> dict:
        """Toàn bộ S, S0, R, L cùng cạnh có event và số liệu thực tế."""
        return {
            "stage": "G2",
            "version": self.version,
            "initial_states": ["s0"],
            "event_assumptions": {"admin_reset": {"admin_authenticated": True}},
            "statistics": self.statistics(),
            "structural_checks": self.structural_checks(),
            "basic_invariants": self.basic_invariants(),
            "states": [
                {"id": sid, **asdict(state), "labels": sorted(labels(state)),
                 "bfs_depth": self.distances[sid]}
                for sid, state in self.states.items()
            ],
            "transitions": [asdict(edge) for edge in self.transitions],
            "relation": [
                {"source": source, "target": target}
                for source in self.states
                for target in sorted(self.graph.transitions[source], key=lambda sid: int(sid[1:]))
            ],
        }


def build_model(version: Version = "v1") -> SmartLockModel:
    """BFS thực sự sinh state từ initial + sự kiện + guard/action.

    Không có danh sách states/đồ thị đầu vào hoặc bộ lọc invariant.
    Hash/equality của State (đủ sáu biến) là khóa nhận diện trùng lặp.
    """
    if version not in VERSIONS:
        raise ValueError(f"Phiên bản không hợp lệ: {version}")
    graph = KripkeStructure()
    graph.add_state("s0", labels=labels(INITIAL_STATE), initial=True)
    states = {"s0": INITIAL_STATE}
    state_ids = {INITIAL_STATE: "s0"}
    distances = {"s0": 0}
    parents = {"s0": None}
    transitions = []
    queue = deque([INITIAL_STATE])

    while queue:
        current = queue.popleft()
        source = state_ids[current]
        for event, next_state in successors(current, version):
            if next_state not in state_ids:
                target = f"s{len(states)}"
                state_ids[next_state] = target
                states[target] = next_state
                graph.add_state(target, labels=labels(next_state))
                distances[target] = distances[source] + 1
                parents[target] = Transition(source, event, target)
                queue.append(next_state)
            target = state_ids[next_state]
            transitions.append(Transition(source, event, target))
            graph.add_transition(source, target)

    return SmartLockModel(version, states, graph, transitions, distances, parents)


def write_model(model: SmartLockModel, path: Path) -> None:
    """Lưu JSON đọc được bằng editor và dùng làm bằng chứng G2."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(model.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_g2_model(path: Path) -> SmartLockModel:
    """Dùng chính BFS G2 và yêu cầu khớp toàn bộ snapshot G2 trước G3.

    Không có bộ state/transition riêng dành cho bộ kiểm chứng.
    Snapshot sai hoặc cũ phải báo lỗi thay vì bị ghi đè âm thầm.
    """
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    model = build_model(snapshot["version"])
    if snapshot != model.to_dict():
        raise ValueError(f"Snapshot G2 không khớp guard/action/BFS hiện tại: {path}")
    return model


def make_trace(model: SmartLockModel, state_ids: list[str], events: list[str], property_id: str) -> dict:
    """Ghép ID và event thành đường đi có đầy đủ sáu giá trị của từng state."""
    if not state_ids or len(events) + 1 != len(state_ids):
        raise ValueError("Đường đi cần n+1 states và n events")
    return {
        "property": property_id,
        "kind": "finite",
        "steps": [
            {"step": i, "state_id": sid, "state": asdict(model.states[sid]),
             "labels": sorted(labels(model.states[sid])),
             "incoming_event": events[i - 1] if i else None,
             "admin_authenticated": bool(i and events[i - 1] == "admin_reset")}
            for i, sid in enumerate(state_ids)
        ],
    }


def replay_trace(model: SmartLockModel, trace: dict) -> bool:
    """Replay từng bước bằng guard/action G2, kể cả bằng chứng quyền admin.

    Chỉ kiểm tra đường đi; điều kiện vi phạm và chu trình P5 do ctl.py kiểm tra.
    Ném ValueError nếu dữ liệu không khớp; không sửa đường đi để làm nó hợp lệ.
    """
    rows = trace["steps"]
    if not rows or rows[0]["state_id"] not in model.graph.initial:
        raise ValueError("Trace không bắt đầu từ initial")
    if rows[0]["incoming_event"] is not None or rows[0]["admin_authenticated"] is not False:
        raise ValueError("Bước initial không có sự kiện đầu vào")
    edges = set(model.transitions)
    for i, row in enumerate(rows):
        state = model.states[row["state_id"]]
        if (row["step"] != i or row["state"] != asdict(state)
                or row["labels"] != sorted(labels(state))):
            raise ValueError(f"Dữ liệu state/label sai tại bước {i}")
        if i == 0:
            if state != INITIAL_STATE:
                raise ValueError("Giá trị initial sai")
            continue
        previous = rows[i - 1]
        event = row["incoming_event"]
        authorized = row["admin_authenticated"]
        if type(authorized) is not bool or authorized != (event == "admin_reset"):
            raise ValueError(f"Điều kiện xác thực admin sai tại bước {i}")
        edge = Transition(previous["state_id"], event, row["state_id"])
        if edge not in edges:
            raise ValueError(f"Cạnh không tồn tại trong Kripke tại bước {i}")
        actual = step(model.states[previous["state_id"]], event, model.version,
                      admin_authenticated=authorized)
        if actual != state:
            raise ValueError(f"Action không khớp state đích tại bước {i}")
    return True
