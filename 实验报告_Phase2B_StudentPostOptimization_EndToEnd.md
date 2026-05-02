# Phase 2B 实验报告：Student Assignment Post-Optimization 与 End-to-End

## 1. 阶段目标

Phase 2B 在 Phase 2A 的 student MIP 初解基础上做后优化，目标是进一步降低 student conflicts。

最终输出是完整 ITC2019 solution XML，包含：

```text
class time assignment
class room assignment
student-to-class assignment
```

## 2. Pipeline 位置

```text
Phase 1B optimized class solution
 -> Phase 2A MIP student assignment
 -> Phase 2B student LNS / MARL optimization
 -> final complete solution XML
 -> official validator
```

## 3. 已实现方法

| 方法 | 状态 | 说明 |
|---|---|---|
| Student-level LNS | 已实现 | 选择冲突高的学生集合进行重排 |
| Small MIP repair | 已实现 | 对 destroy students 解小规模 binary MIP |
| MARL post-refinement | 已实现 | 可通过 `post_marl_iterations` 开启 |
| Official validator output path | 已接入 | `validate: true` 时可提交最终 XML |

## 4. 当前未完成实验

| 实验 | 状态 |
|---|---|
| MIP + LNS 对比 MIP only | 待完成 |
| MIP + LNS + MARL 对比 MIP + LNS | 待完成 |
| 全 available-pool instances 最终解 | 待完成 |
| 官方 validator 全量验证 | 待完成 |
| End-to-End 最终结果表 | 待完成 |

## 5. 推荐实验矩阵

| 实验名 | initial | lns_iterations | lns_destroy_students | post_marl_iterations |
|---|---|---:|---:|---:|
| greedy_baseline | greedy | 0 | 0 | 0 |
| marl_only | greedy | 0 | 0 | 2 |
| mip_only | mip | 0 | 0 | 0 |
| mip_lns_20 | mip | 20 | 20 | 0 |
| mip_lns_50 | mip | 50 | 20 | 0 |
| mip_lns_marl | mip | 50 | 20 | 2 |

## 6. 与 Official SOTA Score 对比

Phase 2B 是最终完整 solution 阶段，因此必须与 official SOTA full score 直接对比。

对比口径：

```text
final_total = phase1_optimized_total + final_student_conflicts * student_weight
gap_to_sota = final_total - official_sota_total
gap_pct = gap_to_sota / official_sota_total
```

需要同时报告 no-student component 和 student component，避免只看 final total 时无法判断差距来源。

正式结果表建议如下：

| instance | official SOTA total | SOTA no-student | SOTA student conflicts | phase1 optimized total | final student conflicts | final total | gap to SOTA | valid |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| agh-fal17 | 117627 | 60627 | 11400 | 待跑 | 待填 | 待填 | 待填 | 待跑 |
| agh-fis-spr17 | 2985 | 2740 | 49 | 待跑 | 待填 | 待填 | 待填 | 待跑 |
| agh-ggis-spr17 | 34285 | 21545 | 2548 | 16514 | 待填 | 待填 | 待填 | 待跑 |
| agh-ggos-spr17 | 2855 | 2730 | 25 | 待跑 | 待填 | 待填 | 待填 | 待跑 |
| agh-h-spr17 | 21161 | 21111 | 10 | 待跑 | 待填 | 待填 | 待填 | 待跑 |
| bet-fal17 | 289452 | 287106 | 391 | 待跑 | 待填 | 待填 | 待填 | 待跑 |
| bet-spr18 | 348524 | 346976 | 258 | 待跑 | 待填 | 待填 | 待填 | 待跑 |
| iku-fal17 | 18968 | 18968 | 0 | 待跑 | 待填 | 待填 | 待填 | 待跑 |
| iku-spr18 | 25863 | 25863 | 0 | 待跑 | 待填 | 待填 | 待填 | 待跑 |
| lums-fal17 | 349 | 349 | 0 | 待跑 | 待填 | 待填 | 待填 | 待跑 |
| lums-spr18 | 95 | 95 | 0 | 95 | 待填 | 待填 | 待填 | 待跑 |
| mary-fal18 | 4331 | 1991 | 234 | 1871 | 待填 | 待填 | 待填 | 待跑 |
| mary-spr17 | 14910 | 14480 | 43 | 14473 | 待填 | 待填 | 待填 | 待跑 |
| muni-fi-fal17 | 2837 | 597 | 448 | 273 | 待填 | 待填 | 待填 | 待跑 |
| muni-fi-spr16 | 3752 | 842 | 582 | 372 | 待填 | 待填 | 待填 | 待跑 |
| muni-fi-spr17 | 3738 | 353 | 677 | 188 | 待填 | 待填 | 待填 | 待跑 |
| muni-fsps-spr17 | 868 | 368 | 5 | 368 | 待填 | 待填 | 待填 | 待跑 |
| muni-fsps-spr17c | 2594 | 2594 | 0 | 10601 | 待填 | 待填 | 待填 | 待跑 |
| muni-fspsx-fal17 | 10014 | 10014 | 0 | 待跑 | 待填 | 待填 | 待填 | 待跑 |
| muni-pdf-spr16 | 17159 | 9999 | 358 | 待跑 | 待填 | 待填 | 待填 | 待跑 |
| muni-pdf-spr16c | 32762 | 20602 | 608 | 待跑 | 待填 | 待填 | 待填 | 待跑 |
| muni-pdfx-fal17 | 82258 | 66838 | 771 | 待跑 | 待填 | 待填 | 待填 | 待跑 |
| nbi-spr18 | 18014 | 16254 | 440 | 13721 | 待填 | 待填 | 待填 | 待跑 |
| pu-d5-spr17 | 15184 | 15056 | 16 | 14631 | 待填 | 待填 | 待填 | 待跑 |
| pu-d9-fal19 | 38834 | 26814 | 601 | 待跑 | 待填 | 待填 | 待填 | 待跑 |
| pu-llr-spr17 | 10038 | 4894 | 643 | 3561 | 待填 | 待填 | 待填 | 待跑 |
| pu-proj-fal19 | 117169 | 99713 | 2182 | 待跑 | 待填 | 待填 | 待填 | 待跑 |
| tg-fal17 | 4215 | 4215 | 0 | 4215 | 待填 | 待填 | 待填 | 待跑 |
| tg-spr18 | 12704 | 12704 | 0 | 14128 | 待填 | 待填 | 待填 | 待跑 |
| yach-fal17 | 1074 | 464 | 122 | 314 | 待填 | 待填 | 待填 | 待跑 |

