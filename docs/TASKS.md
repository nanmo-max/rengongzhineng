# 可执行任务清单

状态定义见 [WORKFLOW.md](WORKFLOW.md)。任务状态只在本文件维护。

## 当前任务图

```text
EVIDENCE-RSI-001(DONE)
  -> DUAL-DATA-001(DONE)
  -> DUAL-TXN-001(DONE)
  -> DUAL-VALUE-001(DONE)
  -> DUAL-QWEN-001(DONE)
  -> DUAL-PLUGIN-001(DONE)
  -> DUAL-MODEL-001(DONE)
  -> DUAL-INTEGRATION-001(DONE)
  -> DUAL-EXPERIMENT-001(DONE_MIXED)
  -> GENERALIST-MODEL-001(DONE)
  -> DUAL-RC-001(IN_PROGRESS)
```

以上为D-052当前正式重构图；既有RC和下方历史任务图保持冻结，不因重构而改写。

### EVIDENCE-RSI-001 宣讲证据与双闭环语义

- 状态：`DONE`
- 优先级：P0
- 完成标准：13张截图的哈希、证据等级和边界登记；追加十轮与两层迭代决策；正式设计和实施计划可恢复
- 证据：`source_notes/RSI_LECTURE_EVIDENCE_2026-11-13.md`、`B-RSI-002`、`D-051`、`D-052`、`superpowers/specs/2026-11-13-controlled-dual-loop-design.md`、`superpowers/plans/2026-11-13-controlled-dual-loop.md`

### DUAL-DATA-001 四缓冲区与物理数据能力边界

- 状态：`DONE`
- 依赖：EVIDENCE-RSI-001
- 优先级：P0
- 完成标准：Anchor/Update/Gate/Replay用途与隔离期可审计；候选训练集合只含Update或Update+eligible Replay；RoundDataManifest不暴露源根；未来批次诱饵无法被训练器或插件发现；专项和完整回归通过
- 停止条件：实现必须猜测正式SDK字段；此时仅保留平台无关的数据能力接口和模拟测试
- 证据：`src/brace_msi/online_data.py`、`tests/dual_loop/test_online_data.py`；专项`4 passed`，完整回归`275 passed`

### DUAL-TXN-001 每批单决策事务与恢复

- 状态：`DONE`
- 依赖：DUAL-DATA-001
- 优先级：P0
- 完成标准：每批恰好一次决策；0至2候选；第二候选只能由首候选结果、新证据和预算触发；原子提交、崩溃恢复和重复事件幂等
- 证据：`src/brace_msi/dual_loop.py`、`tests/dual_loop/test_dual_loop.py`；专项`5 passed`，完整回归`280 passed`

### DUAL-VALUE-001 动作收益、Pareto与影子归因

- 状态：`DONE`
- 依赖：DUAL-TXN-001
- 优先级：P0
- 完成标准：每任务ActionValueTable、性能—成本Pareto、同批影子配对收益和低置信度降级通过自动测试，影子资源全部计量
- 证据：`src/brace_msi/policy_learning.py`、`tests/dual_loop/test_policy_learning.py`；专项`5 passed`，完整回归`285 passed`

### DUAL-QWEN-001 证据触发Qwen与确定性恢复

- 状态：`DONE`
- 依赖：DUAL-VALUE-001
- 优先级：P0
- 完成标准：只在严重退化、复杂漂移、连续失败或动作不可区分时调用；限时重试一次；异常有收据并由确定性策略继续；不微调Qwen
- 证据：`src/brace_msi/pytrio_agent.py`、`tests/dual_loop/test_agent_advisor.py`；专项`9 passed`，完整回归`294 passed`，真实服务调用0次

### DUAL-PLUGIN-001 受限纯函数补丁沙箱

- 状态：`DONE`
- 依赖：DUAL-QWEN-001
- 优先级：P0
- 完成标准：AST、签名、子进程、CPU/RSS/超时、形状、有限值、确定性和差异测试齐全；文件、网络、反射、无限循环、OOM与越界输出失败关闭
- 证据：`src/brace_msi/restricted_plugin.py`、`tests/dual_loop/test_restricted_plugin.py`；专项`13 passed`、agent+dual-loop`69 passed`、完整回归`307 passed`

### DUAL-MODEL-001 分层CPU模型注册门

- 状态：`DONE`
- 依赖：DUAL-PLUGIN-001
- 优先级：P0
- 完成标准：Tier0/1训练—保存—加载—同预测验证；增量能力不误报；Tier2仅在依赖体积、4核8GB和协议验收通过后启用
- 新增官方门：实际加载平台父检查点并保留父链；提供独立预测入口；`checkpoint.npz`及全部模型产物不超过64 MiB；禁止从头训练伪装续训 `[O-PLATFORM-007]`
- 证据：`src/brace_msi/model_gate.py`、`python -m brace_msi checkpoint-predict`、`tests/dual_loop/test_model_gate.py`；专项`9 passed`，完整回归`316 passed`

### DUAL-INTEGRATION-001 十批受控双闭环集成

- 状态：`DONE`
- 依赖：DUAL-MODEL-001
- 优先级：P0
- 完成标准：统一CLI、RuntimeAdapter、证据路由、候选执行、门控、影子、审计和恢复贯通；任务重命名不改变决策
- 证据：`src/brace_msi/controlled_harness.py`、`python -m brace_msi controlled-loop-smoke`、`tests/dual_loop/test_controlled_harness.py`；分类/回归十轮、任务重命名不变性、中断续跑和CLI共`4 passed`，完整回归`320 passed`。该入口只接受本地`TaskStream`并显式写入`synthetic=true/formal_eligible=false`，不是官方父检查点续训或平台成绩。

### DUAL-EXPERIMENT-001 A/B/C合法顺序对照

- 状态：`DONE_MIXED`
- 依赖：DUAL-INTEGRATION-001；实验预注册
- 优先级：P1
- 完成标准：静态、固定更新、确定性双闭环和PyTRiO受控双闭环公平比较；十轮、至少三次真实实验链、资源和失败齐全；不消耗官方试运行
- 实际：A1/A2共18个确定性运行完成，均为官方父检查点真实续训、十批、官方试运行0次。A1暴露跨批遗忘；A2三任务均不低于静态，A/C改善、B保持静态，但改善幅度不足RC门。PyTRiO臂因确定性性能门未满足而按预注册未启动，避免无性能依据的Token消耗。证据：`D:/brace-msi-dual-loop/DUAL-EXPERIMENT-001-A1/`、`A2/`，专项`6 passed`、完整回归`326 passed`。

### GENERALIST-MODEL-001 父检查点增强的自建通用CPU候选

