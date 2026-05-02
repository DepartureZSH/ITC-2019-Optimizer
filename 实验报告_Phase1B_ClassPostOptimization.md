# Phase 1B 实验报告：Class Solution Post-Optimization

## 1. 阶段目标

Phase 1B 在已有 Phase 1A MIP solution pool 的基础上进行后优化。

本阶段仍然只优化 class assignment，不处理 student assignment。

```text
输入：Phase 1A solution pool
输出：优化后的 class solution XML
目标：进一步降低 time + room + distribution weighted total
```

## 2. 注意命名修正

早期项目中部分报告使用了 `Phase2` 这个名字，但当时的实验实际上仍然是无 student 的 class-solution 后优化。

因此更准确的命名是：

```text
旧 Phase2 direct / LNS 实验
= Phase 1B class post-optimization
```

## 3. 已实现方法与组件边界

为避免论文实验表中把“方法”和“组件”混用，本节按论文口径重新划分。

### 3.1 可作为论文方法的求解器

| 方法 | 状态 | 论文中建议角色 |
|---|---|---|
| MIP solution pool best | 已完成 | Phase 1A baseline，不是新算法 |
| Local Search | 已实现，只有代表实例验证 | 可作为 baseline，但需要全实例结果后再进主表 |
| Solution-Pool LNS / Direct Repair | 已完成全实例验证 | Phase 1B 当前主方法 |
| Full-model LNS | 已实现，但全约束建模成本高 | 作为可扩展性诊断或工程对照，不建议作为主结果 |
| Tensor Gradient Search | 已完成 available-pool 15 实例服务器实验 | Phase 1B 独立探索方法；需报告建模成本和显存风险 |
| Solution Merging | 已实现 | 若无全实例结果，暂不进主实验表 |

### 3.2 LNS 内部组件

| 组件 / 配置 | 代码中是否存在 | 论文中建议角色 |
|---|---|---|
| Beam repair | 存在于 `src/lns/search.py` 和 direct repair script | LNS repair 子模块，不是独立方法 |
| Validator-aware scoring / affected distribution scoring | 存在于 `src/lns/search.py` | LNS scoring 子模块或消融项 |
| Affected distribution cache | 存在于 `src/lns/search.py` | 工程加速结论，不作为独立算法结果 |
| High-distribution destroy | 存在于 `src/lns/search.py` 和 direct repair script | LNS destroy strategy，可做消融 |
| Mixed random/high-distribution destroy | 存在于 `src/lns/search.py` 和 direct repair script | LNS destroy strategy，可做消融 |
| SA acceptance | 存在于 `src/lns/search.py` 与 `src/local_search/search.py` | 参数/接受准则消融，不是独立方法 |
| MARL-guided destroy | 存在于 `src/lns/search.py` | 已有部分批处理结果，可作为 LNS destroy strategy 的初步有效性证据；仍需补完整同预算消融 |

## 4. 主实验结果摘要

当前 stronger/extended direct repair 实验覆盖已有约 15 个 MIP pool instances。

已完成输出：

```text
output/phase2_direct_all_instances_stronger/phase2_direct_all_instances_summary.csv
output/phase2_direct_all_instances_extended_20260425/phase2_direct_all_instances_summary.csv
Phase2实验报告.md
Phase2实验报告_扩展搜索.md
```

扩展搜索结果：

| instance | pool best | optimized total | improvement | valid |
|---|---:|---:|---:|---|
| agh-fal17 | 待跑 | 待跑 | 待跑 | 待跑 |
| agh-fis-spr17 | 待跑 | 待跑 | 待跑 | 待跑 |
| agh-ggis-spr17 | 16514 | 16514 | 0.0 / 0.00% | True |
| agh-ggos-spr17 | 待跑 | 待跑 | 待跑 | 待跑 |
| agh-h-spr17 | 待跑 | 待跑 | 待跑 | 待跑 |
| bet-fal17 | 待跑 | 待跑 | 待跑 | 待跑 |
| bet-spr18 | 待跑 | 待跑 | 待跑 | 待跑 |
| iku-fal17 | 待跑 | 待跑 | 待跑 | 待跑 |
| iku-spr18 | 待跑 | 待跑 | 待跑 | 待跑 |
| lums-fal17 | 待跑 | 待跑 | 待跑 | 待跑 |
| lums-spr18 | 95 | 95 | 0.0 / 0.00% | True |
| mary-fal18 | 1871 | 1871 | 0.0 / 0.00% | True |
| mary-spr17 | 14473 | 14473 | 0.0 / 0.00% | True |
| muni-fi-fal17 | 273 | 273 | 0.0 / 0.00% | True |
| muni-fi-spr16 | 372 | 372 | 0.0 / 0.00% | True |
| muni-fi-spr17 | 208 | 188 | 20.0 / 9.62% | True |
| muni-fsps-spr17 | 368 | 368 | 0.0 / 0.00% | True |
| muni-fsps-spr17c | 10772 | 10601 | 171.0 / 1.59% | True |
| muni-fspsx-fal17 | 待跑 | 待跑 | 待跑 | 待跑 |
| muni-pdf-spr16 | 待跑 | 待跑 | 待跑 | 待跑 |
| muni-pdf-spr16c | 待跑 | 待跑 | 待跑 | 待跑 |
| muni-pdfx-fal17 | 待跑 | 待跑 | 待跑 | 待跑 |
| nbi-spr18 | 13721 | 13721 | 0.0 / 0.00% | True |
| pu-d5-spr17 | 14631 | 14631 | 0.0 / 0.00% | True |
| pu-d9-fal19 | 待跑 | 待跑 | 待跑 | 待跑 |
| pu-llr-spr17 | 3561 | 3561 | 0.0 / 0.00% | True |
| pu-proj-fal19 | 待跑 | 待跑 | 待跑 | 待跑 |
| tg-fal17 | 4215 | 4215 | 0.0 / 0.00% | True |
| tg-spr18 | 14128 | 14128 | 0.0 / 0.00% | True |
| yach-fal17 | 314 | 314 | 0.0 / 0.00% | True |

其余 available-pool instances 当前保持 pool best。

补充：Tensor Gradient Search 在服务器实验中将 `muni-fsps-spr17c` 从 10772 进一步改进到 10247；MARL-guided LNS 部分结果将 `mary-spr17` 从 14473 改进到 14463。因此若按 Phase 1B best-of-methods 统计，这两个实例应分别使用 10247 和 14463。

## 5. 与 Official SOTA No-Student 分数对比

Phase 1B 仍然是 class-only 后优化，因此与 SOTA 对比时使用：

```text
sota_no_student_adjusted = official_sota_total - student_conflicts * student_weight
```

Gap 定义：

```text
gap = Phase1B optimized total - SOTA no-student adjusted
```

这里的 `Phase1B optimized` 使用当前 best-of-methods：大多数实例来自 Solution-Pool LNS / Direct Repair extended；`muni-fsps-spr17c` 使用 Tensor Gradient Search 的 10247；`mary-spr17` 使用 MARL-guided LNS 部分结果的 14463。

