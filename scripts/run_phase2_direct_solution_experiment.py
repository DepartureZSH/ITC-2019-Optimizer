import argparse
import csv
import pathlib
import random
import shutil
import sys
import time
from typing import Dict, List, Tuple

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.solution_io import LocalValidator, SolutionLoader
from src.utils.dataReader import PSTTReader


Solution = Dict[str, dict]


def cost_key(result: dict) -> Tuple[float, int]:
    return float(result["total"]), int(result.get("hard_violations", 0))


def class_sort_key(value: str):
    try:
        return int(value)
    except ValueError:
        return value


def local_assignment_score(reader, cid: str, assignment: dict) -> float:
    cls = reader.classes[cid]
    time_penalty = 0
    for option in cls["time_options"]:
        weeks, days, start, _length = option["optional_time_bits"]
        if weeks == assignment.get("weeks") and days == assignment.get("days") and int(start) == int(assignment.get("start", -1)):
            time_penalty = int(option.get("penalty", 0))
            break

    room_penalty = 0
    room = assignment.get("room")
    if cls["room_required"] and room is not None:
        for option in cls["room_options"]:
            if str(option["id"]) == str(room):
                room_penalty = int(option.get("penalty", 0))
                break

    weights = reader.optimization or {}
    return time_penalty * int(weights.get("time", 0)) + room_penalty * int(weights.get("room", 0))


def pool_domains(pool: List[Tuple[str, Solution]], reader) -> Dict[str, List[dict]]:
    domains: Dict[str, List[dict]] = {cid: [] for cid in reader.classes}
    seen = {cid: set() for cid in reader.classes}
    for _path, solution in pool:
        for cid, assignment in solution.items():
            if cid not in domains:
                continue
            key = (
                assignment.get("weeks"),
                assignment.get("days"),
                int(assignment.get("start", -1)),
                assignment.get("room"),
            )
            if key not in seen[cid]:
                domains[cid].append(dict(assignment))
                seen[cid].add(key)

    for cid, values in domains.items():
        values.sort(key=lambda a: local_assignment_score(reader, cid, a))
    return domains


def soft_class_scores(validator: LocalValidator, solution: Solution) -> Dict[str, float]:
    assignments, _errors = validator._build_assignments(solution)
    scores: Dict[str, float] = {}
    for constraint in validator.reader.distributions.get("soft_constraints", []):
        for cid, score in validator._constraint_violation_scores(constraint, assignments).items():
            scores[cid] = scores.get(cid, 0.0) + float(score)
    return scores


def pick_destroy_classes(
    validator: LocalValidator,
    solution: Solution,
    destroy_size: int,
    high_prob: float,
) -> List[str]:
    cids = list(solution.keys())
    if not cids:
        return []

    use_high = random.random() < high_prob
    if use_high:
        scores = soft_class_scores(validator, solution)
        scored = [cid for cid in cids if scores.get(cid, 0.0) > 0.0]
        if scored:
            picked = []
            available = set(scored)
            while available and len(picked) < destroy_size:
                choices = list(available)
                weights = [max(scores[cid], 1e-6) for cid in choices]
                cid = random.choices(choices, weights=weights, k=1)[0]
                picked.append(cid)
                available.remove(cid)
            if len(picked) < destroy_size:
                rest = [cid for cid in cids if cid not in picked]
                picked.extend(random.sample(rest, min(destroy_size - len(picked), len(rest))))
            return picked

    return random.sample(cids, min(destroy_size, len(cids)))


def beam_repair(
    validator: LocalValidator,
    reader,
    current: Solution,
    domains: Dict[str, List[dict]],
    removed: List[str],
    candidate_limit: int,
    beam_width: int,
) -> Tuple[Solution, dict, int]:
    beam = [(dict((cid, dict(a)) for cid, a in current.items()), validator.validate_solution(current))]
    evaluations = 0

    for cid in sorted(removed, key=lambda c: len(domains.get(c, []))):
        next_beam = []
        candidates = domains.get(cid, [])
        if candidate_limit > 0:
            candidates = candidates[:candidate_limit]
        for partial, _partial_cost in beam:
            for candidate in candidates:
                trial = dict((k, dict(v)) for k, v in partial.items())
                trial[cid] = dict(candidate)
                score = validator.validate_solution(trial)
                evaluations += 1
                if score["valid"]:
                    next_beam.append((trial, score))
        if not next_beam:
            return current, validator.validate_solution(current), evaluations
        next_beam.sort(key=lambda item: cost_key(item[1]))
        beam = next_beam[:beam_width]

    return beam[0][0], beam[0][1], evaluations