- 状态：`DONE`
- 依赖：DUAL-EXPERIMENT-001
- 优先级：P1
- 完成标准：不读取数据集名称，仅按分类/回归和数值schema构建父模型集成候选；先在公开train内部组折验证，保存真实父哈希、模型与资源证据；独立预测一致且总产物不超过64 MiB；至少两个任务相对父模型有可复核改善且第三项不发生灾难性退化
- 停止条件：训练内部组折未显示互补性、产物/CPU超限、无法证明实际使用父模型，或需要再次依据同一公开validation反复调参
- 证据：`generalist_model.py`、`generalist_experiment.py`、`generalist-predict`及`tests/dual_loop/test_generalist_model.py`；B/C固定父模型集成分别将RMSE 681.159833降至675.010677、52.868573降至49.336020，A候选由门控拒绝保留父模型。三产物115,392/239,908/200,613字节；专项8项、完整回归328项通过。结果：`D:/brace-msi-generalist/GENERALIST-MODEL-001-A1/`。

### DUAL-RC-001 新候选回归与容器验收

- 状态：`IN_PROGRESS`
- 依赖：GENERALIST-MODEL-001
- 优先级：P1
- 完成标准：Gas/Bearing/Engine超过静态，至少两项显著改善；零泄漏；完整回归；Docker小于2GB、4核8GB、无公网、无数据/权重/密钥；满足后才生成新RC
- 上传验收：归档必须由`docker save`生成并可`docker load`；分别记录镜像可用、模型校验、续训协议和评测状态，不把上传完成冒充通过 `[O-PLATFORM-007]`

```text
ROUTE-001(DONE)
  -> PYTRIO-001(DONE)
  -> PYTRIO-SFT-001(DONE)
  -> OFFICIAL-HARNESS-002(DONE)
  -> ACTION-SANDBOX-001(DONE)
  -> PERF-A-001(DONE) -> PERF-B-001(DONE) -> PERF-C-001(DONE)
  -> PAPER-METHOD-001
  -> LOOP-10-001
  -> FORMAL-COMPARE-001
  -> PLATFORM-TRIAL-DIAG-001(DONE)
  -> RC5-FAILCLOSED-001(DONE)
  -> FORMAL-RELEASE-001
```

以上是D-035当前正式执行图；下方旧任务图与任务记录保留作历史证据，不再决定当前路线。

## 当前正式路线任务

### ROUTE-001 正式路线锁定与SSOT同步

- 状态：`DONE`
- 依赖：O-PLATFORM-005、O-PYTRIO-001、B-PLATFORM-002、L-AUTH-009
- 优先级：P0
- 完成标准：正式路线、平台能力、未知接口、任务图、实验成功标准和风险边界写入既有SSOT；旧决策和负结果不删除
- 证据：`docs/FORMAL_ROUTE.md`、`D-035`至`D-037`及本节

### PYTRIO-001 PyTRiO结构化Agent客户端

- 状态：`DONE`
- 依赖：ROUTE-001
- 优先级：P0
- 完成标准：Qwen3.5-4B模型名和服务参数由配置/环境注入；Sampler调用可替换；严格解析结构化实验提案；记录Token、延迟和错误；不序列化密钥；服务缺失、超时、非法输出时返回可审计的确定性降级；自动测试不访问真实服务
- 停止条件：实现需要真实密钥、付费调用或猜测比赛专用字段；此时保留接口并用假客户端完成测试
- 证据：`src/brace_msi/pytrio_agent.py`、`tests/agent/test_pytrio_agent.py`、`tests/agent/test_pytrio_transport.py`；8项专项测试与完整回归`189 passed`；真实服务调用0次，凭据0项

### PYTRIO-SFT-001 BRACE结构化提案Sampler微调

- 状态：`DONE`（A3达到预注册门；按D-043永久停止继续LLM调参）
- 依赖：PYTRIO-001、Qwen3.5-4B位于当前PyTRiO模型白名单、用户已完成本机`trio login`
- 优先级：P0
- 完成标准：生成不含原始样本/密钥的版本化训练与留出评测语料；普通生成式SFT只监督assistant JSON；训练前后比较严格schema有效率、允许动作匹配率和预算安全性；保存持久化Sampler路径；本地记录数据哈希、SDK版本、超参数、loss、Token/步骤与失败；Sampler异常仍由确定性Harness降级
- 停止条件：当前账户无可用训练额度、真实付费训练未经用户确认、支持模型/API签名变化、语料含私有数据或密钥、或无法获得持久化Sampler路径；停止时保留本地准备与失败证据，不伪造训练完成
- 当前边界：官方Skill `pytrio-skill` v0.2.3已审计并安装；本地SDK为`pytrio 0.2.9`，实时白名单返回`Qwen/Qwen3.5-4B`和`Qwen/Qwen3.8-27B`。24条训练与12条archetype隔离留出语料已冻结。A1已产生真实采样和首个训练请求但失败；修复后完整回归235项通过，A2按L-AUTH-011从新目录继续。累计费用不得超过10元。
- 本地证据：`src/brace_msi/pytrio_sft.py`、`scripts/run_pytrio_sft.py`、`tests/agent/test_pytrio_sft.py`、`D:/brace-msi-pytrio/PYTRIO-SFT-001/`；独立代码审查无剩余Critical/Important。
- A1失败证据：`D:/brace-msi-pytrio/PYTRIO-SFT-001-A1/failure.json`；基础评测12/12完成，4,213输入Token、2,425输出Token，严格schema有效率0；远程首步已返回但在本地loss换算时因`TensorData`不能直接传给NumPy而中止，无持久化Sampler。已改为优先`to_numpy()`并新增真实SDK形态及远程请求/完成分离回归测试；专项20项、完整回归235项通过，未自动重试。
- A2成功证据：`D:/brace-msi-pytrio/PYTRIO-SFT-001-A2/`；18/18远程步完成、最终loss 0.009076、持久化Sampler已保存。原始后评测因精确Qwen终止标记被严格JSON解析器误判且保留；修复后同Sampler复评schema/budget 100%、action/tool/policy 66.67%，完整回归236项通过。下一停止条件为三任务受控对照完成并确认确定性降级不变。
- 三任务对照：`PYTRIO-HARNESS-001-A2`六运行均复算有效，PyTRiO与确定性最终指标完全相同；Sampler 30/30建议noop并由守卫完成最低候选，故任务尚不能以“Agent有额外价值”完成。按D-042只剩一次合规语料SFT及新留出，随后无论正负均停止LLM调参并确定正式默认。
- A3完成证据：`D:/brace-msi-pytrio/PYTRIO-SFT-001-A3/`；36/36远程步骤、最终loss 0.017709，新留出五项100%，真实A/B/C首轮3/3主动更新且0守卫覆盖。完整Sampler路径仅在Git外收据。
- 竞争候选证据：`D:/brace-msi-pytrio/PYTRIO-COMPETITIVE-001-A1/`；三任务各10轮/3候选，逐项复算`valid=true`，最终A/B/C为0.725695/637.180224/51.635999。两次预算耗尽后的额外建议被训练前沙箱拒绝。见`docs/results/PYTRIO-COMPETITIVE-001-A1.md`。