| instance | pool best | Phase1B optimized | SOTA no-student | gap | gap % | Phase1B improvement |
|---|---:|---:|---:|---:|---:|---:|
| agh-fal17 | 待跑 | 待跑 | 60627 | 待填 | 待填 | 待跑 |
| agh-fis-spr17 | 待跑 | 待跑 | 2740 | 待填 | 待填 | 待跑 |
| agh-ggis-spr17 | 16514 | 16514 | 21545 | -5031 | -23.35% | 0 / 0.00% |
| agh-ggos-spr17 | 待跑 | 待跑 | 2730 | 待填 | 待填 | 待跑 |
| agh-h-spr17 | 待跑 | 待跑 | 21111 | 待填 | 待填 | 待跑 |
| bet-fal17 | 待跑 | 待跑 | 287106 | 待填 | 待填 | 待跑 |
| bet-spr18 | 待跑 | 待跑 | 346976 | 待填 | 待填 | 待跑 |
| iku-fal17 | 待跑 | 待跑 | 18968 | 待填 | 待填 | 待跑 |
| iku-spr18 | 待跑 | 待跑 | 25863 | 待填 | 待填 | 待跑 |
| lums-fal17 | 待跑 | 待跑 | 349 | 待填 | 待填 | 待跑 |
| lums-spr18 | 95 | 95 | 95 | +0 | +0.00% | 0 / 0.00% |
| mary-fal18 | 1871 | 1871 | 1991 | -120 | -6.03% | 0 / 0.00% |
| mary-spr17 | 14473 | 14463 | 14480 | -17 | -0.12% | 10 / 0.07% |
| muni-fi-fal17 | 273 | 273 | 597 | -324 | -54.27% | 0 / 0.00% |
| muni-fi-spr16 | 372 | 372 | 842 | -470 | -55.82% | 0 / 0.00% |
| muni-fi-spr17 | 208 | 188 | 353 | -165 | -46.74% | 20 / 9.62% |
| muni-fsps-spr17 | 368 | 368 | 368 | +0 | +0.00% | 0 / 0.00% |
| muni-fsps-spr17c | 10772 | 10247 | 2594 | +7653 | +295.03% | 525 / 4.87% |
| muni-fspsx-fal17 | 待跑 | 待跑 | 10014 | 待填 | 待填 | 待跑 |
| muni-pdf-spr16 | 待跑 | 待跑 | 9999 | 待填 | 待填 | 待跑 |
| muni-pdf-spr16c | 待跑 | 待跑 | 20602 | 待填 | 待填 | 待跑 |
| muni-pdfx-fal17 | 待跑 | 待跑 | 66838 | 待填 | 待填 | 待跑 |
| nbi-spr18 | 13721 | 13721 | 16254 | -2533 | -15.58% | 0 / 0.00% |
| pu-d5-spr17 | 14631 | 14631 | 15056 | -425 | -2.82% | 0 / 0.00% |
| pu-d9-fal19 | 待跑 | 待跑 | 26814 | 待填 | 待填 | 待跑 |
| pu-llr-spr17 | 3561 | 3561 | 4894 | -1333 | -27.24% | 0 / 0.00% |
| pu-proj-fal19 | 待跑 | 待跑 | 99713 | 待填 | 待填 | 待跑 |
| tg-fal17 | 4215 | 4215 | 4215 | +0 | +0.00% | 0 / 0.00% |
| tg-spr18 | 14128 | 14128 | 12704 | +1424 | +11.21% | 0 / 0.00% |
| yach-fal17 | 314 | 314 | 464 | -150 | -32.33% | 0 / 0.00% |

汇总：

| 指标 | 数值 |
|---|---:|
| 可对比 available-pool instances | 15 |
| 不差于 SOTA no-student adjusted | 13 |
| 差于 SOTA no-student adjusted | 2 |
| 平均 gap % | +2.80% |

Phase 1B 相比 Phase 1A 缩小了 `muni-fsps-spr17c` 和 `mary-spr17` 的 SOTA gap，其中 `muni-fsps-spr17c` 的 best-of-methods 来自 Tensor Gradient Search，`mary-spr17` 的 best-of-methods 来自 MARL-guided LNS 部分结果。`muni-fsps-spr17c` 仍明显落后于 SOTA no-student adjusted，`tg-spr18` 仍未改进，后续应作为重点优化实例。

## 6. 方法演进实验结果对比

本节汇总 Phase 1B 各方法组件的已有实验结果。优先使用 `output/` 中已经完成的 all-instances 结果；单实例结果作为组件验证和参数演进证据。

需要注意：这些实验尚未完全统一时间预算、seed 和搜索空间，因此目前只能作为方法演进证据，不能替代最终公平消融实验。历史输出目录中的 `phase2_*` 名称对应的是 class-only 后优化，应归入 Phase 1B。

### 6.1 All-instances 已有结果

这里的 `direct baseline / stronger / extended` 不是三种独立算法，而是同一个 **Solution-Pool LNS / Direct Repair** 方法在不同参数强度下的三轮实验。论文主结果建议保留 `direct extended` 作为该方法当前最好配置，并同时报告 Tensor Gradient Search 作为独立探索方法；其余 direct 批次作为参数增强过程的证据。

| 实验批次 | 方法归属 | 覆盖实例 | 配置摘要 | improved instances | 关键改进 | search seconds | total seconds | 输出 |
|---|---|---:|---|---:|---|---:|---:|---|
| direct baseline | Solution-Pool LNS / Direct Repair | 15/30 | `max_iter=5`, `destroy_size=3`, mixed high-distribution, beam width 2, candidate 8 | 0 | 无 | 41.078 | 93.070 | `output/phase2_direct_all_instances/phase2_direct_all_instances_summary.csv` |
| direct stronger | Solution-Pool LNS / Direct Repair | 15/30 | `max_iter=20`, `destroy_size=5`, mixed high-distribution, beam width 2, candidate 12 | 2 | `muni-fi-spr17`: 208->188; `muni-fsps-spr17c`: 10772->10649 | 394.388 | 444.921 | `output/phase2_direct_all_instances_stronger/phase2_direct_all_instances_summary.csv` |
| direct extended | Solution-Pool LNS / Direct Repair | 15/30 | `max_iter=35`, `destroy_size=6`, high-distribution prob 0.9, beam width 3, candidate 16 | 2 | `muni-fi-spr17`: 208->188; `muni-fsps-spr17c`: 10772->10601 | 1344.360 | 1396.949 | `output/phase2_direct_all_instances_extended_20260425/phase2_direct_all_instances_summary.csv` |
| tensor search server run | Tensor Gradient Search | 15/30 | `steps=500`, `lr=0.05`, `sample_count=2`, `hard_surrogate=none` | 1 | `muni-fsps-spr17c`: 10772->10247 | 3982.230 | 20779.330 | `output/analysis/tensor_search_server_results.csv` |
| MARL-guided LNS partial | Full-model LNS destroy strategy | 6/30 completed | `destroy_strategy=marl_guided`, `destroy_size=8`, beam width 3, candidate 40 | 2 | `mary-spr17`: 14473->14463; `muni-fi-spr17`: 208->198 | 46066.710 | 48135.110 | `output/analysis/marl_guided_lns_partial_results.csv` |
| full-model LNS attempt | Full-model LNS diagnostic | 1/30 | full `ConstraintsResolver` build + LNS repair | 0 | `agh-ggis-spr17`: 16514->16514 | 871.352 | 1371.427 | `output/phase2_all_instances/phase2_lns_all_instances_summary.csv` |

观察：

| 观察 | 说明 |
|---|---|
| direct extended 是当前 Solution-Pool LNS 最好配置 | 在 15 个 available-pool instances 上保持全部 valid，并改进 2 个实例 |
| Tensor Search 是独立方法且在单实例上更强 | `muni-fsps-spr17c` 得到 10247，优于 direct extended 的 10601 |
| MARL-guided destroy 有初步效果 | 已完成的 6 个实例中有 2 个改进，尤其 `mary-spr17` 是 direct repair 和 Tensor Search 未改进的实例 |
| 改进来自 distribution penalty 与 room/time penalty 的局部重排 | `muni-fi-spr17` distribution 从 7 降到 5；`muni-fsps-spr17c` time/room/distribution 均有下降 |
| full-model LNS 成本过高 | 单个 `agh-ggis-spr17` 需要 1371.427s，其中搜索 871.352s，不适合作为当前全实例主线 |
| direct loader + local validator 更适合全实例验证 | 避免重复构建巨大 sparse hard constraints，能快速遍历已有 solution pool |

### 6.2 Tensor Gradient Search 全实例服务器结果

Tensor Gradient Search 是 Phase 1B 的独立探索方法，代码位于 `src/tensor_search/search.py`。它对每个 class 的可行 assignment 学习 logits，用 softmax relaxation 做梯度优化，并周期性投影回离散解；最终只接受 validator-feasible 且更优的离散解。

本批结果来自服务器输出 `E:\Desktop\test\output`，解析后的汇总 CSV 已保存为 `output/analysis/tensor_search_server_results.csv`。运行配置为 `steps=500`, `lr=0.05`, `temperature=1.0`, `eval_every=10`, `sample_count=2`, `hard_surrogate=none`。

| 指标 | 数值 |
|---|---:|
| 覆盖 available-pool instances | 15/30 |
| 输出可行 | 15/15 |
| 找到改进 | 1 |
| 最好改进 | `muni-fsps-spr17c`: 10772 -> 10247, +525 / 4.87% |
| 总建模时间 | 16797.1s |
| 总搜索时间 | 3982.2s |

