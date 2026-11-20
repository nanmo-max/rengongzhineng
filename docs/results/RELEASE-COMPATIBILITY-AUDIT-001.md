# RELEASE-COMPATIBILITY-AUDIT-001 独立准入审计

## 结论

审计结论分为两层：

1. **协议和容器兼容性：本地通过。** 冻结归档能够从`docker save`包重载，在Linux/amd64、4 CPU、8 GiB、非root、只读根和断网条件下完成官方SDK 1.0.2的`describe/train/predict`生命周期；A/B/C各10轮、每轮2次宿主模型调用、每轮1个真实候选，共60个调用ID和30个候选；父链、状态链、候选声明及逐行预测均完成。
2. **最终发布准入：不通过。** 精确冻结镜像仍允许错误的Qwen部署决定覆盖明确退化的主指标。独立负向测试中，C候选RMSE由`52.868573`恶化至`55.629944`，宿主返回`deploy`后镜像实际选择了该候选。该缺陷已经在当前源码提交`afa9038`之后修复，但修复不在冻结镜像`0.10.6rc1`内；而当前源码尚未通过D-088/D-091最终泛化门，也未构建新的正式归档。

因此最准确的发布判断是：**现有镜像可以本地证明“接口能接、流程能跑”，但不能作为最终正式提交镜像；精确归档在真实平台的导入与运行仍需外部确认，且在选择一致性缺陷修复进入新归档前不应消耗试运行次数。**

## 审计对象与血缘

- 归档：`D:/brace-msi-first-principles-release/BRACE-MSI-0.10.6rc1-A1/harness.tar`
- 大小：`81,208,320`字节
- SHA-256：`F7518609974EAB3C156C07F6D0AA7CBFE6CF9253B43C5D20B3DC71B4C91D89CB`
- 镜像：`brace-msi:0.10.6rc1`
- 镜像ID：`sha256:52333ab152aa11a4a6b14a8270fcebe3e1e2290813f18ac77bf46e1810ca7504`
- 镜像大小：`81,190,622`字节
- 运行身份：`10001:10001`
- 源码血缘：镜像`/app`全部19个文件与提交`c653e0e04297b655b93e28a90abd9f36e2ff761d`逐文件SHA-256一致；无多余文件。
- 远程源码：`https://github.com/nanmo-max/rengongzhineng/tree/c653e0e04297b655b93e28a90abd9f36e2ff761d`

## 本地独立验证

### 官方SDK与运行契约

| 检查项 | 状态 | 证据 |
|---|---|---|
| SDK/协议声明 | PASS | `describe`返回`contest_harness 1.0.2`、`contest.harness.workspace.v2`、`host_gateway_rpc` |
| 官方SDK上游离线测试 | PASS | 精确镜像、4 CPU、8 GiB、断网下17项中15项通过，2项需真实API/PI而跳过 |
| A/B/C十轮 | PASS | 三任务各10轮，共30轮 |
| 每轮两次宿主调用 | PASS | 每任务20个、总计60个非空且被完成记录引用的调用ID |
| 每轮真实候选 | PASS | 30/30轮均生成并提交候选 |
| 父checkpoint连续性 | PASS | 每轮入站父哈希与上一轮实际选择产物一致 |
| 状态连续性 | PASS | 三任务均形成10轮状态链 |
| 独立预测入口 | PASS | 三任务各5行逐行预测，共15行 |
| 64 MiB产物门 | PASS | 最大checkpoint `132,180`字节 |
| 4核8GB/断网/只读/非root | PASS | 容器命令显式设置；30轮与预测全部完成 |
| Docker归档格式 | PASS | OCI/docker-save归档包含`manifest.json`、`index.json`、`oci-layout`并可`docker load`恢复同一镜像ID |
| 运行镜像白名单 | PASS | `/app`仅19个运行文件；依赖仅NumPy 1.26.4及基础打包工具 |
| 数据/工业权重/测试/报告禁入 | PASS | 镜像文件清单无这些内容 |
| 凭据禁入 | PASS_WITH_NOTE | 未发现凭据值；官方SDK源码含`API_KEY`环境变量名称，不是密钥 |
| 精确平台导入与真实Qwen | BLOCKED_EXTERNAL | 本地替身不能替代平台导入、真实Token计量及网关故障行为 |

机器证据：

- `D:/brace-msi-release-audit/RELEASE-COMPATIBILITY-AUDIT-001-A1/acceptance.json`
- SHA-256：`307581D27589AD17A90BEF69A1283D86B51AEF553238D5F34AEB08400CDF2CD8`
- 近似本地容器墙钟：`179.49`秒；候选训练CPU合计A/B/C分别约`0.061/0.296/1.547`秒。该墙钟使用本地即时宿主替身，不能外推平台Qwen延迟。
- 精确镜像没有记录峰值RSS字段；8 GiB cgroup未触发OOM只证明上界未突破，不能作为精确内存计量。

### 描述性效果复算

