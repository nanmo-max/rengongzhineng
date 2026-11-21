# 可执行任务清单

状态定义见 [WORKFLOW.md](WORKFLOW.md)。任务状态只在本文件维护。

## 当前任务图

### COMPETITION-CORE-PLAN-001 Competition Core实施计划

- 状态：`IN_PROGRESS_TASK_9_LOCAL_OFFICIAL_SIMULATOR`
- 授权：用户于2026-11-20批准Competition Core书面规格并要求实行。
- 依赖：COMPETITION-CORE-DESIGN-001、D-093。
- 优先级：P0，当前唯一执行任务。
- 工作范围：依据已批准规格，映射现有`brace_formal`、官方SDK、PyTRiO/SwanLab和双镜像代码，形成测试先行、任务级提交、可连续执行的实施计划。
- 完成标准：计划覆盖任务画像、历史数据、注册recipe、双阶段Qwen、同作用域选择、正式轮编排、本地与正式镜像、A/B/C与未知任务训练、PyTRiO/SwanLab、Docker与发布验收；每项给出精确文件、接口、红绿测试、命令和提交边界；完成自审并独立提交。
- 停止条件：计划完成前不得修改产品代码、启动训练、调用远程服务或构建镜像。
- 证据：`superpowers/plans/2026-11-20-competition-core.md`。Task 1提交`e0097a7`；Task 2提交`54578db`；Task 3提交`a887f46`；Task 4提交`5a1c5bc`；Task 5提交`ae75de9`；Task 6提交`4a21f05`；Task 7提交`5242a4a`。Task 8新增排序静态`formal_runtime_allowlist.json`、逐文件普通文件/禁入校验、正式与本地上下文内容哈希清单、两个独立Dockerfile与构建脚本；正式隔离上下文固定入口可独立导入且不含tests/scripts/docs/data/weights/PyTRiO/SwanLab/密钥，本地上下文显式`LOCAL_TEST_ONLY`并独占模拟/报告脚本。专项`19 passed`，全量`600 passed in 155.58s`；尚未执行真实Docker构建。Task 9已就绪。

### COMPETITION-CORE-DESIGN-001 赛题语义重审与唯一正式架构规格

- 状态：`DONE_APPROVED`
- 授权：用户于2026-11-20逐项确认：隐藏评测可出现A/B/C之外但与官方训练包同格式的新工业任务；平台直接调用正式镜像；每轮必须至少完成一次真实候选训练后再部署、保留或回滚；历史数据可用；本地测试镜像与正式上传镜像必须分离；不增加非官方硬限制；PyTRiO训练的Qwen Agent必须进入正式方案。
- 依赖：O-PLATFORM-014、O-PLATFORM-019、RELEASE-COMPATIBILITY-AUDIT-001。
- 优先级：P0，当前唯一执行任务。
- 工作范围：只形成一套经用户确认的正式架构规格；保留已验证官方SDK、父checkpoint、预测和Docker边界；定义未知同格式任务识别、每轮真实训练、双阶段Qwen、历史数据、同作用域模型选择、PyTRiO/SwanLab镜像外训练记录、本地测试镜像与正式上传镜像分离。
- 完成标准：设计不存在并列路线、未决占位或与官方SDK冲突；明确组件、轮次数据流、任务泛化、训练与选择、PyTRiO、两镜像、验证和发布边界；通过自审、链接检查和`git diff --check`；形成独立Git提交。
- 停止条件：本任务不得修改产品代码、启动训练、调用PyTRiO/SwanLab、构建镜像、上传平台或消耗试运行；用户审阅并批准书面规格后，才可进入实施计划。
- 证据：`superpowers/specs/2026-11-20-competition-core-design.md`；D-093、L-AUTH-017、R-059；文档自审、相对链接检查和`git diff --check`通过。等待用户审阅书面规格。

### RELEASE-COMPATIBILITY-AUDIT-001 独立本地效果与官方平台准入审计

- 状态：`DONE_AUDIT_FAIL_RELEASE`
- 授权：用户于2026-11-20明确要求独立本地验证效果、独立审计官方符合性和平台运行兼容性。
- 依赖：FORMAL-EVERY-ROUND-TRAIN-001、O-PLATFORM-014、O-PLATFORM-019、FINAL-GENERALIZATION-VALIDATION-001。
- 优先级：P0，当前唯一执行任务。
- 工作范围：只读锁定现有正式归档、源码提交和已完成实验；使用官方SDK 1.0.2及本地宿主替身复验`describe/train/predict`、父链、状态、候选、模型调用和逐行预测；从`docker save`归档重新加载后在4核8GB、非root、只读根和断网条件下复验；独立汇总公开/代理/官方试运行性能证据并标明暴露与适用边界；只读核对平台当前页面和最新正式资料。
- 完成标准：形成一份机器可核验的准入矩阵，逐项给出`PASS/FAIL/BLOCKED_EXTERNAL/NOT_APPLICABLE`；记录精确归档SHA-256、镜像ID、测试命令与结果；确认正式镜像不含数据、权重、密钥、PyTRiO私有SDK或SwanLab客户端；验证每轮真实宿主模型调用ID、十轮父链、候选训练/部署决策、预测输出和64MiB产物约束；性能结论严格区分官方隐藏试运行、已暴露公开验证、代理开发和独立留出；最终明确“可本地证明的兼容性”和“仍需真实平台才能确认的外部项”。
- 停止条件：不得消耗官方试运行次数、上传镜像、保存新提交版本、写入SwanLab/PyTRiO、重新打开密封确认集、修改正式代码或把本地替身冒充平台成功；若冻结归档缺失或哈希不符，立即判失败并保留证据。
- 证据：`results/RELEASE-COMPATIBILITY-AUDIT-001.md`；精确归档哈希与血缘通过、三任务30轮/60调用/30候选及15行预测通过，但错误Qwen部署对抗测试证明退化C候选仍会被采用，现有归档不得作为最终正式提交。

### 选择可靠性与跨任务泛化（2026-11-20当前正式任务图）

#### SELECTION-RELIABILITY-001 指标事实、选择一致性与阶段计时

- 状态：`DONE`
- 依赖：O-PLATFORM-019、D-087、FORMAL-EVERY-ROUND-TRAIN-001
- 优先级：P0
- 完成标准：建立唯一`MetricContract`并拒绝指标—方向冲突；Harness计算同一验证作用域内父/候选有向收益；Qwen决策与确定性数值事实冲突时失败保留父模型；硬门失败不提交候选；轮收据记录父、候选、选择产物及验证作用域；阶段计时覆盖history/call1/train-eval-save/call2/submit-state-finish且不记录原始数据或prompt；用最新官方报告反例形成冻结测试夹具。
- 停止条件：不得解析自然语言理由来建立第二套真相；不得跨不同validation哈希比较历史“最佳”；不得改变训练recipe、父checkpoint schema、官方SDK、预测入口或调用次数；不得上传平台。
- 计划：`superpowers/plans/2026-11-20-selection-generalization-runtime.md` Task 1-3。
- 证据：提交`afa9038`；正式运行核`50 passed`，完整回归`487 passed in 143.52s`；独立复审无剩余P0/P1。详见`results/SELECTION-RELIABILITY-001.md`。

#### GENERALIZATION-MATRIX-001 多策略跨任务本地验证

