# Phase 1B 方法 / 组件说明

本文档用于澄清 Phase 1B 中各方法、组件和参数批次的关系，避免论文中把“独立方法”和“内部配置”混用。

Phase 1B 的任务是：从 Phase 1A MIP solution pool 出发，只优化 class assignment 的 `time + room + distribution`，不处理 student assignment。

## 1. 总体分类

| 名称 | 类型 | 是否适合论文主表 | 说明 |
|---|---|---|---|
| MIP pool best | Baseline | 是 | Phase 1A 已有 solution pool 的 best valid solution |
| Solution-Pool LNS / Direct Repair | 独立 Phase 1B 方法 | 是 | 当前轻量、可全实例跑通的主要后优化方法 |
| Tensor Gradient Search | 独立 Phase 1B 方法 | 是，作为探索性方法 | 能在 `muni-fsps-spr17c` 上取得更好结果，但建模成本高 |
| Full-model LNS | 独立实现 / 诊断方法 | 不建议进主表 | 使用完整 tensor constraint model，运行成本过高 |
| Local Search | 独立 baseline 方法 | 暂不进主表 | 已实现，但目前缺全实例结果 |
| Solution Merging | 独立候选方法 | 暂不进主表 | 已实现，但当前报告中缺系统结果 |
| Beam Repair | LNS 内部组件 | 不作为独立方法 | 是 repair strategy |
| Validator Delta Scoring | LNS 内部组件 | 不作为独立方法 | 是 repair scoring strategy |
| Affected Distribution Cache | LNS 工程优化 | 不作为独立方法 | 加速 validator-aware scoring |
| High Distribution Destroy | LNS 内部组件 | 可作为消融项 | 是 destroy strategy |
| Mixed Destroy | LNS 内部组件 | 可作为消融项 | random 与 high-distribution 混合 |
| MARL-guided Destroy | LNS 内部组件 | 可作为消融项 | 已有部分结果证明有一定效果，但还需完整同预算对比 |

## 2. MIP Pool Best

### 定位

Phase 1A 的 baseline，不是 Phase 1B 新算法。

Phase 1B 的 improvement 都应相对它计算：

```text
Phase1B improvement = pool best total - method total score
```

### 涉及文件

| 文件 | 作用 |
|---|---|
| `data/solutions/<instance>/solution*.xml` | Phase 1A MIP solution pool |
| `src/solution_io/loader.py` | 读取 solution XML |
| `src/solution_io/local_validator.py` | 本地 validator，计算 class-only total |
| `output/validation/solutions_validation_summary.csv` | 已验证的 pool best 汇总 |

### 如何运行 / 验证

当前没有单独的 pool-best 命令；通常由 `main.py` 或实验脚本加载 solution pool 时自动计算。若只需要复核，使用已有验证输出：

```powershell
Import-Csv .\output\validation\solutions_validation_summary.csv | Format-Table
```

## 3. Solution-Pool LNS / Direct Repair

### 定位

这是当前 Phase 1B 最适合进入论文主表的方法。

它不构建完整 `ConstraintsResolver` sparse hard matrix，而是直接从 `data/solutions` 的 XML 解池出发：

1. 用本地 validator 找到 best valid solution。
2. 对每个 class 收集 solution pool 中出现过的 assignment 作为候选域。
3. destroy 当前解中的部分 class。
4. 用 beam repair 在解池候选域内重新插入这些 class。
5. 只接受 validator-feasible 且不变差 / 更好的解。

### 与 Full-model LNS 的区别

| 对比项 | Solution-Pool LNS / Direct Repair | Full-model LNS |
|---|---|---|
| 输入 | XML solution pool | 编码后的 `x_tensor` |
| 候选域 | 解池中出现过的 assignment | `ConstraintsResolver.x` 的完整变量域 |
| hard feasibility | `LocalValidator.validate_solution` | `ConstraintTracker` + evaluator |
| 是否构建巨大 sparse hard constraints | 否 | 是 |
| 速度 | 快，适合全实例 | 慢，大实例成本高 |
| 当前论文角色 | 主方法 | 诊断/工程对照 |

### 涉及文件

| 文件 | 作用 |
|---|---|
| `scripts/run_phase2_direct_solution_experiment.py` | 全实例 direct repair 实验脚本 |
| `src/solution_io/local_validator.py` | 本地 validator |
| `src/solution_io/loader.py` | XML 读取与保存 |
| `src/utils/dataReader.py` | 读取 reduced problem XML |

