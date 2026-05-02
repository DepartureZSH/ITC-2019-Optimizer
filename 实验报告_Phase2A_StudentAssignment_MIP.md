# Phase 2A 实验报告：Student Assignment MIP

## 1. 阶段目标

Phase 2A 在 Phase 1B 优化后的 class solution 基础上进行 student assignment。

本阶段固定 class 的 time 和 room，不再修改 class assignment，只决定每个 student 选择哪些 course configuration / subpart class bundle。

输出 XML 会写入：

```xml
<class id="..." days="..." start="..." weeks="..." room="...">
  <student id="..." />
</class>
```

## 2. Pipeline 位置

```text
Phase 1 optimized class solution
 -> Phase 2A MIP student assignment
 -> Phase 2B student assignment post-optimization
 -> final complete solution
```

## 3. 已实现接口

当前已实现：

```text
src/student_assignment/marl_sectioning.py
```

支持：

| 功能 | 状态 |
|---|---|
| 从已有 solution XML 开始 | 已完成 |
| 不构建 class assignment constraint model | 已完成 |
| 读取 problem XML 中 students/courses/classes | 已完成 |
| 输出带 `<student>` 的 solution XML | 已完成 |
| Gurobi MIP interface | 已完成 |
| SciPy fallback | 已完成 |
| MIP batch repair | 已完成 |
| student-level LNS repair | 已完成 |

## 4. 当前配置

```yaml
student_assignment:
  method: mip_lns_marl
  source: best_local
  source_xml: null
  initial: mip
  mip_solver: gurobi
  mip_fallback: true
  mip_batch_size: 40
  mip_candidate_limit: 8
  mip_time_limit: 30.0
  mip_rel_gap: 0.05
  lns_iterations: 50
  lns_destroy_students: 20
  lns_candidate_limit: 10
  post_marl_iterations: 0
```

## 5. 已完成 Smoke Test

在无 Gurobi 本机环境下，曾使用 greedy/MARL 直接生成 student assignment，结果可行但 student conflicts 偏高。

示例：

| instance | source | student conflicts | weighted student | valid |
|---|---|---:|---:|---|
| muni-fsps-spr17c | best local solution | 6667 | 666700 | True |

该结果说明：

```text
direct greedy/MARL student assignment is not enough
```

因此后续应以完整 MIP student assignment 作为初解，再用 LNS/MARL 优化。

## 6. 与 Official SOTA Score 对比

Phase 2A 开始生成完整 solution XML，因此 SOTA 对比应使用 official full score，而不是 no-student adjusted score。

对比口径：

```text
phase2a_total = fixed_phase1_class_total + student_conflicts * student_weight
gap_to_sota = phase2a_total - official_sota_total
```

其中 official SOTA score 来自：

```text
output/analysis/official_sota_no_student_scores.csv
```

当前仅有 greedy/MARL smoke test，不代表正式 MIP 结果：

| instance | method | phase1 source total | student conflicts | weighted student | Phase2A total | official SOTA total | gap | gap % |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| muni-fsps-spr17c | greedy/MARL smoke | 10772 | 6667 | 666700 | 677472 | 2594 | +674878 | +26016.88% |

该 smoke test 的 SOTA gap 极大，说明直接 greedy/MARL sectioning 不能作为最终 student assignment 方法。正式实验需要使用 Gurobi MIP 先生成高质量 student assignment，再进入 Phase 2B 的 LNS/MARL 后优化。

正式 MIP-only 实验表应补充如下字段：