### OFFICIAL-HARNESS-002 官方训练器主Harness接入

- 状态：`DONE`
- 依赖：PYTRIO-001
- 优先级：P0
- 完成标准：A/B/C真实检查点、HistoryReader、Agent/确定性提案、隔离训练、独立评估、SafetyGate及部署/拒绝/回滚贯通；同一入口可关闭Agent；不修改原包
- 停止条件：需要正式平台事件字段时只阻塞RuntimeAdapter，不阻塞本地训练包工作流
- 证据：`src/brace_msi/official_agent_harness.py`、`python -m brace_msi official-agent-run`、7项专项测试、全量`196 passed`；`FORMAL-AGENT-SMOKE-001`在提交`24c70c8`上完成A/B/C各1个真实候选，3/3机器复算`valid=true`，详见`docs/results/FORMAL-AGENT-SMOKE-001.md`

### ACTION-SANDBOX-001 受控工具和配置修改

- 状态：`DONE`
- 依赖：OFFICIAL-HARNESS-002
- 优先级：P0
- 完成标准：工具白名单、参数schema、允许路径/配置键、候选隔离、预算预检和审计齐全；模型文本不得直接成为shell或Python代码
- 停止条件：任何路径能绕过预算、SafetyGate或写入原始包
- 证据：`src/brace_msi/action_sandbox.py`、`tests/agent/test_action_sandbox.py`及`official_agent_harness.py`集成；版本化工具注册表、任务兼容、参数白名单、训练前CPU估算、输出路径隔离、插件根/许可证/哈希检查通过5项专项测试；全量`201 passed`

### PERF-A-001 / PERF-B-001 / PERF-C-001 三任务独立性能优化

- 状态：`PERF-A-001 DONE`；`PERF-B-001 DONE`；`PERF-C-001 DONE`
- 依赖：ACTION-SANDBOX-001；各任务新实验预注册
- 优先级：P1
- 完成标准：分别完成数据/误差/阶段/资源诊断，建立静态、固定更新和BRACE无大模型对照，运行有明确假设的低成本优化；不能仅凭训练集或已反复使用的单次验证指标宣布成功
- 停止条件：独立确认数据未冻结、原始数据指纹变化、或连续候选无增益且作用机制不成立
- `PERF-A-001`证据：`PERF-A-OVER-001`排除简单源域过采样；`PERF-A-REPLAY-001`在因果Batch 2—7流中比较静态、`current_only`与两种回放，15个候选和父链审计通过；复杂回放被简单当前批次更新支配，按D-016停止扩展。见`docs/results/PERF-A-REPLAY-001.md`。
- `PERF-B-001`证据：`REGRESSION-SPRINT-001` B矩阵9/9成功，整轴承确认门通过；冻结`e5-lr3p0`，公开门控RMSE 681.159833→637.180224、MAE 563.105841→540.456251，机器校验有效；按D-039停止搜索。
- `PERF-C-001`入口：B完成或停止后复用同一矩阵执行C；按整发动机FD001+2/FD003/FD004训练/开发/确认，不新增算法模块。
- `PERF-C-001`证据：同一矩阵9/9成功，整发动机确认门通过；冻结`e5-lr1p0`，公开门控RMSE 52.868573→52.367735、MAE 38.899830→38.322199，机器校验有效；按D-039停止搜索。

### PAPER-METHOD-001 高价值开源方法筛选、复现与融合

- 状态：`DONE`（独立`codex/paper-fusion-sprint`分支；D-045至D-047）
- 依赖：至少一个PERF任务给出可测量瓶颈
- 优先级：P1
- 完成标准：论文贡献、官方代码、许可证、CPU/内存、官方模型兼容性审计通过；独立实验ID下完成基线、复现、消融和失败记录；只有实测有效方法进入主Harness
- 停止条件：无明确瓶颈、许可证不清、依赖GPU/公网、或4核8GB预算不成立
- 完成证据：`PAPER-FUSION-SPRINT-001`完成最多三项来源、train内部组折选型和冻结后一次公开validation；A/B负结果保留，C融合RMSE 42.330230通过相对RC3严格改善门。机器验证`valid=true`；RC4容器与归档证据见`docs/results/RC4_CONTAINER_ACCEPTANCE.json`、`docs/results/RC4_VERIFICATION.json`，完整结论见`docs/results/PAPER-FUSION-SPRINT-001.md`。

### LOOP-10-001 PyTRiO+BRACE十轮自主闭环

- 状态：`DONE`（本地确定性闭环；真实PyTRiO效果仍属外部对照缺口）
- 依赖：三项PERF任务完成最低可用候选；PAPER方法非强制依赖
- 优先级：P2
- 完成标准：每任务十轮历史读取、提案、检查、训练/跳过、评估、门控和记录；每任务至少三次真实候选；无意义训练允许跳过但必须记录；服务失败可完成确定性降级

### FORMAL-COMPARE-001 正式对照与消融

- 状态：`DEFERRED`（D-039冲刺不新增训练；已有静态/固定/BRACE与负结果证据，真实PyTRiO对照待平台）
- 依赖：LOOP-10-001
- 优先级：P3
- 完成标准：官方静态、固定更新、BRACE无大模型、PyTRiO+BRACE及有效论文方法在同一可见性和预算下比较；报告主指标、最差阶段、恢复、CPU/RSS、Token/费用、接受/回滚；负结果保留

### PLATFORM-TRIAL-DIAG-001 首次官方试运行根因与证据固化

- 状态：`DONE`
- 依赖：O-PLATFORM-006、用户确认RC4尚未提交
- 优先级：P0
- 完成标准：区分旧提交与RC4；登记Token、隐藏指标和次数；定位可复现的零Token完成路径；不得猜测镜像绑定
- 证据：`docs/source_notes/PLATFORM_TRIAL_V1_2026-11-13.md`、`PLATFORM-TRIAL-V1`实验条目、D-048、R-034；附件SHA-256 `8B7B5CEC...BBA5368`

### RC5-FAILCLOSED-001 Agent失败关闭修复候选

