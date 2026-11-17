# FORMAL-PERF-001 阶段记录

## A1：train内部父链兼容矩阵

- 数据：官方A/B/C `public/train.jsonl`；公开validation读取0。
- 候选：retain、1 epoch原学习率、3 epoch三倍学习率、3 epoch后0.25父候选参数融合。
- 切分：A按类别分层哈希三折；B/C从样本ID提取轴承/发动机轨迹组并按组三折，单组不跨边界。
- A：`e1_lr1`胜出；平均Macro-F1有向增益`+0.004902644`，2/3折不劣，最差相对变化`-0.000598743`。
- B：retain胜出；e1/e3lr3/soup平均RMSE有向增益分别为`-97.34/-298.82/-22.33`，负结果保留，不用复杂方法覆盖证据。
- C：`soup_e3_alpha0.25`胜出；三折RMSE全部改善，平均降低`0.189824503`，最差折相对改善`+0.001375325`。
- 机器结果：`D:/brace-msi-first-principles-performance/FORMAL-PERF-001-A1/summary.json`，SHA-256 `FE5158C0EE76A6179E7641195E9CC394105F0E00AA2389279F81A31787B08968`。

## 集成原则

只有Agent选择train时才运行portfolio。内部证据明确支持的recipe可覆盖参数强度；若只能retain而Agent明确要求train，则保留Agent给定epoch/LR作为唯一候选，随后必须通过官方validation安全门。该设计既保留真实Agent作用，也不让无证据复杂方法自动上线。

## 当前边界

A1不是独立测试或隐藏成绩；B的负结果说明跨设备泛化仍是主要风险。性能版镜像、30轮容器父链和资源门尚待A2完成。