| instance | phase1 source total | official SOTA total | SOTA student conflicts | MIP student conflicts | MIP weighted student | MIP final total | gap to SOTA |
|---|---:|---:|---:|---:|---:|---:|---:|
| agh-fal17 | 待跑 | 117627 | 11400 | 待填 | 待填 | 待填 | 待填 |
| agh-fis-spr17 | 待跑 | 2985 | 49 | 待填 | 待填 | 待填 | 待填 |
| agh-ggis-spr17 | 16514 | 34285 | 2548 | 待填 | 待填 | 待填 | 待填 |
| agh-ggos-spr17 | 待跑 | 2855 | 25 | 待填 | 待填 | 待填 | 待填 |
| agh-h-spr17 | 待跑 | 21161 | 10 | 待填 | 待填 | 待填 | 待填 |
| bet-fal17 | 待跑 | 289452 | 391 | 待填 | 待填 | 待填 | 待填 |
| bet-spr18 | 待跑 | 348524 | 258 | 待填 | 待填 | 待填 | 待填 |
| iku-fal17 | 待跑 | 18968 | 0 | 待填 | 待填 | 待填 | 待填 |
| iku-spr18 | 待跑 | 25863 | 0 | 待填 | 待填 | 待填 | 待填 |
| lums-fal17 | 待跑 | 349 | 0 | 待填 | 待填 | 待填 | 待填 |
| lums-spr18 | 95 | 95 | 0 | 待填 | 待填 | 待填 | 待填 |
| mary-fal18 | 1871 | 4331 | 234 | 待填 | 待填 | 待填 | 待填 |
| mary-spr17 | 14473 | 14910 | 43 | 待填 | 待填 | 待填 | 待填 |
| muni-fi-fal17 | 273 | 2837 | 448 | 待填 | 待填 | 待填 | 待填 |
| muni-fi-spr16 | 372 | 3752 | 582 | 待填 | 待填 | 待填 | 待填 |
| muni-fi-spr17 | 188 | 3738 | 677 | 待填 | 待填 | 待填 | 待填 |
| muni-fsps-spr17 | 368 | 868 | 5 | 待填 | 待填 | 待填 | 待填 |
| muni-fsps-spr17c | 10601 | 2594 | 0 | 待填 | 待填 | 待填 | 待填 |
| muni-fspsx-fal17 | 待跑 | 10014 | 0 | 待填 | 待填 | 待填 | 待填 |
| muni-pdf-spr16 | 待跑 | 17159 | 358 | 待填 | 待填 | 待填 | 待填 |
| muni-pdf-spr16c | 待跑 | 32762 | 608 | 待填 | 待填 | 待填 | 待填 |
| muni-pdfx-fal17 | 待跑 | 82258 | 771 | 待填 | 待填 | 待填 | 待填 |
| nbi-spr18 | 13721 | 18014 | 440 | 待填 | 待填 | 待填 | 待填 |
| pu-d5-spr17 | 14631 | 15184 | 16 | 待填 | 待填 | 待填 | 待填 |
| pu-d9-fal19 | 待跑 | 38834 | 601 | 待填 | 待填 | 待填 | 待填 |
| pu-llr-spr17 | 3561 | 10038 | 643 | 待填 | 待填 | 待填 | 待填 |
| pu-proj-fal19 | 待跑 | 117169 | 2182 | 待填 | 待填 | 待填 | 待填 |
| tg-fal17 | 4215 | 4215 | 0 | 待填 | 待填 | 待填 | 待填 |
| tg-spr18 | 14128 | 12704 | 0 | 待填 | 待填 | 待填 | 待填 |
| yach-fal17 | 314 | 1074 | 122 | 待填 | 待填 | 待填 | 待填 |

## 7. 当前实验状态

| 实验 | 状态 |
|---|---|
| Greedy student assignment baseline | 部分完成，仅 smoke |
| MARL-only student assignment | 部分完成，仅 smoke，质量不够 |
| Gurobi MIP student assignment | 待完成，需要服务器 Gurobi 环境 |
| MIP parameter sensitivity | 待完成 |
| 全实例 student assignment | 待完成 |

## 8. 推荐实验设计

| 实验 | 参数 |
|---|---|
| MIP only | `initial: mip`, `lns_iterations: 0`, `post_marl_iterations: 0` |
| MIP candidate limit | `mip_candidate_limit = 4 / 8 / 12` |
| MIP batch size | `mip_batch_size = 20 / 40 / 80` |
| MIP time limit | `mip_time_limit = 10 / 30 / 60` |

主要指标：

| 指标 | 说明 |
|---|---|
| assigned_student_courses | 成功分配的 student-course 数 |
| failed_student_courses | 未能分配的 student-course 数 |
| student_conflicts | student conflict raw count |
| weighted_student | `student_conflicts * w_student` |
| runtime | MIP 求解耗时 |
| valid | 是否满足 hard constraints 和 capacity |

## 9. 推荐运行命令

服务器需安装 Gurobi：

```bash
pip install gurobipy
```

单实例：

```bash
python main.py --instance muni-fsps-spr17c --student_assignment
```

指定 Phase 1B 优化解：

```yaml
student_assignment:
  source_xml: output/phase2_direct_all_instances_extended_20260425/muni-fsps-spr17c_phase2_direct.xml
```

## 10. 当前结论

Phase 2A 的代码接口已经准备好，但正式 Gurobi MIP 结果还未系统完成。当前 smoke test 与 official SOTA score 差距极大，进一步证明必须使用 MIP student assignment 作为初解。下一步最关键的是在有 Gurobi license 的服务器上跑 MIP-only student assignment，确认相比 greedy/MARL direct assignment 是否显著降低 student conflicts 和 final total gap。
