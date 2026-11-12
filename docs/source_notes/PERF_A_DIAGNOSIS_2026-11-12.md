# PERF-A-001 Gas误差诊断与实验边界

## 数据事实

- 官方A包训练集为Gas Batch 1，共445条；公开验证为Batch 2，共1,244条。
- Batch 1类别数：Ethanol 90、Ethylene 98、Ammonia 83、Acetaldehyde 30、Acetone 70、Toluene 74。
- Batch 2类别数：Ethanol 164、Ethylene 334、Ammonia 100、Acetaldehyde 109、Acetone 532、Toluene 5。
- 官方初始检查点在Batch 1的Macro-F1为0.955754，在Batch 2为0.714030，说明主要问题不是源训练集拟合不足，而是批次漂移及类别不均衡下的迁移失败。

## 可测量瓶颈

Batch 2混淆矩阵显示Acetaldehyde的109条中108条被预测为Ethanol、1条为Toluene，召回和F1均为0；Ethanol、Ethylene、Ammonia、Acetone和Toluene的F1分别约0.684、0.942、0.995、0.996和0.667。标准化特征均值漂移绝对值的中位数约0.465、P90约0.942，存在显著协变量漂移。

因此本轮只验证一个低成本假设：Batch 1的Acetaldehyde样本不足使继续训练仍偏向Ethanol；在不使用Batch 2标签训练的前提下，确定性过采样Acetaldehyde可能恢复该类决策边界并提高Macro-F1。

## 防泄漏与暴露边界

- 原始训练包保持只读；派生JSONL只写入独立运行根。
- Batch 1是唯一训练来源；Batch 2答案不进入训练、预处理或过采样决策。
- 在任何候选指标计算前，按类别和固定哈希冻结Batch 2的70%开发/30%确认子集。
- 公开Batch 2的整体指标和混淆已在历史运行中查看，因此确认子集只能称为“样本级冻结确认”，不能称为真正未见独立测试或隐藏评测。
- 六个候选只按开发子集选择；确认子集最多评估基线和冻结胜者各一次，结果不得反馈调参。

## 成功与停止标准

- 开发Macro-F1相对基线至少提高0.005，且Acetaldehyde F1至少0.05；资源不超预注册上限。
- 满足开发门后才打开确认子集；确认结果无论正负都保留。
- 若没有候选满足开发门，则实验按负结果停止，不打开确认子集，不扩大搜索空间。

配置见`configs/perf_a_oversampling.json`，实验登记见`EXPERIMENTS.md`中的`PERF-A-OVER-001`。
