# BRACE-MSI论文融合性能冲刺设计

## 1. 目标与边界

在不修改`BRACE-MSI-0.3.0rc3`标签、A3 Sampler、历史实验和官方原始训练包的前提下，建立独立研究候选，将高质量开源研究中的可验证核心机制接入BRACE的预算、安全、审计与回滚边界。当天必须产生A/B/C真实本地实验结果和可运行候选；30%相对改善是进取目标，不是通过伪造、验证集过拟合或隐藏测试换取的验收门。

相对官方静态基线的冲刺目标为：A Macro-F1不低于0.928239；B RMSE不高于476.811883；C RMSE不高于37.008001。所有结果必须同时报告相对静态基线和相对RC3候选的变化。

## 2. 论文与代码上限

本轮最多纳入三项方法来源：

1. Gas半监督知识蒸馏：Lin与Zhan的传感器漂移补偿方法及MIT复现仓库。只复现教师软目标、温度蒸馏和源域保持机制；原仓库“全批次拟合标准化器”的做法不得进入因果实验。
2. RUL可解释树模型集成：Özcan的C-MAPSS LightGBM/CatBoost/Gradient Boosting集成研究及公开仓库。当前依赖栈先使用scikit-learn HistGradientBoosting与ExtraTrees复现其互补集成思想，避免新增重依赖。
3. Hyperband/Successive Halving：Li等人的预算自适应资源分配方法。只实现有限候选的逐级预算淘汰，不实现BOHB或无界HPO。

PROCEED、Type-LDA、TaFCN、深度域对抗网络和GPU时序网络本轮不进入实现：它们与当前监督分类/回归接口不直接匹配、依赖过重或许可证/CPU部署边界尚未通过。

## 3. 架构

新增`PaperFusionRunner`，保持RC3主Harness不变：

```text
只读官方train
  -> TaskFeatureAdapter（原始输入 + 仅历史可得的meta/趋势特征）
  -> GroupedInternalCV（按batch/bearing/unit隔离）
  -> TeacherPool（HistGradientBoosting + ExtraTrees + 任务适配线性/MLP）
  -> SuccessiveHalvingSelector（小预算淘汰，完整预算复核）
  -> OOFWeightedEnsemble
  -> 可选CompactStudentDistillation
  -> PaperFusionSafetyGate
  -> 冻结候选
  -> 一次公开validation暴露评估
```

任务适配允许不同特征与模型配置，但不绕过共享预算、分组切分、指标方向、安全门和审计。

### 3.1 Gas

- 原始128维输入；标签分层内部切分，不使用公开validation标签选型。
- 教师池输出类别概率；按内部组外Macro-F1加权集成。
- 学生同时拟合真实硬标签和教师软概率；温度、硬/软损失比例只取固定小集合。
- 类别权重和每类F1进入安全门；任何单类崩溃候选拒绝。

### 3.2 Bearing

- 原始34维特征；增加当前可知`snapshot`及其因果变换，不使用轨迹总长度或未来快照。
- 按整根bearing做分组交叉验证。
- HistGradientBoosting、ExtraTrees、Ridge/MLP形成回归教师池；组外RMSE反比加权。
- 允许非负裁剪和仅基于训练组拟合的轻量校准；禁止使用确认轴承寿命拟合特征。

### 3.3 Engine

- 原始3个settings与21个sensors；增加当前`cycle`和只使用同一unit过去观测的滚动均值、差分和趋势。
- 按整台unit分组，保留source_subset分布。
- 使用与Bearing相同的CPU教师池和组外集成；同时报告RMSE、MAE和NASA非对称分。

## 4. 数据与评估

- 官方原始包只读，派生数据和模型全部写入`D:/brace-msi-paper-fusion/PAPER-FUSION-SPRINT-001/`。
- 模型和融合权重仅由官方`public/train.jsonl`内部切分决定。
- 官方`public/validation.jsonl`历史暴露，只允许在最终配置冻结后评估一次；不得反馈修改候选。
- Gas按确定性分层折；Bearing按bearing；Engine按unit与subset分组。任何身份交叉立即停止。
- 每个方法保留内部CV、资源、失败和最终公开validation结果；负结果不删除。

## 5. 预算与停止条件

- 每任务最多12个教师配置；第一阶段使用低预算，最多保留4个进入完整预算。
- 单任务CPU不超过3600秒、墙钟不超过1800秒、峰值RSS小于4GiB；总镜像仍必须小于2GB。
- 若一个模型族在内部CV上不优于当前官方MLP基线或产生非有限指标，立即淘汰。
- 公开validation打开后配置冻结；无论结果好坏均不得在同一实验ID重跑选型。
- 若自定义模型正式接口尚未确认，研究候选保留两种部署声明：`native_teacher`为待平台确认，`compact_student`为固定轻量回退。不得声称未知平台已支持自定义pickle模型。

## 6. 成功标准

最低交付不是30%数字，而是：

1. 三项论文/代码/许可证/兼容性审计完成；
2. 至少一项论文核心方法完成真实复现，正负均保留；
3. A/B/C均产生内部组外和一次公开validation结果；
4. 新候选在至少一个任务显著优于RC3，其他任务不被强制包装；
5. 有静态、简单续训、RC3、单模块及融合候选的公平表；
6. 可运行代码、测试、配置、资源收据、消融和失败分析齐全。

若达到30%则如实报告；未达到则报告真实幅度和最主要瓶颈。
