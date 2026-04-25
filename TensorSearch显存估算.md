# Tensor Search 内存/显存估算

估算对象是当前 `src/tensor_search` + `ConstraintsResolver_v2` 路径：先构建 x 变量、valid/hard/soft sparse tensors，再创建 logits、gradient、Adam state 和 soft assignment。单位为 GiB，可近似理解为 G。

更新说明：下面表格是“常驻张量 + 粗略峰值”的静态估算，不包含 CUDA `torch.sparse.mm(hard_dist_tensor, x_soft)` 在反向传播中的额外 workspace。`muni-fsps-spr17c` 的真实运行已经证明，旧的 full hard surrogate 会显著超过这个估算。

## 口径

- `steady`: 训练中张量常驻显存/内存估算。
- `peak`: `steady × 1.6`，考虑 sparse 构建临时张量、autograd 临时量和 allocator 碎片。
- `recommended`: `steady × 2.0`，原始建议显存余量。对于 full hard sparse surrogate，大实例应额外保留 sparse.mm workspace。
- `as-is CPU risk`: 当前 `ConstraintsResolver_v2` 构建 room-capacity 时 Python dict/list/cache 的粗略 CPU 额外开销估计，不是 GPU 显存；大实例会先卡在这里。

## 真实 OOM 观测

`muni-fsps-spr17c` 在 24 GiB GPU 上构建模型成功，但旧版 tensor search 在第一步 full hard sparse surrogate 处 OOM：

- 模型构建后进程已占用约 `21.01 GiB`。
- `torch.sparse.mm(hard_dist_tensor, x_soft)` 额外申请 `5.03 GiB`。
- 因此旧模式最低峰值已经超过 `26.04 GiB`，考虑碎片和 allocator reserve 后应按 `32 GiB+` 看。

当前默认配置已改为 `hard_surrogate: none`、`hard_weight: 0.0`：连续松弛不再做完整 hard sparse.mm，硬约束由离散 probe 后的 official-aligned local validator 保证。这样 24 GiB 上有机会继续跑 `muni-fsps-spr17c`，但模型常驻仍接近 21 GiB，建议设置 `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` 并清空其他 GPU 进程。

## 结果表

| instance | x vars | room pairs | steady G | peak G | recommended G | as-is CPU risk G |
|---|---:|---:|---:|---:|---:|---:|
| agh-ggis-spr17 | 261,873 | 18,334,330 | 1.06 | 1.70 | 2.12 | 6.0 |
| lums-spr18 | 379,909 | 264,945,292 | 11.39 | 18.23 | 22.79 | 86.4 |
| mary-fal18 | 181,332 | 37,591,748 | 1.61 | 2.57 | 3.22 | 12.3 |
| mary-spr17 | 166,311 | 32,813,368 | 1.41 | 2.26 | 2.83 | 10.7 |
| muni-fi-fal17 | 40,142 | 2,046,246 | 0.11 | 0.17 | 0.21 | 0.7 |
| muni-fi-spr16 | 39,279 | 2,229,784 | 0.11 | 0.18 | 0.23 | 0.7 |
| muni-fi-spr17 | 49,088 | 3,415,992 | 0.17 | 0.28 | 0.35 | 1.1 |
| muni-fsps-spr17 | 29,259 | 1,112,930 | 0.07 | 0.11 | 0.13 | 0.4 |
| muni-fsps-spr17c | 353,629 | 149,730,796 | 6.99 | 11.19 | 13.99 | 48.8 |
| nbi-spr18 | 140,708 | 17,710,364 | 0.80 | 1.28 | 1.60 | 5.8 |
| pu-d5-spr17 | 74,375 | 3,870,048 | 0.21 | 0.34 | 0.42 | 1.3 |
| pu-llr-spr17 | 174,671 | 16,843,504 | 0.78 | 1.25 | 1.56 | 5.5 |
| tg-fal17 | 53,838 | 1,055,589 | 0.09 | 0.15 | 0.18 | 0.3 |
| tg-spr18 | 45,597 | 818,674 | 0.17 | 0.27 | 0.33 | 0.3 |
| yach-fal17 | 88,707 | 15,792,975 | 0.75 | 1.20 | 1.50 | 5.1 |

## 结论

- 显存压力主要来自 room-capacity hard sparse tensor，而不是梯度 logits 本身。
- `lums-spr18` 和 `muni-fsps-spr17c` 是高风险实例；旧的 full hard sparse surrogate 对 `muni-fsps-spr17c` 至少需要 26G+ 峰值，实际建议 32G+。
- 小实例如 `muni-*`, `pu-d5`, `tg-*` 的张量显存需求很低，通常 1G 内足够；但构建时间仍可能受约束生成影响。
- 如果要真正大规模跑 tensor search，下一步应重写 room-capacity 构建为 streaming COO，或不要在 GPU 上显式展开所有 room conflict pairs，把硬约束保持在 validator / incremental cache 路径。

CSV 明细：`output/analysis/tensor_search_memory_estimate.csv`
