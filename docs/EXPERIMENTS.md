# 实验登记与结果

本文件是全部实验运行的唯一登记处，包括失败和中止实验。

## PYTRIO-ONLINE-001（COMPLETED_PASS）

- 研究问题：此前两次有效基础模型响应后出现的连续`RuntimeError`是否主要由过短客户端超时导致；扩大到60秒但保持一次SDK尝试，能否获得至少3次独立非零Token严格提案并由RC7安全执行至少1次？
- 输入：仅使用不含原始样本、标签、路径或凭据的聚合AgentContext；随后用官方A包公开train首批和父checkpoint做一次受控入口验收，不读取公开validation。
- 模型：平台已校验的`Qwen/Qwen3.5-4B`基础模型；不使用Sampler路径，不训练LoRA。
- 预算：最多6次远程采样；每次最多768输出Token、60秒客户端超时；沿用既有10元累计上限；官方试运行0次。
- 成功标准：至少3次非零Token且严格schema合法的响应；至少1次提案通过RC7白名单并实际进入候选执行；完整收据含哈希、Token、延迟和失败分类但不含凭据/原始响应。
- 停止条件：达到成功标准立即停止，或6次额度用尽/余额不足/服务持续异常即保留负证据停止。
- 代码基线：`3587fcde9381f919e869d18569b13582e07755ec`；分支`codex/native-competitive-rc`。
- A1结果：三个独立进程均在第一次请求内获得严格合法提案，输入/输出Token分别为`330/184`、`370/197`、`403/200`，累计`1103/581`；第1轮建议按冻结策略真实训练候选，第2/3轮因不在候选日程而retain。公开validation、LoRA/SFT和官方试运行使用均为0。摘要SHA-256为`3005C56BAE0AF4A444B6CD231C449F34F66A1A049D351E4415B132F4D063C7AF`。
- 根因与修正：此前有效调用约14.86秒，而失败验收使用更短窗口；A1的三次有效调用耗时13.33—16.56秒。正式入口默认超时由15秒提高到60秒，仍保留SDK单次尝试和Harness至多一次重试。
- 容器发布验收：`0.7.1rc1`只内置7个固定SHA-256的Qwen3.5-4B Tokenizer/配置文件（22,912,511字节），不包含任何模型权重。4核8GB、只读根、256 PID容器在只挂载运行时凭据、不挂载宿主Tokenizer缓存时一次请求成功，330/184 Token、4.620秒，`incremental_update`候选真实训练；独立断网运行两次失败后执行`noop/retain`且候选训练为false。完整回归383项通过；归档SHA-256为`6BA798571F88CC88A6FB298FA63E99CE723DFCC057A3BDEB9EF103E69DCF3CFE`。

## NATIVE-COMPETITIVE-RC-001（REGISTERED）

- 研究问题：平台原生执行器与官方训练器逐状态等价后，迁移已冻结日程并使用train内部风险规则，能否形成同时具备性能、协议、PyTRiO、SwanLab和Docker证据的新竞争RC？
- 数据：官方A/B/C训练包；参数和Gate选择只使用train内部批次/组证据；公开validation只在配置冻结后读取一次，不反馈调整。
- 对照：`0.6.0rc1`原生结果、早期冻结日程证据；不把两者成绩混为同一实验。
- 预算：不新增HPO、SFT、论文复现或官方试运行；PyTRiO仅做Native入口最少3次非零Token验收；A/B/C最多各10轮、每轮0或1候选。
- 成功标准：见`TASKS.md`的`NATIVE-COMPETITIVE-RC-001`；所有失败、等价差异和发布阻塞必须保留。
- 代码基线：`836920c`；执行分支`codex/native-competitive-rc`。
- Task 1结果：A/B/C官方Model与Native一轮loss、全部权重、Adam、预处理、metadata及预测逐值相同；Native 1+1与连续2 epoch逐状态相同。相关37项测试通过。既有30轮只读反事实确认A/B/C正收益候选为0/4/6、接受0/1/0；结果见`results/NATIVE-COMPETITIVE-RC-001-PARITY.md`。
- DEV-A1：`COMPLETED_NEGATIVE_TRAIN_INTERNAL`。三个候选集中在前3轮；A不变，B从RMSE 233.357824退化到239.789618，C未形成可接受全历史优势。摘要`D:/brace-msi-native-competitive/NATIVE-COMPETITIVE-RC-001-DEV-A1/summary.json`，SHA-256 `E2C7A00EBD0289FCA0BB458190FCE7F156D9B4F940A4CD43B94F86069E8090CB`。
- DEV-A2：`COMPLETED_MIXED_REJECTED_TRAIN_INTERNAL`。候选分散到第1/5/9轮；A不变，B首轮错误部署后RMSE从233.357824退化到299.846993，C RMSE从55.380385小幅改善至55.342797但MAE退化。摘要`D:/brace-msi-native-competitive/NATIVE-COMPETITIVE-RC-001-DEV-A2/summary.json`，SHA-256 `7A73559F89C3EF480466529CFAE401298823CE0B6717492CB4023C3DC4E668D4`。
- Task 2修正：首轮候选因缺少历史证据只训练不部署；B/C强候选移到第5轮，最后一轮为低成本候选。专项32项、完整回归365项通过。公开validation、官方试运行和在线PyTRiO调用均为0。
- DEV-A3：`COMPLETED_SAFE_NO_GAIN`。三任务各10决策/3候选，父链均有效；A/B/C接受数均为0，train全历史指标与父模型相同。摘要SHA-256 `F0584EE6C1613023CDF8517C47FA51291C0039F87ECA8778C3661017D202FC2A`。A第9轮当前Gate持平但Replay Macro-F1从0.787783升至0.988676，揭示Gate未利用安全历史收益；B/C强候选在第5轮历史仍不足。公开validation、官方试运行和在线PyTRiO调用均为0。
- DEV-A4：`COMPLETED_ONE_GAIN`。A接受第9轮安全Replay候选，train Macro-F1从0.955754升至0.990778；B/C保持父模型。摘要SHA-256 `18958383B31ECE64360B36CB6474E7F3FB88D3AEF3BCDB5401590F661E02D23B`。C第9轮当前RMSE与历史主辅指标、Anchor均改善，但当前MAE只退化0.54%，被零容忍辅助门拒绝；B当前主辅指标明显恶化，继续拒绝。
- DEV-A5：`COMPLETED_FROZEN_TRAIN_INTERNAL`。A Macro-F1 `0.955754 -> 0.990778`，C RMSE/MAE `55.380385/40.580370 -> 54.967102/40.047855`，B保持父模型；A/C各接受1个候选，B拒绝全部3个。累计CPU约1.02/5.78/22.11秒，峰值RSS约85.1/160.0/247.7MB，父链均有效。摘要SHA-256 `A5981B9F8FABE02CC5475AF609CE61F095ADB35BB99126C4236975CF2C965FCF`。
- CONFIRM-A1预注册：`FROZEN_NOT_RUN`。配置`configs/platform_native_competitive_frozen.json`，SHA-256 `5D9147818562FA5A4F17E8269B1A1E68E71D3A4EBFE7669BB486B6AAE1DF5E8A`；冻结后仅一次读取三任务公开validation。成功门：相对`0.6.0rc1`的A/B/C `0.714030/660.076488/52.868573`均不退化且至少两个任务严格改善；结果只决定发布或退回，不再调参重开。
- CONFIRM-A1：`COMPLETED_MIXED_NOT_RELEASEABLE_ALONE`。A Macro-F1 `0.725695`、C RMSE `51.949287`优于`0.6.0rc1`；B因竞争策略retain回官方父模型，RMSE `681.159833`低于`0.6.0rc1`的`660.076488`。摘要SHA-256 `73371324359ABA3B59BA60BBF661E9861DF7BB14A366FB8D57C682AFE32609B9`。按预注册不修改竞争参数、不重开validation。
- COMPOSE-A1：`INVALID_CONFIGURATION`。虽然B路由进入protocol，但配置仍设`max_training_rounds=3`，导致旧协议第4—10轮未训练，不能代表`0.6.0rc1`；A/B/C候选总数仅9而非16。结果保留但不用于发布，未读取validation。
- COMPOSE-A2预注册：`RUNNING_TRAIN_INTERNAL`。唯一修正是`max_training_rounds=10`；A/C仍由固定日程限制为各3候选，B完整执行10候选。成功标准：候选总数16，B路由与旧protocol测试等价，A/C结果复现A5；不读取validation。
- COMPOSE-A2：`COMPLETED_RELEASE_COMPOSITION_TRAIN_INTERNAL`。候选数A/B/C=`3/10/3`，接受数均1，父链均有效；A/C复现DEV-A5，B复现protocol行为。摘要SHA-256 `CBF2FF87DF6DB1252E54F827FD2A6C131F4D2A7236C0AEB09B28E0E859D115C5`，配置SHA-256 `66BAE85D4DA6A50BA66EB64C89E431A049BC30F4D18170C3388F77DDA6C20314`。公开validation未重开。
- NATIVE-PYTRIO-A1：`COMPLETED_MIXED_NOT_ACCEPTED`。第1轮服务返回376/311个非零Token及合法action，但包含Native未执行的额外参数，建议被安全拒绝；第2/3轮各两次RuntimeError后retain，Token为0。没有把失败冒充Agent成功。摘要SHA-256 `D05760D35998D314DB16125E2218528CAEBC3C17B16D61F83076EFCE6E3F64FF`。
- NATIVE-PYTRIO-A2：`COMPLETED_PARTIAL`。首轮Qwen建议被执行，362/208 Token；后两轮同进程内各两次RuntimeError并retain。提示词收紧已解决参数拒绝，但连续服务调用仍不稳定。
- NATIVE-PYTRIO-A3预注册：`READY_SINGLE_RECOVERY_CALL`。使用全新进程继续A2已提交的3轮历史，仅调用第4轮一次（仍允许SDK内部一次重试）；若获得非零Token且建议执行，则与A1/A2首轮共同构成3次非零调用证据。无论成败停止远程验收，不扩大费用。
- NATIVE-PYTRIO-A3：`BLOCKED_EXTERNAL_RETAINED`。全新进程继续3轮历史，但两次RuntimeError、Token为0，执行noop/retain；摘要SHA-256 `DA70C131F519304CA63D2DECA4A9B450E2467B94F49CA8DBDA336CC02E8E7B64`。A1/A2合计只有2次非零Token响应、1次建议执行，未达到3次门，不再消耗余额。
- SWANLAB-NATIVE-RC-A1：`COMPLETED`。COMPOSE-A2的A/B/C三项聚合离线记录经敏感扫描后同步到`brace-msi-platform-native`，各112条；链接与边界见`results/NATIVE-COMPETITIVE-RC-001-PYTRIO-SWANLAB.md`。