- 状态：`DONE`
- 依赖：PLATFORM-TRIAL-DIAG-001
- 优先级：P0，唯一当前任务
- 完成标准：正式CLI无隐式provider默认值；PyTRiO传输/解析失败与Harness provider异常不能静默回退；本地专项及完整回归通过；基于修复提交构建新的Linux镜像并保留RC4归档不变
- 停止条件：正式平台要求与失败关闭冲突、完整回归失败无法修复、或容器验收失败；失败时保留RC4与本任务证据，不上传平台
- 证据：红阶段先后复现静默回退和未受控SDK等待；修复后完整回归`271 passed`。linux/amd64镜像在4核8GB断网下完成Smoke，严格PyTRiO负向测试12.726秒退出、文件0项、未静默回退；归档SHA-256 `daf42786...307d32`并经`docker load`验证。详见`docs/results/RC5_CONTAINER_ACCEPTANCE.json`与`RC5_VERIFICATION.json`

### FORMAL-RELEASE-001 正式环境与交付

- 状态：`BLOCKED_EXTERNAL`（基础模型兼容候选本地完成；平台上传/试运行仍由用户控制）
- 依赖：FORMAL-COMPARE-001、正式SDK/SwanLab规范
- 优先级：P4
- 完成标准：Docker构建、4核8GB断网、正式RuntimeAdapter、最终模型重训SwanLab记录、十轮无人值守、干净环境独立复现及交付审计全部通过
- 停止条件：外部规范或容器环境缺失时明确`BLOCKED`，不得制造通过证据
- 本地证据：RC2运行时代码/全新venv均`221 passed`，`pip check`、编译、静态上下文与确定性源码归档通过；实际镜像170,356,869字节，linux/amd64、UID 10001、无禁入文件，4核8GB断网Smoke完成3候选；最终`docker save`归档SHA-256为`7b64490b0456c4b36bdc6189f34c9ce5e372894b911d76a3b40a6e8142e09327`，证据见`docs/results/RC2_CONTAINER_ACCEPTANCE.json`。
- RC3本地证据：最终代码回归`246 passed`、打包前全新venv`243 passed`；PyTRiO0.2.9依赖无冲突；实际镜像240,579,085字节、linux/amd64、UID10001、无Torch/数据/权重/密钥；4核8GB断网双协议Smoke完成3/4候选；`docker save`归档SHA-256为`0daef2e0e66cd2d3bc809a5d836a03020d1f90d677df91830fedc4feeb6d325a`并已重载。证据见`docs/results/RC3_CONTAINER_ACCEPTANCE.json`。
- RC4本地证据：最终代码回归`264 passed`；实际镜像240,701,023字节、linux/amd64、UID10001、无Torch/数据/权重/密钥；4核8GB断网完成Engine冻结候选训练，峰值RSS 3,198,783,488字节；`docker save`归档240,723,968字节，SHA-256为`97bb0a9fcfed688ba1b7feadadf09528e232fea578d06a1d782f2dccee306dfa`并已重载。证据见`docs/results/RC4_CONTAINER_ACCEPTANCE.json`与`docs/results/RC4_VERIFICATION.json`。
- 基础模型兼容进度：平台重复拒绝持久化Sampler而接受Qwen3.5-4B基础模型后，`0.4.1rc1`已通过TDD专项27项与完整回归271项；CLI允许`provider=pytrio/model_path=None`，仍保留显式provider、失败关闭和非零调用要求。单次本机在线Smoke无响应且无收据，已按预注册停止，不写成通过；本地镜像验收见下一条。
- RC6本地证据：`0.4.1rc1`镜像linux/amd64、240,662,396字节、UID10001、无Torch/数据/权重/密钥；4核8GB断网Synthetic Smoke完成。基础模型入口无Sampler路径时在断网环境8.696秒明确失败关闭且运行文件0项；归档240,685,056字节，SHA-256 `63fff363...54e48e`并经`docker load`验证。见`RC6_CONTAINER_ACCEPTANCE.json`与`RC6_VERIFICATION.json`。
- 外部剩余：正式SDK事件映射、评分细则和比赛SwanLab规范；平台上传、校验和试运行属于用户控制的外部写操作。未满足前不得标记全量DONE。

```text
DOC-001
  -> CORE-001 -> SDK-001 -> CORE-002 -> CORE-003
  -> DATA-001 -> BASE-001/BASE-002/BASE-003
  -> CORE-004 -> CORE-005 -> LOG-001
  -> INT-001 -> PKG-001 -> REPRO-001 -> MAT-001
  -> EXP-001 -> EXP-002 -> PAPER-001

CORE-001
  -> LOCAL-DATA-001 -> LOCAL-CORE-001 -> LOCAL-LOOP-001
  -> LOCAL-SMOKE-001 -> LOCAL-EXP-001

LOCAL-EXP-001
  -> SYS-001 -> SYS-002 -> SYS-003 -> SYS-004 -> SYS-005

SYS-005
  -> RR-001 -> RR-002 -> RR-003 -> RR-004 -> RR-005
```

## P0：11月13日前最低版本

### DOC-001 文档与恢复体系

- 状态：`DONE`
- 依赖：无
- 产物：`AGENTS.md`、`docs/`正式文档、初始文件审计
- 完成标准：要求文档全部存在；内部链接有效；证据分类明确；新会话恢复步骤可执行；未修改原始数据
- 停止条件：发现原始文件缺失或需要覆盖历史文件
- 证据：`docs/`文档树；必需文件、相对链接、证据ID和原始数据哈希一致性检查通过；Git基线见首次提交

### CORE-001 模拟SDK事件协议与防泄漏状态机

- 状态：`DONE`
- 依赖：DOC-001
- 优先级：P0
- 完成标准：支持两种候选协议；同一评分样本不能先用标签训练；批次只能按适配器允许的事件推进；单元测试覆盖非法顺序
- 停止条件：需要猜测正式SDK字段或调用真实服务
- 备注：只构建模拟接口，不训练模型
- 实施计划：`docs/plans/CORE-001.md`
- 证据：`src/brace_msi/protocol/__init__.py`、`tests/protocol/test_state_machine.py`；`D:\anaconda3\python.exe -m pytest -q --tb=short`于2026-11-06通过，结果为`13 passed`

### SDK-001 正式平台与SDK核验

- 状态：`BLOCKED`
- 依赖：CORE-001、官方平台开放
- 优先级：P0
- 完成标准：登记SDK版本、事件顺序、数据模式、输出格式、标签规则、模型白名单、计费、迭代定义和SwanLab机制；更新全部H项
- 停止条件：只有转写或二手消息，没有正式文档/可运行SDK
- 当前阻塞：截至2026-11-06，仓库内没有正式SDK、平台文档或可运行平台入口；不能仅依据宣讲转写解除

### LOCAL-DATA-001 代理数据审计与冻结切分

- 状态：`DONE`
- 依赖：CORE-001、L-AUTH-001
- 优先级：P0，本地独立路径
- 完成标准：Gas与C-MAPSS结构、哈希、任务类型、标签构造、组/时间字段和冻结切分有代码与审计证据；训练/开发/密封样本互斥；原始数据只读
- 停止条件：压缩包哈希变化、数据损坏、标签含义无法从本地资料确认
- 实施计划：`docs/plans/LOCAL-PROXY-PIPELINE.md` Task 1
- 证据：`src/brace_msi/data/`、`scripts/audit_proxy_data.py`、`tests/data/`、`docs/source_notes/PROXY_DATA_AUDIT.md`；完整测试`23 passed`

