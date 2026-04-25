"""
Solution Pool Merging — Approach 4

Two strategies share the same greedy backbone:
  - 'greedy'    : rank candidates by weighted local penalty only
  - 'frequency' : rank candidates by pool frequency + penalty (combined score)

Core idea:
  For each class, collect candidate (tidx, rid) assignments. Rank them.
  Assign classes one by one (most-constrained first). For each class, pick
  the best candidate that does not violate any hard constraint with already-
  assigned classes.

Constraint tracking uses a lightweight in-memory reverse index over
hard_constraints (not the sparse tensor) for O(1) per-variable lookup.
"""

import pathlib
import time
from collections import defaultdict
from typing import Dict, List, Tuple, Optional

import torch


# -----------------------------------------------------------------------
# Constraint Tracker
# -----------------------------------------------------------------------

class ConstraintTracker:
    """
    Incrementally tracks hard-constraint violations during greedy assignment.

    Internally builds var_to_hc: x_idx -> [(row_idx, upper_bound), ...]
    and maintains the running row-sum for every hard constraint row.
    """

    def __init__(self, constraints):
        # row_idx -> upper_bound
        self._upper: List[int] = []
        # x_idx -> [(row_idx, upper)]
        self._var_to_rows: Dict[int, List[Tuple[int, int]]] = defaultdict(list)
        # row_idx -> current sum
        self._row_sum: List[int] = []

        for row_idx, (key, (x_indices, upper)) in enumerate(
                constraints.hard_constraints.items()):
            self._upper.append(upper)
            self._row_sum.append(0)
            for xidx in x_indices:
                self._var_to_rows[xidx].append((row_idx, upper))

    def can_add(self, xidx: int) -> bool:
        """Return True iff setting x[xidx]=1 won't violate any hard constraint."""
        for row_idx, upper in self._var_to_rows.get(xidx, []):
            if self._row_sum[row_idx] + 1 > upper:
                return False
        return True

    def add(self, xidx: int):
        for row_idx, _ in self._var_to_rows.get(xidx, []):
            self._row_sum[row_idx] += 1

    def remove(self, xidx: int):
        for row_idx, _ in self._var_to_rows.get(xidx, []):
            self._row_sum[row_idx] -= 1

    def reset(self):
        """Zero all row sums — reuse the tracker for a new offspring without rebuild."""
        self._row_sum = [0] * len(self._row_sum)

    def violation_count(self) -> int:
        upper = self._upper
        return sum(1 for i, s in enumerate(self._row_sum) if s > upper[i])


# -----------------------------------------------------------------------
# Solution Pool Statistics
# -----------------------------------------------------------------------

class SolutionPool:
    """
    Aggregates statistics over a collection of x_tensors.

    For each class, records which (tidx, rid) assignments appear and
    how often (frequency = count / pool_size).
    """

    def __init__(self, constraints):
        self.c = constraints
        # cid -> {(tidx, rid): count}
        self.freq: Dict[str, Dict[Tuple, int]] = defaultdict(lambda: defaultdict(int))
        self.pool_size = 0

    def add_x(self, x_tensor: torch.Tensor):
        assigned = torch.where(x_tensor > 0.5)[0].tolist()
        for xidx in assigned:
            cid, tidx, rid = self.c.xidx_to_x[xidx]
            self.freq[cid][(tidx, rid)] += 1
        self.pool_size += 1

    def frequency(self, cid: str, tidx: int, rid: str) -> float:
        if self.pool_size == 0:
            return 0.0
        return self.freq[cid].get((tidx, rid), 0) / self.pool_size


# -----------------------------------------------------------------------
# Greedy Merger
# -----------------------------------------------------------------------