| instance | tensor total score | pool best | Phase1B improvement | SOTA no-student | feasible | model(s) | search(s) |
|---|---:|---:|---:|---:|---|---:|---:|
| agh-fal17 | 待跑 | 待跑 | 待跑 | 60627 | 待跑 | 待跑 | 待跑 |
| agh-fis-spr17 | 待跑 | 待跑 | 待跑 | 2740 | 待跑 | 待跑 | 待跑 |
| agh-ggis-spr17 | 16514 | 16514 | 0 / 0.00% | 21545 | True | 697.4 | 625.0 |
| agh-ggos-spr17 | 待跑 | 待跑 | 待跑 | 2730 | 待跑 | 待跑 | 待跑 |
| agh-h-spr17 | 待跑 | 待跑 | 待跑 | 21111 | 待跑 | 待跑 | 待跑 |
| bet-fal17 | 待跑 | 待跑 | 待跑 | 287106 | 待跑 | 待跑 | 待跑 |
| bet-spr18 | 待跑 | 待跑 | 待跑 | 346976 | 待跑 | 待跑 | 待跑 |
| iku-fal17 | 待跑 | 待跑 | 待跑 | 18968 | 待跑 | 待跑 | 待跑 |
| iku-spr18 | 待跑 | 待跑 | 待跑 | 25863 | 待跑 | 待跑 | 待跑 |
| lums-fal17 | 待跑 | 待跑 | 待跑 | 349 | 待跑 | 待跑 | 待跑 |
| lums-spr18 | 95 | 95 | 0 / 0.00% | 95 | True | 7992.1 | 342.2 |
| mary-fal18 | 1871 | 1871 | 0 / 0.00% | 1991 | True | 789.2 | 294.9 |
| mary-spr17 | 14473 | 14473 | 0 / 0.00% | 14480 | True | 721.2 | 296.5 |
| muni-fi-fal17 | 273 | 273 | 0 / 0.00% | 597 | True | 58.6 | 138.0 |
| muni-fi-spr16 | 372 | 372 | 0 / 0.00% | 842 | True | 77.2 | 186.2 |
| muni-fi-spr17 | 208 | 208 | 0 / 0.00% | 353 | True | 88.2 | 171.2 |
| muni-fsps-spr17 | 368 | 368 | 0 / 0.00% | 368 | True | 33.2 | 172.7 |
| muni-fsps-spr17c | 10247 | 10772 | 525 / 4.87% | 2594 | True | 4755.0 | 356.5 |
| muni-fspsx-fal17 | 待跑 | 待跑 | 待跑 | 10014 | 待跑 | 待跑 | 待跑 |
| muni-pdf-spr16 | 待跑 | 待跑 | 待跑 | 9999 | 待跑 | 待跑 | 待跑 |
| muni-pdf-spr16c | 待跑 | 待跑 | 待跑 | 20602 | 待跑 | 待跑 | 待跑 |
| muni-pdfx-fal17 | 待跑 | 待跑 | 待跑 | 66838 | 待跑 | 待跑 | 待跑 |
| nbi-spr18 | 13721 | 13721 | 0 / 0.00% | 16254 | True | 395.4 | 243.8 |
| pu-d5-spr17 | 14631 | 14631 | 0 / 0.00% | 15056 | True | 91.4 | 294.1 |
| pu-d9-fal19 | 待跑 | 待跑 | 待跑 | 26814 | 待跑 | 待跑 | 待跑 |
| pu-llr-spr17 | 3561 | 3561 | 0 / 0.00% | 4894 | True | 366.0 | 304.3 |
| pu-proj-fal19 | 待跑 | 待跑 | 待跑 | 99713 | 待跑 | 待跑 | 待跑 |
| tg-fal17 | 4215 | 4215 | 0 / 0.00% | 4215 | True | 153.9 | 208.2 |
| tg-spr18 | 14128 | 14128 | 0 / 0.00% | 12704 | True | 203.7 | 198.4 |
| yach-fal17 | 314 | 314 | 0 / 0.00% | 464 | True | 374.6 | 150.3 |

结论：Tensor Search 在 `muni-fsps-spr17c` 上明显优于当前 direct repair extended，但在其他 14 个 available-pool instances 上没有超过 pool best。因此论文中应把它作为独立 Phase 1B 方法报告，而不是 LNS 的组件；同时需要说明它依赖完整 tensor constraint model，建模成本显著高于 direct solution-pool repair。

### 6.3 单实例组件验证结果

主要对比实例为 `tg-spr18`，其 corrected MIP pool best 为：

```text
total = 14128
time = 1014
room = 140
distribution = 598
```

这些结果只用于说明组件是否有效、哪里存在瓶颈，不建议直接放入论文主结果表。

| 方法 / 组件 | 实验实例 | 归属 | 配置摘要 | seconds | repairs / accepted | final total | improvement | valid | 结论 |
|---|---|---|---|---:|---:|---:|---:|---|---|
| Local Search | tg-spr18 | 独立 baseline 方法 | SA, single-class, `max_iter=200` | 6.15 search / 117.2 build | accepted 27 | 14128 | 0.00% | True | 可运行并保持 best incumbent，但未超过 MIP best |
| LNS baseline | tg-spr18 | Full-model LNS 单实例验证 | mixed destroy, beam repair, `max_iter=500` | 待填 | repairs 492 / accepted 0 | 14128 | 0.00% | True | 大量 repair 可行，但未找到改进 |
| Validator Delta Scoring | tg-spr18 | Full-model LNS 内部 scoring | random destroy, `validator_delta`, `candidate_limit=8` | 29.846 | repairs 15 / accepted 0 | 14128 | 0.00% | True | 评分更贴近官方目标，但它不是独立方法 |
| High Distribution Destroy | tg-spr18 | LNS destroy strategy | `high_distribution`, `validator_delta` | 21.961 | repairs 8 / accepted 0 | 14128 | 0.00% | True | 能稳定命中 soft-violation class，但局部破坏规模不足 |
| Mixed Destroy + Validator Delta | tg-spr18 | LNS destroy + scoring 组合 | `mixed`, high-dist prob 0.7 | 30.265 | repairs 13 / accepted 0 | 14128 | 0.00% | True | random 与 high-distribution 混合后仍未越过局部平台 |
| Stronger LNS + SA | tg-spr18 | Full-model LNS 参数批次 | destroy 10, SA, candidate 16 | 174.081 | repairs 21 / accepted 9 | 14128 | 0.00% | True | SA 能接受中间解，但最佳仍回到 MIP best |
| Beam Repair | tg-spr18 | LNS repair strategy | beam width 2, candidate 6 | 56.71 | repairs 2 / accepted 1 | 14128 | 0.00% | True | 功能闭环通过，但 full evaluator 版本速度较慢 |
| Affected Distribution Cache | tg-spr18 | Full-model LNS 工程优化 | same beam config + affected cache | 8.29 | repairs 1 / accepted 1 | 14128 | 0.00% | True | 将 beam smoke test 从 56.71s 降到 8.29s |
| MARL-guided Destroy | partial batch | LNS destroy strategy | `destroy_strategy=marl_guided`, beam width 3, candidate 40 | 46066.71 search / 2068.4 build | accepted 2 / repairs 1355 | best partial: 198 on `muni-fi-spr17` | 2/6 completed instances improved | True | 已有部分结果，证明有一定效果；仍需完整同预算消融 |

### 6.4 LNS 小参数对比

输出文件：

```text
output/experiments/lns_parameter_compare_tg-spr18.csv
```

| name | destroy strategy | repair scoring | candidate limit | seconds | repairs | accepted | total | improvement |
|---|---|---|---:|---:|---:|---:|---:|---:|
| random_local | random | local | 0 | 14.517 | 79 | 0 | 14128 | 0.00% |
| random_delta | random | validator_delta | 8 | 29.846 | 15 | 0 | 14128 | 0.00% |
| high_distribution_delta | high_distribution | validator_delta | 8 | 21.961 | 8 | 0 | 14128 | 0.00% |
| mixed_delta | mixed | validator_delta | 8 | 30.265 | 13 | 0 | 14128 | 0.00% |

观察：

| 观察 | 说明 |
|---|---|
| `validator_delta` 更严格 | 更贴近官方 total，但小 candidate limit 下 repair 数下降 |
| `high_distribution` 能定向破坏 soft penalty class | 但 destroy size = 5 时不足以穿过局部平台 |
| `mixed` 没有带来立即改善 | 需要更大 destroy 或 SA / beam / MIP repair 配合 |

### 6.5 MARL-guided LNS 部分结果

本节记录 `E:\Desktop\test\output\output1.log` 中已完成的 MARL-guided LNS 批处理结果。该批次尚未完成 13 个实例，因此不能作为最终全实例主实验；但已完成的 6 个实例中有 2 个出现可行改进，可作为 MARL-guided destroy strategy 有一定效果的初步证据。

