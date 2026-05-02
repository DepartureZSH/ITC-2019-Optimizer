# Phase 1A 实验报告：完整 MIP Class Assignment

## 1. 阶段目标

Phase 1A 负责求解固定学生分配之前的 class assignment 问题，即为每个 class 选择：

```text
time option + room option
```

本阶段不写入 `<student>` 元素，目标函数只考虑三项：

```text
Total = w_time * TimePenalty
      + w_room * RoomPenalty
      + w_distribution * DistributionPenalty
```

## 2. Pipeline 位置

```text
SOTA/DTU reduced data XML
 -> Phase 1A full MIP class assignment
 -> Phase 1 solution pool
 -> Phase 1B post-optimization
```

## 3. 当前数据覆盖范围

ITC2019 总体约有 30 个 instances。目前只有约 15 个 instances 拥有可用的 MIP solution pool。

| 范围 | 状态 |
|---|---|
| 全部 ITC2019 instances | 约 30 个 |
| 当前已有 MIP solution pool | 约 15 个 |
| 每个已有 pool 的解数量 | 通常 98 个 XML |
| 剩余 instances | 约 15 个，完整 MIP 暂未跑出可用 solution pool |

## 4. 当前 MIP Pool 验证结果

已有结果来自：

```text
output/validation/solutions_validation_summary.csv
```

| instance | solutions | valid | invalid | best valid solution | best valid total |
|---|---:|---:|---:|---|---:|
| agh-fal17 | 待跑 | 待跑 | 待跑 | 待跑 | 待跑 |
| agh-fis-spr17 | 待跑 | 待跑 | 待跑 | 待跑 | 待跑 |
| agh-ggis-spr17 | 98 | 98 | 0 | solution43 | 16514 |
| agh-ggos-spr17 | 待跑 | 待跑 | 待跑 | 待跑 | 待跑 |
| agh-h-spr17 | 待跑 | 待跑 | 待跑 | 待跑 | 待跑 |
| bet-fal17 | 待跑 | 待跑 | 待跑 | 待跑 | 待跑 |
| bet-spr18 | 待跑 | 待跑 | 待跑 | 待跑 | 待跑 |
| iku-fal17 | 待跑 | 待跑 | 待跑 | 待跑 | 待跑 |
| iku-spr18 | 待跑 | 待跑 | 待跑 | 待跑 | 待跑 |
| lums-fal17 | 待跑 | 待跑 | 待跑 | 待跑 | 待跑 |
| lums-spr18 | 98 | 84 | 14 | solution1 | 95 |
| mary-fal18 | 98 | 98 | 0 | solution41 | 1871 |
| mary-spr17 | 98 | 98 | 0 | solution1 | 14473 |
| muni-fi-fal17 | 98 | 98 | 0 | solution1 | 273 |
| muni-fi-spr16 | 98 | 10 | 88 | solution31 | 372 |
| muni-fi-spr17 | 98 | 10 | 88 | solution21 | 208 |
| muni-fsps-spr17 | 98 | 78 | 20 | solution77 | 368 |
| muni-fsps-spr17c | 98 | 19 | 79 | solution91 | 10772 |
| muni-fspsx-fal17 | 待跑 | 待跑 | 待跑 | 待跑 | 待跑 |
| muni-pdf-spr16 | 待跑 | 待跑 | 待跑 | 待跑 | 待跑 |
| muni-pdf-spr16c | 待跑 | 待跑 | 待跑 | 待跑 | 待跑 |
| muni-pdfx-fal17 | 待跑 | 待跑 | 待跑 | 待跑 | 待跑 |
| nbi-spr18 | 98 | 95 | 3 | solution11 | 13721 |
| pu-d5-spr17 | 98 | 98 | 0 | solution1 | 14631 |
| pu-d9-fal19 | 待跑 | 待跑 | 待跑 | 待跑 | 待跑 |
| pu-llr-spr17 | 98 | 98 | 0 | solution74 | 3561 |
| pu-proj-fal19 | 待跑 | 待跑 | 待跑 | 待跑 | 待跑 |
| tg-fal17 | 98 | 98 | 0 | solution11 | 4215 |
| tg-spr18 | 98 | 98 | 0 | solution11 | 14128 |
| yach-fal17 | 98 | 98 | 0 | solution11 | 314 |