- 状态：`DONE_DEVELOPMENT_STRATEGY_SCREENING`
- 依赖：SELECTION-RELIABILITY-001
- 优先级：P0
- 完成标准：在不读取公开确认集作选择的前提下，比较严格父子门、有限探索、合法历史冠军和recipe反馈四种策略；A/B/C使用各自合法组/时间顺序，但共享契约、证据和资源治理；报告平均、最差阶段、恢复、CPU、墙钟、RSS、Token和模型体积；至少保留一套稳定优于当前正式策略的候选，否则维持冻结RC。
- 停止条件：任一未来/确认泄漏、跨作用域选优、按数据集名称硬编码动作、或任何任务明显灾难性退化时停止该候选；不消耗官方试运行。
- 计划：同上Task 4-5。
- 证据：A1零训练反例重放11项通过；A2四策略因B灾难门全部淘汰；A3实验ID失配无效；A4/A5的独立复审缺陷均保留。A6精确复演120/120轮，symlink/junction与最终checkpoint绑定门通过；只保留`bounded_exploration`为开发候选。摘要SHA-256 `BA850904...B126F68`；本任务不代替D-088的最终独立泛化门。

#### PERFORMANCE-METHOD-PILOT-001 原生checkpoint兼容方法趋势筛选

- 状态：`DONE_DEVELOPMENT_METHOD_SCREENING`
- 依赖：GENERALIZATION-MATRIX-001、METHOD-PORTFOLIO-PILOT-001
- 优先级：P0
- 完成标准：基于合法相邻未见阶段，针对A类别不平衡/近期回放、B高尺度异质回归、C稳健与非对称RUL损失分别运行有界方法pilot；每项先独立对照，只有平均、最差阶段和资源同时满足门才与A4策略组合；至少保留一套不劣于A4双候选且改善C RMSE/NASA趋势的父checkpoint兼容方法，否则维持A4策略候选。
- 停止条件：不得改变checkpoint schema、从头训练替代父模型、读取公开confirmation作选择、按A/B/C名称在正式动作中硬编码方法，或把论文/成熟方法名称当作已验证收益；任一方法连续父链出现非有限值、不可加载或5%灾难退化立即停止。
- 计划：`superpowers/plans/2026-11-20-selection-generalization-runtime.md` Task 5。
- 证据：A1/A2完成有界方法筛选，A3完整组合按无效/负结果保留；A4只接入`balanced_current_e3 + native_recent_e3`复合分类候选，A平均有向收益`0.312990→0.360481`且最差阶段`-0.5470%→0`，B/C checkpoint与A6完全相同。该比较不能把收益归因于类平衡单因素。摘要SHA-256 `4237A9F4...10637BD`；仍需D-088独立门。

#### PYTRIO-ADVISOR-OPT-001 镜像外Advisor训练与SwanLab聚合记录

- 状态：`DONE_EXTERNAL_ADVISOR_CANDIDATE`
- 依赖：GENERALIZATION-MATRIX-001、PERFORMANCE-METHOD-PILOT-001
- 优先级：P0
- 完成标准：先验证基础Qwen在冻结反例集的结构化有效率和数值关系正确率；只有仍存在系统性错误时才用获授权、脱敏轨迹训练PyTRiO Advisor，并在未参与训练的轨迹上证明优于基础模型；SwanLab只同步聚合配置、指标、资源、Token和失败类别，敏感扫描为零。
- 停止条件：不得把PyTRiO私有SDK、Sampler、Tokenizer、API Key或SwanLab依赖放入正式镜像；不得用隐藏标签、逐样本数据或已暴露确认集训练Advisor；未显著改善则保持基础模型。
- 计划：同上Task 6。
- 证据：A1基础Qwen 12例schema/Token门100%，但2个硬风险场景仍请求deploy；A2按D-090完成唯一一次24训练/12全新留出、18步LoRA，基础同留出policy 66.67%/安全91.67%，新Sampler四项100%，重新加载复评仍四项100%。结果SHA-256 `E192DB1F...703B5DF`，重载摘要`179F6BEC...CCC09D`。SwanLab聚合包敏感扫描零命中并同步到公开运行`k4jvqkuj`。新Sampler仅为镜像外候选，平台提交页未校验前不声称正式采用。

#### FINAL-GENERALIZATION-VALIDATION-001 冻结方法后独立替代流/任务留出验收

- 状态：`DONE_INVALID_PROTOCOL_AND_NEGATIVE_NO_FORMAL_PROMOTION`
- 依赖：PERFORMANCE-METHOD-PILOT-001；如PYTRIO-ADVISOR-OPT-001的产物改变最终决策逻辑，则其也是依赖
- 优先级：P0
- 完成标准：在不参与触发阈值、recipe或方法选择的替代流/任务留出上，对冻结策略+方法一次性评估；平均、最差阶段、恢复、CPU/墙钟/RSS/模型体积和泄漏门均通过；失败时维持冻结Protocol RC。
- 停止条件：禁止使用已暴露confirmation/public validation；打开留出后禁止调阈值或方法；禁止用同一开发代理流重命名冒充独立证据；不消耗官方试运行。
- 证据：A1在提交`5f03a17`冻结后一次性打开XJTU三个密封轴承；密封全局RMSE/MAE分别改善9.35%/8.75%，2/3轴承改善。但开发第10轮最差相对收益`-99.61%`，且独立审查发现延迟收益复用当前Gate标签、峰值RSS和恢复未验证。A1不得晋级或针对密封结果调参；密封数值只保留描述性证据。摘要SHA-256 `22D4143B...38AA05`，详见`results/FINAL-GENERALIZATION-VALIDATION-001.md`。

#### FORMAL-RC-NEXT-001 新正式候选冻结

- 状态：`BLOCKED_BY_LOCAL_GATES`
- 依赖：SELECTION-RELIABILITY-001、GENERALIZATION-MATRIX-001、PERFORMANCE-METHOD-PILOT-001、FINAL-GENERALIZATION-VALIDATION-001；PYTRIO-ADVISOR-OPT-001只有在证明有效且被采用时才是依赖
- 优先级：P0
- 完成标准：仅集成已证明稳定的策略与方法；完整回归、官方SDK、A/B/C十轮、60次宿主调用、30个真实候选、父链、预测、4核8GB、64MiB、禁入扫描及docker save/load全部通过；形成唯一归档、源码提交和脱敏实验记录。
- 停止条件：任一任务、协议、资源或禁入门失败时不得替换冻结归档；平台上传继续由FORMAL-RELEASE-001单独授权。

```text
SELECTION-RELIABILITY-001(DONE)
  -> GENERALIZATION-MATRIX-001(DONE_DEVELOPMENT_STRATEGY_SCREENING)
  -> PERFORMANCE-METHOD-PILOT-001(DONE_DEVELOPMENT_METHOD_SCREENING)
  -> PYTRIO-ADVISOR-OPT-001(DONE_EXTERNAL_ADVISOR_CANDIDATE)
  -> FINAL-GENERALIZATION-VALIDATION-001(DONE_INVALID_PROTOCOL_AND_NEGATIVE)
  -> FORMAL-RC-NEXT-001(BLOCKED_BY_LOCAL_GATES)
  -> FORMAL-RELEASE-001(BLOCKED_EXTERNAL)
```