## PLATFORM-NATIVE-CONTAINER-002-A2-FINAL

- 状态：`COMPLETED_PASS`。
- 目的：验证平台原生四挂载入口在A/B/C上均完成全部10个决策轮和10次真实候选，而非只检查前三轮。
- 环境：真实Linux/amd64 Docker，4核、8GB、断网、256 PID、只读根文件系统、无GPU；本地确定性Advisor，官方试运行0次。
- 结果：A/B/C均为10轮、10决策、10候选和连续父链；接受数0/1/0；独立预测1,244/1,679/23,049行。完整回归348项通过。
- 产物：`D:/brace-msi-platform-native-container/PLATFORM-NATIVE-CONTAINER-002-A2-FINAL/`；机器摘要SHA-256 `EAB693A1F423B8B1B4A8FF91302FFB705F6D4ED898B4FE6E4E8F61D98140BA5E`；聚合报告`docs/results/PLATFORM-NATIVE-001.md`。正式`docker save`归档SHA-256为`F98FB679D1216564634382E00CC105980C7857021BE33F99A59A240496CBC62D`。
- 边界：公开validation历史暴露；断网验收没有真实PyTRiO Token；不宣称平台或隐藏测试通过。

## PLATFORM-NATIVE-SIM-001-A1（REGISTERED）

- 目的：在不消耗平台试运行机会的前提下，按O-PLATFORM-009四挂载契约模拟A/B/C十轮原生父检查点续训，验证每轮真实候选、父链、门控、独立预测、资源记录与SwanLab离线记录。
- 配置：`configs/platform_native_simulation.json`；代码基线为本次任务提交前工作树，最终报告必须补充固定Git提交。
- 输入：只读官方训练包的`public/train.jsonl`与初始`checkpoint.npz`；运行时每轮只物化当前批次与平台父检查点，不向原生入口暴露包根、`training.json`或`baselines/`。
- 预算：A/B/C各10轮，每轮1 epoch、1个真实候选；总候选30；4核8GB；无GPU；不调用付费API；Qwen Token为0；官方试运行0次。
- 成功标准：三任务各10轮、10个真实候选、父SHA链连续、候选训练与门控收据齐全、独立预测成功、模型产物小于64 MiB、SwanLab离线实验可生成；任何任务不得以预设NOOP代替完整轮次。
- 停止条件：父检查点不兼容、当前批次少于合法切分下限、出现schema/未来数据泄漏、父链断裂、资源超限或SwanLab记录包含逐样本数据。
- 结果边界：本地平台挂载模拟，不是官方隐藏评测或正式成绩；公开训练数据用于流程验收，不据此调参。

## PLATFORM-NATIVE-SIM-001-A2（REGISTERED）

- 目的：在A1十轮/30候选流程证据基础上，增加与训练流完全分离的`public/validation.jsonl`独立预测，并在相同样本上比较初始父模型和十轮最终模型，发现累积续训退化而不是只证明程序完成。
- 配置：`configs/platform_native_simulation_a2.json`。
- 输入与预算：同A1；训练仍只读取`public/train.jsonl`十个互斥顺序批次，最终预测/指标只读取公开validation，不回流到动作或参数选择；A/B/C各10轮、总候选30、官方试运行0次。
- 成功标准：A1全部流程标准，加上三任务初始/最终主辅指标、独立预测行数和公开validation隔离证据。
- 结果边界：validation已有历史暴露，只能用于回归验收和退化检测，不能宣称独立泛化或官方成绩；本轮结果不得触发继续调参。

## PLATFORM-NATIVE-SIM-001-A3（REGISTERED）

- 假设：A2的Bearing恶化来自仅以当前批次Gate部署、没有历史保护与Replay；加入首批固定Anchor和最多4096条合法历史Update回放，可在十轮全部真实训练的同时降低顺序遗忘。
- 配置：`configs/platform_native_simulation_a3.json`；相对A2只新增`max_anchor_degradation=0`和`max_replay_samples=4096`，其他预算、数据顺序和最终验证不变。
- 成功标准：A/B/C均完成10个真实候选且父链连续；B最终公开validation不得低于其初始父模型；Anchor、Replay样本数和门控原因逐轮可审计。
- 停止条件与结果边界：同A2；若仍退化则保留负结果并修正动作/门控，不得用减少真实轮次掩盖。

## PLATFORM-NATIVE-SIM-001-A4（REGISTERED）

- 假设：A3退化来自零收益仍部署及当前Gate小幅收益噪声；要求严格正收益、相对改善至少5%且Anchor不退化，可保留十轮真实候选同时拒绝证据不足更新。
- 配置：`configs/platform_native_simulation_a4.json`；相对A3只新增`min_relative_improvement=0.05`并把绝对门改为严格大于。
- 成功标准：三任务各10个真实候选、零预设NOOP、父链连续；三任务最终validation均不低于各自初始父模型，至少一项有改善。
- 结果边界：同A2/A3，公开validation仅作本地回归验收，不反馈继续调参或包装为官方成绩。

## 当前汇总

- 正式实验：0
- 探索实验：7（既有3项、XJTU A1/A2、规则对齐开发及官方训练包本地开发实验）
- 工程验收实验：2次运行尝试（A1 INVALID、A2 SUCCEEDED）
- 训练运行：58（新增官方训练包本地开发15个真实候选；全部为本地开发任务，无官方评分实验）
- 已报告模型指标：仅本地代理/开发实验，见`results/LOCAL-SMOKE-001.md`、`results/LOCAL-EXP-001.md`、`results/XJTU-LOCAL-DEV-001.md`、`results/OFFICIAL-RULES-ALIGNED-DEV-001.md`与`results/OFFICIAL-PACKAGE-DEV-001.md`
- 完整系统模拟：`LOCAL-FORMAL-SIM-001`已完成（只用合法开发段与合成协议任务）

Gas和C-MAPSS已完成只读审计、代理开发训练和预注册实验；所有结果仍是`proxy_only`，不得表述为官方成绩 `[L-DATA-001]` `[L-DATA-002]`。

`OFFICIAL-PACKAGE-DEV-001`已从干净提交完成；结果只属于公开开发包本地续训，不增加“正式实验”计数。

## 状态定义

- `PLANNED`：已预注册，尚未运行。
- `RUNNING`：正在执行。
- `SUCCEEDED`：按协议完成，不代表结论为正。
- `FAILED`：运行失败，保留根因和产物。
- `STOPPED`：触发预注册停止条件。
- `INVALID`：存在泄漏、协议偏差或证据不完整，不得用于结论。

## 登记表

