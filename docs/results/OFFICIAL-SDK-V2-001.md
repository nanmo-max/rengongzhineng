# OFFICIAL-SDK-V2-001 本地正式接入验收

## 结论

`BRACE-MSI-0.9.0rc1`已按官方`contest_harness` 1.0.2接入`contest.harness.workspace.v2`。本地A/B/C三任务宿主协议复演、完整代码回归、正式镜像内容审计、4核8GB断网容器、独立预测以及`docker save/load`均通过。该结论只覆盖本地正式接入与发布准备，不等于平台导入、真实Qwen调用、Token结算或隐藏评测已经通过。

## 官方证据

- SDK归档：`contest-harness-sdk-1.0.2.tar.gz`，SHA-256 `c676c8beeef69cece9cbec5a633d05dbb9832eb22b6f761913f2315bd1f85133`。
- SDK说明：`contest-harness-sdk-1.0.2.txt`，SHA-256 `0433a8a3c7b6641985b1abf90c9ce5de349b1b3efdad1c6494ed6680c9ebc99c`。
- vendored `src/contest_harness/*.py`九个文件与官方解压件逐文件SHA-256一致。
- 官方SDK上游测试在Linux 4核8GB断网容器中`15/15 OK`；Windows单项管道行为差异保留为环境证据，未修改上游SDK。

## 正式实现边界

- 固定入口：`python3 /app/harness.py describe|train|predict`。
- 模型调用：只经官方宿主`rnd.model()`；正式镜像不安装PyTRiO客户端、不保存API Key、不内置Tokenizer或Qwen权重。
- 训练：继续使用已验证的原生父`checkpoint.npz`续训/retain、竞争策略和SafetyGate；不改变checkpoint schema。
- 候选：仅内部Gate允许时提交给平台；平台测量可再次拒绝，最终只选择已声明的父或候选artifact。
- 预测：严格使用`CONTEST_ARTIFACT_PATH`，逐行读取、逐行输出并flush。
- SwanLab：仍使用既有外部公开聚合训练记录，不安装进离线评测镜像，也不伪造本次SDK接入为一次新训练。

## 机器验证

| 项目 | 结果 |
|---|---|
| 官方SDK入口专项 | `5 passed` |
| 完整代码回归 | `435 passed in 142.62s` |
| A/B/C宿主协议复演 | 各10轮，共30轮 |
| 宿主模型调用 | 每轮1次，共30次；完成记录引用全部`model_call_ids` |
| 候选提交路径 | C第1、2轮真实提交并连续选择；A/B由SafetyGate合法retain |
| 独立预测 | A/B/C各5行，共15行 |
| 最大候选artifact | 36,598字节，远低于64 MiB |
| 容器资源 | Linux/amd64、4 CPU、8 GiB、`--network none`、UID 10001 |
| 镜像内容 | `/app`仅`harness.py`和`contest_submission.py`；无测试、模拟脚本、数据、权重、密钥或报告 |
| 可选依赖 | `pytrio_installed=false`，`swanlab_installed=false` |
| `pip check` | PASS |

平台测量拒绝候选的状态对账先由红灯测试复现，随后验证持久状态、公开收据和最终父artifact一致；该分支不依赖本地宿主替身返回特定分数。复演机器结果：`D:/brace-msi-workspace-v2/WORKSPACE-V2-ACCEPTANCE-001-A4/acceptance.json`，SHA-256 `1a4387ffbacb058ca159d4f94ac5f01346d299d5ce0693a1962b6d044749a6ba`。其scope固定为`local_protocol_only_not_official_score`，没有计算或反馈公开验证成绩。

## 正式上传归档

- 路径：`D:/brace-msi-workspace-v2/BRACE-MSI-0.9.0rc1-A4/brace-msi-0.9.0rc1-harness.tar`
- 格式：`docker save`归档
- 大小：151,393,280字节
- SHA-256：`dc0147706e5c20a62360bf309a280b890ac6cea2707eee4aa66f8f7169c57cbc`
- 镜像ID：`sha256:b82d631f3d3a7727d4ec433124bcec8629c4d79248c3727d3cb1a7c02519d53a`
- 镜像内部大小：151,369,904字节
- 重载验证：删除正式tag后执行`docker load`成功；重载镜像再次`describe`返回SDK 1.0.2和host gateway协议。

## 版本分离

- A1/A2/A3归档和0.8.3及更早镜像均只保留历史，不得上传代替A4。
- `scripts/verify_workspace_v2_image.py`、测试、官方训练包和本地复演目录只属于研发/验收，不在正式镜像中。
- 当前仅剩平台外部确认：上传导入状态、真实宿主Qwen非零Token、平台父artifact生命周期、公开测量和隐藏评测。
