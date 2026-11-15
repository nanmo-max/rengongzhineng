# NATIVE-COMPETITIVE-RC-001 发布验收

## 结论

`BRACE-MSI-0.7.0rc1`已完成本地发布验收。镜像默认使用A/C竞争策略与B已验证Protocol策略；未知profile不按数据集名称硬编码，默认使用竞争策略。PyTRiO不可用时只保留父模型，不静默执行确定性训练。

## 性能边界

冻结后仅进行一次公开validation确认：

| 任务 | 0.6.0rc1 | 0.7.0rc1发布组合 | 说明 |
|---|---:|---:|---|
| A | Macro-F1 0.714030 | Macro-F1 0.725695 | A竞争策略，严格改善 |
| B | RMSE 660.076488 | RMSE 660.076488 | 复用0.6已验证Protocol证据；未重开validation |
| C | RMSE 52.868573 | RMSE 51.949287 | C竞争策略，严格改善 |

这些是已暴露公开验证结果，不是隐藏测试或官方成绩。A/C改善、B不退化满足本冲刺修订后的冻结门；不声称达到30%冲刺目标。

## 容器验收

- 完整回归：`377 passed in 150.76s`。
- 镜像：linux/amd64、UID 10001、`241,874,808`字节，无数据、权重、密钥。
- 资源限制：`--network none --cpus=4 --memory=8g --pids-limit=256 --read-only`。
- A/B/C均完成10轮、父链连续、独立预测；候选数为3/10/3，部署数均为1。
- 最大RSS：A 94,965,760；B 113,430,528；C 238,686,208字节。
- 最终checkpoint：A 132,180；B 36,600；C 28,848字节，远低于64 MiB。
- 默认PyTRiO在断网环境重试两次后执行`noop/retain`，候选训练数0，未发生静默确定性训练。
- 独立`submit`入口生成1,244条预测。
- `docker save`归档已`docker load`验证，SHA-256：`B4EF8820FE38B4479B16657A85594719EB86CA7BAD157C0B484DDF4715FB1BD7`。

机器证据：

- [RC7_VERIFICATION.json](RC7_VERIFICATION.json)
- [RC7_CONTAINER_ACCEPTANCE.json](RC7_CONTAINER_ACCEPTANCE.json)
- Git外完整运行目录：`D:/brace-msi-native-competitive/RC7-CONTAINER-ACCEPTANCE-FINAL/`

## PyTRiO与SwanLab

- Native PyTRiO已取得2次非零响应，只有1次建议被执行；计划的3次在线门未达到，状态继续为`BLOCKED_EXTERNAL`，不伪造通过。
- COMPOSE-A2三任务聚合记录已同步到SwanLab公开项目，112条/任务；已扫描无API Key、逐样本特征、标签或checkpoint内容。
- 公开项目：<https://swanlab.cn/@nanmo-max/brace-msi-platform-native>

## 可上传归档

`D:/brace-msi-native-competitive/RC7-CONTAINER-ACCEPTANCE-FINAL/brace-msi-0.7.0rc1-harness.tar`

该文件由`docker save`生成。平台仍需完成“镜像可用”、模型校验、正式续训协议和试运行；本地验收不能替代这些外部状态。
