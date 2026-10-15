"""BMC/Z3 cho riêng P1–P4 của mô hình G2; không dùng bad-state cho P5."""

from z3 import And, BoolVal, Int, Or, Solver, sat, unknown, unsat

from .ctl import SAFETY_PROPERTIES, bad_state, reachable_depths, validate_counterexample, validate_model
from .kripke import SmartLockModel, make_trace
from .model import EVENTS


def transition_constraint(model: SmartLockModel, source, event, target):
    """T(x,e,y): OR đúng các cạnh source/event/target đã sinh ở G2."""
    ids = {sid: i for i, sid in enumerate(model.states)}
    event_ids = {name: i for i, name in enumerate(EVENTS)}
    return Or([
        And(source == ids[edge.source], event == event_ids[edge.event], target == ids[edge.target])
        for edge in model.transitions
    ])


def encode_path(model: SmartLockModel, bound: int) -> tuple[list, list, list]:
    """Unroll k bước: k+1 biến state ID, k biến event, I/domain/T."""
    if type(bound) is not int or bound < 0:
        raise ValueError("bound phải là số nguyên không âm")
    states = [Int(f"x_{i}") for i in range(bound + 1)]
    events = [Int(f"e_{i}") for i in range(bound)]
    ids = {sid: i for i, sid in enumerate(model.states)}
    constraints = [Or([states[0] == ids[sid] for sid in model.graph.initial])]
    constraints += [And(state >= 0, state < len(ids)) for state in states]
    for i, event in enumerate(events):
        constraints.append(And(event >= 0, event < len(EVENTS)))
        constraints.append(transition_constraint(model, states[i], event, states[i + 1]))
    return states, events, constraints


def check_bound(model: SmartLockModel, property_id: str, bound: int) -> dict:
    """Một lần gọi Solver.check thật, kèm SMT-LIB và replay khi SAT.

    status của ứng dụng có thể ERROR trong khi solver_status vẫn là SAT,
    ví dụ giải mã hoặc replay thất bại. Không gán UNSAT cho nhánh chưa gọi solver.
    """
    result = {
        "property": property_id, "bound": bound, "status": "ERROR",
        "solver_called": False, "solver_status": None, "reason": None,
        "counterexample": None, "replay_validated": False,
    }
    try:
        if property_id not in SAFETY_PROPERTIES:
            raise ValueError("BMC bad-state chỉ hỗ trợ P1–P4; P5 dùng CTL fixed-point")
        validate_model(model)
        states, events, constraints = encode_path(model, bound)
        ids = list(model.states)
        bad_ids = [i for i, sid in enumerate(ids) if bad_state(model.states[sid], property_id)]
        solver = Solver()
        solver.set(timeout=10000)
        solver.add(*constraints)
        bad = Or([state == bad_id for state in states for bad_id in bad_ids]) if bad_ids else BoolVal(False)
        solver.add(bad)  # Tập bad rỗng vẫn gọi solver, SMT-LIB ghi rõ (assert false).
        result["smt2"] = solver.to_smt2()
        result["solver_called"] = True
        outcome = solver.check()
        result["solver_status"] = str(outcome).upper()
        if outcome == sat:
            witness = solver.model()
            result["solver_model"] = str(witness)
            state_numbers = [witness.eval(state, model_completion=True).as_long() for state in states]
            event_numbers = [witness.eval(event, model_completion=True).as_long() for event in events]
            if (any(not 0 <= i < len(ids) for i in state_numbers)
                    or any(not 0 <= i < len(EVENTS) for i in event_numbers)):
                raise ValueError("Model Z3 chứa ID ngoài miền")
            trace = make_trace(model, [ids[i] for i in state_numbers],
                               [EVENTS[i] for i in event_numbers], property_id)
            trace["violation_step"] = next(
                i for i, row in enumerate(trace["steps"])
                if bad_state(model.states[row["state_id"]], property_id)
            )
            validate_counterexample(model, trace, property_id)
            result.update(status="SAT", counterexample=trace, replay_validated=True)
        elif outcome == unsat:
            result["status"] = "UNSAT"
        elif outcome == unknown:
            result.update(status="UNKNOWN", reason=solver.reason_unknown())
        else:
            raise ValueError(f"Kết quả solver không nhận diện được: {outcome}")
    except Exception as error:
        result.update(status="ERROR", reason=f"{type(error).__name__}: {error}")
    return result


def check_safety_bmc(model: SmartLockModel, property_id: str, max_bound: int | None = None) -> dict:
    """Tăng k từ 0, dừng ở SAT/UNKNOWN/ERROR hoặc reachability diameter D.

    Chỉ gọi phản ví dụ ngắn nhất khi mọi bound nhỏ hơn đều thực sự UNSAT.
    Nếu UNKNOWN thì dừng để không bỏ qua một lỗi nông chưa được kết luận.
    """
    if property_id not in SAFETY_PROPERTIES:
        raise ValueError("Chỉ P1–P4 có safety BMC")
    validate_model(model)
    threshold = max(reachable_depths(model).values())
    if max_bound is not None and (type(max_bound) is not int or max_bound < 0):
        raise ValueError("max_bound phải là số nguyên không âm")
    limit = threshold if max_bound is None else min(max_bound, threshold)
    checks = []
    holds = None
    status = "BOUNDED_NO_COUNTEREXAMPLE"
    for bound in range(limit + 1):
        check = check_bound(model, property_id, bound)
        checks.append(check)
        if check["status"] == "SAT":
            status, holds = "VIOLATED", False
            break
        if check["status"] in ("UNKNOWN", "ERROR"):
            status = "INCONCLUSIVE" if check["status"] == "UNKNOWN" else "ERROR"
            break
    else:
        if limit == threshold:
            status, holds = "HOLDS", True
    last = checks[-1]
    return {
        "method": "bmc_z3", "property": property_id,
        "status": status, "holds": holds, "completeness_threshold": threshold,
        "checked_bounds": [check["bound"] for check in checks],
        "last_solver_status": last["solver_status"],
        "shortest_counterexample": status == "VIOLATED",
        "counterexample": last["counterexample"] if status == "VIOLATED" else None,
        "checks": checks,
    }