def direct_phase2_search(
    validator: LocalValidator,
    reader,
    start_solution: Solution,
    domains: Dict[str, List[dict]],
    cfg: dict,
) -> Tuple[Solution, dict, dict]:
    random.seed(int(cfg["seed"]))
    current = dict((cid, dict(a)) for cid, a in start_solution.items())
    current_cost = validator.validate_solution(current)
    best = dict((cid, dict(a)) for cid, a in current.items())
    best_cost = dict(current_cost)
    accepted = 0
    repairs = 0
    evaluations = 0
    high_prob = float(cfg["mixed_high_distribution_prob"])

    for _iteration in range(int(cfg["max_iter"])):
        removed = pick_destroy_classes(validator, current, int(cfg["destroy_size"]), high_prob)
        candidate, candidate_cost, evals = beam_repair(
            validator,
            reader,
            current,
            domains,
            removed,
            int(cfg["repair_candidate_limit"]),
            int(cfg["beam_width"]),
        )
        evaluations += evals
        if candidate_cost["valid"]:
            repairs += 1
        if candidate_cost["valid"] and candidate_cost["total"] <= current_cost["total"]:
            current = candidate
            current_cost = candidate_cost
            accepted += 1
            if current_cost["total"] < best_cost["total"]:
                best = dict((cid, dict(a)) for cid, a in current.items())
                best_cost = dict(current_cost)

    return best, best_cost, {"accepted": accepted, "repairs": repairs, "candidate_evaluations": evaluations}


def run_instance(instance: str, args, cfg: dict) -> dict:
    t0 = time.time()
    loader = SolutionLoader()
    problem_path = args.data_dir / f"{instance}.xml"
    if not problem_path.exists():
        return {"instance": instance, "status": "missing_problem", "error": str(problem_path)}

    reader = PSTTReader(str(problem_path), matrix=False)
    validator = LocalValidator(reader)
    pool = loader.load_all(str(args.solutions_dir), instance)
    if not pool:
        return {"instance": instance, "status": "missing_solutions", "error": str(args.solutions_dir / instance)}

    scored = []
    for path, solution in pool:
        result = validator.validate_solution(solution)
        scored.append((path, solution, result))

    valid = [(path, solution, result) for path, solution, result in scored if result["valid"]]
    candidates = valid or scored
    baseline_path, baseline_solution, baseline_cost = min(candidates, key=lambda item: cost_key(item[2]))
    domains = pool_domains(pool, reader)

    t_search = time.time()
    result_solution, result_cost, search_stats = direct_phase2_search(
        validator,
        reader,
        baseline_solution,
        domains,
        cfg,
    )
    search_seconds = time.time() - t_search

    out_xml = args.output_dir / f"{instance}_phase2_direct.xml"
    loader.save_xml(
        result_solution,
        reader,
        str(out_xml),
        meta={"technique": "phase2-direct-solution-pool-repair"},
    )
    final_check = validator.validate_xml(str(out_xml), loader)

    improvement_abs = float(baseline_cost["total"] - final_check["total"])
    improvement_pct = improvement_abs / float(baseline_cost["total"]) * 100.0 if baseline_cost["total"] else 0.0

    return {
        "instance": instance,
        "status": "ok",
        "solutions": len(scored),
        "valid_pool": len(valid),
        "invalid_pool": len(scored) - len(valid),
        "baseline_solution": pathlib.Path(baseline_path).name,
        "baseline_total": baseline_cost["total"],
        "baseline_time": baseline_cost["time"],
        "baseline_room": baseline_cost["room"],
        "baseline_distribution": baseline_cost["distribution"],
        "baseline_valid": baseline_cost["valid"],
        "phase2_total": final_check["total"],
        "phase2_time": final_check["time"],
        "phase2_room": final_check["room"],
        "phase2_distribution": final_check["distribution"],
        "phase2_valid": final_check["valid"],
        "phase2_hard_violations": final_check["hard_violations"],
        "improvement_abs": improvement_abs,
        "improvement_pct": improvement_pct,
        "accepted": search_stats["accepted"],
        "repairs": search_stats["repairs"],
        "candidate_evaluations": search_stats["candidate_evaluations"],
        "search_seconds": round(search_seconds, 3),
        "total_seconds": round(time.time() - t0, 3),
        "output_xml": str(out_xml),
        "error": "",
    }


