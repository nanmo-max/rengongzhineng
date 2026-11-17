# WORKSPACE-V2-INDEPENDENT-TEST-001 本地独立平台模拟

## 结论

冻结A4 `docker save`归档在删除原标签、重新加载全新独立标签和全新状态目录后，完成A/B/C三任务各10轮官方workspace v2协议复演、宿主模型调用、父artifact继承、候选或retain、状态恢复及独立预测。机器结果为`valid=true`。

这是本地协议模拟，不计正式成绩。宿主模型为结构化本地替身；隐藏测试、正式Qwen Token、平台计费、公开指标和官方综合成绩均未产生。

## 输入与隔离

- 冻结归档：`D:/brace-msi-workspace-v2/BRACE-MSI-0.9.0rc1-A4/brace-msi-0.9.0rc1-harness.tar`
- 归档SHA-256：`dc0147706e5c20a62360bf309a280b890ac6cea2707eee4aa66f8f7169c57cbc`
- 镜像：从归档重新加载并标记为`brace-msi:0.9.0rc1-independent-test`
- 镜像ID：`sha256:b82d631f3d3a7727d4ec433124bcec8629c4d79248c3727d3cb1a7c02519d53a`
- 资源：Linux/amd64、4 CPU、8 GiB、`--network none`、非root用户`brace`
- 运行根：`D:/brace-msi-workspace-v2/WORKSPACE-V2-INDEPENDENT-TEST-001-A1/`
- 官方试运行、远程PyTRiO、SwanLab同步、隐藏数据：均为0

## 结果

| 任务 | 完成轮次 | 模型调用 | 候选提交 | 最终选择 | 独立预测 |
|---|---:|---:|---:|---|---:|
| A 气体识别 | 10/10 | 10 | 0 | `baseline-A` | 5 |
| B 轴承寿命 | 10/10 | 10 | 0 | `baseline-B` | 5 |
| C 发动机寿命 | 10/10 | 10 | 2 | `candidate-C-2` | 5 |
| 合计 | 30/30 | 30 | 2 | — | 15 |

所有轮次均引用非空`model_call_ids`。A/B由SafetyGate保留父模型；C第1、2轮提交并连续选择候选，后续轮次保持该父链。报告不计算隐藏指标，也不根据公开validation选择轮次。

## 报告产物

- HTML：`D:/brace-msi-workspace-v2/WORKSPACE-V2-INDEPENDENT-TEST-001-A1/platform-style-report-v2/platform-style-report.html`，SHA-256 `7d931103855fdeef08d47137e23ef7008b8bef2b18ad1d1dd46d8a3b16c34271`
- 机器报告JSON：`D:/brace-msi-workspace-v2/WORKSPACE-V2-INDEPENDENT-TEST-001-A1/platform-style-report-v2/platform-style-report.json`，SHA-256 `eb8929cfff82f4ac8576421419195f3dbf9ced498073529c35bccdd0b648215c`
- 协议验收JSON：`D:/brace-msi-workspace-v2/WORKSPACE-V2-INDEPENDENT-TEST-001-A1/acceptance.json`，SHA-256 `773bb1895382bbb0033c1d44378b71fdc1001084f9da6c4e3811ec7a8e82c42f`

HTML显著标记“本地协议模拟，不计正式成绩”，隐藏指标显示“正式平台产生，本地不可获得”，不存在“官方评测通过”表述。报告含三任务全部30轮，而不是只展示前三轮。

## 自动验证

- 报告专项：`2 passed`
- 完整回归：`437 passed in 150.59s`
- 缺少任一轮宿主模型调用收据时，生成器失败关闭且不产生HTML。

下一步仍是上传冻结A4归档，由真实平台验证模型网关、Token结算、公开测量和隐藏评测；本报告不能解除该外部阻塞。