| 实验ID | 状态 | 研究问题 | 数据/切分 | 代码与配置 | 资源预算 | 结果 | 产物 |
|---|---|---|---|---|---|---|---|
| LOCAL-SMOKE-001 | SUCCEEDED | 两类代理任务能否在低成本下完成三策略端到端闭环，并真实执行增量与重拟合候选？ | Gas每批最多96条、FD001前20台发动机；只用初训和开发流，未打开完整密封段 | `configs/local_smoke.json`；执行提交`64ccce2` | 每个任务×策略最多4候选、20,000训练样本、60秒墙钟/CPU；种子20261106 | 6/6运行完成；增量10、重拟合3；指标见结果文档，不能外推 | `results/LOCAL-SMOKE-001.md`；本地`artifacts/experiments/LOCAL-SMOKE-001/run-64ccce2/` |
| LOCAL-EXP-001-DEV | SUCCEEDED | 全量开发流上三策略能否公平完成并覆盖真实动作，足以冻结密封运行？ | Gas批次1–7；FD001发动机1–80；未打开密封段 | `configs/local_full_dev.json`；执行提交`f9647dd` | 每个任务×策略最多4候选、80,000训练样本、180秒墙钟/CPU；种子20261106 | 6/6完成；增量9、重拟合5；机器验收通过 | 本地`artifacts/experiments/LOCAL-EXP-001-DEV/run-f9647dd/` |
| LOCAL-EXP-001 | SUCCEEDED | 冻结策略在完整密封段的性能、最差阶段与资源相对静态/简单触发如何？ | Gas冻结1–3/4–7/8–10；FD001发动机60%/20%/20%；密封仅运行一次 | `configs/local_full.json`；执行提交`f9647dd`，与DEV阈值一致 | 同DEV；密封阶段禁止训练；种子20261106 | 6/6完成；开发指标与DEV完全一致；密封指标见结果文档 | `results/LOCAL-EXP-001.md`；本地`artifacts/experiments/LOCAL-EXP-001/run-f9647dd-sealed-once/` |
| LOCAL-FORMAL-SIM-001-A1 | INVALID | 完整候选Harness能否在三任务上无人干预完成初始化、至少三次候选、部署/拒绝、恢复、记录、资源审计和报告？ | Gas仅1–7；FD001仅发动机1–80；合成轴承漂移流仅作协议验收；未加载/评估已消费密封段 | `configs/formal_simulation.json`；预注册`ee2c3a6`/`a99656c`；执行`ce3e907` | 每任务最多8候选、80,000训练样本、120秒候选墙钟/CPU；进程最多4逻辑CPU；RSS验收8GB | 运行完成，但验收器把2次注入失败误算为真实训练，合成任务实际只完成2次模型拟合；最终自审判定INVALID | 本地保留`artifacts/formal_simulation/LOCAL-FORMAL-SIM-001/run-ce3e907/`，不得作成功证据 |
| LOCAL-FORMAL-SIM-001-A2 | SUCCEEDED | 修正真实候选计数和审计恢复后，是否满足原预注册工程验收标准？ | 与A1完全相同，仅开发段与合成协议流；不用于性能调参 | 原配置不变；执行`7ef3829` | 与A1相同 | 三任务真实候选4/4/3；动作增量7、回放1、HPO3；机器验收通过 | `results/LOCAL-FORMAL-SIM-001.md`；本地`artifacts/formal_simulation/LOCAL-FORMAL-SIM-001/run-7ef3829/` |
| XJTU-LOCAL-DEV-001-A1 | INVALID | 新增XJTU-SY数据能否在严格按轴承分组下完成可恢复特征缓存、强静态基线和两种自主更新策略？ | 9初训/3开发；密封未加载；自定RUL，仅本地开发 | `configs/xjtu_local_serial.json`；实现提交`2460577` | 4逻辑CPU；策略最多8候选、50,000训练样本、600秒候选墙钟/CPU | 5轮运行成功，但事后审查发现静态模型用了全部9个初训轴承，策略留出2个锚点，配对比较不公平，判定INVALID | `D:/brace-msi-xjtu/XJTU-LOCAL-DEV-001/experiments/`与`A1-INVALID.json`完整保留 |
| XJTU-LOCAL-DEV-001-A2 | SUCCEEDED | 修复初训可见性后，五轮队列能否完成且形成至少3次真实候选？ | 静态与策略均用相同7个初训轴承训练、2个初训轴承作锚点；3开发；密封未加载 | 同一配置；修正代码提交`2e29ae7` | 同A1 | 5/5轮完成，指标有限；BRACE完成3次真实候选并全部被门控拒绝；简单触发0次动作；机器验收`valid=true` | `results/XJTU-LOCAL-DEV-001.md`；本地`D:/brace-msi-xjtu/XJTU-LOCAL-DEV-001/experiments-a2/`与`validation-experiments-a2.json` |
| OFFICIAL-RULES-ALIGNED-DEV-001 | SUCCEEDED | 参数量匹配的可替换MLP检查点与BRACE能否在三官方任务口径下完成每任务10轮、三策略公平比较，并形成35分维度的本地证据？ | Gas 1–3初训/4–7开发重分10轮；FD001发动机1–60初训/61–80每2台一轮；XJTU 9初训/3开发按轨迹进度合成10轮；所有既有密封段关闭 | `configs/official_rules_aligned_dev.json`；执行提交`512d477`；报告提交`9c7bdba` | 最多4逻辑CPU、RSS<8GB；每策略10决策轮，候选预算按配置；种子20261111 | 9/9完成、机器验收有效；Gas BRACE +0.229939 Macro-F1，Engine BRACE改善0.248934 RMSE，Bearing BRACE退化35.086308 RMSE；D-027停止同流继续调参 | `results/OFFICIAL-RULES-ALIGNED-DEV-001.md`；本地`D:/brace-msi-official-dev/OFFICIAL-RULES-ALIGNED-DEV-001/` |
| OFFICIAL-PACKAGE-DEV-001 | SUCCEEDED | 原版训练器真实续训下，单次固定低成本续训与BRACE在A/B/C公开开发包上的候选适应结果、父链安全与资源成本如何？ | 三包只读`public/train.jsonl`续训；同包`public/validation.jsonl`仅作候选门控；无隐藏测试、无真实时间批次 | `configs/official_package_dev.json`；执行`34098bf`，干净工作树 | 总估算CPU≤3600秒、墙钟≤1800秒、磁盘≤200MiB；每策略≤3候选、≤600秒CPU/墙钟 | 9/9作业、15候选、机器验收有效；A/B BRACE与低成本对照持平但更贵，C BRACE RMSE 51.889566优于对照52.350178；A1导入失败0训练负证据保留 | `results/OFFICIAL-PACKAGE-DEV-001.md`；`D:/brace-msi-official-package/OFFICIAL-PACKAGE-DEV-001/` |
| UNIFIED-POLICY-OPT-001-SMOKE-A1 | INVALID | 一套身份盲、无量纲共享策略能否在三个公开任务的中期开发段完成四策略公平比较和任务级留一验证？ | Gas 1–3初训/4–7中期；FD001 1–60初训/61–80中期；XJTU 9初训/3中期；所有末期数据关闭 | `configs/unified_policy_optimization.json`；执行提交`cf3adcc`；CLI另传`mlp_max_iter=8` | 2个共享候选、15作业；官方测试次数0 | 15/15完成且机器验收通过，但终审发现CLI的MLP迭代数未进入执行manifest，恢复可混入不同训练协议，因此判定INVALID，不用于选型 | `D:/brace-msi-unified/UNIFIED-POLICY-OPT-001-SMOKE/`完整保留 |
| UNIFIED-POLICY-OPT-001-SMOKE-A2 | SUCCEEDED | 修复评估器身份冻结后，真实三任务Smoke能否形成可恢复、公平且可复算的统一策略证据？ | 与A1相同，只用初训和中期开发段 | `configs/unified_policy_smoke.json`；执行提交`72898b9` | 固定MLP 8迭代、2共享候选、15作业；官方测试次数0 | 15/15完成，机器验收`valid=true`；3个任务级留出fold完成；Smoke胜者`shared-47a97ce002b9`，只作运行证明，不直接冻结最终配置 | `D:/brace-msi-unified/UNIFIED-POLICY-OPT-001-SMOKE-A2/` |
| UNIFIED-POLICY-OPT-001-DEV-A1 | SUCCEEDED_WITH_STOP | 24组共享策略参数中，哪一组在三个任务级留一验证上具有最佳最差任务表现、平均增益和资源效率？ | 与Smoke相同，只用初训和中期开发段；末期关闭 | `configs/unified_policy_optimization.json`；执行提交`e057589` | 24共享候选；9基线+72 BRACE=81串行作业；MLP 80迭代；官方测试次数0 | 81/81完成、严格验收`valid=true`；复杂BRACE在3/3留出fold相对简单策略无优势且资源更高，触发预注册停止规则；冻结简单性能触发候选，复杂配置仅作对照 | `docs/results/UNIFIED-POLICY-OPT-001.md`；`D:/brace-msi-unified/UNIFIED-POLICY-OPT-001-DEV-A1/` |
| FORMAL-AGENT-SMOKE-001 | SUCCEEDED | 新的受控Agent Harness能否在不调用模型服务时，用同一入口分别驱动A/B/C官方原版训练器并保留预算、父链、门控和审计？ | 官方A/B/C公开train续训、公开validation仅门控；每任务仅运行第1轮；不用于算法选型或正式成绩 | `configs/formal_agent_dev.json`；执行提交`24c70c8` | 每任务最多1个1-epoch候选；合计CPU≤300秒、墙钟≤300秒；Token=0；官方试运行=0 | 3/3各完成1个真实候选且均接受；机器复算3/3 `valid=true`；合计CPU 12.75秒、Token 0；只证明主链路，不形成新独立性能结论 | `docs/results/FORMAL-AGENT-SMOKE-001.md`；`D:/brace-msi-formal-agent/FORMAL-AGENT-SMOKE-001/` |
| PERF-A-OVER-001 | STOPPED_NEGATIVE | 只用Batch 1确定性过采样Acetaldehyde，能否缓解Batch 2该类F1=0并提高Gas Macro-F1？ | Batch 1训练；Batch 2按类别+固定哈希预先冻结70%开发/30%确认；确认整体历史暴露，样本级候选指标未读取 | 预注册`0944b9f`；执行`af335e4` | 6个1-epoch候选；CPU≤120秒、墙钟≤180秒、RSS≤1GiB；Token/官方试运行均0 | 6/6完成但Acetaldehyde开发F1均为0；最高Macro-F1 0.743187仍未过双门；确认未打开，按停止条件不扩大过采样搜索 | `docs/results/PERF-A-OVER-001.md`；`D:/brace-msi-performance/PERF-A-OVER-001/` |
| PERF-A-REPLAY-001 | SUCCEEDED_WITH_STOP | 当前批次先预测、收到标签后用当前数据与有限历史回放更新，能否提高后续Gas批次恢复并控制遗忘？ | 官方原始Gas：Batch 2—5开发，Batch 6—7冻结确认；Batch 8—10禁止加载；每批按类别+固定哈希留20%只作当轮门控 | `configs/perf_a_replay.json`；实现`4159b66`；A2执行`cb6d187` | 3策略、总15候选；CPU≤300秒、墙钟≤480秒、RSS≤1GiB；Token/官方试运行均0 | A1在训练前因Batch 4哈希手工转录错误失败并保留；A2完成15候选，`current_only`开发均值0.587581，两回放均0.580352未过+0.005门；确认上简单策略仍胜出，停止回放扩展 | `results/PERF-A-REPLAY-001.md`；`D:/brace-msi-performance/PERF-A-REPLAY-001/` |
| REGRESSION-SPRINT-001 | SUCCEEDED | B/C各一次9候选有界矩阵能否稳定超过官方静态基线并固化安全候选？ | B整轴承`*_1/*_2/*_3`训练/开发/确认；C整发动机FD001+2/FD003/FD004训练/开发/确认；公开validation仅冻结后门控 | `configs/regression_sprint.json`；执行提交`241a465` | 每任务1父模型+9矩阵+1最终候选；单次≤180秒；官方试运行/PyTRiO/SwanLab=0 | A1训练前缓存指纹失败、0候选；修复后B/C均9/9成功并接受：B RMSE 681.159833→637.180224，C 52.868573→52.367735；两者MAE均改善，按D-039停止搜索 | `results/REGRESSION-SPRINT-001.md`；`D:/brace-msi-sprint/REGRESSION-SPRINT-001/`；机器校验`valid=true` |
| SPRINT-HARNESS-001 | SUCCEEDED | 三个冻结任务候选能否在同一确定性Harness中各完成10轮、3次真实候选、预算检查、MAE风险门控和7次有理由跳过？ | 官方A/B/C公开训练包；不是实时漂移流，公开validation为历史暴露候选门控 | `configs/sprint_harness.json`；执行提交`09770c6`，干净树 | 每任务3候选、10轮、CPU/墙钟≤600秒、RSS≤512MiB；Token/官方试运行/SwanLab=0 | A/B/C均10轮、3候选、7 no-op并复算有效；稳定主指标0.725695/637.180224/51.635999，C进一步改善；回归MAE均未退化 | `results/SPRINT-HARNESS-001.md`；`D:/brace-msi-sprint/SPRINT-HARNESS-001/` |
| RC2-CONTAINER-ACCEPTANCE-001 | SUCCEEDED | RC2 Harness镜像能否在真实Linux容器中满足体积、非root、禁入文件、4核8GB断网和归档可重载要求？ | 仅协议合成Smoke；不加载官方/代理原始数据，不形成性能结论 | Dockerfile来自干净提交`e28113c`；镜像`brace-msi:0.2.0rc2` | `--network=none --cpus=4 --memory=8g --pids-limit=256`；镜像<2GB | 镜像170,356,869字节，UID 10001、`pip check`通过、禁入文件0；Smoke完成3候选；`docker save`归档可重载 | `docs/results/RC2_CONTAINER_ACCEPTANCE.json`；`D:/brace-msi-release/BRACE-MSI-0.2.0rc2/BRACE-MSI-0.2.0rc2-image-clean.tar` |
| PYTRIO-SFT-001-A1 | FAILED | 对Qwen3.5-4B进行有界SFT，能否提高BRACE提案严格schema有效率和允许动作/工具匹配率，并得到可提交的持久化Sampler？ | 24条合成聚合决策训练场景；12条archetype与scenario ID均隔离的留出场景；无工业原始样本、标签、任务名称、密钥或隐藏数据 | 执行提交`0e9884b`，实现基线`2e0ca6a`；语料SHA见预注册 | rank 8、3 epoch、batch 4、计划18步；官方试运行0；用户充值10元；估算≤0.65元 | 基础评测12/12完成但schema有效率0；输入4,213/输出2,425 Token。首个forward/optim返回后，本地loss把SDK `TensorData`直接传NumPy导致`TypeError`，训练进度0、Sampler未保存；立即停止且未自动重试 | `D:/brace-msi-pytrio/PYTRIO-SFT-001-A1/failure.json`、`base_evaluation.json` |
| PYTRIO-SFT-001-A2 | SUCCEEDED | 修复真实SDK `TensorData`兼容后，同一冻结SFT是否完成并生成有效持久化Sampler？ | 与A1完全相同的24训练/12留出及固定SHA，不新增样本或调参 | 修复提交`441aeb8`；启动前全量`235 passed`；终止标记修复`6da8cea`后全量`236 passed` | rank 8、3 epoch、18步；累计PyTRiO总预算≤10元；官方试运行0 | 18/18远程步完成，最终loss 0.009076，持久化Sampler已生成；原始评测因SDK文本保留`<|im_end|>`误记全0，保留原件；精确终止标记修复后的同Sampler复评为schema/budget 100%、action/tool/policy 66.67%，相对基础模型全0显著改善 | `D:/brace-msi-pytrio/PYTRIO-SFT-001-A2/result.json`、`persistent_sampler.json`、`tuned_evaluation_rescored.json` |
| PYTRIO-HARNESS-001-A1 | SUCCEEDED_NEGATIVE | A2持久化Sampler面对真实A/B/C官方包的首轮聚合状态时，能否分别给出可执行且不越权的提案？ | 每任务仅首轮提案；复用原始官方包和稳定检查点，不打开隐藏数据；若提案为noop则本轮不训练 | 执行基线`512680c`，解析器修复`6da8cea`，完整回归236项 | 3次Sampler调用；候选训练最多3个但只有提案允许时发生；累计PyTRiO≤10元；官方试运行0 | A/B/C均返回schema有效、预算安全的noop；输入352/350/350、输出均67 Token；候选0、稳定指标不变。证明Sampler不会无证据训练，但暴露“最低三次真实候选”合规证据未进入上下文 | `D:/brace-msi-pytrio/PYTRIO-HARNESS-001-A1/A|B|C/state.json` |
| PYTRIO-HARNESS-001-A2 | SUCCEEDED_NEGATIVE | 加入身份无关的最低候选证据和确定性合规守卫后，PyTRiO+BRACE能否在A/B/C各完成10轮、至少3次真实候选，并保持稳定模型不低于初始基线？ | 同一官方训练包、同一`formal_agent_dev.json`与SafetyGate；deterministic和pytrio两个独立运行根；不使用隐藏数据/官方试运行 | 执行提交`29a9c7e`；专项31项通过；A1负结果保留 | 每臂每任务10轮、最多3候选；PyTRiO最多30次调用；累计费用≤10元；CPU/墙钟/RSS按配置 | 六运行均10轮/3候选且`valid=true`；两臂A/B/C最终指标完全相同0.725695/656.351785/52.350178。Sampler 30/30建议noop，9次训练由守卫覆盖；增加20072/1961 Token，无性能增益 | `docs/results/PYTRIO-HARNESS-001-A2.md`；`D:/brace-msi-pytrio/PYTRIO-HARNESS-001-A2/` |
| PYTRIO-SFT-001-A3 | SUCCEEDED | 唯一一次合规语料SFT能否让Sampler在身份无关的最低候选证据下主动提出正确动作，同时保持安全noop和严格schema？ | 48训练：原v1训练24条+新增合规24条；12条新archetype留出，与新增训练ID/archetype不交叉；不含工业样本、任务名、凭据或隐藏信息 | 语料提交`9db3035`；train SHA `c9802d49...935f69`，eval SHA `67b823d9...161b12` | Qwen3.5-4B、rank8、3 epoch、batch4、36步、lr1e-4；累计预算≤10元、官方试运行0 | 36/36远程步完成，最终loss 0.017709；新留出schema/action/tool/budget/policy均100%；真实首轮A/B/C 3/3主动提出并执行更新，0守卫覆盖 | `D:/brace-msi-pytrio/PYTRIO-SFT-001-A3/`；`docs/results/PYTRIO-COMPETITIVE-001-A1.md` |
| PYTRIO-COMPETITIVE-001-A1 | SUCCEEDED | A3 Sampler负责动作意图、BRACE执行冻结参数日程时，能否同时保持自主十轮合规与当前三个任务最强公开候选性能？ | A/B/C官方公开包；参数日程仅来自已冻结`REGRESSION-SPRINT-001`/`SPRINT-HARNESS-001`，不新增搜索；公开验证历史暴露 | 执行提交`0b556c0`；配置`formal_agent_competitive.json`；三任务逐项`validate-only`复算 | 每任务10轮/3真实候选、30次Sampler调用；CPU≤600秒、RSS≤512MiB、累计PyTRiO≤10元、官方试运行0 | 3/3机器复算有效，0守卫覆盖/0服务回退；A 0.725695、B 637.180224、C 51.635999，回归MAE同步改善。A/C各1次预算耗尽后的额外建议在训练前被拒绝 | `D:/brace-msi-pytrio/PYTRIO-COMPETITIVE-001-A1/`；`docs/results/PYTRIO-COMPETITIVE-001-A1.md` |
| RC3-CONTAINER-ACCEPTANCE-001 | SUCCEEDED | 含PyTRiO客户端的正式候选镜像能否满足linux/amd64、小于2GB、非root、4核8GB断网、双协议Smoke和归档可重载要求？ | 仅合成协议Smoke；不加载A/B/C原始数据或权重，不产生性能结论 | 镜像源提交`66f1cae`；`brace-msi:0.3.0rc3` | `--network=none --cpus=4 --memory=8g --pids-limit=256`；两种协议；官方试运行0 | 镜像240,579,085字节，UID10001，PyTRiO0.2.9，Torch缺失、禁入文件0；双协议候选3/4；归档240,602,112字节且`docker load`通过 | `docs/results/RC3_CONTAINER_ACCEPTANCE.json`；`D:/brace-msi-release/BRACE-MSI-0.3.0rc3/BRACE-MSI-0.3.0rc3-image-clean.tar` |
| SWANLAB-FINAL-001 | SUCCEEDED_WITH_RECOVERY | 冻结RC3策略能否在不重新选型的前提下完成一次A/B/C最终工程训练记录，并将脱敏聚合指标同步到SwanLab公开项目？ | 官方A/B/C公开训练包；公开validation历史暴露；无隐藏数据、无官方试运行 | `configs/formal_agent_competitive.json`；执行`b64bf7f`；A3持久化Sampler；输出根`D:/brace-msi-final-record/SWANLAB-FINAL-001/` | 每任务10轮/3候选；最多30次Sampler调用；CPU/RSS/Token沿用冻结上限；SwanLab 0.10.4；不修改RC3或参数 | A/B/C均`valid=true`；公开项目3个实验均`FINISHED`。Gas首次同步因GBK控制台emoji输出失败，使用同一run ID在UTF-8环境恢复完成，未产生重复实验 | `docs/results/SWANLAB-FINAL-001.md`；SwanLab项目`nanmo-max/brace-msi-final` |
| PAPER-FUSION-SPRINT-001 | COMPLETED | 三项有来源的CPU方法能否在train内部组折上形成互补教师，并在冻结后一次公开validation中显著超过RC3？ | 官方A/B/C `public/train`只用于拟合/内部组折；`public/validation`历史暴露且仅冻结后打开一次；无隐藏测试 | `configs/paper_fusion_sprint.json`；分支`codex/paper-fusion-sprint`；D-045至D-047 | 每任务≤12教师配置、≤4完整预算；单任务CPU≤3600秒、墙钟≤1800秒、RSS<4GiB；官方试运行/PyTRiO/SwanLab=0 | A/B相对RC3为负并拒绝；C RMSE 42.330230，相对RC3改善18.02%；30%目标未达到 | `D:/brace-msi-paper-fusion/PAPER-FUSION-SPRINT-001/`与`docs/results/PAPER-FUSION-SPRINT-001.md` |
| PAPER-FUSION-SMOKE-001 | REGISTERED | 新运行器能否在不读取公开validation时完成A/B/C真实train的因果特征、三折和模型冻结？ | 只读三个官方`public/train`；validation路径存在但不得打开 | `configs/paper_fusion_smoke.json`；分支`codex/paper-fusion-sprint` | 每任务1个线性教师、3折；不做蒸馏或validation；官方试运行/PyTRiO/SwanLab=0 | 待运行，仅证明链路和资源，不用于选型 | `D:/brace-msi-paper-fusion/PAPER-FUSION-SMOKE-001/` |