### LOCAL-CORE-001 本地模型、预算、监测与SafetyGate

- 状态：`DONE`
- 依赖：LOCAL-DATA-001
- 优先级：P0，本地独立路径
- 完成标准：通用分类/回归模型能力、增量/重拟合、漂移与性能证据、训练前预算、候选评估、部署/拒绝均有自动测试
- 停止条件：需要未来批次信息或重依赖不符合CPU路线
- 实施计划：`docs/plans/LOCAL-PROXY-PIPELINE.md` Task 2
- 证据：`src/brace_msi/modeling.py`、`evidence.py`、`budget.py`、`safety.py`、`resources.py`及`tests/core/`；完整测试`34 passed`

### LOCAL-LOOP-001 本地策略与无人值守闭环

- 状态：`DONE`
- 依赖：LOCAL-CORE-001
- 优先级：P0，本地独立路径
- 完成标准：静态、性能触发和BRACE策略使用同一数据可见性运行；动作由证据选择；日志可审计且不含原始特征
- 停止条件：无法公平共享初始模型、切分或预算
- 实施计划：`docs/plans/LOCAL-PROXY-PIPELINE.md` Task 3
- 证据：`src/brace_msi/policies.py`、`runner.py`、`audit.py`及`tests/loop/`；完整测试`42 passed`

### LOCAL-SMOKE-001 代理数据低成本Smoke Test

- 状态：`DONE`
- 依赖：LOCAL-LOOP-001
- 优先级：P0，本地独立路径
- 完成标准：Gas与FD001均完成三策略小样本运行；至少出现一次增量和一次重拟合候选；资源、门控、失败和脱敏日志齐全
- 停止条件：任一数据防泄漏检查失败或运行超过预注册Smoke预算
- 实施计划：`docs/plans/LOCAL-PROXY-PIPELINE.md` Task 4
- 证据：执行提交`64ccce2`；`configs/local_smoke.json`、`docs/results/LOCAL-SMOKE-001.md`及本地忽略产物；六个运行完成，动作计数增量10/重拟合3，机器验收通过

### LOCAL-EXP-001 完整代理基线与迭代比较

- 状态：`DONE`
- 依赖：LOCAL-SMOKE-001
- 优先级：P0，本地独立路径
- 完成标准：两任务完成静态、性能触发和BRACE配对比较；全局至少三次真实候选训练/评估；分类与回归阶段指标及CPU资源有可复核产物
- 停止条件：Smoke未通过、密封段已被用于调参或策略被简单基线全面支配后仍试图增加模块
- 实施计划：`docs/plans/LOCAL-PROXY-PIPELINE.md` Task 5
- 证据：执行提交`f9647dd`；DEV与唯一密封运行均6/6完成并机器验收通过；`docs/results/LOCAL-EXP-001.md`；全局增量9/重拟合5

### CORE-002 TaskBootstrap

- 状态：`BLOCKED`
- 依赖：SDK-001
- 优先级：P0
- 完成标准：官方初始模型、合法初训数据、官方弃权/默认路径均有明确处理；不兼容任务拒绝跨任务复用
- 停止条件：SDK未定义新任务首批初始化方式

### SYS-001 平台无关TaskBootstrap、CPU模型池与注册表

- 状态：`DONE`
- 依赖：LOCAL-EXP-001、L-AUTH-002
- 优先级：P0，本地正式候选路径
- 完成标准：任务描述与兼容性检查、未知同领域任务合法初始化、四类CPU模型能力适配、候选配置、原子注册与回滚均有自动测试；持久化预测一致
- 停止条件：实现需要猜测官方SDK字段或打开已消费密封段
- 实施计划：`docs/plans/FORMAL-CANDIDATE-SYSTEM.md` Task 1
- 证据：`src/brace_msi/bootstrap.py`、`modeling.py`、`registry.py`和`tests/system/test_bootstrap_models_registry.py`；四类模型在分类/回归上完成构造与预测，非法增量调用、任务不兼容、持久化与回滚均有测试；完整测试`58 passed`

### SYS-002 证据路由、预算动作选择与有限HPO

- 状态：`DONE`
- 依赖：SYS-001
- 优先级：P0，本地正式候选路径
- 完成标准：数据质量/性能/漂移/历史/预算证据统一路由；回放、族切换、有限HPO和自动停止均受训练前预算约束；失败候选不污染稳定模型
- 停止条件：简单确定性策略被替换为无法审计或运行时动态代码
- 实施计划：`docs/plans/FORMAL-CANDIDATE-SYSTEM.md` Task 2
- 证据：`src/brace_msi/decision.py`、`search.py`、扩展的`budget.py`/`policies.py`及`tests/system/test_decision_search.py`；数据质量阻断、证据升级、预算余量、有限搜索、耐心停止、回放上限和稳定模型隔离均通过测试；完整测试`64 passed`

### SYS-003 无人值守Harness、恢复与记录接口

- 状态：`DONE`
- 依赖：SYS-002
- 优先级：P0，本地正式候选路径
- 完成标准：两种模拟协议、检查点恢复、CLI、公开记录队列和私有审计组成可无人值守运行的统一Harness；恢复不重复已提交训练
- 停止条件：需要把未确认的SwanLab同步方式写成正式事实
- 实施计划：`docs/plans/FORMAL-CANDIDATE-SYSTEM.md` Task 3
- 证据：`src/brace_msi/harness.py`、`checkpoint.py`、`recording.py`、`cli.py`、`simulation.py`和`tests/system/test_unified_harness.py`；两种协议、可替换适配器、三次真实候选、故障拒绝、批次级恢复、私有审计、公开聚合队列和非交互CLI均通过测试；完整测试`71 passed`

### SYS-004 Docker、入口与静态HTML报告

- 状态：`DONE`
- 依赖：SYS-003
- 优先级：P0，本地正式候选路径
- 完成标准：Dockerfile、一键入口、锁定依赖、合规清单、接入说明和离线HTML报告齐全；构建上下文小于2GB且不含数据/权重/密钥
- 停止条件：本机没有Docker时仅阻塞实际镜像构建，不阻塞文件与静态验收
- 实施计划：`docs/plans/FORMAL-CANDIDATE-SYSTEM.md` Task 4
- 证据：`Dockerfile`、`.dockerignore`、`requirements.lock`、`run.ps1`/`run.sh`、`src/brace_msi/reporting.py`、`packaging.py`、`docs/RUNBOOK.md`、`SDK_INTEGRATION.md`和`OPEN_SOURCE_COMPLIANCE.md`；静态上下文审计73文件/251,854字节、无禁入文件；PowerShell一键Smoke完成3次候选；完整测试`74 passed`。该阶段当时没有容器运行时；后续真实镜像证据已由`PKG-RUNTIME-001`/`RR-001`补齐。

