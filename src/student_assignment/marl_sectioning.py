import math
import pathlib
import random
from collections import defaultdict
from typing import Dict, List, Optional, Tuple


class MARLStudentSectioning:
    """
    Lightweight MARL-guided student sectioning.

    Each (student, course) pair is treated as an independent agent. Its action
    is choosing one legal bundle of classes for the course. The environment is
    centralized through class capacities and the student's current timetable.
    Rewards are based on reduction in student conflicts.
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

        class_load = defaultdict(int)
        student_plan: Dict[str, Dict[str, Tuple[str, ...]]] = defaultdict(dict)
        failed = []

        students = self._sorted_student_ids()
        for sid in students:
            for course_id in self.reader.students[sid].get("courses", []):
                bundle = self._choose_initial_bundle(sid, course_id, student_plan[sid], class_load)
                if bundle is None:
                    failed.append((str(sid), course_id))
                    continue
                self._apply_bundle(sid, course_id, bundle, student_plan, class_load)

        initial_conflicts = self._total_student_conflicts(student_plan)
        revisions = self._marl_refine(student_plan, class_load)
        final_conflicts = self._total_student_conflicts(student_plan)

        solution_with_students = self._attach_students(solution, student_plan)
        stats = {
            "students": len(students),
            "student_courses": sum(len(self.reader.students[sid].get("courses", [])) for sid in students),
            "assigned_student_courses": sum(len(plan) for plan in student_plan.values()),
            "failed_student_courses": len(failed),
            "initial_conflicts": initial_conflicts,
            "student_conflicts": final_conflicts,
            "improved_conflicts": initial_conflicts - final_conflicts,
            "revisions": revisions,
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

    def _choose_initial_bundle(self, sid, course_id: str, plan: Dict[str, Tuple[str, ...]], class_load) -> Optional[Tuple[str, ...]]:
        candidates = self._candidate_bundles(sid, course_id, plan, class_load)
        if not candidates:
            return None
        return candidates[0][1]

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
        f"Running student_assignment  method=marl_guided  "
        f"iterations={cfg.get('iterations', 2)}  "
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
    print(f"Revisions              : {stats['revisions']}")
    if stats.get("top_q"):
        print(f"MARL top Q             : {stats['top_q'][:3]}")
    print(f"Saved student XML      : {out_path}")
    return solution_with_students, stats, str(out_path)
