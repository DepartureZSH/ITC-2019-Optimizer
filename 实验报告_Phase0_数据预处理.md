# Phase 0 实验报告：Reduced Dataset 来源与说明

## 1. 阶段目标

Phase 0 的目标不是在本项目中重新实现 data reduction，而是说明本项目所使用的 `reduced data XML` 的来源、依据和后续使用方式。

本项目中的 reduced XML 直接采用 ITC2019 SOTA / 1st place 团队提供的 reduced datasets，而不是由本项目从 raw XML 重新生成。

整体位置：

```text
ITC2019 raw data XML
 -> SOTA/DTU reduced data XML
 -> Phase 1 MIP class assignment
```

## 2. 数据来源

Reduced data 的来源为 Dennis S. Holm 等人在 ITC2019 相关工作中提供的数据集与论文说明。

| 项目 | 内容 |
|---|---|
| 论文 | `Data Reductions for the International Timetabling Competition 2019 Problem` |
| 作者 | Dennis S. Holm |
| 单位 | Technical University of Denmark |
| DOI | `10.11581/DTU.00000241` |
| reduced dataset DOI | `10.11583/DTU.20014070` |
| competition reduced dataset DOI | `10.11583/DTU.20014127` |
| 本地 PDF | `E:/Desktop/FYP/reduced/Data_Reductions_for_the_International_Timetabling_Competition_2019_Problem.pdf` |

同时，1st place / SOTA 团队为：

```text
Dennis S. Holm,
Rasmus Ørnstrup Mikkelsen,
Matias Sørensen,
Thomas R. Stidsen
MaCom / Technical University of Denmark, Denmark
```

该团队提供了 ITC2019 late instances 的 best solutions，其中包含 nine late instances 的 best solutions，除 `agh-fal17` 外均覆盖。

## 3. 输入与输出

| 项目 | 内容 |
|---|---|
| 上游输入 | ITC2019 原始 problem XML |
| 本项目实际输入 | SOTA/DTU 提供的 reduced problem XML |
| 本项目路径 | `data/reduced/<instance>.xml` |
| 当前数量 | `data/reduced/` 下约 30 个 instances |
| 后续用途 | Phase 1 class assignment MIP、solution validator、student assignment |

## 4. Reduction 方法摘要

根据论文说明，reduction 的核心思想是从 raw data 中识别冗余，减少 MIP 建模规模。

主要包括：

| Reduction 内容 | 说明 |
|---|---|
| available times reduction | 移除被约束隐含排除的 class time options |
| available rooms reduction | 移除被约束隐含排除的 class room options |
| conflict graph reduction | 使用 class-time、class-room、class-time-room conflict graph |
| clique / SAT-style reduction | 利用 set equality clique 和 probing 思路减少变量 |
| redundant distribution constraints removal | 删除冗余 distribution constraints |

论文指出 reduced datasets 可用于所有求解策略，不仅限于 MIP，因为 reduction 发生在建模之前。

## 5. Reduced XML 保留内容

Reduced XML 仍保留 ITC2019 problem 的核心结构，但可选 time/room/domain 和部分 redundant constraints 已被上游 reduction 处理：

| 模块 | 是否保留 | 用途 |
|---|---|---|
| rooms | 保留 | room capacity、unavailable、travel time |
| courses/configs/subparts/classes | 保留 | class assignment 和 student assignment |
| class time options | 保留 | Phase 1 决定 class time |
| class room options | 保留 | Phase 1 决定 class room |
| distributions | 保留 | hard feasibility 和 distribution penalty |
| students | 保留 | Phase 2 student assignment |
| optimization weights | 保留 | time、room、distribution、student weighted total |

## 6. 当前完成状态

| 项目 | 状态 | 说明 |
|---|---|---|
| reduced XML 文件准备 | 已完成 | 使用 SOTA/DTU 提供的 reduced datasets，`data/reduced/` 已包含约 30 个 instances |
| reduction 算法复现 | 不在本项目范围 | 本项目引用并使用上游 reduced XML，不重新实现 reduction |
| reader 解析 | 已完成 | `src/utils/dataReader.py` 可解析 reduced problem XML |
| matrix=false 轻量解析 | 已完成 | validator 和 student assignment 可不构建 dense timetable |
| reduced XML 与 solution XML 对齐检查 | 部分完成 | 已对当前约 15 个有 solution pool 的实例做 validation |

## 7. 已知风险

部分 instances 的已有 solution pool 在本地 validator 下出现 hard violation。可能原因包括：

| 可能原因 | 说明 |
|---|---|
| reduced XML 与 solution pool 不完全匹配 | solution 可能来自不同 preprocessing 版本 |
| solution XML 中存在 class assignment 无法匹配 reduced domain | 特别是部分 invalid-heavy 实例 |
| 本地 validator 仍有边界差异 | 已与官方 validator 多次对齐，但仍建议最终抽样确认 |

## 8. 后续需要补充

| 优先级 | 待补充内容 |
|---|---|
| P0 | 为 30 个 reduced XML 生成实例规模统计表 |
| P0 | 记录每个 instance 的 classes、rooms、students、distributions、candidate variables、constraint pairs |
| P1 | 对剩余无 MIP pool 的大实例做 reduced XML 与建模规模分析 |

## 9. 论文写作建议

论文中 Phase 0 应表述为：

```text
We use the reduced ITC2019 datasets released by the first-place/SOTA team from MaCom and the Technical University of Denmark. These reduced instances were generated using conflict-graph and redundancy-removal techniques described by Holm (2022), rather than being regenerated in this project.
```

因此，本项目贡献从 Phase 1 class assignment solution pool 的利用与后优化开始，而不是 data reduction algorithm 本身。