### SYS-005 三任务模拟正式评测与资源验收

- 状态：`DONE`
- 依赖：SYS-004
- 优先级：P0，本地正式候选路径
- 完成标准：Gas开发流、FD001开发流、明确标注的合成轴承流完成初始化、至少三次候选、部署/拒绝、故障回滚、恢复、4核8GB监测、日志和HTML证据包；不打开旧密封段
- 停止条件：任何泄漏检查失败、资源超限或需要重用已消费密封段选型
- 实施计划：`docs/plans/FORMAL-CANDIDATE-SYSTEM.md` Task 5
- 证据：A1`ce3e907`因真实候选误计标记INVALID并保留；A2执行`7ef3829`，三任务真实候选4/4/3，动作覆盖增量7、回放1、有限HPO3；4核亲和性、RSS、幂等日志、注册表和HTML经独立验收；完整测试`80 passed`；详见`docs/results/LOCAL-FORMAL-SIM-001.md`

### PKG-RUNTIME-001 实际Docker镜像构建与4核8GB容器验收

- 状态：`DONE`
- 依赖：SYS-004、本机或可用环境提供Docker/Podman运行时
- 优先级：P0，外部环境阻塞
- 完成标准：实际构建镜像并测量小于2GB；`--network=none --cpus=4 --memory=8g`完整运行；镜像内无数据、权重和密钥
- 停止条件：没有容器运行时，不得用静态上下文大小冒充镜像大小
- 证据：2026-11-12在Docker Desktop 28.5.1 / linux/amd64构建`brace-msi:0.2.0rc2`；镜像170,356,869字节，非root UID 10001，无数据/权重/密钥禁入文件；4核8GB、无网络Smoke完成3个真实协议候选；归档与哈希见`docs/results/RC2_CONTAINER_ACCEPTANCE.json`。

### RR-001 实际容器运行时验收

- 状态：`DONE`
- 依赖：SYS-005、L-AUTH-003
- 优先级：P0，Release Readiness
- 完成标准：实际Linux镜像小于2GB；4核8GB、断网容器完成非密封Smoke；镜像内无数据、权重和密钥
- 停止条件：本机无Docker/Podman/可用Linux容器运行时，或安装需要重启/管理员交互
- 执行清单：`docs/plans/RELEASE-READINESS.md`任务1
- 证据：2026-11-12启用WSL/VMP并重启后，Docker Engine 28.5.1可用；干净提交`e28113c`上缓存重建、镜像审计、4核8GB断网Smoke、`docker save`及重新加载均通过。旧阻塞记录保留在研究进度，当前机器证据见`docs/results/RC2_CONTAINER_ACCEPTANCE.json`。

### RR-002 干净环境依赖与完整回归

- 状态：`DONE`
- 依赖：RR-001完成或有可核验的BLOCKED结论
- 优先级：P0，Release Readiness
- 完成标准：隔离环境只按锁文件安装；`pip check`、完整测试、CLI Smoke、编译及包审计均有日志
- 停止条件：锁文件无法在支持的Python/Linux范围解析，或需要修改算法才能安装
- 执行清单：`docs/plans/RELEASE-READINESS.md`任务2
- 证据：全新`tmp/release-venv-final`仅安装`requirements.lock`、`requirements-dev.lock`及本项目；`pip check`无冲突，`81 passed`，两协议CLI Smoke分别完成3/4候选；CPython 3.12 manylinux二进制轮子解析成功。发布审计发现并修复`psutil==5.9.0`无cp312 Linux轮子问题。

### RR-003 SwanLab离线适配与同步准备

- 状态：`DONE`
- 依赖：RR-002
- 优先级：P0，Release Readiness
- 完成标准：可选依赖、离线记录、公开字段白名单、显式同步命令和失败降级均有自动测试与文档
- 停止条件：需要猜测比赛专用字段、自动上传私有数据或使用未知凭据
- 执行清单：`docs/plans/RELEASE-READINESS.md`任务3
- 证据：`swanlab_adapter.py`、CLI离线导出/同步命令、4项自动测试及`SWANLAB_INTEGRATION.md`；真实SwanLab 0.10.4离线生成`run-*`目录并记录8条聚合事件，`pip check`无冲突。未执行云端同步。

### RR-004 正式SDK接入适配器准备

- 状态：`DONE`
- 依赖：RR-002
- 优先级：P0，Release Readiness
- 完成标准：可配置字段映射、动态官方模块边界、协议契约测试和接入检查表齐全；核心Harness不依赖官方包
- 停止条件：任何实现需要编造官方字段、标签权限、模型服务或错误语义
- 执行清单：`docs/plans/RELEASE-READINESS.md`任务4
- 证据：`official_sdk.py`、`sdk-contract-check`、5项契约测试、清单模板及扩展后的`SDK_INTEGRATION.md`；缺模块、非法清单、接口不完整均fail-closed。实际字段和数据出入站仍归`SDK-001`阻塞。

### RR-005 Release Candidate最终审计

- 状态：`DONE`
- 依赖：RR-003、RR-004及RR-001可核验结论
- 优先级：P0，Release Readiness
- 完成标准：生成版本清单、哈希、交付审计、完整测试证据和阻塞表；Git提交且不合并main
- 停止条件：存在未登记的P0失败、证据与文档冲突或工作树不干净
- 执行清单：`docs/plans/RELEASE-READINESS.md`任务5
- 证据：`BRACE-MSI-0.1.0rc1`、确定性源码打包器及发布树测试；全新环境安装的wheel实际CLI完成两协议Smoke和SwanLab 0.10.4离线导出，完整回归`95 passed`、`pip check`通过、上下文124文件/487,662字节且无禁入文件。该任务完成时RR-001仍阻塞；当前RC2已在后续任务中补齐真实容器证据。

### CORE-003 模型能力声明与CPU模型适配

- 状态：`BLOCKED`
- 依赖：CORE-002
- 优先级：P0
- 完成标准：模型能力可机读；批量模型不调用`partial_fit`；保存/加载一致；资源上限可配置
- 停止条件：正式任务类型或指标仍未知

### DATA-001 官方三任务数据审计

