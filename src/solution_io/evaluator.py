import torch
from typing import Dict

from .local_validator import LocalValidator


class SolutionEvaluator:
    """
    Computes the three-component objective for ITC2019 (no student conflict).

    Objective = w_time * TimePenalty
              + w_room * RoomPenalty
              + w_dist * DistributionPenalty

    Raw penalties are stored in tensors, weights are applied at evaluation time.
    """

    def __init__(self, constraints):
        """
        Args:
            constraints: a fully built ConstraintsResolver_v2 instance
                         (build_model() must have been called).
        """
        self.c = constraints
        w_time, w_room, (soft_dist, soft_upper, soft_dist_cost), weights = constraints.objective_penalty
        self.w_time     = w_time          # (N,) - raw penalty values
        self.w_room     = w_room          # (N,) - raw penalty values
        self.soft_dist  = soft_dist       # sparse (num_soft, N)
        self.soft_upper = soft_upper.squeeze(0)   # (num_soft,)
        self.w_dist     = soft_dist_cost.squeeze(0)       # (num_soft,) - raw penalty values
        self.time_weight, self.room_weight, self.dist_weight = weights

        self._post_constraints = self._collect_post_constraints()
        self.local_validator = LocalValidator(constraints.reader)

    def _collect_post_constraints(self):
        """Collect constraints that need post-assignment computation."""
        pc = {'maxblock': [], 'maxdayload': [], 'maxdays': [], 'maxbreaks': []}
        for c in self.c.reader.distributions.get('hard_constraints', []):
            t = c['type']
            if t.startswith('MaxBlock'):
                pc['maxblock'].append((c, True))
            elif t.startswith('MaxDayLoad'):
                pc['maxdayload'].append((c, True))
            elif t.startswith('MaxDays'):
                pc['maxdays'].append((c, True))
            elif t.startswith('MaxBreaks'):
                pc['maxbreaks'].append((c, True))
        for c in self.c.reader.distributions.get('soft_constraints', []):
            t = c['type']
            if t.startswith('MaxBlock'):
                pc['maxblock'].append((c, False))
            elif t.startswith('MaxDayLoad'):
                pc['maxdayload'].append((c, False))
            elif t.startswith('MaxDays'):
                pc['maxdays'].append((c, False))
            elif t.startswith('MaxBreaks'):
                pc['maxbreaks'].append((c, False))
        return pc

    def _compute_maxblock_violation(self, x_tensor):
        """Compute MaxBlock violation from assigned solution."""
        x = x_tensor.float()
        assigned = torch.where(x > 0.5)[0].tolist()
        if not assigned:
            return 0

        c = self.c
        violations = 0
        nrWeeks = c.reader.nrWeeks

        for constraint, is_hard in self._post_constraints['maxblock']:
            ctype = constraint['type']
            classes = constraint['classes']
            penalty = constraint.get('penalty', 1)
            M, S = map(int, ctype.split('(')[1].rstrip(')').split(','))

            class_times = []
            for xidx in assigned:
                cid, tidx, rid = c.xidx_to_x[xidx]
                if cid in classes and cid in c.class_to_time_options:
                    topt, _ = c.class_to_time_options[cid][tidx]
                    w, d, start, length = topt['optional_time_bits']
                    class_times.append((cid, w, d, start, length))

            if len(class_times) < 2:
                continue

            overM_blocks = 0
            for w_idx in range(nrWeeks):
                for d_idx in range(c.reader.nrDays):
                    day_vars = []
                    for cid, weeks, days, start, length in class_times:
                        if w_idx < len(weeks) and weeks[w_idx] == '1' and d_idx < len(days) and days[d_idx] == '1':
                            day_vars.append((start, length))
                    if len(day_vars) < 2:
                        continue

                    day_vars = sorted(day_vars, key=lambda v: v[0])
                    blocks = []
                    current = [day_vars[0]]
                    for i in range(1, len(day_vars)):
                        s1, l1 = current[-1]
                        s2, l2 = day_vars[i]
                        if s1 + l1 + S >= s2:
                            current.append((s2, l2))
                        else:
                            blocks.append(current)
                            current = [(s2, l2)]
                    blocks.append(current)

                    for block in blocks:
                        if len(block) > 1:
                            block_len = block[-1][0] + block[-1][1] - block[0][0]
                            if block_len > M:
                                overM_blocks += 1

            avg_viol = int(overM_blocks / max(nrWeeks, 1))
            if avg_viol > 0:
                violations += penalty * avg_viol

        return violations

    def _compute_post_assignment_violations(self, x_tensor):
        """Compute all post-assignment constraint violations."""
        total = 0
        total += self._compute_maxblock_violation(x_tensor)
        return total

    # ------------------------------------------------------------------
    # Cost
    # ------------------------------------------------------------------

    def evaluate(self, x_tensor: torch.Tensor) -> Dict[str, float]:
        """
        Compute weighted cost breakdown.

        Returns:
            {"time": float, "room": float, "distribution": float, "total": float}
        """
        result = self.local_validator.validate_x_tensor(x_tensor, self.c)
        time_raw = float(result["time_raw"])
        room_raw = float(result["room_raw"])
        soft_raw = float(result["distribution_raw"])
        time_pen = float(result["time"])
        room_pen = float(result["room"])
        soft_pen = float(result["distribution"])
        total = float(result["total"])
        return {
            "time_raw":      time_raw,
            "room_raw":     room_raw,
            "soft_raw":     soft_raw,
            "time":         time_pen,
            "room":         room_pen,
            "distribution": soft_pen,
            "weighted_time": float(result["weighted_time"]),
            "weighted_room": float(result["weighted_room"]),
            "weighted_distribution": float(result["weighted_distribution"]),
            "total":        total,
            "valid":        result["valid"],
            "hard_violations": result["hard_violations"],
        }

    # ------------------------------------------------------------------
    # Feasibility
    # ------------------------------------------------------------------

    def is_feasible(self, x_tensor: torch.Tensor) -> bool:
        """
        Returns True iff:
          1. Every class is assigned exactly once.
          2. No hard distribution constraint is violated.
        """
        return bool(self.local_validator.validate_x_tensor(x_tensor, self.c)["valid"])

    def check_violations(self, x_tensor: torch.Tensor) -> Dict:
        """
        Return a breakdown of feasibility violations for debugging.

        Returns:
            {
                "unassigned":      list of class ids not assigned,
                "multi_assigned":  list of class ids assigned more than once,
                "hard_violations": int  (number of violated hard constraints),
            }
        """
        x = x_tensor.float()
        assign = torch.sparse.mm(
            self.c.valid_dist_tensor, x.unsqueeze(1)
        ).squeeze(1)

        unassigned    = []
        multi_assigned = []
        cid_list = list(self.c.valid_solution_constraint.keys())
        for i, key in enumerate(cid_list):
            v = assign[i].item()
            if v < 1:
                # key is like "assign_<cid>"
                unassigned.append(key.replace("assign_", ""))
            elif v > 1:
                multi_assigned.append(key.replace("assign_", ""))

        hard_viol = 0
        if self.c.hard_dist_tensor._nnz() > 0:
            act = torch.sparse.mm(
                self.c.hard_dist_tensor, x.unsqueeze(1)
            ).squeeze(1)
            upper = self.c.hard_dist_upper_tensor.squeeze(0)
            hard_viol = int((act - upper).clamp(min=0.0).gt(0).sum().item())

        return {
            "unassigned":      unassigned,
            "multi_assigned":  multi_assigned,
            "hard_violations": hard_viol,
        }

    # ------------------------------------------------------------------
    # Batch evaluation over a pool of x_tensors
    # ------------------------------------------------------------------

    def evaluate_pool(self, x_list) -> list:
        """Evaluate a list of x_tensors; return list of cost dicts."""
        return [self.evaluate(x) for x in x_list]

    def best_in_pool(self, x_list):
        """Return (best_x, best_cost_dict) from a list of x_tensors."""
        results = self.evaluate_pool(x_list)
        best_i  = min(range(len(results)), key=lambda i: results[i]["total"])
        return x_list[best_i], results[best_i]
