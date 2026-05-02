# Research Paper 大纲：MIP + Post-Optimization 两阶段完整项目

> 注意：课程要求明确禁止 Generative AI 用于提交作品。本文档仅作为项目内部规划与检查清单，最终提交文本、实验解释和表述应由学生自行完成，并遵守学校 academic misconduct 规定。

## 目标定位

Research Paper 的 70+ 高分关键是 Methodology 与 Evaluation，两项合计 60%。基于完整项目，论文不应只写本仓库的后优化部分，而应写成：

**A two-stage optimization framework for a no-student-assignment ITC2019 timetabling variant: first generate feasible solutions with MIP, then improve them through validator-aware solution-pool post-optimization.**

建议论文题目：

**A Two-Stage MIP and Solution-Pool Post-Optimization Framework for a No-Student ITC2019 Timetabling Variant**

可选中文理解：

**面向无学生分配 ITC2019 变体的 MIP 与解池后优化两阶段框架**

## 论文核心主线

1. ITC2019 是真实大学排课问题，具有大规模离散搜索空间、复杂 hard/soft distribution constraints、多目标加权优化等特点。
2. 本项目研究的是 no-student-assignment 版本：solution XML 不包含 student assignment，目标函数只保留 time、room、distribution 三项。
3. 第一阶段使用 MIP 求解器为每个实例生成多个 hard-feasible 初始解，形成 solution pool。
4. 第二阶段使用本仓库实现的 post-optimization，在不重新运行完整 MIP 的条件下，从 solution pool 中提取 class-level assignment 片段，通过 validator-aware repair / beam search / distribution-guided destroy-and-repair 进一步降低目标值。
5. 论文的技术价值在于两阶段结合：
   - MIP 提供可行性和高质量起点。
   - Post-optimization 利用多解池中的局部多样性，在保持 hard feasibility 的前提下做轻量改进。
6. 实验应同时评估：
   - MIP 解池质量。
   - Post-optimization 相对 MIP pool best 的提升。
   - 与官方 leaderboard 的 no-student 派生分数对比。
   - 所有最终解的 hard feasibility。
   - 运行时间、改进来源和失败改进的原因。

## 70+ 评分要求到本文对应策略

| 评分项 | 权重 | 本文应如何满足 70+ |
|---|---:|---|
| Relevance | 10% | 明确说明该问题属于大学排课、整数规划、组合优化、约束满足和启发式搜索，属于计算机科学核心方向。 |
| Significance | 10% | 强调真实排课中单次求解往往不够；MIP 可生成可行解，但后续利用解池结构继续改进具有实际价值。 |
| Methodology | 30% | 系统描述两阶段框架：MIP 建模与解池生成、XML solution encoding、三项目标验证、hard feasibility 检查、solution-pool repair、distribution-guided destroy、beam repair、acceptance policy。 |
| Evaluation | 30% | 报告每实例 98 个 MIP 解、valid/invalid pool 统计、MIP pool best、post-optimization total、absolute/relative improvement、runtime、hard violations；补充与官方 leaderboard 扣除 student component 后的派生分数对比，并对改进实例做 component-level analysis。 |
| Scholarship | 10% | 引用 ITC2019 官方格式/论文、curriculum-based/university timetabling、MIP/matheuristic、local search、large neighbourhood search、solution merging/recombination 相关文献。 |
| Presentation | 10% | 采用 ACM/IEEE 双栏结构；用 pipeline 图、算法伪代码和实验表支撑论点；避免夸大 beyond data 的结论。 |

## 建议页数分配

Research Paper 要求 4-10 页，不含 references。建议写 8-9 页：

| 部分 | 建议页数 | 重点 |
|---|---:|---|
| Abstract | 0.2 | 两阶段方法和主要结果 |
| Introduction | 0.8 | 动机、研究问题、贡献 |
| Background and Related Work | 1.0 | ITC2019、MIP、matheuristics、post-optimization |
| Problem Variant and Objective | 0.8 | 无学生版本、三项目标、feasibility |
| Stage 1: MIP Solution-Pool Generation | 1.0 | MIP 建模、可行解池、解多样性 |
| Stage 2: Validator-Aware Post-Optimization | 2.0 | 本项目核心方法 |
| Experimental Setup | 0.8 | 数据、baseline、metrics、配置 |
| Results and Analysis | 1.5 | 总体结果、leaderboard 对比、改进来源、效率 |
| Discussion and Limitations | 0.5 | 局限、future work |
| Conclusion | 0.2 | 总结 |

