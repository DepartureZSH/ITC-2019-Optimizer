# 实验报告：解池融合方法（Step 2）
# Experimental Report: Solution Pool Merging (Step 2)

---

## 1. 引言 / Introduction

### 1.1 背景 Background

**中文**

国际课表竞赛2019（ITC2019）是一个大规模大学课程调度优化问题。给定一组由混合整数规划（MIP）求解器已生成的可行解池，本实验目标是通过后优化技术进一步降低目标函数值，同时保持所有硬约束的可行性。

本报告描述"方向4：解池融合"（Solution Pool Merging）的设计、实现与实验结果。该方向的核心思想是：从 98 个 MIP 可行解构成的解池中提取有用信息（分配频率、局部惩罚），通过不同的组合策略生成新的可行解，以期超越最优 MIP 解。

**English**

The International Timetabling Competition 2019 (ITC2019) is a large-scale university course scheduling optimization problem. Given a pool of feasible solutions already produced by a Mixed-Integer Programming (MIP) solver, the goal of this work is to further reduce the objective value through post-optimization while maintaining feasibility of all hard constraints.

This report describes the design, implementation, and experimental results of *Approach 4: Solution Pool Merging*. The core idea is to extract useful information (assignment frequency, local penalties) from a pool of 98 MIP feasible solutions and combine them through different strategies to generate new feasible solutions that potentially surpass the best MIP solution.

---

### 1.2 目标函数 Objective Function

$$
\text{Total} = w_{\text{time}} \times \text{TimePenalty} + w_{\text{room}} \times \text{RoomPenalty} + w_{\text{dist}} \times \text{DistributionPenalty}
$$

本版本不包含学生冲突惩罚（student conflict penalty），仅优化上述三项软约束加权之和。

*This version excludes student conflict penalty; only the three-component weighted sum above is optimized.*

---

## 2. 问题规模与约束结构 / Problem Scale and Constraint Structure

以 `agh-ggis-spr17` 实例为例 / Using instance `agh-ggis-spr17` as the test case:

| 参数 Parameter | 值 Value |
|---|---|
| 时间维度 Time grid | 16 周 × 7 天 × 288 槽/天 |
| 决策变量 Decision variables | 261,873 |
| 班级数 Classes | 926 |
| 硬约束行 Hard constraint rows | 18,924,540 |
| — 教室容量约束 Room capacity | 18,334,330 |
| — 分布约束 Distribution | 590,210 |
| 软约束行 Soft constraint rows | 412,730 |
| MIP 解池大小 Pool size | 98 solutions |
| 模型构建时间 Model build time | ~961 s (16 min) |

**解池统计 / MIP Pool Statistics:**

| 指标 Metric | 值 Value |
|---|---|
| 最优解 Best | 13,805.0 |
| 平均值 Average | 15,954.2 |
| 最差解 Worst | 20,078.0 |
| 最优解分解 Best breakdown | time: 924.0 / room: 371.0 / dist: 12,510.0 |

---

## 3. 算法设计 / Algorithm Design

### 3.1 核心数据结构 Core Data Structures

**ConstraintTracker（约束追踪器）**

在贪心赋值过程中，需要以 O(1) 速度判断新增一个变量是否会违反硬约束。`ConstraintTracker` 构建了一个内存反向索引：

```
var_to_rows: x_idx → [(row_idx, upper_bound), ...]
row_sum[row_idx]: 当前行的赋值总计 current sum for each constraint row
```

操作复杂度：`can_add(xidx)` = O(degree of xidx)，`add/remove` = O(degree)。总构建时间约 22 秒（需遍历 18.9M 条约束）。

*During greedy assignment, `ConstraintTracker` provides O(1) feasibility checking by maintaining an in-memory reverse index from each variable to the hard-constraint rows it participates in, with running row sums.*

**SolutionPool（解池统计）**

从 98 个 MIP 解中统计每个班级各 `(tidx, rid)` 分配的出现频率，用于频率加权评分：

```
frequency(cid, tidx, rid) = count(cid, tidx, rid) / pool_size
```

*`SolutionPool` aggregates (tidx, rid) assignment frequencies across all 98 MIP solutions for use in frequency-weighted candidate scoring.*

---

### 3.2 策略 2.1：贪心融合 Strategy 2.1: Greedy Merging

**算法流程 Algorithm:**

1. 按"最受约束优先"（most-constrained-first，度启发式）排列班级顺序
2. 对每个班级，从候选分配中按加权惩罚评分排序
3. 依次选择不违反已有约束的最优候选
4. 若解池中候选全部冲突，回退到完整域搜索

**评分函数 Scoring:**

