import pathlib
import random
import time
from typing import Dict, List, Tuple

import torch


class TensorGradientSearch:
    """
    Tensor relaxation search for ITC2019 post-optimization.

    The optimizer learns one logit per x variable. For each class, logits are
    normalized with a softmax over that class's valid assignments, giving a
    differentiable one-assignment-per-class relaxation. Periodically, the
    gradient is projected back to discrete class moves and only validator-feasible
    candidates can replace the incumbent.
    """

    def __init__(self, constraints, evaluator, cfg: dict):
        self.c = constraints
        self.ev = evaluator
        self.cfg = cfg
        self.device = self.c.x_tensor.device

        self.w_time = evaluator.w_time.float()
        self.w_room = evaluator.w_room.float()
        self.soft_dist = evaluator.soft_dist
        self.soft_upper = evaluator.soft_upper.float()
        self.w_dist = evaluator.w_dist.float()
        self.time_weight = float(evaluator.time_weight)
        self.room_weight = float(evaluator.room_weight)
        self.dist_weight = float(evaluator.dist_weight)
        self.hard_weight = float(cfg.get("hard_weight", 0.0))
        self.hard_surrogate = str(cfg.get("hard_surrogate", "none")).lower()
        self.entropy_weight = float(cfg.get("entropy_weight", 0.001))

        self.class_domains = self._build_class_domains()
        self.cid_order = sorted(self.class_domains.keys(), key=self._sort_key)
        self.class_domain_tensors = {
            cid: torch.tensor(self.class_domains[cid], dtype=torch.long, device=self.device)
            for cid in self.cid_order
        }

    def _sort_key(self, value: str):
        try:
            return int(value)
        except ValueError:
            return value

    def _build_class_domains(self) -> Dict[str, List[int]]:
        domains: Dict[str, List[int]] = {cid: [] for cid in self.c.reader.classes}
        for (cid, _tidx, _rid), xidx in self.c.x.items():
            domains.setdefault(cid, []).append(int(xidx))
        for values in domains.values():
            values.sort()
        return {cid: values for cid, values in domains.items() if values}

    def _init_logits(self, x_init: torch.Tensor) -> torch.Tensor:
        init_bias = float(self.cfg.get("init_bias", 6.0))
        noise = float(self.cfg.get("init_noise", 0.01))
        logits = torch.zeros_like(self.c.x_tensor, dtype=torch.float32, device=self.device)
        logits += torch.randn_like(logits) * noise
        assigned = torch.where(x_init.to(self.device) > 0.5)[0]
        logits[assigned] += init_bias
        return logits.detach().requires_grad_(True)

    def _soft_assignment(self, logits: torch.Tensor, temperature: float) -> Tuple[torch.Tensor, torch.Tensor]:
        x_soft = torch.zeros_like(logits)
        entropy = torch.zeros((), dtype=torch.float32, device=self.device)
        temp = max(float(temperature), 1e-6)
        for cid in self.cid_order:
            idx = self.class_domain_tensors[cid]
            probs = torch.softmax(logits[idx] / temp, dim=0)
            x_soft[idx] = probs
            entropy = entropy - torch.sum(probs * torch.log(probs.clamp_min(1e-12)))
        return x_soft, entropy

    def _use_full_hard_surrogate(self) -> bool:
        return (
            self.hard_weight > 0.0
            and self.hard_surrogate in {"full", "full_sparse", "sparse"}
            and self.c.hard_dist_tensor._nnz() > 0
        )

    def _surrogate_loss(self, x_soft: torch.Tensor, entropy: torch.Tensor) -> Tuple[torch.Tensor, Dict[str, float]]:
        time_pen = torch.dot(x_soft, self.w_time) * self.time_weight
        room_pen = torch.dot(x_soft, self.w_room) * self.room_weight

        if self.soft_dist._nnz() > 0:
            soft_activity = torch.sparse.mm(self.soft_dist, x_soft.unsqueeze(1)).squeeze(1)
            soft_pen = torch.sum((soft_activity - self.soft_upper).clamp(min=0.0) * self.w_dist) * self.dist_weight
        else:
            soft_pen = torch.zeros((), dtype=torch.float32, device=self.device)

        if self._use_full_hard_surrogate():
            hard_activity = torch.sparse.mm(self.c.hard_dist_tensor, x_soft.unsqueeze(1)).squeeze(1)
            hard_upper = self.c.hard_dist_upper_tensor.squeeze(0).float()
            hard_violation = (hard_activity - hard_upper).clamp(min=0.0)
            hard_pen = torch.sum(hard_violation * hard_violation) * self.hard_weight
        else:
            hard_pen = torch.zeros((), dtype=torch.float32, device=self.device)

        loss = time_pen + room_pen + soft_pen + hard_pen + self.entropy_weight * entropy
        stats = {
            "surrogate": float((time_pen + room_pen + soft_pen).detach().cpu()),
            "hard_penalty": float(hard_pen.detach().cpu()),
            "entropy": float(entropy.detach().cpu()),
            "loss": float(loss.detach().cpu()),
        }
        return loss, stats

    def _project_argmax(self, logits: torch.Tensor, noise_scale: float = 0.0) -> torch.Tensor:
        x = torch.zeros_like(self.c.x_tensor)
        scores = logits.detach()
        if noise_scale > 0:
            scores = scores + torch.randn_like(scores) * noise_scale
        for cid in self.cid_order:
            idx = self.class_domain_tensors[cid]
            best_pos = int(torch.argmax(scores[idx]).item())
            x[idx[best_pos]] = 1.0
        return x

    def _class_assignment_map(self, x: torch.Tensor) -> Dict[str, int]:
        result = {}
        for xidx in torch.where(x > 0.5)[0].tolist():
            cid, _tidx, _rid = self.c.xidx_to_x[int(xidx)]
            result[cid] = int(xidx)
        return result

    def _gradient_moves(self, base_x: torch.Tensor, grad: torch.Tensor) -> List[Tuple[float, str, int]]:
        current = self._class_assignment_map(base_x)
        moves = []
        grad = grad.detach()
        max_options = int(self.cfg.get("gradient_options_per_class", 1))
        for cid in self.cid_order:
            old_idx = current.get(cid)
            if old_idx is None:
                continue
            old_grad = float(grad[old_idx].item())
            scored = []
            for xidx in self.class_domains[cid]:
                if xidx == old_idx:
                    continue
                score = float(grad[xidx].item()) - old_grad
                scored.append((score, cid, xidx))
            scored.sort(key=lambda item: item[0])
            moves.extend(scored[:max_options])
        return [move for move in sorted(moves, key=lambda item: item[0]) if move[0] < 0.0]

    def _apply_moves(self, base_x: torch.Tensor, moves: List[Tuple[float, str, int]]) -> torch.Tensor:
        x = base_x.clone()
        current = self._class_assignment_map(x)
        for _score, cid, new_idx in moves:
            old_idx = current.get(cid)
            if old_idx is not None:
                x[old_idx] = 0.0
            x[new_idx] = 1.0
            current[cid] = new_idx
        return x

    def _evaluate_candidate(self, x: torch.Tensor, best_cost: dict):
        cost = self.ev.evaluate(x)
        if cost["valid"] and cost["total"] < best_cost["total"]:
            return cost
        return None

    def _discrete_probe(self, logits: torch.Tensor, grad: torch.Tensor, best_x: torch.Tensor, best_cost: dict):
        checked = 0
        improved = 0
        best_local_x = best_x
        best_local_cost = best_cost

        candidates = [self._project_argmax(logits)]
        sample_count = int(self.cfg.get("sample_count", 2))
        sample_noise = float(self.cfg.get("sample_noise", 0.5))
        for _ in range(sample_count):
            candidates.append(self._project_argmax(logits, noise_scale=sample_noise))

        max_gradient_moves = int(self.cfg.get("max_gradient_moves", 8))
        prefix_sizes = [1, 2, 3, 5, max_gradient_moves]
        moves = self._gradient_moves(best_x, grad)[:max_gradient_moves]
        for size in prefix_sizes:
            if moves and size <= len(moves):
                candidates.append(self._apply_moves(best_x, moves[:size]))

        for candidate in candidates:
            checked += 1
            candidate_cost = self._evaluate_candidate(candidate, best_local_cost)
            if candidate_cost is not None:
                best_local_x = candidate.clone()
                best_local_cost = dict(candidate_cost)
                improved += 1

        return best_local_x, best_local_cost, {"checked": checked, "improved": improved}

    def search(self, x_init: torch.Tensor):
        seed = self.cfg.get("seed", None)
        if seed is not None:
            random.seed(int(seed))
            torch.manual_seed(int(seed))

        steps = int(self.cfg.get("steps", 500))
        lr = float(self.cfg.get("lr", 0.05))
        temperature = float(self.cfg.get("temperature", 1.0))
        cooling = float(self.cfg.get("cooling", 0.995))
        min_temperature = float(self.cfg.get("min_temperature", 0.1))
        eval_every = max(1, int(self.cfg.get("eval_every", 10)))
        log_every = max(1, int(self.cfg.get("log_every", 50)))

        x_init = x_init.to(self.device)
        best_x = x_init.clone()
        best_cost = self.ev.evaluate(best_x)
        if not best_cost["valid"]:
            raise ValueError("Tensor search requires a feasible initial incumbent")

        logits = self._init_logits(best_x)
        optimizer = torch.optim.Adam([logits], lr=lr)
        probes = 0
        improvements = 0
        last_stats = {}

        for step in range(1, steps + 1):
            optimizer.zero_grad(set_to_none=True)
            x_soft, entropy = self._soft_assignment(logits, temperature)
            loss, last_stats = self._surrogate_loss(x_soft, entropy)
            loss.backward()

            if step % eval_every == 0:
                grad_snapshot = logits.grad.detach().clone()
                best_x, new_best_cost, probe_stats = self._discrete_probe(
                    logits, grad_snapshot, best_x, best_cost
                )
                probes += probe_stats["checked"]
                improvements += probe_stats["improved"]
                if new_best_cost["total"] < best_cost["total"]:
                    best_cost = dict(new_best_cost)
                    # Pull the relaxation back toward the new incumbent.
                    with torch.no_grad():
                        logits.mul_(0.2)
                        logits[torch.where(best_x > 0.5)[0]] += float(self.cfg.get("init_bias", 6.0))

            optimizer.step()
            temperature = max(min_temperature, temperature * cooling)

            if step % log_every == 0:
                print(
                    f"  step={step} temp={temperature:.4f} "
                    f"loss={last_stats.get('loss', 0.0):.1f} "
                    f"hard={last_stats.get('hard_penalty', 0.0):.1f} "
                    f"best={best_cost['total']:.1f}"
                )

        # Final deterministic projection is checked, but never replaces a better incumbent unless valid.
        final_x = self._project_argmax(logits)
        final_cost = self._evaluate_candidate(final_x, best_cost)
        if final_cost is not None:
            best_x = final_x.clone()
            best_cost = dict(final_cost)
            improvements += 1
        probes += 1

        return best_x, {
            "cost": best_cost,
            "steps": steps,
            "probes": probes,
            "improvements": improvements,
            "last_surrogate": last_stats,
        }