### 第一性原理重建（2026-11-17当前正式任务图）

#### REBUILD-FORENSICS-001 首次成功与正式失败取证

- 状态：`DONE`
- 优先级：P0
- 完成标准：首次成功、最近两次失败、官方SDK硬契约和证据边界均有直接证据；不猜测镜像绑定。
- 证据：`replans/FIRST-PRINCIPLES-REBUILD-FORENSICS-2026-11-17.md`、O-PLATFORM-015、D-079至D-081。

#### FORMAL-MINIMAL-001 最小workspace v2正式运行核

- 状态：`DONE`
- 依赖：REBUILD-FORENSICS-001
- 优先级：P0，当前唯一执行任务
- 完成标准：真实宿主模型调用位于所有分支前；低token上限/模型别名/无usage/retain均有call ID；每轮唯一工作目录；父checkpoint续训或retain；候选提交、状态、历史和预测符合官方SDK。
- 停止条件：官方SDK与实际平台再次出现不可调和冲突时保存原始证据并失败关闭；不得改官方SDK或伪造call ID。
- 计划：`superpowers/plans/2026-11-17-first-principles-formal-runtime.md` Task 1-4。
- 证据：`results/FORMAL-MINIMAL-001.md`；451项完整回归；A/B/C合成协议测试30/30轮、30个唯一宿主call ID、父链与状态链全部有效。

#### FORMAL-CLEAN-IMAGE-001 最小正式Docker与十轮验收

- 状态：`DONE`
- 依赖：FORMAL-MINIMAL-001
- 优先级：P0
- 完成标准：镜像白名单、4核8GB断网、A/B/C各10轮、30个真实本地宿主回执、独立预测、64MiB、非root和docker save/load全部通过。
- 停止条件：任一禁入文件、镜像超限、非root/只读/资源门失败或归档无法`docker load`时不得冻结RC。
- 计划：同上Task 5。
- 证据：`results/FORMAL-CLEAN-IMAGE-001.md`；最终归档81,201,152字节，SHA-256 `DC73FAFC...C05C39E`；精确镜像A/B/C各10轮、30次宿主调用及独立预测通过。

#### FORMAL-PERF-001 父链兼容性能候选集成

- 状态：`SUPERSEDED_BY_FORMAL-AUDIT-FIX-001`
- 依赖：FORMAL-CLEAN-IMAGE-001
- 优先级：P1
- 完成标准：只用训练内部证据筛选，至少比较retain、1 epoch和两个成熟父链兼容recipe；无跨轮正趋势的机制不进入正式镜像。
- 计划：同上Task 6。
- 证据：A1仅用官方train内部三折比较`retain/e1_lr1/e3_lr3/soup_e3_alpha0.25`；A选择e1、B选择retain、C选择soup。精确`0.10.2rc1`在4核8GB断网容器完成A/B/C各10轮、30次宿主调用和15行独立预测；B十轮全部由训练内负证据否决训练。458项回归、白名单/非root/64MiB/依赖门和`docker save/load`同镜像ID通过。见`results/FORMAL-PERF-001.md`。

#### FORMAL-AUDIT-FIX-001 正式候选终审修复

- 状态：`DONE_LOCAL_EXTERNAL_BLOCK`
- 依赖：FORMAL-PERF-001
- 优先级：P0，当前唯一执行任务
- 完成标准：以平台返回测量作为候选部署权威且缺失时失败关闭；声明区分Agent请求与真实执行recipe/epoch/LR/seed；独立组不足时可审计retain；工作区按dataset隔离；验收报告保留真实入站父哈希；train/predict在只读根、4核8GB、断网条件下通过；模拟宿主返回非空权威指标；完整回归和新镜像重载通过。
- 停止条件：任一权威测量、父链、工作区隔离、真实执行声明或只读容器门失败时，不得生成可上传候选；不得覆盖`0.10.2rc1`及其历史证据。
- 证据：独立终审发现6项重要缺陷和1项验收范围缺口；修复采用测试先行并冻结为`0.10.3rc1`，不回写历史RC。完整回归465项；官方SDK Linux离线15项通过、2项在线条件测试跳过；A/B/C各10轮共30次宿主调用；4核8GB只读断网、非root、64MiB、白名单和`docker save/load`同ID通过。见`results/FORMAL-AUDIT-FIX-001.md`。

#### FORMAL-RELEASE-001 正式平台受控验证与最终记录

- 状态：`BLOCKED_EXTERNAL`
- 依赖：FORMAL-EVERY-ROUND-TRAIN-001
- 优先级：P0（只在用户明确决定消耗平台次数后执行）
- 完成标准：平台导入通过终审的新RC归档并显示镜像可用；受控试运行证明真实宿主Qwen调用、十轮父链、候选/retain、逐行预测和平台训练报告；正式训练记录、源码分支和作品材料引用同一冻结提交与镜像哈希。
- 停止条件：未经用户确认不得上传或消耗试运行；平台失败时先保存原始报告并定位根因，不盲目重试；本地模拟不得冒充平台通过或隐藏成绩。

#### FORMAL-AGENT-OUTPUT-001 宿主模型输出契约修复

- 状态：`DONE_LOCAL_PLATFORM_CONFIRMATION_PENDING`
- 依赖：FORMAL-AUDIT-FIX-001、O-PLATFORM-017
- 优先级：P0，当前唯一执行任务
- 完成标准：用平台报告复现并解释30轮非法提案；在不改变训练器、性能recipe、SafetyGate和正式SDK的前提下，删除参赛者自设Token上限、由官方SDK使用宿主完整授权预算，接受宿主回复中唯一合法的有界JSON对象，非法输出继续安全retain；专项、完整回归和正式镜像验收全部通过。
- 停止条件：无法以平台Token结算和本地红绿测试证明根因时不得修改；不得直连PyTRiO、内置密钥、强制训练或绕过提案白名单；不得自动发起新的平台试运行。
- 预注册：`FORMAL-AGENT-OUTPUT-001-A1`。
- 证据：O-PLATFORM-017、`results/FORMAL-AGENT-OUTPUT-001.md`；专项10项、正式运行与SDK专项37项、完整回归469项；`0.10.4rc2`容器三任务30轮、30调用、候选1/0/3、15行预测及重载同ID通过。

#### FORMAL-EVERY-ROUND-TRAIN-001 每轮候选训练与部署决策分离

- 状态：`DONE_LOCAL_PLATFORM_CONFIRMATION_PENDING`
- 依赖：FORMAL-AGENT-OUTPUT-001、O-PLATFORM-018、D-085、D-086
- 优先级：P0
- 完成标准：A/B/C每轮都由Qwen选择受控recipe并真实续训一个候选；Harness本地计算主辅指标与资源；第二次Qwen调用决定deploy/retain/rollback；SafetyGate只执行硬约束；平台逐轮指标缺失时流程仍完整。专项、完整回归、三任务30轮容器、4核8GB、白名单、64 MiB和`docker save/load`通过。
- 停止条件：任一轮无真实候选、平台指标影响内部选择、父链/双模型调用/预测被破坏，或需要读取隐藏标签调参时不得冻结；不得自动发起平台试运行。
- 预注册与结果：A1无效、A2中止、A3通过、A4为最终本地RC验收；证据见`results/FORMAL-EVERY-ROUND-TRAIN-001.md`。