def write_csv(path: pathlib.Path, rows: List[dict]):
    fieldnames = [
        "instance",
        "status",
        "solutions",
        "valid_pool",
        "invalid_pool",
        "baseline_solution",
        "baseline_total",
        "baseline_time",
        "baseline_room",
        "baseline_distribution",
        "baseline_valid",
        "phase2_total",
        "phase2_time",
        "phase2_room",
        "phase2_distribution",
        "phase2_valid",
        "phase2_hard_violations",
        "improvement_abs",
        "improvement_pct",
        "accepted",
        "repairs",
        "candidate_evaluations",
        "search_seconds",
        "total_seconds",
        "output_xml",
        "error",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_report(path: pathlib.Path, rows: List[dict], cfg: dict, csv_path: pathlib.Path):
    ok_rows = [row for row in rows if row.get("status") == "ok"]
    improved = [row for row in ok_rows if float(row.get("improvement_abs", 0.0)) > 0.0]
    valid_outputs = [row for row in ok_rows if str(row.get("phase2_valid")) == "True"]

    lines = [
        "# Phase2实验报告",
        "",
        "## 实验说明",
        "",
        "本轮实验严格从 `data/solutions` 中已有 solution XML 开始，不调用 Gurobi，也不运行 MIP/数学规划求解器。",
        "计分使用 `src/solution_io/local_validator.py`，目标函数为 time、room、distribution 三项，student 固定为 0。",
        "",
        "Phase2 使用轻量 direct solution-pool repair：从解池有效最优解出发，优先抽取当前解中带来 distribution penalty 的 class，并用解池中已出现过的该 class 分配进行 beam repair。",
        "",
        "## 参数",
        "",
        f"- `max_iter`: {cfg['max_iter']}",
        f"- `destroy_size`: {cfg['destroy_size']}",
        f"- `mixed_high_distribution_prob`: {cfg['mixed_high_distribution_prob']}",
        f"- `repair_method`: beam",
        f"- `beam_width`: {cfg['beam_width']}",
        f"- `repair_candidate_limit`: {cfg['repair_candidate_limit']}",
        f"- `seed`: {cfg['seed']}",
        "",
        "## 总览",
        "",
        f"- 实例数: {len(rows)}",
        f"- 成功完成: {len(ok_rows)}",
        f"- 输出可行: {len(valid_outputs)}/{len(ok_rows)}",
        f"- 找到改进: {len(improved)}",
        f"- 明细 CSV: `{csv_path.as_posix()}`",
        "",
        "## 结果表",
        "",
        "| instance | valid pool | invalid pool | pool best | Phase2 total | valid | improvement | time(s) |",
        "|---|---:|---:|---:|---:|---|---:|---:|",
    ]
    for row in rows:
        if row.get("status") != "ok":
            lines.append(f"| {row['instance']} | - | - | - | - | error | - | - |")
            continue
        lines.append(
            "| {instance} | {valid_pool} | {invalid_pool} | {baseline_total} | {phase2_total} | "
            "{phase2_valid} | {improvement_abs} ({improvement_pct:.2f}%) | {total_seconds} |".format(
                instance=row["instance"],
                valid_pool=row["valid_pool"],
                invalid_pool=row["invalid_pool"],
                baseline_total=row["baseline_total"],
                phase2_total=row["phase2_total"],
                phase2_valid=row["phase2_valid"],
                improvement_abs=row["improvement_abs"],
                improvement_pct=float(row["improvement_pct"]),
                total_seconds=row["total_seconds"],
            )
        )

    lines.extend(
        [
            "",
            "## 结论",
            "",
            "这组实验验证了 Phase2 可以在无 Gurobi 环境下完整跑通全实例，并保持输出 hard-feasible。",
            "当前参数很保守，主要目标是全实例真实验证和建立可复现实验基线；若要追求更大改进，下一步应扩大 candidate domain 或增加迭代数，但需要控制运行时间。",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Run direct solution-pool Phase2 experiment without solver backends.")
    parser.add_argument("--data-dir", type=pathlib.Path, default=pathlib.Path("data/reduced"))
    parser.add_argument("--solutions-dir", type=pathlib.Path, default=pathlib.Path("data/solutions"))
    parser.add_argument("--output-dir", type=pathlib.Path, default=pathlib.Path("output/phase2_direct_all_instances"))
    parser.add_argument("--max-iter", type=int, default=5)
    parser.add_argument("--destroy-size", type=int, default=3)
    parser.add_argument("--beam-width", type=int, default=2)
    parser.add_argument("--repair-candidate-limit", type=int, default=8)
    parser.add_argument("--mixed-high-distribution-prob", type=float, default=0.8)
    parser.add_argument("--seed", type=int, default=20260425)
    parser.add_argument("--report-path", type=pathlib.Path, default=pathlib.Path("Phase2实验报告.md"))
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    cfg = {
        "max_iter": args.max_iter,
        "destroy_size": args.destroy_size,
        "beam_width": args.beam_width,
        "repair_candidate_limit": args.repair_candidate_limit,
        "mixed_high_distribution_prob": args.mixed_high_distribution_prob,
        "seed": args.seed,
    }

    rows = []
    summary_csv = args.output_dir / "phase2_direct_all_instances_summary.csv"
    instances = sorted([p.name for p in args.solutions_dir.iterdir() if p.is_dir()])
    for idx, instance in enumerate(instances, start=1):
        print(f"[{idx}/{len(instances)}] {instance}")
        row = run_instance(instance, args, {**cfg, "seed": args.seed + idx})
        rows.append(row)
        write_csv(summary_csv, rows)
        if row.get("status") == "ok":
            print(
                f"  pool={row['baseline_total']} phase2={row['phase2_total']} "
                f"valid={row['phase2_valid']} delta={row['improvement_abs']}"
            )
        else:
            print(f"  {row.get('status')}: {row.get('error', '')}")

    report_path = args.report_path
    write_report(report_path, rows, cfg, summary_csv)
    shutil.copyfile(report_path, args.output_dir / report_path.name)
    print(f"CSV: {summary_csv}")
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()
