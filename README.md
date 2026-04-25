# 📘 ITC2019 项目介绍

## 1. 项目背景

**International Timetabling Competition 2019 (ITC2019)** 是一个面向真实大学排课问题的国际竞赛，目标是解决复杂的课程安排问题，包括：

* 时间分配（Time Assignment）
* 教室分配（Room Assignment）
* 学生选课冲突（Student Sectioning）

该问题来源于真实大学系统（如 UniTime），具有高度现实复杂性和多目标优化特征 。

---

## 2. 数据格式（Data Format）

ITC2019 使用 **XML 格式**描述排课问题（详见官网 format）。

详细Data Format见同目录下的Dataset.md

### 2.1 核心结构

#### （1）Course Structure（课程结构）

```
Course
 ├── Configuration
 │    ├── Subpart (Lecture / Lab / Tutorial)
 │    │     └── Class
```

特点：

* 一个课程可以有多个 configuration（不同选课路径）
* 每个 configuration 包含多个 subpart（如 lecture + lab）
* 每个 subpart 包含多个 class（具体上课实例）
* 存在 **父子关系（parent-child）**（如 lecture → tutorial）

👉 学生必须选：

* 每个 subpart **恰好一个 class**
* 且满足 parent-child 约束

---

#### （2）Time（时间）

时间由以下属性定义：

* `days`（星期）
* `start`（开始时间）
* `length`（持续时间）
* `weeks`（周）

特点：

* 时间粒度为 **5分钟 slot**
* 支持：

  * 跨天
  * 跨周
  * 不规则时间（如单双周）

---

#### （3）Room（教室）

每个教室包含：

* 容量（capacity）
* 不可用时间（unavailability）
* 与其他教室的距离（travel time）

👉 travel time 会影响学生是否能赶上下一节课

---

#### （4）Class Assignment（决策变量）

每个 class 需要决定：

```
(class) → (time, room)
```

---

#### （5）Student（学生）

* 学生选课程（course）
* 通过 course structure 被分配到 class

---

#### （6）Distribution Constraints（分布约束）

约束定义在 class 集合上，包括：

##### 常见约束类型：

| 类型            | 含义     |
| ------------- | ------ |
| NotOverlap    | 不能时间冲突 |
| SameDays      | 同一天    |
| SameRoom      | 同教室    |
| SameAttendees | 同学生需可达 |
| MinGap(G)     | 间隔至少 G |
| MaxDays       | 最大天数   |
| MaxBlock      | 连续上课限制 |

👉 一部分是：

* **Hard constraint（必须满足）**
* **Soft constraint（违反有惩罚）**

---

## 3. 项目目标（Objective / Cost）

ITC2019 是一个 **多目标最小化问题**。

### 总 Cost：

[
\text{Total Cost} =
\text{Time Penalty}

* \text{Room Penalty}
* \text{Distribution Penalty}
* \text{Student Conflict Penalty}
  ]

---

### 3.1 Time Penalty（时间偏好）

* 每个 class 的 time 有 penalty
* 例如：

  * 早上不好 → penalty 高
  * preferred slot → penalty 低

---

### 3.2 Room Penalty（教室偏好）

* 不同教室质量不同
* 可能包括：

  * 容量匹配
  * 设备
  * 距离

---

### 3.3 Distribution Penalty（软约束）

违反 soft constraint 的惩罚：

例如：

* 两门课应该同一天但没做到
* 两节课间隔太短

👉 通常是 **pair-wise 或 group-wise penalty**

---

### 3.4 Student Conflict（最重要）

学生冲突包括：

1. **时间冲突**
2. **不可达冲突（travel time 不够）**

👉 定义：

如果学生无法参加两门课 → 产生 penalty

👉 这是 ITC2019 的核心难点之一 

---

### 3.5 权重（Weights）

不同实例权重不同，例如：

| 项目           | 权重    |
| ------------ | ----- |
| Time         | 3     |
| Room         | 1     |
| Distribution | 10–30 |
| Student      | 5–100 |

👉 不同学校侧重点不同 

---

## 4. 关键难点

### 4.1 三层耦合问题

* 时间分配
* 教室分配
* 学生分配

👉 三者强耦合（NP-hard）

---

### 4.2 巨大搜索空间

* 每个 class：

  * 多个 time × 多个 room
* 实例规模：

  * up to 9000 classes 

---

### 4.3 复杂约束

* 19种 constraint 类型
* 部分是 global constraint（如 MaxBlock）

---

### 4.4 不规则时间结构

* 不同周不同课
* 非固定周期（非常难）

---

## 5. FAQ & 注意事项（基于官方 FAQ）

### 5.1 一定要保证 Hard Constraint 满足

否则：

❌ 解直接无效

---

### 5.2 Student Conflict 不能忽略

* 即使无学生数据，也可能通过：

  * NotOverlap / SameAttendees 表达

---

### 5.3 Travel Time 很重要

* 两个课：

  * 不冲突 ≠ 可参加
* 还需考虑：

  * room distance

---

### 5.4 Class 不一定需要 room

* 部分 class：

  * online / no-room

---

### 5.5 时间是多维的

不要只用：

```
timeslot index
```

而是：

```
(days, start, length, weeks)
```

---

### 5.6 Distribution Constraint 可能爆炸

* pair 数量巨大（几十万级）

👉 实践建议：

* 不要 naive pair 建模
* 用：

  * graph
  * lazy constraint
  * clique reduction

---

### 5.7 数据中存在冗余

论文指出：

👉 可以做 preprocessing（reduction）
👉 可显著降低规模

本项目已做好reduction：data/reduced

---

## 6. 适合的求解方法

根据 SOTA：

### 方法分类：

| 方法                 | 代表                        |
| ------------------ | ------------------------- |
| MIP / Matheuristic | Gurobi + Fix-and-optimize |
| Metaheuristic      | SA / Tabu                 |
| CP / Hybrid        | UniTime                   |
| MaxSAT             | Boolean encoding          |

---

## 8. 总结

ITC2019 是一个：

> **高度复杂、强约束、多目标的真实世界组合优化问题**

核心挑战在于：

* 多维决策（time + room + student）
* 强耦合约束
* 巨大规模