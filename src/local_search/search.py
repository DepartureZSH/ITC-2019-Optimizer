import math
import pathlib
import random
import time
from typing import Iterable, Optional, Tuple

import torch

from .delta_eval import DeltaEvaluator
from .neighborhood import NeighborhoodGenerator


class LocalSearch:
    """Local-search driver supporting best, first, and SA acceptance."""

    def __init__(self, constraints, evaluator, device: Optional[str] = None):
        self.c = constraints
        self.evaluator = evaluator
        self.device = device or getattr(constraints, "device", "cpu")
        self.neighborhood = NeighborhoodGenerator(constraints)
        self.delta_eval = DeltaEvaluator(constraints, evaluator)

    def search(self, x_init: torch.Tensor, config: dict) -> Tuple[torch.Tensor, dict]:
        method = config.get("method", config.get("acceptance", "best_improvement"))
        max_iter = int(config.get("max_iter", 10000))
        seed = config.get("seed", None)
        if seed is not None:
            random.seed(seed)
            torch.manual_seed(int(seed))

        if method == "best_improvement":
            return self._best_improvement(x_init, max_iter, config)
        if method == "first_improvement":
            return self._first_improvement(x_init, max_iter, config)
        if method in ("sa", "simulated_annealing"):
            return self._simulated_annealing(x_init, max_iter, config)
        raise ValueError(f"Unknown local-search method: {method}")

    def _moves(self, x_tensor: torch.Tensor, mode: str, shuffle: bool = False) -> Iterable[dict]:
        if mode == "room_swap":
            return self.neighborhood.room_swap_neighbors(x_tensor, shuffle=shuffle)
        return self.neighborhood.single_class_neighbors(x_tensor, shuffle=shuffle)

    def _best_improvement(self, x_init: torch.Tensor, max_iter: int, config: dict):
        x = x_init.clone()
        best_cost = self.evaluator.evaluate(x)
        move_mode = config.get("neighborhood", "single_class")
        iterations = 0
        accepted = 0

        for iterations in range(1, max_iter + 1):
            best_move = None
            best_delta = 0.0
            checked = 0
            for move in self._moves(x, move_mode):
                checked += 1
                delta, feasible = self.delta_eval.delta(x, move)
                if feasible and delta < best_delta:
                    best_delta = delta
                    best_move = move

            if best_move is None:
                break

            x = self.delta_eval.apply_neighbor(x, best_move)
            best_cost = self.evaluator.evaluate(x)
            accepted += 1
            if iterations % int(config.get("log_every", 25)) == 0:
                print(f"  iter={iterations} checked={checked} total={best_cost['total']:.1f}")

        return x, {"cost": best_cost, "iterations": iterations, "accepted": accepted}

    def _first_improvement(self, x_init: torch.Tensor, max_iter: int, config: dict):
        x = x_init.clone()
        best_cost = self.evaluator.evaluate(x)
        move_mode = config.get("neighborhood", "single_class")
        iterations = 0
        accepted = 0

        for iterations in range(1, max_iter + 1):
            accepted_this_iter = False
            for move in self._moves(x, move_mode, shuffle=True):
                delta, feasible = self.delta_eval.delta(x, move)
                if feasible and delta < -1e-9:
                    x = self.delta_eval.apply_neighbor(x, move)
                    best_cost = self.evaluator.evaluate(x)
                    accepted += 1
                    accepted_this_iter = True
                    break
            if not accepted_this_iter:
                break
            if iterations % int(config.get("log_every", 100)) == 0:
                print(f"  iter={iterations} total={best_cost['total']:.1f}")

        return x, {"cost": best_cost, "iterations": iterations, "accepted": accepted}

    def _simulated_annealing(self, x_init: torch.Tensor, max_iter: int, config: dict):
        x = x_init.clone()
        current_cost = self.evaluator.evaluate(x)
        best_x = x.clone()
        best_cost = dict(current_cost)
        temperature = float(config.get("sa_temperature", 100.0))
        cooling = float(config.get("sa_cooling", 0.995))
        min_temperature = float(config.get("sa_min_temperature", 1e-6))
        move_mode = config.get("neighborhood", "single_class")
        accepted = 0
        improving = 0
        no_move = 0

        for iteration in range(1, max_iter + 1):
            cid = None
            if move_mode != "room_swap":
                cid = self.neighborhood.random_class(x)
            moves = list(
                self.neighborhood.single_class_neighbors(x, cid=cid, shuffle=True)
                if move_mode != "room_swap"
                else self.neighborhood.room_swap_neighbors(x, shuffle=True)
            )
            if not moves:
                no_move += 1
                continue

            move = random.choice(moves)
            delta, feasible = self.delta_eval.delta(x, move)
            if not feasible:
                temperature = max(min_temperature, temperature * cooling)
                continue

            accept = delta < 0.0
            if not accept and temperature > min_temperature:
                accept = random.random() < math.exp(-delta / max(temperature, min_temperature))

            if accept:
                x = self.delta_eval.apply_neighbor(x, move)
                current_cost = self.evaluator.evaluate(x)
                accepted += 1
                if delta < 0.0:
                    improving += 1
                if current_cost["total"] < best_cost["total"]:
                    best_x = x.clone()
                    best_cost = dict(current_cost)

            temperature = max(min_temperature, temperature * cooling)
            if iteration % int(config.get("log_every", 1000)) == 0:
                print(
                    f"  iter={iteration} temp={temperature:.4f} "
                    f"current={current_cost['total']:.1f} best={best_cost['total']:.1f}"
                )

        return best_x, {
            "cost": best_cost,
            "iterations": max_iter,
            "accepted": accepted,
            "improving": improving,
            "no_move": no_move,
        }

    def search_multi_start(self, x_list, config: dict):
        best_x = None
        best_result = None
        for idx, x_init in enumerate(x_list):
            print(f"  Restart {idx + 1}/{len(x_list)}")
            x, result = self.search(x_init, config)
            if best_result is None or result["cost"]["total"] < best_result["cost"]["total"]:
                best_x = x
                best_result = result
        return best_x, best_result


