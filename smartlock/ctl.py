"""Đúng năm CTL của Smart Lock: bốn invariants và một AF fixed-point.

Các chuỗi công thức chỉ để trình bày, không được đưa vào parser tổng quát.
"""

from collections import deque

from .kripke import SmartLockModel, make_trace, replay_trace
from .model import State, labels

FORMULAS = {
    "P1": "AG(door_open -> (authenticated AND NOT locked_out))",
    "P2": "AG(locked_out -> attempts_eq_3)",
    "P3": "AG(alarm -> NOT door_open)",
    "P4": "AG(resetting -> admin_authorized)",
    "P5": "AG(resetting -> AF idle)",
}
MEANINGS = {
    "P1": "Cửa mở phải có xác thực và không bị lockout.",
    "P2": "Khi lockout, bộ đếm sai phải bằng 3.",
    "P3": "Khi có báo động, cửa phải đóng.",
    "P4": "Khi đang reset, phải có quyền admin đã xác thực.",
    "P5": "Mọi reset đã bắt đầu đều phải về idle trên mọi đường tiếp diễn.",
}
ANTECEDENTS = {"P1": "door_open", "P2": "locked_out", "P3": "alarm",
               "P4": "resetting", "P5": "resetting"}
SAFETY_PROPERTIES = ("P1", "P2", "P3", "P4")


def bad_state(state: State, property_id: str) -> bool:
    """Phủ định mệnh đề trạng thái của riêng P1–P4, đọc AP từ State."""
    ap = labels(state)
    bad = {
        "P1": "door_open" in ap and ("authenticated" not in ap or "locked_out" in ap),
        "P2": "locked_out" in ap and "attempts_eq_3" not in ap,
        "P3": "alarm" in ap and "door_open" in ap,
        "P4": "resetting" in ap and "admin_authorized" not in ap,
    }
    if property_id not in bad:
        raise ValueError("bad_state chỉ áp dụng P1–P4, không áp dụng P5")
    return bad[property_id]


def reachable_depths(model: SmartLockModel) -> dict[str, int]:
    """Tính lại khoảng cách ngắn nhất trên R; không tin số depth ghi sẵn."""
    depths = {sid: 0 for sid in model.graph.initial}
    queue = deque(depths)
    while queue:
        source = queue.popleft()
        for target in model.graph.transitions[source]:
            if target not in depths:
                depths[target] = depths[source] + 1
                queue.append(target)
    return depths


def validate_model(model: SmartLockModel) -> None:
    """Kiểm tra mô hình đầy đủ/total trước khi kết luận trên toàn đồ thị."""
    failed = [name for name, ok in model.structural_checks().items() if not ok]
    if failed:
        raise ValueError(f"Cấu trúc Kripke không hợp lệ: {failed}")
    if reachable_depths(model) != model.distances:
        raise ValueError("Độ sâu BFS không đúng khoảng cách ngắn nhất")


def validate_counterexample(model: SmartLockModel, trace: dict, property_id: str) -> bool:
    """Replay đường đi rồi kiểm tra bằng chứng vi phạm đúng thuộc tính."""
    if trace["property"] != property_id:
        raise ValueError("Counterexample sai ID thuộc tính")
    replay_trace(model, trace)
    rows = trace["steps"]
    if property_id in SAFETY_PROPERTIES:
        violations = [i for i, row in enumerate(rows)
                      if bad_state(model.states[row["state_id"]], property_id)]
        if (trace["kind"] != "finite" or not violations
                or trace.get("violation_step") != violations[0]):
            raise ValueError("Trace không có bước vi phạm safety được khai báo")
    elif property_id == "P5":
        loop = trace.get("loop_start")
        reset = trace.get("reset_step")
        if (trace["kind"] != "lasso" or type(loop) is not int or type(reset) is not int
                or not 0 <= reset <= loop < len(rows) - 1):
            raise ValueError("Lasso cần prefix, chu trình không rỗng và reset_step hợp lệ")
        if rows[-1]["state_id"] != rows[loop]["state_id"]:
            raise ValueError("Chu trình không khép kín")
        if "resetting" not in rows[reset]["labels"]:
            raise ValueError("Điểm vi phạm không ở resetting")
        if any("idle" in row["labels"] for row in rows[reset:]):
            raise ValueError("Lasso đi qua idle sau reset, không chứng minh P5 sai")
    else:
        raise ValueError("Chỉ hỗ trợ P1–P5")
    return True