### Direct Baseline / Stronger / Extended 的关系

它们不是三个方法，只是同一个 direct repair 方法的三组参数。

### 推荐运行入口

推荐从 `main.py` 使用轻量入口运行：

```powershell
python .\main.py --method direct_lns --instance muni-fsps-spr17c --device cpu
```

批量运行：

```powershell
python .\main.py --method direct_lns --data_folder .\data\batch_15 --device cpu
```

`direct_lns` 只加载 problem XML 和 solution XML，不会构建 `ConstraintsResolver`，因此会跳过 `Adding distribution constraints`。

### 配置：direct baseline

```yaml
method_family: solution_pool_lns_direct_repair
output_dir: output/phase2_direct_all_instances
max_iter: 5
destroy_size: 3
mixed_high_distribution_prob: 0.8
repair_method: beam
beam_width: 2
repair_candidate_limit: 8
seed: 20260425
```

运行方式：

```powershell
python .\scripts\run_phase2_direct_solution_experiment.py `
  --data-dir .\data\reduced `
  --solutions-dir .\data\solutions `
  --output-dir .\output\phase2_direct_all_instances `
  --max-iter 5 `
  --destroy-size 3 `
  --beam-width 2 `
  --repair-candidate-limit 8 `
  --mixed-high-distribution-prob 0.8 `
  --seed 20260425
```

### 配置：direct stronger

```yaml
method_family: solution_pool_lns_direct_repair
output_dir: output/phase2_direct_all_instances_stronger
max_iter: 20
destroy_size: 5
mixed_high_distribution_prob: 0.8
repair_method: beam
beam_width: 2
repair_candidate_limit: 12
seed: 20260426
```

运行方式：

```powershell
python .\scripts\run_phase2_direct_solution_experiment.py `
  --data-dir .\data\reduced `
  --solutions-dir .\data\solutions `
  --output-dir .\output\phase2_direct_all_instances_stronger `
  --max-iter 20 `
  --destroy-size 5 `
  --beam-width 2 `
  --repair-candidate-limit 12 `
  --mixed-high-distribution-prob 0.8 `
  --seed 20260426
```

### 配置：direct extended

```yaml
method_family: solution_pool_lns_direct_repair
output_dir: output/phase2_direct_all_instances_extended_20260425
max_iter: 35
destroy_size: 6
mixed_high_distribution_prob: 0.9
repair_method: beam
beam_width: 3
repair_candidate_limit: 16
seed: 20260427
```

运行方式：

```powershell
python .\scripts\run_phase2_direct_solution_experiment.py `
  --data-dir .\data\reduced `
  --solutions-dir .\data\solutions `
  --output-dir .\output\phase2_direct_all_instances_extended_20260425 `
  --max-iter 35 `
  --destroy-size 6 `
  --beam-width 3 `
  --repair-candidate-limit 16 `
  --mixed-high-distribution-prob 0.9 `
  --seed 20260427
```

### 已有结果

| 输出 | 说明 |
|---|---|
| `output/phase2_direct_all_instances/phase2_direct_all_instances_summary.csv` | baseline 参数 |
| `output/phase2_direct_all_instances_stronger/phase2_direct_all_instances_summary.csv` | stronger 参数 |
| `output/phase2_direct_all_instances_extended_20260425/phase2_direct_all_instances_summary.csv` | 当前 direct repair 最好配置 |

论文主表建议使用 `direct extended`。

## 4. Tensor Gradient Search

### 定位

Phase 1B 的独立探索方法。

核心思想：

1. 为每个 `x` 变量学习一个 logit。
2. 对每个 class 的候选 assignment 做 softmax relaxation。
3. 用 differentiable surrogate 优化 time、room、soft distribution。
4. 周期性根据 logits / gradient 投影回离散解。
5. 只有 validator-feasible 且更优的离散候选才会替换 incumbent。

### 与 LNS 的区别

| 对比项 | Tensor Gradient Search | LNS / Repair |
|---|---|---|
| 搜索方式 | 连续 relaxation + 离散投影 | destroy-and-repair |
| 主要变量 | logits over `x_tensor` | class destroy set + repair candidates |
| feasibility | 离散 probe 后 validator 检查 | repair 过程中维护 / 检查 |
| 资源瓶颈 | tensor model 建模、显存、sparse operations | repair evaluator 次数 |
| 当前结果 | `muni-fsps-spr17c` 改进明显 | 多数实例更快，改进较保守 |

### 涉及文件

| 文件 | 作用 |
|---|---|
| `src/tensor_search/search.py` | Tensor Gradient Search 实现 |
| `main.py` | `method == "tensor_search"` 入口 |
| `config.yaml` | `tensor_search` 配置 |
| `output/analysis/tensor_search_server_results.csv` | 服务器结果解析汇总 |
| `E:\Desktop\test\output\output_*.log` | 服务器原始 log |
| `E:\Desktop\test\output\xml\*_tensor_search.xml` | 服务器输出 XML |

### 配置

```yaml
method: tensor_search
tensor_search:
  steps: 500
  lr: 0.05
  temperature: 1.0
  cooling: 0.995
  min_temperature: 0.1
  eval_every: 10
  log_every: 50
  init_bias: 6.0
  init_noise: 0.01
  hard_surrogate: none
  hard_weight: 0.0
  entropy_weight: 0.001
  sample_count: 2
  sample_noise: 0.5
  max_gradient_moves: 8
  gradient_options_per_class: 1
  seed: 42
  validate: false
