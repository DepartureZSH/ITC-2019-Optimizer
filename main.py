"""
ITC2019 Post-Optimization Entry Point
Usage:
    python main.py                            # uses config.yaml
    python main.py --config my_config.yaml
    python main.py --instance muni-fi-fal17
    python main.py --method local_search
"""

import argparse
import csv
import gc
import pathlib
import time
import torch
import yaml

folder = pathlib.Path(__file__).parent.resolve()


def resolve_path(path_value: str) -> pathlib.Path:
    path = pathlib.Path(path_value)
    if not path.is_absolute():
        path = folder / path
    return path


def build_model(instance: str, data_dir: pathlib.Path, device: str, matrix: bool = False):
    from src.utils.dataReader import PSTTReader
    from src.utils.ConstraintsResolver_v2 import ConstraintsResolver

    if str(device).startswith("cuda") and not torch.cuda.is_available():
        print(f"CUDA device requested ({device}) but torch.cuda.is_available() is false; falling back to cpu")
        device = "cpu"

    problem_path = data_dir / f"{instance}.xml"
    if not problem_path.exists():
        raise FileNotFoundError(f"Problem XML not found: {problem_path}")

    print(f"\n{'='*60}")
    print(f"Building constraint model: {instance}")
    print(f"Device: {device}")
    t0 = time.time()
    reader      = PSTTReader(str(problem_path), matrix=matrix)
    constraints = ConstraintsResolver(reader, device=device)
    constraints.build_model()
    print(f"Model built in {time.time()-t0:.1f}s")
    return reader, constraints


def _repair_invalid_with_anchor(x, anchor_x, constraints, loader, evaluator, max_classes: int = None):
    """Try to make a hard-invalid pool member feasible by reverting hot classes to anchor."""
    scores = evaluator.local_validator.hard_violation_class_scores_from_x(x, constraints)
    if not scores:
        return None, None, 0

    current = loader._class_assignment_from_x(x, constraints)
    fallback = loader._class_assignment_from_x(anchor_x, constraints)
    scored_order = sorted(scores, key=lambda cid: (-scores[cid], int(cid) if str(cid).isdigit() else str(cid)))
    remaining = [
        cid for cid in constraints.reader.classes
        if cid not in scores and current.get(cid) != fallback.get(cid)
    ]
    remaining.sort(key=lambda cid: int(cid) if str(cid).isdigit() else str(cid))
    ordered = scored_order + remaining
    if max_classes is not None:
        ordered = ordered[:max_classes]
    checkpoints = {1, 2, 4, 8, 16, 32, 64, 128, 256, 512, len(ordered)}

    candidate = x.clone()
    changed = 0
    for cid in ordered:
        old_idx = current.get(cid)
        new_idx = fallback.get(cid)
        if new_idx is None or old_idx == new_idx:
            continue
        if old_idx is not None:
            candidate[old_idx] = 0.0
        candidate[new_idx] = 1.0
        current[cid] = new_idx
        changed += 1

        if changed in checkpoints:
            cost = evaluator.evaluate(candidate)
            if cost.get("valid", True):
                return candidate, cost, changed

    if changed:
        cost = evaluator.evaluate(candidate)
        if cost.get("valid", True):
            return candidate, cost, changed
    return None, None, changed


