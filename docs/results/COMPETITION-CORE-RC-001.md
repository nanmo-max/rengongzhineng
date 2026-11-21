# COMPETITION-CORE-RC-001 独立本地验收与正式发布审计

## 结论

`BRACE-MSI 0.11.0rc1`已完成当前无需官方平台即可执行的独立验收。正式镜像、官方SDK协议替身、候选训练、双阶段模型调用、父链、历史模型回选、预测、资源边界、归档重载和干净环境回归均通过。该结论是**本地发布准入通过**，不是官方平台运行成功或隐藏成绩；真实平台生命周期、模型网关和隐藏评分仍为外部验证项，未消耗试运行次数。

## 正式发布物

| 项目 | 值 |
| --- | --- |
| 镜像标签 | `brace-msi:0.11.0rc1` |
| 镜像ID | `sha256:578e7c9aa0c507efddeb6b4a182fc28299591a2a0a0e7fb1401a02f39b50da51` |
| 平台协议 | `contest.harness.workspace.v2` / `contest_harness 1.0.2` |
| 运行用户 | `10001:10001` |
| 镜像大小 | 81,214,923 bytes |
| `docker save`归档 | `D:/brace-msi-release/COMPETITION-CORE-RC-001/harness.tar` |
| 归档大小 | 81,232,384 bytes |
| 归档SHA-256 | `b7ba01bcc8a60502896082b58578b56c60c539a5460bb373285ff0abe4503e30` |
| 构建源码提交 | `a28a1fe00cc700f2adc6ea535e2dd0817863e8bd` |
| 平台模型 | `Qwen/Qwen3.5-4B`基础模型；SFT候选未达采用门 |
| SwanLab | <https://swanlab.cn/@nanmo-max/BRACE-MSI/runs/ph2ztekq> |

归档经删除本地标签后重新`docker load`，镜像ID保持一致。正式镜像只含固定入口、`brace_formal`最小运行核、官方SDK和NumPy；不含数据、权重、测试、模拟器、报告、PyTRiO、SwanLab、Tokenizer、Sampler或凭据。

## 独立协议验收

正式镜像在4核、8GB、无网络、只读根文件系统和非root约束下完成：

- A/B/C各10轮，共30轮、60次真实宿主模型替身调用、30个父checkpoint候选；
- 两个内容身份不透明的同格式分类/回归任务各10轮，共20轮、40次模型调用、20个候选；
- 五类任务合计50轮全部执行双阶段调用和真实候选训练；
- 错误要求部署劣质候选时，确定性同作用域选择拒绝错误部署；
- 历史产物在当前合法作用域重新评价后可回选，保存—加载预测一致；
- 正式`describe`声明分类/回归能力和宿主模型网关；独立`predict`入口工作；
- `release-audit.json`全部门为`PASS`。

身份不透明测试使用SDK允许的A/C槽位但替换内容身份，未虚构官方不支持的数据集键；它验证任务画像和内容身份无关路径，不证明官方隐藏任务分布等价。

## 本地效果证据

### 独立开发/确认矩阵

`COMPETITION-CORE-EXP-001`先用train内部十轮开发，再在策略冻结后一次读取确认分区。A/B/C公开validation历史上已经暴露，因此只作描述性开发证据：

| 任务 | 静态父模型 | 冻结`core_robust` | 相对变化 |
| --- | ---: | ---: | ---: |
| A Macro-F1 | 0.714030 | 0.730826 | +2.35% |
| B RMSE | 681.159833 | 680.012612 | -0.17% |
| C RMSE | 52.868573 | 51.877279 | -1.88% |
| 代理分类 Macro-F1 | 0.229391 | 0.841576 | +266.88% |
| 代理回归 RMSE | 6.554071 | 0.551207 | -91.59% |

风险优先`core_stable`在B/C改善，但A回退到0.699854；所以固定单一recipe没有被写入正式策略。正式运行由任务画像、历史实验、注册recipe和同作用域选择共同决定。

### 精确镜像协议复演

已知任务复演中，最终同作用域公开指标为A Macro-F1 0.725843、B RMSE 657.645417、C RMSE 51.735030，均好于对应起始父模型。该复演反复使用历史公开validation，目的仅是验证选择器、父链和报告字段，**不得作为独立性能、官方成绩或获奖水平证据**。

准确评价：正式候选已经具备可学习、回退和通用分类/回归闭环；已知官方公开任务提升仍然偏小，不能声称达到30%或获奖水平。最新历史官方试运行O-PLATFORM-019的A/B/C隐藏结果属于另一历史镜像，不归因于本RC。

## PyTRiO与SwanLab

- Task 11真实执行两次PyTRiO SFT。A2完成36步、持久化和重载，schema与部署选择100%，严格总体策略87.5%，低于预注册90%采用门，因此正式候选继续使用平台已经校验的Qwen3.5-4B基础模型。
- SwanLab公开运行只含39条脱敏聚合记录，敏感扫描零匹配；逐样本数据、标签、特征和凭据未上传。
- 正式镜像不直连PyTRiO或SwanLab；模型经官方宿主`rnd.model()`访问，记录链接由提交材料外部绑定。

## 自动验证

- 当前主机完整回归：`629 passed in 163.91s`。
- 全新venv安装项目、`requirements-dev.lock`和`requirements-pytrio.lock`后：`pip check`无冲突，`629 passed in 175.11s`。
- 本地测试镜像`brace-msi:competition-core-local`在4核8GB、断网、只读环境完成两个任务画像各10轮并生成JSON/HTML；它带模拟器且明确标记`LOCAL_TEST_ONLY`，不得上传。

## 机器证据

- 发布审计：`D:/brace-msi-release/COMPETITION-CORE-RC-001/release-audit.json`
- 最终HTML：`D:/brace-msi-release/COMPETITION-CORE-RC-001/release-report.html`
- 已知任务验收：`D:/brace-msi-release/COMPETITION-CORE-RC-001/acceptance-known-v6/acceptance.json`
- 身份不透明验收：`D:/brace-msi-release/COMPETITION-CORE-RC-001/acceptance-opaque-v5/acceptance.json`
- 对抗与回滚：`D:/brace-msi-release/COMPETITION-CORE-RC-001/blackbox-v4/blackbox.json`
- 本地测试镜像模拟：`D:/brace-msi-release/COMPETITION-CORE-RC-001/local-image-simulation-v2/`

## 剩余外部项

以下无法由本地替身诚实证明：平台实际导入、正式宿主Qwen调用、真实挂载/状态持久化、平台Token计量、14,773条隐藏预测与官方评分。只有用户另行授权一次平台试运行后才能解除`BLOCKED_EXTERNAL`。失败时必须先保存平台原始报告，不盲目重试。