## Abstract

### 应写内容

- 一句话介绍 ITC2019 排课问题和 no-student-assignment 变体。
- 说明本文提出两阶段框架：
  - Stage 1：MIP 生成多个 feasible candidate solutions。
  - Stage 2：solution-pool post-optimization 利用局部 assignment 片段改进 MIP 解。
- 强调目标函数：time、room、distribution 三项 weighted sum。
- 给出主要实验发现：
  - 每个实例 98 个 MIP-generated solutions。
  - post-optimization 输出保持 hard-feasible。
  - 在 15 个有 solution pool 的实例中，2 个实例获得改进，最大相对改进 9.62%，另一个为 1.59%。
  - 与官方 ITC2019 leaderboard 的完整分数相比，本文使用 `Total cost - Student conflicts * Student Weight` 得到 no-student 派生基准，再与本文三项目标分数比较。
- 总结意义：MIP 解池不只是终点，也可作为后续局部优化的结构化搜索空间。

### 避免写法

- 不要声称解决完整 ITC2019 student sectioning。
- 不要说 post-optimization 全面优于 MIP；准确说是“在部分实例上进一步改进 MIP pool best”。
- 不要把 invalid solution 的低分当作可行结果。

## 1. Introduction

### 目标

建立完整项目动机：为什么需要 MIP，为什么 MIP 后还需要 optimization。

### 内容结构

1. 介绍大学排课问题：
   - 需要为 classes 分配 time 和 room。
   - hard constraints 必须满足。
   - soft preferences 通过 penalty 进入目标函数。
   - 问题是大规模、强约束、离散组合优化问题。

2. 引出 ITC2019：
   - XML instances 包含 rooms、classes、times、distribution constraints、students。
   - 原始 ITC2019 目标含 time、room、distribution、student conflict。
   - 本文研究 no-student-assignment variant，因此 student component 不参与 objective。

3. 引出两阶段求解动机：
   - MIP 能系统表达约束并生成 high-quality feasible solutions。
   - 但单个 MIP 解不一定局部最优；多个 MIP 解之间存在 class-level assignment 多样性。
   - Post-optimization 可以在已有解池上轻量搜索，不必重新运行完整 MIP。

4. 研究问题：
   - RQ1：MIP 能否为 no-student ITC2019 变体生成可用于后续优化的 feasible solution pool？
   - RQ2：如何利用 MIP solution pool 中的局部 assignment 多样性进一步降低三项目标？
   - RQ3：如何在后优化中严格保持 hard feasibility？
   - RQ4：invalid 或 near-valid pool members 是否仍能提供有用的局部 assignment 信息？

5. 贡献点：
   - 构建 MIP + post-optimization 两阶段框架。
   - 定义 no-student-assignment ITC2019 三项目标与验证流程。
   - 生成并利用每实例 98 个 MIP solution XML 作为 solution pool。
   - 提出 validator-aware solution-pool repair 方法，在 hard-feasible 约束下复用局部 assignment。
   - 在 15 个实例上评估 feasibility、objective improvement、runtime，并通过扣除 student component 的方式与官方 leaderboard 做目标对齐后的外部比较。

### 建议图

Figure 1：完整两阶段 pipeline：

```text
Problem XML
   -> MIP model
   -> 98 MIP-generated solution XMLs per instance
   -> solution pool validation and encoding
   -> validator-aware post-optimization
   -> improved hard-feasible XML solution
```

## 2. Background and Related Work

### 2.1 University Timetabling and ITC2019

应说明：

- ITC2019 problem components：
  - rooms
  - classes
  - time options
  - room options
  - distribution constraints
  - students
- 原始 ITC2019 weighted objective：
  - time penalty
  - room penalty
  - distribution penalty
  - student conflict penalty
- 本文 variant：
  - 不执行 student sectioning。
  - solution XML 无 `<student>` elements。
  - student weight 保留在 XML 中，但不进入本文 objective。

### 2.2 MIP for Timetabling

应写：