def run_local_search(
    cfg: dict,
    constraints,
    loader,
    evaluator,
    pool_data: list,
    pool_costs: list,
    instance: str,
    output_dir: pathlib.Path,
):
    """Entry point called by main.py."""
    print(f"\n{'=' * 60}")
    acceptance = cfg.get("acceptance", "best_improvement")
    neighborhood = cfg.get("neighborhood", "single_class")
    print(f"Running local_search  acceptance={acceptance}  neighborhood={neighborhood}")

    if not pool_data:
        raise ValueError("Local search needs at least one initial solution in the solution pool")

    valid_indices = [i for i, c in enumerate(pool_costs) if c.get("valid", True)]
    best_candidates = valid_indices or list(range(len(pool_costs)))
    best_pool_idx = min(best_candidates, key=lambda i: pool_costs[i]["total"])
    x_init = pool_data[best_pool_idx][1]
    pool_best = pool_costs[best_pool_idx]
    print(f"Initial pool best: total={pool_best['total']:.1f} valid={pool_best.get('valid', True)}")

    search_cfg = dict(cfg)
    search_cfg["method"] = acceptance

    t0 = time.time()
    searcher = LocalSearch(constraints, evaluator, device=getattr(constraints, "device", None))
    if cfg.get("multi_start", False):
        starts = [x for _, x in pool_data[: int(cfg.get("num_starts", min(5, len(pool_data))))]]
        result_x, result = searcher.search_multi_start(starts, search_cfg)
    else:
        result_x, result = searcher.search(x_init, search_cfg)
    elapsed = time.time() - t0

    result_cost = evaluator.evaluate(result_x)
    feasible = evaluator.is_feasible(result_x)
    improve = (pool_best["total"] - result_cost["total"]) / pool_best["total"] * 100 if pool_best["total"] > 0 else 0.0

    print(f"Search time : {elapsed:.2f}s")
    print(f"Iterations  : {result.get('iterations', 0)}")
    print(f"Accepted    : {result.get('accepted', 0)}")
    print(f"Feasible    : {feasible}")
    if not feasible:
        viol = evaluator.check_violations(result_x)
        print(f"  Unassigned    : {len(viol['unassigned'])}")
        print(f"  Multi-assigned: {len(viol['multi_assigned'])}")
        print(f"  Hard violations: {viol['hard_violations']}")
    print(
        f"Local cost : total={result_cost['total']:.1f}  "
        f"time={result_cost['time']:.1f}  "
        f"room={result_cost['room']:.1f}  "
        f"dist={result_cost['distribution']:.1f}"
    )
    print(f"Pool best  : {pool_best['total']:.1f}  improvement: {improve:+.2f}%")

    output_dir = pathlib.Path(output_dir)
    out_path = output_dir / f"{instance}_local_search_{acceptance}.xml"
    sol_dict = loader.decode(result_x, constraints)
    loader.save_xml(sol_dict, constraints.reader, str(out_path), meta={"technique": f"local-search-{acceptance}"})
    print(f"Saved: {out_path}")

    return result_x, result_cost, str(out_path)