```

### 如何运行

单实例：

```powershell
python .\main.py --method tensor_search --instance muni-fsps-spr17c --device cuda:0
```

批量实例：

```powershell
python .\main.py --method tensor_search --data_folder .\data\batch_15 --device cuda:0
```

服务器建议用：

```bash
nohup python main.py --method tensor_search --data_folder data/batch_15 --device cuda:0 > output_tensor.log 2>&1 &
```

### 已有结果

| 输出 | 说明 |
|---|---|
| `output/analysis/tensor_search_server_results.csv` | 15 个 available-pool instances 解析结果 |
| `output/tensor_search_smoke/yach-fal17_tensor_search.xml` | 本机 smoke test |

关键结论：`muni-fsps-spr17c` 从 `10772` 改进到 `10247`，优于 direct extended 的 `10601`，但建模时间很高。

## 5. Full-model LNS

### 定位

独立实现，但当前更适合作为工程诊断实验，不建议进入论文主结果表。

它使用完整 `ConstraintsResolver` 构建 `x_tensor` 和 hard / soft sparse constraint structures，再做 destroy-and-repair。

### 涉及文件

| 文件 | 作用 |
|---|---|
| `src/lns/search.py` | Full-model LNS 主实现 |
| `src/merging/greedy.py` | `ConstraintTracker`，用于 repair 时维护 hard feasibility |
| `src/solution_io/evaluator.py` | evaluator |
| `src/solution_io/local_validator.py` | validator-aware scoring |
| `main.py` | `method == "lns"` 入口 |
| `config.yaml` | `lns` 配置 |

### 配置

```yaml
method: lns
lns:
  max_iter: 500
  destroy_size: 8
  destroy_strategy: marl_guided
  mixed_high_distribution_prob: 0.7
  marl_alpha: 0.2
  marl_epsilon: 0.1
  marl_temperature: 1.0
  marl_q_weight: 1.0
  marl_distribution_weight: 0.7
  marl_local_weight: 0.2
  marl_difficulty_weight: 0.1
  marl_failed_reward: 0.02
  repair_method: beam
  beam_width: 3
  repair_scoring: validator_delta
  repair_candidate_limit: 40
  acceptance: improvement
  temperature: 100.0
  cooling: 0.995
  seed: 42
  validate: true
```

### 如何运行

单实例：

```powershell
python .\main.py --method lns --instance mary-spr17 --device cuda:0
```

批量实例：

```powershell
python .\main.py --method lns --data_folder .\data\batch_15 --device cuda:0
```

### 已有结果

| 输出 | 说明 |
|---|---|
| `output/phase2_all_instances/phase2_lns_all_instances_summary.csv` | full-model LNS 尝试，只完成 `agh-ggis-spr17` |
| `output/analysis/marl_guided_lns_partial_results.csv` | MARL-guided LNS 部分批处理结果 |
| `E:\Desktop\test\output\output1.log` | MARL-guided LNS 原始 log |

结论：方法可运行，但完整 tensor model 构建和 repair 成本高。MARL-guided destroy 有部分有效性证据，但需要同预算消融。

## 6. Local Search

### 定位

独立 baseline 方法。

它以 best pool solution 为初始解，做 single-class move 或 room-swap move，并用 delta evaluator 只评估受影响的约束。

### 涉及文件

| 文件 | 作用 |
|---|---|
| `src/local_search/search.py` | Local Search 主流程 |
| `src/local_search/neighborhood.py` | 邻域生成 |
| `src/local_search/delta_eval.py` | delta evaluation |
| `main.py` | `method == "local_search"` 入口 |
| `config.yaml` | `local_search` 配置 |

### 配置

```yaml
method: local_search
local_search:
  max_iter: 50000
  neighborhood: single_class
  acceptance: sa
  sa_temperature: 500.0
  sa_cooling: 0.9995
  restart_from_best: true
  validate: true