## PYTRIO-SFT-001预注册

- 研究问题：普通assistant-only SFT能否让Qwen3.5-4B更稳定地输出BRACE允许的单一JSON提案，同时不削弱确定性Harness的预算、安全门与降级边界。
- 语料：固定种子20261112；训练24例、留出12例；训练SHA-256 `1d6763854a307ccbd10f1b2b6c49a748d8272288ff2dcf9665d9f58f3b0717c3`，留出SHA-256 `5119947ed2f81b99bc32729d6e53aa7d4fa86472feb0bc4953aa8fff9c6bb824`。训练与留出使用互不重叠的archetype和scenario ID；语料是合成聚合策略场景，不是A/B/C数据或实验成绩。
- 模型与训练：`Qwen/Qwen3.5-4B`；LoRA rank 8；3 epoch；batch 4；学习率`1e-4`；18步。prompt/system内容loss权重为0，只监督assistant JSON及EOS。
- 留出指标：严格schema有效率、action匹配率、tool匹配率、预算安全率和policy匹配率；基础模型与持久化Sampler使用同一12例、温度0、固定seed比较。逐响应仅保存SHA-256、Token计数和布尔得分，不保存原文。
- 成功标准：远程训练完成；loss有限；`save_weights_for_sampler(..., ttl_seconds=None)`返回`trio://`路径；微调后schema有效率不低于基础模型且policy匹配率提高，或两者已满分且输出Token/失败率不恶化。若未达到，Sampler不替换基础模型，负结果保留。
- 停止条件：账户额度不可用、模型不在实时白名单、SDK签名变化、训练/评测异常、返回路径非持久化`trio://`、语料哈希变化、非有限loss或凭据/原始数据进入产物。
- 产物：每次远程尝试使用不可复用的新目录；本地语料/manifest、run spec、训练进度、基础/微调留出汇总、持久化Sampler收据、result或failure；不提交API Key，不运行SwanLab，不消耗官方十次试运行。