以下只使用历史已暴露的官方公开`validation.jsonl`，不用于选型或正式泛化主张：

| 任务 | 初始模型 | 本地最终稳定模型 | 变化 |
|---|---|---|---|
| A Gas | Accuracy `0.878617`；Macro-F1 `0.714030` | Accuracy `0.885852`；Macro-F1 `0.725695` | Macro-F1 `+0.011666`（约`+1.63%`相对） |
| B Bearing | MAE `563.105841`；RMSE `681.159833` | MAE `545.860566`；RMSE `656.351785` | RMSE降低`24.808047`（约`3.64%`） |
| C Engine | MAE `38.899830`；RMSE `52.868573` | MAE `38.812042`；RMSE `52.350178` | RMSE降低`0.518395`（约`0.98%`） |

这些结果证明父链续训能产生有限正向变化，不证明未知任务泛化或高竞争力。O-PLATFORM-019的真实平台试运行曾得到A隐藏Macro-F1 `0.861027`、B隐藏RMSE `354.669933`和C隐藏RMSE `56.187077`，但报告未记录镜像digest或Git提交，不能把这些成绩直接归因给本归档；C的隐藏收益也明显不足。

## 关键失败：选择一致性

精确镜像负向测试使用官方C父checkpoint和公开验证，只改变本地宿主的第二次回答：

```text
父模型 RMSE       52.8685725661
候选模型 RMSE     55.6299443899
宿主建议           deploy
实际选择           candidate-C-1
wrong_deploy_accepted = true
```

产物：`D:/brace-msi-release-audit/RELEASE-COMPATIBILITY-AUDIT-001-A2-WRONG-DECISION/`。

这与O-PLATFORM-019已观察的Gas第5轮、Bearing第2轮和Engine第4轮数值—决定矛盾一致。`0.10.6rc1`只校验决定枚举、理由和硬安全约束，没有把确定性指标方向变成可行决定集合。本地正常复演使用会正确比较大小的宿主替身，因此不能发现该问题。

当前工作树已通过`MetricContract`、同作用域有向收益和`allowed_decisions`修复此缺陷；专项加完整回归新鲜结果为`533 passed in 157.64s`。但该工作树相对远程分支领先9个提交、尚无匹配Docker归档，且D-091禁止把未通过最终泛化门的研究组合直接晋级，因此不能用“源码已修”替代“正式镜像已修”。

## 正式材料与外部服务

| 材料/服务 | 状态 | 结论 |
|---|---|---|
| Docker `harness.tar` | PASS_FORMAT / FAIL_RELEASE | 格式、体积、运行契约通过；选择一致性缺陷阻止最终发布 |
| 源码仓库 | PASS_FOR_RC_SOURCE | `c653e0e`已在远程`codex/first-principles-rebuild`历史中，可精确对应镜像 |
| PyTRiO/Qwen | PASS_BY_OFFICIAL_HOST_CONTRACT / BLOCKED_EXACT_RUN | 正式镜像正确地不内置PyTRiO私有SDK；通过`rnd.model()`使用平台绑定Qwen。精确归档真实平台Token仍未和digest绑定 |
| SwanLab | STALE_FOR_CURRENT_RC | 现有公开记录属于历史RC或镜像外Advisor训练；没有与`0.10.6rc1`提交、归档哈希和正式十轮运行一致的最终工程训练记录 |
| 官方隐藏性能 | BLOCKED_EXACT_ATTRIBUTION | 有O-PLATFORM-019平台成绩，但缺精确镜像digest/提交绑定 |
| 作品说明/技术报告 | NOT_REAUDITED | 本任务只审计运行与性能证据，未生成或提交材料 |

## 发布决定

- `0.10.6rc1`：`DO_NOT_UPLOAD_AS_FINAL`。
- 当前HEAD：`SOURCE_FIX_VERIFIED_BUT_NO_FORMAL_IMAGE`。
- 新正式RC：继续由`FORMAL-RC-NEXT-001`阻塞，直到只集成发布必要的选择一致性修复，并重新通过精确归档的30轮、负向决策、官方SDK、Docker和材料绑定门；D-091失败的研究策略不得顺带进入。
- 官方平台：本地兼容性很高，但“精确新归档可被平台导入并真实运行”只能由一次受控试运行确认，不能从本地替身保证。

## 新鲜验证命令摘要

```text
Get-FileHash harness.tar
docker load -i harness.tar
docker run ... brace-msi:0.10.6rc1 describe
python -m pytest -q tests/formal_runtime tests/official_sdk_v2 ...
python scripts/verify_workspace_v2_image.py --image brace-msi:0.10.6rc1 ...
docker run ... official SDK unittest discovery
python -m pytest -q
```

结果：专项`62 passed`；官方SDK离线`15 passed, 2 skipped`；完整当前源码`533 passed`；精确镜像三任务复演`valid=true`；精确镜像错误部署对抗测试`wrong_deploy_accepted=true`。