def _best_valid_pool_index(pool_costs: list) -> int:
    valid_indices = [i for i, c in enumerate(pool_costs) if c.get("valid", True)]
    candidates = valid_indices or list(range(len(pool_costs)))
    return min(candidates, key=lambda i: pool_costs[i]["total"])


def run_tensor_search(
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
        f"Running tensor_search  steps={cfg.get('steps', 500)}  "
        f"lr={cfg.get('lr', 0.05)}  "
        f"temperature={cfg.get('temperature', 1.0)}  "
        f"eval_every={cfg.get('eval_every', 10)}  "
        f"sample_count={cfg.get('sample_count', 2)}  "
        f"hard_surrogate={cfg.get('hard_surrogate', 'none')}"
    )

    if not pool_data:
        raise ValueError("Tensor search needs at least one initial solution in the solution pool")

    best_pool_idx = _best_valid_pool_index(pool_costs)
    x_init = pool_data[best_pool_idx][1]
    pool_best = pool_costs[best_pool_idx]
    print(f"Initial pool best: total={pool_best['total']:.1f} valid={pool_best.get('valid', True)}")

    t0 = time.time()
    searcher = TensorGradientSearch(constraints, evaluator, cfg)
    result_x, result = searcher.search(x_init)
    elapsed = time.time() - t0

    result_cost = evaluator.evaluate(result_x)
    feasible = evaluator.is_feasible(result_x)
    improve = (pool_best["total"] - result_cost["total"]) / pool_best["total"] * 100 if pool_best["total"] > 0 else 0.0

    print(f"Tensor time : {elapsed:.2f}s")
    print(f"Steps       : {result.get('steps', 0)}")
    print(f"Probes      : {result.get('probes', 0)}")
    print(f"Improvements: {result.get('improvements', 0)}")
    print(f"Feasible    : {feasible}")
    if not feasible:
        viol = evaluator.check_violations(result_x)
        print(f"  Unassigned    : {len(viol['unassigned'])}")
        print(f"  Multi-assigned: {len(viol['multi_assigned'])}")
        print(f"  Hard violations: {viol['hard_violations']}")
    print(
        f"Tensor cost: total={result_cost['total']:.1f}  "
        f"time={result_cost['time']:.1f}  "
        f"room={result_cost['room']:.1f}  "
        f"dist={result_cost['distribution']:.1f}"
    )
    print(f"Pool best  : {pool_best['total']:.1f}  improvement: {improve:+.2f}%")

    output_dir = pathlib.Path(output_dir)
    out_path = output_dir / f"{instance}_tensor_search.xml"
    sol_dict = loader.decode(result_x, constraints)
    loader.save_xml(sol_dict, constraints.reader, str(out_path), meta={"technique": "tensor-gradient-search"})
    print(f"Saved: {out_path}")

    return result_x, result_cost, str(out_path)
