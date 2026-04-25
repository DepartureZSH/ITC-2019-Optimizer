# AGENTS.md — ITC2019 MAZE Project

## Project Overview

Post-optimization of feasible solutions for the **International Timetabling Competition 2019 (ITC2019)** problem. The MIP solver has already produced 98 feasible solutions per instance (14 instances total). The goal is to further minimize the weighted-sum objective while keeping all hard constraints satisfied.

**This version removes student assignment and student conflict.** Student sectioning is not performed; solution XMLs contain no `<student>` elements inside classes. The effective objective is three-component only:

**Objective (minimize):**
```
Total = w_time × TimePenalty + w_room × RoomPenalty + w_dist × DistributionPenalty
```

The problem XML still contains `<students>` and `<optimization student="...">` nodes, but the student weight is unused in this version.

---

## Repository Layout

```
ITC-2019-MAZE/
├── AGENTS.md                   # this file
├── README.md                   # problem background (Chinese)
├── Dataset.md                  # ITC2019 data format spec
├── resolver.py                 # legacy entry point (GPU memory check)
├── main.py                     # unified entry point (reads config.yaml)
├── config.yaml                 # run configuration
├── data/
│   ├── reduced/                # 29 problem XML files (preprocessed/reduced)
│   └── solutions/              # 14 instance folders, 98 MIP solutions each
│       └── <instance>/
│           └── solution<N>_<instance>.xml
└── src/
    ├── __init__.py
    └── utils/
        ├── dataReader.py           # PSTTReader — XML parser for problem+solution
        ├── ConstraintsResolver_v2.py  # PyTorch tensor constraint model
        ├── ConstraintsResolver.py  # (legacy, v1)
        ├── constraints.py
        └── preconstraints.py
```

**Post-optimization packages (to be added under `src/`):**
```
src/
├── evaluator/      # shared cost evaluation (time/room/dist/student)
├── solution_io/    # load/save XML solutions, encode to x_tensor
├── local_search/   # Approach 1: neighborhood-based local search
├── lns/            # Approach 2: large neighborhood search (fix-and-optimize)
├── tensor_search/  # Approach 3: gradient / beam search on x_tensor
└── merging/        # Approach 4: solution pool merging
```

---

## Core Classes

### `PSTTReader` (`src/utils/dataReader.py`)

Parses an ITC2019 problem XML file into Python dicts. Key attributes after `_parse()`:

| Attribute | Type | Description |
|-----------|------|-------------|
| `problem_name` | str | instance name |
| `nrDays/nrWeeks/slotsPerDay` | int | time grid dimensions |
| `optimization` | dict | `{time, room, distribution, student}` weights |
| `rooms` | dict[id→dict] | capacity, unavailables_bits, unavailable_zip |
| `travel` | dict[id→dict[id→int]] | travel time between rooms (slots) |
| `classes` | dict[id→dict] | limit, parent, room_required, room_options, time_options |
| `students` | dict[id→dict] | list of course ids per student |
| `distributions` | dict | `{hard_constraints: [...], soft_constraints: [...]}` |

Each `class` dict has:
- `time_options`: list of `{optional_time_bits: (weeks_str, days_str, start, length), optional_time: tensor, penalty: int}`
- `room_options`: list of `{id: str, penalty: int}`
- `room_required`: bool (False → assign dummy room)

Each `time_options` entry uses `optional_time_bits = (weeks_bits_str, days_bits_str, start_int, length_int)`. Bit strings are MSB-first (e.g. `"1010100"` = Mon+Wed+Fri for 7-day week).

### `ConstraintsResolver` (`src/utils/ConstraintsResolver_v2.py`)

Builds a PyTorch sparse-tensor constraint model on top of a `PSTTReader`. Call `build_model()` once.