- MIP 适合表达 binary assignment decisions。
- class-time-room assignment 可用 binary variable 表示。
- hard constraints 可转化为 linear constraints。
- soft penalties 可加入 objective。
- 优点：
  - feasible solution 质量高。
  - 约束清晰，可解释。
- 局限：
  - 大实例搜索空间巨大。
  - 运行时间和内存成本高。
  - 多个 feasible solutions 之间仍可能存在可重组的局部优势。

### 2.3 Matheuristics and Post-Optimization

可覆盖：

- Fix-and-optimize。
- Large neighbourhood search。
- Local search / simulated annealing。
- Solution merging / path relinking / crossover。

与本文关系：

- 本文不是纯 MIP，也不是纯 metaheuristic。
- MIP 负责初始可行性和高质量解池。
- 后优化负责从解池中组合/修复局部片段。

### 2.4 Gap Addressed by This Work

本文填补的具体 gap：

- 多数方法将 MIP 输出视为最终解。
- 本项目将 MIP 输出视为 reusable solution pool。
- 重点研究如何在不破坏 hard constraints 的前提下，从多个 MIP 解中提取局部改进。
- 官方 ITC2019 leaderboard 使用完整四项目标；本文提供一个 no-student 派生比较方式，用于判断三项目标优化质量与公开强基线之间的差距。

## 3. Problem Variant and Objective

### 3.1 No-Student ITC2019 Variant

本文问题定义：

- 每个 class 选择一个 allowed time option。
- 若 class 需要 room，则选择一个 allowed room。
- 若 class 不需要 room，内部使用 dummy room 表示。
- 不进行 student sectioning。
- 不计算 student conflict。

### 3.2 Objective Function

```text
Total = w_time * TimePenalty
      + w_room * RoomPenalty
      + w_dist * DistributionPenalty
```

说明：

- `TimePenalty`：所有 class 被选 time option 的 penalty 之和。
- `RoomPenalty`：所有 class 被选 room option 的 penalty 之和。
- `DistributionPenalty`：soft distribution constraints 的 violation penalty。
- `StudentConflict = 0`：本项目版本不包含 student assignment。

### 3.3 Hard Feasibility

最终解必须满足：

- 每个 class 恰好分配一次。
- time-room assignment 来自该 class 的合法 domain。
- room unavailable periods 不被使用。
- hard distribution constraints 不被违反。
- 输出 XML 能被 validator 判定为 valid。

应强调：

- objective 变低但 hard-invalid 的解没有意义。
- 本文所有后优化 acceptance 都以 hard feasibility 为前提。

## 4. Stage 1: MIP Solution-Pool Generation

### 目标

把 MIP 作为完整项目的第一阶段讲清楚。即使 MIP 代码不在本仓库，也要在论文中说明模型思想、输入输出和它对第二阶段的作用。

### 4.1 MIP Decision Variables

建议定义：

```text
x_{c,t,r} = 1 if class c is assigned to time option t and room r
```

其中：

- `c` 是 class。
- `t` 是该 class 的可选 time。
- `r` 是该 class 的可选 room；无 room class 可使用 dummy room。

### 4.2 MIP Constraints

至少说明：

1. Assignment constraint：

```text
sum_{t,r} x_{c,t,r} = 1, for each class c
```

2. Room availability：
   - 不允许 class 使用 room unavailable 的 time-room pair。

3. Hard distribution constraints：
   - NotOverlap、SameRoom、DifferentRoom、SameAttendees、Precedence、MaxDays 等 hard constraints 不能违反。

4. Domain filtering：
   - 只创建合法 time-room pair 的 variables，降低模型规模。

### 4.3 MIP Objective

MIP 阶段优化同一三项目标：

```text
minimize w_time * TimePenalty
       + w_room * RoomPenalty
       + w_dist * DistributionPenalty
```

需要说明：

- soft distribution constraints 以 penalty 形式进入 objective。
- student component 不包含在本文模型。

### 4.4 Solution Pool Generation

应写：

- MIP 不只输出一个解，而是为每个实例生成 98 个 solution XML。
- 多解池可以来自不同 seeds、time limits、solver parameters、solution pool mechanism 或 repeated runs。
- solution pool 既提供 baseline，也提供后优化的候选 assignment 来源。

### 4.5 Why MIP Alone Is Not the End