```

可选配置：

```yaml
local_search:
  neighborhood: room_swap       # single_class | room_swap
  acceptance: best_improvement  # best_improvement | first_improvement | sa
```

### 如何运行

```powershell
python .\main.py --method local_search --instance tg-spr18 --device cuda:0
```

### 当前论文定位

已实现、已验证可运行，但目前缺全实例结果。因此可在方法章节介绍，主实验表暂不建议纳入，除非后续补全实例结果。

## 7. Solution Merging

### 定位

独立候选方法，但当前 Phase 1B 报告中没有形成系统全实例结果。

它从 solution pool 中统计每个 class assignment 的出现频率，并尝试用 greedy / frequency / crossover 组合得到新解。

### 涉及文件

| 文件 | 作用 |
|---|---|
| `src/merging/greedy.py` | greedy / frequency / improve_from_best |
| `src/merging/crossover.py` | crossover merging |
| `main.py` | `method == "merging"` 入口 |
| `config.yaml` | `merging` 配置 |

### 配置

```yaml
method: merging
merging:
  strategy: crossover
  candidate_source: pool_only
  scoring: combined
  freq_weight: 0.3
  sort_classes: most_constrained
  num_passes: 3
  top_k: 10
  num_offspring: 500
  seed: 42
  validate: true
```

可选策略：

```yaml
merging:
  strategy: greedy           # greedy | frequency | improve_from_best | crossover
```

### 如何运行

```powershell
python .\main.py --method merging --instance tg-spr18 --device cuda:0
```

### 当前论文定位

可以作为候选方法介绍，但若没有全实例或代表实例结果，不建议放入论文结果主表。

## 8. LNS 内部组件

以下都不是完整独立方法，而是 LNS 的内部配置或工程优化。

### 8.1 Destroy Strategy

所属方法：Full-model LNS / Solution-Pool LNS。

涉及文件：

| 文件 | 作用 |
|---|---|
| `src/lns/search.py` | full-model LNS destroy strategy |
| `scripts/run_phase2_direct_solution_experiment.py` | direct repair 的 mixed high-distribution destroy |

配置：

```yaml
lns:
  destroy_strategy: random           # 随机选择 class
```

```yaml
lns:
  destroy_strategy: high_distribution
```

```yaml
lns:
  destroy_strategy: mixed
  mixed_high_distribution_prob: 0.7
```

```yaml
lns:
  destroy_strategy: marl_guided
  marl_alpha: 0.2
  marl_epsilon: 0.1
  marl_temperature: 1.0
  marl_q_weight: 1.0
  marl_distribution_weight: 0.7
  marl_local_weight: 0.2
  marl_difficulty_weight: 0.1
  marl_failed_reward: 0.02
```

差异：

| strategy | 含义 | 论文中怎么写 |
|---|---|---|
| `random` | 随机 destroy class | baseline destroy |
| `high_distribution` | 优先 destroy 当前产生 distribution penalty 的 class | distribution-aware destroy |
| `mixed` | 按概率混合 random 与 high_distribution | robust mixed destroy |
| `marl_guided` | 用 Q-value + 当前特征采样 destroy set | learning-guided destroy |

MARL-guided destroy 已有部分结果：

| 输出 | 说明 |
|---|---|
| `output/analysis/marl_guided_lns_partial_results.csv` | 6 个完成实例，2 个改进 |
| `E:\Desktop\test\output\output1.log` | 原始 log |

当前结论：可说明“有一定效果”，但还不能作为强消融结论；还需同预算对比 `random`、`high_distribution`、`mixed`。

### 8.2 Repair Method

所属方法：Full-model LNS / Solution-Pool LNS。

涉及文件：

| 文件 | 作用 |
|---|---|
| `src/lns/search.py` | full-model greedy / beam repair |
| `scripts/run_phase2_direct_solution_experiment.py` | direct beam repair |

配置：

```yaml
lns:
  repair_method: greedy
