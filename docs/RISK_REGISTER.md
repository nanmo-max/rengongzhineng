# 风险清单

| ID | 等级 | 风险 | 触发器 | 缓解措施 | 负责人 | 状态 |
|---|---|---|---|---|---|---|
| R-036 | P0 | 训练子进程通过完整源目录发现未来批次 | worker收到官方数据根或可遍历父目录 | RuntimeAdapter唯一入口、每轮物化目录、RoundDataManifest、清理环境变量、未来诱饵测试；无法隔离则失败关闭 | 技术负责人 | MITIGATED_LOCAL：最终Docker每轮只挂载当前`/data`批次与直接父checkpoint，未来批次和完整包根均未挂载；A/B/C各10轮通过。平台实际挂载权限仍需正式试运行复验 |
| R-037 | P0 | Gate/Anchor误入训练或Replay未完成隔离 | 预处理器在非候选训练集合拟合 | 四用途类型、候选集合构造器、样本生命周期审计和专项测试 | 技术负责人 | MITIGATED_LOCAL：A1/A2使用官方父检查点，当前Gate仅作baseline训练器验证参数和SafetyGate，固定Anchor从公开train隔离且不进入候选；Replay只含公开train或完成隔离的历史Gate。正式SDK仍需复验 |
| R-038 | P1 | 下一批自然难度被误归因于上一轮动作 | 只比较跨批绝对指标 | 保留直接前任一轮影子预测并做同样本配对差；不可用时降级为低置信度 | 技术负责人 | MITIGATED_LOCAL：A1记录负延迟收益，A2在同一样本上运行前任影子并对负配对收益执行回滚；额外推理CPU/RSS已计量。正式SDK是否允许影子仍待确认 |
| R-039 | P0 | Qwen补丁突破安全核心或资源边界 | 补丁访问文件/网络/反射/无限循环/OOM | 仅纯函数槽、AST+签名+隔离子进程+资源限制+形状/有限值/确定性/差异门 | 技术负责人 | MITIGATED_CORE：13项攻击/输出契约测试与完整回归通过；正式容器cgroup和只读挂载仍待DUAL-RC-001复验 |
| R-040 | P0 | 新候选不符合父检查点续训或64 MiB产物约束 | 从头训练、异构模型替代baseline、父链未实际使用、模型产物过大或缺独立预测入口 | 正式镜像只允许官方训练器原schema续训或`retain`；逐代验证父哈希、权重/Adam/标准化/epoch/step、独立预测和`<=64*1024*1024`字节；异构研究命令在正式镜像失败关闭 | 技术负责人 | REALIZED_OLD_SUBMISSION/MITIGATED_LOCAL/OPEN_PLATFORM：O-PLATFORM-008证明旧提交被拒；0.9.0rc1按SDK 1.0.2从声明父checkpoint训练或retain，A/B/C 30轮父链/状态、候选提交和独立预测通过，最大候选artifact 36,598字节；正式平台artifact生命周期仍待试运行 |
| R-041 | P0 | Native训练器与官方训练器状态不等价 | 同一父checkpoint、数据顺序和超参数下任一权重、Adam、计数、loss或预测不同 | 新竞争候选在任何性能实验前执行A/B/C逐状态差分门；失败时只修执行器，不迁移日程或发布新RC | 技术负责人 | MITIGATED_LOCAL：A/B/C一轮loss、全部权重、Adam、预处理、metadata与预测逐值相同；Native 1+1与连续2 epoch逐状态相同，37项相关测试通过；见`results/NATIVE-COMPETITIVE-RC-001-PARITY.md` |
| R-042 | P0 | 统一5%与Anchor零退化门系统性拒绝有价值候选 | C正收益均低于5%，B正收益被Anchor零退化门拒绝 | 先对既有30轮做只读反事实；新门只依据train内部任务契约/波动冻结，公开validation仅作一次发布确认 | 技术负责人 | MITIGATED_LOCAL：竞争门按任务尺度接受C的0.5%安全收益、允许B/C最多2%相对Anchor风险，并以辅助指标和Replay历史限制退化；首轮因无历史禁止部署。32项专项及365项完整回归通过，实际泛化仍待冻结确认 |
| R-001 | P0 | 正式SDK事件顺序与预设状态机冲突 | SDK无法映射内部事件 | 事件适配层；SDK-001当天核验 | 技术负责人 | MITIGATED_LOCAL/OPEN_PLATFORM：官方SDK 1.0.2固定workspace v2帧、挂载、模型调用、候选、状态和预测契约已接入；A/B/C各10轮宿主协议替身通过。真实平台调度生命周期仍待一次受控试运行 |
| R-002 | P0 | B包首批无合法初始模型 | 无初训数据/模型且要求预测 | TaskBootstrap；只走官方默认/弃权路径 | 技术负责人 | PARTIAL：本地未知任务TaskBootstrap和兼容性守卫已测试；官方默认/弃权路径仍待SDK |
| R-003 | P0 | 三次迭代计数不合规 | 被拒候选不计数或要求部署 | 以正式定义配置计数；准备三个真实候选 | 技术负责人 | PARTIAL：SPRINT-HARNESS-001中每任务均完成3次真实候选且父链可复算；官方是否计拒绝候选仍待H-003 |
| R-004 | P0 | 标签可见性错误造成泄漏 | 同样本先训练后预测 | 事件级样本身份检查；非法顺序测试 | 技术负责人 | MITIGATED：`src/brace_msi/protocol/__init__.py`与`tests/protocol/test_state_machine.py`，13项测试通过；正式SDK映射后仍需复验 |
| R-005 | P0 | SwanLab公开与B包保密冲突 | 日志包含逐样本私有信息 | 公开/私有双日志；字段白名单；只在最终工程模型正式重训时生成云端记录 | 队员B | MITIGATED/PARTIAL：`SWANLAB-FINAL-001`只同步聚合指标，敏感字段扫描无命中，公开项目3项均`FINISHED`；比赛专用字段与无公网评测同步责任仍等待H-004 |
| R-006 | P0 | 镜像超过2GB或依赖GPU | 引入PyTorch/权重/重依赖 | 轻量CPU栈；持续体积检查 | 队员A | MITIGATED：0.9.0rc1 A4为linux/amd64、151,369,904字节、UID10001，`pip check`通过；正式镜像未安装PyTRiO/SwanLab且无数据、权重、密钥、测试或报告。4核8GB断网30轮与预测通过；151,393,280字节归档`docker load`通过 |
| R-007 | P0 | 截止日期认知错误 | 学校通知晚于内部假设 | 按11月13日准备；专人核实书面通知 | 团队通知负责人 | OPEN |
| R-008 | P1 | BRACE复杂策略被简单更新支配 | EXP-002全面落后 | 停止扩展，回到动作选择/预算策略 | 技术负责人 | REALIZED/MITIGATED：`UNIFIED-POLICY-OPT-001-DEV-A1`中复杂BRACE在3/3任务级留出fold相对简单触发策略无优势且资源更高；已按D-034停止复杂扩展并冻结简单统一候选，证据见`docs/results/UNIFIED-POLICY-OPT-001.md` |
| R-009 | P1 | 公开数据过拟合，B包失效 | 跨任务/密封段性能崩溃 | 通用接口、验证暴露记账、每轮单候选、禁止验证参与训练/预处理；最终以隐藏评测确认 | 技术负责人 | CONTROLLED/OPEN：`OFFICIAL-PACKAGE-DEV-001`记录15次成功训练器加载、15次预检哈希、12次套件审计读取和33次候选指标计算；D-031冻结同流继续调参。反复公开验证的选择偏差无法由本地消除，仍需隐藏评测确认 |
| R-010 | P1 | 论文复现挤占核心闭环 | Gate 1未完成仍开展复现 | PAPER-001保持DEFERRED | 技术负责人 | MITIGATED |
| R-011 | P1 | 原始资料或实验记录被覆盖 | 脚本写入dataji/或根资料 | AGENTS禁止修改；数据目录Git忽略 | 全员 | MITIGATED |
| R-012 | P1 | 长对话造成方向漂移或重复实验 | 新会话从聊天恢复 | 强制读取SSOT、实验注册和交接流程 | Codex | MITIGATED |
| R-013 | P2 | 模型服务名称/模型ID写死 | 正式白名单不同 | 模型、Sampler、端点和凭据全部运行时配置 | 技术负责人 | PARTIAL：Qwen3.5-4B基础模型已通过平台校验，PyTRiO通用接口已确认；比赛Base URL、凭据注入、白名单与Token口径仍待核验，核心不得写死 |
| R-014 | P1 | 代理比较缺少预注册强静态CPU基线 | SGD静态对照弱于树模型/提升模型 | 在新的未见官方数据或新密封代理上预注册ExtraTrees/HistGradientBoosting；不得复用已查看密封段形成确认性结论 | 技术负责人 | OPEN |
| R-015 | P1 | 有限HPO耗尽CPU或候选预算 | 搜索未在训练前停止 | 有限候选空间、逐候选预算检查、耐心停止；集成评测继续验证 | 技术负责人 | MITIGATED：单元测试及`LOCAL-FORMAL-SIM-001`两次HPO候选均在预算内停止 |
| R-016 | P1 | 开发机全局Anaconda环境存在无关依赖冲突 | `pip check`报告anaconda-cli-base/streamlit/tensorflow与全局包版本冲突 | 候选镜像只安装锁定依赖；在干净venv与Linux轮子解析中复验 | 技术负责人 | MITIGATED：RC3全新隔离环境安装核心、SwanLab、PyTRiO及测试锁后`pip check`无冲突、243项测试通过；真实Linux容器同样`pip check`通过。初次构建隔离的镜像TLS证书失败已记录，使用预装锁定构建依赖和`--no-build-isolation`复现成功 |
| R-017 | P0 | 把原始公开数据误当成完整官方评测协议 | 仅有原始数据，没有比赛manifest、轴承目标、官方切分或评分脚本 | 哈希冻结原件；复用加载器但隔离旧结果；获得正式任务定义后预注册再训练 | 技术负责人 | OPEN：三套原件已审计，H-006尚未解除 |
| R-018 | P1 | XJTU本地自定RUL任务被误报为官方任务或使用未来轨迹信息 | 报告省略`local_development_only`，或特征含总轨迹长度/未来文件 | 按轴承冻结9/3/3分组；每CSV独立提取；仅当前分钟序号可作输入；密封组不进入当前队列；所有产物显式标记本地开发 | 技术负责人 | MITIGATED：A2真实运行只加载初训/开发12个轴承，特征名检查和机器验收通过；结果文档明确非官方，H-006保持BLOCKED |
| R-019 | P0 | 参数量匹配拓扑被误认为平台官方权重或代码 | 仅凭4326/865/833参数推断32隐藏单元MLP | 产物强制`official_checkpoint=false`；平台包到达后独立实验ID替换，不继承本地成绩 | 技术负责人 | MITIGATED：检查点构建机器校验4326/865/833，所有状态、结果和报告均标记`official_checkpoint=false`；平台替换义务仍由H-006跟踪 |
| R-020 | P0 | 本地实验误消耗平台最多10次试运行 | 自动化操作登录平台或提交运行 | 当前只运行本地脚本，禁止UI/API提交；正式试运行需单独任务和用户明确授权 | 技术负责人 | MITIGATED：本任务无平台提交路径；浏览器自动化已停止 |
| R-021 | P1 | 10轮重分批造成时间/设备泄漏或公平性不一致 | 三策略看到不同样本或未来进度 | 固定流生成器与摘要；每任务共享检查点、批次和种子；机器验收检查10批次与样本身份 | 技术负责人 | MITIGATED：流生成测试、共享检查点哈希、9×10轮结果和`stream-audit.json`验证通过；密封批次为0 |
| R-022 | P0 | 共享策略仍通过原始指标尺度或任务身份形成隐性专属规则 | Macro-F1/RMSE使用同一原始阈值，或配置出现任务覆盖表 | 历史统一策略已停止；保留其负结果，不执行末期测试 | 技术负责人 | HISTORICAL/CLOSED：D-035允许任务独立模型与策略，D-032/D-034不再是当前路线；81作业证据继续保留 |
| R-023 | P1 | “最后一轮独立测试”被历史暴露结果伪装为全新密封证据 | 重用Gas 8—10或FD001 81—100后声称未见 | 阶段manifest记录暴露等级；Gas/FD001标记historically_exposed；仅未打开XJTU密封轴承可标记virgin | 技术负责人 | CONTROLLED/OPEN：开发搜索81/81完成且末期保持关闭；冻结记录已显式标注Gas/Engine历史暴露与Bearing virgin，等待一次性末期锁执行 |
| R-024 | P0 | PyTRiO凭据、Sampler路径或私有内容泄露 | 配置/异常/公开日志包含密钥或原始响应 | 环境变量注入、字段白名单、秘密脱敏、请求/响应仅存哈希；真实调用前做审计 | 技术负责人 | PARTIAL：PYTRIO-001已拒绝秘密键并仅记录哈希/Token/延迟；真实比赛环境和SDK日志仍需接入时审计 |
| R-025 | P0 | 大模型提案绕过预算、安全门或执行任意代码 | 模型输出直接转shell/Python/路径写入 | 严格schema、工具白名单、允许键/路径、候选隔离、预算预检和SafetyGate；失败时确定性降级 | 技术负责人 | MITIGATED：PYTRIO-001严格提案与ACTION-SANDBOX-001执行计划双重校验；工具注册表有指纹，路径/参数/训练前预算失败关闭，模型文本无shell或动态Python入口 |
| R-026 | P1 | 三任务独立优化导致公开验证过拟合 | 为每任务反复读取同一公开验证并选择参数 | 冻结内部开发/独立确认身份、验证读取记账、候选上限、隐藏评测只作最终确认 | 技术负责人 | CONTROLLED/OPEN：Gas停止于Batch 2—5开发/6—7历史确认；B按整轴承、C按整发动机完成一次9候选矩阵和一次确认后停止。公开validation只作冻结后门控，仍须隐藏评测确认 |
| R-027 | P1 | 开源论文代码许可证、供应链或资源不合规 | 无许可证、未固定版本、下载权重或依赖GPU/公网 | 论文/代码/许可证/哈希/CPU成本准入审计；隔离复现；仅固定哈希插件进入主线 | 技术负责人 | PARTIAL：PluginRegistry已强制根目录、许可证、任务和SHA-256；具体论文仍需PAPER-METHOD-001逐项审计，登记不等于获得执行权 |
| R-028 | P1 | PyTRiO没有实际价值却增加Token、延迟与失败面 | 与BRACE无大模型相比无性能/资源收益 | 公平开关对照；记录Token/延迟/故障；无价值时如实保留并以确定性策略运行 | 技术负责人 | CONTROLLED：A2负结果保留；A3新留出五项100%且A/B/C首轮3/3主动更新，证明动作合规价值。竞争运行的工业性能仍来自冻结参数日程，不能归因于LLM；30轮增加20362/2272 Token，2次预算耗尽后建议被训练前拒绝。按D-043停止继续LLM调参，服务失败保持确定性降级 |
| R-029 | P1 | 在同一公开Gas Batch 2反复优化造成确认污染 | 根据全量或确认指标继续改候选 | 冻结开发/确认；每实验验证读取记账；未过开发门不打开确认；新机制改用下一批恢复协议 | 技术负责人 | MITIGATED/CLOSED FOR LOCAL TUNING：过采样确认未打开；因果回放只用Batch 2—5选型、Batch 6—7冻结确认后不再调参；D-038已停止Gas本地扩展，历史暴露边界仍保留 |
| R-030 | P0 | PyTRiO训练额度不足、远程失败或模型仅学会格式而无决策价值 | 训练前余额为0、保存未返回持久化路径、留出policy match未改善或服务异常 | 有界SFT、训练前后留出、持久化收据、失败保留和正式模式失败关闭 | 技术负责人 | MITIGATED_LOCAL/OPEN_PLATFORM：基础模型在60秒窗口内三个独立宿主进程3/3返回严格合法非零Token提案，其中1次实际训练；0.7.1rc1干净容器不挂载宿主Tokenizer缓存也取得330/184 Token并执行候选。平台侧凭据注入及Token报告仍待正式试运行确认 |
| R-031 | P1 | 公开源码仓库没有项目级许可证 | 评委要求明确源码再利用许可或开源声明 | 依赖许可证与源码许可证分开说明；由权利人选择MIT/Apache-2.0等项目许可证后再提交 | 队长 | OPEN：仓库已公开分支但未虚构许可证，需队长作法律选择 |
| R-032 | P0 | 公开validation一次性门控后继续调参导致选择偏差 | 根据PAPER-FUSION结果重开validation或扩大候选 | 单次打开锁、结果SHA、D-046冻结混合门控；后续只在隐藏测试确认 | 技术负责人 | MITIGATED/OPEN：本轮只打开一次并停止；隐藏泛化仍未知 |
| R-033 | P1 | PaperFusion模型产物过大或被错误打包进镜像 | C模型约456MB、运行中峰值约3.20GB | `.dockerignore`排除joblib；镜像只含代码；运行时挂载数据并在输出卷训练；4核8GB容器复验 | 技术负责人 | MITIGATED：RC4镜像240,701,023字节且无权重；4核8GB断网训练完成、峰值RSS 3,198,783,488字节，运行时模型只存在输出卷。证据`docs/results/RC4_CONTAINER_ACCEPTANCE.json` |
| R-034 | P0 | 正式提交声明使用Agent但运行时静默退回确定性策略 | 平台报告Token为0且流程仍完成 | provider显式选择；PyTRiO模式记录触发、重试、Token和恢复收据；提交前核对模型、镜像/源码绑定和非零调用收据 | 技术负责人 | MITIGATED_LOCAL/OPEN_PLATFORM：60秒窗口下三个独立宿主进程3/3取得非零Token严格响应；发布镜像内另有一次330/184 Token成功与一次断网两失败后retain收据。零Token恢复不会训练候选。下一次平台试运行仍必须核对平台报告Token和绑定镜像 |
| R-035 | P0 | 基础Qwen3.5-4B结构化提案可靠性低于A3 Sampler | 历史新留出schema仅83.33%，任一非法响应可使严格正式运行失败 | 提示词只广告Native可执行action/parameter；保留严格schema与失败关闭；首个新试运行核对非零Token、10轮完成和非法响应数 | 技术负责人 | MITIGATED_LOCAL/OPEN_PLATFORM：收紧能力提示后，60秒窗口内3/3独立宿主响应和发布容器内1次响应均严格合法；冻结策略仍控制轮次与参数。平台容器内完整10轮非法响应数仍需正式试运行核对 |
| R-043 | P0 | PyTRiO提案覆盖冻结轮次、动作或训练参数，导致本地性能证据与默认镜像路径不一致 | 合法提案在非候选轮启动训练，或改写epoch/LR/动作 | Agent只表达训练/retain意图；冻结策略拥有轮次、动作和参数；服务恢复路径只retain；收据记录全部约束 | 技术负责人 | MITIGATED_LOCAL：独立审计发现后以红绿测试修复；A/B/C带PyTRiO训练意图与确定性冻结策略的候选数、最终指标和checkpoint完全一致；42项专项、377项完整回归及修复后容器验收通过 |
| R-044 | P0 | 未知任务同批Gate通过的候选在未来设备或工况上退化 | adaptation当前批改善并部署，但独立confirmation低于静态父模型 | 未知任务采用组/时间前向验证或无足够跨组证据时retain；确认集只作一次冻结评估，不用于回调参数；新机制须独立任务和新数据验证 | 技术负责人 | REALIZED_OPEN：UNSEEN-SIM-001中Battery/Hydraulic各部署1次后独立confirmation退化，Mill未部署并持平；A3/A4均严格改善0/3。当前RC冻结，等待新任务授权后处理 |
| R-045 | P0 | 报告重复评估公开validation并用其选择轮次，制造独立泛化假象 | 同一稳定checkpoint在多轮产生相同指标，报告仍标记“采用最佳轮次” | 逐轮只读Gate收据；冻结后只对round-10最终稳定checkpoint评估一次公开validation；schema记录读取次数并禁止`selected_round`字段；旧V1显著降级 | 技术负责人 | MITIGATED：确认无训练ID/特征/设备直接重叠证据；V2每任务validation读取1次、总3次，逐轮无`public_validation_metrics`，最终来源由Harness部署链决定。V1保留但标记为选择污染、仅界面演示 |
| R-046 | P0 | 本地模拟按行切分破坏Gas自然漂移、Bearing轨迹和Engine unit边界，并在预测前泄露标签 | 模拟器从父模型已见train均切十段或同一组跨轮/跨Gate | 独立StreamPlan；父训练/流/最终确认零交叉；先无标签预测封存再反馈；任务自然分组；ScoreVault不向ActionPolicy回传；顺序不变性与未来不可见测试 | 技术负责人 | MITIGATED_LOCAL：新入口三任务自然流、预测先于反馈、未来不物化、ScoreVault隔离和一次确认均通过；父/流/确认ID与特征交叉0，399项回归通过。旧均切入口只作历史复现；正式隐藏生命周期仍由H-001约束 |
| R-047 | P0 | 已部署候选在下一批证实负收益后仍作为父模型继续训练，造成灾难性最终退化 | `delayed_gain_t+1 < 0`但状态机没有回到直接前任的动作 | 保留一轮直接前任；负配对收益触发schema兼容、64 MiB受限的原子回滚；回滚不计作候选，下一批继续验证 | 技术负责人 | MITIGATED_LOCAL：A2复现B确认RMSE退化至993.202677；A3第10轮按`-310.293697`延迟收益回滚，确认恢复至241.980799。正式平台是否允许保留直接前任仍待H-001 |
| R-048 | P0 | 方法在同批或独立转换有效，但连续父链累积后失效或优化状态异常 | 固定父模型探针优秀，连续部署出现收益崩溃、学习率累乘、Gate标签影响路由或step倒退 | 每种晋级recipe必须从初始父独立跑完整九转换父链；Gate只验证；临时倍率不得写回；保存加载、epoch/step和下一批收益为硬门 | 技术负责人 | MITIGATED_LOCAL：A3保留学习率累乘失败；最终自审发现并修复A4 Gate趋势泄漏，A5因证据ID失配无效，A6三任务十轮平均收益均为正且checkpoint可加载、小于64 MiB；隐藏泛化仍由正式评测确认 |
| R-049 | P0 | 镜像校验在四挂载就绪前执行默认命令，导致原生训练入口因空`/workspace`或缺父checkpoint提前失败 | Docker默认`CMD start`，平台预检以裸容器或空挂载启动 | 默认命令只显示帮助并退出0；桥接器显式追加`start`/`submit`；同时做空挂载和真实挂载双验收 | 技术负责人 | MITIGATED_LOCAL/OPEN_PLATFORM：0.8.1裸启动稳定复现`PermissionError: /workspace`/退出1；0.8.2恢复`CMD --help`后退出0，显式start/submit仍完成父续训和1,244条预测。平台导入与真实生命周期仍待复验 |
| R-050 | P0 | 正式训练绕过宿主模型网关，或完成记录缺少真实模型调用ID | 平台判`model_calls_required`不满足 | 只经官方SDK `rnd.model()`调用宿主网关；每轮至少一次调用；`finish`引用当前轮全部`model_call_ids`；镜像不直连PyTRiO | 技术负责人 | MITIGATED_LOCAL/OPEN_PLATFORM：0.9.0rc1 A/B/C 30轮各产生一次宿主RPC并在完成记录引用全部30个唯一调用ID；正式镜像未安装PyTRiO。真实平台非零Token和计量仍待一次试运行 |

