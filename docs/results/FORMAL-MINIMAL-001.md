# FORMAL-MINIMAL-001 验收记录

## 结论

第一性原理重建的最小正式运行核已完成本地协议验收。该结论只覆盖官方SDK 1.0.2边界、父checkpoint续训/retain、真实宿主call ID、状态、历史、候选和独立预测，不等于镜像或官方平台已经通过。

## 实现证据

- Task 1：宿主模型单调用边界与十轮唯一工作目录；提交`902144d`。
- Task 2：最小NumPy模型与已验证`_NativeModel`逐状态差分等价；提交`5995063`。
- Task 3：官方单轮编排、候选/retain、安全门和独立预测；提交`cf6753a`。
- Task 4：`scripts/simulate_first_principles_runtime.py`独立合成协议测试。

## 验证

- 官方真实`Round`对象转录：`history_request → model_request → state_request → round_complete`，retain仍引用真实call ID。
- focused：`18 passed in 0.81s`；Task 4：`1 passed in 0.51s`。
- 完整回归：`451 passed in 149.89s`。
- A2：A/B/C各10轮，30个唯一宿主call ID；父链、状态链全部有效；A采用4个候选，B/C各采用10个。
- A2机器摘要：`D:/brace-msi-first-principles-sim-20261117-A2/acceptance.json`，SHA-256 `83834956C7539345B7C83D6A06FC44FB12E8244713BAAAE8373CA2501A68E2EF`。
- HTML：`D:/brace-msi-first-principles-sim-20261117-A2/report.html`，明确标注本地合成协议测试、非官方成绩。

## 未通过或未执行

- A1直接源码启动失败，原因是缺`PYTHONPATH=src`，随后暴露默认workspace残留目录冲突；A1不得作为通过证据。
- 尚未构建白名单Docker、未做4核8GB/只读/非root/断网验收、未执行`docker save/load`。
- 未调用在线模型、SwanLab、官方试运行或正式评测。
