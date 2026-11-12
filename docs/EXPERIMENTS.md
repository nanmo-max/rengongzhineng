# 实验登记与结果

本文件是全部实验运行的唯一登记处，包括失败和中止实验。

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
| REGRESSION-SPRINT-001 | RUNNING | B/C各一次9候选有界矩阵能否稳定超过官方静态基线并固化安全候选？ | B整轴承`*_1/*_2/*_3`训练/开发/确认；C整发动机FD001+2/FD003/FD004训练/开发/确认；公开validation仅冻结后门控 | `configs/regression_sprint.json`；执行提交`241a465` | 每任务1父模型+9矩阵+最多1最终候选；单次≤180秒；官方试运行/PyTRiO/SwanLab=0 | A1在训练前因包目录运行时`__pycache__`影响整树指纹而停止，0候选；修复后B的9/9矩阵及最终候选完成，选择`e5-lr3p0`，公开门控RMSE 681.159833→637.180224、MAE 563.105841→540.456251并接受；C待运行 | `D:/brace-msi-sprint/REGRESSION-SPRINT-001/`；B机器校验`valid=true` |

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