风险关闭必须在本表填写证据路径，不得仅写“已解决”。
## R-041 正式模型调用被策略分支跳过

- 等级：Critical
- 状态：平台已确认模型调用，关闭“调用被跳过”风险；提案有效性转R-053
- 证据：O-PLATFORM-017结算输入14,289、输出7,680 Token并完成30轮。
- 缓解：D-080的调用前置已由平台非零Token证实。下一次只需验证D-084后的提案有效与候选训练，不再把该问题描述为“未调用模型”。

## R-053 宿主模型输出被参赛者上限截断或格式解析拒绝

- 等级：Critical
- 状态：本地已缓解，平台待一次确认
- 证据：O-PLATFORM-017的30轮输出合计7,680 Token=`30×256`，且全部`host proposal was invalid`、候选数0。
- 缓解：D-084删除参赛者Token上限，使用SDK完整授权预算；关闭思考并请求JSON对象；只要求实际使用的train/retain意图；唯一对象容错、歧义失败关闭。`0.10.4rc2`通过469项回归和三任务30轮容器验收，平台是否返回有效提案仍须受控试运行确认。

## R-042 跨轮固定workspace目录冲突

- 等级：Critical
- 状态：本地与容器已缓解，平台待确认
- 证据：O-PLATFORM-015；平台指出第二轮`state_workspace`目的目录已存在。
- 缓解：每轮使用由dataset key、round index和stage ID共同派生的全新目录；`0.10.3rc1`在同一持久workspace中完成A/B/C各10轮且状态轮数连续。平台持久workspace行为仍待受控试运行确认。

