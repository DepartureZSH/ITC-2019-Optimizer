# 实现计划：ITC2019 后优化框架

## 总体架构

```
main.py  ←  config.yaml
   │
   ├── src/evaluator/       共享评估模块（cost + feasibility）
   ├── src/solution_io/     解的读写与编码
   │
   ├── src/merging/         方向4：解池融合 (Phase 1)
   ├── src/local_search/    方向1：局部搜索  (Phase 1)
   ├── src/lns/             方向2：大邻域搜索 (Phase 2, 待定)
   └── src/tensor_search/   方向3：张量梯度搜索 (Phase 2, 待定)
```

---

## Phase 1：基础设施 + 方向4（解池融合）+ 方向1（局部搜索）

### Step 1 — 共享基础设施

#### 1.1 `src/evaluator/` — 统一评估器

实现一个 `SolutionEvaluator` 类，接收 `ConstraintsResolver` + 解的 `x_tensor`，返回各项 cost：

```python
class SolutionEvaluator:
    def evaluate(self, x_tensor) -> dict:
        # returns: {time, room, distribution, total}
        # student conflict 不在本版本范围内
    def is_feasible(self, x_tensor) -> bool:
        # hard constraint check: (x @ hard_dist.T - hard_upper).clamp(0).sum() == 0
        # + valid assignment check: all classes assigned exactly once
```

`ConstraintsResolver_v2` 的 `objective_penalty` 已包含全部三项（time / room / soft-distribution），直接使用即可。**本版本不计算 student conflict。**

#### 1.2 `src/solution_io/` — 解的 I/O

```python
class SolutionLoader:
    def load_xml(self, xml_path, reader) -> dict:
        # 返回 {cid: {days_bits, start, weeks_bits, room}}

    def encode_to_x_tensor(self, solution_dict, constraints) -> torch.Tensor:
        # 将 solution_dict 映射到 x_tensor（one-hot per class）

    def decode_from_x_tensor(self, x_tensor, constraints) -> dict:
        # x_tensor → solution_dict

    def save_xml(self, solution_dict, reader, out_path, meta=dict):
        # 写出 ITC2019 solution XML
```

关键：`encode` 时需按 `(days_bits_str, start, weeks_bits_str)` 匹配 `class.time_options`，找到对应 `tidx`，再找到 `rid`，最终得到 `x[cid, tidx, rid]`。

#### 1.3 `main.py` + `config.yaml`

```yaml
# config.yaml 示例
instance: agh-ggis-spr17
data_dir: data/reduced
solutions_dir: data/solutions
output_dir: output

method: merging   # local_search | merging | lns | tensor_search
device: cuda:0    # cpu

merging:
  strategy: best_of_each     # greedy | best_of_each | genetic
  population_size: 98        # 使用全部 MIP 解

local_search:
  max_iter: 10000
  neighborhood: single_class  # single_class | multi_class
  acceptance: best_improvement  # best_improvement | first_improvement | sa
  sa_temperature: 100.0
  sa_cooling: 0.995
```

---

### Step 2 — 方向4：解池融合（Solution Merging）

**思路**：98个 MIP 解已覆盖大量不同的 `(class, time, room)` 组合。融合策略是从解池中提取每个 class 的最优 assignment，同时保证组合起来整体可行。

#### 2.1 贪心融合（Greedy Merging）

算法：
1. 加载所有 98 个解，编码为 `x_tensor` 列表
2. 对每个 class，统计各 `(tidx, rid)` 在解池中出现的频率，以及对应的局部 penalty（time + room）
3. 按 class 逐一贪心分配：选择 penalty 最低的 `(tidx, rid)`，检查与已分配 class 的 hard constraint 是否仍满足
4. 若冲突则回退到次优选项

实现路径：`src/merging/greedy.py`

#### 2.2 频率加权融合（Frequency-Weighted）

在贪心的基础上，给每个 `(tidx, rid)` 的得分加入"出现频率"权重：高频出现说明在多个解中都被选择，可能与其他 class 更兼容。

得分 = `w_pen × local_penalty + w_freq × (1 - frequency)`

#### 2.3 遗传/交叉融合（Crossover）

将两个解的 `x_tensor` 做 chromosome 交叉（按 class 分组），生成子代解，修复 hard constraint 违规后评估。

实现路径：`src/merging/crossover.py`

**输出**：每个实例输出一个融合后的最优解 XML，记录 cost 对比（MIP best vs. merged）。

---

### Step 3 — 方向1：局部搜索（Local Search）