高分分析点：

- MIP 解池中的每个解可能在不同 class 或 constraint neighborhood 上表现更好。
- 单个 best solution 未必包含所有局部最佳 assignment。
- Post-optimization 的作用是安全地重组这些局部片段。

## 5. Stage 2: Validator-Aware Post-Optimization

### 目标

这是本仓库的核心方法章节，也是 Methodology 最高分的关键。

## 5.1 Data Loading and Tensor Encoding

输入：

- `data/reduced/<instance>.xml`
- `data/solutions/<instance>/solution<N>_<instance>.xml`

流程：

1. `PSTTReader` 解析 problem XML。
2. `ConstraintsResolver_v2` 建立 class-time-room variable index。
3. `SolutionLoader` 将 MIP solution XML 编码为 `x_tensor`。
4. `SolutionEvaluator` / `LocalValidator` 计算三项目标和 hard feasibility。

编码：

```text
x[(class_id, time_option_index, room_id)] -> flat index
x_tensor[i] = 1 if the assignment is selected
```

### 5.2 Pool Validation

需要说明：

- MIP solution XMLs 被统一重新验证。
- 每个 solution 记录：
  - total
  - time
  - room
  - distribution
  - valid / invalid
  - hard violations
- best valid MIP solution 是主要 baseline。

### 5.3 Handling Invalid or Near-Valid Pool Members

这个点要小心写：

- invalid pool member 不能作为最终 solution。
- 但它可能包含低代价、局部合法的 class assignment。
- 本项目只在 validator-aware repair 中利用这些局部片段。

可以描述：

- Strict encoding 失败或 hard-invalid 时，不直接接受。
- 使用 feasible anchor solution 作为 fallback。
- 只要 candidate repair 后仍 hard-feasible，才允许进入 incumbent comparison。

### 5.4 Distribution-Guided Destroy

核心思想：

- soft distribution penalty 是后优化的重要改进来源。
- 每次不随机修改大量 classes，而是优先选择与当前 soft violations 相关的 classes。

伪代码：

```text
score each class by its contribution to soft distribution violations
select destroy_size high-score classes
remove their current assignments from the incumbent
```

### 5.5 Validator-Aware Beam Repair

候选来源：

- MIP solution pool 中出现过的该 class assignments。
- 必要时 fallback 到 full class domain。

候选排序可考虑：

- time penalty
- room penalty
- affected distribution penalty
- pool frequency
- feasibility with already assigned classes

核心伪代码：

```text
Input: incumbent solution x, destroyed class set D, solution pool P
beam <- {x without assignments for D}
for each class c in D:
    candidates <- assignments of c observed in P
    next_beam <- empty
    for partial solution b in beam:
        for assignment a in candidates:
            if adding a does not violate hard constraints:
                add b + a to next_beam
    beam <- top beam_width solutions in next_beam by validator-aware score
return best complete feasible solution in beam
```

必须强调：

- hard feasibility 不是最后才检查，而是在 repair 过程中持续过滤。
- 最终仍由 full validator 计算完整 objective。

### 5.6 Acceptance Rule

```text
if candidate is valid and candidate_total < incumbent_total:
    incumbent <- candidate
else:
    keep incumbent
```

当前实验参数可写：

- `max_iter = 35`
- `destroy_size = 6`
- `beam_width = 3`
- `repair_candidate_limit = 16`
- `seed = 20260427`

### 5.7 Optional Search Components

根据篇幅简短介绍项目中实现的其他后优化组件：

- Local Search：
  - single-class move
  - room swap
  - best improvement / first improvement / simulated annealing

- LNS：
  - random / high-distribution / mixed destroy
  - greedy / beam repair

- Tensor Search：
  - softmax relaxation over class domains
  - gradient-guided discrete probes
  - only feasible candidates can replace incumbent

- Merging / Crossover：
  - top-k MIP solutions as parents
  - per-class crossover
  - greedy repair by most-constrained-first ordering

建议论文主线：

- 主方法写 MIP + Phase2 validator-aware solution-pool repair。
- 其他组件作为 implementation alternatives 或 future comparison。

## 6. Experimental Setup

### 6.1 Dataset

应报告：