def evaluate_solution_pool(solutions_dir: pathlib.Path, instance: str,
                           constraints, loader, evaluator):
    """Load existing solution XMLs, compute cost stats, return list of (path, x_tensor)."""
    from src.solution_io import SolutionLoader, SolutionEvaluator

    sol_folder = solutions_dir / instance
    if not sol_folder.exists():
        raise FileNotFoundError(f"Solutions folder not found: {sol_folder}")

    all_solutions = loader.load_all(str(solutions_dir), instance)
    print(f"\nLoaded {len(all_solutions)} existing solution XMLs")

    pool = []
    costs = []
    skipped = []
    for path, sol_dict in all_solutions:
        try:
            x = loader.encode(sol_dict, constraints)
            c = evaluator.evaluate(x)
            pool.append((path, x))
            costs.append(c)
        except Exception as e:
            skipped.append((path, sol_dict, e))
            print(f"  Strict skip {pathlib.Path(path).name}: {e}")

    repaired = 0
    repaired_valid = 0
    repair_log_limit = 20
    if skipped and pool:
        valid_indices = [i for i, c in enumerate(costs) if c.get("valid", True)]
        anchor_candidates = valid_indices or list(range(len(costs)))
        anchor_idx = min(anchor_candidates, key=lambda i: costs[i]["total"])
        anchor_path, anchor_x = pool[anchor_idx]
        print(
            f"Repairing {len(skipped)} skipped solution XMLs with anchor "
            f"{pathlib.Path(anchor_path).name}"
        )

        for path, sol_dict, _err in skipped:
            try:
                x, stats = loader.encode_with_fallback(sol_dict, constraints, anchor_x)
                c = evaluator.evaluate(x)
                pool.append((path, x))
                costs.append(c)
                repaired += 1
                if c.get("valid", True):
                    repaired_valid += 1
                if repaired <= repair_log_limit:
                    print(
                        f"  Repaired {pathlib.Path(path).name}: "
                        f"matched={stats['matched']} fallback={stats['fallback']} "
                        f"valid={c.get('valid', True)} total={c['total']:.1f}"
                    )
            except Exception as e:
                print(f"  Repair failed {pathlib.Path(path).name}: {e}")

    if repaired:
        if repaired > repair_log_limit:
            print(f"  ... {repaired - repair_log_limit} more fallback repairs omitted")
        print(f"Repaired pool additions: {repaired_valid}/{repaired} feasible")

    invalid_indices = [i for i, c in enumerate(costs) if not c.get("valid", True)]
    invalid_repaired = 0
    invalid_repair_log_limit = 20
    if invalid_indices:
        valid_indices = [i for i, c in enumerate(costs) if c.get("valid", True)]
        if valid_indices:
            anchor_idx = min(valid_indices, key=lambda i: costs[i]["total"])
            anchor_path, anchor_x = pool[anchor_idx]
            print(
                f"Repairing {len(invalid_indices)} hard-invalid pool members with anchor "
                f"{pathlib.Path(anchor_path).name}"
            )
            for i in invalid_indices:
                path, x = pool[i]
                repaired_x, repaired_cost, changed = _repair_invalid_with_anchor(
                    x, anchor_x, constraints, loader, evaluator
                )
                if repaired_cost is not None:
                    pool[i] = (path, repaired_x)
                    costs[i] = repaired_cost
                    invalid_repaired += 1
                    if invalid_repaired <= invalid_repair_log_limit:
                        print(
                            f"  Feasibility-repaired {pathlib.Path(path).name}: "
                            f"changed={changed} total={repaired_cost['total']:.1f}"
                        )
            if invalid_repaired > invalid_repair_log_limit:
                print(f"  ... {invalid_repaired - invalid_repair_log_limit} more feasibility repairs omitted")
            print(f"Feasibility-repaired pool members: {invalid_repaired}/{len(invalid_indices)}")

    if not costs:
        raise ValueError(f"No solution XMLs could be loaded for {instance}")

    totals = [c["total"] for c in costs]
    valid_indices = [i for i, c in enumerate(costs) if c.get("valid", True)]
    print(
        f"Solution pool — best: {min(totals):.1f}  "
        f"avg: {sum(totals)/len(totals):.1f}  worst: {max(totals):.1f}  "
        f"valid: {len(valid_indices)}/{len(costs)}"
    )
    best_candidates = valid_indices or list(range(len(costs)))
    best_idx = min(best_candidates, key=lambda i: costs[i]["total"])
    bc = costs[best_idx]
    print(f"Pool best — total: {bc['total']:.1f}  time: {bc['time']:.1f}  room: {bc['room']:.1f}  dist: {bc['distribution']:.1f}")
    return pool, costs