配置：`destroy_strategy=marl_guided`, `destroy_size=8`, `acceptance=improvement`, `repair_method=beam`, `repair_scoring=validator_delta`, `repair_candidate_limit=40`, `beam_width=3`, `max_iter=500`。

| 指标 | 数值 |
|---|---:|
| 已完成实例 | 6 |
| 输出可行 | 6/6 |
| 找到改进 | 2 |
| 代表性改进 | `muni-fi-spr17`: 208 -> 198, +10 / 4.81%; `mary-spr17`: 14473 -> 14463, +10 / 0.07% |
| 已完成搜索时间 | 46066.7s |

| instance | pool best | MARL-guided LNS total | improvement | feasible | accepted | repairs | search(s) |
|---|---:|---:|---:|---|---:|---:|---:|
| mary-fal18 | 1871 | 1871 | 0 / 0.00% | True | 0 | 130 | 20551.6 |
| mary-spr17 | 14473 | 14463 | 10 / 0.07% | True | 1 | 130 | 20782.4 |
| muni-fi-fal17 | 273 | 273 | 0 / 0.00% | True | 0 | 227 | 932.3 |
| muni-fi-spr16 | 363 | 363 | 0 / 0.00% | True | 0 | 351 | 1164.9 |
| muni-fi-spr17 | 208 | 198 | 10 / 4.81% | True | 1 | 228 | 1961.7 |
| muni-fsps-spr17 | 368 | 368 | 0 / 0.00% | True | 0 | 289 | 673.8 |
| muni-fsps-spr17c | 待完成 | 待完成 | 待完成 | 待完成 | 待完成 | 待完成 | 待完成 |

结论：MARL-guided destroy 不是一个完整独立求解器，而是 LNS 的 destroy policy。它的价值在于能引导 LNS 选择更有潜力的 class set；当前部分结果显示它可以在 `mary-spr17` 这类 direct repair / Tensor Search 未改进的实例上产生增益，但运行成本很高，后续需要同预算对比 `random`、`high_distribution`、`mixed` 后才能作为正式消融结论。

### 6.6 Beam Repair 与 Affected Cache 对比

| version | max_iter | destroy_size | beam_width | candidate_limit | seconds | repairs | accepted | total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| full-evaluate beam | 10 | 5 | 2 | 6 | 56.71 | 2 | 1 | 14128 |
| affected-cache beam | 10 | 5 | 2 | 6 | 8.29 | 1 | 1 | 14128 |

Affected Distribution Cache 的主要贡献是速度，而不是直接改善 objective。它使更大的 beam width、candidate limit 和更多迭代成为可行。

### 6.7 内部 tracking 表：不作为论文主结果

本节保留为项目内部 tracking，方便后续补实验。它不应直接作为论文主结果表，因为其中混合了独立方法、LNS 内部组件、参数批次和单实例 smoke test。论文主结果应优先使用 Section 4、Section 5、Section 6.2 和 Section 6.5 中的 `pool best`、`Solution-Pool LNS / Direct Repair extended`、`Tensor Gradient Search`、`MARL-guided LNS partial`、`SOTA no-student` 对比。

没有对应实验输出的单元格标为 `待跑`。

统一列定义：

| 列 | 含义 |
|---|---|
| method total score | 该方法当前得到的 class-only total |
| pool best | Phase 1A MIP solution pool 中 best valid total |
| Phase1B improvement | `pool best - method total score`，越大越好 |
| SOTA no-student | official SOTA total 扣除 student conflict 后的 class-only 参考值 |

<details>
<summary>Direct baseline LNS/Beam</summary>

| instance | method total score | pool best | Phase1B improvement | SOTA no-student |
|---|---:|---:|---:|---:|
| agh-fal17 | 待跑 | 待跑 | 待跑 | 60627 |
| agh-fis-spr17 | 待跑 | 待跑 | 待跑 | 2740 |
| agh-ggis-spr17 | 16514 | 16514 | 0 / 0.00% | 21545 |
| agh-ggos-spr17 | 待跑 | 待跑 | 待跑 | 2730 |
| agh-h-spr17 | 待跑 | 待跑 | 待跑 | 21111 |
| bet-fal17 | 待跑 | 待跑 | 待跑 | 287106 |
| bet-spr18 | 待跑 | 待跑 | 待跑 | 346976 |
| iku-fal17 | 待跑 | 待跑 | 待跑 | 18968 |
| iku-spr18 | 待跑 | 待跑 | 待跑 | 25863 |
| lums-fal17 | 待跑 | 待跑 | 待跑 | 349 |
| lums-spr18 | 95 | 95 | 0 / 0.00% | 95 |
| mary-fal18 | 1871 | 1871 | 0 / 0.00% | 1991 |
| mary-spr17 | 14473 | 14473 | 0 / 0.00% | 14480 |
| muni-fi-fal17 | 273 | 273 | 0 / 0.00% | 597 |
| muni-fi-spr16 | 372 | 372 | 0 / 0.00% | 842 |
| muni-fi-spr17 | 208 | 208 | 0 / 0.00% | 353 |
| muni-fsps-spr17 | 368 | 368 | 0 / 0.00% | 368 |
| muni-fsps-spr17c | 10772 | 10772 | 0 / 0.00% | 2594 |
| muni-fspsx-fal17 | 待跑 | 待跑 | 待跑 | 10014 |
| muni-pdf-spr16 | 待跑 | 待跑 | 待跑 | 9999 |
| muni-pdf-spr16c | 待跑 | 待跑 | 待跑 | 20602 |
| muni-pdfx-fal17 | 待跑 | 待跑 | 待跑 | 66838 |
| nbi-spr18 | 13721 | 13721 | 0 / 0.00% | 16254 |
| pu-d5-spr17 | 14631 | 14631 | 0 / 0.00% | 15056 |
| pu-d9-fal19 | 待跑 | 待跑 | 待跑 | 26814 |
| pu-llr-spr17 | 3561 | 3561 | 0 / 0.00% | 4894 |
| pu-proj-fal19 | 待跑 | 待跑 | 待跑 | 99713 |
| tg-fal17 | 4215 | 4215 | 0 / 0.00% | 4215 |
| tg-spr18 | 14128 | 14128 | 0 / 0.00% | 12704 |
| yach-fal17 | 314 | 314 | 0 / 0.00% | 464 |

</details>

<details>
<summary>Direct stronger LNS/Beam</summary>

| instance | method total score | pool best | Phase1B improvement | SOTA no-student |
|---|---:|---:|---:|---:|
| agh-fal17 | 待跑 | 待跑 | 待跑 | 60627 |
| agh-fis-spr17 | 待跑 | 待跑 | 待跑 | 2740 |
| agh-ggis-spr17 | 16514 | 16514 | 0 / 0.00% | 21545 |
| agh-ggos-spr17 | 待跑 | 待跑 | 待跑 | 2730 |
| agh-h-spr17 | 待跑 | 待跑 | 待跑 | 21111 |
| bet-fal17 | 待跑 | 待跑 | 待跑 | 287106 |
| bet-spr18 | 待跑 | 待跑 | 待跑 | 346976 |
| iku-fal17 | 待跑 | 待跑 | 待跑 | 18968 |
| iku-spr18 | 待跑 | 待跑 | 待跑 | 25863 |
| lums-fal17 | 待跑 | 待跑 | 待跑 | 349 |
| lums-spr18 | 95 | 95 | 0 / 0.00% | 95 |
| mary-fal18 | 1871 | 1871 | 0 / 0.00% | 1991 |
| mary-spr17 | 14473 | 14473 | 0 / 0.00% | 14480 |
| muni-fi-fal17 | 273 | 273 | 0 / 0.00% | 597 |
| muni-fi-spr16 | 372 | 372 | 0 / 0.00% | 842 |
| muni-fi-spr17 | 188 | 208 | 20 / 9.62% | 353 |
| muni-fsps-spr17 | 368 | 368 | 0 / 0.00% | 368 |
| muni-fsps-spr17c | 10649 | 10772 | 123 / 1.14% | 2594 |
| muni-fspsx-fal17 | 待跑 | 待跑 | 待跑 | 10014 |
| muni-pdf-spr16 | 待跑 | 待跑 | 待跑 | 9999 |
| muni-pdf-spr16c | 待跑 | 待跑 | 待跑 | 20602 |
| muni-pdfx-fal17 | 待跑 | 待跑 | 待跑 | 66838 |
| nbi-spr18 | 13721 | 13721 | 0 / 0.00% | 16254 |
| pu-d5-spr17 | 14631 | 14631 | 0 / 0.00% | 15056 |
| pu-d9-fal19 | 待跑 | 待跑 | 待跑 | 26814 |
| pu-llr-spr17 | 3561 | 3561 | 0 / 0.00% | 4894 |
| pu-proj-fal19 | 待跑 | 待跑 | 待跑 | 99713 |
| tg-fal17 | 4215 | 4215 | 0 / 0.00% | 4215 |
| tg-spr18 | 14128 | 14128 | 0 / 0.00% | 12704 |
| yach-fal17 | 314 | 314 | 0 / 0.00% | 464 |