## UNIFIED-POLICY-OPT-001-SMOKE预注册

- 目标：验证真实三任务适配、无量纲证据、固定低成本/归一化性能触发/统一BRACE公平对照、任务级leave-one-task-out和可恢复收据；不是最终参数搜索。
- 策略边界：所有任务共享`SharedPolicyConfig`和候选空间；策略输入无任务ID、数据集/Profile或批次名称。TaskAdapter只提供任务类型、指标方向、模型能力和合法分组。
- 数据边界：只构建既有`build_official_development_streams()`的初训与10个中期开发轮；Gas 8—10、FD001 81—100及XJTU密封轴承不得加载。末期锁不会在Smoke中打开。
- 对照：静态、恰好一次固定低成本更新、归一化性能触发更新、统一BRACE；同一任务所有策略必须共享初始检查点和阶段manifest。
- Smoke范围：确定性搜索空间只取2个共享候选，MLP最多8次迭代；完成9个基线作业和6个BRACE作业。成功只证明运行与证据完整，不冻结最终配置。
- 指标：分别保留Macro-F1或RMSE、相对静态/简单策略的无量纲增益、最差任务、候选CPU/墙钟/RSS和训练样本；不推算官方综合分。
- 停止条件：原始哈希变化、任何末期数据加载、初始检查点/阶段manifest不公平、非有限指标、资源越界、收据/汇总不能复算，或代码尝试使用官方平台测试机会。
- 禁止：根据Smoke末期结果调参、SwanLab、平台SDK/API、外部服务、修改RC/main、覆盖既有实验。
- A1失效：15个作业实际完成且未打开末期数据，但`mlp_max_iter=8`来自CLI而未进入执行manifest；同一运行根可用不同迭代数恢复，违反配置冻结。A1保留为INVALID工程证据，不把其候选排名用于后续选择。A2将MLP迭代数写入独立配置并将评估器协议SHA纳入manifest。

## OFFICIAL-PACKAGE-DEV-001预注册

- 类型：官方训练包的本地开发参考实验；`official_package=true`、`official_scoring_ready=false`，不是平台试跑、隐藏评测或正式成绩。
- 输入锁：A检查点/训练/验证SHA分别为`fd1e...c757`/`c724...e6c0`/`6be1...fbee`；B为`c7d8...14b4`/`71b2...054a`/`2367...9eb3`；C为`98ec...bc4e`/`fcfa...c281`/`0cc7...aca7`。运行时核验完整64文件清单与完整SHA。
- 模型继承：只使用随包原版NumPy训练器和官方包检查点；连续2 epoch与1+1恢复等价已在Task 2证明。候选必须证明epoch/step、权重和Adam真实变化；被拒绝候选不得进入父模型链。
- 队列：先A/B/C各1 epoch Smoke；健康且资源实测不超限后，按A/B/C低成本对照、A/B/C BRACE串行执行。内部`performance_triggered`标识在无真实流的本实验中实际为一次无条件续训加9轮`noop`；BRACE固定最低3且最多3个候选。每个策略固定10个候选适应决策轮，轮次不是时间批次或真实漂移流。
- 候选空间：epoch仅1/2/3/5，学习率仅基线的0.25/0.5/1.0倍，批大小仅基线或2倍；每轮最多一个候选，不根据同一验证结果修改动作空间重跑。
- 门控：A以公开验证Macro-F1严格提高为部署条件；B/C以RMSE严格降低为条件；相等或退化拒绝并保留稳定模型。所有模型可加载、schema、父SHA、输入SHA、资源和有限指标为硬约束。
- 验证使用：公开验证文件不得进入训练、均值/方差或目标缩放拟合；每个候选记录文件读取次数和逐epoch指标评估次数。反复用于策略选择存在过拟合风险，最终泛化只能由未见隐藏评测确认。
- 资源：训练前按历史耗时和检查点体积估算，总CPU≤3600秒、墙钟≤1800秒、磁盘≤209,715,200字节；三Smoke后用实际CPU/墙钟/RSS修正，任一超限则停止完整队列。每策略候选CPU和墙钟各≤600秒。
- 成功标准：三个Smoke完成且真实继承证据有效；六个策略作业各10轮；BRACE每任务3个真实候选；父链、验证账本、失败收据、资源、恢复、报告和机器验收完整；原包哈希不变。
- 停止条件：任何包/代码/数据SHA变化、验证泄漏、非有限指标、父链纳入拒绝候选、资源估算超限、候选目录冲突或原包出现写入。负结果和失败收据必须保留，不用同一公开验证流继续调参重跑。
- 禁止项：SwanLab、外部API、平台提交、平台额度、隐藏测试、Docker打包权重、修改RC标签。
- 失败尝试A1：预注册提交`0d3ba5c`启动后，CLI在训练前因`ModuleNotFoundError: brace_msi`退出；未生成清单、资源估算或候选，训练运行数为0。失败状态保留于运行根，修复入口后从同一实验ID恢复，不更改预注册策略或预算。

## OFFICIAL-RULES-ALIGNED-DEV-001预注册

- 类型：最新官方规则对齐的本地开发实验；不是平台试运行、正式评测或官方成绩。
- 初始检查点：从合法初训段本地拟合单隐藏层32单元MLP并原子保存；三策略按任务共享完全相同的本地检查点。参数量应分别严格为4326/865/833。`official_checkpoint=false`。
- 数据可见性：Gas只用批次1–7；FD001只用训练文件发动机1–80；XJTU只用此前缓存的9初训和3开发轴承。Gas 8–10、FD001 81–100及XJTU三个密封轴承不得加载。
- 10轮协议：Gas开发样本按原始批次顺序分为10个连续块；FD001开发发动机每2台一轮；XJTU三个开发轴承按各自归一化已观测进度分为10个阶段并在同阶段合并。预测后才能使用本轮标签。
- 串行顺序：Gas静态、轴承静态、发动机静态为前三个健康检查实验；随后依次运行三任务性能触发与三任务BRACE，共9个实验。每个实验使用同一任务检查点、10个批次和固定种子。
- 指标：Gas Macro-F1主指标/Accuracy参考；轴承RMSE/MAE；发动机RMSE/MAE/NASA非对称分。另报告相对初始/静态增益、最差阶段、达到最佳值轮次、阶段标准差、候选CPU/墙钟/RSS和训练样本。
- 成功标准：9/9实验完成、每个10批次、所有指标有限、BRACE每任务至少3次真实候选、无密封样本、参数量匹配、错误日志为空、自动汇总存在。
- 停止条件：见`FORMAL-DEV-001`。A1或失败结果必须保留，不得覆盖。

## XJTU-LOCAL-DEV-001预注册

- 类型：平台接入前本地开发训练，不是官方评分实验；`local_development_only=true`。
- 任务：根据XJTU-SY说明书的run-to-failure结构，自定剩余采样分钟数为回归目标；平台若给出不同目标，本实验不迁移结论。
- 防泄漏切分：初训`Bearing1_1..1_3`、`Bearing2_1..2_3`、`Bearing3_1..3_3`；开发`Bearing1_4/Bearing2_4/Bearing3_4`；密封`Bearing1_5/Bearing2_5/Bearing3_5`。轴承身份不跨分区。前三轮和策略开发均不使用密封结果选型。
- 特征：每个CSV独立提取双通道时域/频域统计量，只使用当前文件、已知工况和当前已观测分钟序号；不得使用轨迹总长度、未来文件或剩余寿命派生量作为输入。
- 串行轮次：Ridge静态、HistGradientBoosting静态、ExtraTrees静态、性能触发、BRACE；相同初训/开发可见性与种子20261111。前三轮完成后只确认运行健康，不根据结果更改后续队列。
- 指标：开发流prequential RMSE/MAE、逐轴承/阶段指标、候选动作与门控、训练样本、墙钟/CPU/RSS；密封评估仅在队列预注册逻辑中运行一次。
- 运行方式：独立后台进程、原子状态文件、逐轴承特征缓存和逐轮结果；已完成阶段重启时跳过，失败保留并停止后续轮次。
- 停止条件：见`TASKS.md`的XJTU-LOCAL-001。SwanLab在本实验中禁用。

## LOCAL-SMOKE-001预注册

- 类型：本地代理探索Smoke Test，不是官方实验或成绩。
- 问题：同一初始化和可见性下，静态、简单性能触发与BRACE能否对Gas分类和FD001回归完成严格prequential运行，并覆盖至少一次增量和一次重拟合候选？
- 数据：Gas冻结切分的初训与开发批次，各批最多96条；FD001只取前20台发动机后按60%/20%/20%分组，使用其初训和开发组。完整密封段不打开。
- 指标：分类Accuracy/Macro-F1；回归RMSE/MAE；逐批指标、最差批次、候选动作、接受/拒绝、CPU/墙钟/RSS和训练样本数分别记录。
- 对照：静态、性能触发式单动作、BRACE；共享种子、初始模型、数据和预算。
- 预算：每个任务×策略最多4个候选、20,000训练样本、60秒累计候选墙钟和CPU时间；总运行预期少于3分钟。
- 防泄漏：预测提交后才登记反馈和计算指标；候选训练/验证样本分离；不使用完整密封段、未来批次、官方SDK或外部API。
- 成功标准：六个运行均完成；日志`proxy_only=true`且无特征/标签/样本ID；全局至少一个`incremental_update`和一个`replay_refit`候选；无非有限指标。
- 停止条件：任何样本交叉、原始哈希变化、单运行超过预算、非有限指标或日志包含受禁字段；失败也必须登记。
- 产物：配置、六份汇总、六份JSONL事件、总汇总和失败说明；不保存或提交模型权重。
- SwanLab：当前环境未安装且正式离线同步机制未确认，本Smoke只写本地脱敏审计；不得将其声称为正式SwanLab记录。

## LOCAL-EXP-001完整代理实验预注册

