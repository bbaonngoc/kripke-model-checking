"""Smart Lock: sinh/mô phỏng G2, --verify G3, --artifacts G4."""

import argparse
from collections import Counter
import csv
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from smartlock.kripke import build_model, load_g2_model, write_model
from smartlock.model import INITIAL_STATE, InvalidEvent, step


def _trace_text(trace: dict | None) -> str:
    if trace is None:
        return ""
    rows = trace["steps"]
    text = rows[0]["state_id"]
    for row in rows[1:]:
        text += f" --{row['incoming_event']}--> {row['state_id']}"
    if trace["kind"] == "lasso":
        return text + f"; reset_step={trace['reset_step']}; loop_start={trace['loop_start']}"
    return text + f"; violation_step={trace['violation_step']}"


def _verify(args) -> int:
    # Import muộn: lệnh G2 và 78 tests G2 không cần import Z3.
    from z3 import get_version_string
    from smartlock.bmc import check_safety_bmc
    from smartlock.ctl import SAFETY_PROPERTIES, check_ctl, reachable_depths

    versions = ("v0", "v1") if args.version == "both" else (args.version,)
    comparison = []
    totals = Counter()
    application_errors = 0
    execution_ok = True
    print(f"G3 verification; Z3 {get_version_string()}; no G4/G5 artifacts")
    for version in versions:
        path = args.output_dir / version / "model.json"
        model = load_g2_model(path)
        if model.version != version:
            raise ValueError("Version trong snapshot không khớp thư mục")
        depths = reachable_depths(model)
        ctl = check_ctl(model)
        bmc = {pid: check_safety_bmc(model, pid, args.max_bound) for pid in SAFETY_PROPERTIES}
        agreement = {pid: None if bmc[pid]["holds"] is None
                     else bmc[pid]["holds"] == ctl[pid]["holds"] for pid in SAFETY_PROPERTIES}
        queries = [q for result in bmc.values() for q in result["checks"]]
        counts = Counter(q["solver_status"] for q in queries if q["solver_status"] is not None)
        counts = {name: counts[name] for name in ("SAT", "UNSAT", "UNKNOWN")}
        errors = sum(q["status"] == "ERROR" for q in queries)
        application_errors += errors
        totals.update(counts)
        payload = {
            "stage": "G3", "version": version,
            "source_model": str(path.resolve()),
            "source_model_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "g2_statistics": model.statistics(), "reachable_depths": depths,
            "safety_completeness_threshold": max(depths.values()),
            "z3_version": get_version_string(),
            "solver_calls": sum(q["solver_called"] for q in queries),
            "solver_outcomes": counts, "application_errors": errors,
            "ctl": ctl, "bmc": bmc,
            "safety_methods_agree": agreement,
        }
        output = path.with_name("verification.json")
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{version}: snapshot G2 matched; D={max(depths.values())}; "
              f"solver_calls={payload['solver_calls']}; outcomes={counts}; application_errors={errors}")
        for pid, result in ctl.items():
            bounded = bmc.get(pid)
            print(f"  {pid} {result['formula']}: CTL={result['status']}; "
                  f"antecedent_states={len(result['antecedent_states'])}")
            if bounded:
                for query in bounded["checks"]:
                    print(f"    Z3 k={query['bound']}: {query['solver_status']}; "
                          f"status={query['status']}; called={query['solver_called']}")
                    if query["reason"]:
                        print(f"      {query['reason']}")
                print(f"    BMC conclusion={bounded['status']}; agreement={agreement[pid]}")
                execution_ok &= bounded["status"] not in ("ERROR", "INCONCLUSIVE") and agreement[pid] is not False
            else:
                print(f"    AF fixed-point sizes={[len(z) for z in result['fixed_point_iterations']]}; Z3 not used")
            trace = (bounded["counterexample"] if bounded else None) or result["counterexample"]
            if trace:
                print(f"    Counterexample replay validated: {_trace_text(trace)}")
                for row in trace["steps"]:
                    print(f"      step {row['step']} {row['state_id']}: {row['state']}; "
                          f"incoming={row['incoming_event']}; admin_authenticated={row['admin_authenticated']}")
            comparison.append({
                "version": version, "property": pid, "formula": result["formula"],
                "kind": result["kind"],
                "method": result["method"] + (" + bmc_z3" if bounded else ""),
                "ctl_status": result["status"],
                "bmc_status": bounded["status"] if bounded else "NOT_APPLICABLE",
                "last_solver_status": bounded["last_solver_status"] if bounded else "NOT_USED",
                "checked_bounds": ";".join(map(str, bounded["checked_bounds"])) if bounded else "NOT_APPLICABLE",
                "safety_completeness_threshold": max(depths.values()) if bounded else "NOT_APPLICABLE",
                "counterexample": _trace_text(trace),
            })
        print(f"  Saved {output}")
    comparison_path = args.output_dir / "comparison.csv"
    with comparison_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(comparison[0]))
        writer.writeheader()
        writer.writerows(comparison)
    print(f"All verification-run solver outcomes: {dict(totals)}; "
          f"application_errors={application_errors}; saved {comparison_path}")
    return 0 if execution_ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", choices=("v0", "v1", "both"), default="both")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent / "results")
    parser.add_argument("--events", nargs="+", help="Mô phỏng tuần tự, dùng cùng --version v0 hoặc v1")
    parser.add_argument("--admin-authenticated", action="store_true",
                        help="Kết quả xác thực quản trị True trong môi trường mô phỏng")
    parser.add_argument("--verify", action="store_true", help="G3: kiểm chứng snapshot model.json đã sinh ở G2")
    parser.add_argument("--artifacts", action="store_true", help="G4: sinh Python, đối chiếu toàn bộ bảng và vẽ 7 sơ đồ")
    parser.add_argument("--generated-dir", type=Path, default=Path(__file__).resolve().parent / "generated")
    parser.add_argument("--dot", type=Path, help="Graphviz dot executable, nếu chưa nằm trong PATH")
    parser.add_argument("--max-bound", type=int, help="Giới hạn safety BMC; mặc định tới D của toàn mô hình")
    args = parser.parse_args(argv)
    if args.artifacts:
        if args.verify or args.events or args.max_bound is not None or args.version != "both":
            parser.error("--artifacts dùng cả v0/v1, không dùng cùng --verify/--events/--max-bound")
        from smartlock.artifacts import build_artifacts
        build_artifacts(args.output_dir, args.generated_dir, args.dot)
        return 0
    if args.verify and args.events:
        parser.error("--verify không dùng cùng --events")
    if args.max_bound is not None and (not args.verify or args.max_bound < 0):
        parser.error("--max-bound cần --verify và phải không âm")
    if args.verify:
        return _verify(args)
    if args.events and args.version == "both":
        parser.error("--events yêu cầu chọn một --version v0 hoặc v1")

    versions = ("v0", "v1") if args.version == "both" else (args.version,)
    for version in versions:
        model = build_model(version)
        if not all(model.structural_checks().values()):
            raise ValueError(f"{version}: kiểm tra cấu trúc thất bại")
        if not all(check["holds"] for check in model.basic_invariants().values()):
            raise ValueError(f"{version}: bất biến dữ liệu cơ bản bị vi phạm")
        path = args.output_dir / version / "model.json"
        write_model(model, path)
        stats = model.statistics()
        print(f"{version}: states={stats['states']}, reachable={stats['reachable_states']}, "
              f"event_transitions={stats['event_transitions']}, |R|={stats['relation_pairs']}, "
              f"max_bfs_depth={stats['max_bfs_depth']}")
        print(f"  Structural checks: {len(model.structural_checks())} passed; "
              f"basic data invariants: {len(model.basic_invariants())} passed")
        print(f"  JSON: {path}")

    if args.events:
        current = INITIAL_STATE
        print("step 0:", json.dumps(asdict(current)))
        for index, event in enumerate(args.events, start=1):
            try:
                current = step(current, event, args.version,
                               admin_authenticated=args.admin_authenticated)
            except InvalidEvent as error:
                print(f"step {index}: REJECTED {error}")
                return 1
            print(f"step {index} --{event}-->", json.dumps(asdict(current)))
    print("G2 only: no CTL/BMC verification has been run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