- `data/reduced` 包含 reduced ITC2019 problem XML。
- `data/solutions` 包含 MIP 生成的 solution pools。
- 当前实验覆盖 15 个有 solution pool 的 instances。
- 每个 instance 有 98 个 MIP-generated solution XML。

当前 15 个实例：

| Instance |
|---|
| agh-ggis-spr17 |
| lums-spr18 |
| mary-fal18 |
| mary-spr17 |
| muni-fi-fal17 |
| muni-fi-spr16 |
| muni-fi-spr17 |
| muni-fsps-spr17 |
| muni-fsps-spr17c |
| nbi-spr18 |
| pu-d5-spr17 |
| pu-llr-spr17 |
| tg-fal17 |
| tg-spr18 |
| yach-fal17 |

如果论文最终写 14 个实例，需要先统一数据、实验表和文本中的数量，避免矛盾。

### 6.2 Baselines

主 baseline：

1. **Best valid MIP pool solution**
   - 每个实例 98 个 MIP solutions 中 valid 且 total 最低者。
   - 这是后优化必须超过的主要 baseline。

辅助 baseline：

2. **Best any MIP pool solution**
   - 包含 invalid solution 的最低 total。
   - 只用于分析 invalid pool 的局部价值，不作为可行解质量 baseline。

3. **No-post-optimization**
   - 直接输出 best valid MIP solution。
   - 用于说明 post-optimization 至少不应破坏 MIP 起点。

外部 baseline：

4. **Official leaderboard adjusted to no-student objective**
   - 官方 ITC2019 results/leaderboard 使用完整 objective，包含 student conflict。
   - 本项目不做 student sectioning，因此需要扣除 student component 后再比较。
   - 若 leaderboard 提供 raw `Student conflicts` 和 instance XML 中的 `Student Weight`，使用：

```text
OfficialNoStudentCost = OfficialTotalCost
                      - StudentConflicts * StudentWeight
```

   - 若 leaderboard 或 validator output 已提供 weighted student component，则使用：

```text
OfficialNoStudentCost = OfficialTotalCost - WeightedStudentCost
```

   - 论文中应称为 derived / adjusted leaderboard comparison，不要称为官方 no-student 排名。

如有时间，可补：

- MIP single best vs MIP pool best。
- random destroy LNS vs distribution-guided destroy。
- greedy repair vs beam repair。

### 6.3 Metrics

必须报告：

- MIP pool valid count。
- MIP pool invalid count。
- MIP pool best total。
- Post-optimization total。
- Official total cost。
- Official student conflicts。
- Student weight。
- Official no-student adjusted cost。
- Time penalty。
- Room penalty。
- Distribution penalty。
- Absolute improvement。
- Relative improvement。
- Gap to adjusted official leaderboard。
- Hard violations。
- Runtime。
- Candidate evaluations。
- Accepted repairs。

公式：

```text
Improvement(%) = (MIPPoolBest - PostOptTotal) / MIPPoolBest * 100
```

```text
GapToOfficialAdjusted(%) =
    (PostOptTotal - OfficialNoStudentCost) / OfficialNoStudentCost * 100
```

如果 `OfficialNoStudentCost = 0`，不要计算百分比 gap，只报告 absolute gap。

### 6.4 Validation

写清楚：

- 本地 validator 对齐 no-student variant：
  - student conflict 固定为 0。
  - objective 只含 time、room、distribution。
- 所有最终输出必须 `valid=True` 且 hard violations 为 0。
- 对代表性输出使用 official validator 抽查：
  - `muni-fi-spr17_phase2_direct.xml`
  - `muni-fsps-spr17c_phase2_direct.xml`

### 6.5 Implementation Details

可写：

- Python + PyTorch。
- XML parsing 使用 `PSTTReader`。
- Constraint model 使用 `ConstraintsResolver_v2`。
- `matrix=False` 使用 bits representation，降低内存。
- random seed 固定，保证可复现。
- 输出 XML 与 summary CSV。

## 7. Results

### 7.1 Overall Two-Stage Performance

主结果表建议写成：

