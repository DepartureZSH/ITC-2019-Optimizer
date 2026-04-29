import xml.etree.ElementTree as ET
import torch
import pathlib
from typing import Dict, Optional, Tuple


class SolutionLoader:
    """
    Loads ITC2019 solution XMLs and encodes them into the x_tensor representation
    used by ConstraintsResolver_v2.

    Solution XML format per class:
        <class id="1" days="0010000" start="116" weeks="0101010010010101" room="43" />
    No <student> children — student assignment is out of scope.
    """

    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------

    def load_xml(self, xml_path: str) -> Dict:
        """
        Parse a solution XML into a plain dict.

        Returns:
            {
                cid (str): {
                    "days":  str  (bit string, e.g. "0010000"),
                    "start": int,
                    "weeks": str  (bit string),
                    "room":  str | None   (None for no-room classes)
                },
                ...
            }
        """
        tree = ET.parse(str(xml_path))
        root = tree.getroot()

        solution = {}
        for cls in root.findall("class"):
            cid = cls.attrib["id"]
            solution[cid] = {
                "days":  cls.attrib.get("days", ""),
                "start": int(cls.attrib.get("start", 0)),
                "weeks": cls.attrib.get("weeks", ""),
                "room":  cls.attrib.get("room"),   # None if absent
            }
        return solution

    def load_all(self, solutions_dir: str, instance: str) -> list:
        """
        Load all solution XMLs for an instance from solutions_dir/<instance>/.
        Returns a list of (path, solution_dict) tuples sorted by filename.
        """
        folder = pathlib.Path(solutions_dir) / instance
        paths = sorted(folder.glob(f"solution*_{instance}.xml"),
                       key=lambda p: int(p.stem.split("_")[0].replace("solution", "")))
        return [(str(p), self.load_xml(p)) for p in paths]

    # ------------------------------------------------------------------
    # Encode: solution dict → x_tensor
    # ------------------------------------------------------------------

    def encode(self, solution: Dict, constraints) -> torch.Tensor:
        """
        Encode a solution dict into a binary x_tensor compatible with
        ConstraintsResolver_v2.

        Returns a float32 tensor on the same device as constraints.x_tensor.
        Raises ValueError for any class whose assignment cannot be matched.
        """
        x = torch.zeros_like(constraints.x_tensor)
        unmatched = []

        for cid, assignment in solution.items():
            if cid not in constraints.reader.classes:
                continue

            days_str  = assignment["days"]
            start     = assignment["start"]
            weeks_str = assignment["weeks"]
            room_str  = assignment["room"]  # None → dummy

            rid = room_str if room_str is not None else "dummy"

            # Find the matching tidx in class_to_time_options
            tidx = self._match_time_option(cid, days_str, start, weeks_str, constraints)

            if tidx is None:
                unmatched.append(cid)
                continue

            key = (cid, tidx, rid)
            if key not in constraints.x:
                # Room not in valid options for this class (e.g. filtered out)
                unmatched.append(cid)
                continue

            x[constraints.x[key]] = 1.0

        if unmatched:
            raise ValueError(
                f"Could not match {len(unmatched)} classes: {unmatched[:10]}"
                + (" ..." if len(unmatched) > 10 else "")
            )
        return x

    def encode_with_fallback(
        self,
        solution: Dict,
        constraints,
        fallback_x: torch.Tensor,
    ) -> Tuple[torch.Tensor, Dict[str, int]]:
        """
        Encode a possibly partial/invalid solution by filling unmatched classes
        from a known complete incumbent.

        This is intentionally conservative: we only trust exact solution
        assignments that map to an existing x variable. Missing, blank, invalid,
        or room-filtered assignments are copied class-by-class from fallback_x.
        The caller should still run the local validator and keep only feasible
        candidates for best-solution decisions.
        """
        fallback = self._class_assignment_from_x(fallback_x, constraints)
        x = torch.zeros_like(constraints.x_tensor)
        stats = {
            "matched": 0,
            "fallback": 0,
            "missing": 0,
            "invalid_time": 0,
            "invalid_room": 0,
            "filtered_room_time": 0,
            "unmatched": 0,
        }

        for cid in constraints.reader.classes:
            xidx, reason = self._match_assignment_xidx(cid, solution.get(cid), constraints)
            if xidx is not None:
                x[xidx] = 1.0
                stats["matched"] += 1
                continue

            if reason in stats:
                stats[reason] += 1
            else:
                stats["unmatched"] += 1

            fallback_idx = fallback.get(cid)
            if fallback_idx is not None:
                x[fallback_idx] = 1.0
                stats["fallback"] += 1
            else:
                stats["unmatched"] += 1

        return x, stats

    def _match_time_option(self, cid: str, days_str: str, start: int,
                           weeks_str: str, constraints) -> Optional[int]:
        """Return tidx of the matching time option, or None if not found."""
        for topt, tidx in constraints.class_to_time_options[cid]:
            w, d, s, _l = topt["optional_time_bits"]
            if d == days_str and s == start and w == weeks_str:
                return tidx
        return None

    def _match_assignment_xidx(self, cid: str, assignment: Optional[Dict], constraints):
        """Return (xidx, reason). reason is set when xidx is None."""
        if assignment is None:
            return None, "missing"

        days_str = assignment.get("days", "")
        weeks_str = assignment.get("weeks", "")
        start = assignment.get("start", 0)
        room_str = assignment.get("room")

        tidx = self._match_time_option(cid, days_str, start, weeks_str, constraints)
        if tidx is None:
            return None, "invalid_time"

        rid = room_str if room_str is not None else "dummy"
        if rid not in constraints.class_to_room_options.get(cid, []):
            return None, "invalid_room"

        key = (cid, tidx, rid)
        if key not in constraints.x:
            return None, "filtered_room_time"
        return constraints.x[key], None

    def _class_assignment_from_x(self, x_tensor: torch.Tensor, constraints) -> Dict[str, int]:
        result = {}
        for xidx in torch.where(x_tensor > 0.5)[0].tolist():
            cid, _tidx, _rid = constraints.xidx_to_x[int(xidx)]
            result[cid] = int(xidx)
        return result

    # ------------------------------------------------------------------
    # Decode: x_tensor → solution dict
    # ------------------------------------------------------------------

    def decode(self, x_tensor: torch.Tensor, constraints) -> Dict:
        """
        Convert a binary x_tensor back to a solution dict.
        Only entries with value == 1.0 are included.
        """
        solution = {}
        assigned = torch.where(x_tensor > 0.5)[0].tolist()
        for idx in assigned:
            cid, tidx, rid = constraints.xidx_to_x[idx]
            topt, _ = constraints.class_to_time_options[cid][tidx]  # list index = tidx
            # Recover (topt, tidx) at the correct tidx
            topt = self._get_topt(cid, tidx, constraints)
            w, d, s, _l = topt["optional_time_bits"]
            solution[cid] = {
                "days":  d,
                "start": s,
                "weeks": w,
                "room":  rid if rid != "dummy" else None,
            }
        return solution

    def _get_topt(self, cid: str, tidx: int, constraints):
        for topt, t in constraints.class_to_time_options[cid]:
            if t == tidx:
                return topt
        raise KeyError(f"tidx {tidx} not found for class {cid}")

    # ------------------------------------------------------------------
    # Save XML
    # ------------------------------------------------------------------

    def save_xml(self, solution: Dict, reader, out_path: str,
                 meta: Optional[Dict] = None):
        """
        Write a solution dict to ITC2019 solution XML format.

        meta keys (all optional):
            name, runtime, cores, technique, author, institution, country
        """
        meta = meta or {}
        root = ET.Element("solution")
        root.set("name",        meta.get("name", reader.problem_name or ""))
        root.set("runtime",     str(meta.get("runtime", 0)))
        if "cores" in meta:
            root.set("cores", str(meta["cores"]))
        root.set("technique",   meta.get("technique", "post-optimization"))
        root.set("author",      meta.get("author", "ZSH"))
        root.set("institution", meta.get("institution", "UNNC"))
        root.set("country",     meta.get("country", "China"))

        for cid in sorted(solution.keys(), key=lambda x: int(x)):
            asgn = solution[cid]
            elem = ET.SubElement(root, "class")
            elem.set("id",    cid)
            elem.set("days",  asgn["days"])
            elem.set("start", str(asgn["start"]))
            elem.set("weeks", asgn["weeks"])
            if asgn["room"] is not None:
                elem.set("room", asgn["room"])

        tree = ET.ElementTree(root)
        ET.indent(tree, space="\t")
        pathlib.Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n'
                    b'<!DOCTYPE solution PUBLIC\n'
                    b'\t"-//ITC 2019//DTD Problem Format/EN"\n'
                    b'\t"http://www.itc2019.org/competition-format.dtd">\n')
            tree.write(f, encoding="utf-8", xml_declaration=False)