- 类型：本地代理开发与一次密封评估，不是官方成绩。
- 冻结依据：沿用`LOCAL-SMOKE-001`的动作阈值；全量DEV阶段只确认运行、预算、动作覆盖和日志合法性。若DEV触发防泄漏、非有限指标或资源停止条件，则停止并登记失败，不打开密封段。
- 数据：Gas按批次1–3初训、4–7开发、8–10密封；FD001按发动机1–60初训、61–80开发、81–100密封。相同样本不跨分区。
- 对照与指标：静态、性能触发、BRACE；分类Accuracy/Macro-F1，回归RMSE/MAE，逐批最差值、候选动作/门控、训练样本、墙钟/CPU/RSS分别报告。
- 预算：每个任务×策略最多4候选、80,000训练样本、180秒累计候选墙钟和CPU；种子20261106。
- 成功标准：DEV六个运行通过机器验收并至少覆盖增量和重拟合；随后同一代码和阈值完成六个密封运行；全局至少三次真实候选训练/评估；所有结果有聚合审计。
- 停止条件：原始哈希变化、数据交叉、非有限指标、日志越界、DEV超预算，或在打开密封前修改`local_full.json`使其与DEV阈值不一致。
- 密封承诺：`local_full.json`执行后，无论结果好坏都不得基于密封指标更改模型、阈值或动作策略并重跑同一密封段。
- 对照限制：本实验的静态对照是同一SGD模型族的无更新版本，用于隔离策略贡献；它不满足“最强静态CPU模型”证据要求。由于密封段已经查看，不能事后加入新模型并把结果当作预注册比较。

## LOCAL-FORMAL-SIM-001完整系统模拟预注册

- 类型：本地代理工程验收，不是官方实验、排行榜结果或真实轴承性能证据。
- 问题：统一Harness能否在两类真实代理开发流和一个合成协议流上，独立完成任务初始化、合法事件顺序、至少三次真实候选、门控、部署/拒绝、故障回滚、恢复、审计和静态报告？
- 数据边界：Gas只允许读取批次1–7；FD001读取同一训练文件时只解析发动机1–80，遇到81即停止；合成轴承流标记`synthetic=true`和`protocol_only`。Gas 8–10与FD001 81–100不得进入本实验的加载器输出、指标或决策。
- 配置与种子：`configs/formal_simulation.json`，种子20261107；三任务使用同一核心Harness与预算，任务专属指标分别报告。分类门控至少16个验证样本、锚点退化上限0.10；回归至少16个验证样本、锚点RMSE退化上限5.0；主指标最低增益均为0。
- 真实候选：每任务至少3次实际训练与评估；合成任务的第1、2个候选注入失败，用于验证稳定模型保持与回滚计数；失败候选仍消耗候选预算。
- 资源：每任务最多8候选、80,000训练样本、120秒累计候选墙钟和CPU；运行进程亲和性最多4逻辑CPU；验收观测RSS低于8GB；Docker镜像内限额因本机无运行时保持单独阻塞。
- 指标：Gas/合成分类记录Accuracy、Macro-F1和逐批最差值；FD001记录RMSE、MAE和逐批最差值；另记录候选/接受/拒绝/回滚、训练样本、墙钟/CPU、操作边界RSS、协议事件和日志完整性。
- 成功标准：三任务均无人干预完成；每任务候选不少于3；合成故障被拒且稳定注册表可加载；协议/日志验证通过；CPU亲和性不超过4；观测RSS低于8GB；生成汇总JSON和离线HTML。
- 停止条件：数据哈希变化、开发/密封身份交叉、任何已消费密封段进入输出、非有限指标、日志出现受禁字段、候选/时间/样本预算超限或恢复后重复提交批次。
- 结论边界：本实验只证明工程完整性和代理开发流行为；不更新`LOCAL-EXP-001`密封结论，不用于模型选型，不宣称官方性能、跨种子稳定或真实轴承泛化。

## PAPER-FUSION-SPRINT-001

- 状态：`SUCCEEDED_MIXED`（按协议完成；A/B负、C正）。
- 研究问题：三个官方任务能否通过Gas知识蒸馏、CPU异构集成和Successive Halving获得显著且4核8GB可承受的性能提升？
- 数据：官方公开train作内部组折开发；历史暴露公开validation仅在冻结后打开一次。未访问隐藏测试，官方试运行0次。
- 配置与代码：`configs/paper_fusion_sprint.json`；`src/brace_msi/paper_fusion.py`、`paper_fusion_runner.py`、`paper_fusion_selection.py`；分支`codex/paper-fusion-sprint`。
- 结果：PaperFusion A Macro-F1 0.687918（拒绝）、B RMSE 644.113606（相对静态改善5.44%但落后RC3，拒绝）、C RMSE 42.330230（相对静态改善19.93%、相对RC3改善18.02%，接受）。
- 资源：A/B/C CPU 9.72/64.56/979.44秒；峰值RSS 120MB/387MB/3.02GB。
- 产物：`D:/brace-msi-paper-fusion/PAPER-FUSION-SPRINT-001/`；聚合报告`docs/results/PAPER-FUSION-SPRINT-001.md`；机器验证`valid=true`。

## PAPER-FUSION-SMOKE-001

- 状态：`SUCCEEDED`（仅链路证据，未打开公开validation）。
- 结果：A/B/C均生成冻结模型、资源收据和哈希，机器验证`valid=true/stage=candidate_frozen`；不作性能结论。
- 产物：`D:/brace-msi-paper-fusion/PAPER-FUSION-SMOKE-001/`。

## PLATFORM-TRIAL-V1

- 状态：`OBSERVED_OFFICIAL_TRIAL_FAILED_AGENT_AND_GENERALIZATION`
- 类型：官方平台试运行，不计正式成绩；不是RC4实验。
- 使用次数：1/10，剩余9/10；正式评测0/2。
- Agent证据：平台输入/输出Token均为0，无法证明任何有效PyTRiO调用；按D-048判定不满足Agent路线准入门槛。
- 隐藏结果：A Macro-F1 0.413368；B RMSE 691.660970；C RMSE 56.220512、NASA 48,596,667,177.965034。
- 选择结果：三任务均保留第1轮；后续轮次未改善。
- 原始证据：`docs/source_notes/PLATFORM_TRIAL_V1_2026-11-13.md`；附件SHA-256 `8B7B5CEC3C50775BD5621DCBEB8DE7337BC39F0F6123767B27E36E004BBA5368`。
- 失败边界：无法从平台报告区分CLI默认、客户端回退或Harness回退；无法确认旧提交绑定的具体镜像编号。失败与未知均保留，不反推RC4表现。

## PYTRIO-BASE-SMOKE-001预注册

- 状态：`FAILED_LOCAL_TIMEOUT_NO_RECEIPT`。
- 类型：基础模型正式入口的单次低成本连通性与结构化响应Smoke；不是工业模型训练、平台试运行或正式成绩。
- 模型：`Qwen/Qwen3.5-4B`基础模型；`model_path=None`；不使用持久化Sampler，不修改A/B/C模型或冻结参数。
- 输入：仅使用一个合成、聚合且不含样本/标签/密钥的BRACE决策上下文。
- 调用预算：最多1次Sampler调用，`temperature=0`、固定种子、最多384输出Token；不训练、不保存权重、不自动重试。
- 成功标准：来源为`pytrio`，严格proposal schema通过，输入/输出Token均大于0，`model_path_configured=false`，无fallback。
- 停止条件：传输失败、超时、非法JSON/schema或Token为0时立即保留失败证据并停止；不得因此放宽schema或恢复静默降级。
- 记录边界：只保存状态、动作/工具、Token、延迟和请求/响应哈希，不保存原始响应、API Key或服务凭据。
- 实际结果：首次启动因临时进程未设置`PYTHONPATH=src`在导入阶段退出，远程调用0；修正后发起唯一一次Sampler调用，但本机进程在约90秒内没有返回可核验响应，随后被终止。没有proposal、Token或哈希收据，因此不计为成功，也无法确认服务端是否已接受/计费该请求；按预注册停止，不重试。

## DUAL-EXPERIMENT-001-A1预注册

- 状态：`COMPLETED_NEGATIVE`。
- 目的：在不消耗官方试运行的前提下，检验静态、简单固定更新、确定性受控双闭环和PyTRiO受控双闭环能否从A/B/C官方初始`checkpoint.npz`真实续训，并对十批顺序反馈完成公平prequential比较。
- 证据边界：数据来自三个官方训练包的公开`validation.jsonl`，历史上已经暴露；本实验是本地开发证据，不是独立确认、隐藏测试、平台试运行或官方成绩。不得据此重写既有RC性能结论。
- 初始模型：每个任务均从只读官方包的初始`checkpoint.npz`开始；候选必须加载父检查点并延续权重、Adam、标准化、epoch和step。禁止从头初始化或把本地SGD模型写成正式候选。
- 十批构造：仅从公开validation生成冻结顺序清单。A按文件原始顺序/`source_index`连续分十批；B按`bearing`及`snapshot`顺序形成十个连续阶段；C保持整台`source_subset+unit`不跨批，并按首次出现顺序近似均衡分十批。冻结后四个策略读取完全相同的批次清单。
- 每批协议：父模型先对当前批预测；标签随后才开放；当前批按任务合法的分层或连续块拆分为80% Update和20%一次性Gate；Gate当前轮不训练；完成一轮隔离后才可进入Replay。候选训练文件只由Update或Update+合格Replay物化，不能访问未来批次、Anchor或当前Gate。
- 对照：`static`零候选；`fixed_update`使用预注册固定低成本更新点且不看任务名称；`deterministic_dual_loop`按D-052证据与预算选择0至2候选；`pytrio_dual_loop`仅在D-052触发条件满足时向Qwen3.5-4B基础模型请求结构化建议，执行仍受同一白名单、预算和SafetyGate约束。
- 候选上限：每任务/策略全程最多8个真实候选，每批最多2个；第二候选只在第一候选失败或收益不足且存在新证据时运行；最后三批至少保留25%初始CPU预算。小型搜索最多3个内部试验且全部计费。
- 指标：A报告Macro-F1/Accuracy；B报告RMSE/MAE；C报告RMSE/MAE/NASA非对称分。所有任务报告逐批主指标、最差阶段、延迟影子收益、CPU、墙钟、RSS、checkpoint大小、参数量、Token、接受/拒绝/回滚和归因置信度。
- PyTRiO门：只有确定性三臂机器验收通过、服务可达且运行时凭据由环境注入时才启动；最多按证据触发调用，不做LoRA、不修改prompt来迎合公开结果。服务失败重试一次后保留失败收据并按正式失败关闭规则结束该臂，不用静默确定性结果冒充PyTRiO结果。
- 成功标准：12个任务×策略运行均有十批记录；每个受控双闭环至少三次真实候选；父链、未来隔离、Gate生命周期、影子成本、模型保存—加载—同预测和64 MiB门均可复算；三个任务最终均不低于各自静态臂，至少两项取得可复核改善。
- 停止条件：发现未来/当前Gate泄漏、父链断裂、非有限指标、输出不可加载、产物超过64 MiB、单策略超预算、原始包哈希变化，或正式逐轮SDK必要字段无法从现有公开材料确定。失败与部分结果必须保留；不调用官方十次试运行。
- 实际结果：九个确定性运行全部完成十批且官方试运行0次。静态A/B/C分别为0.714030 Macro-F1、681.159833 RMSE、52.868573 RMSE；固定更新为0.717688、697.343278、53.058643；A1双闭环为0.715596、700.803581、53.155215。B/C劣于静态，未达到成功标准；根因证据是当前Update首候选虽通过同批Gate/Anchor，却在后续分布上产生负延迟收益，且A1未执行延迟回滚。结果根`D:/brace-msi-dual-loop/DUAL-EXPERIMENT-001-A1/`，`summary.json` SHA-256为`BBCE5AF7144B047A8265085C75565BD0A04E6C720B4ECD54A76F26F2A6169869`。原始结果冻结，不覆盖。