| Instance | Valid MIP pool | Invalid MIP pool | MIP pool best | Post-opt total | Improvement | Runtime |
|---|---:|---:|---:|---:|---:|---:|
| agh-ggis-spr17 | 98 | 0 | 16514 | 16514 | 0.00% | 374.20s |
| lums-spr18 | 84 | 14 | 95 | 95 | 0.00% | 56.49s |
| mary-fal18 | 98 | 0 | 1871 | 1871 | 0.00% | 12.90s |
| mary-spr17 | 98 | 0 | 14473 | 14473 | 0.00% | 50.13s |
| muni-fi-fal17 | 98 | 0 | 273 | 273 | 0.00% | 27.42s |
| muni-fi-spr16 | 10 | 88 | 372 | 372 | 0.00% | 5.91s |
| muni-fi-spr17 | 10 | 88 | 208 | 188 | 9.62% | 73.14s |
| muni-fsps-spr17 | 78 | 20 | 368 | 368 | 0.00% | 16.98s |
| muni-fsps-spr17c | 19 | 79 | 10772 | 10601 | 1.59% | 127.10s |
| nbi-spr18 | 95 | 3 | 13721 | 13721 | 0.00% | 56.28s |
| pu-d5-spr17 | 98 | 0 | 14631 | 14631 | 0.00% | 119.51s |
| pu-llr-spr17 | 98 | 0 | 3561 | 3561 | 0.00% | 22.16s |
| tg-fal17 | 98 | 0 | 4215 | 4215 | 0.00% | 281.93s |
| tg-spr18 | 98 | 0 | 14128 | 14128 | 0.00% | 120.42s |
| yach-fal17 | 98 | 0 | 314 | 314 | 0.00% | 52.41s |

核心总结：

- Stage 1 MIP 提供每实例 98 个候选解。
- Stage 2 后优化保持 15/15 输出 hard-feasible。
- 2/15 实例获得进一步改进。
- 最大改进：`muni-fi-spr17`，208 -> 188，9.62%。
- 第二个改进：`muni-fsps-spr17c`，10772 -> 10601，1.59%。

### 7.2 Comparison with the Official Leaderboard under the No-Student Objective

这个小节非常适合提高 Evaluation 和 Scholarship 分数，因为它把项目结果放到公开强基线里比较。

写法：

- 官方 leaderboard 是完整 ITC2019 objective：

```text
OfficialTotal =
    w_time * TimePenalty
  + w_room * RoomPenalty
  + w_dist * DistributionPenalty
  + w_student * StudentConflicts
```

- 本文 objective 不含 student conflict：

```text
ProjectTotal =
    w_time * TimePenalty
  + w_room * RoomPenalty
  + w_dist * DistributionPenalty
```

- 因此将官方结果转换为：

```text
OfficialNoStudentCost =
    OfficialTotal - StudentConflicts * StudentWeight
```

建议结果表：

| Instance | Official total | Student conflicts | Student weight | Official no-student cost | MIP pool best | MIP + post-opt | Gap to official adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|
| instance-1 | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| instance-2 | TBD | TBD | TBD | TBD | TBD | TBD | TBD |

分析重点：

- 如果本文结果低于官方 no-student adjusted cost，要说明可能原因：
  - 官方完整解为了降低 student conflicts，可能牺牲 time/room/distribution。
  - 本文不考虑 student sectioning，因此三项目标更容易降低。
  - 这不表示本文优于官方完整 solver，只表示在 no-student projection 上更低。
- 如果本文结果高于官方 no-student adjusted cost，要说明差距和可能原因：
  - 官方强 solver 在 time/room/distribution 上也更优。
  - 本文 MIP pool 或后优化搜索空间仍不足。
  - 可作为 future work 的优化目标。
- 最重要的是措辞：
  - 可以说 “compared against an adjusted official leaderboard score under the no-student projection”。
  - 不要说 “outperforms the official ITC2019 leaderboard”。

### 7.3 Component-Level Improvements

建议表：

| Instance | Method | Time | Room | Distribution | Total |
|---|---|---:|---:|---:|---:|
| muni-fi-spr17 | MIP pool best | 10 | 108 | 7 | 208 |
| muni-fi-spr17 | MIP + post-opt | 10 | 108 | 5 | 188 |
| muni-fsps-spr17c | MIP pool best | 285 | 1187 | 164 | 10772 |
| muni-fsps-spr17c | MIP + post-opt | 280 | 1186 | 161 | 10601 |

分析：

