# Step 3 验证报告：Local Search

验证日期：2026-04-25

## 1. 验证范围

本报告验证 `PLAN.md` Step 3 的局部搜索实现：

- `src/local_search/neighborhood.py`：single-class / room-swap 邻域生成
- `src/local_search/delta_eval.py`：基于反向索引的局部 delta 评估
- `src/local_search/search.py`：best improvement / first improvement / simulated annealing
- `main.py --method local_search` 集成入口
- 新本地 validator 与官方 validator 对齐后的 cost 口径

本版本不计算 student assignment / student conflict，`student=0`。

## 2. Validator 口径

本轮已修正本地 validator，并与官方接口对齐：

```text
Official endpoint:
https://www.itc2019.org/itc2019-validator

Auth:
HTTP Basic Auth, email/password

Payload:
Content-Type:text/xml;charset=UTF-8
raw solution XML body
```

本地 validator 输出的 `time / room / distribution / student` 为官方同名 raw component penalty。

总分计算为：

```text
total = time * w_time
      + room * w_room
      + distribution * w_distribution
      + student * w_student
```

示例 `tg-spr18` 权重下：

```text
time=1014, room=140, distribution=598, student=0
total=1014*2 + 140*1 + 598*20 = 14128
```

## 3. solutions 全量重测

已重新扫描 `data/solutions` 下 14 个实例，每个实例 98 个 XML 解。

输出文件：

- `output/validation/solutions_validation_summary.csv`
- `output/validation/<instance>_solution_validation.csv`

重测命令使用 `PSTTReader(matrix=False)` + `LocalValidator`，不构建 `ConstraintsResolver`，因此只验证 problem XML 与 solution XML 的官方 cost / hard feasibility。

| instance | solutions | valid | invalid | best valid solution | best valid total | time | room | dist | avg total |
|---|---:|---:|---:|---|---:|---:|---:|---:|---:|
| agh-ggis-spr17 | 98 | 98 | 0 | solution43_agh-ggis-spr17.xml | 16514 | 238 | 322 | 1016 | 18995.020 |
| mary-fal18 | 98 | 98 | 0 | solution41_mary-fal18.xml | 1871 | 229 | 333 | 216 | 1900.041 |
| mary-spr17 | 98 | 98 | 0 | solution1_mary-spr17.xml | 14473 | 793 | 52 | 2567 | 14575.153 |
| muni-fi-fal17 | 98 | 98 | 0 | solution1_muni-fi-fal17.xml | 273 | 22 | 127 | 8 | 330.367 |
| muni-fi-spr16 | 98 | 10 | 88 | solution31_muni-fi-spr16.xml | 372 | 60 | 162 | 3 | 418.235 |
| muni-fi-spr17 | 98 | 10 | 88 | solution21_muni-fi-spr17.xml | 208 | 10 | 108 | 7 | 214.082 |
| muni-fsps-spr17 | 98 | 78 | 20 | solution77_muni-fsps-spr17.xml | 368 | 0 | 68 | 20 | 4381.337 |
| muni-fsps-spr17c | 98 | 19 | 79 | solution91_muni-fsps-spr17c.xml | 10772 | 285 | 1187 | 164 | 13064.888 |
| nbi-spr18 | 98 | 95 | 3 | solution11_nbi-spr18.xml | 13721 | 5300 | 3081 | 5 | 25569.276 |
| pu-d5-spr17 | 98 | 98 | 0 | solution1_pu-d5-spr17.xml | 14631 | 1231 | 90 | 678 | 15212.776 |
| pu-llr-spr17 | 98 | 98 | 0 | solution74_pu-llr-spr17.xml | 3561 | 497 | 1414 | 41 | 3979.449 |
| tg-fal17 | 98 | 98 | 0 | solution11_tg-fal17.xml | 4215 | 1792 | 31 | 30 | 4952.490 |
| tg-spr18 | 98 | 98 | 0 | solution11_tg-spr18.xml | 14128 | 1014 | 140 | 598 | 16073.449 |
| yach-fal17 | 98 | 98 | 0 | solution11_yach-fal17.xml | 314 | 0 | 284 | 3 | 1055.694 |

注意：`muni-fi-spr16`、`muni-fi-spr17`、`muni-fsps-spr17`、`muni-fsps-spr17c`、`nbi-spr18` 中存在本地 hard violation。报告中基线使用 `best valid solution`，不是最低 total 的 invalid XML。后续建议对这些实例抽样提交官方 validator，确认是否是 reduced problem 与 solution pool 不完全匹配，还是本地 hard 检查仍有差异。

## 4. Step 3 正式验证实验

实验实例：`tg-spr18`

初始解池：`data/solutions/tg-spr18` 全部 98 个解

运行配置：

```python
{
    "acceptance": "sa",
    "neighborhood": "single_class",
    "max_iter": 200,
    "sa_temperature": 100.0,
    "sa_cooling": 0.995,
    "seed": 42,
    "log_every": 50,
    "validate": False,
}
```

本地运行结果：

| item | value |
|---|---:|
| model build time | 117.2s |
| pool size | 98 |
| MIP best total | 14128 |
| MIP avg total | 16073.4 |
| MIP worst total | 25098 |
| local search iterations | 200 |
| accepted moves | 27 |
| local search time | 6.15s |
| result feasible | True |
| result total | 14128 |
| improvement vs MIP best | +0.00% |

输出文件：

```text
output/tg-spr18_local_search_sa.xml
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

Step 3 的代码落地与主流程集成验证通过。

关键结论：

- Local Search 可以从 98 个 MIP 解池中选择 corrected MIP best 作为 incumbent。
- 搜索过程保持 hard feasibility，最终 XML 可通过官方 validator。
- 在 `tg-spr18` 的 200 次 SA 短跑中没有超过 MIP best，最终保持 `14128`。
- 原先错误的 `13768` 来自旧 evaluator 少算 distribution penalty；当前本地 total 与官方 total 已对齐。

后续建议：

- 将 `DeltaEvaluator` 的 soft distribution delta 进一步对齐 `LocalValidator` 的官方计数逻辑，否则搜索排序仍可能使用近似 delta。
- 对含 invalid 的 solution pool 实例做官方抽样验证，确认 invalid 来源。
- 在 `agh-ggis-spr17` 上补一次完整 local search 实验，作为 PLAN.md 原定集成测试。
