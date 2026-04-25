# Phase 2 验证报告：LNS Baseline

验证日期：2026-04-25

## 1. 验证范围

本报告验证 Phase 2 的 LNS baseline：

- `src/lns/search.py`：destroy-and-repair large neighborhood search
- `src/lns/__init__.py`：package export
- `main.py --method lns` 集成入口
- `config.yaml` 中 `lns` 配置
- 本地 validator 与官方 validator 对齐后的 LNS 输出验证

当前 LNS 不调用 Gurobi / CP-SAT，而是实现一个可运行的 baseline：

```text
1. 从 incumbent 中移除 K 个 class，支持 random / high_distribution / mixed
2. 保留其余 assignment
3. 对移除 class 按 domain size 排序
4. 用官方口径 total delta-aware scoring 做 greedy 或 beam 修复
5. 保持 hard feasibility
6. improvement 或 SA 接受
```

## 2. Validator 口径

本轮使用 `src/solution_io/local_validator.py` 作为本地验证器，component penalty 与官方 validator 对齐：

```text
time / room / distribution / student = raw component penalty
total = weighted sum
```

官方接口：

```text
curl -u email:password \
     -H "Content-Type:text/xml;charset=UTF-8" \
     -d @solution.xml \
     https://www.itc2019.org/itc2019-validator
```

账号密码未写入代码，运行时通过 `ITC2019_EMAIL` / `ITC2019_PASSWORD` 环境变量传入。

## 3. solutions 全量重测基线

Phase 2 的比较基线使用重新验证后的 `best valid solution`。

CSV 输出：

- `output/validation/solutions_validation_summary.csv`
- `output/validation/<instance>_solution_validation.csv`

| instance | valid / 98 | best valid solution | best valid total | time | room | dist |
|---|---:|---|---:|---:|---:|---:|
| agh-ggis-spr17 | 98 | solution43_agh-ggis-spr17.xml | 16514 | 238 | 322 | 1016 |
| mary-fal18 | 98 | solution41_mary-fal18.xml | 1871 | 229 | 333 | 216 |
| mary-spr17 | 98 | solution1_mary-spr17.xml | 14473 | 793 | 52 | 2567 |
| muni-fi-fal17 | 98 | solution1_muni-fi-fal17.xml | 273 | 22 | 127 | 8 |
| muni-fi-spr16 | 10 | solution31_muni-fi-spr16.xml | 372 | 60 | 162 | 3 |
| muni-fi-spr17 | 10 | solution21_muni-fi-spr17.xml | 208 | 10 | 108 | 7 |
| muni-fsps-spr17 | 78 | solution77_muni-fsps-spr17.xml | 368 | 0 | 68 | 20 |
| muni-fsps-spr17c | 19 | solution91_muni-fsps-spr17c.xml | 10772 | 285 | 1187 | 164 |
| nbi-spr18 | 95 | solution11_nbi-spr18.xml | 13721 | 5300 | 3081 | 5 |
| pu-d5-spr17 | 98 | solution1_pu-d5-spr17.xml | 14631 | 1231 | 90 | 678 |
| pu-llr-spr17 | 98 | solution74_pu-llr-spr17.xml | 3561 | 497 | 1414 | 41 |
| tg-fal17 | 98 | solution11_tg-fal17.xml | 4215 | 1792 | 31 | 30 |
| tg-spr18 | 98 | solution11_tg-spr18.xml | 14128 | 1014 | 140 | 598 |
| yach-fal17 | 98 | solution11_yach-fal17.xml | 314 | 0 | 284 | 3 |

## 4. Phase 2 LNS 主流程验证

实验实例：`tg-spr18`

运行入口：

```powershell
python -B main.py --method lns --instance tg-spr18 --device cpu
```

LNS 配置：

```yaml
lns:
  max_iter: 500
  destroy_size: 8
  destroy_strategy: mixed
  mixed_high_distribution_prob: 0.7
  repair_method: beam
  beam_width: 3
  repair_scoring: validator_delta
  repair_candidate_limit: 40
  acceptance: improvement
  temperature: 100.0
  cooling: 0.995
  seed: 42
```

运行结果：

