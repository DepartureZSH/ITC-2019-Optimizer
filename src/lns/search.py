import math
import pathlib
import random
import time
from collections import defaultdict
from typing import Dict, List, Set, Tuple

import torch

from src.merging.greedy import ConstraintTracker
from src.solution_io.local_validator import Assignment


class LargeNeighborhoodSearch:
    """
    Destroy-and-repair LNS baseline.

    This implementation avoids external mathematical-programming solvers: it removes a batch of
    classes from the incumbent and greedily repairs them while maintaining hard
    constraints. It gives Phase 2 a working baseline directly from existing XML solutions.
    """

    def __init__(self, constraints, evaluator, cfg: dict):
        self.c = constraints
        self.ev = evaluator
        self.cfg = cfg
        self.tracker = ConstraintTracker(constraints)
        self._cid_domain: Dict[str, List[int]] = defaultdict(list)
        for (cid, _, _), xidx in self.c.x.items():
            self._cid_domain[cid].append(xidx)

        self.w_time = evaluator.w_time
        self.w_room = evaluator.w_room
        self.time_weight = evaluator.time_weight
        self.room_weight = evaluator.room_weight
        self.validator = getattr(evaluator, "local_validator", None)
        self.dist_weight = self.validator.weights["distribution"] if self.validator else evaluator.dist_weight
        self._xidx_assignment_cache = {}
        self._affected_score_cache = {}
        self._soft_constraints = self.c.reader.distributions.get("soft_constraints", [])
        self._cid_to_soft_rows: Dict[str, List[int]] = defaultdict(list)
        for row_idx, constraint in enumerate(self._soft_constraints):
            for cid in constraint.get("classes", []):
                self._cid_to_soft_rows[cid].append(row_idx)
        self.destroy_stats = {"random": 0, "high_distribution": 0, "marl_guided": 0, "fallback": 0}
        self._marl_q: Dict[str, float] = defaultdict(float)
        self._marl_count: Dict[str, int] = defaultdict(int)

    def _class_map(self, x_tensor: torch.Tensor) -> Dict[str, int]:
        result = {}
        for xidx in torch.where(x_tensor > 0.5)[0].tolist():
            cid, _, _ = self.c.xidx_to_x[xidx]
            result[cid] = xidx
        return result

    def _local_score(self, xidx: int) -> float:
        return (
            float(self.w_time[xidx]) * self.time_weight
            + float(self.w_room[xidx]) * self.room_weight
        )

    def _assignment_for_xidx(self, xidx: int) -> Assignment:
        if xidx in self._xidx_assignment_cache:
            return self._xidx_assignment_cache[xidx]

        cid, tidx, rid = self.c.xidx_to_x[xidx]
        topt = self.c.reader.classes[cid]["time_options"][tidx]
        weeks, days, start, length = topt["optional_time_bits"]
        room = rid if rid != "dummy" else None
        room_penalty = 0
        if room is not None:
            for option in self.c.reader.classes[cid]["room_options"]:
                if str(option["id"]) == str(room):
                    room_penalty = int(option.get("penalty", 0))
                    break

        assignment = Assignment(
            cid=cid,
            weeks=weeks,
            days=days,
            start=int(start),
            length=int(length),
            room=room,
            time_penalty=int(topt.get("penalty", 0)),
            room_penalty=room_penalty,
        )
        self._xidx_assignment_cache[xidx] = assignment
        return assignment

    def _assigned_xidx_map(self, x: torch.Tensor) -> Dict[str, int]:
        result = {}
        for xidx in torch.where(x > 0.5)[0].tolist():
            cid, _, _ = self.c.xidx_to_x[xidx]
            result[cid] = int(xidx)
        return result

    def _soft_constraint_cost(self, row_idx: int, assigned_map: Dict[str, int]) -> float:
        constraint = self._soft_constraints[row_idx]
        relevant = tuple(
            sorted(
                (cid, assigned_map[cid])
                for cid in constraint.get("classes", [])
                if cid in assigned_map
            )
        )
        key = (row_idx, relevant)
        if key in self._affected_score_cache:
            return self._affected_score_cache[key]

        assignments = {
            cid: self._assignment_for_xidx(xidx)
            for cid, xidx in relevant
        }
        count = self.validator._constraint_violation_count(constraint, assignments, hard=False)
        penalty = int(constraint.get("penalty", 0))
        ctype = constraint["type"]
        if ctype.startswith(("MaxDayLoad", "MaxBreaks", "MaxBlock")):
            cost = float(count)
        else:
            cost = float(count * penalty)

        self._affected_score_cache[key] = cost
        return cost

    def _affected_distribution_score(self, assigned_map: Dict[str, int], cid: str) -> float:
        if self.validator is None:
            return 0.0
        raw_cost = 0.0
        for row_idx in self._cid_to_soft_rows.get(cid, []):
            raw_cost += self._soft_constraint_cost(row_idx, assigned_map)
        return raw_cost * self.dist_weight

    def _candidate_incremental_score(self, assigned_map_base: Dict[str, int], cid: str, xidx: int) -> float:
        assigned_map = dict(assigned_map_base)
        assigned_map[cid] = xidx
        return self._local_score(xidx) + self._affected_distribution_score(assigned_map, cid)

    def _candidate_order(self, x: torch.Tensor, cid: str, tracker: ConstraintTracker = None) -> List[int]:
        """
        Rank repair candidates.

        validator_delta uses an official-aligned affected-distribution scorer:
        candidates are first pre-filtered by local time+room score, then only
        soft distribution rows involving the repaired class are recomputed.
        Final solutions are still evaluated by the complete validator.
        """
        tracker = tracker or self.tracker
        candidates = sorted(self._cid_domain.get(cid, []), key=self._local_score)
        scoring = self.cfg.get("repair_scoring", "validator_delta")
        limit = int(self.cfg.get("repair_candidate_limit", 40))

        if scoring in ("local", "time_room"):
            return candidates

        if limit > 0:
            candidates = candidates[:limit]

        scored = []
        assigned_map_base = self._assigned_xidx_map(x)
        for xidx in candidates:
            if not tracker.can_add(xidx):
                continue
            if self.validator is None:
                x[xidx] = 1.0
                score = self.ev.evaluate(x)["total"]
                x[xidx] = 0.0
            else:
                score = self._candidate_incremental_score(assigned_map_base, cid, xidx)
            scored.append((score, self._local_score(xidx), xidx))

        return [xidx for _score, _local, xidx in sorted(scored)]

    def _clone_tracker_for_x(self, x: torch.Tensor) -> ConstraintTracker:
        tracker = ConstraintTracker(self.c)
        for xidx in torch.where(x > 0.5)[0].tolist():
            tracker.add(xidx)
        return tracker

    def _copy_tracker(self, tracker: ConstraintTracker) -> ConstraintTracker:
        new_tracker = object.__new__(ConstraintTracker)
        new_tracker._upper = tracker._upper
        new_tracker._var_to_rows = tracker._var_to_rows
        new_tracker._row_sum = list(tracker._row_sum)
        return new_tracker

    def _destroy_classes(self, x_current: torch.Tensor, class_to_xidx: Dict[str, int], destroy_size: int) -> List[str]:
        strategy = self.cfg.get("destroy_strategy", "random")
        if strategy == "mixed":
            high_prob = float(self.cfg.get("mixed_high_distribution_prob", 0.7))
            strategy = "high_distribution" if random.random() < high_prob else "random"

        if strategy in {"marl", "marl_guided"}:
            cids = self._marl_guided_classes(x_current, class_to_xidx, destroy_size)
            if cids:
                self.destroy_stats["marl_guided"] += 1
                return cids
            self.destroy_stats["fallback"] += 1

        if strategy == "high_distribution":
            cids = self._high_distribution_classes(x_current, class_to_xidx, destroy_size)
            if cids:
                self.destroy_stats["high_distribution"] += 1
                return cids
            self.destroy_stats["fallback"] += 1

        cids = list(class_to_xidx.keys())
        self.destroy_stats["random"] += 1
        if destroy_size >= len(cids):
            return cids
        return random.sample(cids, destroy_size)

    def _high_distribution_classes(
        self,
        x_current: torch.Tensor,
        class_to_xidx: Dict[str, int],
        destroy_size: int,
    ) -> List[str]:
        validator = getattr(self.ev, "local_validator", None)
        if validator is None:
            return []

        scores = validator.soft_violation_class_scores_from_x(x_current, self.c)
        scored_cids = [cid for cid in scores if cid in class_to_xidx]
        if not scored_cids:
            return []

        selected = []
        available = set(scored_cids)
        while available and len(selected) < destroy_size:
            candidates = list(available)
            weights = [max(scores[cid], 1e-6) for cid in candidates]
            cid = random.choices(candidates, weights=weights, k=1)[0]
            selected.append(cid)
            available.remove(cid)

        if len(selected) < destroy_size:
            remaining = [cid for cid in class_to_xidx if cid not in selected]
            selected.extend(random.sample(remaining, min(destroy_size - len(selected), len(remaining))))

        return selected

    def _marl_guided_classes(
        self,
        x_current: torch.Tensor,
        class_to_xidx: Dict[str, int],
        destroy_size: int,
    ) -> List[str]:
        """
        Lightweight MARL-style destroy policy.

        Each class acts as an independent agent with a learned Q preference.
        A centralized scorer mixes Q with current validator-derived features,
        then samples a cooperative destroy set. Rewards are assigned back to
        the selected class agents after repair/evaluation in search().
        """
        cids = list(class_to_xidx.keys())
        if not cids:
            return []
        if destroy_size >= len(cids):
            return cids

        epsilon = float(self.cfg.get("marl_epsilon", 0.10))
        if random.random() < epsilon:
            return random.sample(cids, destroy_size)

        validator = getattr(self.ev, "local_validator", None)
        soft_scores = validator.soft_violation_class_scores_from_x(x_current, self.c) if validator else {}
        max_soft = max(soft_scores.values(), default=0.0)

        local_scores = {cid: self._local_score(xidx) for cid, xidx in class_to_xidx.items()}
        max_local = max(local_scores.values(), default=0.0)

        q_weight = float(self.cfg.get("marl_q_weight", 1.0))
        dist_weight = float(self.cfg.get("marl_distribution_weight", 0.7))
        local_weight = float(self.cfg.get("marl_local_weight", 0.2))
        difficulty_weight = float(self.cfg.get("marl_difficulty_weight", 0.1))
        temperature = max(float(self.cfg.get("marl_temperature", 1.0)), 1e-6)

        scored = []
        for cid in cids:
            q = self._marl_q[cid]
            soft = soft_scores.get(cid, 0.0) / max(max_soft, 1e-9)
            local = local_scores.get(cid, 0.0) / max(max_local, 1e-9)
            domain_size = max(len(self._cid_domain.get(cid, [])), 1)
            difficulty = 1.0 / math.sqrt(domain_size)
            score = (
                q_weight * q
                + dist_weight * soft
                + local_weight * local
                + difficulty_weight * difficulty
            )
            scored.append((cid, score))

        selected = []
        available = scored
        while available and len(selected) < destroy_size:
            max_score = max(score for _cid, score in available)
            weights = [math.exp((score - max_score) / temperature) for _cid, score in available]
            pos = random.choices(range(len(available)), weights=weights, k=1)[0]
            cid, _score = available.pop(pos)
            selected.append(cid)

        return selected

    def _update_marl_policy(self, removed: Set[str], reward: float):
        if not removed:
            return
        alpha = float(self.cfg.get("marl_alpha", 0.20))
        reward = max(-1.0, min(1.0, float(reward)))
        for cid in removed:
            old_q = self._marl_q[cid]
            self._marl_q[cid] = old_q + alpha * (reward - old_q)
            self._marl_count[cid] += 1

    def _repair(self, base_x: torch.Tensor, removed: Set[str]) -> Tuple[torch.Tensor, bool]:
        if self.cfg.get("repair_method", "beam") == "beam":
            return self._beam_repair(base_x, removed)

        x = base_x.clone()
        self.tracker.reset()

        for xidx in torch.where(x > 0.5)[0].tolist():
            self.tracker.add(xidx)

        repair_order = sorted(
            removed,
            key=lambda cid: len(self._cid_domain.get(cid, [])),
        )

        for cid in repair_order:
            candidates = self._candidate_order(x, cid)
            placed = False
            for xidx in candidates:
                if self.tracker.can_add(xidx):
                    x[xidx] = 1.0
                    self.tracker.add(xidx)
                    placed = True
                    break
            if not placed:
                return x, False

        return x, True

    def _beam_repair(self, base_x: torch.Tensor, removed: Set[str]) -> Tuple[torch.Tensor, bool]:
        repair_order = sorted(
            removed,
            key=lambda cid: len(self._cid_domain.get(cid, [])),
        )
        beam_width = max(1, int(self.cfg.get("beam_width", 3)))
        beam = [(base_x.clone(), self._clone_tracker_for_x(base_x), 0.0)]

        for cid in repair_order:
            next_beam = []
            for partial_x, partial_tracker, _partial_score in beam:
                candidates = self._candidate_order(partial_x, cid, partial_tracker)
                assigned_map_base = self._assigned_xidx_map(partial_x)
                for xidx in candidates:
                    if not partial_tracker.can_add(xidx):
                        continue
                    x_new = partial_x.clone()
                    x_new[xidx] = 1.0
                    tracker_new = self._copy_tracker(partial_tracker)
                    tracker_new.add(xidx)
                    score = _partial_score + self._candidate_incremental_score(assigned_map_base, cid, xidx)
                    next_beam.append((x_new, tracker_new, score))

            if not next_beam:
                return base_x, False

            next_beam.sort(key=lambda item: item[2])
            beam = next_beam[:beam_width]

        for x_candidate, _tracker, _score in beam:
            if self.ev.is_feasible(x_candidate):
                return x_candidate, True
        return beam[0][0], False

    def step(self, x_current: torch.Tensor, destroy_size: int) -> Tuple[torch.Tensor, bool, Set[str]]:
        class_to_xidx = self._class_map(x_current)
        removed = set(self._destroy_classes(x_current, class_to_xidx, destroy_size))

        base_x = x_current.clone()
        for cid in removed:
            old_idx = class_to_xidx[cid]
            base_x[old_idx] = 0.0

        candidate_x, repaired = self._repair(base_x, removed)
        return candidate_x, repaired, removed

    def search(self, x_init: torch.Tensor):
        seed = self.cfg.get("seed", None)
        if seed is not None:
            random.seed(seed)
            torch.manual_seed(int(seed))

        max_iter = int(self.cfg.get("max_iter", 500))
        destroy_size = int(self.cfg.get("destroy_size", 8))
        acceptance = self.cfg.get("acceptance", "improvement")
        temperature = float(self.cfg.get("temperature", 100.0))
        cooling = float(self.cfg.get("cooling", 0.995))
        log_every = int(self.cfg.get("log_every", 50))

        x_current = x_init.clone()
        current_cost = self.ev.evaluate(x_current)
        best_x = x_current.clone()
        best_cost = dict(current_cost)

        accepted = 0
        feasible_repairs = 0

        for iteration in range(1, max_iter + 1):
            candidate_x, repaired, removed = self.step(x_current, destroy_size)
            if not repaired or not self.ev.is_feasible(candidate_x):
                if self.cfg.get("destroy_strategy", "random") in {"marl", "marl_guided"}:
                    self._update_marl_policy(removed, -float(self.cfg.get("marl_failed_reward", 0.02)))
                temperature *= cooling
                continue

            feasible_repairs += 1
            candidate_cost = self.ev.evaluate(candidate_x)
            delta = candidate_cost["total"] - current_cost["total"]
            if self.cfg.get("destroy_strategy", "random") in {"marl", "marl_guided"}:
                reward_scale = max(abs(float(current_cost["total"])), 1.0)
                self._update_marl_policy(removed, -float(delta) / reward_scale)
            accept = delta < 0.0
            if not accept and acceptance == "sa":
                accept = random.random() < math.exp(-delta / max(temperature, 1e-9))

            if accept:
                x_current = candidate_x
                current_cost = candidate_cost
                accepted += 1
                if current_cost["total"] < best_cost["total"]:
                    best_x = x_current.clone()
                    best_cost = dict(current_cost)

            temperature *= cooling
            if iteration % log_every == 0:
                print(
                    f"  iter={iteration} repaired={feasible_repairs} "
                    f"current={current_cost['total']:.1f} best={best_cost['total']:.1f}"
                )

        return best_x, {
            "cost": best_cost,
            "iterations": max_iter,
            "accepted": accepted,
            "feasible_repairs": feasible_repairs,
            "destroy_stats": dict(self.destroy_stats),
            "marl_top_q": self._top_marl_q(),
        }

    def _top_marl_q(self, limit: int = 10):
        items = [(cid, q, self._marl_count[cid]) for cid, q in self._marl_q.items() if self._marl_count[cid] > 0]
        items.sort(key=lambda item: item[1], reverse=True)
        return items[:limit]