</details>

<details>
<summary>Direct extended LNS/Beam</summary>

| instance | method total score | pool best | Phase1B improvement | SOTA no-student |
|---|---:|---:|---:|---:|
| agh-fal17 | 待跑 | 待跑 | 待跑 | 60627 |
| agh-fis-spr17 | 待跑 | 待跑 | 待跑 | 2740 |
| agh-ggis-spr17 | 16514 | 16514 | 0 / 0.00% | 21545 |
| agh-ggos-spr17 | 待跑 | 待跑 | 待跑 | 2730 |
| agh-h-spr17 | 待跑 | 待跑 | 待跑 | 21111 |
| bet-fal17 | 待跑 | 待跑 | 待跑 | 287106 |
| bet-spr18 | 待跑 | 待跑 | 待跑 | 346976 |
| iku-fal17 | 待跑 | 待跑 | 待跑 | 18968 |
| iku-spr18 | 待跑 | 待跑 | 待跑 | 25863 |
| lums-fal17 | 待跑 | 待跑 | 待跑 | 349 |
| lums-spr18 | 95 | 95 | 0 / 0.00% | 95 |
| mary-fal18 | 1871 | 1871 | 0 / 0.00% | 1991 |
| mary-spr17 | 14473 | 14473 | 0 / 0.00% | 14480 |
| muni-fi-fal17 | 273 | 273 | 0 / 0.00% | 597 |
| muni-fi-spr16 | 372 | 372 | 0 / 0.00% | 842 |
| muni-fi-spr17 | 188 | 208 | 20 / 9.62% | 353 |
| muni-fsps-spr17 | 368 | 368 | 0 / 0.00% | 368 |
| muni-fsps-spr17c | 10601 | 10772 | 171 / 1.59% | 2594 |
| muni-fspsx-fal17 | 待跑 | 待跑 | 待跑 | 10014 |
| muni-pdf-spr16 | 待跑 | 待跑 | 待跑 | 9999 |
| muni-pdf-spr16c | 待跑 | 待跑 | 待跑 | 20602 |
| muni-pdfx-fal17 | 待跑 | 待跑 | 待跑 | 66838 |
| nbi-spr18 | 13721 | 13721 | 0 / 0.00% | 16254 |
| pu-d5-spr17 | 14631 | 14631 | 0 / 0.00% | 15056 |
| pu-d9-fal19 | 待跑 | 待跑 | 待跑 | 26814 |
| pu-llr-spr17 | 3561 | 3561 | 0 / 0.00% | 4894 |
| pu-proj-fal19 | 待跑 | 待跑 | 待跑 | 99713 |
| tg-fal17 | 4215 | 4215 | 0 / 0.00% | 4215 |
| tg-spr18 | 14128 | 14128 | 0 / 0.00% | 12704 |
| yach-fal17 | 314 | 314 | 0 / 0.00% | 464 |

</details>

<details>
<summary>Full-model LNS attempt</summary>

| instance | method total score | pool best | Phase1B improvement | SOTA no-student |
|---|---:|---:|---:|---:|
| agh-fal17 | 待跑 | 待跑 | 待跑 | 60627 |
| agh-fis-spr17 | 待跑 | 待跑 | 待跑 | 2740 |
| agh-ggis-spr17 | 16514 | 16514 | 0 / 0.00% | 21545 |
| agh-ggos-spr17 | 待跑 | 待跑 | 待跑 | 2730 |
| agh-h-spr17 | 待跑 | 待跑 | 待跑 | 21111 |
| bet-fal17 | 待跑 | 待跑 | 待跑 | 287106 |
| bet-spr18 | 待跑 | 待跑 | 待跑 | 346976 |
| iku-fal17 | 待跑 | 待跑 | 待跑 | 18968 |
| iku-spr18 | 待跑 | 待跑 | 待跑 | 25863 |
| lums-fal17 | 待跑 | 待跑 | 待跑 | 349 |
| lums-spr18 | 待跑 | 95 | 待跑 | 95 |
| mary-fal18 | 待跑 | 1871 | 待跑 | 1991 |
| mary-spr17 | 待跑 | 14473 | 待跑 | 14480 |
| muni-fi-fal17 | 待跑 | 273 | 待跑 | 597 |
| muni-fi-spr16 | 待跑 | 372 | 待跑 | 842 |
| muni-fi-spr17 | 待跑 | 208 | 待跑 | 353 |
| muni-fsps-spr17 | 待跑 | 368 | 待跑 | 368 |
| muni-fsps-spr17c | 待跑 | 10772 | 待跑 | 2594 |
| muni-fspsx-fal17 | 待跑 | 待跑 | 待跑 | 10014 |
| muni-pdf-spr16 | 待跑 | 待跑 | 待跑 | 9999 |
| muni-pdf-spr16c | 待跑 | 待跑 | 待跑 | 20602 |
| muni-pdfx-fal17 | 待跑 | 待跑 | 待跑 | 66838 |
| nbi-spr18 | 待跑 | 13721 | 待跑 | 16254 |
| pu-d5-spr17 | 待跑 | 14631 | 待跑 | 15056 |
| pu-d9-fal19 | 待跑 | 待跑 | 待跑 | 26814 |
| pu-llr-spr17 | 待跑 | 3561 | 待跑 | 4894 |
| pu-proj-fal19 | 待跑 | 待跑 | 待跑 | 99713 |
| tg-fal17 | 待跑 | 4215 | 待跑 | 4215 |
| tg-spr18 | 待跑 | 14128 | 待跑 | 12704 |
| yach-fal17 | 待跑 | 314 | 待跑 | 464 |

</details>

<details>
<summary>Local Search</summary>

| instance | method total score | pool best | Phase1B improvement | SOTA no-student |
|---|---:|---:|---:|---:|
| agh-fal17 | 待跑 | 待跑 | 待跑 | 60627 |
| agh-fis-spr17 | 待跑 | 待跑 | 待跑 | 2740 |
| agh-ggis-spr17 | 待跑 | 16514 | 待跑 | 21545 |
| agh-ggos-spr17 | 待跑 | 待跑 | 待跑 | 2730 |
| agh-h-spr17 | 待跑 | 待跑 | 待跑 | 21111 |
| bet-fal17 | 待跑 | 待跑 | 待跑 | 287106 |
| bet-spr18 | 待跑 | 待跑 | 待跑 | 346976 |
| iku-fal17 | 待跑 | 待跑 | 待跑 | 18968 |
| iku-spr18 | 待跑 | 待跑 | 待跑 | 25863 |
| lums-fal17 | 待跑 | 待跑 | 待跑 | 349 |
| lums-spr18 | 待跑 | 95 | 待跑 | 95 |
| mary-fal18 | 待跑 | 1871 | 待跑 | 1991 |
| mary-spr17 | 待跑 | 14473 | 待跑 | 14480 |
| muni-fi-fal17 | 待跑 | 273 | 待跑 | 597 |
| muni-fi-spr16 | 待跑 | 372 | 待跑 | 842 |
| muni-fi-spr17 | 待跑 | 208 | 待跑 | 353 |
| muni-fsps-spr17 | 待跑 | 368 | 待跑 | 368 |
| muni-fsps-spr17c | 待跑 | 10772 | 待跑 | 2594 |
| muni-fspsx-fal17 | 待跑 | 待跑 | 待跑 | 10014 |
| muni-pdf-spr16 | 待跑 | 待跑 | 待跑 | 9999 |
| muni-pdf-spr16c | 待跑 | 待跑 | 待跑 | 20602 |
| muni-pdfx-fal17 | 待跑 | 待跑 | 待跑 | 66838 |
| nbi-spr18 | 待跑 | 13721 | 待跑 | 16254 |
| pu-d5-spr17 | 待跑 | 14631 | 待跑 | 15056 |
| pu-d9-fal19 | 待跑 | 待跑 | 待跑 | 26814 |
| pu-llr-spr17 | 待跑 | 3561 | 待跑 | 4894 |
| pu-proj-fal19 | 待跑 | 待跑 | 待跑 | 99713 |
| tg-fal17 | 待跑 | 4215 | 待跑 | 4215 |
| tg-spr18 | 14128 | 14128 | 0 / 0.00% | 12704 |
| yach-fal17 | 待跑 | 314 | 待跑 | 464 |