以下旧任务图保留为历史证据，不决定当前执行顺序。

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
  -> DUAL-RC-001(DONE)
  -> FORMAL-CONTINUATION-RC-001(DONE)
  -> PLATFORM-NATIVE-001(DONE)
  -> NATIVE-COMPETITIVE-RC-001(DONE_LOCAL_EXTERNAL_BLOCK)
  -> PLATFORM-REPORT-SIM-001(DONE)
  -> PYTRIO-ONLINE-001(DONE)
  -> UNSEEN-SIM-001(DONE_NEGATIVE)
  -> UNSEEN-REPORT-001(DONE)
  -> OFFICIAL-DATA-REPORT-001(DONE)
  -> REPORT-EVIDENCE-FIX-001(DONE)
  -> OFFICIAL-FLOW-SIM-001(DONE_MIXED)
  -> DELAYED-GAIN-SIM-001(DONE_MIXED)
  -> METHOD-PORTFOLIO-PILOT-001(DONE)
  -> COMPETITIVE-POLICY-002(DONE_LOCAL_EXTERNAL_BLOCK)
  -> PLATFORM-BRIDGE-001(DONE_LOCAL_EXTERNAL_BLOCK)
  -> PLATFORM-PREFLIGHT-001(DONE_LOCAL_EXTERNAL_BLOCK)
  -> PLATFORM-MODEL-TRANSPORT-001(DONE_LOCAL_EXTERNAL_BLOCK)
  -> OFFICIAL-SDK-V2-001(DONE_LOCAL_PLATFORM_PENDING)
  -> FORMAL-RELEASE-001(BLOCKED_EXTERNAL)