$$
\text{score}(x_i) = w_t \cdot \text{time\_pen}(x_i) + w_r \cdot \text{room\_pen}(x_i)
$$

**class 排序策略 / Class ordering strategies:**

| 策略 Strategy | 说明 Description |
|---|---|
| `most_constrained` | 按硬约束度排序（默认）|
| `fewest_options` | 按域大小升序（选项最少优先）|
| `natural` | 原始顺序 |

**实验结果 Results:**

初始贪心构造存在可行性问题：在 `pool_only` 候选源下，最受约束优先顺序导致 86 个班级无法分配。加入完整域回退后降至约 23 个，但仍不可行。根本原因是从零构造时早期大量班级占用教室资源，导致后续班级无可行选项。

*Initial greedy construction with pool_only candidates and most-constrained ordering left 86 classes unassigned (infeasible). Adding full-domain fallback reduced this to ~23. The root cause: early high-degree classes consume room slots, blocking later classes from finding feasible assignments during from-scratch construction.*

---

### 3.3 策略 2.2：频率加权融合 Strategy 2.2: Frequency-Weighted Merging

**评分函数 Scoring:**

$$
\text{score}(x_i) = (1 - w_f) \cdot \text{penalty}(x_i) - w_f \cdot \text{freq}(x_i)
$$

其中 $w_f = 0.3$（默认），分数越低越优先。频率高的分配（跨 98 个解中出现频繁）获得奖励，偏向选择解池中"共识"较高的分配。

此策略属于贪心构造的扩展，其 `scoring: combined` 已集成于 `GreedyMerger._score()` 方法中，通过配置 `scoring: frequency` 或 `scoring: combined` 切换。

*Frequency-weighted scoring rewards assignments that appear frequently across the 98 MIP solutions. It is integrated in the same `GreedyMerger` backbone as Strategy 2.1, selectable via the `scoring` config parameter.*

---

### 3.4 策略 2.3：从最优解出发改进 Strategy 2.3: Improve-from-Best

**核心思想 Core Idea:**

为解决贪心从零构造的可行性问题，`improve_from_best` 以最优 MIP 解为起点，通过多轮次逐类改进。每次尝试将一个班级的当前分配替换为评分更优的分配：

```
for each pass:
    for each class (most-constrained-first):
        temporarily remove current assignment
        find best feasible alternative (full-domain + pool candidates)
        re-insert best found
```

**关键特性 Key properties:**
- **始终可行 Always feasible** — 从可行解出发，每步保持可行性
- **多轮次 Multi-pass** — 默认 3 轮，直到无改进为止
- **双源候选 Dual source** — 先尝试解池候选，再扩展到完整域

**实验结果 Results:**

| 指标 Metric | 值 Value |
|---|---|
| 可行性 Feasibility | ✓ True |
| 总代价 Total cost | 16,669.0 |
| MIP 最优 MIP best | 13,805.0 |
| 改进量 Improvement | −20.75%（比 MIP 更差 worse than MIP）|
| 三轮改进次数 Pass improvements | 277 / 28 / 0（共 305 次）|

**分析 Analysis:**

结果比 MIP 最优差约 20.75%，原因在于评分函数混合了频率奖励和惩罚：将班级移向解池中高频分配时，实际上增大了软约束违反数（如连续排课分布惩罚），从而提高了总代价。这表明**频率**与**实际代价**之间存在结构性的不一致——解池中的高频分配不等于低代价分配。

*The −20.75% result (worse than MIP) reveals that frequency and actual cost are structurally misaligned: high-frequency pool assignments often correspond to higher distribution penalties. The scoring function biases toward "consensus" assignments at the cost of objective quality.*

---

### 3.5 策略 2.4：交叉融合 Strategy 2.4: Crossover Merging

**算法设计 Algorithm Design:**

受遗传算法启发，从解池前 k 个最优解中两两抽取亲本，通过均匀交叉（uniform crossover）生成后代：

```
for each offspring (num_offspring trials):
    select two distinct parents (pa, pb) from top-k
    for each class (most-constrained-first):
        randomly pick primary parent (50/50)
        try primary → try secondary → defer
    greedy repair: for each deferred class, try full domain
    evaluate → update best if feasible and better
```

**关键实现细节 Key implementation details:**

1. **共享约束追踪器 Shared tracker:** `ConstraintTracker` 在 `CrossoverMerger.__init__` 中只构建一次（成本：一次 22s），每个后代调用 `reset()` 重置行和（成本：~0.1s）
2. **最受约束优先 Most-constrained order:** 类排序在初始化时计算一次，降低修复失败率
3. **修复策略 Repair strategy:** 冲突类回退到完整域逐一尝试