</details>

<details>
<summary>LNS baseline single-instance</summary>

| instance | method total score | pool best | Phase1B improvement | SOTA no-student |
|---|---:|---:|---:|---:|
| agh-fal17 | 待跑 | 待跑 | 待跑 | 60627 |
| agh-fis-spr17 | 待跑 | 待跑 | 待跑 | 2740 |
| agh-ggis-spr17 | 待跑 | 16514 | 待跑 | 21545 |
| agh-ggos-spr17 | 待跑 | 待跑 | 待跑 | 2730 |
| agh-h-spr17 | 待跑 | 待跑 | 待跑 | 21111 |
| bet-fal17 | 待跑 | 待跑 | 待跑 | 287106 |
| bet-spr18 | 待跑 | 待跑 | 待跑 | 346976 |
| iku-fal17 | 待跑 | 待跑 | 待跑 | 18968 |
| iku-spr18 | 待跑 | 待跑 | 待跑 | 25863 |
| lums-fal17 | 待跑 | 待跑 | 待跑 | 349 |
| lums-spr18 | 待跑 | 95 | 待跑 | 95 |
| mary-fal18 | 待跑 | 1871 | 待跑 | 1991 |
| mary-spr17 | 待跑 | 14473 | 待跑 | 14480 |
| muni-fi-fal17 | 待跑 | 273 | 待跑 | 597 |
| muni-fi-spr16 | 待跑 | 372 | 待跑 | 842 |
| muni-fi-spr17 | 待跑 | 208 | 待跑 | 353 |
| muni-fsps-spr17 | 待跑 | 368 | 待跑 | 368 |
| muni-fsps-spr17c | 待跑 | 10772 | 待跑 | 2594 |
| muni-fspsx-fal17 | 待跑 | 待跑 | 待跑 | 10014 |
| muni-pdf-spr16 | 待跑 | 待跑 | 待跑 | 9999 |
| muni-pdf-spr16c | 待跑 | 待跑 | 待跑 | 20602 |
| muni-pdfx-fal17 | 待跑 | 待跑 | 待跑 | 66838 |
| nbi-spr18 | 待跑 | 13721 | 待跑 | 16254 |
| pu-d5-spr17 | 待跑 | 14631 | 待跑 | 15056 |
| pu-d9-fal19 | 待跑 | 待跑 | 待跑 | 26814 |
| pu-llr-spr17 | 待跑 | 3561 | 待跑 | 4894 |
| pu-proj-fal19 | 待跑 | 待跑 | 待跑 | 99713 |
| tg-fal17 | 待跑 | 4215 | 待跑 | 4215 |
| tg-spr18 | 14128 | 14128 | 0 / 0.00% | 12704 |
| yach-fal17 | 待跑 | 314 | 待跑 | 464 |

</details>

<details>
<summary>Validator Delta Scoring</summary>

| instance | method total score | pool best | Phase1B improvement | SOTA no-student |
|---|---:|---:|---:|---:|
| agh-fal17 | 待跑 | 待跑 | 待跑 | 60627 |
| agh-fis-spr17 | 待跑 | 待跑 | 待跑 | 2740 |
| agh-ggis-spr17 | 待跑 | 16514 | 待跑 | 21545 |
| agh-ggos-spr17 | 待跑 | 待跑 | 待跑 | 2730 |
| agh-h-spr17 | 待跑 | 待跑 | 待跑 | 21111 |
| bet-fal17 | 待跑 | 待跑 | 待跑 | 287106 |
| bet-spr18 | 待跑 | 待跑 | 待跑 | 346976 |
| iku-fal17 | 待跑 | 待跑 | 待跑 | 18968 |
| iku-spr18 | 待跑 | 待跑 | 待跑 | 25863 |
| lums-fal17 | 待跑 | 待跑 | 待跑 | 349 |
| lums-spr18 | 待跑 | 95 | 待跑 | 95 |
| mary-fal18 | 待跑 | 1871 | 待跑 | 1991 |
| mary-spr17 | 待跑 | 14473 | 待跑 | 14480 |
| muni-fi-fal17 | 待跑 | 273 | 待跑 | 597 |
| muni-fi-spr16 | 待跑 | 372 | 待跑 | 842 |
| muni-fi-spr17 | 待跑 | 208 | 待跑 | 353 |
| muni-fsps-spr17 | 待跑 | 368 | 待跑 | 368 |
| muni-fsps-spr17c | 待跑 | 10772 | 待跑 | 2594 |
| muni-fspsx-fal17 | 待跑 | 待跑 | 待跑 | 10014 |
| muni-pdf-spr16 | 待跑 | 待跑 | 待跑 | 9999 |
| muni-pdf-spr16c | 待跑 | 待跑 | 待跑 | 20602 |
| muni-pdfx-fal17 | 待跑 | 待跑 | 待跑 | 66838 |
| nbi-spr18 | 待跑 | 13721 | 待跑 | 16254 |
| pu-d5-spr17 | 待跑 | 14631 | 待跑 | 15056 |
| pu-d9-fal19 | 待跑 | 待跑 | 待跑 | 26814 |
| pu-llr-spr17 | 待跑 | 3561 | 待跑 | 4894 |
| pu-proj-fal19 | 待跑 | 待跑 | 待跑 | 99713 |
| tg-fal17 | 待跑 | 4215 | 待跑 | 4215 |
| tg-spr18 | 14128 | 14128 | 0 / 0.00% | 12704 |
| yach-fal17 | 待跑 | 314 | 待跑 | 464 |

</details>

<details>
<summary>High Distribution Destroy</summary>

| instance | method total score | pool best | Phase1B improvement | SOTA no-student |
|---|---:|---:|---:|---:|
| agh-fal17 | 待跑 | 待跑 | 待跑 | 60627 |
| agh-fis-spr17 | 待跑 | 待跑 | 待跑 | 2740 |
| agh-ggis-spr17 | 待跑 | 16514 | 待跑 | 21545 |
| agh-ggos-spr17 | 待跑 | 待跑 | 待跑 | 2730 |
| agh-h-spr17 | 待跑 | 待跑 | 待跑 | 21111 |
| bet-fal17 | 待跑 | 待跑 | 待跑 | 287106 |
| bet-spr18 | 待跑 | 待跑 | 待跑 | 346976 |
| iku-fal17 | 待跑 | 待跑 | 待跑 | 18968 |
| iku-spr18 | 待跑 | 待跑 | 待跑 | 25863 |
| lums-fal17 | 待跑 | 待跑 | 待跑 | 349 |
| lums-spr18 | 待跑 | 95 | 待跑 | 95 |
| mary-fal18 | 待跑 | 1871 | 待跑 | 1991 |
| mary-spr17 | 待跑 | 14473 | 待跑 | 14480 |
| muni-fi-fal17 | 待跑 | 273 | 待跑 | 597 |
| muni-fi-spr16 | 待跑 | 372 | 待跑 | 842 |
| muni-fi-spr17 | 待跑 | 208 | 待跑 | 353 |
| muni-fsps-spr17 | 待跑 | 368 | 待跑 | 368 |
| muni-fsps-spr17c | 待跑 | 10772 | 待跑 | 2594 |
| muni-fspsx-fal17 | 待跑 | 待跑 | 待跑 | 10014 |
| muni-pdf-spr16 | 待跑 | 待跑 | 待跑 | 9999 |
| muni-pdf-spr16c | 待跑 | 待跑 | 待跑 | 20602 |
| muni-pdfx-fal17 | 待跑 | 待跑 | 待跑 | 66838 |
| nbi-spr18 | 待跑 | 13721 | 待跑 | 16254 |
| pu-d5-spr17 | 待跑 | 14631 | 待跑 | 15056 |
| pu-d9-fal19 | 待跑 | 待跑 | 待跑 | 26814 |
| pu-llr-spr17 | 待跑 | 3561 | 待跑 | 4894 |
| pu-proj-fal19 | 待跑 | 待跑 | 待跑 | 99713 |
| tg-fal17 | 待跑 | 4215 | 待跑 | 4215 |
| tg-spr18 | 14128 | 14128 | 0 / 0.00% | 12704 |
| yach-fal17 | 待跑 | 314 | 待跑 | 464 |

</details>

<details>
<summary>Mixed Destroy + Validator Delta</summary>