def run_instance(cfg: dict, instance: str, data_dir: pathlib.Path, solutions_dir: pathlib.Path,
                 output_dir: pathlib.Path) -> dict:
    method = cfg.get("method", "merging")
    device = cfg.get("device", "cpu")

    print(f"\n{'#' * 72}")
    print(f"Instance : {instance}")
    print(f"Method   : {method}")

    t0 = time.time()
    result_xml = None
    try:
        # -----------------------------------------------------------------------
        # Build constraint model (shared by all methods)
        # -----------------------------------------------------------------------
        reader, constraints = build_model(instance, data_dir, device, matrix=bool(cfg.get("matrix", False)))

        from src.solution_io import SolutionLoader, SolutionEvaluator
        loader = SolutionLoader()
        evaluator = SolutionEvaluator(constraints)

        # Evaluate existing solution pool.
        pool, pool_costs = evaluate_solution_pool(solutions_dir, instance, constraints, loader, evaluator)

        # -----------------------------------------------------------------------
        # Dispatch to method
        # -----------------------------------------------------------------------
        if method == "merging":
            from src.merging import run_merging
            result_x, result_cost, result_xml = run_merging(
                cfg.get("merging", {}),
                constraints, loader, evaluator,
                pool, pool_costs, instance, output_dir
            )

        elif method == "local_search":
            from src.local_search import run_local_search
            result_x, result_cost, result_xml = run_local_search(
                cfg.get("local_search", {}),
                constraints, loader, evaluator,
                pool, pool_costs, instance, output_dir
            )

        elif method == "lns":
            from src.lns import run_lns
            result_x, result_cost, result_xml = run_lns(
                cfg.get("lns", {}),
                constraints, loader, evaluator,
                pool, pool_costs, instance, output_dir
            )

        elif method == "tensor_search":
            from src.tensor_search import run_tensor_search
            result_x, result_cost, result_xml = run_tensor_search(
                cfg.get("tensor_search", {}),
                constraints, loader, evaluator,
                pool, pool_costs, instance, output_dir
            )

        else:
            raise ValueError(f"Unknown method: {method}. Choices: merging, local_search, lns, tensor_search")

        student_stats = None
        student_xml = ""
        student_cfg = cfg.get("student_assignment", {})
        if student_cfg.get("enabled", False):
            from src.student_assignment import run_student_assignment
            base_solution = loader.decode(result_x, constraints)
            _student_solution, student_stats, student_xml = run_student_assignment(
                student_cfg, reader, loader, base_solution, instance, output_dir
            )
            result_xml = student_xml

        # -----------------------------------------------------------------------
        # Summary
        # -----------------------------------------------------------------------
        valid_pool_costs = [c for c in pool_costs if c.get("valid", True)]
        baseline_costs = valid_pool_costs or pool_costs
        pool_best = min(c["total"] for c in baseline_costs)
        improve = (pool_best - result_cost["total"]) / pool_best * 100 if pool_best > 0 else 0.0
        print(f"\n{'='*60}")
        print(f"Final result ({method}):")
        print(f"  Total cost   : {result_cost['total']:.1f}  (pool best: {pool_best:.1f},  Δ = {improve:+.2f}%)")
        print(f"  Time penalty : {result_cost['time']:.1f}")
        print(f"  Room penalty : {result_cost['room']:.1f}")
        print(f"  Distribution : {result_cost['distribution']:.1f}")
        if student_stats:
            student_weight = int((reader.optimization or {}).get("student", 0))
            weighted_student = student_stats["student_conflicts"] * student_weight
            print(f"  Student conflicts: {student_stats['student_conflicts']}  weighted={weighted_student}")

        # Optional: validate with official API
        validate = cfg.get(method, {}).get("validate", False)
        if validate and result_xml:
            print(f"\nValidating {pathlib.Path(result_xml).name} against official validator ...")
            try:
                from src.solution_io import report_result
                official = report_result(result_xml)
                if official:
                    print(f"Official total cost: {official['Total cost']}")
            except Exception as e:
                print(f"Validator unavailable: {e}")

        return {
            "instance": instance,
            "status": "ok",
            "method": method,
            "pool_best": float(pool_best),
            "total": float(result_cost["total"]),
            "improvement_pct": float(improve),
            "time": float(result_cost["time"]),
            "room": float(result_cost["room"]),
            "distribution": float(result_cost["distribution"]),
            "valid": bool(result_cost.get("valid", True)),
            "runtime_sec": round(time.time() - t0, 2),
            "output_xml": str(result_xml or ""),
            "student_conflicts": "" if not student_stats else int(student_stats["student_conflicts"]),
            "weighted_student": "" if not student_stats else int(student_stats["student_conflicts"]) * int((reader.optimization or {}).get("student", 0)),
            "student_xml": str(student_xml or ""),
            "error": "",
        }
    except Exception as e:
        print(f"\nInstance failed: {instance}: {e}")
        return {
            "instance": instance,
            "status": "failed",
            "method": method,
            "pool_best": "",
            "total": "",
            "improvement_pct": "",
            "time": "",
            "room": "",
            "distribution": "",
            "valid": False,
            "runtime_sec": round(time.time() - t0, 2),
            "output_xml": "",
            "student_conflicts": "",
            "weighted_student": "",
            "student_xml": "",
            "error": str(e),
        }
    finally:
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