## DUAL-EXPERIMENT-001-A2预注册

- 状态：`COMPLETED_MIXED_STOPPED`。
- 变更依据：只针对A1已观察到的跨批遗忘与收益归因缺口；不扩大模型族、不打开隐藏数据、不调用PyTRiO。
- 共享变更：Anchor改为官方公开train中的固定小型历史保护集；其余公开train作为合法初始Replay来源。确定性双闭环首选`Update + bounded initial/eligible Replay`续训，同批Gate使用保守改善门；若下一批前任影子配对收益为负，标签开放后立即回滚到前任父检查点。算法与阈值对A/B/C相同，不读取数据集名称。
- 固定对照：`static`与`fixed_update`定义保持A1不变；A2重新运行它们只为机器级同代码公平性，不把重复公开结果当作新独立证据。
- 候选与资源：每任务最多8候选；首选Replay续训，首候选拒绝时最多追加一个机制不同的当前Update续训；所有父链、CPU、墙钟、RSS、checkpoint字节和预测影子成本计量。
- 成功与停止条件：沿用A1；特别要求双闭环B/C不得继续部署已证实负延迟收益的父链。A2无论正负均停止根据同一公开流继续调整，下一步转向自建通用模型的训练内部交叉任务验证或等待隐藏评测，避免无限公开调参。
- 实际结果：九运行均完成十批、官方试运行0次。A2双闭环A/B/C为0.714552 Macro-F1、681.159833 RMSE、52.378784 RMSE；相对静态分别+0.000522、持平、RMSE降低0.489789（0.93%）。A/C改善但幅度不足“显著改善”门，B由门控保留静态；C发生1次负影子收益回滚。结果根`D:/brace-msi-dual-loop/DUAL-EXPERIMENT-001-A2/`，摘要SHA-256为`62AD2DA12E3D7BC5F27A32827E572760CD4AFCD86313C171EB59647172436C68`。按预注册停止公开流阈值调整，未启动PyTRiO臂。

## GENERALIST-MODEL-001-A1预注册

- 状态：`COMPLETED_ACCEPTED_B_C`。
- 研究问题：同一套身份盲数值表格候选池，能否在A/B/C公开train内部组折中选择出与官方父MLP互补的CPU模型，并以固定50%父模型+50%候选集成在一次公开validation确认中改善至少两个任务、第三项由SafetyGate保持父模型。
- 数据：模型选择只读取各包`public/train.jsonl`；分组字段由可用元数据schema推断（批次、设备或单元），不读取profile/数据集名称选择算法。公开validation在候选族、参数、混合权重和门控阈值全部冻结后只打开一次；其历史暴露属性保留。
- 候选池：所有任务共享`linear`、有界`HistGradientBoosting`、有界`ExtraTrees`三族及同一资源上限；分类/回归仅使用对应估计器接口。输入只取`inputs`内有限数值叶子，不使用`id`、`answer`、设备身份、总寿命或`meta`作特征。
- 组折：优先3折GroupKFold；没有足够组时分类使用分层3折、回归使用连续块3折。分类按Macro-F1选高者，回归按RMSE选低者；不使用公开validation选族或参数。
- 父模型集成：冻结权重为父模型0.5、候选0.5；分类对齐类别概率后加权，回归加权预测并截断非负。父checkpoint字节、哈希和候选模型实际共同进入`checkpoint.npz`，不把候选单模型冒充续训。
- SafetyGate：一次公开validation上只有主指标严格改善且辅助指标不灾难退化时接受集成，否则保留父checkpoint。不得根据结果修改权重、模型池或阈值后重开。
- 资源与产物：4核CPU设计、单模型串行；每个最终`checkpoint.npz`及全部模型产物不超过64 MiB；记录参数/树节点代理量、训练CPU/墙钟/RSS、序列化字节、父哈希、代码哈希和独立保存—加载—同预测。
- 成功标准：至少两个任务接受且相对父模型有可复核改善，第三任务不退化；三任务产物均可独立预测、父模型真实参与、无非法特征、官方试运行/Token/SwanLab均0。
- 停止条件：组折无互补性、候选产物超限、父模型未实际参与、公开validation已打开后仍试图调参，或任一任务出现无法解释的数据泄漏。失败也保留并停止，不消耗官方试运行。
- 实际结果：A内部选中linear但固定混合validation Macro-F1 0.712424低于父0.714030，拒绝；B/C均内部选中有界HGB，固定混合RMSE为675.010677/49.336020，父模型为681.159833/52.868573，均接受。B MAE与NASA从563.105841/3.9004e24降至544.886250/3.5278e24；C从38.899830/5.8234e9降至35.423070/2.4038e9。三产物115,392/239,908/200,613字节，均嵌入父checkpoint且独立预测同结果；官方试运行、PyTRiO、SwanLab均0。结果根`D:/brace-msi-generalist/GENERALIST-MODEL-001-A1/`，摘要SHA-256 `1CE6A72E272DD1426A0BB5FF468C303DBA050BA55001F5E37B70288253ABEB06`。validation已打开一次，禁止据此调整权重或候选池重跑。

## DUAL-RC-001-A1 容器与跨平台验收

- 状态：`COMPLETED_WITH_KNOWN_LIMIT`。
- 目的：不改变D-056冻结算法与参数，在真实Linux镜像中验证通用单包训练、父链、独立预测、4核8GB、断网、模型产物、禁入文件及`docker save/load`。
- 数据与选择边界：训练仅使用官方公开train；公开validation只做一次跨平台等价性验收，不用于改变模型族、50/50权重、参数或A/B/C选择。历史暴露继续标记，官方试运行0次。
- 容器结果：B/C分别在4核8GB、无公网、256 PID限制下完成全量训练，选择同一HGB族；产物239,914/200,616字节，实际嵌入父checkpoint并通过独立预测。A按既有SafetyGate保持官方父模型。
- 跨平台验收：Linux产物序列化哈希与Windows研究产物不同，但B/C公开validation指标完全一致并继续通过原门控；未据此调参。
- 工程结果：329项完整回归；镜像241,051,292字节、UID10001、禁入扫描为空、容器`pip check`和`compileall`通过。归档241,074,176字节，SHA-256 `e3cc5f1c...9799747`，删除本地标签后`docker load`成功。
- 未满足项：A没有严格超过静态父模型；正式SDK、镜像可用、模型校验、续训协议和正式评测均未验证。证据见`docs/results/DUAL-RC-001.md`。

## FORMAL-CONTINUATION-RC-001-A1

- 状态：`SUCCEEDED_LOCAL_PLATFORM_PENDING`。
- 目的：只验证正式发布线确实使用官方训练器完成`baseline -> child -> grandchild`原生续训，并在正式Docker镜像中禁用异构研究模型入口；不进行新模型选择或性能调参。
- 输入：只读官方A/B/C训练包及各自初始`checkpoint.npz`；原始包哈希必须与`configs/official_package_dev.json`一致。
- 候选：每个任务先从baseline续训1 epoch，再从该子checkpoint续训1 epoch。学习率和batch size沿用父包默认值；不读取任务名称改变算法，不使用HGB、ExtraTrees、PaperFusion、PyTRiO、SwanLab或官方试运行。
- 验证：两代checkpoint均须与直接父checkpoint schema完全一致，继承预处理状态，模型和Adam状态真实变化，epoch/step单调增加，父哈希链准确；产物小于64 MiB并可被官方独立预测入口加载。
- 容器门：`BRACE_FORMAL_RELEASE=1`；`generalist-run`、`generalist-fit`、`generalist-predict`和`paper-fusion-run`必须失败关闭；4核8GB、断网、非root、无数据/权重/密钥、`docker save/load`通过。
- 性能边界：不重新打开公开validation做参数选择，不产生新的泛化或性能结论。训练器为验证续训完整性执行的指标读取只作为协议证据，不用于改变参数或候选。
- 成功标准：A/B/C六个候选全部满足父链和schema验证，完整回归与容器验收通过，生成独立新RC和机器证据包。
- 停止条件：包哈希变化、父链/schema/Adam/预处理任一验证失败、产物超限、正式镜像仍能执行异构模型命令、容器资源门失败或需要猜测官方SDK字段。
- 实际：A/B/C均完成十轮和3个真实候选，`validate-only`三项为`valid=true`；两代父链专项3项及完整回归333项通过。镜像在4核8GB断网下完成，四个异构研究命令均失败关闭，A/B/C独立预测通过。归档SHA-256为`6331280b...34e181`，官方试运行/PyTRiO/SwanLab调用均0。公开指标只作历史暴露续训链证据，不产生新独立性能结论。详见`docs/results/FORMAL-CONTINUATION-RC-001.md`。

## NATIVE-COMPETITIVE-RC-001-RELEASE-A1