- 状态：`BLOCKED`
- 依赖：官方数据发布
- 优先级：P0
- 完成标准：数据字典、任务类型、标签、组/时间字段、指标、批次协议、许可证和哈希登记；泄漏风险清单完成
- 停止条件：数据来源或许可证不明
- 已完成：2026-11-10完成三套本地原件只读清点、重复数据逐文件哈希比对和XJTU-SY分卷完整性/结构审计；证据见`docs/source_notes/OFFICIAL_DATA_INTAKE_2026-11-10.md`。
- 已更新：O-PLATFORM-001已确认三任务目标、单位和主指标，轴承目标不再未知。
- 新证据：O-PLATFORM-005已提供三任务训练器、真实初始权重、公开train/validation、任务说明与指标；本任务开始验证清单、schema、父检查点和续训行为。
- 已完成子项：训练包原目录只读复核、关键SHA-256、数据schema/分组/ID隔离、NPZ结构、公开基线复算及随包测试已审计；证据见`docs/source_notes/OFFICIAL_TRAINING_PACKAGE_AUDIT_2026-11-11.md`。
- 当前阻塞：训练包本地审计子项已完成；正式SDK/批次协议、隐藏测试、完整评分公式、平台资源计量和许可证仍缺失 `[H-006]`。这些外部缺口阻塞完整DATA-001验收和正式平台成绩，但不阻塞官方训练包本地续训。

### OFFICIAL-PKG-001 官方训练包适配与十轮续训

- 状态：`DONE`
- 依赖：训练包审计、书面规格与实施计划均已批准；忽略不影响本地续训的外部缺口
- 优先级：P0，官方训练包本地开发路径
- 完成标准：原包只读哈希清单；A/B/C真实检查点Smoke；单次固定低成本续训对照（内部ID`performance_triggered`）与BRACE各10个候选适应决策轮；BRACE每任务至少3次真实候选；1+1/连续2 epoch继承证明、拒绝候选父链隔离、验证使用账本、训练前后资源估算、门控、恢复、静态报告和机器验收齐全。
- 当前证据：Task 1只读清单审计器已实现；真实A/B/C拓扑、关键哈希、行数及ID/设备组隔离通过，篡改检查点在训练前被拒绝。证据：`tests/official_package/test_manifest.py`、`src/brace_msi/official_package.py`。
- 当前证据：Task 2隔离训练适配器已实现；原版A训练器的连续2 epoch与1+1恢复训练产生逐数组相同检查点和相同预测，父/子epoch、step、权重、Adam、标准化及输入哈希均核验；超时保留失败收据，包代码审计后变化会在子进程前拒绝。证据：`tests/official_package/test_trainer.py`、`src/brace_msi/official_trainer.py`。
- 当前证据：Task 3十轮监督器已实现；十轮明确为候选适应决策，BRACE最低候选、严格改善门控、拒绝候选父链隔离、验证使用账本、原子状态和五轮后恢复均通过测试。证据：`tests/official_package/test_rounds.py`、`src/brace_msi/official_rounds.py`。
- 当前证据：Task 4三任务套件与CLI已实现；训练前/Smoke后资源估算、3个Smoke、6个策略作业、全局验证账本、B包上游测试缺口、静态Markdown/HTML和机器验收通过自动测试。证据：`tests/official_package/test_suite.py`、`src/brace_msi/official_package_suite.py`、`scripts/run_official_package_dev.py`。
- 完成证据：执行提交`34098bf`；运行根`D:/brace-msi-official-package/OFFICIAL-PACKAGE-DEV-001/`；9/9作业、15候选、六策略各10轮、BRACE每任务3候选，`validation.json`为`valid=true`。结果与负证据见`docs/results/OFFICIAL-PACKAGE-DEV-001.md`。
- 停止条件：见`docs/superpowers/specs/2026-11-11-official-package-integration-design.md`。
- 边界：`official_package=true`、`official_scoring_ready=false`；不运行SwanLab、不提交平台、不使用隐藏测试、不消耗平台试跑次数、不修改RC标签。

### FORMAL-DEV-001 最新规则对齐无人值守训练

- 状态：`DONE`
- 依赖：O-PLATFORM-001至004、L-AUTH-007、已有三数据加载器与统一Harness
- 优先级：P0，正式平台前开发路径
- 完成标准：三任务使用参数量匹配的可替换MLP本地初始检查点；各自构造10个合法开发批次；静态、性能触发和BRACE共享初始检查点并串行运行；官方指标、最差阶段、恢复速度、稳定性和资源分别记录；前三个实验人工健康检查通过后后台独立继续；自动生成汇总分析和下一轮冻结建议；全部产物可断点恢复。
- 停止条件：原始哈希变化、训练/开发/密封身份交叉、非有限指标、超过4核8GB本地观测边界、输出目录已有冲突证据，或需要把本地重建权重冒充平台权重。
- 边界：`official_rules_aligned=true`、`official_checkpoint=false`；不消耗平台试运行，不提交平台，不运行SwanLab，不打开既有密封段，不改变RC标签。
- 实施计划：`docs/plans/OFFICIAL-RULES-ALIGNED-TRAINING.md`
- 证据：实现提交`512d477`、报告提交`9c7bdba`；`D:/brace-msi-official-dev/OFFICIAL-RULES-ALIGNED-DEV-001/validation.json`为`valid=true`；9/9实验各10轮完成，前三实验健康检查有效，后台PID 6084正常退出；汇总见`docs/results/OFFICIAL-RULES-ALIGNED-DEV-001.md`；完整回归116项通过。
- 后续：按D-027停止复用同一开发流调参；平台训练包与初始权重到达后另建正式实验ID，`DATA-001`继续`BLOCKED`。

### XJTU-LOCAL-001 新增轴承数据本地串行训练

- 状态：`DONE`
- 依赖：DATA-001已完成的XJTU-SY只读结构审计、L-AUTH-006
- 优先级：P0，本地独立路径
- 完成标准：冻结按轴承分组且互斥的初训/开发/密封切分；完成可恢复的独立CSV特征缓存；静态强CPU基线、性能触发和BRACE串行运行；前三个实验轮次经日志/有限指标/资源检查；后台进程可脱离会话继续并保存状态；最终保留本地审计与失败证据。
- 停止条件：原始分卷哈希变化、分组交叉、特征使用未来寿命/未来批次、非有限数据无法清理、派生空间不足，或运行目录包含已有证据且可能被覆盖。
- 边界：`local_development_only=true`；不运行SwanLab，不改变RC标签，不复训Gas/FD001，不把自定RUL协议称为官方任务或成绩。
- 实施计划：`docs/plans/XJTU-LOCAL-SERIAL.md`
- 证据：实现提交`2460577`、公平切分与验收修正`2e29ae7`；`D:/brace-msi-xjtu/XJTU-LOCAL-DEV-001/`；A1因静态/策略初训可见性不一致标记INVALID并保留，A2`experiments-a2/`完成5/5轮、3次真实候选且`validation-experiments-a2.json`为`valid=true`；聚合结果见`docs/results/XJTU-LOCAL-DEV-001.md`；完整回归101项通过。