## R-043 研究代码进入正式镜像

- 等级：High
- 状态：本地已关闭，后续新版本持续审计
- 证据：0.9.0rc1完整wheel含私有PyTRiO、SFT、SwanLab、模拟和论文模块。
- 缓解：D-081采用文件白名单构建；0.10.3最终镜像`/app`仅官方SDK、`brace_formal`与固定入口，依赖仅NumPy。禁入扫描确认旧`brace_msi`、PyTRiO、SwanLab、sklearn、SciPy、psutil、数据、权重和报告均未进入；递归`.pyc`也已排除。证据`results/FORMAL-AUDIT-FIX-001.md`。

## R-051 Agent建议覆盖训练内负证据

- 等级：High
- 状态：`SUPERSEDED_BY_D086`
- 证据：0.10.1过渡探针在B三折选择retain时仍执行e1，可能把公开验证偶然改善误当作跨设备泛化。
- 缓解：该旧风险对应已替代的确定性portfolio。D-086要求每轮真实训练，Qwen读取本地父/候选指标和历史后决定是否部署；SafetyGate只保留硬约束。跨分布泛化风险仍由后续正式评测确认。

## R-052 候选由本地指标采用但平台测量不支持

- 等级：Critical
- 状态：`SUPERSEDED_BY_D086`
- 证据：0.10.2先依据镜像内validation指标选中candidate，未以`candidate_response.summary.metrics`作最终部署权威。
- 缓解：用户已确认平台过程中不返回指标且不参与内部决策。0.10.6rc1只保存平台回执作审计，部署选择完全来自本地评估工具和第二次Qwen决策；A4证明30/30平台指标为空仍完成闭环。

