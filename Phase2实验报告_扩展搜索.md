# Phase2实验报告：扩展搜索

## 实验说明

本轮实验严格从 `data/solutions` 中已有 solution XML 开始，不调用 Gurobi，也不运行 MIP/数学规划求解器。
计分使用 `src/solution_io/local_validator.py`，目标函数为 time、room、distribution 三项，student 固定为 0。

Phase2 使用轻量 direct solution-pool repair：从解池有效最优解出发，优先抽取当前解中带来 distribution penalty 的 class，并用解池中已出现过的该 class 分配进行 beam repair。
本报告是新一轮扩展搜索结果，未覆盖上一轮 `Phase2实验报告.md` 与 `output/phase2_direct_all_instances_stronger/`。

## 参数

- `max_iter`: 35
- `destroy_size`: 6
- `mixed_high_distribution_prob`: 0.9
- `repair_method`: beam
- `beam_width`: 3
- `repair_candidate_limit`: 16
- `seed`: 20260427

## 总览

- 实例数: 15
- 成功完成: 15
- 输出可行: 15/15
- 找到改进: 2
- 相比上一轮 stronger：`muni-fsps-spr17c` 从 `10649` 进一步降低到 `10601`
- 明细 CSV: `output/phase2_direct_all_instances_extended_20260425/phase2_direct_all_instances_summary.csv`

## 官方接口抽查

- `muni-fi-spr17_phase2_direct.xml`: 官方 validator 返回 valid，Total cost = 188，Time = 10，Room = 108，Distribution = 5，Student = 0。
- `muni-fsps-spr17c_phase2_direct.xml`: 官方 validator 返回 valid，Total cost = 10601，Time = 280，Room = 1186，Distribution = 161，Student = 0。

## Improvement 来源分析

两个出现改进的实例都存在大量 invalid 解：`muni-fi-spr17` 有 88/98 个 invalid，`muni-fsps-spr17c` 有 79/98 个 invalid。这说明解池里并非只有可行解信息有价值；大量 invalid 解虽然整体不可行，但仍包含局部低代价 assignment。

在 `muni-fi-spr17` 中，Phase2 相比 pool best 改动 7 个 class，7 个新 assignment 全部来自 invalid 解。改进来自 distribution raw penalty 从 7 降到 5，time 和 room 不变，因此 total 从 208 降到 188。具体来说，原解的 `MaxBlock(48,10)` soft violation 被消除，只剩 `NotOverlap` penalty。

在 `muni-fsps-spr17c` 中，Phase2 相比 pool best 改动 6 个 class，其中大部分新 assignment 只在 invalid 解中出现。改进同时来自 time、room、distribution 三项：time raw 从 285 到 280，room raw 从 1187 到 1186，distribution raw 从 164 到 161；按该实例权重加总后 total 从 10772 降到 10601。

结论是：invalid-heavy 解池提供了更大的“局部片段库”。这些 invalid 解通常因为少量 hard constraint 或 XML assignment 问题整体不可用，但其中部分 class 的 time-room 分配能降低软约束代价。Phase2 的作用就是从 valid incumbent 出发，只抽取这些低代价局部片段，并通过 validator-aware beam repair 过滤掉会破坏 hard feasibility 的组合。

## 结果表

| instance | valid pool | invalid pool | pool best | Phase2 total | valid | improvement | time(s) |
|---|---:|---:|---:|---:|---|---:|---:|
| agh-ggis-spr17 | 98 | 0 | 16514 | 16514 | True | 0.0 (0.00%) | 374.202 |
| lums-spr18 | 84 | 14 | 95 | 95 | True | 0.0 (0.00%) | 56.485 |
| mary-fal18 | 98 | 0 | 1871 | 1871 | True | 0.0 (0.00%) | 12.895 |
| mary-spr17 | 98 | 0 | 14473 | 14473 | True | 0.0 (0.00%) | 50.129 |
| muni-fi-fal17 | 98 | 0 | 273 | 273 | True | 0.0 (0.00%) | 27.424 |
| muni-fi-spr16 | 10 | 88 | 372 | 372 | True | 0.0 (0.00%) | 5.905 |
| muni-fi-spr17 | 10 | 88 | 208 | 188 | True | 20.0 (9.62%) | 73.139 |
| muni-fsps-spr17 | 78 | 20 | 368 | 368 | True | 0.0 (0.00%) | 16.979 |
| muni-fsps-spr17c | 19 | 79 | 10772 | 10601 | True | 171.0 (1.59%) | 127.096 |
| nbi-spr18 | 95 | 3 | 13721 | 13721 | True | 0.0 (0.00%) | 56.278 |
| pu-d5-spr17 | 98 | 0 | 14631 | 14631 | True | 0.0 (0.00%) | 119.506 |
| pu-llr-spr17 | 98 | 0 | 3561 | 3561 | True | 0.0 (0.00%) | 22.161 |
| tg-fal17 | 98 | 0 | 4215 | 4215 | True | 0.0 (0.00%) | 281.925 |
| tg-spr18 | 98 | 0 | 14128 | 14128 | True | 0.0 (0.00%) | 120.415 |
| yach-fal17 | 98 | 0 | 314 | 314 | True | 0.0 (0.00%) | 52.41 |

## 结论

这组实验验证了 Phase2 可以在无 Gurobi 环境下完整跑通全实例，并保持输出 hard-feasible。
扩展搜索没有增加改进实例数量，但提高了 `muni-fsps-spr17c` 的改进幅度；目前最有收益的方向是继续围绕 distribution-heavy instances 做更聚焦的多 seed 搜索，而不是盲目扩大所有实例参数。