| instance | method total score | pool best | Phase1B improvement | SOTA no-student |
|---|---:|---:|---:|---:|
| agh-fal17 | 待跑 | 待跑 | 待跑 | 60627 |
| agh-fis-spr17 | 待跑 | 待跑 | 待跑 | 2740 |
| agh-ggis-spr17 | 待跑 | 16514 | 待跑 | 21545 |
| agh-ggos-spr17 | 待跑 | 待跑 | 待跑 | 2730 |
| agh-h-spr17 | 待跑 | 待跑 | 待跑 | 21111 |
| bet-fal17 | 待跑 | 待跑 | 待跑 | 287106 |
| bet-spr18 | 待跑 | 待跑 | 待跑 | 346976 |
| iku-fal17 | 待跑 | 待跑 | 待跑 | 18968 |
| iku-spr18 | 待跑 | 待跑 | 待跑 | 25863 |
| lums-fal17 | 待跑 | 待跑 | 待跑 | 349 |
| lums-spr18 | 待跑 | 95 | 待跑 | 95 |
| mary-fal18 | 待跑 | 1871 | 待跑 | 1991 |
| mary-spr17 | 待跑 | 14473 | 待跑 | 14480 |
| muni-fi-fal17 | 待跑 | 273 | 待跑 | 597 |
| muni-fi-spr16 | 待跑 | 372 | 待跑 | 842 |
| muni-fi-spr17 | 待跑 | 208 | 待跑 | 353 |
| muni-fsps-spr17 | 待跑 | 368 | 待跑 | 368 |
| muni-fsps-spr17c | 待跑 | 10772 | 待跑 | 2594 |
| muni-fspsx-fal17 | 待跑 | 待跑 | 待跑 | 10014 |
| muni-pdf-spr16 | 待跑 | 待跑 | 待跑 | 9999 |
| muni-pdf-spr16c | 待跑 | 待跑 | 待跑 | 20602 |
| muni-pdfx-fal17 | 待跑 | 待跑 | 待跑 | 66838 |
| nbi-spr18 | 待跑 | 13721 | 待跑 | 16254 |
| pu-d5-spr17 | 待跑 | 14631 | 待跑 | 15056 |
| pu-d9-fal19 | 待跑 | 待跑 | 待跑 | 26814 |
| pu-llr-spr17 | 待跑 | 3561 | 待跑 | 4894 |
| pu-proj-fal19 | 待跑 | 待跑 | 待跑 | 99713 |
| tg-fal17 | 待跑 | 4215 | 待跑 | 4215 |
| tg-spr18 | 14128 | 14128 | 0 / 0.00% | 12704 |
| yach-fal17 | 待跑 | 314 | 待跑 | 464 |

</details>

<details>
<summary>Stronger LNS + SA</summary>

| instance | method total score | pool best | Phase1B improvement | SOTA no-student |
|---|---:|---:|---:|---:|
| agh-fal17 | 待跑 | 待跑 | 待跑 | 60627 |
| agh-fis-spr17 | 待跑 | 待跑 | 待跑 | 2740 |
| agh-ggis-spr17 | 待跑 | 16514 | 待跑 | 21545 |
| agh-ggos-spr17 | 待跑 | 待跑 | 待跑 | 2730 |
| agh-h-spr17 | 待跑 | 待跑 | 待跑 | 21111 |
| bet-fal17 | 待跑 | 待跑 | 待跑 | 287106 |
| bet-spr18 | 待跑 | 待跑 | 待跑 | 346976 |
| iku-fal17 | 待跑 | 待跑 | 待跑 | 18968 |
| iku-spr18 | 待跑 | 待跑 | 待跑 | 25863 |
| lums-fal17 | 待跑 | 待跑 | 待跑 | 349 |
| lums-spr18 | 待跑 | 95 | 待跑 | 95 |
| mary-fal18 | 待跑 | 1871 | 待跑 | 1991 |
| mary-spr17 | 待跑 | 14473 | 待跑 | 14480 |
| muni-fi-fal17 | 待跑 | 273 | 待跑 | 597 |
| muni-fi-spr16 | 待跑 | 372 | 待跑 | 842 |
| muni-fi-spr17 | 待跑 | 208 | 待跑 | 353 |
| muni-fsps-spr17 | 待跑 | 368 | 待跑 | 368 |
| muni-fsps-spr17c | 待跑 | 10772 | 待跑 | 2594 |
| muni-fspsx-fal17 | 待跑 | 待跑 | 待跑 | 10014 |
| muni-pdf-spr16 | 待跑 | 待跑 | 待跑 | 9999 |
| muni-pdf-spr16c | 待跑 | 待跑 | 待跑 | 20602 |
| muni-pdfx-fal17 | 待跑 | 待跑 | 待跑 | 66838 |
| nbi-spr18 | 待跑 | 13721 | 待跑 | 16254 |
| pu-d5-spr17 | 待跑 | 14631 | 待跑 | 15056 |
| pu-d9-fal19 | 待跑 | 待跑 | 待跑 | 26814 |
| pu-llr-spr17 | 待跑 | 3561 | 待跑 | 4894 |
| pu-proj-fal19 | 待跑 | 待跑 | 待跑 | 99713 |
| tg-fal17 | 待跑 | 4215 | 待跑 | 4215 |
| tg-spr18 | 14128 | 14128 | 0 / 0.00% | 12704 |
| yach-fal17 | 待跑 | 314 | 待跑 | 464 |

</details>

<details>
<summary>Beam Repair</summary>

| instance | method total score | pool best | Phase1B improvement | SOTA no-student |
|---|---:|---:|---:|---:|
| agh-fal17 | 待跑 | 待跑 | 待跑 | 60627 |
| agh-fis-spr17 | 待跑 | 待跑 | 待跑 | 2740 |
| agh-ggis-spr17 | 待跑 | 16514 | 待跑 | 21545 |
| agh-ggos-spr17 | 待跑 | 待跑 | 待跑 | 2730 |
| agh-h-spr17 | 待跑 | 待跑 | 待跑 | 21111 |
| bet-fal17 | 待跑 | 待跑 | 待跑 | 287106 |
| bet-spr18 | 待跑 | 待跑 | 待跑 | 346976 |
| iku-fal17 | 待跑 | 待跑 | 待跑 | 18968 |
| iku-spr18 | 待跑 | 待跑 | 待跑 | 25863 |
| lums-fal17 | 待跑 | 待跑 | 待跑 | 349 |
| lums-spr18 | 待跑 | 95 | 待跑 | 95 |
| mary-fal18 | 待跑 | 1871 | 待跑 | 1991 |
| mary-spr17 | 待跑 | 14473 | 待跑 | 14480 |
| muni-fi-fal17 | 待跑 | 273 | 待跑 | 597 |
| muni-fi-spr16 | 待跑 | 372 | 待跑 | 842 |
| muni-fi-spr17 | 待跑 | 208 | 待跑 | 353 |
| muni-fsps-spr17 | 待跑 | 368 | 待跑 | 368 |
| muni-fsps-spr17c | 待跑 | 10772 | 待跑 | 2594 |
| muni-fspsx-fal17 | 待跑 | 待跑 | 待跑 | 10014 |
| muni-pdf-spr16 | 待跑 | 待跑 | 待跑 | 9999 |
| muni-pdf-spr16c | 待跑 | 待跑 | 待跑 | 20602 |
| muni-pdfx-fal17 | 待跑 | 待跑 | 待跑 | 66838 |
| nbi-spr18 | 待跑 | 13721 | 待跑 | 16254 |
| pu-d5-spr17 | 待跑 | 14631 | 待跑 | 15056 |
| pu-d9-fal19 | 待跑 | 待跑 | 待跑 | 26814 |
| pu-llr-spr17 | 待跑 | 3561 | 待跑 | 4894 |
| pu-proj-fal19 | 待跑 | 待跑 | 待跑 | 99713 |
| tg-fal17 | 待跑 | 4215 | 待跑 | 4215 |
| tg-spr18 | 14128 | 14128 | 0 / 0.00% | 12704 |
| yach-fal17 | 待跑 | 314 | 待跑 | 464 |

</details>

<details>
<summary>Affected Distribution Cache</summary>