| item | value |
|---|---:|
| pool size | 98 |
| corrected MIP best total | 14128 |
| LNS iterations | 500 |
| feasible repairs | 492 |
| accepted improvements | 0 |
| result feasible | True |
| result total | 14128 |
| improvement vs MIP best | +0.00% |

输出文件：

```text
output/tg-spr18_lns.xml
```

本地 validator：

| valid | total | time | room | distribution | student |
|---|---:|---:|---:|---:|---:|
| True | 14128 | 1014 | 140 | 598 | 0 |

官方 validator：

| valid | total | time | room | distribution | student |
|---|---:|---:|---:|---:|---:|
| valid | 14128 | 1014 | 140 | 598 | 0 |

## 5. 结论

Phase 2 LNS baseline 已完成可运行闭环：

- `method: lns` 主流程可构建模型、加载 98 个解、执行 destroy-repair、保存 XML。
- LNS 输出通过本地 validator 与官方 validator。
- 在 `tg-spr18` 上 500 次迭代没有超过 corrected MIP best，但保持了 best incumbent。
- 当前 LNS 是 solver-free baseline，适合作为后续 Gurobi / CP-SAT fix-and-optimize 的接入骨架。

主要风险：

- Repair 排序当前只使用 time+room local score，没有使用官方 distribution delta。
- 对 distribution-heavy 实例，LNS 可能频繁修复成功但无法改进 total。
- 部分 `data/solutions` 实例在本地 validator 下存在 hard violation，需要官方抽样确认。

下一步建议：

- 将 repair candidate scoring 改为 `time + room + affected distribution delta`。
- 增加 destroy 策略：按 high distribution penalty classes、same-room conflict neighborhood、soft constraint classes 分组 destroy。
- 接入 CP-SAT 或 Gurobi 子问题，把 destroy set 内的 class 重新优化，而不是纯贪心修复。

## 6. 小参数对比实验

实验日期：2026-04-25

实验实例：`tg-spr18`

基线：

```text
corrected MIP best total = 14128
time = 1014
room = 140
distribution = 598
```

输出 CSV：

```text
output/experiments/lns_parameter_compare_tg-spr18.csv
```

实验矩阵：

| name | max_iter | destroy_size | destroy_strategy | repair_scoring | candidate_limit | seconds | repairs | accepted | total | improvement |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|
| random_local | 80 | 5 | random | local | 0 | 14.517 | 79 | 0 | 14128 | 0.00% |
| random_delta | 40 | 5 | random | validator_delta | 8 | 29.846 | 15 | 0 | 14128 | 0.00% |
| high_distribution_delta | 40 | 5 | high_distribution | validator_delta | 8 | 21.961 | 8 | 0 | 14128 | 0.00% |
| mixed_delta | 40 | 5 | mixed | validator_delta | 8 | 30.265 | 13 | 0 | 14128 | 0.00% |

Destroy 统计：

| name | random | high_distribution | fallback |
|---|---:|---:|---:|
| random_local | 80 | 0 | 0 |
| random_delta | 40 | 0 | 0 |
| high_distribution_delta | 0 | 40 | 0 |
| mixed_delta | 14 | 26 | 0 |

结论：

- 四组均保持 hard-feasible，但没有超过 corrected MIP best。
- `validator_delta` repair 更贴近官方目标，但在 `destroy_size=5`、`candidate_limit=8` 的小参数下修复成功次数明显下降。
- `high_distribution` 确实命中 soft violation class，不发生 fallback，但局部破坏规模可能太小，repair 很容易回到原 incumbent。
- 下一轮更值得尝试 `acceptance=sa`、`destroy_size=10~15`、`candidate_limit=12~20`，让搜索有能力穿过短期变差的中间状态。

## 7. 稍强参数实验

实验日期：2026-04-25

实验实例：`tg-spr18`

配置：

```yaml
name: mixed_delta_sa_stronger
max_iter: 100
destroy_size: 10
destroy_strategy: mixed
mixed_high_distribution_prob: 0.7
repair_scoring: validator_delta
repair_candidate_limit: 16
acceptance: sa
temperature: 80.0
cooling: 0.985
seed: 202
```