**思路**：以某个初始解（如 MIP best）为起点，每次对少量 class 重新分配 `(time, room)`，若新解更好（或在 SA 温度控制下接受）则更新。

#### 3.1 邻域定义

**single-class move**（主要邻域）：
- 随机选一个 class `c`
- 枚举该 class 的所有合法 `(tidx, rid)` 选项（已在 `class_to_valid_options` 中）
- 对每个候选，检查 hard constraints 是否仍满足
- 计算 delta cost（只需重新计算涉及 `c` 的约束行）

**room-swap move**（辅助邻域）：
- 选两个同时间的 class，互换教室（若容量允许）

#### 3.2 高效 delta 评估

利用 `ConstraintsResolver_v2` 的稀疏矩阵，delta cost 计算：

```python
# 从 x_tensor 中移除旧选择，加入新选择
x_new = x_tensor.clone()
x_new[old_idx] = 0
x_new[new_idx] = 1

# 只需重新计算涉及 class c 的约束行
affected_hard_rows = ...   # hard_dist_tensor 中含 old_idx 或 new_idx 的行
affected_soft_rows = ...   # soft_dist_tensor 中含 old_idx 或 new_idx 的行
delta = eval_affected(x_new, affected_rows) - eval_affected(x_tensor, affected_rows)
```

为加速，预先构建 `var_to_hard_rows[x_idx]` 和 `var_to_soft_rows[x_idx]` 反向索引。

#### 3.3 搜索策略

| 策略 | 说明 |
|------|------|
| Best Improvement | 枚举所有邻居，选最优 |
| First Improvement | 接受第一个改进 |
| Simulated Annealing | 以概率接受差解，温度指数衰减 |

实现路径：`src/local_search/`
- `neighborhood.py` — 邻域生成器
- `delta_eval.py` — 高效 delta 评估
- `search.py` — 主搜索循环（支持 SA / best / first）

---

## Phase 2（后续）

### 方向2：大邻域搜索（LNS）

每次"破坏"一批 class（例如冲突最多的 K 个），用 MIP 或贪心重新分配，其余 class 固定。需要调用 Gurobi 或 CP-SAT。

### 方向3：张量梯度搜索

利用 `x_tensor` 的 PyTorch 计算图，对 soft penalty 做梯度下降，结合 straight-through estimator 处理离散约束。适合 GPU 加速的大规模探索。

---

## 实施顺序

```
[x] 阅读代码，理解数据结构
[ ] Step 1.2  src/solution_io/ — 实现 load/encode/decode/save
[ ] Step 1.1  src/evaluator/  — 实现 cost 评估 + feasibility check
[ ] Step 1.3  main.py + config.yaml 框架
[ ] Step 2.1  src/merging/greedy.py — 贪心融合
[ ] Step 2.2  src/merging/frequency.py — 频率加权融合
[x] Step 3.2  src/local_search/delta_eval.py — delta 评估
[x] Step 3.1  src/local_search/neighborhood.py — 邻域生成
[x] Step 3.3  src/local_search/search.py — SA 搜索
[x] Step 3 集成 smoke test：对 tg-spr18 跑 local_search，验证可行并输出 XML
[x] Phase 2 LNS baseline：src/lns/ destroy-repair 基线 + main.py method=lns
[x] Phase 2 LNS 集成测试：对 tg-spr18 跑完整 main.py lns 流程，输出 cost 对比
[ ] 集成测试：对 agh-ggis-spr17 跑完整流程，输出 cost 对比
[ ] Step 2.3  src/merging/crossover.py（可选）
```

---

## 评估指标

对每个实例，报告：
- `mip_best`：98个 MIP 解中最低 total cost
- `mip_avg`：98个 MIP 解的平均 total cost  
- `method_result`：后优化方法得到的 total cost
- `improvement`：`(mip_best - method_result) / mip_best × 100%`
- 分项：time penalty / room penalty / distribution penalty（不含 student，本版本已移除）

---

## 注意事项

1. **Student conflict 已移除**——本版本不做学生分配，solution XML 无 `<student>` 子元素，评估只含 time/room/distribution 三项
2. `ConstraintsResolver_v2.build_model()` 构建耗时，应只调用一次并复用
3. `matrix=True` 时 `PSTTReader` 内存占用高（3D tensor），局部搜索考虑 `matrix=False`
4. 解池中的解**已经是可行解**（MIP 保证 hard constraint 满足），局部搜索时要维护这一性质
5. 部分实例 `data/reduced/` 中没有对应 `data/solutions/` 条目（如 `agh-fal17.xml`），需做路径检查