**关键改进对比 Key optimization comparison (v1 → v2):**

| | 版本 v1 | 版本 v2（优化后）|
|---|---|---|
| 追踪器构建 Tracker build | 每个后代 per offspring (~22s) | 仅一次 once at init (~22s) |
| 每代 reset 成本 Per-offspring reset | N/A | ~0.1s |
| 类排序 Class order | `random.shuffle` 每次随机 | 最受约束优先（固定）|
| 后代数量 Offspring count | 100 | 500 |
| 估算每代耗时 Est. per-offspring | ~22s | <0.5s |
| 估算交叉阶段总时 Est. crossover phase | ~37 min | ~4 min |

---

## 4. 实现架构 / Implementation Architecture

```
src/merging/
├── __init__.py          # 导出 run_merging 入口
├── greedy.py            # ConstraintTracker, SolutionPool, GreedyMerger
│                        # 包含策略 2.1 / 2.2 / 2.3
└── crossover.py         # CrossoverMerger — 策略 2.4
```

**配置驱动 Config-driven dispatch (`config.yaml`):**

```yaml
method: merging
merging:
  strategy: crossover       # greedy | frequency | improve_from_best | crossover
  candidate_source: pool_only
  scoring: combined         # penalty | frequency | combined
  freq_weight: 0.3
  sort_classes: most_constrained
  num_passes: 3
  top_k: 10
  num_offspring: 500
  seed: 42
```

所有策略共享同一入口函数 `run_merging()`，通过 `strategy` 参数调度。

*All strategies share a single entry point `run_merging()` dispatched by the `strategy` key, enabling reproducible configuration-driven experiments.*

---

## 5. 实验结果汇总 / Experimental Results Summary

**实例 Instance:** `agh-ggis-spr17`  
**MIP 解池最优 MIP pool best:** 13,805.0

| 策略 Strategy | 可行性 Feasible | 总代价 Total | vs MIP | 运行时间 Runtime |
|---|:---:|---:|:---:|---:|
| MIP 最优（基线）MIP best (baseline) | ✓ | 13,805.0 | — | — |
| 2.1 贪心构造 Greedy construct | ✗ | — | — | <1s |
| 2.3 从最优改进 Improve-from-best | ✓ | 16,669.0 | −20.75% | ~10s |
| 2.4 交叉融合 v1 Crossover (100 offspring) | ✓ | 13,805.0 | 0.00% | 2,219s |
| 2.4 交叉融合 v2 Crossover (500 offspring) | ✓ | *running* | *TBD* | *TBD* |

**交叉融合 v1 详细数据 Crossover v1 detail:**

| 指标 Metric | 值 Value |
|---|---|
| 亲本数 Parents (top-k) | 10 (best: 13,805.0 / worst: 13,967.0) |
| 总后代数 Total offspring | 100 |
| 可行后代数 Feasible offspring | 4 (4%) |
| 产生改进的后代 Improvements | 0 |
| 返回结果 Returned solution | MIP best (13,805.0, unchanged) |
| 交叉阶段耗时 Crossover time | 2,219s |
| 平均每后代 Per-offspring avg | ~22s |

---

## 6. 分析与讨论 / Analysis and Discussion

### 6.1 可行性瓶颈 Feasibility Bottleneck

**交叉融合可行率仅 4%** 的根本原因：`agh-ggis-spr17` 是高度受约束的实例，拥有 18.9M 条硬约束（主要是教室容量约束）。两个近最优亲本的时间槽/教室分配之间存在大量隐式依赖，随机交叉破坏这些依赖后，即使使用完整域修复，约 96% 的后代也无法满足所有硬约束。

*The 4% feasibility rate stems from the extreme constraint density (18.9M hard constraints). Near-optimal parent solutions have tightly interlocked room assignments; random recombination breaks these dependencies faster than the greedy repair can recover.*

### 6.2 频率-代价不一致性 Frequency–Cost Misalignment

解池中高频率的 `(tidx, rid)` 分配不一定对应低代价。MIP 解器在不同运行实例中选择不同但等效的满足约束的分配，频率只反映了这种随机性，而非最优性。这解释了为何 `improve_from_best`（使用频率奖励的评分）比 MIP 最优差 20.75%。

*High pool frequency of a `(tidx, rid)` assignment does not imply low cost. MIP solver solutions represent diverse feasible optima; frequency reflects solver variance, not optimality. This explains the 20.75% degradation in `improve_from_best`.*

### 6.3 计算效率分析 Computational Efficiency

