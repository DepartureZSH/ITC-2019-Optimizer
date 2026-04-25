# Phase2实验报告

## 实验说明

本轮实验严格从 `data/solutions` 中已有 solution XML 开始，不调用 Gurobi，也不运行 MIP/数学规划求解器。
计分使用 `src/solution_io/local_validator.py`，目标函数为 time、room、distribution 三项，student 固定为 0。

Phase2 使用轻量 direct solution-pool repair：从解池有效最优解出发，优先抽取当前解中带来 distribution penalty 的 class，并用解池中已出现过的该 class 分配进行 beam repair。

## 参数

- `max_iter`: 20
- `destroy_size`: 5
- `mixed_high_distribution_prob`: 0.8
- `repair_method`: beam
- `beam_width`: 2
- `repair_candidate_limit`: 12
- `seed`: 20260426

## 总览

- 实例数: 15
- 成功完成: 15
- 输出可行: 15/15
- 找到改进: 2
- 解池验证 CSV: `output/validation/solutions_validation_summary.csv`
- 明细 CSV: `output/phase2_direct_all_instances_stronger/phase2_direct_all_instances_summary.csv`

## 官方接口抽查

- `muni-fi-spr17_phase2_direct.xml`: 官方 validator 返回 valid，Total cost = 188，Time = 10，Room = 108，Distribution = 5，Student = 0。
- `muni-fsps-spr17c_phase2_direct.xml`: 本地 validator 返回 valid，Total cost = 10649；官方接口两次调用分别返回 504 proxy timeout 和 SSL EOF，未得到可用判定。

## 结果表

| instance | valid pool | invalid pool | pool best | Phase2 total | valid | improvement | time(s) |
|---|---:|---:|---:|---:|---|---:|---:|
| agh-ggis-spr17 | 98 | 0 | 16514 | 16514 | True | 0.0 (0.00%) | 104.759 |
| lums-spr18 | 84 | 14 | 95 | 95 | True | 0.0 (0.00%) | 27.204 |
| mary-fal18 | 98 | 0 | 1871 | 1871 | True | 0.0 (0.00%) | 4.835 |
| mary-spr17 | 98 | 0 | 14473 | 14473 | True | 0.0 (0.00%) | 24.634 |
| muni-fi-fal17 | 98 | 0 | 273 | 273 | True | 0.0 (0.00%) | 11.045 |
| muni-fi-spr16 | 10 | 88 | 372 | 372 | True | 0.0 (0.00%) | 4.505 |
| muni-fi-spr17 | 10 | 88 | 208 | 188 | True | 20.0 (9.62%) | 15.98 |
| muni-fsps-spr17 | 78 | 20 | 368 | 368 | True | 0.0 (0.00%) | 7.275 |
| muni-fsps-spr17c | 19 | 79 | 10772 | 10649 | True | 123.0 (1.14%) | 36.719 |
| nbi-spr18 | 95 | 3 | 13721 | 13721 | True | 0.0 (0.00%) | 18.894 |
| pu-d5-spr17 | 98 | 0 | 14631 | 14631 | True | 0.0 (0.00%) | 27.694 |
| pu-llr-spr17 | 98 | 0 | 3561 | 3561 | True | 0.0 (0.00%) | 7.69 |
| tg-fal17 | 98 | 0 | 4215 | 4215 | True | 0.0 (0.00%) | 92.519 |
| tg-spr18 | 98 | 0 | 14128 | 14128 | True | 0.0 (0.00%) | 43.359 |
| yach-fal17 | 98 | 0 | 314 | 314 | True | 0.0 (0.00%) | 17.809 |

## 结论

这组实验验证了 Phase2 可以在无 Gurobi 环境下完整跑通全实例，并保持输出 hard-feasible。
当前参数很保守，主要目标是全实例真实验证和建立可复现实验基线；若要追求更大改进，下一步应扩大 candidate domain 或增加迭代数，但需要控制运行时间。
