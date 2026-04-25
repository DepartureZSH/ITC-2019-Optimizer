"""
Solution Pool Crossover — Approach 2.3

For each pair of parent solutions, produce offspring by uniform per-class
crossover: each class inherits its assignment from one parent at random.
When both parents' choices conflict with already-placed classes, a greedy
repair uses the full domain to restore feasibility.

Multiple offspring are generated from the top-k pool solutions and the
best feasible one is returned.
"""

import random
import time
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

import torch

from .greedy import ConstraintTracker, SolutionPool


class CrossoverMerger:

    def __init__(self, constraints, evaluator, cfg: dict):
        self.c   = constraints
        self.ev  = evaluator
        self.cfg = cfg
        # Pre-build cid → [xidx, ...] for O(1) full-domain access
        self._cid_domain: Dict[str, List[int]] = defaultdict(list)
        for (cid, _, _), xidx in self.c.x.items():
            self._cid_domain[cid].append(xidx)
        # Build most-constrained order (degree heuristic) once
        self._cid_order: List[str] = self._build_cid_order()
        # Build shared tracker once — reuse via reset() per offspring
        self._shared_tracker = ConstraintTracker(self.c)

    def _build_cid_order(self) -> List[str]:
        """Most-constrained first: sorted by hard-constraint degree descending."""
        degree: Dict[str, int] = defaultdict(int)
        for _, (x_indices, _) in self.c.hard_constraints.items():
            seen = set()
            for xidx in x_indices:
                cid, _, _ = self.c.xidx_to_x[xidx]
                seen.add(cid)
            for cid in seen:
                degree[cid] += 1
        all_cids = list(self.c.reader.classes.keys())
        return sorted(all_cids, key=lambda c: -degree.get(c, 0))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _class_map(self, x: torch.Tensor) -> Dict[str, int]:
        """cid → xidx for all classes assigned in x."""
        result: Dict[str, int] = {}
        for xidx in torch.where(x > 0.5)[0].tolist():
            cid, _, _ = self.c.xidx_to_x[xidx]
            result[cid] = xidx
        return result

    # ------------------------------------------------------------------
    # Single crossover
    # ------------------------------------------------------------------

    def crossover(self, x_a: torch.Tensor, x_b: torch.Tensor) -> torch.Tensor:
        """
        Produce one offspring by uniform per-class crossover.

        Classes are processed in most-constrained-first order to reduce
        repair failures. For each class the primary parent is chosen at
        random (50/50). If that choice conflicts, the other parent is tried.
        Classes still unplaced after both parents are repaired greedily
        from the full domain.  Uses a shared tracker (reset each call).
        """
        map_a = self._class_map(x_a)
        map_b = self._class_map(x_b)

        tracker = self._shared_tracker
        tracker.reset()

        x        = torch.zeros_like(self.c.x_tensor)
        deferred: List[str] = []

        for cid in self._cid_order:
            xa = map_a.get(cid)
            xb = map_b.get(cid)

            # Random primary / secondary parent
            if random.random() < 0.5:
                primary, secondary = xa, xb
            else:
                primary, secondary = xb, xa

            placed = False
            for xidx in (v for v in [primary, secondary] if v is not None):
                if tracker.can_add(xidx):
                    x[xidx] = 1.0
                    tracker.add(xidx)
                    placed = True
                    break

            if not placed:
                deferred.append(cid)

        # Greedy repair: try full domain for unplaced classes
        for cid in deferred:
            for xidx in self._cid_domain.get(cid, []):
                if tracker.can_add(xidx):
                    x[xidx] = 1.0
                    tracker.add(xidx)
                    break

        return x

    # ------------------------------------------------------------------
    # Population run
    # ------------------------------------------------------------------

    def run(self, pool_data: list, pool_costs: list,
            pool: SolutionPool) -> Tuple[torch.Tensor, dict]:
        """
        Generate num_offspring crossover solutions using the top-k pool
        members as parents.  Returns (best_x, best_cost_dict).
        """
        num_offspring = int(self.cfg.get("num_offspring", 100))
        top_k         = int(self.cfg.get("top_k", 10))
        seed          = self.cfg.get("seed", None)

        if seed is not None:
            random.seed(seed)

        # Select top-k pool solutions as parent candidates
        ranked    = sorted(range(len(pool_costs)),
                           key=lambda i: pool_costs[i]["total"])[:top_k]
        top_xs    = [pool_data[i][1] for i in ranked]
        top_costs = [pool_costs[i] for i in ranked]

        print(f"  Parents: top-{len(top_xs)}  "
              f"(best={top_costs[0]['total']:.1f}, "
              f"worst={top_costs[-1]['total']:.1f})")

        # Start from the best pool solution as the incumbent.
        best_x    = top_xs[0]
        best_cost = self.ev.evaluate(best_x)

        feasible_count = 0
        improve_count  = 0

        for k in range(num_offspring):
            # Sample two distinct parents
            if len(top_xs) < 2:
                break
            pa, pb = random.sample(range(len(top_xs)), 2)
            offspring = self.crossover(top_xs[pa], top_xs[pb])

            if not self.ev.is_feasible(offspring):
                continue

            feasible_count += 1
            cost = self.ev.evaluate(offspring)
            if cost["total"] < best_cost["total"]:
                best_x    = offspring
                best_cost = cost
                improve_count += 1

        print(f"  Feasible offspring : {feasible_count}/{num_offspring}")
        print(f"  Improvements found : {improve_count}")
        return best_x, best_cost
