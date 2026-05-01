import math
import pathlib
import random
from collections import defaultdict
from typing import Dict, List, Optional, Tuple


try:
    import numpy as np
except Exception:
    np = None

try:
    from scipy.optimize import Bounds, LinearConstraint, milp
    from scipy.sparse import lil_matrix

    SCIPY_MILP_AVAILABLE = True
except Exception:
    SCIPY_MILP_AVAILABLE = False

try:
    import gurobipy as gp
    from gurobipy import GRB

    GUROBI_AVAILABLE = True
except Exception:
    GUROBI_AVAILABLE = False


class MARLStudentSectioning:
    """
    Lightweight student sectioning with optional MILP + LNS + MARL.

    Each (student, course) pair is treated as an independent agent. Its action
    is choosing one legal bundle of classes for the course. The environment is
    centralized through class capacities and the student's current timetable.
    Rewards are based on reduction in student conflicts. For stronger runs,
    the same action space can be repaired by small MILP subproblems inside LNS.
    """

    def __init__(self, reader, cfg: dict):
        self.reader = reader
        self.cfg = cfg
        self.seed = cfg.get("seed", None)
        if self.seed is not None:
            random.seed(int(self.seed))

        self.max_bundles_per_course = int(cfg.get("max_bundles_per_course", 250))
        self.candidate_limit = int(cfg.get("candidate_limit", 40))
        self.alpha = float(cfg.get("alpha", 0.25))
        self.epsilon = float(cfg.get("epsilon", 0.10))
        self.temperature = max(float(cfg.get("temperature", 1.0)), 1e-6)
        self.q_weight = float(cfg.get("q_weight", 1.0))
        self.conflict_weight = float(cfg.get("conflict_weight", 1.0))
        self.capacity_weight = float(cfg.get("capacity_weight", 4.0))
        self.initial_method = str(cfg.get("initial", "mip")).lower()
        self.lns_iterations = int(cfg.get("lns_iterations", 50))
        self.lns_destroy_students = int(cfg.get("lns_destroy_students", 20))
        self.lns_candidate_limit = int(cfg.get("lns_candidate_limit", min(self.candidate_limit, 10)))
        self.mip_candidate_limit = int(cfg.get("mip_candidate_limit", min(self.candidate_limit, 8)))
        self.mip_batch_size = int(cfg.get("mip_batch_size", 40))
        self.mip_time_limit = float(cfg.get("mip_time_limit", 30.0))
        self.mip_max_variables = int(cfg.get("mip_max_variables", 250000))
        self.post_marl_iterations = int(cfg.get("post_marl_iterations", cfg.get("iterations", 0)))
        self.mip_solver = str(cfg.get("mip_solver", "auto")).lower()
        self.mip_fallback = bool(cfg.get("mip_fallback", True))
        self.gurobi_threads = int(cfg.get("gurobi_threads", 0))
        self.gurobi_output = bool(cfg.get("gurobi_output", False))

        self.class_info: Dict[str, dict] = {}
        self.course_bundles: Dict[str, List[Tuple[str, ...]]] = {}
        self.q_values: Dict[Tuple[str, str, Tuple[str, ...]], float] = defaultdict(float)
        self.q_counts: Dict[Tuple[str, str, Tuple[str, ...]], int] = defaultdict(int)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def assign(self, solution: Dict[str, dict]) -> Tuple[Dict[str, dict], dict]:
        self.class_info = self._build_class_info(solution)
        self.course_bundles = self._build_course_bundles()
        students = self._sorted_student_ids()

        if self.initial_method == "mip":
            student_plan, class_load, failed, mip_stats = self._build_initial_mip()
        else:
            student_plan, class_load, failed = self._build_initial_greedy()
            mip_stats = {"used": False, "status": "not_requested", "batches": 0}

        initial_conflicts = self._total_student_conflicts(student_plan)
        lns_stats = self._student_lns(student_plan, class_load)
        after_lns_conflicts = self._total_student_conflicts(student_plan)

        revisions = 0
        if self.post_marl_iterations > 0:
            old_iterations = self.cfg.get("iterations", 2)
            self.cfg["iterations"] = self.post_marl_iterations
            revisions = self._marl_refine(student_plan, class_load)
            self.cfg["iterations"] = old_iterations

        final_conflicts = self._total_student_conflicts(student_plan)

        solution_with_students = self._attach_students(solution, student_plan)
        stats = {
            "students": len(students),
            "student_courses": sum(len(self.reader.students[sid].get("courses", [])) for sid in students),
            "assigned_student_courses": sum(len(plan) for plan in student_plan.values()),
            "failed_student_courses": len(failed),
            "initial_conflicts": initial_conflicts,
            "after_lns_conflicts": after_lns_conflicts,
            "student_conflicts": final_conflicts,
            "improved_conflicts": initial_conflicts - final_conflicts,
            "lns_improved_conflicts": initial_conflicts - after_lns_conflicts,
            "revisions": revisions,
            "mip": mip_stats,
            "lns": lns_stats,
            "top_q": self._top_q(),
        }
        return solution_with_students, stats

    def student_weighted_cost(self, conflicts: int) -> int:
        opt = self.reader.optimization or {}
        return int(conflicts) * int(opt.get("student", 0))

    # ------------------------------------------------------------------
    # Course bundles
    # ------------------------------------------------------------------

    def _build_course_bundles(self) -> Dict[str, List[Tuple[str, ...]]]:
        bundles = {}
        for course_id, course in self.reader.courses.items():
            course_key = str(course_id)
            course_bundles = []
            for config in course.get("configs", {}).values():
                config_bundles = self._bundles_for_config(config)
                course_bundles.extend(config_bundles)
                if len(course_bundles) >= self.max_bundles_per_course:
                    break
            bundles[course_key] = self._unique_bundles(course_bundles)[: self.max_bundles_per_course]
        return bundles

    def _bundles_for_config(self, config: dict) -> List[Tuple[str, ...]]:
        subparts = list(config.get("subparts", {}).values())
        if not subparts:
            return []

        bundles = [tuple()]
        for subpart in subparts:
            next_bundles = []
            class_ids = sorted(subpart.get("classes", {}).keys(), key=self._sort_key)
            for bundle in bundles:
                selected = set(bundle)
                for cid in class_ids:
                    parent = self.reader.classes[cid].get("parent")
                    if parent and parent not in selected:
                        continue
                    next_bundles.append(tuple(list(bundle) + [cid]))
                    if len(next_bundles) >= self.max_bundles_per_course:
                        break
                if len(next_bundles) >= self.max_bundles_per_course:
                    break
            bundles = next_bundles
            if not bundles:
                return []
        return [tuple(sorted(bundle, key=self._sort_key)) for bundle in bundles]

    def _unique_bundles(self, bundles: List[Tuple[str, ...]]) -> List[Tuple[str, ...]]:
        seen = set()
        result = []
        for bundle in bundles:
            if bundle not in seen:
                seen.add(bundle)
                result.append(bundle)
        return result

    # ------------------------------------------------------------------
    # Initial assignment and MARL refinement
    # ------------------------------------------------------------------

    def _build_initial_greedy(self):
        class_load = defaultdict(int)
        student_plan: Dict[str, Dict[str, Tuple[str, ...]]] = defaultdict(dict)
        failed = []
        for sid in self._sorted_student_ids():
            for course_id in self.reader.students[sid].get("courses", []):
                bundle = self._choose_initial_bundle(sid, course_id, student_plan[sid], class_load)
                if bundle is None:
                    failed.append((str(sid), course_id))
                    continue
                self._apply_bundle(sid, course_id, bundle, student_plan, class_load)
        return student_plan, class_load, failed

    def _build_initial_mip(self):
        if not self._any_mip_solver_available():
            student_plan, class_load, failed = self._build_initial_greedy()
            return student_plan, class_load, failed, {"used": False, "status": "mip_solver_unavailable", "batches": 0}

        student_plan: Dict[str, Dict[str, Tuple[str, ...]]] = defaultdict(dict)
        class_load = defaultdict(int)
        failed = []
        batches = 0
        repaired_batches = 0
        student_ids = self._sorted_student_ids()

        for start in range(0, len(student_ids), max(1, self.mip_batch_size)):
            batch = student_ids[start : start + max(1, self.mip_batch_size)]
            ok, batch_failed = self._mip_repair_students(
                batch,
                student_plan,
                class_load,
                candidate_limit=self.mip_candidate_limit,
                time_limit=self.mip_time_limit,
            )
            batches += 1
            if ok:
                repaired_batches += 1
                failed.extend(batch_failed)
                continue

            # If a batch MILP is too large or infeasible, fall back to exact-ish
            # one-student MILP repairs before giving up to greedy.
            for sid in batch:
                ok_one, one_failed = self._mip_repair_students(
                    [sid],
                    student_plan,
                    class_load,
                    candidate_limit=self.mip_candidate_limit,
                    time_limit=max(2.0, self.mip_time_limit / 5.0),
                )
                if ok_one:
                    repaired_batches += 1
                    failed.extend(one_failed)
                    continue
                for course_id in self.reader.students[sid].get("courses", []):
                    bundle = self._choose_initial_bundle(sid, course_id, student_plan[sid], class_load)
                    if bundle is None:
                        failed.append((str(sid), course_id))
                    else:
                        self._apply_bundle(sid, course_id, bundle, student_plan, class_load)

        return student_plan, class_load, failed, {
            "used": True,
            "status": "ok",
            "preferred_solver": self._solver_order()[0],
            "gurobi_available": GUROBI_AVAILABLE,
            "scipy_available": SCIPY_MILP_AVAILABLE,
            "batches": batches,
            "repaired_batches": repaired_batches,
        }

    def _choose_initial_bundle(self, sid, course_id: str, plan: Dict[str, Tuple[str, ...]], class_load) -> Optional[Tuple[str, ...]]:
        candidates = self._candidate_bundles(sid, course_id, plan, class_load)
        if not candidates:
            return None
        return candidates[0][1]

    def _student_lns(self, student_plan, class_load) -> dict:
        if self.lns_iterations <= 0 or not self._any_mip_solver_available():
            return {
                "used": False,
                "status": "disabled" if self.lns_iterations <= 0 else "mip_solver_unavailable",
                "iterations": 0,
                "accepted": 0,
            }

        accepted = 0
        best = self._total_student_conflicts(student_plan)
        for iteration in range(self.lns_iterations):
            destroy = self._select_lns_students(student_plan, iteration)
            if not destroy:
                break
            before = self._total_student_conflicts(student_plan)
            snapshot = {sid: dict(student_plan.get(sid, {})) for sid in destroy}
            ok, _failed = self._mip_repair_students(
                destroy,
                student_plan,
                class_load,
                candidate_limit=self.lns_candidate_limit,
                time_limit=self.mip_time_limit,
            )
            after = self._total_student_conflicts(student_plan)
            if ok and after <= before:
                if after < best:
                    best = after
                accepted += 1
            else:
                self._restore_students(destroy, snapshot, student_plan, class_load)

        return {
            "used": True,
            "status": "ok",
            "iterations": self.lns_iterations,
            "accepted": accepted,
        }

    def _select_lns_students(self, student_plan, iteration: int) -> List[str]:
        scores = [(self._student_conflicts(plan), sid) for sid, plan in student_plan.items()]
        scores = [(score, sid) for score, sid in scores if score > 0]
        if not scores:
            return []
        scores.sort(key=lambda item: (-item[0], self._sort_key(item[1])))
        head = [sid for _score, sid in scores[: max(1, self.lns_destroy_students // 2)]]
        tail_pool = [sid for _score, sid in scores[max(1, self.lns_destroy_students // 2):]]
        random.shuffle(tail_pool)
        return (head + tail_pool)[: self.lns_destroy_students]

    def _restore_students(self, student_ids, snapshot, student_plan, class_load):
        for sid in student_ids:
            for bundle in student_plan.get(sid, {}).values():
                self._remove_bundle(bundle, class_load)
            student_plan[sid] = dict(snapshot.get(sid, {}))
            for bundle in student_plan[sid].values():
                self._add_bundle(bundle, class_load)

    def _mip_repair_students(self, student_ids, student_plan, class_load, candidate_limit: int, time_limit: float):
        if not self._any_mip_solver_available():
            return False, []

        student_ids = [sid for sid in student_ids if sid in self.reader.students]
        removed = {sid: dict(student_plan.get(sid, {})) for sid in student_ids}
        for sid in student_ids:
            for bundle in student_plan.get(sid, {}).values():
                self._remove_bundle(bundle, class_load)
            student_plan[sid] = {}

        variables = []
        var_index = {}
        failed = []
        for sid in student_ids:
            current_plan = self._fixed_plan_for_student(sid, student_plan)
            for course_id in self.reader.students[sid].get("courses", []):
                candidates = self._candidate_bundles_for_mip(course_id, current_plan, class_load, candidate_limit)
                if not candidates:
                    failed.append((str(sid), course_id))
                    continue
                for bundle in candidates:
                    var_index[(sid, course_id, bundle)] = len(variables)
                    variables.append((sid, course_id, bundle))

        if not variables:
            self._restore_students(student_ids, removed, student_plan, class_load)
            return False, failed

        pair_terms = self._mip_pair_terms(student_ids, variables, var_index)
        n_vars = len(variables) + len(pair_terms)
        if n_vars > self.mip_max_variables:
            self._restore_students(student_ids, removed, student_plan, class_load)
            return False, failed

        c = np.zeros(n_vars, dtype=float)
        for idx, (sid, _course_id, bundle) in enumerate(variables):
            fixed_plan = self._fixed_plan_for_student(sid, student_plan)
            c[idx] = self._incremental_conflicts(bundle, fixed_plan)
        for offset, (_left, _right, cost) in enumerate(pair_terms, start=len(variables)):
            c[offset] = float(cost)

        constraint_rows = []
        lb = []
        ub = []

        # Exactly one bundle for every student-course that has candidates.
        by_agent = defaultdict(list)
        for idx, (sid, course_id, _bundle) in enumerate(variables):
            by_agent[(sid, course_id)].append(idx)
        for idxs in by_agent.values():
            constraint_rows.append({idx: 1.0 for idx in idxs})
            lb.append(1.0)
            ub.append(1.0)

        # Class capacities after fixed non-destroyed assignments.
        by_class = defaultdict(list)
        for idx, (_sid, _course_id, bundle) in enumerate(variables):
            for cid in bundle:
                by_class[cid].append(idx)
        for cid, idxs in by_class.items():
            limit = self.class_info.get(cid, {}).get("limit")
            if limit is None:
                continue
            remaining = int(limit) - class_load[cid]
            if remaining < 0:
                self._restore_students(student_ids, removed, student_plan, class_load)
                return False, failed
            constraint_rows.append({idx: 1.0 for idx in idxs})
            lb.append(0.0)
            ub.append(float(remaining))

        # Linearization for pair conflict z = x_i AND x_j.
        pair_start = len(variables)
        for pair_offset, (left, right, _cost) in enumerate(pair_terms):
            z = pair_start + pair_offset
            constraint_rows.append({z: 1.0, left: -1.0})
            lb.append(-np.inf)
            ub.append(0.0)
            constraint_rows.append({z: 1.0, right: -1.0})
            lb.append(-np.inf)
            ub.append(0.0)
            constraint_rows.append({z: 1.0, left: -1.0, right: -1.0})
            lb.append(-1.0)
            ub.append(np.inf)

        solution = self._solve_binary_mip(c, constraint_rows, lb, ub, time_limit)
        if solution is None:
            self._restore_students(student_ids, removed, student_plan, class_load)
            return False, failed

        selected = [variables[idx] for idx, value in enumerate(solution[: len(variables)]) if value > 0.5]
        selected_agents = {(sid, course_id) for sid, course_id, _bundle in selected}
        required_agents = set(by_agent.keys())
        if selected_agents != required_agents:
            self._restore_students(student_ids, removed, student_plan, class_load)
            return False, failed

        for sid, course_id, bundle in selected:
            self._apply_bundle(sid, course_id, bundle, student_plan, class_load)
        return True, failed

    def _any_mip_solver_available(self) -> bool:
        if np is None:
            return False
        if self.mip_solver == "gurobi":
            return GUROBI_AVAILABLE or (self.mip_fallback and SCIPY_MILP_AVAILABLE)
        if self.mip_solver == "scipy":
            return SCIPY_MILP_AVAILABLE or (self.mip_fallback and GUROBI_AVAILABLE)
        return GUROBI_AVAILABLE or SCIPY_MILP_AVAILABLE

    def _solve_binary_mip(self, c, constraint_rows, lb, ub, time_limit: float):
        if np is None:
            return None
        solver_order = self._solver_order()
        for solver in solver_order:
            if solver == "gurobi" and GUROBI_AVAILABLE:
                result = self._solve_binary_mip_gurobi(c, constraint_rows, lb, ub, time_limit)
                if result is not None:
                    return result
            if solver == "scipy" and SCIPY_MILP_AVAILABLE:
                result = self._solve_binary_mip_scipy(c, constraint_rows, lb, ub, time_limit)
                if result is not None:
                    return result
            if not self.mip_fallback:
                break
        return None

    def _solver_order(self):
        if self.mip_solver == "gurobi":
            return ["gurobi", "scipy"]
        if self.mip_solver == "scipy":
            return ["scipy", "gurobi"]
        return ["gurobi", "scipy"]

    def _solve_binary_mip_gurobi(self, c, constraint_rows, lb, ub, time_limit: float):
        try:
            model = gp.Model("itc2019_student_assignment")
            model.Params.OutputFlag = 1 if self.gurobi_output else 0
            model.Params.TimeLimit = max(float(time_limit), 1.0)
            model.Params.MIPGap = float(self.cfg.get("mip_rel_gap", 0.05))
            if self.gurobi_threads > 0:
                model.Params.Threads = self.gurobi_threads

            x_vars = model.addVars(len(c), vtype=GRB.BINARY, name="x")
            model.setObjective(
                gp.quicksum(float(c[idx]) * x_vars[idx] for idx in range(len(c)) if float(c[idx]) != 0.0),
                GRB.MINIMIZE,
            )

            for row, coeffs in enumerate(constraint_rows):
                expr = gp.LinExpr()
                for idx, value in coeffs.items():
                    expr.addTerms(float(value), x_vars[int(idx)])
                lower = lb[row]
                upper = ub[row]
                lower_finite = not math.isinf(float(lower))
                upper_finite = not math.isinf(float(upper))
                if lower_finite and upper_finite and abs(float(lower) - float(upper)) <= 1e-9:
                    model.addConstr(expr == float(lower))
                else:
                    if lower_finite:
                        model.addConstr(expr >= float(lower))
                    if upper_finite:
                        model.addConstr(expr <= float(upper))

            model.optimize()
            if model.SolCount <= 0:
                return None
            return [float(x_vars[idx].X) for idx in range(len(c))]
        except Exception:
            return None

    def _solve_binary_mip_scipy(self, c, constraint_rows, lb, ub, time_limit: float):
        if not SCIPY_MILP_AVAILABLE:
            return None
        n_vars = len(c)
        mat = lil_matrix((len(constraint_rows), n_vars), dtype=float)
        for row, coeffs in enumerate(constraint_rows):
            for idx, value in coeffs.items():
                mat[row, idx] = value
        try:
            result = milp(
                c=c,
                integrality=np.ones(n_vars),
                bounds=Bounds(np.zeros(n_vars), np.ones(n_vars)),
                constraints=LinearConstraint(mat.tocsr(), np.array(lb), np.array(ub)),
                options={"time_limit": time_limit, "mip_rel_gap": float(self.cfg.get("mip_rel_gap", 0.05))},
            )
        except Exception:
            return None
        if result.x is None or not result.success:
            return None
        return result.x

    def _candidate_bundles_for_mip(self, course_id: str, current_plan, class_load, limit: int):
        candidates = []
        for bundle in self.course_bundles.get(str(course_id), []):
            if not self._capacity_ok(bundle, class_load):
                continue
            candidates.append((self._incremental_conflicts(bundle, current_plan), tuple(bundle)))
        candidates.sort(key=lambda item: (item[0], item[1]))
        return [bundle for _score, bundle in candidates[: max(1, limit)]]

    def _mip_pair_terms(self, student_ids, variables, var_index):
        by_student_course = defaultdict(lambda: defaultdict(list))
        for idx, (sid, course_id, bundle) in enumerate(variables):
            by_student_course[sid][course_id].append((idx, bundle))

        pair_terms = []
        for sid in student_ids:
            course_ids = list(by_student_course.get(sid, {}).keys())
            for i in range(len(course_ids)):
                for j in range(i + 1, len(course_ids)):
                    left_options = by_student_course[sid][course_ids[i]]
                    right_options = by_student_course[sid][course_ids[j]]
                    for left_idx, left_bundle in left_options:
                        for right_idx, right_bundle in right_options:
                            cost = self._bundle_pair_conflicts(left_bundle, right_bundle)
                            if cost > 0:
                                pair_terms.append((left_idx, right_idx, cost))
        return pair_terms

    def _bundle_pair_conflicts(self, left_bundle, right_bundle) -> int:
        conflicts = 0
        for cid_a in left_bundle:
            for cid_b in right_bundle:
                if self._classes_conflict(cid_a, cid_b):
                    conflicts += 1
        return conflicts

    def _fixed_plan_for_student(self, sid, student_plan):
        return dict(student_plan.get(sid, {}))

    def _marl_refine(self, student_plan, class_load) -> int:
        iterations = int(self.cfg.get("iterations", 2))
        revisions = 0
        student_ids = self._sorted_student_ids()
        for _iteration in range(iterations):
            random.shuffle(student_ids)
            for sid in student_ids:
                course_ids = list(student_plan.get(sid, {}).keys())
                random.shuffle(course_ids)
                for course_id in course_ids:
                    old_bundle = student_plan[sid][course_id]
                    old_conflicts = self._student_conflicts(student_plan[sid])
                    self._remove_bundle(old_bundle, class_load)
                    plan_without = dict(student_plan[sid])
                    plan_without.pop(course_id, None)

                    candidates = self._candidate_bundles(sid, course_id, plan_without, class_load)
                    if not candidates:
                        self._add_bundle(old_bundle, class_load)
                        continue

                    new_bundle = self._sample_bundle(sid, course_id, candidates)
                    student_plan[sid][course_id] = new_bundle
                    self._add_bundle(new_bundle, class_load)
                    new_conflicts = self._student_conflicts(student_plan[sid])

                    reward = old_conflicts - new_conflicts
                    if reward < 0:
                        self._remove_bundle(new_bundle, class_load)
                        student_plan[sid][course_id] = old_bundle
                        self._add_bundle(old_bundle, class_load)
                        new_bundle = old_bundle
                        reward = -float(self.cfg.get("worse_reward", 0.02))
                    elif new_bundle != old_bundle:
                        revisions += 1

                    self._update_q(sid, course_id, new_bundle, reward)
        return revisions

    def _candidate_bundles(self, sid, course_id: str, current_plan: Dict[str, Tuple[str, ...]], class_load):
        bundles = self.course_bundles.get(str(course_id), [])
        scored = []
        for bundle in bundles:
            if not self._capacity_ok(bundle, class_load):
                continue
            conflict = self._incremental_conflicts(tuple(bundle), current_plan)
            capacity_slack = self._bundle_capacity_slack(bundle, class_load)
            q = self.q_values[(str(sid), str(course_id), tuple(bundle))]
            score = (
                self.conflict_weight * conflict
                - self.capacity_weight * capacity_slack
                - self.q_weight * q
            )
            scored.append((score, tuple(bundle), conflict, q))
        scored.sort(key=lambda item: (item[0], item[2], item[1]))
        return scored[: self.candidate_limit] if self.candidate_limit > 0 else scored

    def _sample_bundle(self, sid, course_id: str, candidates):
        if random.random() < self.epsilon:
            return random.choice(candidates)[1]
        weights = []
        for score, bundle, _conflict, _q in candidates:
            q = self.q_values[(str(sid), str(course_id), tuple(bundle))]
            weights.append(math.exp((q - score) / self.temperature))
        return random.choices([bundle for _score, bundle, _conflict, _q in candidates], weights=weights, k=1)[0]

    def _update_q(self, sid, course_id: str, bundle: Tuple[str, ...], reward: float):
        key = (str(sid), str(course_id), tuple(bundle))
        reward = max(-1.0, min(1.0, float(reward)))
        self.q_values[key] += self.alpha * (reward - self.q_values[key])
        self.q_counts[key] += 1

    # ------------------------------------------------------------------
    # Conflicts and capacity
    # ------------------------------------------------------------------

    def _build_class_info(self, solution: Dict[str, dict]) -> Dict[str, dict]:
        result = {}
        for cid, assignment in solution.items():
            class_data = self.reader.classes.get(cid, {})
            time_option = self._match_time_option(cid, assignment)
            weeks, days, start, length = time_option if time_option else (
                assignment.get("weeks", ""),
                assignment.get("days", ""),
                int(assignment.get("start", 0)),
                0,
            )
            result[cid] = {
                "weeks": weeks,
                "days": days,
                "start": int(start),
                "length": int(length),
                "end": int(start) + int(length),
                "room": assignment.get("room"),
                "limit": class_data.get("limit"),
            }
        return result

    def _match_time_option(self, cid: str, assignment: dict):
        for option in self.reader.classes.get(cid, {}).get("time_options", []):
            weeks, days, start, length = option["optional_time_bits"]
            if weeks == assignment.get("weeks") and days == assignment.get("days") and int(start) == int(assignment.get("start", -1)):
                return weeks, days, int(start), int(length)
        return None

    def _capacity_ok(self, bundle: Tuple[str, ...], class_load) -> bool:
        for cid in bundle:
            limit = self.class_info.get(cid, {}).get("limit")
            if limit is not None and class_load[cid] + 1 > int(limit):
                return False
        return True

    def _bundle_capacity_slack(self, bundle: Tuple[str, ...], class_load) -> float:
        slack = 0.0
        for cid in bundle:
            limit = self.class_info.get(cid, {}).get("limit")
            if limit:
                slack += max(0, int(limit) - class_load[cid])
        return slack / max(len(bundle), 1)

    def _incremental_conflicts(self, bundle: Tuple[str, ...], current_plan: Dict[str, Tuple[str, ...]]) -> int:
        existing = [cid for selected in current_plan.values() for cid in selected]
        conflicts = 0
        for cid in bundle:
            for other in existing:
                if self._classes_conflict(cid, other):
                    conflicts += 1
        for i in range(len(bundle)):
            for j in range(i + 1, len(bundle)):
                if self._classes_conflict(bundle[i], bundle[j]):
                    conflicts += 1
        return conflicts

    def _student_conflicts(self, plan: Dict[str, Tuple[str, ...]]) -> int:
        classes = [cid for selected in plan.values() for cid in selected]
        conflicts = 0
        for i in range(len(classes)):
            for j in range(i + 1, len(classes)):
                if self._classes_conflict(classes[i], classes[j]):
                    conflicts += 1
        return conflicts

    def _total_student_conflicts(self, student_plan) -> int:
        return sum(self._student_conflicts(plan) for plan in student_plan.values())

    def _classes_conflict(self, cid_a: str, cid_b: str) -> bool:
        if cid_a == cid_b:
            return False
        a = self.class_info.get(cid_a)
        b = self.class_info.get(cid_b)
        if not a or not b:
            return False
        if not self._same_day_week(a, b):
            return False
        travel_ab = self._travel(a.get("room"), b.get("room"))
        travel_ba = self._travel(b.get("room"), a.get("room"))
        return not (a["end"] + travel_ab <= b["start"] or b["end"] + travel_ba <= a["start"])

    def _same_day_week(self, a: dict, b: dict) -> bool:
        return (self._bits(a["weeks"]) & self._bits(b["weeks"])) != 0 and (self._bits(a["days"]) & self._bits(b["days"])) != 0

    def _travel(self, room_a: Optional[str], room_b: Optional[str]) -> int:
        if room_a is None or room_b is None:
            return 0
        return int(self.reader.travel.get(str(room_a), {}).get(str(room_b), 0))

    # ------------------------------------------------------------------
    # Solution projection
    # ------------------------------------------------------------------

    def _apply_bundle(self, sid, course_id: str, bundle: Tuple[str, ...], student_plan, class_load):
        student_plan[sid][str(course_id)] = tuple(bundle)
        self._add_bundle(bundle, class_load)

    def _add_bundle(self, bundle: Tuple[str, ...], class_load):
        for cid in bundle:
            class_load[cid] += 1

    def _remove_bundle(self, bundle: Tuple[str, ...], class_load):
        for cid in bundle:
            class_load[cid] -= 1

    def _attach_students(self, solution: Dict[str, dict], student_plan) -> Dict[str, dict]:
        result = {
            cid: {**assignment, "students": []}
            for cid, assignment in solution.items()
        }
        for sid, plan in student_plan.items():
            for bundle in plan.values():
                for cid in bundle:
                    if cid in result:
                        result[cid].setdefault("students", []).append(str(sid))
        for assignment in result.values():
            assignment["students"] = sorted(set(assignment.get("students", [])), key=self._sort_key)
        return result

    def _top_q(self, limit: int = 10):
        items = [
            {"student": sid, "course": course_id, "q": q, "updates": self.q_counts[key]}
            for key, q in self.q_values.items()
            for sid, course_id, _bundle in [key]
            if self.q_counts[key] > 0
        ]
        items.sort(key=lambda item: item["q"], reverse=True)
        return items[:limit]

    def _sorted_student_ids(self):
        return sorted(self.reader.students.keys(), key=self._sort_key)

    def _bits(self, bit_string: str) -> int:
        return int(bit_string or "0", 2)

    def _sort_key(self, value):
        return int(value) if str(value).isdigit() else str(value)


def run_student_assignment(cfg: dict, reader, loader, solution: Dict[str, dict], instance: str, output_dir: pathlib.Path):
    print(f"\n{'=' * 60}")
    print(
        f"Running student_assignment  method=mip_lns_marl  "
        f"solver={cfg.get('mip_solver', 'auto')}  "
        f"lns_iterations={cfg.get('lns_iterations', 50)}  "
        f"candidate_limit={cfg.get('candidate_limit', 40)}"
    )
    sectioner = MARLStudentSectioning(reader, cfg)
    solution_with_students, stats = sectioner.assign(solution)

    output_dir = pathlib.Path(output_dir)
    out_path = output_dir / f"{instance}_student_marl.xml"
    loader.save_xml(
        solution_with_students,
        reader,
        str(out_path),
        meta={"technique": "marl-student-sectioning"},
    )

    weighted = sectioner.student_weighted_cost(stats["student_conflicts"])
    print(f"Students              : {stats['students']}")
    print(f"Assigned student-course: {stats['assigned_student_courses']}/{stats['student_courses']}")
    print(f"Failed student-course  : {stats['failed_student_courses']}")
    print(f"Student conflicts      : {stats['student_conflicts']}  weighted={weighted}")
    print(f"Conflict improvement   : {stats['improved_conflicts']}")
    print(f"MIP stats              : {stats.get('mip')}")
    print(f"LNS stats              : {stats.get('lns')}")
    print(f"Revisions              : {stats['revisions']}")
    if stats.get("top_q"):
        print(f"MARL top Q             : {stats['top_q'][:3]}")
    print(f"Saved student XML      : {out_path}")
    return solution_with_students, stats, str(out_path)