| instance | method total score | pool best | Phase1B improvement | SOTA no-student |
|---|---:|---:|---:|---:|
| agh-fal17 | 待跑 | 待跑 | 待跑 | 60627 |
| agh-fis-spr17 | 待跑 | 待跑 | 待跑 | 2740 |
| agh-ggis-spr17 | 待跑 | 16514 | 待跑 | 21545 |
| agh-ggos-spr17 | 待跑 | 待跑 | 待跑 | 2730 |
| agh-h-spr17 | 待跑 | 待跑 | 待跑 | 21111 |
| bet-fal17 | 待跑 | 待跑 | 待跑 | 287106 |
| bet-spr18 | 待跑 | 待跑 | 待跑 | 346976 |
| iku-fal17 | 待跑 | 待跑 | 待跑 | 18968 |
| iku-spr18 | 待跑 | 待跑 | 待跑 | 25863 |
| lums-fal17 | 待跑 | 待跑 | 待跑 | 349 |
| lums-spr18 | 待跑 | 95 | 待跑 | 95 |
| mary-fal18 | 待跑 | 1871 | 待跑 | 1991 |
| mary-spr17 | 待跑 | 14473 | 待跑 | 14480 |
| muni-fi-fal17 | 待跑 | 273 | 待跑 | 597 |
| muni-fi-spr16 | 待跑 | 372 | 待跑 | 842 |
| muni-fi-spr17 | 待跑 | 208 | 待跑 | 353 |
| muni-fsps-spr17 | 待跑 | 368 | 待跑 | 368 |
| muni-fsps-spr17c | 待跑 | 10772 | 待跑 | 2594 |
| muni-fspsx-fal17 | 待跑 | 待跑 | 待跑 | 10014 |
| muni-pdf-spr16 | 待跑 | 待跑 | 待跑 | 9999 |
| muni-pdf-spr16c | 待跑 | 待跑 | 待跑 | 20602 |
| muni-pdfx-fal17 | 待跑 | 待跑 | 待跑 | 66838 |
| nbi-spr18 | 待跑 | 13721 | 待跑 | 16254 |
| pu-d5-spr17 | 待跑 | 14631 | 待跑 | 15056 |
| pu-d9-fal19 | 待跑 | 待跑 | 待跑 | 26814 |
| pu-llr-spr17 | 待跑 | 3561 | 待跑 | 4894 |
| pu-proj-fal19 | 待跑 | 待跑 | 待跑 | 99713 |
| tg-fal17 | 待跑 | 4215 | 待跑 | 4215 |
| tg-spr18 | 14128 | 14128 | 0 / 0.00% | 12704 |
| yach-fal17 | 待跑 | 314 | 待跑 | 464 |

</details>

<details>
<summary>MARL-guided Destroy</summary>

| instance | method total score | pool best | Phase1B improvement | SOTA no-student |
|---|---:|---:|---:|---:|
| agh-fal17 | 待跑 | 待跑 | 待跑 | 60627 |
| agh-fis-spr17 | 待跑 | 待跑 | 待跑 | 2740 |
| agh-ggis-spr17 | 待跑 | 待跑 | 待跑 | 21545 |
| agh-ggos-spr17 | 待跑 | 待跑 | 待跑 | 2730 |
| agh-h-spr17 | 待跑 | 待跑 | 待跑 | 21111 |
| bet-fal17 | 待跑 | 待跑 | 待跑 | 287106 |
| bet-spr18 | 待跑 | 待跑 | 待跑 | 346976 |
| iku-fal17 | 待跑 | 待跑 | 待跑 | 18968 |
| iku-spr18 | 待跑 | 待跑 | 待跑 | 25863 |
| lums-fal17 | 待跑 | 待跑 | 待跑 | 349 |
| lums-spr18 | 待跑 | 待跑 | 待跑 | 95 |
| mary-fal18 | 1871 | 1871 | 0 / 0.00% | 1991 |
| mary-spr17 | 14463 | 14473 | 10 / 0.07% | 14480 |
| muni-fi-fal17 | 273 | 273 | 0 / 0.00% | 597 |
| muni-fi-spr16 | 363 | 363 | 0 / 0.00% | 842 |
| muni-fi-spr17 | 198 | 208 | 10 / 4.81% | 353 |
| muni-fsps-spr17 | 368 | 368 | 0 / 0.00% | 368 |
| muni-fsps-spr17c | 待完成 | 待完成 | 待完成 | 2594 |
| muni-fspsx-fal17 | 待跑 | 待跑 | 待跑 | 10014 |
| muni-pdf-spr16 | 待跑 | 待跑 | 待跑 | 9999 |
| muni-pdf-spr16c | 待跑 | 待跑 | 待跑 | 20602 |
| muni-pdfx-fal17 | 待跑 | 待跑 | 待跑 | 66838 |
| nbi-spr18 | 待跑 | 待跑 | 待跑 | 16254 |
| pu-d5-spr17 | 待跑 | 待跑 | 待跑 | 15056 |
| pu-d9-fal19 | 待跑 | 待跑 | 待跑 | 26814 |
| pu-llr-spr17 | 待跑 | 待跑 | 待跑 | 4894 |
| pu-proj-fal19 | 待跑 | 待跑 | 待跑 | 99713 |
| tg-fal17 | 待跑 | 待跑 | 待跑 | 4215 |
| tg-spr18 | 待跑 | 待跑 | 待跑 | 12704 |
| yach-fal17 | 待跑 | 待跑 | 待跑 | 464 |

</details>

### 6.8 论文中建议保留的 Phase 1B 实验口径

| 内容 | 是否进入论文主表 | 原因 |
|---|---|---|
| MIP pool best | 是 | Phase 1A 给出的直接 baseline |
| Solution-Pool LNS / Direct Repair extended | 是 | 当前唯一完成 available-pool 全实例验证并产生改进的 Phase 1B 方法 |
| Official SOTA no-student | 是 | 外部参考基准 |
| Local Search | 暂不进主表 | 目前只有代表实例验证，缺全实例结果 |
| Full-model LNS attempt | 不进主表 | 主要证明全约束 sparse model 方案成本过高 |
| Tensor Gradient Search | 是，作为独立探索方法 | 已有 15/30 available-pool 结果，`muni-fsps-spr17c` 改进 4.87%，但建模成本高 |
| Validator Delta / Affected Cache / Beam Repair | 不作为独立方法 | 它们是 LNS 内部 scoring、加速和 repair 机制 |
| High-distribution / Mixed destroy | 可作为 LNS 消融 | 若要进论文，需要同预算全实例或代表实例消融 |
| MARL-guided destroy | 部分进入消融讨论 | 已有 6 个完成实例、2 个改进，可说明有一定效果；但仍需完整同预算对比后才能作为强结论 |

### 6.9 当前缺口

| 缺口 | 状态 |
|---|---|
| Local Search 全实例结果 | 待补 |
| Solution-Pool LNS 的 destroy / beam / candidate 参数消融 | 待补 |
| Full-model LNS 中 validator-aware scoring 与 affected cache 的工程对比 | 只保留为实现结论，若进论文需补同预算实验 |
| MARL-guided Destroy 完整批处理 / 同预算消融 | 部分完成 |
| `muni-fi-spr17` 和 `muni-fsps-spr17c` 上的组件贡献拆分 | 待补 |
| 多 seed 稳定性 | 待补 |

## 7. Improvement 来源

当前出现改进的两个实例都有大量 invalid pool members：

| instance | invalid / 98 | 观察 |
|---|---:|---|
| muni-fi-spr17 | 88 | 改进 assignment 主要来自 invalid solution 的局部片段 |
| muni-fsps-spr17c | 79 | invalid pool 提供了低代价 time/room/distribution 局部选择 |

这说明 invalid solution 虽然整体不可用，但可作为局部 assignment fragment library。

## 8. 当前结论

| 结论 | 说明 |
|---|---|
| Phase 1B 可稳定保持 feasibility | 输出均通过本地 validator，部分通过官方 validator |
| 改进集中在 invalid-heavy instances | valid pool 已很强的实例较难继续改 |
| Beam + validator delta + affected cache 是有效工程升级 | 显著降低 scoring 成本 |
| 方法组件已有 smoke / 小参数证据 | 但还缺统一公平消融 |
| SOTA gap 主要集中在少数实例 | `muni-fsps-spr17c` 与 `tg-spr18` 是当前主要短板 |
| 还缺统计严谨性 | 多 seed 和系统消融仍不足 |

## 9. 后续需要补充

| 优先级 | 实验 |
|---|---|
| P0 | 对 available-pool instances 做最终 Phase 1B 统一汇总表 |
| P0 | 针对 `muni-fsps-spr17c` 和 `tg-spr18` 做更强参数或 MIP repair |
| P0 | 补 MARL-guided Destroy 与其他 destroy strategy 的同预算对比 |
| P1 | 多 seed 稳定性实验 |
| P1 | LNS destroy / repair / scoring 消融 |