**Decision variable encoding:**
- `x[(cid, tidx, rid)] → int` maps (class, time_option_index, room_id) to a flat index into `x_tensor`
- `x_tensor`: float32 1D tensor of length N (number of valid assignments); value 1.0 = selected
- `xidx_to_x[idx] → (cid, tidx, rid)` reverse map
- `y[(cid, tidx)] → [x_indices]` — all x variables for a given (class, time)
- `w[(cid, rid)] → [x_indices]` — all x variables for a given (class, room)

**Tensor structures (built by `build_model()`):**

| Attribute | Shape | Description |
|-----------|-------|-------------|
| `x_tensor` | (N,) | binary assignment vector |
| `room_transformer` | (N,) | room id for each x variable |
| `week_transformer` | (nrWeeks, N) | week bits for each x variable |
| `day_transformer` | (nrDays, N) | day bits for each x variable |
| `start_transformer` | (N,) | start slot |
| `end_transformer` | (N,) | start + length |
| `valid_dist_tensor` | sparse (num_classes, N) | assignment constraint matrix |
| `hard_dist_tensor` | sparse (num_hard, N) | hard distribution constraints |
| `hard_dist_upper_tensor` | (1, num_hard) | upper bounds (all 1) |
| `soft_dist_tensor` | sparse (num_soft, N) | soft distribution constraints |
| `soft_dist_upper_tensor` | (1, num_soft) | upper bounds |
| `soft_dist_cost_tensor` | (1, num_soft) | per-constraint penalty |

**Objective (stored in `objective_penalty`):**
```python
w_time, w_room, (soft_dist, soft_upper, w_dist) = constraints.objective_penalty
time_pen  = x @ w_time
room_pen  = x @ w_room
soft_pen  = ((x @ soft_dist.T - soft_upper).clamp(0) * w_dist).sum()
total_pen = time_pen + room_pen + soft_pen
# Student conflict is NOT included — student assignment is out of scope in this version.
```

**Constraint checking:**
```python
# Hard constraint violations (must be 0 for feasibility):
viol = (x @ hard_dist.T - hard_upper).clamp(0).sum()

# Valid assignment check (each class assigned exactly once):
assign_counts = sparse_mm(valid_dist, x.unsqueeze(1))  # should all be 1
```

---

## Solution XML Format

```xml
<solution name="instance-name" runtime="..." technique="MIP" author="ZSH">
  <class id="1" days="0010000" start="116" weeks="0101010010010101" room="43" />
  ...
</solution>
```

`days` and `weeks` are bit strings (MSB-first). `room` attribute is absent if the class needs no room. There are **no `<student>` child elements** — student assignment is out of scope in this version.

---

## Data Encoding Notes

- Time slot unit: **5 minutes**; 288 slots/day = midnight to midnight
- `days` bit string length = `nrDays` (typically 7)
- `weeks` bit string length = `nrWeeks` (13–18 depending on instance)
- Travel time is in **slots**; student conflict occurs if `end_i + travel(room_i, room_j) > start_j`
- Room IDs and class IDs in the XML are **strings**, converted to int inside `PSTTReader`
- `dummy` room is used internally for `room_required=False` classes

---

## Key Conventions

- **Never violate hard constraints** — a solution with any hard violation is invalid
- Student conflict is **not part of this version's objective** — student assignment is removed from scope
- `ConstraintsResolver_v2` supports `device='cuda:0'` or `'cpu'`
- `matrix=True` in `PSTTReader` builds full 3D tensors (weeks×days×slots) for rooms and times; `matrix=False` is lighter (bits only)
- All IDs are stored as **strings** in reader dicts (e.g. `classes["1"]`), but `cid_to_idx` maps string → int index

---

## Running

```bash
# Legacy entry point (just builds model and checks GPU memory):
python resolver.py

# Unified entry point (to be implemented):
python main.py --config config.yaml
```

---

## Environment

- Python 3.x, PyTorch (CUDA supported)
- GPU: available via `torch.cuda.is_available()`
- Dependencies: `torch`, `tqdm`, `numpy`, `xml.etree.ElementTree`, `pathlib`, `yaml`
