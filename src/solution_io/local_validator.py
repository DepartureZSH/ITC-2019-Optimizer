import itertools
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

import torch


@dataclass(frozen=True)
class Assignment:
    cid: str
    weeks: str
    days: str
    start: int
    length: int
    room: Optional[str]
    time_penalty: int
    room_penalty: int

    @property
    def end(self) -> int:
        return self.start + self.length


class LocalValidator:
    """
    Local ITC2019 validator for the no-student-assignment project variant.

    It follows the official XML scoring definitions for time, room, and
    distribution penalties. Student conflicts are intentionally reported as 0
    because this project version writes no <student> elements in solutions.
    """

    PAIRWISE_TYPES = {
        "SameStart",
        "SameTime",
        "DifferentTime",
        "SameDays",
        "DifferentDays",
        "SameWeeks",
        "DifferentWeeks",
        "Overlap",
        "NotOverlap",
        "SameRoom",
        "DifferentRoom",
        "SameAttendees",
        "Precedence",
        "WorkDay",
        "MinGap",
    }

    def __init__(self, reader):
        self.reader = reader
        opt = reader.optimization or {}
        self.weights = {
            "time": int(opt.get("time", 0)),
            "room": int(opt.get("room", 0)),
            "distribution": int(opt.get("distribution", 0)),
            "student": int(opt.get("student", 0)),
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate_xml(self, xml_path: str, loader=None) -> dict:
        if loader is None:
            from .loader import SolutionLoader

            loader = SolutionLoader()
        return self.validate_solution(loader.load_xml(xml_path))

    def validate_x_tensor(self, x_tensor: torch.Tensor, constraints) -> dict:
        solution = {}
        duplicate_classes = []
        for xidx in torch.where(x_tensor > 0.5)[0].tolist():
            cid, tidx, rid = constraints.xidx_to_x[xidx]
            if cid in solution:
                duplicate_classes.append(cid)
            topt = self._time_option_by_index(cid, tidx)
            weeks, days, start, _length = topt["optional_time_bits"]
            solution[cid] = {
                "weeks": weeks,
                "days": days,
                "start": start,
                "room": rid if rid != "dummy" else None,
            }
        result = self.validate_solution(solution)
        if duplicate_classes:
            result["validation_errors"].extend(
                f"class {cid} assigned multiple times" for cid in sorted(set(duplicate_classes), key=self._sort_key)
            )
            result["hard_violations"] += len(set(duplicate_classes))
            result["valid"] = False
        return result

    def soft_violation_class_scores_from_x(self, x_tensor: torch.Tensor, constraints) -> Dict[str, float]:
        """
        Return cid -> score for classes involved in soft distribution violations.

        Scores use the same official-aligned violation predicates as validation.
        Pairwise violations add the soft penalty to both classes. Polygon
        violations add the whole soft cost to each assigned class in the
        violated distribution, which is a heuristic but keeps destroy focused
        on the right constraint neighborhood.
        """
        solution = {}
        for xidx in torch.where(x_tensor > 0.5)[0].tolist():
            cid, tidx, rid = constraints.xidx_to_x[xidx]
            topt = self._time_option_by_index(cid, tidx)
            weeks, days, start, _length = topt["optional_time_bits"]
            solution[cid] = {
                "weeks": weeks,
                "days": days,
                "start": start,
                "room": rid if rid != "dummy" else None,
            }

        assignments, _errors = self._build_assignments(solution)
        scores: Dict[str, float] = {}

        for constraint in self.reader.distributions.get("soft_constraints", []):
            for cid, score in self._constraint_violation_scores(constraint, assignments).items():
                scores[cid] = scores.get(cid, 0.0) + score

        return scores

    def validate_solution(self, solution: Dict[str, dict]) -> dict:
        assignments, validation_errors = self._build_assignments(solution)

        time_raw = sum(a.time_penalty for a in assignments.values())
        room_raw = sum(a.room_penalty for a in assignments.values())

        room_violations = self._room_violations(assignments)
        hard_dist_violations, soft_distribution_raw, soft_details = self._distribution_penalties(assignments)

        hard_violations = room_violations + hard_dist_violations + len(validation_errors)
        student_conflicts = 0

        weighted_time = time_raw * self.weights["time"]
        weighted_room = room_raw * self.weights["room"]
        weighted_distribution = soft_distribution_raw * self.weights["distribution"]
        weighted_student = student_conflicts * self.weights["student"]
        total = weighted_time + weighted_room + weighted_distribution + weighted_student

        return {
            "instance": self.reader.problem_name,
            "valid": hard_violations == 0,
            "time_raw": time_raw,
            "room_raw": room_raw,
            "distribution_raw": soft_distribution_raw,
            "student_conflicts": student_conflicts,
            # Official validator labels component values as raw penalties.
            "time": time_raw,
            "room": room_raw,
            "distribution": soft_distribution_raw,
            "student": student_conflicts,
            "weighted_time": weighted_time,
            "weighted_room": weighted_room,
            "weighted_distribution": weighted_distribution,
            "weighted_student": weighted_student,
            "total": total,
            "hard_violations": hard_violations,
            "room_violations": room_violations,
            "hard_distribution_violations": hard_dist_violations,
            "validation_errors": validation_errors,
            "soft_details": soft_details,
        }

    # ------------------------------------------------------------------
    # Assignment parsing
    # ------------------------------------------------------------------

    def _build_assignments(self, solution: Dict[str, dict]) -> Tuple[Dict[str, Assignment], List[str]]:
        assignments = {}
        errors = []
        expected = set(self.reader.classes.keys())
        present = set(solution.keys())

        for cid in sorted(expected - present, key=self._sort_key):
            errors.append(f"class {cid} missing")
        for cid in sorted(present - expected, key=self._sort_key):
            errors.append(f"class {cid} not in problem")

        for cid in sorted(expected & present, key=self._sort_key):
            class_data = self.reader.classes[cid]
            sol = solution[cid]
            time_option = self._match_time_option(cid, sol)
            if time_option is None:
                errors.append(f"class {cid} has invalid time assignment")
                continue

            room = sol.get("room")
            room_penalty = 0
            if class_data["room_required"]:
                if room is None:
                    errors.append(f"class {cid} requires a room")
                    continue
                room_option = self._match_room_option(cid, room)
                if room_option is None:
                    errors.append(f"class {cid} has invalid room {room}")
                    continue
                room_penalty = int(room_option.get("penalty", 0))
            elif room is not None:
                errors.append(f"class {cid} should not have room {room}")
                continue

            weeks, days, start, length = time_option["optional_time_bits"]
            assignments[cid] = Assignment(
                cid=cid,
                weeks=weeks,
                days=days,
                start=int(start),
                length=int(length),
                room=room,
                time_penalty=int(time_option.get("penalty", 0)),
                room_penalty=room_penalty,
            )

        return assignments, errors

    def _match_time_option(self, cid: str, sol: dict) -> Optional[dict]:
        for option in self.reader.classes[cid]["time_options"]:
            weeks, days, start, _length = option["optional_time_bits"]
            if weeks == sol.get("weeks") and days == sol.get("days") and int(start) == int(sol.get("start", -1)):
                return option
        return None

    def _time_option_by_index(self, cid: str, tidx: int) -> dict:
        return self.reader.classes[cid]["time_options"][tidx]

    def _match_room_option(self, cid: str, room: str) -> Optional[dict]:
        for option in self.reader.classes[cid]["room_options"]:
            if str(option["id"]) == str(room):
                return option
        return None

    # ------------------------------------------------------------------
    # Hard room constraints
    # ------------------------------------------------------------------

    def _room_violations(self, assignments: Dict[str, Assignment]) -> int:
        violations = 0
        by_room: Dict[str, List[Assignment]] = {}
        for assignment in assignments.values():
            if assignment.room is None:
                continue
            by_room.setdefault(assignment.room, []).append(assignment)
            for unavailable in self.reader.rooms.get(assignment.room, {}).get("unavailables_bits", []):
                if self._time_overlap_bits(
                    (assignment.weeks, assignment.days, assignment.start, assignment.length),
                    unavailable,
                ):
                    violations += 1

        for room_assignments in by_room.values():
            for a, b in itertools.combinations(room_assignments, 2):
                if self._overlap(a, b):
                    violations += 1
        return violations

    # ------------------------------------------------------------------
    # Distribution constraints
    # ------------------------------------------------------------------

    def _distribution_penalties(self, assignments: Dict[str, Assignment]) -> Tuple[int, int, list]:
        hard_violations = 0
        soft_cost = 0
        soft_details = []

        for constraint in self.reader.distributions.get("hard_constraints", []):
            hard_violations += self._constraint_violation_count(constraint, assignments, hard=True)

        for constraint in self.reader.distributions.get("soft_constraints", []):
            count = self._constraint_violation_count(constraint, assignments, hard=False)
            penalty = int(constraint.get("penalty", 0))
            ctype = constraint["type"]
            if ctype.startswith(("MaxDayLoad", "MaxBreaks", "MaxBlock")):
                cost = count
            else:
                cost = count * penalty
            soft_cost += cost
            if cost:
                soft_details.append({"type": ctype, "violations": count, "penalty": penalty, "cost": cost})

        return hard_violations, soft_cost, soft_details

    def _constraint_violation_count(self, constraint: dict, assignments: Dict[str, Assignment], hard: bool) -> int:
        ctype, params = self._parse_type(constraint["type"])
        cids = [cid for cid in constraint["classes"] if cid in assignments]

        if len(cids) < 2 and ctype in self.PAIRWISE_TYPES:
            return 0

        if ctype in self.PAIRWISE_TYPES:
            count = 0
            ordered_pairs = self._ordered_pairs(cids) if ctype == "Precedence" else itertools.combinations(cids, 2)
            for cid_a, cid_b in ordered_pairs:
                if self._pair_violates(ctype, params, assignments[cid_a], assignments[cid_b]):
                    count += 1
                    if hard:
                        return count
            return count

        if ctype == "MaxDays":
            days = 0
            for cid in cids:
                days |= self._bits(assignments[cid].days)
            extra = max(0, days.bit_count() - int(params))
            return 1 if hard and extra > 0 else extra

        if ctype == "MaxDayLoad":
            raw_extra = self._max_day_load_extra(cids, assignments, int(params))
            if hard:
                return 1 if raw_extra > 0 else 0
            return int(int(constraint.get("penalty", 0)) * raw_extra // max(self.reader.nrWeeks, 1))

        if ctype == "MaxBreaks":
            r, s = map(int, params.split(","))
            raw_extra = self._max_breaks_extra(cids, assignments, r, s)
            if hard:
                return 1 if raw_extra > 0 else 0
            return int(int(constraint.get("penalty", 0)) * raw_extra // max(self.reader.nrWeeks, 1))

        if ctype == "MaxBlock":
            m, s = map(int, params.split(","))
            raw_extra = self._max_block_extra(cids, assignments, m, s)
            if hard:
                return 1 if raw_extra > 0 else 0
            return int(int(constraint.get("penalty", 0)) * raw_extra // max(self.reader.nrWeeks, 1))

        return 0

    def _constraint_violation_scores(self, constraint: dict, assignments: Dict[str, Assignment]) -> Dict[str, float]:
        ctype, params = self._parse_type(constraint["type"])
        penalty = int(constraint.get("penalty", 0))
        cids = [cid for cid in constraint["classes"] if cid in assignments]
        scores: Dict[str, float] = {}

        if len(cids) < 2 and ctype in self.PAIRWISE_TYPES:
            return scores

        if ctype in self.PAIRWISE_TYPES:
            ordered_pairs = self._ordered_pairs(cids) if ctype == "Precedence" else itertools.combinations(cids, 2)
            for cid_a, cid_b in ordered_pairs:
                if self._pair_violates(ctype, params, assignments[cid_a], assignments[cid_b]):
                    scores[cid_a] = scores.get(cid_a, 0.0) + penalty
                    scores[cid_b] = scores.get(cid_b, 0.0) + penalty
            return scores

        count = self._constraint_violation_count(constraint, assignments, hard=False)
        if count <= 0:
            return scores
        for cid in cids:
            scores[cid] = scores.get(cid, 0.0) + float(count)
        return scores

    def _pair_violates(self, ctype: str, params: Optional[str], a: Assignment, b: Assignment) -> bool:
        if ctype == "SameStart":
            return a.start != b.start
        if ctype == "SameTime":
            return not ((a.start <= b.start and b.end <= a.end) or (b.start <= a.start and a.end <= b.end))
        if ctype == "DifferentTime":
            return not (a.end <= b.start or b.end <= a.start)
        if ctype == "SameDays":
            union = self._bits(a.days) | self._bits(b.days)
            return not (union == self._bits(a.days) or union == self._bits(b.days))
        if ctype == "DifferentDays":
            return (self._bits(a.days) & self._bits(b.days)) != 0
        if ctype == "SameWeeks":
            union = self._bits(a.weeks) | self._bits(b.weeks)
            return not (union == self._bits(a.weeks) or union == self._bits(b.weeks))
        if ctype == "DifferentWeeks":
            return (self._bits(a.weeks) & self._bits(b.weeks)) != 0
        if ctype == "Overlap":
            return not self._overlap(a, b)
        if ctype == "NotOverlap":
            return self._overlap(a, b)
        if ctype == "SameRoom":
            return a.room != b.room
        if ctype == "DifferentRoom":
            return a.room == b.room
        if ctype == "SameAttendees":
            return not self._same_attendees_ok(a, b)
        if ctype == "Precedence":
            return not self._precedes(a, b)
        if ctype == "WorkDay":
            s = int(params)
            return self._same_day_week(a, b) and max(a.end, b.end) - min(a.start, b.start) > s
        if ctype == "MinGap":
            g = int(params)
            return self._same_day_week(a, b) and not (a.end + g <= b.start or b.end + g <= a.start)
        return False

    # ------------------------------------------------------------------
    # Polygon constraint helpers
    # ------------------------------------------------------------------

    def _max_day_load_extra(self, cids: List[str], assignments: Dict[str, Assignment], limit: int) -> int:
        total = 0
        for week in range(self.reader.nrWeeks):
            for day in range(self.reader.nrDays):
                load = 0
                for cid in cids:
                    a = assignments[cid]
                    if a.weeks[week] == "1" and a.days[day] == "1":
                        load += a.length
                total += max(0, load - limit)
        return total

    def _max_breaks_extra(self, cids: List[str], assignments: Dict[str, Assignment], max_breaks: int, gap: int) -> int:
        total = 0
        for week in range(self.reader.nrWeeks):
            for day in range(self.reader.nrDays):
                intervals = self._intervals_on(cids, assignments, week, day)
                blocks = self._merge_blocks(intervals, gap)
                total += max(0, len(blocks) - (max_breaks + 1))
        return total

    def _max_block_extra(self, cids: List[str], assignments: Dict[str, Assignment], max_length: int, gap: int) -> int:
        total = 0
        for week in range(self.reader.nrWeeks):
            for day in range(self.reader.nrDays):
                intervals = self._intervals_on(cids, assignments, week, day)
                blocks = self._merge_blocks(intervals, gap)
                for start, end, class_count in blocks:
                    if class_count > 1 and end - start > max_length:
                        total += 1
        return total

    def _intervals_on(
        self,
        cids: Iterable[str],
        assignments: Dict[str, Assignment],
        week: int,
        day: int,
    ) -> List[Tuple[int, int]]:
        intervals = []
        for cid in cids:
            a = assignments[cid]
            if a.weeks[week] == "1" and a.days[day] == "1":
                intervals.append((a.start, a.end))
        return intervals

    def _merge_blocks(self, intervals: List[Tuple[int, int]], gap: int) -> List[Tuple[int, int, int]]:
        if not intervals:
            return []
        blocks = []
        current_start, current_end = sorted(intervals)[0]
        class_count = 1
        for start, end in sorted(intervals)[1:]:
            if current_end + gap >= start:
                current_end = max(current_end, end)
                class_count += 1
            else:
                blocks.append((current_start, current_end, class_count))
                current_start, current_end = start, end
                class_count = 1
        blocks.append((current_start, current_end, class_count))
        return blocks

    # ------------------------------------------------------------------
    # Generic time helpers
    # ------------------------------------------------------------------

    def _same_attendees_ok(self, a: Assignment, b: Assignment) -> bool:
        if not self._same_day_week(a, b):
            return True
        travel_ab = self._travel(a.room, b.room)
        travel_ba = self._travel(b.room, a.room)
        return a.end + travel_ab <= b.start or b.end + travel_ba <= a.start

    def _precedes(self, a: Assignment, b: Assignment) -> bool:
        week_a = a.weeks.find("1")
        week_b = b.weeks.find("1")
        day_a = a.days.find("1")
        day_b = b.days.find("1")
        return week_a < week_b or (
            week_a == week_b and (day_a < day_b or (day_a == day_b and a.end <= b.start))
        )

    def _overlap(self, a: Assignment, b: Assignment) -> bool:
        return self._same_day_week(a, b) and a.start < b.end and b.start < a.end

    def _same_day_week(self, a: Assignment, b: Assignment) -> bool:
        return (self._bits(a.days) & self._bits(b.days)) != 0 and (self._bits(a.weeks) & self._bits(b.weeks)) != 0

    def _time_overlap_bits(self, a_bits: tuple, b_bits: tuple) -> bool:
        a_weeks, a_days, a_start, a_length = a_bits
        b_weeks, b_days, b_start, b_length = b_bits
        if a_weeks is None or a_days is None or b_weeks is None or b_days is None:
            return False
        return (
            (self._bits(a_weeks) & self._bits(b_weeks)) != 0
            and (self._bits(a_days) & self._bits(b_days)) != 0
            and int(a_start) < int(b_start) + int(b_length)
            and int(b_start) < int(a_start) + int(a_length)
        )

    def _travel(self, room_a: Optional[str], room_b: Optional[str]) -> int:
        if room_a is None or room_b is None:
            return 0
        return int(self.reader.travel.get(str(room_a), {}).get(str(room_b), 0))

    def _parse_type(self, ctype: str) -> Tuple[str, Optional[str]]:
        if "(" not in ctype:
            return ctype, None
        base, rest = ctype.split("(", 1)
        return base, rest.rstrip(")")

    def _ordered_pairs(self, cids: List[str]):
        for i in range(len(cids)):
            for j in range(i + 1, len(cids)):
                yield cids[i], cids[j]

    def _bits(self, bit_string: str) -> int:
        return int(bit_string or "0", 2)

    def _sort_key(self, value: str):
        return int(value) if str(value).isdigit() else str(value)
