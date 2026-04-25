from collections import defaultdict
from typing import Dict, Iterable, List, Set, Tuple

import torch


class DeltaEvaluator:
    """
    Fast delta evaluator for local-search moves.

    The reverse indices map x variables to affected hard/soft constraint rows,
    so a candidate move only recomputes the rows it can change.
    """

    def __init__(self, constraints, evaluator):
        self.c = constraints
        self.evaluator = evaluator
        self.w_time = evaluator.w_time
        self.w_room = evaluator.w_room
        self.time_weight = evaluator.time_weight
        self.room_weight = evaluator.room_weight
        self.dist_weight = evaluator.dist_weight
        self.var_to_hard_rows: Dict[int, List[int]] = defaultdict(list)
        self.var_to_soft_rows: Dict[int, List[int]] = defaultdict(list)
        self.hard_rows: List[Tuple[List[int], float]] = []
        self.soft_rows: List[Tuple[List[int], float, float]] = []
        self._build_reverse_index()

    def _build_reverse_index(self):
        for row_idx, (_name, (x_indices, upper)) in enumerate(self.c.hard_constraints.items()):
            indices = list(x_indices)
            self.hard_rows.append((indices, float(upper)))
            for xidx in indices:
                self.var_to_hard_rows[int(xidx)].append(row_idx)

        for row_idx, (_name, (x_indices, upper, penalty)) in enumerate(self.c.soft_constraints.items()):
            indices = list(x_indices)
            self.soft_rows.append((indices, float(upper), float(penalty)))
            for xidx in indices:
                self.var_to_soft_rows[int(xidx)].append(row_idx)

    def get_affected_rows(self, old_indices: Iterable[int], new_indices: Iterable[int]):
        hard: Set[int] = set()
        soft: Set[int] = set()
        for xidx in list(old_indices) + list(new_indices):
            hard.update(self.var_to_hard_rows.get(int(xidx), []))
            soft.update(self.var_to_soft_rows.get(int(xidx), []))
        return hard, soft

    def _row_sum(self, x_tensor: torch.Tensor, indices: List[int]) -> float:
        if not indices:
            return 0.0
        return float(x_tensor[indices].sum().item())

    def _soft_subset_cost(self, x_tensor: torch.Tensor, rows: Iterable[int]) -> float:
        total = 0.0
        for row_idx in rows:
            indices, upper, penalty = self.soft_rows[row_idx]
            total += max(0.0, self._row_sum(x_tensor, indices) - upper) * penalty
        return total * self.dist_weight

    def _hard_subset_feasible(self, x_tensor: torch.Tensor, rows: Iterable[int]) -> bool:
        for row_idx in rows:
            indices, upper = self.hard_rows[row_idx]
            if self._row_sum(x_tensor, indices) - upper > 1e-6:
                return False
        return True

    def eval_subset(self, x_tensor: torch.Tensor, hard_rows, soft_rows) -> dict:
        return {
            "hard_feasible": self._hard_subset_feasible(x_tensor, hard_rows),
            "soft_cost": self._soft_subset_cost(x_tensor, soft_rows),
        }

    def _delta_for_indices(
        self,
        x_tensor: torch.Tensor,
        old_indices: List[int],
        new_indices: List[int],
    ) -> Tuple[float, bool]:
        hard_rows, soft_rows = self.get_affected_rows(old_indices, new_indices)
        old_soft = self._soft_subset_cost(x_tensor, soft_rows)

        x_new = x_tensor.clone()
        for idx in old_indices:
            x_new[idx] = 0.0
        for idx in new_indices:
            x_new[idx] = 1.0

        if not self._hard_subset_feasible(x_new, hard_rows):
            return float("inf"), False

        new_soft = self._soft_subset_cost(x_new, soft_rows)
        time_delta = float((self.w_time[new_indices].sum() - self.w_time[old_indices].sum()).item())
        room_delta = float((self.w_room[new_indices].sum() - self.w_room[old_indices].sum()).item())
        delta = time_delta * self.time_weight + room_delta * self.room_weight + (new_soft - old_soft)
        return delta, True

    def delta_single_class(self, x_tensor: torch.Tensor, move: dict) -> Tuple[float, bool]:
        return self._delta_for_indices(x_tensor, [move["old_idx"]], [move["new_idx"]])

    def delta_room_swap(self, x_tensor: torch.Tensor, move: dict) -> Tuple[float, bool]:
        return self._delta_for_indices(x_tensor, move["old_indices"], move["new_indices"])

    def delta(self, x_tensor: torch.Tensor, move: dict) -> Tuple[float, bool]:
        if move["type"] == "single_class":
            return self.delta_single_class(x_tensor, move)
        if move["type"] == "room_swap":
            return self.delta_room_swap(x_tensor, move)
        raise ValueError(f"Unknown move type: {move['type']}")

    def apply_neighbor(self, x_tensor: torch.Tensor, move: dict) -> torch.Tensor:
        x_new = x_tensor.clone()
        if move["type"] == "single_class":
            x_new[move["old_idx"]] = 0.0
            x_new[move["new_idx"]] = 1.0
            return x_new
        if move["type"] == "room_swap":
            for idx in move["old_indices"]:
                x_new[idx] = 0.0
            for idx in move["new_indices"]:
                x_new[idx] = 1.0
            return x_new
        raise ValueError(f"Unknown move type: {move['type']}")