### BASE-001/002/003 三任务静态基线

- 状态：`BLOCKED`
- 依赖：DATA-001、CORE-003
- 优先级：P0
- 完成标准：气体、轴承、RUL分别完成官方静态基线和强CPU基线；配置、资源和本地审计齐全。SwanLab正式记录仅在最终工程模型重训阶段生成 `[D-023]`
- 停止条件：任一任务的数据切分或指标无法确认

### CORE-004 候选实验与预算账本

- 状态：`BLOCKED`
- 依赖：CORE-003、SDK-001
- 优先级：P0
- 完成标准：真实候选事件、训练前预算、超时降级、至少三次迭代计数均可配置和审计
- 停止条件：官方迭代计数仍存在会导致资格风险的歧义

### CORE-005 三层SafetyGate与回滚

- 状态：`BLOCKED`
- 依赖：CORE-004、BASE任务
- 优先级：P0
- 完成标准：硬约束、统计评估、部署决策分离；失败候选不污染稳定模型；原子回滚通过故障测试
- 停止条件：没有合法验证数据或检查点无法恢复

### LOG-001 SwanLab与私有审计

- 状态：`BLOCKED`
- 依赖：SDK-001、CORE-004
- 优先级：P0
- 完成标准：官方要求字段完整；公开/私有记录隔离；断网缓存与正式同步机制经官方确认
- 停止条件：同步方案可能泄露B包或不被官方认可
- 阶段边界：当前不执行。等待平台提供规范并冻结最终工程模型后，通过正式重新训练一次性生成所需记录 `[L-AUTH-005]` `[D-023]`。

### INT-001 端到端无人值守闭环

- 状态：`BLOCKED`
- 依赖：BASE任务、CORE-005、LOG-001
- 优先级：P0
- 完成标准：三任务从初始化到三次候选、部署/拒绝、回滚和报告均无需人工操作
- 停止条件：任一基础资格门槛失败

### PKG-001 受限Docker镜像

- 状态：`DONE`
- 依赖：INT-001
- 优先级：P0
- 完成标准：Linux 4核8GB、无公网运行；镜像小于2GB；无模型权重、Embedding和密钥
- 停止条件：镜像或运行时违反正式限制
- 证据：`brace-msi:0.2.0rc2`为linux/amd64、170,356,869字节、非root、无打包数据/权重/Embedding/密钥；在`--network=none --cpus=4 --memory=8g --pids-limit=256`下完成Smoke，归档可由`docker load`重新加载。

### REPRO-001 独立复现

- 状态：`BLOCKED`
- 依赖：PKG-001
- 优先级：P0
- 完成标准：队友在干净环境按文档一键运行；产物哈希和关键指标一致
- 停止条件：需要作者手工修复或隐含环境状态

### MAT-001 最低提交材料

- 状态：`DONE`
- 依赖：RC3本地容器与干净环境验收（已完成）；正式SDK不是作品材料生成的前置依赖
- 优先级：P0
- 完成标准：镜像、Harness/配置/依赖与复现说明、SwanLab最终聚合训练记录、设计论证、作品说明书、源码仓库和开源合规材料齐全；不泄露密钥/权重/原始数据
- 停止条件：GitHub或SwanLab认证失效、公开记录出现敏感字段、或提交平台新增强制模板/字段
- 证据：`docs/SUBMISSION_DOCUMENT.md`、`docs/SUBMISSION_CHECKLIST.md`、`docs/results/SWANLAB-FINAL-001.md`；DOCX/PDF位于`D:/brace-msi-release/BRACE-MSI-0.3.0rc3-submission-materials/`；GitHub分支与RC3标签已推送；SwanLab公开项目3项实验均`FINISHED`。项目源码许可证仍由权利人决定，当前材料不虚构许可证。

## P1：企业赛竞争力

### UNIFIED-POLICY-001 三任务统一策略优化

- 状态：`STOPPED`
- 依赖：OFFICIAL-PKG-001、FORMAL-DEV-001、XJTU-LOCAL-001、L-AUTH-008
- 优先级：P0，当前唯一执行任务
- 完成标准：实现身份盲、无量纲的共享策略核心；冻结三阶段manifest；完成三个任务级leave-one-task-out fold；公平比较静态、固定低成本、性能触发和BRACE；冻结一组共享配置；末期只测且明确历史暴露等级；生成资源、失败、停止条件和机器验收证据。
- 停止条件：样本/设备组泄漏、策略读取任务身份、末期数据提前访问、BRACE被简单策略在至少两个任务级留出fold上全面支配、资源超限，或需要使用官方测试反馈继续调参。
- 设计：`docs/superpowers/specs/2026-11-11-unified-policy-optimization-design.md`
- 实施计划：`docs/superpowers/plans/2026-11-11-unified-policy-optimization.md`
- 边界：不修改D-031冻结实验、RC标签、main或原始数据；Gas/FD001末期为历史暴露，XJTU末期首次打开前必须预注册；不运行SwanLab和平台SDK。
- 当前证据：`UNIFIED-POLICY-OPT-001-DEV-A1`已完成81/81作业并严格验收`valid=true`；复杂BRACE在3/3留出fold无性能优势且资源更高。D-035已替代该路线为当前正式方向；不执行末期测试，配置、报告和负结果继续保留。报告见`docs/results/UNIFIED-POLICY-OPT-001.md`。

### LOCAL-BASE-STRONG 强静态CPU基线补充

- 状态：`BLOCKED`
- 依赖：新的未见官方数据或新的合法密封代理切分
- 完成标准：分类与回归分别预注册至少一个强静态CPU模型，并在未见密封段与同族静态、简单触发和BRACE公平比较
- 停止条件：只能复用已经查看的`LOCAL-EXP-001`密封段；此时仅可标记为事后探索，不能补写成确认性基线
- 当前阻塞：Gas批次8–10和FD001发动机81–100已在2026-11-06查看；正式数据尚未发布

### EXP-001 性能触发式强对照

- 状态：`BLOCKED`
- 依赖：INT-001
- 完成标准：同数据可见性、初始模型和资源下完成性能触发式低成本更新
- 停止条件：协议无法公平对齐

### EXP-002 BRACE-MSI关键比较与消融

- 状态：`BLOCKED`
- 依赖：EXP-001
- 完成标准：平均增益、最差阶段和总资源均有配对比较；完整策略不被简单策略全面支配
- 停止条件：简单策略全面支配BRACE；返回动作策略，不增加模块

## P2：证明价值后再做

### PAPER-001 主干论文复现与组合

- 状态：`DEFERRED`
- 依赖：EXP-002证明明确失败点
- 完成标准：只复现能解决失败点、许可证清楚、CPU可执行的关键结论
- 停止条件：无法优于简单基线或破坏镜像/时间预算