输出：

```text
output/experiments/lns_stronger_tg-spr18.csv
output/tg-spr18_lns_mixed_delta_sa_stronger.xml
```

结果：

| item | value |
|---|---:|
| seconds | 174.081 |
| feasible repairs | 21 |
| accepted moves | 9 |
| destroy random | 30 |
| destroy high_distribution | 70 |
| destroy fallback | 0 |
| final feasible | True |
| final total | 14128 |
| time | 1014 |
| room | 140 |
| distribution | 598 |
| improvement vs corrected MIP best | 0.00% |

官方 validator：

| valid | total | time | room | distribution | student |
|---|---:|---:|---:|---:|---:|
| valid | 14128 | 1014 | 140 | 598 | 0 |

结论：

- SA 接受了 9 个中间解，说明搜索已经能穿越局部平台。
- 但最佳解仍回到 corrected MIP best `14128`，未找到改进。
- 修复成功率只有 21%，说明 `destroy_size=10` + `candidate_limit=16` 已经比较激进，继续扩大 destroy 可能需要更强 repair，例如 beam repair 或 CP-SAT/Gurobi 子问题。

## 8. Beam Repair Smoke Test

实验日期：2026-04-25

目的：验证 greedy repair 升级为 beam repair 后是否能保持可行闭环。

配置：

```yaml
max_iter: 10
destroy_size: 5
destroy_strategy: mixed
mixed_high_distribution_prob: 0.7
repair_method: beam
beam_width: 2
repair_scoring: validator_delta
repair_candidate_limit: 6
acceptance: sa
temperature: 50.0
cooling: 0.98
seed: 303
```

结果：

| item | value |
|---|---:|
| seconds | 56.71 |
| feasible repairs | 2 |
| accepted moves | 1 |
| destroy random | 4 |
| destroy high_distribution | 6 |
| destroy fallback | 0 |
| final feasible | True |
| final total | 14128 |
| time | 1014 |
| room | 140 |
| distribution | 598 |

结论：

- Beam repair 功能闭环通过，输出保持 hard-feasible。
- 当前实现每个 beam branch 重新构建 tracker 并调用完整官方口径 evaluator，速度较慢。
- 在扩大 beam_width / candidate_limit / max_iter 前，需要做 evaluator 缓存或 affected-distribution incremental scoring。

## 9. Affected-Distribution Incremental Scoring / Cache

实验日期：2026-04-25

实现内容：

- `src/lns/search.py` 新增 affected-distribution scorer。
- repair candidate 不再对每个候选完整调用 `SolutionEvaluator.evaluate()`。
- 候选评分改为：

```text
score = weighted(time_penalty + room_penalty)
      + weighted(affected soft distribution cost)
```

- affected rows 由 `cid -> soft distribution rows` 反向索引得到。
- soft distribution row cost 使用 `LocalValidator._constraint_violation_count()` 的官方对齐逻辑。
- 增加 `_affected_score_cache`，以 `(constraint_row, relevant assigned classes)` 缓存 affected soft cost。
- beam branch 使用轻量 tracker copy，不再每次从 `x_tensor` 重建 tracker。
- 最终输出仍使用完整 `SolutionEvaluator.evaluate()` 和官方 validator 验证。

同配置 smoke test 对比：

| version | max_iter | destroy_size | beam_width | candidate_limit | seconds | repairs | accepted | total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| full-evaluate beam | 10 | 5 | 2 | 6 | 56.71 | 2 | 1 | 14128 |
| affected-cache beam | 10 | 5 | 2 | 6 | 8.29 | 1 | 1 | 14128 |

官方 validator：

| valid | total | time | room | distribution | student |
|---|---:|---:|---:|---:|---:|
| valid | 14128 | 1014 | 140 | 598 | 0 |

结论：

- affected-cache scoring 将 beam smoke test 的 LNS 阶段耗时从 `56.71s` 降到 `8.29s`。
- 输出仍保持 hard-feasible，并通过官方 validator。
- repair 成功次数略有变化，因为 beam 排序分数从完整 partial total 改为 affected heuristic，但最终完整验证不受影响。