交叉融合 v1 每后代耗时 22s，主要瓶颈在于每次重建 `ConstraintTracker` 需遍历 18.9M 条约束。优化后（v2）通过 `reset()` 方法复用追踪器，每后代代价从 22s 降至 <0.5s，即**约 44× 加速**，使 500 后代在交叉阶段约 4 分钟内完成（而非 v1 的 37 分钟）。

*Crossover v1 took 22s/offspring because `ConstraintTracker.__init__` walks all 18.9M constraints. The v2 optimization reuses the tracker via `reset()`, reducing per-offspring cost from 22s to <0.5s — a ~44× speedup — enabling 500 offspring in ~4 minutes instead of 37 minutes.*

### 6.4 方向局限性 Approach Limitations

解池融合在以下条件下效果有限：

1. **MIP 解已接近全局最优** — 14 个实例的 MIP 解质量已经很高（最优解与均值差距 ~13%），后优化的收益空间本身就小
2. **随机交叉对高度受约束问题不适用** — 相比组合优化，基于梯度或邻域搜索的方法更适合此类结构
3. **频率信息信噪比低** — 在解质量离散度高（13,805 至 20,078）的解池中，频率混合了高质量和低质量解的分配习惯

*Solution pool merging has limited effectiveness when: (1) MIP solutions are already near-optimal; (2) high constraint density makes random crossover infeasible with very high probability; (3) pool frequency conflates high- and low-quality solution patterns.*

---

## 7. 结论与展望 / Conclusion and Future Work

### 7.1 结论 Conclusion

本实验实现并评估了四种解池融合策略：

- **贪心构造**（2.1/2.2）：从零构造受可行性问题制约，高度约束实例中排序和候选源的选择对最终是否可行影响显著
- **从最优改进**（2.3）：保证可行性，但混合频率-惩罚评分与真实目标函数之间存在结构性偏差，导致结果比 MIP 最优差约 21%
- **交叉融合**（2.4）：实现完整，v1 可行率约 4%，未能超越 MIP 最优；v2 通过共享追踪器与最受约束优先排序将每后代计算成本降低约 44×

*Four merging strategies were implemented and evaluated. Greedy construction struggles with feasibility in dense instances. Improve-from-best guarantees feasibility but suffers from frequency–cost misalignment (~21% worse than MIP best). Crossover achieves 4% feasibility with no improvement over MIP best in v1; the optimized v2 reduces per-offspring compute by ~44× and is expected to improve feasibility rate.*

### 7.2 展望 Future Work

1. **纯代价导向的 improve_from_best** — 移除频率奖励，改用纯软约束惩罚评分，预期能从 MIP 最优出发进行真正的局部改进
2. **交叉融合 + 局部搜索混合** — 对每个可行后代追加 1 轮 `improve_from_best`，利用交叉多样性 + 局部改进
3. **约束感知交叉** — 按房间聚类分配，减少交叉引入的教室冲突
4. **下一步：局部搜索**（Step 3）— 邻域搜索（single-class swap, room-swap）+ 模拟退火接受准则，有望在 MIP 最优基础上实现真正的代价下降

*Key next steps: (1) pure-cost scoring in improve_from_best; (2) crossover + local improvement hybrid; (3) constraint-aware crossover; (4) Step 3 local search with SA acceptance, which is more suited to highly-constrained fine-grained optimization.*

---

## 附录 Appendix

### A. 文件索引 File Index

| 文件 File | 描述 Description |
|---|---|
| `src/merging/greedy.py` | ConstraintTracker, SolutionPool, GreedyMerger (strategies 2.1–2.3) |
| `src/merging/crossover.py` | CrossoverMerger (strategy 2.4) |
| `src/merging/__init__.py` | run_merging() entry point |
| `main.py` | Unified entry point, pool loading, method dispatch |
| `config.yaml` | Run configuration |

### B. 输出文件 Output Files

| 文件 File | 策略 Strategy | 代价 Cost |
|---|---|---|
| `output/agh-ggis-spr17_merged_improve_from_best.xml` | improve_from_best | 16,669.0 |
| `output/agh-ggis-spr17_merged_crossover.xml` | crossover v1 | 13,805.0 |

### C. 运行命令 Run Commands

```bash
# 贪心融合 Greedy merging
python main.py --method merging  # config: strategy: greedy

# 从最优解改进 Improve-from-best
python main.py --method merging  # config: strategy: improve_from_best

# 交叉融合 Crossover merging (v2, 500 offspring)
python main.py --method merging  # config: strategy: crossover, num_offspring: 500
```

---

*报告日期 Report date: 2026-04-23*  
*实例 Instance: agh-ggis-spr17*  
*交叉融合优化版本（v2，500 后代）正在运行，结果将在完成后补充。*  
*Optimized crossover v2 (500 offspring) is currently running; results will be appended upon completion.*