- 状态：`SUCCEEDED_LOCAL_PLATFORM_PENDING`。
- 配置：A/C竞争策略，B协议策略；A/B/C均从官方父checkpoint开始，容器内完成十轮父链和独立预测。PyTRiO训练意图不能改变冻结轮次、动作、epoch或学习率。
- 资源：4核、8 GiB、无网络、只读根、256 PID；候选3/10/3，接受1/1/1；最大RSS约95.0/113.4/238.7 MB；checkpoint均小于0.13 MiB。
- PyTRiO：断网时两次失败后`noop/retain`，零候选、零Token且无静默训练；在线历史为2次非零响应、1次建议执行，第三次外部阻塞。
- SwanLab：三任务各112条聚合记录公开同步，敏感字段扫描通过。
- 归档：`docker save` tar 241,897,984字节，SHA-256 `B4EF8820FE38B4479B16657A85594719EB86CA7BAD157C0B484DDF4715FB1BD7`，重载通过。
- 边界：没有使用官方试运行；容器训练内指标不作为新独立性能结论；平台镜像/模型/续训/评测状态待外部验证。

## PLATFORM-REPORT-SIM-001-A1

- 状态：`INVALID_FOR_PERFORMANCE / RETAINED_AS_INTERFACE_DEMO`（被D-067替代）。
- 输入：RC7修复后容器的A/B/C各10轮checkpoint；三个官方训练包的历史暴露`public/validation.jsonl`。
- 行为：逐轮只读评估，按A Macro-F1最大、B/C RMSE最小模拟官方“采用本轮/保留此前最佳”；不训练、不修改checkpoint。
- 结果：A/B/C均10/10轮，共25,972条逐轮重复公开validation预测；该实现按validation选择第9/1/9轮，构成选择污染，不能证明泛化或选择最终轮次。
- 产物：`D:/brace-msi-native-competitive/RC7-OFFICIAL-REPORT-SIM/report.json`与`report.html`；详情见`results/PLATFORM-REPORT-SIM-001.md`。
- 边界：只保留界面和协议演示；Token为本地确定性容器记录0，不冒充在线或官方成绩；官方试运行新增使用0次。

## REPORT-EVIDENCE-FIX-001-A1

- 状态：`SUCCEEDED_LOCAL_REPORT_CORRECTION`。
- 输入：同一RC7冻结十轮收据、round-10最终稳定checkpoint及历史暴露公开validation；未重训或改写checkpoint。
- 行为：逐轮仅展示Gate稳定/候选指标和Harness真实部署；A/B/C各在十轮完全冻结后对round-10执行一次公开validation评估，总读取3次。
- 结果：最终模型来源由部署链确定为A第9轮、B第1轮、C第9轮；冻结后单次公开validation数值保持A Macro-F1 0.725695、B RMSE 660.076488、C RMSE 51.949287，但不再用于选轮次。
- 产物：`D:/brace-msi-native-competitive/RC7-OFFICIAL-REPORT-SIM-V2-A2/`；证据见`results/REPORT-EVIDENCE-FIX-001.md`。
- 边界：公开validation历史已暴露，仍非独立泛化或官方隐藏成绩；PyTRiO、SwanLab和官方试运行新增使用均为0。

## UNSEEN-SIM-001-A1预注册

- 状态：`FAILED_DATA_QUALITY_BEFORE_TRAINING`。首次只读解析在Battery `B0050/B0052`发现25条`discharge`记录的`Capacity`为空数组，原实现尝试强制转标量并抛出`TypeError`；训练、confirmation、PyTRiO、SwanLab和官方试运行均未启动。失败目录只含原始清单`D:/brace-msi-unseen/UNSEEN-SIM-001-A1/raw-manifest.json`，保留不覆盖。
- 研究问题：冻结RC7的原生续训、门控和保留机制，在未参与其设计的电池容量回归、液压蓄能器状态分类和铣削VB回归上，能否完成十轮并相对模拟静态父模型获得安全改善？
- 原始数据：只读使用`C:/Users/Administrator/Desktop/人工智能创新大赛/模拟正式数据集`；运行根固定为新目录`D:/brace-msi-unseen/UNSEEN-SIM-001-A1/`。
- 特征：每个传感器序列只提取数量、均值、标准差、最小、最大、中位数、四分位数、RMS、首尾差和线性斜率；允许合法工况量，但禁止目标、未来总循环数、总寿命、未来容量/VB、其余液压profile目标或数据集名称作为模型输入。
- 任务：Battery预测放电循环容量；Hydraulic预测蓄能器状态`90/100/115/130`；Mill只使用实测非缺失VB记录预测VB。
- 划分：以电池ID、液压循环的目标分层隔离索引、Mill case为不可交叉组，固定种子`20261115`建立bootstrap/adaptation/confirmation；bootstrap只建模拟父checkpoint，adaptation按合法组内顺序分十轮，confirmation冻结后只评估一次。所有样本ID和组清单保存哈希审计。
- 对照与执行：静态模拟父模型 vs 冻结RC7未知profile的原生十轮路径；不启用数据集名称路由、PyTRiO、SwanLab或额外HPO。每轮最多一个候选，沿用RuntimeAdapter、父链、Gate、Replay、64 MiB和独立预测检查。
- 指标：分类记录Macro-F1、Accuracy；回归记录RMSE、MAE；同时记录逐轮指标、最差阶段、候选/接受/拒绝、CPU、墙钟、峰值RSS、参数量、checkpoint大小和预测数。
- 预算：4 CPU设计、8 GiB上限；原始派生特征缓存与运行产物不得写回数据目录；三任务串行执行。
- 成功标准：三任务10/10轮、父链有效、零分组交叉和零目标泄漏；最终confirmation三任务均不劣于静态父模型，至少两个严格改善；全部checkpoint可加载且小于64 MiB。
- 停止条件：任一泄漏/交叉、标签定义不明确、少于50条adaptation样本、非有限特征、父模型或续训链不可加载，或confirmation打开后需要改参数。若性能失败则保留负结果并停止，不用confirmation调参重跑。
- 证据边界：这是模拟正式流程和未知任务压力测试，不是官方试运行、隐藏成绩或RC7重新选型；完成后`REGISTERED_NOT_RUN`改为实际状态并记录全部失败。

## UNSEEN-SIM-001-A2预注册

- 状态：`INVALID_EVIDENCE_ID_MISMATCH`。三任务均完成10轮且协议检查通过，但机器报告内部`experiment_id`被脚本硬编码为A1，与A2输出目录不一致，故不作为最终有效报告。诊断结果保留：Battery/Hydraulic各部署1次后confirmation退化，Mill部署0次并保持静态；未据此调参。
- 唯一变更：Battery只接受尺寸为1且有限的实测`Capacity`；空数组、多值或非有限目标显式排除，不插值、不从传感器反算、不改变其余特征、切分、模型、十轮策略、预算、成功标准或confirmation规则。
- 输出：新目录`D:/brace-msi-unseen/UNSEEN-SIM-001-A2/`；A1失败目录保持只读证据。
- 其余协议：完全继承A1预注册。

## UNSEEN-SIM-001-A3预注册

- 状态：`COMPLETED_NEGATIVE_DETERMINISTIC_CONTROL`。三任务均完成10轮，父链、分组隔离和协议检查通过；Battery/Hydraulic各部署1次但confirmation退化，Mill部署0次保持静态，最终严格改善任务0/3，未达到成功标准。该结果说明未知profile的同批Gate不能保证跨组泛化，不能据此修改RC7。
- 唯一变更：CLI必须显式传入实验ID，报告原样记录`UNSEEN-SIM-001-A3`；所有数据、特征、分组、父模型、随机种子、十轮策略、门控、预算与成功标准继承A2且保持不变。
- 输出：新目录`D:/brace-msi-unseen/UNSEEN-SIM-001-A3/`；A1/A2目录均保留。

## UNSEEN-SIM-001-A4预注册

- 状态：`COMPLETED_AGENT_PASS_PERFORMANCE_FAIL`。三任务各10轮及全部协议检查通过；PyTRiO有效响应16次、接受并执行15次，输入/输出Token为8,100/3,470，Agent门通过。Battery最终RMSE从静态0.335763退化至0.409475，Hydraulic Macro-F1从0.238964退化至0.092620，Mill RMSE保持0.392140；严格改善0/3，性能成功标准失败。
- 目的：按用户要求在A3完全相同的数据、模拟父checkpoint、十轮、门控和资源边界上启用正式基础模型`Qwen/Qwen3.5-4B` PyTRiO Advisor，形成确定性A3的公平Agent对照。
- PyTRiO协议：只通过`build_platform_advisor`调用基础模型，不使用Sampler微调权重；temperature 0、最大768输出Token、单次60秒、失败最多重试一次。Qwen只能返回受限训练/retain意图，不能改变数据、轮次、动作实现、epoch、学习率、Gate、父链或部署；失败必须留下收据并确定性retain。
- 记录：逐轮保存advisor来源、触发原因、尝试次数、错误类别、输入/输出Token、延迟、提案动作、实际动作和约束；不得保存API Key或原始私有数据。
- 成功门：除A3协议门外，至少3次非零Token有效响应、至少1次建议被执行；若服务失败或全为确定性恢复，仍完成可安全完成的轮次并标记Agent门失败，不冒充PyTRiO成功。
- 输出：新目录`D:/brace-msi-unseen/UNSEEN-SIM-001-A4/`；不覆盖A1/A2/A3，不消耗官方试运行，不同步SwanLab。
- 证据：`results/UNSEEN-SIM-001.md`；报告JSON/HTML SHA-256为`AA3CA8F...AEE8D7`/`A0165511...E1E92B8`。confirmation已经打开，禁止据此调参重跑。

## OFFICIAL-FLOW-SIM-001-A1/A2

- 状态：`PROTOCOL_PASS_PERFORMANCE_MIXED_CONFIRMATION_EXPOSED`。
- A1：三任务使用静态父模型完成十轮预测封存、后反馈和一次本地确认，候选数0；只验证流程。A1已经打开全部本地确认分区。
- A2：配置在查看A1结果前已冻结为A/C竞争策略、B protocol；三任务分别3/10/3个真实候选、采用0/1/0，全部10/10轮、父链和ScoreVault硬门通过。A/C保持静态；B流平均RMSE从静态623.356135降至612.887552，但本地确认RMSE从241.980799恶化到495.437675。
- 数据：Gas Batch 2—9流/Batch 10确认；Bearing未见轴承寿命进度流/完整轴承确认；Engine完整unit流/完整unit确认。父训练、流和确认ID/特征交叉0。
- 资源：A/B/C CPU 5.734/1.797/6.203秒，峰值RSS约202.6/204.5/493.9 MiB；Token 0。SwanLab仅生成离线聚合目录，未同步。
- 边界：A2确认是第2次历史暴露，只作负面诊断，禁止据此调参。正式隐藏测试尚未开始；官方试运行新增使用0次。证据见`results/OFFICIAL-FLOW-SIM-001.md`。
