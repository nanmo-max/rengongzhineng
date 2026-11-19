# FORMAL-EVERY-ROUND-TRAIN-001 结果

## 结论

`0.10.6rc1`已在本地完成与D-086一致的正式候选链：每轮先由Qwen选择受控训练recipe，Harness真实续训并自行计算比赛关注的主辅指标，再由Qwen依据父/候选指标、资源和历史决定`deploy / retain / rollback`。平台逐轮不提供指标，也不参与内部部署决策；SafetyGate仅检查产物可加载、指标有限、父链/任务schema和64 MiB等硬约束。

本结果是本地官方SDK协议与容器验收，不是官方试运行、隐藏成绩或独立性能证明。历史公开validation已暴露，只作为描述性诊断。

## 根因与修复边界

- O-PLATFORM-018证明`0.10.4rc2`的模型调用与JSON解析已经恢复，但30/30轮主动`retain`使候选训练数为0。
- A1验证“每轮强制真实训练”，但错误地让平台返回指标决定部署，判为`INVALID_WRONG_DECISION_OWNER`。
- A2因模拟器仍假设平台逐轮返回指标而中止。
- A3删除平台指标后通过核心链路。
- A4只改变本地模拟Qwen的决策回答以覆盖严格退化时的`rollback`；正式镜像代码与A3完全相同。

## A4容器验收

- 镜像：`brace-msi:0.10.6rc1`
- 镜像ID：`sha256:52333ab152aa11a4a6b14a8270fcebe3e1e2290813f18ac77bf46e1810ca7504`
- 平台：`linux/amd64`，非root `10001:10001`
- 镜像大小：81,190,622字节
- 归档：`D:/brace-msi-first-principles-release/BRACE-MSI-0.10.6rc1-A1/harness.tar`
- 归档大小：81,208,320字节
- 归档SHA-256：`F7518609974EAB3C156C07F6D0AA7CBFE6CF9253B43C5D20B3DC71B4C91D89CB`
- `docker save`归档删除标签后重新`docker load`，镜像ID保持一致。
- A/B/C共30轮；30次训练方案调用、30次部署决策调用、30个真实候选训练。
- 平台逐轮指标30/30为空；本地Qwen模拟决策为4次deploy、26次rollback；硬安全失败0。
- 机器证据：`D:/brace-msi-first-principles-performance/FORMAL-EVERY-ROUND-TRAIN-001-A4-CONTAINER/acceptance.json`
- 机器证据SHA-256：`307581D27589AD17A90BEF69A1283D86B51AEF553238D5F34AEB08400CDF2CD8`

## 描述性性能诊断

以下只来自已暴露的官方公开validation，不参与本轮代码或参数选择，不得写成隐藏测试或独立泛化成绩：

| 任务 | 父模型 | A4最终稳定模型 | 变化 |
| --- | --- | --- | --- |
| A | Accuracy 0.878617；Macro-F1 0.714030 | Accuracy 0.885852；Macro-F1 0.725695 | Macro-F1 +0.011666 |
| B | MAE 563.105841；RMSE 681.159833 | MAE 545.860566；RMSE 656.351785 | RMSE -24.808047 |
| C | MAE 38.899830；RMSE 52.868573 | MAE 38.812042；RMSE 52.350178 | RMSE -0.518395 |

最终稳定artifact分别为A `candidate-A-1`、B `candidate-B-2`、C `candidate-C-1`。后续退化候选均由Qwen依据本地指标回滚到稳定父模型。

## 验证边界

- 完整代码回归：`471 passed in 146.50s`。
- `pip check`：无破损依赖。
- 镜像`/app`仅19个白名单文件；不含数据、权重、密钥、PyTRiO私有SDK、SwanLab、测试或报告。
- 本阶段远程PyTRiO调用、SwanLab同步、平台上传、官方试运行和隐藏测试使用均为0。
- 正式平台是否接受每轮两次`rnd.model()`、最终Token计量和真实Qwen决策质量，只能由下一次受控平台试运行确认。