## 5. 与 Official SOTA No-Student 分数对比

对比基线来自：

```text
output/analysis/official_sota_no_student_scores.csv
```

该 CSV 将 official SOTA 完整分数中的 student cost 扣除，得到 `sota_no_student_adjusted`：

```text
sota_no_student_adjusted = official_sota_total - student_conflicts * student_weight
```

因此该对比只用于衡量 class-only 目标，即 time、room、distribution 三项。需要注意：official SOTA 原始解是针对完整目标优化的，包含 student assignment；扣除 student cost 后的 no-student adjusted 分数不一定是 class-only 目标下的理论最优。

Gap 定义：

```text
gap = MIP pool best valid total - SOTA no-student adjusted
```

其中：

| gap | 含义 |
|---|---|
| `gap < 0` | 当前 MIP pool best 在 no-student 口径下低于 official SOTA adjusted |
| `gap = 0` | 当前 MIP pool best 与 official SOTA adjusted 持平 |
| `gap > 0` | 当前 MIP pool best 差于 official SOTA adjusted |

| instance | valid / 98 | invalid / 98 | MIP pool best | SOTA no-student | gap | gap % | best solution |
|---|---:|---:|---:|---:|---:|---:|---|
| agh-fal17 | 待跑 | 待跑 | 待跑 | 60627 | 待填 | 待填 | 待跑 |
| agh-fis-spr17 | 待跑 | 待跑 | 待跑 | 2740 | 待填 | 待填 | 待跑 |
| agh-ggis-spr17 | 98 | 0 | 16514 | 21545 | -5031 | -23.35% | solution43_agh-ggis-spr17.xml |
| agh-ggos-spr17 | 待跑 | 待跑 | 待跑 | 2730 | 待填 | 待填 | 待跑 |
| agh-h-spr17 | 待跑 | 待跑 | 待跑 | 21111 | 待填 | 待填 | 待跑 |
| bet-fal17 | 待跑 | 待跑 | 待跑 | 287106 | 待填 | 待填 | 待跑 |
| bet-spr18 | 待跑 | 待跑 | 待跑 | 346976 | 待填 | 待填 | 待跑 |
| iku-fal17 | 待跑 | 待跑 | 待跑 | 18968 | 待填 | 待填 | 待跑 |
| iku-spr18 | 待跑 | 待跑 | 待跑 | 25863 | 待填 | 待填 | 待跑 |
| lums-fal17 | 待跑 | 待跑 | 待跑 | 349 | 待填 | 待填 | 待跑 |
| lums-spr18 | 84 | 14 | 95 | 95 | +0 | +0.00% | solution1_lums-spr18.xml |
| mary-fal18 | 98 | 0 | 1871 | 1991 | -120 | -6.03% | solution41_mary-fal18.xml |
| mary-spr17 | 98 | 0 | 14473 | 14480 | -7 | -0.05% | solution1_mary-spr17.xml |
| muni-fi-fal17 | 98 | 0 | 273 | 597 | -324 | -54.27% | solution1_muni-fi-fal17.xml |
| muni-fi-spr16 | 10 | 88 | 372 | 842 | -470 | -55.82% | solution31_muni-fi-spr16.xml |
| muni-fi-spr17 | 10 | 88 | 208 | 353 | -145 | -41.08% | solution21_muni-fi-spr17.xml |
| muni-fsps-spr17 | 78 | 20 | 368 | 368 | +0 | +0.00% | solution77_muni-fsps-spr17.xml |
| muni-fsps-spr17c | 19 | 79 | 10772 | 2594 | +8178 | +315.27% | solution91_muni-fsps-spr17c.xml |
| muni-fspsx-fal17 | 待跑 | 待跑 | 待跑 | 10014 | 待填 | 待填 | 待跑 |
| muni-pdf-spr16 | 待跑 | 待跑 | 待跑 | 9999 | 待填 | 待填 | 待跑 |
| muni-pdf-spr16c | 待跑 | 待跑 | 待跑 | 20602 | 待填 | 待填 | 待跑 |
| muni-pdfx-fal17 | 待跑 | 待跑 | 待跑 | 66838 | 待填 | 待填 | 待跑 |
| nbi-spr18 | 95 | 3 | 13721 | 16254 | -2533 | -15.58% | solution11_nbi-spr18.xml |
| pu-d5-spr17 | 98 | 0 | 14631 | 15056 | -425 | -2.82% | solution1_pu-d5-spr17.xml |
| pu-d9-fal19 | 待跑 | 待跑 | 待跑 | 26814 | 待填 | 待填 | 待跑 |
| pu-llr-spr17 | 98 | 0 | 3561 | 4894 | -1333 | -27.24% | solution74_pu-llr-spr17.xml |
| pu-proj-fal19 | 待跑 | 待跑 | 待跑 | 99713 | 待填 | 待填 | 待跑 |
| tg-fal17 | 98 | 0 | 4215 | 4215 | +0 | +0.00% | solution11_tg-fal17.xml |
| tg-spr18 | 98 | 0 | 14128 | 12704 | +1424 | +11.21% | solution11_tg-spr18.xml |
| yach-fal17 | 98 | 0 | 314 | 464 | -150 | -32.33% | solution11_yach-fal17.xml |