## R-054 Qwen双阶段决策无效或质量不足

- 等级：High
- 状态：本地已缓解，平台待确认
- 证据：正式候选每轮依赖训练recipe与部署判断两次宿主模型输出；平台真实Qwen尚未验证该新双阶段契约。
- 缓解：严格JSON schema、受控recipe白名单、非法训练提案降级到最保守真实续训、非法部署判断保留父模型、硬SafetyGate不可绕过；A4 30轮/60调用本地协议验收通过。下一次平台试运行必须检查真实Token、两个call ID、候选数和决策记录。

## R-053 训练声明与实际执行recipe不一致

- 等级：High
- 状态：本地已关闭
- 证据：0.10.2候选实际由portfolio选recipe，但收据使用Agent请求epoch/LR和分折seed，可能造成复现声明错误。
- 缓解：0.10.3分别记录proposal与executed参数、有效学习率、父checkpoint优化器seed和fold seed；提交候选与完成记录使用真实执行seed。专项与全量回归通过。

## R-055 Qwen数值判断错误导致部署退化候选

- 等级：Critical
- 状态：`MITIGATED_CODE_DEVELOPMENT_MATRIX_PASSED_FINAL_HOLDOUT_PENDING`
- 证据：O-PLATFORM-019中Gas第5轮、Bearing第2轮、Engine第4轮的父/候选主指标关系与deploy动作冲突；当前`agent.py`只校验枚举和非空理由，`submission.py`未校验结构化决定与指标方向。
- 缓解：SELECTION-RELIABILITY-001建立唯一MetricContract；A1冻结反例3/3失败保留。A6关闭末轮探索、路径失败关闭和最终checkpoint绑定缺陷，有限探索开发矩阵无5%灾难任务。D-088的独立替代流门仍是正式RC前置。