- `muni-fi-spr17` 的改进来自 distribution raw penalty 从 7 降到 5，time 和 room 不变。
- `muni-fsps-spr17c` 的改进来自 time、room、distribution 三项共同降低。

### 7.4 Role of the MIP Solution Pool

重点分析 MIP 解池如何帮助 Stage 2：

- MIP 解池提供 feasible anchor。
- 多个 MIP solutions 提供 class-level assignment diversity。
- invalid-heavy pools 说明低代价局部片段可能与 hard feasibility 冲突，但可通过 repair 安全复用。

两个关键实例：

- `muni-fi-spr17`：
  - valid pool 10，invalid pool 88。
  - post-opt 改动 7 个 classes。
  - 新 assignments 来自 invalid 解池片段。

- `muni-fsps-spr17c`：
  - valid pool 19，invalid pool 79。
  - post-opt 改动 6 个 classes。
  - 改进同时影响 time、room、distribution。

### 7.5 Feasibility Results

应明确写：

- 所有 post-optimization 输出 valid。
- hard violations = 0。
- official validator 抽查：
  - `muni-fi-spr17_phase2_direct.xml` valid，Total cost = 188，Student = 0。
  - `muni-fsps-spr17c_phase2_direct.xml` valid，Total cost = 10601，Student = 0。

### 7.6 Runtime and Efficiency

需要满足评分表中的 efficiency evaluation。

分析角度：

- Stage 1 MIP 运行时间若有记录，应单独报告；若没有，说明本文重点实验记录 Stage 2 runtime。
- Stage 2 不调用 MIP/Gurobi，运行时间主要来自：
  - candidate generation
  - local validation
  - affected distribution scoring
  - beam repair
- 较大实例或 distribution-heavy instances runtime 更高。
- 后优化是相对 lightweight 的增量搜索，而不是完整重新求解。

建议图：

- Bar chart：post-optimization runtime by instance。
- Scatter plot：candidate evaluations vs runtime。
- Bar chart：valid/invalid MIP pool count by instance。

## 8. Discussion

### 8.1 Why Two-Stage Optimization Is Useful

可写：

- MIP 负责全局建模和可行性。
- 后优化负责利用多个 MIP 解之间的局部差异。
- 两者结合比单独使用后优化更稳定，因为后优化从 high-quality feasible anchors 出发。
- 也比只看 MIP best 更灵活，因为 solution pool 中的非最佳解仍可能包含有价值片段。

### 8.2 Why Improvements Are Limited to Two Instances

可能原因：

- MIP pool best 在很多实例上已经很强。
- pool 中 assignment diversity 不足。
- hard constraints 限制了局部低代价 assignment 的组合。
- 当前 candidate source 偏保守，主要使用 pool-observed assignments。
- 参数目标是保持 feasibility 和可复现，而不是最大化冒险搜索。

### 8.3 Invalid Pool Members as Local Information

这是本文较新颖的 insight：

- invalid solution 不能直接提交。
- 但 invalid solution 的部分 class assignment 可能仍是低 penalty 且局部可用。
- validator-aware repair 可以把 invalid pool 从“废解”变成“局部片段库”。

### 8.4 Limitations

诚实写：

- 不包含 student sectioning，不是完整 ITC2019 objective。
- Stage 1 MIP 的详细运行时间、参数和 optimality gap 若没有记录，需要说明限制。
- 后优化只在 2/15 实例上改进。
- 与 official ITC2019 leaderboard 的比较需要扣除 student component，因此是 no-student projection 下的派生对比，不等价于完整比赛排名。
- official validator 只抽查代表性实例时，应说明还需要批量验证。
- 当前方法依赖 MIP solution pool 的质量和多样性。

## 9. Conclusion

应总结：

- 本文提出 MIP + validator-aware post-optimization 两阶段框架。
- MIP 阶段生成每实例 98 个 candidate solutions。
- Post-optimization 阶段将 solution pool 作为局部 assignment 库。
- 实验显示所有输出保持 hard-feasible，并在两个 invalid-heavy instances 上进一步改进 MIP pool best。
- 结论：MIP solution pool 不仅可以提供最终解，也可以作为后续轻量优化的结构化搜索空间。

Future work：

