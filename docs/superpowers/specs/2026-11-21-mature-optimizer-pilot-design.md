# 成熟优化器方法探针规格

## 目标

在不修改冻结 `0.11.0rc1` 和不读取已暴露公开 confirmation 的前提下，将三种成熟、CPU可运行且父 checkpoint 兼容的训练机制作为开发探针，比较它们在 A/B/C 训练内部序贯分段上的指标趋势、最差阶段与 CPU 代价。

## 候选机制

1. `l2sp_parent`：对 `w1/w2` 增加相对本轮父权重的 L2-SP 梯度，偏置不约束。解决续训中的灾难性偏移，不引入新持久状态。
2. `sam_adam`：用第一次梯度产生有界扰动，在扰动点重算梯度，只用第二次梯度更新原有 Adam 状态。不引入新 checkpoint 字段，但预期增加近一倍梯度计算。
3. `adamw`：在原有 Adam 步之后对 `w1/w2` 实施解耦权重衰减，偏置不衰减；沿用父 checkpoint 的 Adam 一、二阶矩。

三种机制首先独立与 `native_current` 及 `native_replay` 比较，不先行组合。Replay 是已实现对照，不声称为新复现。

## 数据与证据边界

- 原始官方包只读；以既有 SHA-256 清单做运行前后校验。
- 只使用 `public/train.jsonl` 内部已定义的类别分层、轴承轨迹和发动机 unit 分组。
- 首轮小测只运行前 3 个相邻阶段；不读取 `public/validation.jsonl`、密封集或官方隐藏标签。
- 开发 Gate 只比较同一作用域内的父模型和候选；完整十轮前不评价 confirmation。
- 不因数据集名称选方法；三任务使用同一候选清单和评价字段。

## 小测矩阵

- 对照：`native_current` 和 `native_replay`。
- L2-SP：`lambda = 1e-4, 1e-3`。
- SAM：`rho = 0.01, 0.05`。
- AdamW：`weight_decay = 1e-5, 1e-4`。
- 全部候选使用同一父 checkpoint、轮次、样本顺序、epoch 和基础学习率；不为单任务设专属参数。

## 晋级规则

不设置伪官方综合分或人为百分比门槛。小测结果以 Pareto 方式报告：三任务平均有向收益、跨任务最差阶段、改善/退化任务数，以及 CPU、墙钟、RSS 和 checkpoint 大小。

只有同时呈现跨任务正向趋势、最差阶段不比现有最强对照差，且实测代价可接受的方法，才进入独立完整十轮任务。小测本身不修改正式 RecipeRegistry、不构建新正式镜像。

## 文献来源

- Li et al., *Explicit Inductive Bias for Transfer Learning with Convolutional Networks*, ICML 2018: <https://proceedings.mlr.press/v80/li18a.html>
- Foret et al., *Sharpness-Aware Minimization for Efficiently Improving Generalization*, ICLR 2021: <https://openreview.net/forum?id=6Tm1mposlrM>
- Loshchilov and Hutter, *Decoupled Weight Decay Regularization*, ICLR 2019: <https://openreview.net/forum?id=Bkg6RiCqY7>

