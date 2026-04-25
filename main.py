"""
ITC2019 Post-Optimization Entry Point
Usage:
    python main.py                            # uses config.yaml
    python main.py --config my_config.yaml
    python main.py --instance muni-fi-fal17
    python main.py --method local_search
"""

import argparse
import pathlib
import time
import torch
import yaml

folder = pathlib.Path(__file__).parent.resolve()


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
    for path, sol_dict in all_solutions:
        try:
            x = loader.encode(sol_dict, constraints)
            c = evaluator.evaluate(x)
            pool.append((path, x))
            costs.append(c)
        except Exception as e:
            print(f"  Skipping {pathlib.Path(path).name}: {e}")

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


def main():
    parser = argparse.ArgumentParser(description="ITC2019 post-optimization")
    parser.add_argument("--config",   default="config.yaml", help="config file path")
    parser.add_argument("--instance", default=None, help="override instance name")
    parser.add_argument("--method",   default=None, help="override method")
    parser.add_argument("--device",   default=None, help="override device")
    args = parser.parse_args()

    config_path = folder / args.config
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    if args.instance: cfg["instance"] = args.instance
    if args.method:   cfg["method"]   = args.method
    if args.device:   cfg["device"]   = args.device

    instance     = cfg["instance"]
    method       = cfg.get("method", "merging")
    device       = cfg.get("device", "cpu")
    data_dir     = folder / cfg.get("data_dir",     "data/reduced")
    solutions_dir = folder / cfg.get("solutions_dir", "data/solutions")
    output_dir   = folder / cfg.get("output_dir",   "output")
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Instance : {instance}")
    print(f"Method   : {method}")

    # -----------------------------------------------------------------------
    # Build constraint model (shared by all methods)
    # -----------------------------------------------------------------------
    reader, constraints = build_model(instance, data_dir, device, matrix=bool(cfg.get("matrix", False)))

    from src.solution_io import SolutionLoader, SolutionEvaluator
    loader    = SolutionLoader()
    evaluator = SolutionEvaluator(constraints)

    # Evaluate existing solution pool.
    pool, pool_costs = evaluate_solution_pool(solutions_dir, instance, constraints,
                                              loader, evaluator)

    # -----------------------------------------------------------------------
    # Dispatch to method
    # -----------------------------------------------------------------------
    result_xml = None
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

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    valid_pool_costs = [c for c in pool_costs if c.get("valid", True)]
    baseline_costs = valid_pool_costs or pool_costs
    pool_best = min(c["total"] for c in baseline_costs)
    improve  = (pool_best - result_cost["total"]) / pool_best * 100 if pool_best > 0 else 0.0
    print(f"\n{'='*60}")
    print(f"Final result ({method}):")
    print(f"  Total cost   : {result_cost['total']:.1f}  (pool best: {pool_best:.1f},  Δ = {improve:+.2f}%)")
    print(f"  Time penalty : {result_cost['time']:.1f}")
    print(f"  Room penalty : {result_cost['room']:.1f}")
    print(f"  Distribution : {result_cost['distribution']:.1f}")

    # Optional: validate with official API
    validate = cfg.get(method, {}).get("validate", False)
    if validate and result_xml:
        print(f"\nValidating {pathlib.Path(result_xml).name} against official validator …")
        try:
            from src.solution_io import report_result
            official = report_result(result_xml)
            if official:
                print(f"Official total cost: {official['Total cost']}")
        except Exception as e:
            print(f"Validator unavailable: {e}")


if __name__ == "__main__":
    main()