- 记录并分析 MIP stage runtime、gap 和 solution diversity。
- 扩大 post-optimization candidate domain。
- 加入 adaptive destroy size、多 seed、多策略 ensemble。
- 系统比较 local search、LNS、crossover 和 tensor search。
- 恢复 student sectioning，扩展到完整 ITC2019。
- 对所有输出进行 official validator 批量验证。

## 建议图表清单

| 图表 | 放置位置 | 作用 |
|---|---|---|
| Figure 1: Two-stage pipeline | Introduction | 展示 MIP -> solution pool -> post-optimization |
| Figure 2: MIP variable / x_tensor mapping | Stage 1 / Stage 2 | 连接 MIP 变量和后优化编码 |
| Algorithm 1: MIP solution-pool generation | Stage 1 | 概括第一阶段 |
| Algorithm 2: Validator-aware beam repair | Stage 2 | 表达核心后优化算法 |
| Table 1: Dataset and solution pool | Experimental Setup | 展示实例与 98 解池 |
| Table 2: Overall results | Results | 核心结果 |
| Table 3: Adjusted official leaderboard comparison | Results | 与官方强基线做 no-student 目标对齐比较 |
| Table 4: Component-level improvements | Results | 解释改进来源 |
| Figure 3: Gap to adjusted official leaderboard | Results | 展示外部基准差距 |
| Figure 4: Valid vs invalid MIP pool count | Analysis | 支撑 invalid pool 片段价值 |
| Figure 5: Runtime by instance | Efficiency analysis | 满足效率评估要求 |

## 推荐贡献表述

可在 Introduction 末尾使用类似结构：

```text
This paper makes the following contributions:
1. It formulates a no-student-assignment variant of ITC2019 timetabling with a three-component objective over time, room, and distribution penalties.
2. It presents a two-stage optimization framework in which MIP first generates a pool of feasible candidate solutions and a validator-aware post-optimization phase subsequently improves the best pool solution.
3. It develops a tensor-based solution encoding and validation pipeline for loading, evaluating, repairing, and exporting ITC2019 XML solutions.
4. It proposes a solution-pool repair method that reuses class-level assignments from MIP-generated pool members, including invalid or near-valid members, while preserving hard feasibility.
5. It evaluates the framework on 15 ITC2019 solution pools and shows that all final outputs remain feasible, with further improvements over the MIP pool best on two instances.
6. It compares the resulting three-component scores with official ITC2019 leaderboard results after subtracting the weighted student-conflict component.
```

## 写作风险提醒

- 不要把论文写成“只有 post-optimization”；完整项目应是 MIP + post-optimization。
- 不要把 student conflict 写入本文 objective。
- 不要声称 post-optimization 全部实例都提升；当前结果是 2/15。
- 不要把 invalid pool 的低 total 当作可行 baseline。
- 不要直接声称超过 ITC2019 SOTA；如果使用 leaderboard，应明确这是 `Total - StudentConflicts * StudentWeight` 的 no-student 派生比较。
- 不要忽略 MIP 阶段；至少要解释变量、约束、目标、solution pool generation。
- 不要只给 total；必须拆 time、room、distribution，并报告 hard violations。
- 如果 MIP stage runtime/gap 没有记录，不要编造，应写为 limitation 或补实验。

## 最终 70+ 自检清单

- [ ] 论文题目和摘要体现 MIP + post-optimization 两阶段。
- [ ] Research question 明确，并与 integer programming / combinatorial optimization / timetabling 相关。
- [ ] Introduction 解释为什么 MIP 后还需要 post-optimization。
- [ ] Related Work 覆盖 ITC2019、MIP、matheuristics、LNS、solution merging。
- [ ] Problem Definition 清楚说明 no-student variant。
- [ ] Stage 1 有 MIP variables、constraints、objective、solution pool generation。
- [ ] Stage 2 有 encoding、validation、destroy、beam repair、acceptance rule。
- [ ] Evaluation 的主要 baseline 是 best valid MIP pool solution。
- [ ] Evaluation 包含 official leaderboard adjusted no-student comparison。
- [ ] 所有结果报告 hard feasibility。
- [ ] 至少两个改进实例有 component-level analysis。
- [ ] 有 runtime / efficiency analysis。
- [ ] 有 limitations，尤其是 student sectioning 和 MIP runtime/gap。
- [ ] 图表可读，格式符合 ACM/IEEE 双栏。