汇总：

| 指标 | 数值 |
|---|---:|
| 已有 MIP pool 且可对比实例 | 15 |
| 不差于 SOTA no-student adjusted | 13 |
| 差于 SOTA no-student adjusted | 2 |
| 平均 gap % | +4.53% |

两个明显需要关注的实例：

| instance | 问题 |
|---|---|
| `muni-fsps-spr17c` | 当前 best valid pool total 为 10772，明显差于 SOTA no-student 2594；说明 Phase 1A MIP pool 质量不足或 reduced/solution 对齐存在问题 |
| `tg-spr18` | 当前 best valid pool total 为 14128，差于 SOTA no-student 12704；是后续 Phase 1B 优化应重点尝试的实例 |

当前缺少 MIP pool 的 SOTA 对比实例：

```text
agh-fal17, agh-fis-spr17, agh-ggos-spr17, agh-h-spr17,
bet-fal17, bet-spr18,
iku-fal17, iku-spr18,
lums-fal17,
muni-fspsx-fal17,
muni-pdf-spr16, muni-pdf-spr16c, muni-pdfx-fal17,
pu-d9-fal19, pu-proj-fal19
```

## 6. 剩余实例困难

剩余约 15 个 instances 的主要困难是完整 MIP 中约束对过多，之前服务器无法稳定跑完。

曾尝试过图分解方式降低问题规模，但实验观察是：

```text
graph decomposition solution quality < full MIP solution quality
```

因此图分解目前更适合作为一个单独 baseline，而不能直接替代完整 MIP pool。

## 7. 当前结论

| 结论 | 说明 |
|---|---|
| Phase 1A 只完成约一半 | 目前有约 15/30 instances 的 MIP solution pool |
| 已有 pool 可支持 Phase 1B 和 Phase 2 | 后优化和 student assignment 可以先在 available-pool instances 上进行 |
| 多数已有 pool 在 no-student 口径下不差于 SOTA adjusted | 15 个已有 pool 中 13 个 gap <= 0 |
| 个别实例仍明显落后 | `muni-fsps-spr17c` 和 `tg-spr18` 需要重点补强 |
| 剩余 instances 是论文风险点 | 需要明确说明 full benchmark 尚未完全覆盖 |

## 8. 后续需要补充

| 优先级 | 实验 |
|---|---|
| P0 | 在更强服务器上继续补齐剩余 instances 的 full MIP solution pool |
| P0 | 对 `muni-fsps-spr17c` 和 `tg-spr18` 进行更强 Phase 1A/Phase 1B 优化 |
| P1 | 记录剩余 instances 的 MIP 建模规模和失败原因 |
| P1 | 将图分解作为独立 baseline，与 full MIP 在已有可跑实例上比较 |