def af_idle_fixed_point(model: SmartLockModel) -> tuple[set[str], list[list[str]]]:
    """μZ.(idle ∪ AX Z), trên quan hệ total; trả tập AF idle và các vòng lặp."""
    if any(not model.graph.transitions.get(sid) for sid in model.states):
        raise ValueError("AF yêu cầu Kripke total, không chấp nhận deadlock")
    order = list(model.states)
    reached = {sid for sid, state in model.states.items() if "idle" in labels(state)}
    history = [[sid for sid in order if sid in reached]]
    while True:
        expanded = reached | {
            sid for sid in order if model.graph.transitions[sid] <= reached
        }
        if expanded == reached:
            return reached, history
        reached = expanded
        history.append([sid for sid in order if sid in reached])


def _prefix_trace(model: SmartLockModel, target: str, property_id: str) -> dict:
    path = model.path_to(target)
    return make_trace(model, ["s0"] + [edge.target for edge in path],
                      [edge.event for edge in path], property_id)


def _liveness_trace(model: SmartLockModel, target: str, af_idle: set[str]) -> dict:
    """Từ resetting ngoài AF idle, theo cạnh ngoài AF cho tới khi lặp state."""
    prefix = model.path_to(target)
    ids = ["s0"] + [edge.target for edge in prefix]
    events = [edge.event for edge in prefix]
    seen = {target: len(ids) - 1}
    current = target
    while True:
        edge = next(edge for edge in model.transitions
                    if edge.source == current and edge.target not in af_idle)
        ids.append(edge.target)
        events.append(edge.event)
        if edge.target in seen:
            loop_start = seen[edge.target]
            break
        seen[edge.target] = len(ids) - 1
        current = edge.target
    trace = make_trace(model, ids, events, "P5")
    trace.update(kind="lasso", reset_step=len(prefix), loop_start=loop_start)
    validate_counterexample(model, trace, "P5")
    return trace


def check_ctl(model: SmartLockModel) -> dict[str, dict]:
    """Kiểm chứng đầy đủ đúng năm công thức trên mô hình G2 hữu hạn."""
    validate_model(model)
    results = {}
    for property_id in SAFETY_PROPERTIES:
        bad_ids = [sid for sid, state in model.states.items() if bad_state(state, property_id)]
        trace = None
        if bad_ids:
            target = min(bad_ids, key=lambda sid: model.distances[sid])
            trace = _prefix_trace(model, target, property_id)
            trace["violation_step"] = len(trace["steps"]) - 1
            validate_counterexample(model, trace, property_id)
        results[property_id] = {
            "method": "explicit_reachable_states", "holds": not bad_ids,
            "status": "VIOLATED" if bad_ids else "HOLDS",
            "violating_states": bad_ids, "counterexample": trace,
        }

    af_idle, history = af_idle_fixed_point(model)
    bad_resets = [sid for sid, state in model.states.items()
                  if "resetting" in labels(state) and sid not in af_idle]
    trace = None
    if bad_resets:
        target = min(bad_resets, key=lambda sid: model.distances[sid])
        trace = _liveness_trace(model, target, af_idle)
    results["P5"] = {
        "method": "ctl_least_fixed_point", "holds": not bad_resets,
        "status": "VIOLATED" if bad_resets else "HOLDS",
        "violating_states": bad_resets, "counterexample": trace,
        "af_idle_states": history[-1], "fixed_point_iterations": history,
    }
    for property_id, result in results.items():
        result.update(
            formula=FORMULAS[property_id], meaning=MEANINGS[property_id],
            kind="safety" if property_id in SAFETY_PROPERTIES else "liveness",
            antecedent_states=[sid for sid, state in model.states.items()
                               if ANTECEDENTS[property_id] in labels(state)],
        )
    return results
