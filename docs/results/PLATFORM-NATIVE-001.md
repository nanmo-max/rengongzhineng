# PLATFORM-NATIVE-001 平台原生十轮验收

## 结论

`BRACE-MSI-0.6.0rc1`新增不依赖完整训练包树的原生运行入口，直接消费平台已知的`/data`、`/previous/checkpoint.npz`、`/workspace`和`/output`四个挂载。A/B/C三项均在真实Linux容器中完成10个决策轮、10次真实候选训练、门控部署或拒绝及独立预测；不是前三轮抽查。

本证据是本地平台挂载模拟，不是官方平台通过或隐藏成绩。公开validation有历史暴露，只用于接口和输出完整性核验。

## 原生契约

- `python -m brace_msi describe`：声明挂载、模型格式和操作。
- `python -m brace_msi start`：加载平台父`checkpoint.npz`，延续权重、Adam、标准化、epoch与step，对当前带标签批次产生候选并经Gate/Anchor门控输出子checkpoint。
- `python -m brace_msi submit`：从冻结checkpoint对无标签JSONL独立预测。
- 每轮均写出`training.json`、`history.jsonl`、`checkpoint.npz`；私有`/workspace/state.json`保存十轮父链和缓冲区状态。
- 每轮均包含`brace-msi.platform-decision.v1`收据。正式镜像默认使用`Qwen/Qwen3.5-4B` PyTRiO受控建议；模型只能提出白名单动作和有界参数，训练、预算与部署仍由确定性Harness控制。服务异常最多重试一次后记录失败并确定性恢复。

## 完整回归

- 命令：`D:/anaconda3/python.exe -m pytest -q --tb=short`
- 结果：`348 passed in 120.53s`（最终`0.6.0rc1`工作树）
- 原生专项：`15 passed`

## 四挂载容器验收

- 镜像：`brace-msi:0.6.0rc1`
- Linux/amd64，非root用户`brace`。
- 镜像大小：241,855,558字节，小于2 GiB。
- 约束：`--network none --cpus 4 --memory 8g --pids-limit 256 --read-only`，无GPU。
- 镜像内未发现`.npz`、`.jsonl`、Key或Secret文件；`pip check`无破损依赖；PyTRiO和SwanLab均可导入。
- 运行证据：`D:/brace-msi-platform-native-container/PLATFORM-NATIVE-CONTAINER-002-A2-FINAL/`
- 机器摘要SHA-256：`EAB693A1F423B8B1B4A8FF91302FFB705F6D4ED898B4FE6E4E8F61D98140BA5E`
- `docker save`归档：`D:/brace-msi-release/BRACE-MSI-0.6.0rc1/BRACE-MSI-0.6.0rc1-image-clean.tar`，241,879,040字节，SHA-256 `F98FB679D1216564634382E00CC105980C7857021BE33F99A59A240496CBC62D`；`docker load`后镜像ID保持`sha256:70500514...d605123e`。

| 任务 | 决策轮 | 真实候选 | 接受/拒绝 | 父链 | 独立预测行 | CPU总时长 | 峰值RSS |
|---|---:|---:|---:|---|---:|---:|---:|
| A | 10 | 10 | 0/10 | 通过 | 1,244 | 0.434851秒 | 127,041,536字节 |
| B | 10 | 10 | 1/9 | 通过 | 1,679 | 2.017933秒 | 130,326,528字节 |
| C | 10 | 10 | 0/10 | 通过 | 23,049 | 21.111130秒 | 154,902,528字节 |

全部30轮均满足：轮号连续、父checkpoint哈希与上一轮提交一致、`parent_loaded=true`、候选真实训练、决策收据存在、输出checkpoint小于64 MiB。A/C的候选均未越过严格门控，因此保持父模型；这属于正确拒绝，不是缺少训练。

## 本地公开验证观察

严格门控A4仅作为暴露公开数据观察：A Macro-F1保持0.714030；B RMSE由681.159833降至660.076488；C RMSE保持52.868573。不得把这些数值写成官方隐藏成绩，也不得据此继续调门。

## 未冒充通过的边界

- 断网容器验收使用确定性Advisor，故Token为0；PyTRiO提案解析、触发、一次重试、非法建议拒绝和确定性恢复由自动测试覆盖，但本轮没有制造在线调用成功证据。
- 精确官方启动命令、凭据注入字段、平台是否调用`describe/start/submit`仍未发布，继续属于`FORMAL-RELEASE-001`外部阻塞。
- 旧`official-agent-run`整包审计入口继续保留作研究和供应链验证，没有为适配平台而削弱。