## R-056 跨轮评价作用域变化导致伪历史最优

- 等级：High
- 状态：`MITIGATED_HISTORY_STRATEGY_EXCLUDED`
- 证据：O-PLATFORM-019中同一artifact在不同轮展示值变化，逐轮报告不支持直接全局排名。
- 缓解：所有比较携带validation作用域指纹；不同作用域历史只保留动作/资源摘要。A6明确使`conditional_champion`在正式SDK历史artifact持久化/恢复未验证时无条件不得晋级；开发候选不依赖该能力。

## R-057 墙钟耗时优化破坏决策信息或正式协议

- 等级：High
- 状态：`INSTRUMENTED_LOCAL_OFFICIAL_ATTRIBUTION_OPEN`
- 证据：O-PLATFORM-019三任务墙钟约10,442秒而CPU约1,692秒，但无逐阶段耗时，不能归因。
- 缓解：已增加互斥、脱敏且明确scope/excluded的history、两次模型调用、训练评估保存、候选提交、state序列化/RPC和finish ACK计时。仍未用平台运行验证归因；任何减少调用、缩短证据窗口或改变训练行为都必须独立实验，墙钟改善不足15%不得进入正式线。

## R-058 开发代理流多重尝试导致方法过拟合

- 等级：Critical
- 状态：`MITIGATED_DEVELOPMENT_FREEZE_FINAL_HOLDOUT_PENDING`
- 证据：PERFORMANCE-METHOD-PILOT-001在同一代理流运行A1—A4；A2/A3负结果已经影响最终只保留`balanced_current_e3 + native_recent_e3`复合分类候选的选择。
- 缓解：D-089冻结方法后禁止再用该流调方法/阈值；正式RC前必须执行D-088的一次性独立替代流/任务留出。打开留出后任何失败只允许回退已冻结A6，不允许继续针对留出调参。
