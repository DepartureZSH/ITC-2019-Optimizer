import random
from collections import defaultdict
from typing import Dict, Iterable, List, Optional

import torch


class NeighborhoodGenerator:
    """Generate local-search moves over the flat x_tensor assignment space."""

    def __init__(self, constraints):
        self.c = constraints
        self._cid_domain: Dict[str, List[int]] = defaultdict(list)
        self._time_room_to_idx = {}
        for (cid, tidx, rid), xidx in self.c.x.items():
            self._cid_domain[cid].append(xidx)
            self._time_room_to_idx[(cid, tidx, rid)] = xidx

    def get_class_options(self, cid: str) -> List[int]:
        """Return all valid x indices for one class."""
        return list(self._cid_domain.get(cid, []))

    def current_assignment(self, x_tensor: torch.Tensor) -> Dict[str, int]:
        """Return cid -> selected x index for a complete one-hot solution."""
        assigned = {}
        for xidx in torch.where(x_tensor > 0.5)[0].tolist():
            cid, _, _ = self.c.xidx_to_x[xidx]
            assigned[cid] = xidx
        return assigned

    def random_class(self, x_tensor: torch.Tensor) -> Optional[str]:
        """Pick a random assigned class id."""
        assigned = self.current_assignment(x_tensor)
        if not assigned:
            return None
        return random.choice(list(assigned.keys()))

    def single_class_neighbors(
        self,
        x_tensor: torch.Tensor,
        cid: Optional[str] = None,
        shuffle: bool = False,
    ) -> Iterable[dict]:
        """Yield moves that replace one class assignment with another option."""
        assigned = self.current_assignment(x_tensor)
        cids = [cid] if cid is not None else list(assigned.keys())
        if shuffle:
            random.shuffle(cids)

        for current_cid in cids:
            old_idx = assigned.get(current_cid)
            if old_idx is None:
                continue
            options = self.get_class_options(current_cid)
            if shuffle:
                random.shuffle(options)
            for new_idx in options:
                if new_idx == old_idx:
                    continue
                yield {
                    "type": "single_class",
                    "cid": current_cid,
                    "old_idx": old_idx,
                    "new_idx": new_idx,
                }

    def room_swap_neighbors(
        self,
        x_tensor: torch.Tensor,
        shuffle: bool = False,
    ) -> Iterable[dict]:
        """
        Yield moves that swap rooms between two classes with the same time option.

        This is intentionally conservative: only exact same tidx values are
        considered, and dummy-room swaps are skipped.
        """
        assigned = list(self.current_assignment(x_tensor).items())
        if shuffle:
            random.shuffle(assigned)

        for i, (cid_a, idx_a) in enumerate(assigned):
            _, tidx_a, rid_a = self.c.xidx_to_x[idx_a]
            if rid_a == "dummy":
                continue
            for cid_b, idx_b in assigned[i + 1:]:
                _, tidx_b, rid_b = self.c.xidx_to_x[idx_b]
                if rid_b == "dummy" or tidx_a != tidx_b or rid_a == rid_b:
                    continue

                new_a = self._time_room_to_idx.get((cid_a, tidx_a, rid_b))
                new_b = self._time_room_to_idx.get((cid_b, tidx_b, rid_a))
                if new_a is None or new_b is None:
                    continue

                yield {
                    "type": "room_swap",
                    "cid_a": cid_a,
                    "cid_b": cid_b,
                    "old_indices": [idx_a, idx_b],
                    "new_indices": [new_a, new_b],
                }
