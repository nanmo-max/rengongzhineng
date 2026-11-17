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

只有Agent选择train时才运行portfolio。内部证据明确支持的recipe才可形成候选；若三折证据只能retain，则安全核否决Agent训练提案并记录原因，不生成候选。Agent决定是否发起实验，确定性核决定实验是否有足够证据执行，官方validation再决定是否部署。

## A2：过渡探针（已淘汰）

`0.10.1`在B的训练内证据选择retain时仍执行Agent的1 epoch建议，违反“确定性安全核不能被建议覆盖”的集成原则。该问题由回归测试捕获并修复；A2与其公开validation诊断全部保留为负证据，不得上传或作为最终性能结论。

## A3：精确正式候选验收

- 镜像：`brace-msi:0.10.2rc1`，ID `sha256:d216a379e26f64d37a90ef54f629739bb2e4c9d649214252a57377e7fb1001a9`。
- A/B/C均完成10轮，合计30个唯一宿主模型调用；每任务独立预测5行。
- A：第1轮部署`e1_lr1`，后9轮候选未超过父模型并拒绝；最终`candidate-A-1`。
- B：10/10轮训练内三折均选择retain，全部记录`train_vetoed_by_internal_cv`，未生成候选；最终保留`baseline-B`。
- C：前三轮部署`soup_e3_alpha0.25`，后7轮训练内证据选择retain；最终`candidate-C-3`。
- portfolio累计CPU约A `0.743`秒、B `3.927`秒、C `28.980`秒；最大checkpoint `132,180`字节。
- 本地协议验收：`D:/brace-msi-first-principles-performance/FORMAL-PERF-001-A3-FINAL-CONTAINER/acceptance.json`，SHA-256 `B8D613065EE92BC5CD0786745D74D2F4FD3A7AD8E3D884D7FD1641A54739687B`，`valid=true`。

冻结后才对历史暴露的公开validation各读取一次作描述性诊断，不参与recipe、轮次或参数选择：A Macro-F1 `0.714030 → 0.725695`；B RMSE保持`681.159833`；C RMSE `52.868573 → 52.331755`。这些不是独立测试、隐藏成绩或官方成绩。

## 最终镜像门

- 归档：`D:/brace-msi-first-principles-release/BRACE-MSI-0.10.2rc1-FINAL/harness.tar`。
- 大小：`81,205,248`字节；SHA-256：`1F4B4C70061E2228977A98984ED3DF8D6E4C691E23D35DB95517A83173C5C6C0`。
- Linux amd64；镜像大小`81,187,012`字节；用户`10001:10001`；运行依赖仅`numpy==1.26.4`（基础镜像自带setuptools/wheel）。
- `/app`仅官方SDK九个源码文件、`brace_formal`八个源码文件和两个固定入口；禁入扫描未发现旧`brace_msi`、PyTRiO、SwanLab、sklearn、SciPy、psutil、数据、权重、密钥或报告。
- `pip check`、4核8GB断网、只读根、非root、独立预测、64 MiB产物门通过。
- 删除本地tag后从归档`docker load`，恢复相同镜像ID并再次通过`describe`。
- 完整回归：`458 passed in 143.01s`。

## 结论与边界

`FORMAL-PERF-001`本地完成，`0.10.2rc1`冻结为正式平台候选。它证明的是本地官方SDK 1.0.2契约、真实宿主调用边界、父checkpoint原生续训/retain、确定性训练内选择和干净镜像；尚未证明平台导入、真实Qwen Token、隐藏泛化或官方得分。在线PyTRiO私有客户端、SwanLab、官方试运行和正式评测本阶段使用均为0。