class GreedyMerger:
    """
    Assigns classes one by one (most-constrained first) picking the
    highest-ranked feasible candidate at each step.
    """

    def __init__(self, constraints, evaluator, cfg: dict):
        self.c   = constraints
        self.ev  = evaluator
        self.cfg = cfg

        _, w_room, _, weights = constraints.objective_penalty
        self.w_time     = evaluator.w_time      # raw time penalty per xidx
        self.w_room_vec = w_room                # raw room penalty per xidx
        self.time_w, self.room_w, _ = weights

        self._class_order = self._build_class_order()

    def _build_class_order(self) -> List[str]:
        """Return class IDs in assignment priority order."""
        strategy = self.cfg.get("sort_classes", "most_constrained")
        all_cids = list(self.c.reader.classes.keys())

        if strategy == "natural":
            return all_cids

        if strategy == "fewest_options":
            # Count domain options per class from x dict (O(N), fast)
            from collections import Counter
            opt_counts = Counter(cid for (cid, _, _) in self.c.x.keys())
            return sorted(all_cids, key=lambda c: opt_counts.get(c, 0))

        # default: most_constrained — degree heuristic (hard constraint count)
        degree: Dict[str, int] = defaultdict(int)
        for _, (x_indices, _) in self.c.hard_constraints.items():
            seen_classes = set()
            for xidx in x_indices:
                cid, _, _ = self.c.xidx_to_x[xidx]
                seen_classes.add(cid)
            for cid in seen_classes:
                degree[cid] += 1

        return sorted(all_cids, key=lambda c: -degree.get(c, 0))

    def _score(self, xidx: int, pool: Optional[SolutionPool],
               scoring: str, freq_w: float) -> float:
        """Lower score = better candidate."""
        pen = (self.time_w * float(self.w_time[xidx]) +
               self.room_w * float(self.w_room_vec[xidx]))

        if scoring == "penalty" or pool is None:
            return pen

        cid, tidx, rid = self.c.xidx_to_x[xidx]
        freq = pool.frequency(cid, tidx, rid)

        if scoring == "frequency":
            return -freq   # higher frequency = better

        # combined: normalise both to [0,1] — use raw values since scale unknown;
        # just weight frequency inversely (more frequent = lower score)
        return (1.0 - freq_w) * pen - freq_w * freq

    def _candidates_for_class(self, cid: str,
                               pool: Optional[SolutionPool],
                               source: str) -> List[int]:
        """Return sorted list of x_indices for cid (best first)."""
        scoring  = self.cfg.get("scoring", "combined")
        freq_w   = float(self.cfg.get("freq_weight", 0.3))

        if source == "pool_only" and pool is not None:
            seen = pool.freq.get(cid, {})
            if seen:
                xindices = [
                    self.c.x[(cid, tidx, rid)]
                    for (tidx, rid) in seen
                    if (cid, tidx, rid) in self.c.x
                ]
            else:
                # Fall back to full domain if class never appeared
                xindices = self._full_domain_indices(cid)
        else:
            xindices = self._full_domain_indices(cid)

        return sorted(xindices, key=lambda xi: self._score(xi, pool, scoring, freq_w))

    def _full_domain_indices(self, cid: str) -> List[int]:
        indices = []
        for (c, tidx, rid), xidx in self.c.x.items():
            if c == cid:
                indices.append(xidx)
        return indices

    def merge(self, pool: Optional[SolutionPool],
              initial_x: Optional[torch.Tensor] = None) -> torch.Tensor:
        """
        If initial_x is provided, start from that feasible solution and try
        to improve individual class assignments (improvement mode).
        Otherwise build a solution from scratch (construction mode).
        """
        if initial_x is not None:
            return self._improve(pool, initial_x)
        return self._construct(pool)

    def _construct(self, pool: Optional[SolutionPool]) -> torch.Tensor:
        source  = self.cfg.get("candidate_source", "pool_only")
        tracker = ConstraintTracker(self.c)
        x       = torch.zeros_like(self.c.x_tensor)
        failed  = []

        for cid in self._class_order:
            if cid not in self.c.reader.classes:
                continue
            candidates = self._candidates_for_class(cid, pool, source)
            assigned   = False
            for xidx in candidates:
                if tracker.can_add(xidx):
                    x[xidx] = 1.0
                    tracker.add(xidx)
                    assigned = True
                    break
            if not assigned and source == "pool_only":
                for xidx in self._full_domain_indices(cid):
                    if tracker.can_add(xidx):
                        x[xidx] = 1.0
                        tracker.add(xidx)
                        assigned = True
                        break
            if not assigned:
                failed.append(cid)

        if failed:
            print(f"  [warn] {len(failed)} classes could not be assigned: {failed[:5]}")

        return x

    def _improve(self, pool: Optional[SolutionPool],
                 initial_x: torch.Tensor) -> torch.Tensor:
        """
        Start from a feasible initial_x and greedily improve class assignments.
        Each class is temporarily removed, the best feasible replacement is found,
        and the class is re-inserted. Feasibility is maintained throughout.
        Repeats for num_passes until no improvement is made.
        """
        source    = self.cfg.get("candidate_source", "pool_only")
        scoring   = self.cfg.get("scoring", "combined")
        freq_w    = float(self.cfg.get("freq_weight", 0.3))
        num_passes = int(self.cfg.get("num_passes", 1))

        tracker = ConstraintTracker(self.c)
        x = initial_x.clone()

        # Populate tracker from initial solution
        for xidx in torch.where(x > 0.5)[0].tolist():
            tracker.add(xidx)

        # class -> current xidx
        class_to_xidx: Dict[str, int] = {}
        for xidx in torch.where(x > 0.5)[0].tolist():
            cid, _, _ = self.c.xidx_to_x[xidx]
            class_to_xidx[cid] = xidx

        total_improvements = 0
        for pass_idx in range(num_passes):
            improvements = 0
            for cid in self._class_order:
                current_xidx = class_to_xidx.get(cid)
                if current_xidx is None:
                    continue

                tracker.remove(current_xidx)
                x[current_xidx] = 0.0

                candidates = self._candidates_for_class(cid, pool, source)
                # also include full domain if pool_only might miss options
                if source == "pool_only":
                    seen = set(candidates)
                    candidates = candidates + [
                        xi for xi in self._full_domain_indices(cid) if xi not in seen
                    ]

                best_xidx  = current_xidx
                best_score = self._score(current_xidx, pool, scoring, freq_w)
                for xidx in candidates:
                    if not tracker.can_add(xidx):
                        continue
                    score = self._score(xidx, pool, scoring, freq_w)
                    if score < best_score:
                        best_score = score
                        best_xidx  = xidx

                x[best_xidx] = 1.0
                tracker.add(best_xidx)
                class_to_xidx[cid] = best_xidx
                if best_xidx != current_xidx:
                    improvements += 1

            total_improvements += improvements
            print(f"  Pass {pass_idx+1}: improved {improvements} class assignments")
            if improvements == 0:
                break

        print(f"  Total improvements: {total_improvements}")
        return x