def run_lns(
    cfg: dict,
    constraints,
    loader,
    evaluator,
    pool_data: list,
    pool_costs: list,
    instance: str,
    output_dir: pathlib.Path,
):
    print(f"\n{'=' * 60}")
    print(
        f"Running lns  destroy_size={cfg.get('destroy_size', 8)}  "
        f"destroy_strategy={cfg.get('destroy_strategy', 'random')}  "
        f"acceptance={cfg.get('acceptance', 'improvement')}  "
        f"repair_method={cfg.get('repair_method', 'beam')}  "
        f"repair_scoring={cfg.get('repair_scoring', 'validator_delta')}  "
        f"candidate_limit={cfg.get('repair_candidate_limit', 40)}  "
        f"beam_width={cfg.get('beam_width', 3)}"
    )

    if not pool_data:
        raise ValueError("LNS needs at least one initial solution in the solution pool")

    valid_indices = [i for i, c in enumerate(pool_costs) if c.get("valid", True)]
    best_candidates = valid_indices or list(range(len(pool_costs)))
    best_pool_idx = min(best_candidates, key=lambda i: pool_costs[i]["total"])
    x_init = pool_data[best_pool_idx][1]
    pool_best = pool_costs[best_pool_idx]
    print(f"Initial pool best: total={pool_best['total']:.1f} valid={pool_best.get('valid', True)}")

    t0 = time.time()
    searcher = LargeNeighborhoodSearch(constraints, evaluator, cfg)
    result_x, result = searcher.search(x_init)
    elapsed = time.time() - t0

    result_cost = evaluator.evaluate(result_x)
    feasible = evaluator.is_feasible(result_x)
    improve = (pool_best["total"] - result_cost["total"]) / pool_best["total"] * 100 if pool_best["total"] > 0 else 0.0

    print(f"LNS time   : {elapsed:.2f}s")
    print(f"Iterations : {result.get('iterations', 0)}")
    print(f"Accepted   : {result.get('accepted', 0)}")
    print(f"Repairs    : {result.get('feasible_repairs', 0)}")
    if result.get("destroy_stats"):
        print(f"Destroy    : {result['destroy_stats']}")
    if result.get("marl_top_q"):
        formatted = ", ".join(f"{cid}:{q:.3f}/{count}" for cid, q, count in result["marl_top_q"])
        print(f"MARL top Q : {formatted}")
    print(f"Feasible   : {feasible}")
    if not feasible:
        viol = evaluator.check_violations(result_x)
        print(f"  Unassigned    : {len(viol['unassigned'])}")
        print(f"  Multi-assigned: {len(viol['multi_assigned'])}")
        print(f"  Hard violations: {viol['hard_violations']}")
    print(
        f"LNS cost  : total={result_cost['total']:.1f}  "
        f"time={result_cost['time']:.1f}  "
        f"room={result_cost['room']:.1f}  "
        f"dist={result_cost['distribution']:.1f}"
    )
    print(f"Pool best : {pool_best['total']:.1f}  improvement: {improve:+.2f}%")

    output_dir = pathlib.Path(output_dir)
    out_path = output_dir / f"{instance}_lns.xml"
    sol_dict = loader.decode(result_x, constraints)
    loader.save_xml(sol_dict, constraints.reader, str(out_path), meta={"technique": "lns-destroy-repair"})
    print(f"Saved: {out_path}")

    return result_x, result_cost, str(out_path)