解释规则：

| 情况 | 含义 |
|---|---|
| `phase1 optimized total <= SOTA no-student` | class assignment 部分不弱于 SOTA adjusted |
| `final student conflicts > SOTA student conflicts` | final gap 主要来自 student assignment |
| `phase1 optimized total > SOTA no-student` | final gap 同时来自 class assignment 和 student assignment |

## 7. End-to-End 最终表字段

最终论文表建议包含：

| 字段 | 含义 |
|---|---|
| instance | 实例名 |
| official_sota_total | official SOTA 完整 score |
| official_sota_no_student | official SOTA 扣除 student cost 后的 class-only adjusted score |
| official_sota_student_conflicts | official SOTA 的 student conflicts |
| phase1_pool_best_total | Phase 1A pool 中 best valid total |
| phase1_optimized_total | Phase 1B 后优化 total |
| phase1_improvement | Phase 1B 相比 pool best 的改善 |
| student_conflicts | Phase 2 最终 student conflicts |
| weighted_student | student weighted cost |
| final_total | 完整最终 total |
| gap_to_sota | `final_total - official_sota_total` |
| gap_to_sota_pct | 相对 official SOTA total 的百分比差距 |
| official_total | 官方 validator total |
| valid | 官方 validator 是否 valid |
| runtime_phase1 | Phase 1B runtime |
| runtime_phase2 | Phase 2 runtime |

## 8. 推荐输出目录

```text
output/final_end_to_end/
  <instance>_final.xml
  end_to_end_summary.csv
  official_validation_summary.csv
```

## 9. 推荐运行顺序

1. 选择 Phase 1B 最优 XML 作为 `student_assignment.source_xml`。
2. 运行 `mip_only`，确认 Gurobi MIP 初解质量。
3. 运行 `mip_lns_20` 和 `mip_lns_50`，比较 student conflicts 改善。
4. 可选运行 `mip_lns_marl`，观察 MARL 是否继续改善。
5. 对最终 XML 调官方 validator。

## 10. 当前结论

Phase 2B 目前是最重要的未完成实验。只有完成本阶段，项目才能从“class assignment 后优化”闭环进入真正的 ITC2019 完整 solution 闭环。

当前优先级：

| 优先级 | 任务 |
|---|---|
| P0 | 在 Gurobi 服务器上跑 `mip_only` student assignment |
| P0 | 跑 `mip_lns_50` 并生成最终 XML |
| P0 | 用官方 validator 验证最终 XML |
| P1 | 做 student LNS/MARL 消融 |
| P1 | 生成 end-to-end final summary |