# -----------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------

def run_merging(cfg: dict, constraints, loader, evaluator,
                pool_data: list, pool_costs: list,
                instance: str, output_dir: pathlib.Path):
    """
    Main entry point called from main.py.

    pool_data : list of (path_str, x_tensor) from main.py's evaluate_solution_pool
    pool_costs: list of cost dicts (parallel with pool_data)

    Returns (best_x_tensor, best_cost_dict).
    """
    strategy = cfg.get("strategy", "greedy")
    print(f"\n{'='*60}")
    print(f"Running merging  strategy={strategy}")

    # Build pool statistics
    sol_pool = SolutionPool(constraints)
    for path, x in pool_data:
        sol_pool.add_x(x)
    print(f"Pool size: {sol_pool.pool_size} solutions")

    # Find the best valid pool solution (used as initial solution for improvement strategy).
    valid_indices = [i for i, c in enumerate(pool_costs) if c.get("valid", True)]
    best_candidates = valid_indices or list(range(len(pool_costs)))
    best_pool_idx = min(best_candidates, key=lambda i: pool_costs[i]["total"])
    best_pool_x   = pool_data[best_pool_idx][1]

    # Run merger
    t0 = time.time()
    if strategy == "crossover":
        from .crossover import CrossoverMerger
        merger   = CrossoverMerger(constraints, evaluator, cfg)
        merged_x, _ = merger.run(pool_data, pool_costs, sol_pool)
    else:
        merger = GreedyMerger(constraints, evaluator, cfg)
        if strategy == "improve_from_best":
            merged_x = merger.merge(sol_pool, initial_x=best_pool_x)
        elif strategy in ("greedy", "frequency"):
            merged_x = merger.merge(sol_pool)
        else:
            merged_x = merger.merge(None)
    elapsed = time.time() - t0

    # Evaluate
    feasible    = evaluator.is_feasible(merged_x)
    merged_cost = evaluator.evaluate(merged_x)
    pool_best   = pool_costs[best_pool_idx]["total"]
    improve     = (pool_best - merged_cost["total"]) / pool_best * 100 if pool_best > 0 else 0.0

    print(f"Merge time : {elapsed:.2f}s")
    print(f"Feasible   : {feasible}")
    if not feasible:
        viol = evaluator.check_violations(merged_x)
        print(f"  Unassigned    : {len(viol['unassigned'])}")
        print(f"  Multi-assigned: {len(viol['multi_assigned'])}")
        print(f"  Hard violations: {viol['hard_violations']}")
    print(f"Merged cost: total={merged_cost['total']:.1f}  "
          f"time={merged_cost['time']:.1f}  "
          f"room={merged_cost['room']:.1f}  "
          f"dist={merged_cost['distribution']:.1f}")
    print(f"Pool best  : {pool_best:.1f}  improvement: {improve:+.2f}%")

    # Compare with pool best.
    best_pool_path = pool_data[best_pool_idx][0]
    print(f"Pool best solution: {pathlib.Path(best_pool_path).name}")

    # Save merged solution
    output_dir = pathlib.Path(output_dir)
    out_path   = output_dir / f"{instance}_merged_{strategy}.xml"
    sol_dict   = loader.decode(merged_x, constraints)
    loader.save_xml(sol_dict, constraints.reader, str(out_path),
                    meta={"technique": f"merging-{strategy}"})
    print(f"Saved: {out_path}")

    return merged_x, merged_cost, str(out_path)