```

以上为当前正式重构图；`0.6.0rc1`及下方历史任务图保持冻结，新竞争候选只在独立分支演进。

### OFFICIAL-SDK-V2-001 官方Workspace V2最小正式接入

- 状态：`DONE_LOCAL_PLATFORM_PENDING`
- 依赖：PLATFORM-MODEL-TRANSPORT-001、O-PLATFORM-014
- 优先级：P0
- 目标：以首次平台可运行的原生父checkpoint训练/预测内核为稳定边界，接入官方`contest_harness` 1.0.2固定`describe/train/predict`入口；只替换平台协议边界，不改变冻结性能策略、checkpoint schema或历史RC。
- 完成标准：官方SDK源码与哈希可追溯；`describe`声明workspace v2及host gateway；每轮至少一次真实宿主模型调用并引用非空`model_call_ids`；从声明父checkpoint真实续训或retain；候选由平台测量后选择；prediction逐行输出且使用`CONTEST_ARTIFACT_PATH`；官方15项测试、项目专项/完整回归、三任务宿主替身十轮、4核8GB断网容器、64MiB、禁入扫描和`docker save/load`全部通过。
- 停止条件：不得猜测SDK外字段；不得把本地宿主替身或公开验证写成正式成绩；不得内置密钥、数据、权重、测试报告或直接PyTRiO客户端；若真实宿主行为仍未知，只将对应项保留为`BLOCKED_EXTERNAL`。
- 当前证据：官方归档/说明哈希已登记，vendored九个SDK源文件与官方解压件逐文件SHA-256一致；Linux 4核8GB断网环境运行官方SDK自带测试`15/15 OK`。项目完整回归`435 passed`；A/B/C最终镜像各10轮、30次宿主模型调用、候选提交/retain、状态/父链及15行独立预测通过；平台测量拒绝后的父状态与公开收据对账有红绿测试。镜像151,369,904字节，正式归档SHA-256 `dc0147706e5c20a62360bf309a280b890ac6cea2707eee4aa66f8f7169c57cbc`且重载通过。真实平台状态仍交由`FORMAL-RELEASE-001`，见`results/OFFICIAL-SDK-V2-001.md`。

### WORKSPACE-V2-INDEPENDENT-TEST-001 冻结归档独立平台模拟

- 状态：`DONE_LOCAL_ONLY`
- 依赖：OFFICIAL-SDK-V2-001、A4正式归档
- 授权：用户2026-11-17明确要求模拟官方平台独立测试并生成官方风格HTML。
- 目标：不从工作树构建镜像，直接从A4 `docker save`归档加载全新标签，在全新状态目录以4核8GB、断网、非root条件完成A/B/C各10轮workspace v2宿主事务和独立预测；从机器JSON生成官方页面风格HTML。
- 完成标准：归档哈希匹配冻结值；三任务各10轮且每轮引用非空模型调用收据；父链、候选/retain、状态恢复、三任务预测均通过；HTML包含30轮并显著标记“本地协议模拟，不计正式成绩”；隐藏指标、正式Token和官方成绩不虚构；专项和完整回归通过。
- 停止条件：归档哈希变化、镜像加载失败、任一轮缺模型调用/父链中断、预测失败、报告遗漏轮次或把本地结果写成官方成绩时立即判失败并保留证据。
- 证据：A4归档SHA-256复核一致并删除原标签后重新加载为独立标签；A/B/C各10轮、30次宿主调用、C两次候选提交、A/B retain及15行预测通过，`acceptance.json valid=true`。HTML/JSON机器校验为30/30轮且无“官方评测通过”表述；报告专项2项、完整回归437项通过。详见`results/WORKSPACE-V2-INDEPENDENT-TEST-001.md`。

### PLATFORM-MODEL-TRANSPORT-001 平台Chat Completions原生模型边界

- 状态：`DONE_LOCAL_EXTERNAL_BLOCK`
- 依赖：PLATFORM-PREFLIGHT-001、O-PLATFORM-013
- 优先级：P0
- 目标：让原生`brace_msi start`通过镜像内定义的标准Chat Completions语义直接调用平台`workspace_io.model_transport`，消除只能由平台语义重写PyTRiO私有Sampler协议的兼容性缺口；正式训练不得在零模型调用时静默继续。
- 完成标准：请求构造、响应解析和正Token收据由镜像实现；平台传输每轮强制触发；两次失败后retain且不训练；`describe`声明绑定协议；CLI支持依赖注入和`workspace_io`运行时解析；完整回归、4核8GB断网只读容器真实替身调用、独立预测、`pip check`、禁入扫描及`docker save/load`通过。
- 停止条件：不猜测平台私有frame字段，不改变父checkpoint schema、训练器、性能策略、Gate或历史RC；本地替身调用不得冒充平台真实服务通过。
- 证据：430项回归；容器替身调用123/45 Token并完成官方A候选训练；独立预测1,244条；镜像249,015,083字节；归档249,039,360字节且SHA-256为`4BE4327D...EA3A694`。见`results/PLATFORM-MODEL-TRANSPORT-001.md`与`results/RC83_CONTAINER_ACCEPTANCE.json`。

### PLATFORM-PREFLIGHT-001 空挂载镜像预检兼容修复

- 状态：`DONE_LOCAL_EXTERNAL_BLOCK`
- 依赖：PLATFORM-BRIDGE-001、O-PLATFORM-012
- 优先级：P0
- 目标：恢复首个平台可运行版本具备的无输入安全启动语义；平台尚未挂载`/data`、`/previous`、`/workspace`和`/output`时，镜像默认启动必须退出0且不得误触发训练，同时显式`start`/`submit`继续执行原生父checkpoint续训和独立预测。
- 完成标准：红灯测试能捕获`CMD ["start"]`；补丁恢复`CMD ["--help"]`；裸容器退出0；带官方A父checkpoint的`start`退出0并生成`checkpoint.npz`；独立`submit`生成1,244条预测；完整回归、4核8GB只读断网、禁入扫描、`pip check`及`docker save/load`通过。
- 停止条件：不修改训练策略、模型参数、SafetyGate、PyTRiO、SwanLab或0.8.1历史证据；不把本地预检写成平台兼容通过；平台真实挂载和在线模型调用仍由FORMAL-RELEASE-001判定。
- 证据：运行提交`8566807`；424项回归；裸启动由退出1修复为退出0；原生A一轮续训及1,244条独立预测通过；248,980,992字节归档已重载。见`results/PLATFORM-PREFLIGHT-001.md`与`results/RC82_CONTAINER_ACCEPTANCE.json`。

### PLATFORM-BRIDGE-001 平台薄桥接边界加固

- 状态：`DONE_LOCAL_EXTERNAL_BLOCK`
- 依赖：COMPETITIVE-POLICY-002、O-PLATFORM-011
- 优先级：P0（平台草稿适配器有缺陷，尚未形成有效兼容性结论）
- 目标：不实现未知的官方私有frame schema，只为现有Native CLI补充可由外部桥接器可靠调用的显式父哈希、期望轮次和模型产物收据；保留空输出挂载、父链、retain与十轮状态边界。
- 完成标准：父哈希不符在读取训练数据前失败；期望轮次与持久化workspace历史不符失败；部署、拒绝和retain均返回并实际生成一致的`checkpoint.npz`产物声明；describe暴露无mode命令前缀；现有CLI/父链/空输出测试、全量回归及新镜像构建/重载通过。
- 停止条件：不得猜测或复制未发布`workspace_io`字段；不得修改训练策略、历史RC、数据或模型参数；若平台不持久化workspace/history，必须继续记录外部阻塞，不能伪造十轮状态。
- 证据：父哈希/轮次/retain产物红绿测试、54项平台专项和424项完整回归通过；官方A父checkpoint在4核8GB断网只读容器中连续两轮并完成1,244条独立预测；249,029,120字节`docker save`归档经删除tag后重载成功。见`results/PLATFORM-BRIDGE-001.md`与`results/RC81_CONTAINER_ACCEPTANCE.json`。平台私有桥接器和真实生命周期继续由`FORMAL-RELEASE-001`跟踪。

### METHOD-PORTFOLIO-PILOT-001 方法级跨批可行性筛选

- 状态：`DONE`
- 依赖：DELAYED-GAIN-SIM-001
- 优先级：P0（现有候选仅改变epoch/LR/Replay，A/C可能误拒，B存在小Gate假阳性）
- 目标：不读取本地确认集，使用十轮训练流的`t训练→t+1未见评价`比较静态父模型、原生MLP当前批/累计续训、线性模型、HGB、ExtraTrees及低成本教师集成；先验证方法是否具有跨批趋势，再决定蒸馏、持续学习或正式集成。
- 完成标准：A/B/C各完成9个相邻批次转移；所有方法使用相同合法历史；记录主指标收益、胜率、最差转移、CPU和样本数；产物标记为教师上界/研究代理而非可提交checkpoint；至少一个方法在不少于两个任务或一个任务多数转移上明显优于原生续训，才进入下一阶段。
- 停止条件：不读取任何confirmation/public validation；不消耗官方试运行或PyTRiO；单方法单任务超过5分钟、内存超过4 GiB或连续多数转移退化即停止；无明显趋势则不工程化。
- 证据：A1教师矩阵、A2正式MLP矩阵、A3失败保留及A4连续父链全部完成；confirmation读取0、官方试运行0。A4中A `recent_e3`九转换对静态9/9胜且平均Macro-F1有向收益`+0.386974`；B `current_e3_lr3`为9/9且平均RMSE有向收益`+287.436213`；C `soup_current_e3_alpha0.25`平均RMSE有向收益`+1.007474`、最坏`-0.196010`。详见`results/METHOD-PORTFOLIO-PILOT-001.md`。

### COMPETITIVE-POLICY-002 证据驱动双候选正式策略

- 状态：`DONE_LOCAL_EXTERNAL_BLOCK`
- 依赖：METHOD-PORTFOLIO-PILOT-001
- 优先级：P0
- 目标：把A4通过的正式MLP recipe接入平台原生Harness；第一候选使用跨任务低风险父权重插值，第二候选仅在当前证据与历史延迟收益支持时，从最近窗口、累计回放或高步长当前更新中选择；不得按数据集名称硬编码。
- 完成标准：平台父checkpoint真实继承；每轮0至2候选；候选选择只使用当前及历史合法证据；下一批结算与负收益回滚；A/B/C十轮代理流均完成且相对静态平均有向收益为正；全部checkpoint可加载、独立预测、64 MiB、CPU/RSS/Token完整；PyTRiO建议不能覆盖执行边界。
- 停止条件：任一任务平均收益非正、未来或确认泄漏、父链/step倒退、候选无法从任务契约和数据证据解释，或全量/容器验收失败。
- 证据：A1—A6全部保留；A3激进早触发因B平均收益`-92.775049`淘汰，A5因报告ID失配判无效。最终A6严格隔离Gate并经`start_round`完成三任务十轮，A/B/C平均有向收益为`+0.319620` Macro-F1、`+21.850812`和`+0.438766` RMSE降低；421项回归、三任务4核8GB断网容器、PyTRiO失败retain、禁入扫描及`docker save/load`通过。最终归档SHA-256 `CB9F28D1...FC232E6EA`。平台导入、在线凭据和官方评测继续由`FORMAL-RELEASE-001`跟踪。

### DELAYED-GAIN-SIM-001 当前批证据与下一批延迟收益模拟

- 状态：`DONE_MIXED`
- 依赖：OFFICIAL-FLOW-SIM-001
- 优先级：P0（V1将Prequential结果隔离在ScoreVault，不能驱动当前retain/训练决策，也未在下一批结算上一轮部署真实收益）
- 目标：在不覆盖V1和冻结RC的前提下，实现`arrival_metric_t -> 当前动作与Gate -> delayed_gain_t+1`十轮序贯闭环，完成A/B/C训练、机器验收、SwanLab离线记录和HTML报告。
- 完成标准：三任务各10轮；到达指标进入结构化决策证据；上一轮仅在下一批同样本影子比较结算；候选Gate仍与Update隔离；未来不可见、确认只读一次、父链连续；专项和完整回归通过。
- 停止条件：不得用本地确认调参、不得把Bearing十段代理假设写成官方事实、不得把本地结果称为正式隐藏成绩；性能负结果必须保留。
- 设计与计划：`docs/superpowers/specs/2026-11-16-delayed-gain-sequential-simulation-design.md`、`docs/superpowers/plans/2026-11-16-delayed-gain-sequential-simulation.md`。
- 证据：Smoke、A2负结果和A3回滚修复均保留；A3三任务各10轮、父链连续、确认只读一次、到达证据可见，B在第10轮根据`-310.293697`配对延迟收益回滚直接前任。专项59项及完整回归407项通过；报告见`results/DELAYED-GAIN-SIM-001.md`。性能结论为混合：B避免灾难性部署，A/C没有获得新提升。

### OFFICIAL-FLOW-SIM-001 官方生命周期双层本地模拟

- 状态：`DONE_MIXED`
- 依赖：REPORT-EVIDENCE-FIX-001、PLATFORM-NATIVE-001
- 优先级：P0（现有按行均切十段模拟器不符合任务自然分组，也没有先预测后反馈）
- 目标：冻结现有RC与历史报告，新增独立`StreamPlan`、任务流构造器、预测封存、`ScoreVault`和分组Update/Gate入口；逐轮严格执行“未见批次预测→封存→标签反馈→Prequential计分→候选Gate→部署/保留”，最终确认集只在策略冻结后读取一次。
- 数据边界：Gas父模型已见Batch 1，使用完整原始Batch 2—9构造十轮并保留Batch 10作最终确认；Bearing以未见完整轴承和寿命进度构流；Engine以完整unit分组构流。父训练ID、流ID和最终确认ID必须零交叉。
- 完成标准：移除新入口的行号均切逻辑；Prequential与候选Gate指标分离；预测文件在标签反馈前封存并校验哈希；Bearing未来snapshot不可提前进入Replay；Engine unit不跨轮；调整输入文件名或JSONL行顺序不改变归属；最终确认只读一次且不反馈ActionPolicy；专项测试和完整回归通过，生成机器可审计本地模拟证据。
- 停止条件：不得把本地最终确认称为官方隐藏测试；不得读取未来正式隐藏数据、调用官方试运行或覆盖原始数据；若本地数据无法满足十轮和独立确认，必须失败关闭或明确降级，不得按行伪造。
- 设计与计划：`superpowers/specs/2026-11-15-official-flow-simulation-design.md`、`superpowers/plans/2026-11-15-official-flow-simulation.md`。
- 证据：任务自然分组、预测封存、ScoreVault、显式Update/Gate和未来不物化测试全部通过；399项完整回归通过。A2三任务均10/10轮且父链有效，A/C部署0次，B部署1次；B相对静态流平均RMSE略降但本地确认RMSE由静态241.980799恶化为495.437675，作为负证据保留。详见`results/OFFICIAL-FLOW-SIM-001.md`。

### REPORT-EVIDENCE-FIX-001 报告验证选择污染修正

- 状态：`DONE`
- 依赖：PLATFORM-REPORT-SIM-001、OFFICIAL-DATA-REPORT-001
- 优先级：P0（现有报告证据等级错误）
- 根因：旧生成器对十轮冻结checkpoint重复读取同一公开validation，并用该指标选择“最佳轮次”；这不是训练样本泄漏，但构成validation参与模型选择。
- 目标：逐轮只展示当前批次Gate上的稳定/候选指标和Harness真实部署决策；策略与十轮完全冻结后，仅对最终稳定checkpoint读取一次公开validation，且不得据此选择轮次。
- 完成标准：每任务公开validation评估恰好一次；逐轮记录不含公开validation指标；最终模型来源由Harness部署链确定；旧V1报告明确降级为界面/协议演示；专项与完整回归通过，并生成独立V2产物。
- 停止条件：不重训、不修改checkpoint、不调用PyTRiO/SwanLab/官方试运行，不把公开validation写成独立泛化证据。
- 证据：V2三任务30轮、每任务公开validation恰好读取1次，零`selected_round`/`selected_metrics`和零逐轮`public_validation_metrics`；专项7项、完整回归390项通过。详见`results/REPORT-EVIDENCE-FIX-001.md`。

### OFFICIAL-DATA-REPORT-001 Gas/Bearing/Engine官方要素风格报告

- 状态：`DONE`
- 依赖：PLATFORM-REPORT-SIM-001、UNSEEN-REPORT-001
- 优先级：P0（用户要求对原始三任务生成同样报告）
- 目标：复用RC7冻结A/B/C十轮checkpoint及`PLATFORM-REPORT-SIM-001`历史公开validation复演结果，生成与UNSEEN报告相同的信息层级和可展开逐轮记录。
- 完成标准：Gas/Bearing/Engine各10轮；显示最终采用轮、公开验证样本、CPU/运行时间、Accuracy/Macro-F1或MAE/RMSE/NASA、逐轮模型选择、动作、Token和资源；缺失的历史假设/Gate字段明确显示“未记录”，不补造；显著标记历史暴露公开验证和非官方成绩。
- 停止条件：不得重训、再次读取公开validation、调用PyTRiO或使用官方试运行；现有机器报告字段不足时只降级展示。
- 产物：`D:/brace-msi-native-competitive/RC7-OFFICIAL-REPORT-SIM/platform-style/`下HTML与JSON。
- 证据更正：三任务各10轮、30个展开记录及页面字段有效，但继承V1的validation轮次选择污染；仅保留界面演示。修正证据见`REPORT-EVIDENCE-FIX-001`。


### UNSEEN-REPORT-001 官方要素风格的本地模拟报告

- 状态：`DONE`
- 依赖：UNSEEN-SIM-001、O-PLATFORM-010
- 优先级：P0（用户要求按官方页面要素生成易读报告）
- 目标：不重训、不调用PyTRiO、不修改A4证据，从`UNSEEN-SIM-001-A4/report.json`生成单页HTML与机器JSON；包含完成轮次、最终采用模型、确认样本、CPU/运行时间、最终指标、逐轮评估、模型选择和可展开实验记录。
- 完成标准：三任务各10轮；最终采用来源可由checkpoint链复算；逐轮记录包含历史、假设、修改、Advisor/Token、Gate与资源；明显标注“本地独立确认集、非官方隐藏成绩”；无密钥、原始样本或伪造字段；专项测试和完整回归通过。
- 停止条件：A4证据字段不足以可靠映射时显示“未记录”，不得猜测；不得重新打开数据或重跑confirmation补字段。
- 产物：`D:/brace-msi-unseen/UNSEEN-SIM-001-A4/platform-style-report.json`与`.html`，仓库内保留脱敏说明和生成器测试。
- 证据：三任务各10轮、30个展开记录、全部规定字段和敏感标记扫描通过；专项2项通过。产物哈希和摘要见`results/UNSEEN-REPORT-001.md`。


### PYTRIO-ONLINE-001 基础模型在线稳定性与RC入口验收

- 状态：`DONE`
- 依赖：NATIVE-COMPETITIVE-RC-001
- 优先级：P0（用户2026-11-15明确要求补齐PyTRiO）
- 目标：不训练新Sampler、不改工业模型参数，使用平台已校验的`Qwen/Qwen3.5-4B`基础模型完成至少3次独立非零Token结构化提案，其中至少1次建议实际进入RC7受控Harness；验证服务失败仍只retain。
- 预算：最多6次远程采样、每次最多768输出Token、60秒客户端超时；不消耗官方试运行，不调用27B，不进行LoRA/SFT。
- 完成标准：至少3次非零Token、严格schema合法的PyTRiO响应；至少1次在冻结策略约束下实际执行；请求/响应只保存哈希、Token、延迟和结构化收据；专项测试、完整回归及必要镜像补丁验收通过。
- 停止条件：6次额度用尽仍不足3次有效响应、账户余额不足、服务端持续异常或必须泄露凭据；此时保留全部失败证据并标记外部阻塞，不制造通过。
- 边界：不得重开公开validation、改变RC7性能策略、训练大模型、打印凭据或消耗官方平台试运行。
- 证据：3个独立宿主进程均取得严格合法非零Token响应，累计输入/输出1,103/581 Token，至少1次建议进入受控Harness；`0.7.1rc1`正式镜像内置tokenizer-only资产后，在4核8GB只读容器中不挂载宿主模型缓存也取得330/184 Token并执行候选；断网两次失败后只retain。383项完整回归、镜像扫描及`docker save/load`通过。见`D:/brace-msi-pytrio/PYTRIO-ONLINE-001-A1/summary.json`、`results/PYTRIO-ONLINE-001.md`及`results/RC71_CONTAINER_ACCEPTANCE.json`。

### UNSEEN-SIM-001 三个新工业数据集的冻结RC泛化复演

- 状态：`DONE_NEGATIVE`
- 依赖：NATIVE-COMPETITIVE-RC-001、PLATFORM-REPORT-SIM-001
- 优先级：P0（用户授权的本地独立验证；不替换或修改RC7）
- 目标：在电池老化、液压状态监测和铣削刀具磨损三个此前未用于RC7开发的数据集上，使用统一数值特征契约、模拟父checkpoint、十轮原生续训、门控、独立预测和官方报告字段，检验未知任务泛化与资源成本。
- 完成标准：原始数据保持只读并登记哈希；三任务均形成不含目标泄漏的特征与设备/工况隔离切分；模拟父模型只读取bootstrap分区；十轮只读取adaptation分区；confirmation分区在策略冻结后只评估一次；每轮父链、候选、部署/拒绝、CPU、RSS、checkpoint大小和预测数可复算；输出JSON/HTML报告及机器校验。
- 停止条件：发现目标/未来泄漏、分组交叉、样本不足以形成十轮、非有限特征、父checkpoint不可加载、产物超过64 MiB或需要修改RC7策略；失败也必须保存并报告，不得用confirmation结果调参重跑。
- 边界：这是自建模拟父模型上的本地泛化实验，不是官方数据、官方父checkpoint、隐藏成绩或新RC性能证明；按用户补充要求A4调用Qwen3.5-4B PyTRiO，但未调用SwanLab或官方试运行，也未修改`0.7.0rc1`镜像和归档。
- 证据：A1数据质量失败、A2证据ID失配、A3确定性负对照、A4真实PyTRiO对照全部保留。A4三任务30轮、16次有效响应、15次建议执行，协议门和Agent门通过，但严格改善0/3；见`results/UNSEEN-SIM-001.md`。

### PLATFORM-REPORT-SIM-001 官方报告字段本地复演

- 状态：`DONE`
- 依赖：NATIVE-COMPETITIVE-RC-001、O-PLATFORM-010
- 目标：不消耗官方试运行，以冻结RC7轮次checkpoint和历史暴露公开validation复演官方报告的10轮、逐轮指标、模型采用、资源和Token字段。
- 证据更正：A/B/C均10/10轮，但25,972条是对同一公开validation逐轮重复评估，且V1据此模拟选择第9/1/9轮，构成选择污染。机器JSON/HTML保留为界面演示；修正见`REPORT-EVIDENCE-FIX-001`。
- 边界：只验证旧报告页面流程；不是隐藏测试、官方成绩、独立泛化或有效轮次选择证据。

### NATIVE-COMPETITIVE-RC-001 原生竞争候选冲刺

- 状态：`DONE_LOCAL_EXTERNAL_BLOCK`
- 依赖：PLATFORM-NATIVE-001、PYTRIO-COMPETITIVE-001-A1、REGRESSION-SPRINT-001
- 优先级：P0，当前唯一执行任务
- 目标：在不改写`0.6.0rc1`的前提下，验证`_NativeModel.fit`与官方训练器逐状态等价，迁移已冻结日程，使用train内部证据修正Gate/retain语义，形成带PyTRiO非零调用、SwanLab聚合记录和真实Docker归档的完整新RC。
- 完成标准：A/B/C差分等价门通过；十轮每轮有真实决策且允许0或1候选，至少3次真实候选；公开validation只在配置冻结后读取一次且三任务均不低于`0.6.0rc1`、至少两项严格改善；Native PyTRiO至少3次非零Token调用且至少1项建议执行；SwanLab只含聚合记录；完整回归、4核8GB、断网降级、父链、独立预测、64 MiB、2 GiB和`docker save/load`通过。
- 停止条件：任一Native状态无法在限定修复内与官方训练器等价；必须再次利用公开validation选择参数或Gate；任何任务冻结确认退化；平台凭据/网络不可用时只允许把在线PyTRiO标为`BLOCKED_EXTERNAL`，不得制造成功证据。
- 边界：不运行新SFT、论文包装或模型家族搜索；允许D-062定义的成熟父链兼容方法，但只做train内部有证据的有界候选，不扩张为无界HPO；D-060只约束冻结的Protocol RC，竞争候选按D-061执行；不使用官方试运行机会完成基础调试。
- 计划：`superpowers/specs/2026-11-15-native-competitive-rc-design.md`、`superpowers/plans/2026-11-15-native-competitive-rc.md`
- 当前证据：Task 1逐状态等价门通过；Task 2竞争模式、真实retain和任务尺度Gate通过；Task 3冻结发布组合为A/C竞争策略+B复用旧protocol，一次冻结确认得到A `0.725695`、B `660.076488`、C `51.949287`。Task 4 Native PyTRiO取得2次非零响应/1次建议执行，第三次因服务RuntimeError保持外部阻塞；SwanLab三任务聚合记录已公开。Task 5完成377项回归、linux/amd64非root镜像、4核8GB断网30轮、独立预测、64 MiB、禁入扫描和`docker save/load`。归档SHA-256 `B4EF8820...5FB1BD7`；证据见`results/NATIVE-COMPETITIVE-RC-001-RELEASE.md`。本地任务完成，平台镜像/模型/试运行仍由`FORMAL-RELEASE-001`跟踪。

### PLATFORM-NATIVE-001 平台原生挂载训练/预测入口

- 状态：`DONE`
- 依赖：FORMAL-CONTINUATION-RC-001、O-PLATFORM-009
- 优先级：P0，当前唯一执行任务
- 完成标准：镜像无需完整官方包根即可直接读取`/data`与`/previous/checkpoint.npz`；父检查点模型、Adam、标准化、epoch/step真实续接；`describe/start/submit`本地契约模拟、独立预测、十轮均完成真实候选训练/验证/部署或拒绝、SwanLab离线聚合记录、原子输出与恢复通过；`checkpoint.npz`及模型产物不超过64 MiB；4核8GB断网容器模拟平台四挂载完成。
- 停止条件：必须猜测平台未公布的命令或JSON字段才能继续。此时保留自动发现/显式参数双入口和本地模拟证据，把精确启动映射标为外部阻塞，不伪造官方通过。
- 边界：旧`official-agent-run`整包审计继续用于本地研究，不得削弱；新入口只接受当前运行时数据和父检查点，不访问原始官方包根，不从头训练替代父模型。
- 证据：`src/brace_msi/platform_runtime.py`、`platform_advisor.py`、`platform_simulation.py`；专项15项、完整回归348项；A/B/C正式镜像各10轮/10决策/10候选、父链和独立预测通过；`docs/results/PLATFORM-NATIVE-001.md`；归档SHA-256 `F98FB679...CBC62D`。

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

- 状态：`DONE`
- 依赖：GENERALIST-MODEL-001
- 优先级：P1
- 完成标准：Gas/Bearing/Engine超过静态，至少两项显著改善；零泄漏；完整回归；Docker小于2GB、4核8GB、无公网、无数据/权重/密钥；满足后才生成新RC
- 上传验收：归档必须由`docker save`生成并可`docker load`；分别记录镜像可用、模型校验、续训协议和评测状态，不把上传完成冒充通过 `[O-PLATFORM-007]`
- 修订门：D-057在D-056负证据后将本地冻结标准修订为A不低于父模型、至少B/C两项改善；不再要求用不安全候选强行提高A，也不把A写成提升
- 实际：`BRACE-MSI-0.5.0rc1`已生成；329项回归通过，linux/amd64镜像241,051,292字节，4核8GB断网十轮Smoke、B/C完整训练、B/C独立预测、禁入扫描、`pip check`、`compileall`与`docker save/load`均通过。A按D-056保留父模型，因此没有满足“Gas严格超过静态”；B/C公开历史暴露验证分别由RMSE 681.159833/52.868573改善至675.010677/49.336020。该局限不隐瞒，不再重开validation调参。证据：`docs/results/DUAL-RC-001.md`。
- 正式边界修订：O-PLATFORM-008到达后，D-058将本任务产物降为研究RC并标记`DO_NOT_UPLOAD`；历史本地验收继续有效，但不能证明符合平台原生续训协议。

### FORMAL-CONTINUATION-RC-001 原生父检查点续训正式候选

- 状态：`DONE`
- 依赖：DUAL-RC-001、O-PLATFORM-008
- 优先级：P0，唯一当前任务
- 完成标准：正式镜像禁用全部异构研究模型命令；A/B/C均以官方训练器从官方baseline生成子checkpoint，再从子checkpoint续训生成孙checkpoint；schema、标准化、Adam、epoch、step和父哈希链可验证；独立预测、64 MiB、完整回归、4核8GB断网及`docker save/load`通过。
- 停止条件：需要猜测正式SDK字段、原训练包哈希变化、任一父链/schema/优化器状态验证失败、镜像包含数据/权重/密钥或容器验收失败。正式SDK字段仍可标记外部阻塞，但不得阻止平台无关续训候选构建。
- 选择边界：不重新打开公开validation调参，不重新训练HGB/PaperFusion，不消耗官方试运行；本任务只修复平台合规发布线，不产生新的性能结论。
- 证据：三任务父链专项3项、完整回归333项；linux/amd64镜像241,750,529字节，4核8GB断网A/B/C各十轮/3候选，三项`validate-only=true`，独立预测和异构命令失败关闭通过；`docker save/load`归档SHA-256 `6331280b...34e181`。详见`docs/results/FORMAL-CONTINUATION-RC-001.md`。

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
- 依赖：PLATFORM-NATIVE-001、正式SDK/SwanLab规范
- 优先级：P4
- 完成标准：Docker构建、4核8GB断网、正式RuntimeAdapter、最终模型重训SwanLab记录、十轮无人值守、干净环境独立复现及交付审计全部通过
- 停止条件：外部规范或容器环境缺失时明确`BLOCKED`，不得制造通过证据
- 本地证据：RC2运行时代码/全新venv均`221 passed`，`pip check`、编译、静态上下文与确定性源码归档通过；实际镜像170,356,869字节，linux/amd64、UID 10001、无禁入文件，4核8GB断网Smoke完成3候选；最终`docker save`归档SHA-256为`7b64490b0456c4b36bdc6189f34c9ce5e372894b911d76a3b40a6e8142e09327`，证据见`docs/results/RC2_CONTAINER_ACCEPTANCE.json`。
- RC3本地证据：最终代码回归`246 passed`、打包前全新venv`243 passed`；PyTRiO0.2.9依赖无冲突；实际镜像240,579,085字节、linux/amd64、UID10001、无Torch/数据/权重/密钥；4核8GB断网双协议Smoke完成3/4候选；`docker save`归档SHA-256为`0daef2e0e66cd2d3bc809a5d836a03020d1f90d677df91830fedc4feeb6d325a`并已重载。证据见`docs/results/RC3_CONTAINER_ACCEPTANCE.json`。
- RC4本地证据：最终代码回归`264 passed`；实际镜像240,701,023字节、linux/amd64、UID10001、无Torch/数据/权重/密钥；4核8GB断网完成Engine冻结候选训练，峰值RSS 3,198,783,488字节；`docker save`归档240,723,968字节，SHA-256为`97bb0a9fcfed688ba1b7feadadf09528e232fea578d06a1d782f2dccee306dfa`并已重载。证据见`docs/results/RC4_CONTAINER_ACCEPTANCE.json`与`docs/results/RC4_VERIFICATION.json`。
- 基础模型兼容进度：平台重复拒绝持久化Sampler而接受Qwen3.5-4B基础模型后，`0.4.1rc1`已通过TDD专项27项与完整回归271项；CLI允许`provider=pytrio/model_path=None`，仍保留显式provider、失败关闭和非零调用要求。单次本机在线Smoke无响应且无收据，已按预注册停止，不写成通过；本地镜像验收见下一条。
- RC6本地证据：`0.4.1rc1`镜像linux/amd64、240,662,396字节、UID10001、无Torch/数据/权重/密钥；4核8GB断网Synthetic Smoke完成。基础模型入口无Sampler路径时在断网环境8.696秒明确失败关闭且运行文件0项；归档240,685,056字节，SHA-256 `63fff363...54e48e`并经`docker load`验证。见`RC6_CONTAINER_ACCEPTANCE.json`与`RC6_VERIFICATION.json`。
- RC7本地证据：`0.5.0rc1`完整回归329项；镜像241,051,292字节、linux/amd64、UID10001、无数据/权重/密钥；4核8GB断网十轮Smoke、B/C通用父集成训练与独立预测通过；归档241,074,176字节，SHA-256 `e3cc5f1c...9799747`并经`docker load`验证。A按SafetyGate保留父模型。见`DUAL_RC_CONTAINER_ACCEPTANCE.json`、`DUAL_RC_VERIFICATION.json`与`DUAL-RC-001.md`。
- RC8本地证据：D-058后`0.5.1rc1`恢复为官方原生MLP续训；完整回归333项，A/B/C容器各十轮/3候选、父链/schema/Adam/预处理连续、独立预测和正式命令边界均通过。linux/amd64镜像241,750,529字节；归档241,774,080字节，SHA-256 `6331280b...34e181`并经`docker load`验证。见`FORMAL_CONTINUATION_RC_CONTAINER_ACCEPTANCE.json`、`FORMAL_CONTINUATION_RC_VERIFICATION.json`与`FORMAL-CONTINUATION-RC-001.md`。
- RC9本地证据：`0.6.0rc1`新增直接四挂载原生入口和逐轮决策收据；完整回归348项，A/B/C各完成10轮/10决策/10真实候选及独立预测，共30轮父链连续。镜像241,855,558字节；归档241,879,040字节，SHA-256 `F98FB679...CBC62D`并经`docker load`验证。见`docs/results/PLATFORM-NATIVE-001.md`。
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