```

```yaml
lns:
  repair_method: beam
  beam_width: 3
```

差异：

| repair | 含义 |
|---|---|
| `greedy` | 每个 removed class 只选当前排序最好的可行 candidate |
| `beam` | 保留多个 partial repair states，降低局部贪心错误 |

论文写法：Beam Repair 是 LNS 的 repair component，不是独立方法。

### 8.3 Repair Scoring

所属方法：Full-model LNS。

涉及文件：

| 文件 | 作用 |
|---|---|
| `src/lns/search.py` | `_candidate_order`, `_candidate_incremental_score` |
| `src/solution_io/local_validator.py` | official-aligned distribution violation calculation |

配置：

```yaml
lns:
  repair_scoring: local
```

```yaml
lns:
  repair_scoring: validator_delta
  repair_candidate_limit: 40
```

差异：

| scoring | 含义 |
|---|---|
| `local` | 只看 time + room local penalty |
| `validator_delta` | 在候选排序中加入受影响 soft distribution rows 的官方口径评分 |

论文写法：Validator Delta Scoring 是 LNS scoring component，不是独立方法。

### 8.4 Affected Distribution Cache

所属方法：Full-model LNS。

涉及文件：

| 文件 | 作用 |
|---|---|
| `src/lns/search.py` | `_affected_score_cache`, `_soft_constraint_cost`, `_affected_distribution_score` |

配置差异：无独立 YAML 开关。只要使用 `repair_scoring: validator_delta`，该 cache 就参与候选评分。

```yaml
lns:
  repair_scoring: validator_delta
```

作用：缓存受影响 soft distribution row 的局部评分，降低 beam repair 中重复调用 validator 的成本。

论文写法：工程加速，不作为算法结果。

### 8.5 Acceptance Rule

所属方法：Full-model LNS / Local Search。

配置：

```yaml
lns:
  acceptance: improvement
```

```yaml
lns:
  acceptance: sa
  temperature: 100.0
  cooling: 0.995
```

```yaml
local_search:
  acceptance: sa
  sa_temperature: 500.0
  sa_cooling: 0.9995
```

差异：

| acceptance | 含义 |
|---|---|
| `improvement` | 只接受更优 candidate |
| `sa` | 按 simulated annealing 概率接受变差 candidate |

论文写法：参数/接受准则消融，不是独立方法。

## 9. 推荐论文实验组织

### 主结果表

建议只包含：

```text
MIP pool best
Solution-Pool LNS / Direct Repair extended
Tensor Gradient Search
Best-of-methods Phase 1B
Official SOTA no-student
```

若要加入 MARL-guided LNS，请标注为 partial / component evidence，而不是完整全实例方法。

### 消融实验表

建议单独开表：

```text
LNS destroy strategy:
random vs high_distribution vs mixed vs marl_guided

LNS repair strategy:
greedy vs beam

LNS scoring:
local vs validator_delta

Runtime engineering:
full evaluator vs affected distribution cache
```

这些消融必须尽量统一：

```yaml
common_budget:
  instances: representative_or_all_available
  max_iter: same
  destroy_size: same
  beam_width: same
  repair_candidate_limit: same
  seed: same_or_multi_seed
```

## 10. 当前已有输出与对应解释

| 输出文件 | 对应内容 | 论文用途 |
|---|---|---|
| `output/validation/solutions_validation_summary.csv` | MIP pool best | baseline |
| `output/phase2_direct_all_instances_extended_20260425/phase2_direct_all_instances_summary.csv` | Solution-Pool LNS / Direct Repair extended | Phase 1B 主方法 |
| `output/analysis/tensor_search_server_results.csv` | Tensor Gradient Search | Phase 1B 探索方法 |
| `output/analysis/marl_guided_lns_partial_results.csv` | MARL-guided LNS partial | LNS destroy policy 初步证据 |
| `output/phase2_all_instances/phase2_lns_all_instances_summary.csv` | Full-model LNS diagnostic | 工程瓶颈说明 |
| `output/experiments/lns_parameter_compare_tg-spr18.csv` | LNS 单实例参数比较 | 中间实验 / 消融动机 |
| `output/experiments/lns_stronger_tg-spr18.csv` | 更强 LNS 单实例尝试 | 中间实验 / 消融动机 |