def write_batch_summary(rows: list, output_dir: pathlib.Path, method: str) -> pathlib.Path:
    out_path = output_dir / f"batch_{method}_summary.csv"
    if not rows:
        return out_path
    fields = [
        "instance", "status", "method", "pool_best", "total", "improvement_pct",
        "time", "room", "distribution", "valid", "runtime_sec", "output_xml",
        "student_conflicts", "weighted_student", "student_xml", "error",
    ]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return out_path


def print_batch_summary(rows: list):
    print(f"\n{'=' * 72}")
    print("Batch summary")
    ok_rows = [r for r in rows if r["status"] == "ok"]
    failed_rows = [r for r in rows if r["status"] != "ok"]
    improved_rows = [
        r for r in ok_rows
        if isinstance(r.get("improvement_pct"), float) and r["improvement_pct"] > 0
    ]
    print(f"Instances : {len(rows)}")
    print(f"OK        : {len(ok_rows)}")
    print(f"Failed    : {len(failed_rows)}")
    print(f"Improved  : {len(improved_rows)}")
    for r in rows:
        if r["status"] == "ok":
            print(
                f"  {r['instance']}: total={r['total']:.1f} "
                f"pool={r['pool_best']:.1f} improve={r['improvement_pct']:+.2f}% "
                f"valid={r['valid']}"
            )
        else:
            print(f"  {r['instance']}: FAILED - {r['error']}")


def main():
    parser = argparse.ArgumentParser(description="ITC2019 post-optimization")
    parser.add_argument("--config",   default="config.yaml", help="config file path")
    parser.add_argument("--instance", default=None, help="override instance name")
    parser.add_argument("--data_folder", default=None, help="run every *.xml instance in this problem-data folder")
    parser.add_argument("--method",   default=None, help="override method")
    parser.add_argument("--device",   default=None, help="override device")
    parser.add_argument("--student_assignment", action="store_true", help="enable final MARL-guided student assignment")
    args = parser.parse_args()

    config_path = resolve_path(args.config)
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    if args.instance: cfg["instance"] = args.instance
    if args.method:   cfg["method"]   = args.method
    if args.device:   cfg["device"]   = args.device
    if args.data_folder:
        cfg["data_dir"] = args.data_folder
    if args.student_assignment:
        cfg.setdefault("student_assignment", {})["enabled"] = True

    method       = cfg.get("method", "merging")
    data_dir     = resolve_path(cfg.get("data_dir", "data/reduced"))
    solutions_dir = resolve_path(cfg.get("solutions_dir", "data/solutions"))
    output_dir   = resolve_path(cfg.get("output_dir", "output"))
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.data_folder:
        instance_paths = sorted(data_dir.glob("*.xml"))
        if not instance_paths:
            raise FileNotFoundError(f"No problem XML files found in data_folder: {data_dir}")
        print(f"Batch mode: {len(instance_paths)} instances from {data_dir}")
        print(f"Method    : {method}")
        print(f"Device    : {cfg.get('device', 'cpu')}")
        rows = [
            run_instance(cfg, path.stem, data_dir, solutions_dir, output_dir)
            for path in instance_paths
        ]
        summary_path = write_batch_summary(rows, output_dir, method)
        print_batch_summary(rows)
        print(f"Summary CSV: {summary_path}")
        return

    instance = cfg["instance"]
    run_instance(cfg, instance, data_dir, solutions_dir, output_dir)


if __name__ == "__main__":
    main()
