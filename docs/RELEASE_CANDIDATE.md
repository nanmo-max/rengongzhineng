# BRACE-MSI 0.3.0rc3 Release Candidate

## 结论

`BRACE-MSI-0.3.0rc3`是当前本地正式候选。它在RC2确定性Harness、A/B/C官方训练器与冻结性能参数上增加PyTRiO 0.2.9客户端、A3持久化Sampler的结构化动作意图，以及训练前ActionSandbox和训练后SafetyGate。`BRACE-MSI-0.1.0rc1`、`0.2.0rc2`、A1失败和A2负对照均保留为历史，不回写。

RC3不包含原始数据、A/B/C检查点、Sampler权重、Embedding、API密钥或私有日志。模型路径和凭据只在平台运行时注入。公开验证已历史暴露，三任务指标不是隐藏测试或官方成绩。

## 验收结论

| 项目 | 状态 | 证据或边界 |
|---|---|---|
| PyTRiO A3合规Sampler | PASS | 36/36远程步；新留出五项100%；A/B/C首轮3/3主动更新 |
| 三任务十轮自主闭环 | PASS | 各10轮/3候选；0守卫覆盖、0服务回退；逐项`valid=true` |
| 工业模型公开验证 | PASS_WITH_EXPOSURE | A 0.725695 Macro-F1；B 637.180224 RMSE；C 51.635999 RMSE |
| 预算与SafetyGate | PASS | 候选预算耗尽后的2次额外建议在训练前拒绝；拒绝候选不污染父链 |
| 完整代码回归 | PASS | 最终代码246项、打包前全新venv243项通过 |
| 干净依赖 | PASS | `brace-msi 0.3.0rc3`、`pytrio 0.2.9`、`pip check`通过 |
| Docker镜像 | PASS | linux/amd64；240,579,085字节；UID10001；无Torch/数据/权重/密钥 |
| 4核8GB断网容器 | PASS | 两种内部协议Smoke完成3/4候选；256 PID限制 |
| `docker save`归档 | PASS | 240,602,112字节；SHA-256 `0daef2e0...6d325a`；重载通过 |
| 比赛SwanLab正式记录 | BLOCKED | 等待比赛项目、字段、可见性与同步责任规范 `[H-004]` |
| 正式SDK事件/挂载 | BLOCKED | 等待平台接口 `[H-001]` `[H-002]` |
| 官方评分优化 | BLOCKED | 等待数学公式和隐藏评测 `[H-003]` |

机器证据见`docs/results/RC3_CONTAINER_ACCEPTANCE.json`与`docs/results/RC3_VERIFICATION.json`；PyTRiO与三任务证据见`docs/results/PYTRIO-COMPETITIVE-001-A1.md`。

## 当前上传入口

- Harness镜像归档：`D:/brace-msi-release/BRACE-MSI-0.3.0rc3/BRACE-MSI-0.3.0rc3-image-clean.tar`
- SHA-256：`0daef2e0e66cd2d3bc809a5d836a03020d1f90d677df91830fedc4feeb6d325a`
- 持久化Sampler完整路径：从Git外`D:/brace-msi-pytrio/PYTRIO-SFT-001-A3/result.json`的`sampler_model_path`读取，填入平台“持久化Sampler微调权重”字段
- 模型基座：`Qwen/Qwen3.5-4B`
- PyTRiO API Key：只填平台字段，不写入镜像、源码仓库或作品文档

## 生成最终交付目录

在干净Git工作树、最终提交和验证证据完成后执行：

```powershell
$env:PYTHONPATH='src'
python scripts/build_release_candidate.py `
  --output D:/brace-msi-release/BRACE-MSI-0.3.0rc3-final `
  --verification-evidence docs/results/RC3_VERIFICATION.json `
  --container-evidence docs/results/RC3_CONTAINER_ACCEPTANCE.json `
  --image-archive D:/brace-msi-release/BRACE-MSI-0.3.0rc3/BRACE-MSI-0.3.0rc3-image-clean.tar
```

打包器会重新核对发布ID、非root、体积、禁入文件、4核8GB断网状态、归档大小和SHA-256，并将镜像归档复制进最终目录。任一证据不一致即失败关闭。

## 真实平台到货后的唯一工作方向

1. 登记正式SDK、评分和SwanLab规范的版本与哈希；
2. 只替换插件内真实字段映射、挂载路径及模型服务注入；
3. 在不改变预算、沙箱和SafetyGate的前提下运行平台校验；
4. 最终工程模型冻结后按官方规范正式重训并生成SwanLab记录；
5. 不重开公开验证调参，不消耗十次试运行做基础调试。
