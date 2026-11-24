# 研究与工程决策日志

决策只追加，不删除。新决策替代旧决策时必须写明被替代ID和证据。

| ID | 日期 | 状态 | 决策 | 依据 |
|---|---|---|---|---|
| D-001 | 2026-11-06 | LOCKED | 锁定BRACE-MSI V4.1主线：预算与风险约束的最小充分迭代Harness，不再重新设计V5。 | 用户确认；外部评审仅作参考 |
| D-002 | 2026-11-06 | LOCKED | 确定性Harness是最低可运行核心，大模型仅为可关闭的白名单建议器。 | O-RULE-001、资源和稳定性目标 |
| D-003 | 2026-11-06 | LOCKED | 正式CPU镜像不默认加入PyTorch；先用轻量传统模型，正式数据证明需要时再评估。 | B-PLATFORM-001、2GB/CPU约束 |
| D-004 | 2026-11-06 | LOCKED | 个人100元预算不预先消费，只有客观实验支持时启用。 | L-TEAM-001 |
| D-005 | 2026-11-06 | LOCKED | 用户的视觉、MCU和边缘部署能力只用于执行风险评估，不改变赛题路线。 | 用户明确要求 |
| D-006 | 2026-11-06 | LOCKED | 状态机采用SDK事件驱动，预实现两种协议配置，不写死批次顺序。 | H-001及V4评审 |
| D-007 | 2026-11-06 | LOCKED | 新任务必须经过TaskBootstrap；禁止跨不兼容任务直接复用模型。 | B-DATA-001及V4评审 |
| D-008 | 2026-11-06 | LOCKED | ModelAdapter必须声明能力，批量模型不得错误调用`partial_fit`。 | 工程正确性 |
| D-009 | 2026-11-06 | PROVISIONAL | 初始CPU模型池为SGD、Logistic/Ridge、HistGradientBoosting、ExtraTrees。 | 正式任务小体量、CPU约束；待数据验证 |
| D-010 | 2026-11-06 | LOCKED | 漂移证据不是昂贵更新的唯一前置条件，性能退化可独立触发候选。 | 避免漏检与无效训练 |
| D-011 | 2026-11-06 | LOCKED | 运行时只执行白名单动作，禁止动态生成并执行代码。 | O-RULE-006、安全目标 |
| D-012 | 2026-11-06 | LOCKED | SafetyGate分为硬约束、统计比较和部署决策；隐藏流静态基线只作最终资格门槛。 | 在线信息边界 |
| D-013 | 2026-11-06 | LOCKED | SwanLab公开日志与私有审计日志分离，默认不公开B包逐样本信息。 | B-SWANLAB-001、H-004 |
| D-014 | 2026-11-06 | LOCKED | 技术负责人+Codex控制核心路径；队友承担可替换低风险任务及展示材料。 | L-TEAM-001 |
| D-015 | 2026-11-06 | LOCKED | 默认单种子`20261106`加一次队友干净环境复现；不宣称跨种子稳定。 | 时间预算与证据边界 |
| D-016 | 2026-11-06 | LOCKED | 性能触发式单动作更新是决定性强对照；BRACE被全面支配时停止加模块。 | V4评审 |
| D-017 | 2026-11-06 | LOCKED | 官方公式公布前分别报告性能和资源，不自创模糊总分。 | H-003 |
| D-018 | 2026-11-06 | LOCKED | 当前阶段先完成文档和一致性检查，不启动正式训练。 | 用户当前指令 |
| D-019 | 2026-11-06 | LOCKED | 允许在已下载Gas与C-MAPSS上启动本地代理训练；正式SDK适配仍阻塞。代理研发采用独立任务链，先审计和Smoke，再运行完整基线与迭代；结果不得冒充官方成绩。该决策仅在代理实验范围内替代D-018。 | 用户2026-11-06明确授权 |
| D-020 | 2026-11-07 | LOCKED | 在不解除正式SDK阻塞、不重开已消费密封段的前提下，连续实现平台无关的完整正式候选系统；未知官方部分使用可替换适配器，第三任务可用明确标注的合成流做工程验收。 | 用户2026-11-07明确授权；FORMAL-CANDIDATE-SYSTEM计划 |
| D-021 | 2026-11-07 | LOCKED | 正式候选开发结束，进入Release Readiness；停止代理密封实验和算法扩展，只完成容器、干净依赖、SwanLab/SDK接口准备及最终交付审计，不合并main。 | 用户2026-11-07明确授权；`LOCAL-FORMAL-SIM-001-A2`独立机器验收通过 |
| D-022 | 2026-11-10 | LOCKED | 正式数据接入从只读审计开始。Gas与C-MAPSS原件经哈希确认与既有代理数据完全相同，复用加载器和数据指纹但不把旧代理结果改名为官方成绩；XJTU-SY作为新增第三任务数据，在官方目标、切分与指标明确前不启动确认性训练。 | L-AUTH-004、L-DATA-004、H-006 |
| D-023 | 2026-11-11 | LOCKED | SwanLab/云端正式实验记录只在官方协议确定、最终工程模型冻结后，通过一次正式重新训练生成。当前数据审计、接口接入和开发验证只保留本地审计，不运行、修改或同步SwanLab；等待平台提供剩余规范。 | L-AUTH-005、H-004 |
| D-024 | 2026-11-11 | LOCKED | 在不改变RC和H-006阻塞的前提下，将XJTU-SY暂定为本地轴承RUL回归开发任务：按轴承身份冻结初训/开发/密封组，单个CSV独立提取时频特征，目标为该轴承剩余采样分钟数；只用于验证新增数据训练链和三策略行为，不表述为官方任务或成绩。 | L-AUTH-006、L-DATA-004、XJTU-SY说明书 |
| D-025 | 2026-11-11 | LOCKED | 采用最新平台截图冻结训练阶段三任务、指标和10轮优化协议；展示工作不进入当前关键路径。由于平台训练包未落地，先执行“规则对齐本地开发”，正式平台检查点到达后必须以独立实验ID替换初始模型，不得改名继承本地结果。 | O-PLATFORM-001至004、L-AUTH-007 |
| D-026 | 2026-11-11 | LOCKED | 本地规则对齐开发使用单隐藏层32单元MLP作为可替换初始检查点：128→32→6为4326参数、25→32→1为865参数、24→32→1为833参数，精确匹配平台公布参数量。该拓扑是可检验工程推断，不宣称与平台代码/权重相同；最终接入只替换检查点适配层。 | O-PLATFORM-002、参数量算术、H-006 |
| D-027 | 2026-11-11 | PROVISIONAL | `OFFICIAL-RULES-ALIGNED-DEV-001`完成后停止在同一开发流继续调参。平台接入初始策略为Gas优先复验BRACE、Engine暂定复验BRACE、Bearing安全默认保持静态；只有官方检查点与正式切分的新证据才能改变该选择。 | 9/9本地规则对齐实验；Gas/Engine相对静态改善，Bearing BRACE RMSE退化35.086308；D-016、D-017 |
| D-028 | 2026-11-11 | LOCKED | 正式训练包接入以随包NumPy训练器、真实`checkpoint.npz`及完整Adam/标准化状态为唯一初始模型；原包只读，候选通过隔离子进程写入新目录。D-026仅保留为训练包到达前的本地推断历史，不得用于正式包续训。 | O-PLATFORM-005；用户批准官方包接入设计 |
| D-029 | 2026-11-11 | LOCKED | 官方包本地开发执行三任务×十轮决策，比较简单性能触发与BRACE；每轮最多一个候选、BRACE每任务至少3次真实训练，只有公开验证主指标不退化且硬约束通过才部署。结果标记`official_package=true`、`official_scoring_ready=false`。 | O-PLATFORM-005、D-012、D-016、D-017；用户批准设计 |
| D-030 | 2026-11-11 | LOCKED | 官方包十轮仅称为候选适应决策轮，不宣称真实漂移流；父继承必须以1+1与连续2 epoch等价及状态变化证明；公开验证每次使用均记账且绝不参与训练/预处理；完整队列须在Smoke前后分别验证CPU、磁盘和墙钟预算。 | 用户对实施计划的四项补充要求 |
| D-031 | 2026-11-11 | LOCKED | `OFFICIAL-PACKAGE-DEV-001`完成后停止在同一公开验证集继续调参或重跑。内部`performance_triggered`在本次无真实流实验中只是一轮无条件低成本续训对照，不宣称在线触发策略；A/B保留该对照已达到当前最佳的负结果，C的BRACE增益仅作为隐藏评测待验证假设。 | L-EVIDENCE-003、D-016、D-030 |
| D-032 | 2026-11-11 | LOCKED | 进入独立的统一策略优化阶段：三个公开任务共同研发同一套身份盲EvidenceRouter、ActionPolicy、BudgetLedger与SafetyGate；决策输入统一为无量纲证据，禁止按数据集名称、任务ID或Profile选择动作。该阶段不改写D-031冻结实验，只在新的内部划分和实验ID上工作。 | L-AUTH-008；用户明确要求统一策略而非三套专属策略 |
| D-033 | 2026-11-11 | LOCKED | 每个任务采用“前期训练—中期调参—末期只测”的三阶段协议；共享参数先做任务级leave-one-task-out，再冻结一个最终配置，末期测试不得反馈调参。Gas和FD001末期结果必须标记历史暴露；XJTU三个未打开密封轴承可在预注册与配置冻结后作为真正未见确认集。官方十次测试机会当前保持零使用。 | L-AUTH-008；既有LOCAL-EXP-001与XJTU-LOCAL-DEV-001暴露记录 |
| D-034 | 2026-11-12 | LOCKED | `UNIFIED-POLICY-OPT-001-DEV-A1`的复杂BRACE在3/3任务级留出fold上相对简单性能触发策略无优势且资源更高，触发D-032阶段的预注册停止规则。最终候选冻结为身份盲`normalized_performance_triggered`简单策略；`shared-f8881ba9c291`仅作一次末期复杂对照，不再增加机制或调参。 | `docs/results/UNIFIED-POLICY-OPT-001.md`；严格验收`valid=true`；执行manifest与summary哈希 |
| D-035 | 2026-11-12 | LOCKED | 当前正式路线改为“Qwen3.5-4B PyTRiO Agent + BRACE确定性Harness + 官方A/B/C工业模型 + 经验证的开源优化方法”。统一十轮工作流、预算、安全、审计和回滚，但允许三个任务独立模型、参数、动作与历史。该路线替代D-032/D-034作为当前执行方向；统一策略实验及负结果继续保留，不执行其末期测试。 | O-PLATFORM-001/003/005、O-PYTRIO-001、B-PLATFORM-002、L-AUTH-009、`docs/FORMAL_ROUTE.md` |
| D-036 | 2026-11-12 | LOCKED | 正式Harness默认使用平台已校验通过的Qwen3.5-4B基础模型；持久化LoRA Sampler仅作为经实验验证后的可选增强。模型名、Sampler路径、Base URL和API Key只从运行配置/环境注入，服务失败退回确定性策略且不得绕过预算与SafetyGate。 | O-PYTRIO-001、B-PLATFORM-002、L-AUTH-009 |
| D-037 | 2026-11-12 | LOCKED | 开源论文/代码只在明确性能瓶颈后进入：先审计贡献、官方代码、许可证、官方模型兼容性和4核8GB CPU成本，再预注册、运行对照与消融；无实测增益、许可证不清或只作包装的方法不得进入正式系统。 | L-AUTH-009、实验真实性与供应链风险 |
| D-038 | 2026-11-12 | PROVISIONAL | Gas公开开发阶段保留`current_only + SafetyGate`为当前最低可用候选，不将均匀回放或类平衡回放进入主线，并停止使用Batch 6—7继续调参。该选择只是历史暴露公开流证据，须由隐藏评测确认。 | `PERF-A-OVER-001`负结果、`PERF-A-REPLAY-001`开发/确认结果、D-016 |
| D-040 | 2026-11-12 | LOCKED | PyTRiO微调只训练BRACE提案Agent输出严格、可执行的JSON，不训练或替代A/B/C工业模型，不赋予模型任意代码/工具执行权。首个正式Sampler采用Qwen3.5-4B、rank 8、最多3 epoch的普通assistant-only SFT；语料仅含合成聚合决策场景，独立留出评测schema有效率、动作/工具匹配率。只有持久化`trio://`路径与训练前后证据齐全时才可提交。 | O-PYTRIO-001/002、D-036、R-024/025/028、`PYTRIO-SFT-001`预注册 |
| D-039 | 2026-11-12 | LOCKED | 切换竞赛冲刺：Gas冻结不重训；B/C各只运行一次`1/3/5 epoch × 0.3/1/3 LR`整设备开发/确认矩阵，空间用尽即停止；暂停论文复现、LoRA、高级HPO和新架构。测试收缩为专项、实验机器校验和RC前一次全量/容器验收。 | 用户2026-11-12明确冲刺指令；11月13日提交窗口 |
| D-041 | 2026-11-12 | LOCKED | PyTRiO/Qwen Sampler返回文本仅允许在JSON边界剥离已实测的精确`<|im_end|>`后缀；其他任意尾随文本继续失败关闭。A2原始误判评测保留，不回写；修正后通过新文件复评同一Sampler。 | `PYTRIO-SFT-001-A2`真实输出、红绿回归测试、提交`6da8cea` |
| D-042 | 2026-11-12 | LOCKED | A2 Sampler在三任务静态包对照中30/30建议noop，性能完全来自最低候选守卫；不得表述为大模型带来性能增益。只允许再做一次包含身份无关最低候选证据的有界SFT与新留出验证；若主动候选率仍无改善，则停止LLM调参，正式默认使用确定性BRACE并保留Sampler为可选建议器。 | `PYTRIO-HARNESS-001-A2`六运行均机器复算有效；R-028停止原则 |
| D-043 | 2026-11-12 | LOCKED | A3是D-042允许的最后一次LLM调参并已通过：新留出五项100%，真实A/B/C首轮3/3主动训练。正式候选冻结为“A3持久化Sampler负责结构化动作意图 + BRACE使用已冻结任务参数日程 + ActionSandbox/SafetyGate最终裁决”；此后不再扩充语料、epoch或LLM搜索。Agent没有单独创造工业模型性能，性能贡献归于已冻结参数与门控；候选预算耗尽后的建议必须在训练前拒绝并保留审计。 | `PYTRIO-SFT-001-A3`、`PYTRIO-COMPETITIVE-001-A1`、`docs/results/PYTRIO-COMPETITIVE-001-A1.md` |
| D-044 | 2026-11-13 | LOCKED | RC3、A3和三任务参数保持冻结；允许执行一次`SWANLAB-FINAL-001`最终工程记录重跑并同步公开聚合指标。该运行只形成提交记录，不参与模型/策略选择；GitHub只推送脱敏源码与证据，镜像、数据、权重、凭据和完整Sampler路径不得进入仓库。 | L-AUTH-012、O-SWANLAB-002、D-023阶段条件已满足 |
| D-045 | 2026-11-13 | LOCKED | 在独立`codex/paper-fusion-sprint`分支恢复`PAPER-METHOD-001`，以当天可提交为边界，仅研究Gas知识蒸馏、CPU树模型集成和Successive Halving三项来源；RC3/A3/历史结果保持冻结。模型选择只用train内部组折，公开validation在配置冻结后打开一次。30%为进取目标而非验收伪目标。D-039的论文暂停只对RC3冲刺历史有效，不阻止本独立研究候选。 | 用户2026-11-13高强度性能优化指令；`docs/superpowers/specs/2026-11-13-paper-fusion-sprint-design.md` |
| D-046 | 2026-11-13 | LOCKED | `PAPER-FUSION-SPRINT-001`只在Engine C通过相对RC3严格改善门：A/B继续使用RC3，C采用PaperFusion。Gas蒸馏和Bearing树集成负结果保留；不得再次打开本轮公开validation或根据其结果继续调参。新候选统一使用BRACE预算、记录和SafetyGate，但允许D-035定义的任务专属模型。 | 单次公开validation：A 0.687918 Macro-F1、B 644.113606 RMSE、C 42.330230 RMSE；`docs/results/PAPER-FUSION-SPRINT-001.md`；机器门控manifest |
| D-047 | 2026-11-13 | LOCKED | 冻结`BRACE-MSI-0.4.0rc1`为当天可提交的本地Release Candidate：A/B沿用RC3安全候选，C使用D-046的PaperFusion；镜像不包含工业模型权重，运行时在挂载输出卷训练。该版本不移动RC3标签、不合并main、不再次打开公开validation；只有正式SDK映射、平台校验或隐藏评测新证据才能产生后续版本。 | `docs/results/RC4_CONTAINER_ACCEPTANCE.json`、`docs/results/RC4_VERIFICATION.json`、264项回归、可重载镜像归档SHA-256 `97bb0a9f...306dfa` |
| D-048 | 2026-11-13 | LOCKED | 官方Agent运行必须显式选择provider；选择PyTRiO时，传输失败、非法结构化响应或Harness provider异常一律失败关闭，不得静默改走确定性路线。确定性降级仍可用于明确选择的本地/非正式模式，但不能伪装成有效Agent调用。下一次平台试运行前必须确认持久化Sampler校验通过、提交绑定的镜像/源码版本明确，并以非零Agent调用收据为准入门槛。 | O-PLATFORM-006；红绿测试`tests/agent/test_pytrio_agent.py`、`tests/official_package/test_agent_harness.py`、`tests/test_cli_provider_selection.py` |
| D-049 | 2026-11-13 | LOCKED | 以`BRACE-MSI-0.4.0rc2`作为下一次平台提交候选，替代RC4的上传入口但不删除或改写RC4；在正式提交模型来源上，以已持久化并通过校验的Sampler替代D-036“基础模型默认”，基础模型仅保留为历史/明确对照。RC5只修复正式Agent显式选择、持久化Sampler准入、PyTRiO失败关闭及SDK请求/重试超时；A/B/C冻结算法与历史性能结论不变。 | D-048；提交`5165953`；`docs/results/RC5_CONTAINER_ACCEPTANCE.json`、`RC5_VERIFICATION.json` |
| D-050 | 2026-11-13 | LOCKED | 由于持久化Sampler在平台重复校验失败而Qwen3.5-4B基础模型校验通过，正式提交模型来源恢复为基础模型；该决定只替代D-049的模型来源与“必须提供Sampler路径”准入，不撤销D-048的显式provider、非零调用、超时和失败关闭要求，也不改变A/B/C冻结算法。A3 Sampler及其正负证据继续保留，不伪称基础模型具有A3的结构化准确率。 | B-PLATFORM-003、D-036、D-048、用户2026-11-13指令 |
| D-051 | 2026-11-13 | LOCKED | 将官方十个数据批次解释为十次决策层事务；每轮必须先由稳定模型预测并提交，再在标签合法开放后分析、决策、执行0至2个候选、门控并原子提交历史。执行候选不是固定菜单；第二候选只能由首候选失败或收益不足、新证据和剩余预算共同触发。至少三次真实“历史→假设→实验→评估→决策”，NOOP不计入。 | B-RSI-002、用户批准的受控双闭环计划；正式SDK字段仍由H-001约束 |
| D-052 | 2026-11-13 | LOCKED | 当前正式研发方向为受控双闭环：四缓冲区与物理未来隔离、身份无关证据路由、每任务ActionValueTable、影子前任配对收益、证据触发Qwen3.5-4B基础模型、确定性预算和SafetyGate、受限纯函数插件以及分层CPU模型注册。该决定细化并替代D-035中未定义的轮事务、数据生命周期和策略学习语义，但不改写既有RC、公开验证暴露、负结果或D-050模型来源。 | `superpowers/specs/2026-11-13-controlled-dual-loop-design.md`、B-RSI-002、用户批准计划 |
| D-053 | 2026-11-13 | LOCKED | 新候选必须真实继承平台提供的父`checkpoint.npz`并保留父链，不能以从头训练替代续训；模型注册门新增独立预测入口、父检查点实际加载证明、`checkpoint.npz`兼容和全部模型产物不超过64 MiB。提交镜像只接受`docker save`归档，镜像可用与模型/续训/评测通过分别验收。未知字段和挂载路径不得猜测。 | O-PLATFORM-007；H-001 |
| D-054 | 2026-11-13 | LOCKED | 在D-052双闭环中，Qwen只在证据触发时调用；服务或结构化输出失败时最多重试一次，仍失败则带完整收据继续确定性策略。该恢复必须显式标记`deterministic_recovery`，不得计作有效Qwen输出或隐瞒零Token。此项只替代D-048“任何PyTRiO异常终止整轮”的运行语义，不降低预算、SafetyGate或非零调用审计。 | 用户批准的受控双闭环计划；D-052 |
| D-055 | 2026-11-13 | LOCKED | A1/A2证明官方参考MLP续训可安全做到不低于静态，但不足以形成高竞争力增益；因此停止依据同一公开validation继续微调续训阈值，也不启动无性能依据的PyTRiO臂。下一步允许在公开train内部组折开发身份盲的自建分类/回归CPU候选，但正式候选必须把官方父模型作为实际集成成员、保存父哈希、独立预测并满足64 MiB门，不能把从头训练冒充续训。 | `DUAL-EXPERIMENT-001-A1/A2`；用户明确允许“若不成功则自建”；D-053 |
| D-056 | 2026-11-13 | LOCKED | 冻结GENERALIST-MODEL-001-A1的固定50/50父模型集成：A拒绝并保留官方父模型，B/C接受HGB父集成。不得根据已打开的公开validation改混合权重、模型池或参数；新RC只集成此冻结选择并验证训练/预测、资源、镜像和父链。 | A1一次性validation、B/C主辅指标共同改善、A SafetyGate拒绝、64 MiB与独立预测通过 |
| D-057 | 2026-11-13 | LOCKED | 冻结`BRACE-MSI-0.5.0rc1`为受控双闭环的本地Release Candidate：镜像提供身份盲的单包`generalist-fit`和独立`generalist-predict`入口，A保留官方父模型，B/C按D-056使用固定HGB父集成；模型只在挂载输出卷生成，不打包数据、权重或凭据。该RC已完成4核8GB断网训练、预测、完整回归及`docker save/load`，但不替代任何已在平台绑定的版本，正式SDK映射、镜像可用、模型校验与评测仍须分别验证。D-056已证明A通用候选无安全增益，因此DUAL-RC本地冻结门修订为“A不低于父模型且至少B/C两项改善”；A未严格超过静态的事实继续明示，不作全三任务提升声明。 | `docs/results/DUAL-RC-001.md`、329项回归、`DUAL_RC_CONTAINER_ACCEPTANCE.json`；D-053、D-056 |
| D-058 | 2026-11-15 | LOCKED | O-PLATFORM-008证明平台会拒绝“另一套模型替代baseline”。正式提交产物必须由官方训练器从本轮平台父`checkpoint.npz`继续训练，继承原模型schema、权重、Adam状态、预处理状态、epoch与step；`retain`仅允许原样保留父模型。HGB/ExtraTrees/PaperFusion等异构模型继续作为研究证据，但不得进入正式checkpoint或正式镜像可执行入口。`0.5.0rc1`保留为本地研究RC并标记`DO_NOT_UPLOAD`；后续正式RC采用原生父检查点续训并在镜像内禁用研究命令。 | O-PLATFORM-008、D-028、D-053；平台旧提交实际拒绝提示 |
| D-059 | 2026-11-15 | LOCKED | 平台发布线新增原生运行时适配层，直接消费`/data`和`/previous/checkpoint.npz`并写入`/workspace`、`/output`；本地完整包树审计与包内`baselines.train`只保留为研发/供应链证据，不再作为平台入口前置条件。新入口必须加载父检查点并延续原模型、Adam、标准化和计数状态，未知文件名或调用schema采用显式参数/安全发现并失败关闭。基础Qwen和SwanLab均为可选后端，缺失或断网不得阻断确定性训练闭环。 | O-PLATFORM-009；用户要求先在本地严格模拟完整提交流程 |
| D-060 | 2026-11-15 | LOCKED | 冻结`BRACE-MSI-0.6.0rc1`为平台原生候选：每个官方批次均产生一个决策事务和一个真实官方MLP续训候选，十轮不得以只测前三轮或预设NOOP代替；PyTRiO/Qwen仅能提出受限动作和参数，确定性Harness负责实际训练、门控与回滚。镜像默认启用基础`Qwen/Qwen3.5-4B` PyTRiO，断网/异常最多重试一次后带收据恢复；离线验收必须显式标记Token为0，不能冒充在线通过。 | PLATFORM-NATIVE-CONTAINER-002-A2-FINAL；348项回归；`docs/results/PLATFORM-NATIVE-001.md` |
| D-061 | 2026-11-15 | LOCKED | `0.6.0rc1`继续冻结为Protocol RC，D-060“每轮真实候选”不扩展为竞争策略。新竞争分支每轮必须作真实决策，但可执行0或1候选；`retain`是有证据地不训练并提交父模型，候选训练后不部署仍记`reject`。执行前必须证明Native与官方训练器逐状态等价；只迁移已冻结参数来源，不重开公开validation搜索；统一5%相对增益与Anchor零退化门由train内部证据和任务契约替代。Native PyTRiO、SwanLab和容器验收属于新RC发布门。 | 用户批准2026-11-15竞赛冲刺方案；`PLATFORM-NATIVE-001`收据反事实；独立只读审计 |
| D-062 | 2026-11-15 | LOCKED | 新竞争候选以稳定性能提升为首要目标，不以论文来源、创新性或Agent复杂度作为准入条件。允许在官方MLP父链与checkpoint schema不变的前提下采用公开认可的成熟CPU方法（类/样本权重、稳健或非对称损失、学习率调度、合法Replay等）；每项方法必须先有train内部证据并记录参数量、CPU、RSS、模型大小和最差阶段，禁止借此重开公开validation搜索或扩大为无界HPO。 | 用户2026-11-15补充要求；D-037实验真实性边界；O-PLATFORM-008父模型续训门 |

| D-063 | 2026-11-15 | LOCKED | 冻结`BRACE-MSI-0.7.0rc1`为本地原生竞争Release Candidate：A/C使用冻结竞争策略，B复用已验证Protocol策略；PyTRiO只能表达训练或retain意图，不能覆盖候选轮次、动作、epoch或学习率，服务失败只retain。发布性能边界为一次冻结公开确认A `0.725695` Macro-F1、B复用`0.6.0rc1`的`660.076488` RMSE、C `51.949287` RMSE；公开验证已暴露，不是官方成绩。377项回归、4核8GB断网30轮、独立预测、64 MiB和`docker save/load`通过；平台镜像/模型/试运行仍为外部阻塞。 | D-061/D-062；独立发布审计；`results/NATIVE-COMPETITIVE-RC-001-RELEASE.md` |
| D-064 | 2026-11-15 | LOCKED | 用户新增的电池老化、液压状态监测和铣削刀具磨损数据只用于`UNSEEN-SIM-001`独立泛化复演。RC7镜像、策略、历史证据和归档保持冻结；因新数据没有官方父checkpoint，允许在严格隔离的bootstrap分区生成明确标记为`simulated_parent=true`的兼容MLP父模型，再以adaptation分区执行十轮原生续训，最后一次打开confirmation分区。液压选择文献明确较难的蓄能器状态分类，电池预测放电容量，Mill预测实测VB；数据集名称不得进入动作策略。 | 用户2026-11-15授权；三个数据集随附说明；D-063 |
| D-065 | 2026-11-15 | LOCKED | `UNSEEN-SIM-001-A4`证明基础Qwen3.5-4B可经PyTRiO真实参与三任务十轮决策，但不证明性能泛化：16次有效响应和15次建议执行后，三个确认集最佳仍均为静态round 0。Battery/Hydraulic的同批Gate部署在跨设备/工况confirmation退化，Mill保持静态。confirmation已经打开，禁止据此调参重跑；当前RC7不得宣称未知任务性能。下一代候选若另行授权，优先改进组/时间前向验证或未知任务默认不部署，而非增加Qwen调用。 | `results/UNSEEN-SIM-001.md`；A3/A4机器报告与独立复算 |
| D-066 | 2026-11-15 | LOCKED | 冻结`BRACE-MSI-0.7.1rc1`为`0.7.0rc1`的发布补丁候选：只提高Native PyTRiO默认超时并内置经固定哈希校验的Qwen3.5-4B tokenizer-only资产；不改变工业模型、竞争参数、候选日程、SafetyGate或历史性能结论。镜像不得包含Qwen权重、工业模型权重、数据或凭据。真实容器在线提案、断网retain、383项回归及`docker save/load`全部通过后，`0.7.1rc1`替代`0.7.0rc1`作为本地上传入口；平台导入、模型校验和正式评测仍分别验收。 | `results/PYTRIO-ONLINE-001.md`、`results/RC71_VERIFICATION.json`、`results/RC71_CONTAINER_ACCEPTANCE.json` |
| D-067 | 2026-11-15 | LOCKED | 报告证据链禁止逐轮重复读取同一公开validation并据此选择“最佳轮次”。逐轮只能展示当轮Gate上的稳定/候选指标与Harness真实部署决定；十轮策略完全冻结后，公开validation最多评估最终稳定checkpoint一次，且只作历史暴露的描述性确认。旧`PLATFORM-REPORT-SIM-001`/`OFFICIAL-DATA-REPORT-001` V1报告保留为界面与协议演示，但其轮次排名和泛化结论无效。 | 用户2026-11-15验证集选择污染审计；`REPORT-EVIDENCE-FIX-001`红绿测试与V2机器报告 |
| D-068 | 2026-11-15 | LOCKED | 现有`platform_simulation.py`按JSONL行数均切十段且先开放标签的流程不得继续承担官方流程模拟。新模拟器采用双层评测：稳定模型先预测未见批次并封存，之后开放标签计算不反馈策略的Prequential指标，再按任务自然组生成Update/Gate并训练候选；最终确认集冻结后只读一次。Gas按自然批次与源内时间、Bearing按未见轴承寿命进度、Engine按完整unit构流；正式隐藏测试尚未开始且完全不可见，本地确认指标不得冒充官方隐藏成绩。现有RC、旧V1/V2报告和负证据全部保留。 | 用户2026-11-15架构级修改指令；本地官方包与完整Gas 10批只读审计；H-001 |
| D-069 | 2026-11-16 | LOCKED | 在V1未来隔离、预测封存、Update/Gate和父链基础上新增V2序贯语义：当前批次`arrival_metric_t`进入EvidenceRouter/ActionPolicy决定retain或续训；本轮Gate只作上线安全证据；若上一轮部署，则在下一批相同样本上用当前模型和直接前任影子模型结算`delayed_gain_t`。Bearing按轴承内严格时间顺序跨十轮仍是代理假设；Replay和先预测后标签是否对应正式平台继续由H-001约束。D-068的“Prequential永不反馈策略”仅被本决策替代，其他隔离与证据边界保留。 | 用户2026-11-16明确修正并授权完整训练；`docs/superpowers/specs/2026-11-16-delayed-gain-sequential-simulation-design.md` |
| D-070 | 2026-11-16 | LOCKED | 当上一轮部署模型在下一批相对其直接前任的配对延迟收益为负，且直接前任checkpoint通过schema、任务、特征、类别、拓扑和64 MiB兼容门时，序贯策略优先执行一轮原子`ROLLBACK`，不得继续从已证实有害的父模型训练。回滚不是候选训练，不消耗候选预算；其输出哈希、资源和下一批再验证均进入审计。若直接前任不可用，则保持原有有界候选/retain路径并降低收益归因置信度。 | `DELAYED-GAIN-SIM-001-A2`中B第10轮配对延迟收益`-310.293697`但最终RMSE恶化至`993.202677`；A3回滚后恢复至`241.980799`；红绿测试与407项回归 |
| D-071 | 2026-11-16 | PROVISIONAL | 性能优化不再预先锁定单一论文或方法，也不把当前MLP的epoch/LR微调当作主搜索空间。先在不含确认集的相邻训练批上运行多方法跨批可行性矩阵；异构模型只作为临时教师/性能上界，最终是否蒸馏回官方MLP由真实趋势决定。冻结RC、安全内核、父链和正式输出约束不变。 | 用户要求主动多候选试验、明显有效后再完整工程化；A3候选Gate与下一批证据错位 |
| D-072 | 2026-11-16 | PROVISIONAL | 正式候选层新增可审计MLP recipe而非异构checkpoint：保守父权重插值作为跨任务低风险首候选；最近窗口、累计回放和高步长当前更新作为由任务契约、当前证据与历史延迟收益选择的第二候选。A/B/C可以因证据不同选择不同recipe，但禁止读取数据集名称。该方向必须通过完整十轮Harness后才能替换冻结RC。 | `METHOD-PORTFOLIO-PILOT-001-A1/A2/A4`；异构教师显示A/B上限，正式MLP连续父链显示任务差异和可提交趋势 |
| D-073 | 2026-11-16 | LOCKED | 冻结Gate隔离修正后的`BRACE-MSI-0.8.0rc1`为当前本地性能候选，替代`0.7.1rc1`上传入口但不删除旧RC或标签。正式策略使用不含数据集名称的证据路由：保守父权重插值、分类最近窗口、回归成熟单调趋势高步长、非单调累计回放及下一批负收益直接前任回滚。A3提前激进策略永久淘汰；A5因报告ID失配无效，A6为最终证据。PyTRiO不能覆盖recipe/Gate/预算，失联两次后retain；SwanLab只在正式完成品重训时记录。 | `COMPETITIVE-POLICY-002-A1—A6`；421项回归；`results/COMPETITIVE-POLICY-002.md`；`results/RC80_CONTAINER_ACCEPTANCE.json` |
| D-074 | 2026-11-16 | LOCKED | 冻结`0.8.0rc1`历史归档，不在原归档上覆盖修补。依据O-PLATFORM-011只加固平台薄桥接边界：Native start可显式校验平台顶层父checkpoint哈希和期望轮次；每轮收据无论部署、拒绝或retain都声明实际输出的`checkpoint.npz`产物；argv prefix保持`python3 -m brace_msi`且不把未知平台frame字段写入核心。十轮预算仍由持久化workspace/history执行，若平台不能恢复该状态则失败关闭，不通过改写retain权重或伪造轮次规避。 | O-PLATFORM-011；现有空输出挂载、父链和retain专项测试；平台私有schema仍未知 |
| D-075 | 2026-11-16 | LOCKED | 冻结`BRACE-MSI-0.8.1rc1`为当前平台桥接候选，替代`0.8.0rc1`上传入口但不改写其性能证据。该补丁只增加显式父哈希/轮次校验、无mode argv prefix描述和全路径模型产物声明；训练策略、模型参数、Gate、PyTRiO和SwanLab语义不变。平台草稿适配器已被判无效，因此`0.8.1rc1`本地通过不等于官方兼容；只有平台重写桥接器并以真实挂载检查digest后才能解除阻塞。 | `PLATFORM-BRIDGE-001`；54项专项、424项回归；`RC81_CONTAINER_ACCEPTANCE.json` |
| D-076 | 2026-11-16 | LOCKED | 冻结`BRACE-MSI-0.8.2rc1`为空挂载预检补丁，替代`0.8.1rc1`上传入口但不改写其桥接和性能证据。镜像默认命令从`start`恢复为首个平台可运行版本使用的`--help`，防止镜像校验阶段在四挂载尚未提供时误启动训练；平台桥接器仍须显式追加`start`或`submit`。训练策略、父链、模型参数、PyTRiO和SwanLab均不变。 | O-PLATFORM-012；本机复现0.8.1裸启动`PermissionError: /workspace`/退出1；0.8.2裸启动退出0且真实挂载start/submit通过；`PLATFORM-PREFLIGHT-001` |
| D-077 | 2026-11-16 | LOCKED | 正式训练的模型调用协议改为由镜像原生实现`openai.chat.completions.v1`边界并接收`workspace_io.model_transport`，不再要求平台把Chat Completions重写成PyTRiO私有Sampler协议。平台模式每个`start`强制发起模型调用并要求正Token；两次失败后retain父模型且不训练。PyTRiO私有传输保留为本地/历史入口，训练器、父链、Gate和预测不变。 | O-PLATFORM-013；红绿测试；4核8GB断网容器替身传输123/45 Token；`PLATFORM-MODEL-TRANSPORT-001` |
| D-078 | 2026-11-17 | LOCKED | 正式发布边界改用官方`contest_harness` 1.0.2与`contest.harness.workspace.v2`，替代D-077猜测的`workspace_io`正式接法。新RC保留当前原生父checkpoint续训、性能策略、SafetyGate与预测内核，只新增`/app/harness.py`和薄`contest_submission.py`；每轮模型调用必须经`rnd.model()`/`rnd.transport()`取得真实`model_call_ids`。正式镜像不内置PyTRiO密钥、私有Sampler客户端、本地模拟数据或测试报告。0.8.3保留为历史桥接证据，不再作为上传入口。 | O-PLATFORM-014；官方SDK Linux断网15/15测试；用户要求基于首次可运行版本最小改动 |
| D-079 | 2026-11-17 | LOCKED | 测试版与正式上传版物理分离：本地测试可包含宿主协议替身、自动测试、模拟器和脱敏报告，但正式`docker save`镜像只能包含运行时依赖、官方SDK及`/app/harness.py`/`contest_submission.py`固定入口；不得安装SwanLab、直连PyTRiO、Tokenizer，不得包含测试、脚本、数据、权重、密钥或本地报告。SwanLab继续作为外部公开训练记录链接，宿主模型由平台管理。任何上传归档必须由最终源码重建并通过内容扫描、三任务协议复演及`docker load`。 | 用户2026-11-17明确要求区分用户目标、官方要求、测试版和正式上传版；`OFFICIAL-SDK-V2-001`镜像审计 |

## 已被替代的历史决策

- 早期草稿中的“稳定跑完 > 演示效果 > 客观性能”顺序已被D-001方案替代。当前顺序为：硬性资格、超过静态基线、单位资源收益、可复现审计、答辩展示、额外创新。
- 早期草稿把11月16日作为主要节点。当前按H-005处理，并以11月13日作为内部最早风险节点，等待学校正式通知。
- 早期单一MLP/微调路线已被D-002、D-003和D-009替代。
- D-032的三任务同参身份盲策略及D-034的简单统一候选已被D-035替代为历史研究证据；其81作业和负结果保留，不打开末期数据。
## D-079 第一性原理正式运行核重建

- 日期：2026-11-17
- 状态：`LOCKED`
- 决策：冻结`0.9.0rc1`及全部历史RC，不在失败适配器上继续叠加补丁。新分支`codex/first-principles-rebuild`只保留官方SDK 1.0.2、父checkpoint兼容NumPy续训、候选/retain、状态和纯预测；建立最小`brace_formal`正式运行核。
- 依据：O-PLATFORM-015两次平台失败原文、首次成功零Token证据、第一性原理取证报告。
- 边界：不把零Token成功写成Agent成功；不把本地模拟写成隐藏测试；不消耗官方次数做基础调试。

## D-080 模型调用必须位于所有策略分支之前

- 日期：2026-11-17
- 状态：`LOCKED`
- 决策：每轮在retain、训练、拒绝或回滚判断之前直接调用一次`rnd.model()`；max tokens受宿主上限约束，不硬编码模型名，不要求响应含usage。无真实call ID时失败关闭；有call ID但提案非法时允许安全retain。
- 依据：官方SDK 1.0.2和O-PLATFORM-015。

## D-081 正式镜像采用运行时白名单

- 日期：2026-11-17
- 状态：`LOCKED`
- 决策：正式镜像不安装完整`brace_msi` wheel，只复制官方SDK、固定入口、最小`brace_formal`和NumPy。PyTRiO私有客户端、SwanLab、SFT、模拟器、论文实验、数据、权重、报告和密钥全部禁入。
- 依据：官方SDK宿主管理模型服务设计和历史复杂镜像故障面。

## D-082 正式模型接入只使用官方宿主网关

- 日期：2026-11-17
- 状态：`LOCKED`
- 决策：正式Harness每轮直接使用官方SDK的`rnd.model()`，不在镜像内安装或调用PyTRiO私有`ServiceClient`，不在线训练或保存Sampler权重。账号中已有Sampler只保留为历史研究证据；提交页可选择的基础模型由平台绑定到宿主网关。Agent是否真实工作只由平台非零Token、真实调用ID和轮收据证明。
- 依据：O-PLATFORM-014、O-PLATFORM-015、O-PLATFORM-016；两次历史成功运行均为0 Token，最近失败明确指出正式入口未产生宿主模型调用。

## D-083 0.10.3rc1取代0.10.2rc1作为本地终审候选

- 日期：2026-11-17
- 状态：`LOCKED`
- 决策：`0.10.2rc1`保留为已撤回历史证据，不得上传。`0.10.3rc1`以平台返回测量作为候选部署权威，缺失或不改善时失败关闭；训练声明区分Agent提案与实际recipe；独立组不足时retain；工作区按dataset/stage/round隔离。只有`0.10.3rc1`完成的全量回归、官方SDK离线测试、4核8GB只读断网30轮和`docker save/load`同ID证据可作为下一次平台受控验证的本地准入。
- 依据：`FORMAL-AUDIT-FIX-001`终审、机器验收及`docs/results/FORMAL-AUDIT-FIX-001.md`。

## D-084 正式宿主模型预算与决策职责归位

- 日期：2026-11-18
- 状态：`LOCKED`
- 决策：正式参赛代码不向`rnd.model()`传`max_tokens`，由官方SDK使用宿主本轮下发的完整`max_output_tokens`；禁止再引入256、1024或其他参赛者自设输出上限。宿主模型只给出`train/retain`意图和理由，实际epoch、学习率与recipe由受控执行层依据训练内部证据选择；未被执行的模型参数不得成为提案非法原因。唯一合法JSON对象可从宿主外包装文字中提取，多个/无对象或非法动作继续retain。
- 依据：O-PLATFORM-017的输出Token恰为30×256且30轮全部提案非法；用户明确否决任何非官方Token上限；官方SDK 1.0.2缺省行为会自动使用`rnd.max_output_tokens`；`FORMAL-AGENT-OUTPUT-001`红绿测试与容器验收。

## D-085 每轮真实训练与部署决策分离

- 日期：2026-11-19
- 状态：`LOCKED`
- 决策：正式十轮中每轮必须从平台父checkpoint产生一个真实、父链兼容的候选训练；Agent负责提出和解释实验假设，但其retain建议不得跳过本轮训练。候选训练不等于部署：平台权威测量与SafetyGate决定采用候选、保留父模型或在后续证据变坏时回滚。不得为了保证训练次数而强制部署劣质候选。
- 边界：不改变官方SDK、父checkpoint schema、独立预测、宿主模型调用、平台测量权威和64 MiB门；不增加参赛者自设Token上限；候选recipe只来自现有父链兼容白名单并记录真实执行参数。
- 依据：O-PLATFORM-018证明0.10.4rc2的30次有效Agent提案全部retain，造成候选数0和三任务零提升；用户明确要求“每轮训练，然后决定是否部署与回滚”。

## D-086 Qwen双阶段决策取代平台指标裁决

- 日期：2026-11-19
- 状态：`LOCKED`，替代D-085中“平台权威测量决定部署”的部分；D-085的每轮真实训练要求继续有效。
- 决策：每轮至少两次正式宿主模型调用。第一次由Qwen读取父模型、当前数据摘要和历史实验，从受控白名单中选择本轮训练recipe；Harness完成真实训练和本地合法验证。第二次由Qwen读取父/候选主辅指标、资源、recipe和历史风险，决定`deploy / retain / rollback`。Harness只执行决定并由SafetyGate检查可加载、有限值、资源、父链和数据合法性等硬约束。
- 平台边界：平台只提供当前合法数据、父checkpoint、宿主模型网关和最终评测；`submit_candidate`返回的指标仅保留作平台审计，不参与镜像内部部署选择。`retain`表示候选已经训练和评估但不部署，不再表示跳过训练。
- 依据：用户对D-085实现语义的纠正；官方SDK允许同一Round多次`rnd.model()`并在`finish.model_call_ids`引用全部真实调用，代码中没有单调用限制。

## D-087 Qwen在确定性指标事实与合法证据可行集合内决策

- 日期：2026-11-20
- 状态：`LOCKED`，细化并部分替代D-086中“Harness只检查硬约束”的范围；D-085每轮真实训练与D-086每轮双宿主调用继续有效。
- 决策：指标名称、固定方向、父/候选数值、有向收益、验证作用域和产物合法性由Harness计算并作为唯一机器事实。Qwen继续选择本轮recipe、解释证据，并在Harness给出的合法可行集合内决定`deploy / retain / rollback`；Qwen不得通过结构化字段覆盖已确定的数值关系、证据不可比或硬风险。
- 同口径边界：只有评价作用域指纹一致的父/候选可作确定性比较。历史artifact只有在官方SDK声明可恢复、哈希和schema通过，并在当前合法作用域重新评价后，才能成为`best_stable`或rollback目标；否则rollback只表示拒绝候选并保留当前父模型，必须诚实记录。
- 探索边界：不把“主指标任何微小退化永久禁止部署”写成通用规则。允许预注册、预算受限且可恢复的探索策略参与本地对照；进入正式候选前必须跨任务、跨阶段证明收益和风险。自然语言rationale只作审计，不再解析成第二个决策器。
- 运行时边界：正式镜像仍只调用官方宿主`rnd.model()`，保持每轮两次调用、父链、预测入口和64MiB约束。PyTRiO训练与SwanLab记录只位于镜像外研究/发布层，证明有效后才能影响配置，私有客户端、Sampler、Tokenizer、密钥和SwanLab依赖不得进入正式镜像。
- 提速边界：先记录聚合阶段耗时再优化；允许在不删父/候选数值、方向和硬风险的前提下去除重复措辞。减少模型调用、改变证据窗口、训练recipe或轮次均不是低风险修改，必须独立预注册。
- 依据：O-PLATFORM-019的真实决策矛盾、跨轮作用域变化和墙钟/CPU差；用户批准的分阶段可靠性—泛化—性能—发布方案；只读代码与多Agent审计。

## D-088 开发策略通过不等于最终泛化准入

- 日期：2026-11-20
- 状态：`LOCKED`
- 决策：A5使用与触发条件形成相同的开发代理流，即使通过修正后机器门，也只能产生候选策略，不得直接进入正式RC。先完成父checkpoint兼容性能方法pilot并冻结组合；随后在未参与触发阈值或方法选择的替代流/任务留出上做一次最终泛化验收。只有开发与留出都满足平均、最差阶段、资源和零泄漏门，才能构建新正式候选。
- 边界：最终留出方案不得使用已暴露confirmation/public validation，不得为了通过而在观察结果后调阈值；失败时继续保留冻结Protocol RC。
- 依据：A4独立复审P0/P1、A5审计修复结果与用户“正式确认前多试几次、先本地验证泛化性”的要求。
## D-089：只保留当前批类平衡续训复合分类候选（2026-11-20，PROVISIONAL）

- 决策：在冻结A6有限探索与原生回归recipe的基础上，只把`balanced_current_e3`加入分类候选集，并保留`native_recent_e3`作互补；Huber、非对称Huber和输出偏差校正不进入下一正式候选。
- 依据：A1显示`balanced_current_e3`复合候选提高A的平均和最差相邻未见收益；它相对`native_recent_e3`同时改变训练范围与损失，不能归因于类平衡单因素。A4集成后A平均收益`0.312990→0.360481`、最差相对收益`-0.5470%→0`，B/C checkpoint与A6相同。A2偏差校正降低C的RMSE/NASA趋势；A3全回归组合触发B 5.95%灾难退化。
- 边界：本决策只是同一开发代理流上的候选冻结，不是独立泛化或正式RC通过。只有D-088独立替代流/任务留出通过后才可升级为正式采用；失败则回退A6方法集。
- 证据：`results/PERFORMANCE-METHOD-PILOT-001.md`及A1—A4机器摘要。

## D-090：允许一次正式部署决策Advisor的镜像外有界SFT（2026-11-20，LOCKED）

- 状态：`LOCKED`，仅在本任务范围内替代D-043“此后不再扩充LLM语料或训练”的部分；D-043历史证据和旧Sampler结果保留。
- 决策：用户在本轮明确授权使用PyTRiO训练且预算充足。A1基础Qwen在12个正式deployment提示中schema与Token门均通过，但两个硬风险场景仍请求deploy；因此允许一次新的、预注册且哈希冻结的镜像外LoRA SFT。训练只使用合成聚合指标和正式提示，训练/留出按风险类型与历史组合隔离；不追加HPO或第二次语料修补。
- 采用边界：新Sampler只有在全新留出上schema、可行集合、硬风险与总体决策门全部通过并严格优于同一留出基础模型时，才能成为“建议提交页选择”的Advisor候选。其`trio://`路径、Tokenizer、PyTRiO/SwanLab SDK和凭据不得进入正式镜像；未取得平台模型校验通过前不得声称正式运行已采用。
- 安全事实：A1的6个精确标签差异中，4个是`rollback`替代`retain`，没有越出当轮可行集合；真正需训练修复的是2个硬风险deploy。无论模型结果如何，确定性Harness继续对硬风险和指标事实拥有最终约束。
- 依据：`PYTRIO-ADVISOR-OPT-001-A1`机器结果、独立审计、用户2026-11-20明确的训练与预算授权。

## D-091：一次性XJTU密封结果不得覆盖预注册最差阶段门（2026-11-20，LOCKED）

- 决策：`FINAL-GENERALIZATION-VALIDATION-001-A1`虽在三个密封轴承上取得RMSE/MAE总体改善，但开发流最差相对收益为`-99.61%`，违反打开前冻结的`>=-5%`门；独立审查另发现开发延迟收益复用当前Gate、峰值RSS和恢复未验证。该组合不得晋级新正式RC，也不得用密封结果调整阈值、recipe或模型后重跑。
- 允许保留的证据：密封标签此前未参与选择，最终预测的总体改善可作描述性性能证据；它不补正开发协议缺陷。开发严重阶段退化说明当前连续父链仍不够稳定。正负结果必须同时报告。
- 后续边界：继续保留既有Protocol RC；A4分类复合方法仍缺新的真实独立分类证明。只有新的、未参与当前选择的数据来源或正式新增官方材料才能开启新的性能任务。
- 依据：预注册配置SHA-256 `5DD6512F...671634`、机器摘要SHA-256 `22D4143B...38AA05`及D-088。

## D-092：0.10.6rc1降级为不可最终上传的Protocol RC（2026-11-20，LOCKED）

- 决策：`0.10.6rc1`继续保留为已验证的官方SDK/容器Protocol RC，但标记`DO_NOT_UPLOAD_AS_FINAL`。其精确归档可以完成A/B/C十轮、60次宿主调用、30个候选和预测，却会在宿主错误要求deploy时采用主指标明确退化的候选；协议成功不得替代选择可靠性准入。
- 后续边界：`afa9038`之后的当前源码修复只有在不携带D-091失败研究组合的前提下，构建新的独立正式归档并重新通过错误决策、30轮、官方SDK、Docker及材料绑定门，才可产生新的上传候选。当前HEAD通过测试但没有正式镜像，不得冒充已修复发布物。
- 依据：`RELEASE-COMPATIBILITY-AUDIT-001`；精确归档SHA-256 `F7518609...D89CB`；C父/候选RMSE `52.868573/55.629944`且`wrong_deploy_accepted=true`；当前源码完整回归533项。

## D-093：Competition Core成为唯一待实施正式架构（2026-11-20，LOCKED）

- 决策：正式系统采用`OfficialRoundAdapter → TaskProfiler → 双阶段QwenExperimentAgent → CandidateTrainer → LocalEvaluator → ArtifactSelector → RoundRecorder`唯一运行链。隐藏评测可包含A/B/C之外但与官方训练包同格式的新任务；算法依靠任务合同、父checkpoint、数据画像和历史，不按数据集名称路由。
- 轮次语义：每轮必须从父checkpoint至少训练一个真实候选，训练后才允许部署、保留或回滚。历史数据与历史模型可用；历史模型必须可恢复并在当前同一验证作用域重评后才能参与选择。Harness核对指标方向、数值关系与官方硬约束，不设置非官方Token、候选数、epoch、提升比例或固定安全阈值。
- Agent与发布：PyTRiO在镜像外训练Qwen Agent并由SwanLab记录；只有提交页校验通过的Sampler才可由平台绑定。正式镜像只经`rnd.model()`访问宿主模型，不包含PyTRiO/SwanLab客户端、Sampler、Tokenizer或凭据。本地测试镜像与正式上传镜像使用独立构建清单。
- 替代关系：保留D-079至D-087已经验证的官方SDK、父链、双阶段调用和指标一致性原则；旧四缓冲区、Bandit、影子收益、固定动作日程、固定提升门、Anchor零退化和任意代码补丁不进入新核心。D-088至D-091保留为历史研究证据，不作为新架构必须机制。
- 依据：用户2026-11-20对赛题语义、每轮训练、未知同格式任务、历史数据、双镜像、非官方限制和PyTRiO组成的逐项确认；书面规格`docs/superpowers/specs/2026-11-20-competition-core-design.md`。

## D-094：Competition Agent Sampler未达门，发布继续使用平台基础Qwen（2026-11-21，LOCKED）

- 决策：`COMPETITION-AGENT-SFT-001` A1/A2均保留为真实PyTRiO证据；A2虽完成持久化和重载且schema/部署选择100%，但严格总体策略87.5%低于预注册90%，不得在提交页选择该Sampler。Task 12正式候选继续选择平台已校验的`Qwen/Qwen3.5-4B`基础模型。
- 执行边界：正式镜像仍只调用官方`rnd.model()`，不包含PyTRiO、SwanLab、Tokenizer、Sampler或凭据。基础模型输出仍须经过RecipeRegistry可执行性校验、同作用域指标事实与父模型回退；Sampler路径仅留在仓库外受控收据。
- 依据：A1/A2机器结果、重载复评、预注册采用门及公开SwanLab脱敏运行`ph2ztekq`。不因训练已经付费而降低采用标准。

## D-095：冻结0.11.0rc1为Competition Core正式平台候选（2026-11-21，LOCKED）

- 决策：以提交`a28a1fe`的正式运行清单构建`brace-msi:0.11.0rc1`，冻结`D:/brace-msi-release/COMPETITION-CORE-RC-001/harness.tar`为下一次受控平台验证的唯一候选。正式镜像与`LOCAL_TEST_ONLY`镜像物理分离；正式镜像不包含模拟器、数据、权重、测试、报告、PyTRiO、SwanLab、Tokenizer、Sampler或凭据。
- 准入证据：已知A/B/C与两个内容身份不透明同格式任务共50轮、100次双阶段宿主调用替身、50个真实父链候选；错误部署被拒绝，历史模型须恢复并在当前作用域重评后才可回选；模型保存加载预测一致。4核8GB、断网、只读根、非root、官方SDK 1.0.2、归档重载、内容扫描和全新环境629项测试通过。
- 性能边界：公开A/B/C的独立开发矩阵只有约+2.35% Macro-F1、-0.17%/-1.88% RMSE描述性提升，不能声称30%或获奖水平；精确镜像重复公开validation只验证选择协议。代理任务显著提升不等于隐藏泛化。
- 外部边界：本决策只授予本地Release Candidate地位，不等于平台运行成功。上传、保存新提交版本或消耗试运行仍须用户单独授权；真实模型网关、挂载生命周期、Token计量和隐藏评分只能由平台验证。
- 依据：`results/COMPETITION-CORE-RC-001.md`、`release-audit.json`和归档SHA-256 `b7ba01bc...503e30`。

## D-096：L2-SP、SAM-Adam与AdamW不进入当前正式候选（2026-11-21，LOCKED）

- 决策：`MATURE-OPTIMIZER-PILOT-001-A1`中三种成熟方法和两条原生对照的跨任务平均有向收益均为负；B任务所有方法退化，C的L2-SP/AdamW没有显示出超越原生Adam的额外价值，A短阶段Macro-F1没有分辨率。因此不把L2-SP、SAM-Adam或AdamW注册进当前正式RecipeRegistry，不构建新镜像。
- 保留边界：研究代码、单元测试和负结果保留，用于可复现审计；默认Adam路径已通过兼容回归。该结论只针对当前父模型、当前数据协议与预注册参数，不被解释为方法在其他问题上普遍无效。
- 停止边界：不打开confirmation，不扩大参数搜索，不以Pareto成员名义绕过“跨任务平均正向且最差阶段不劣”的采用门。`0.11.0rc1`及其归档哈希保持不变。
- 依据：`results/MATURE-OPTIMIZER-PILOT-001.md`，机器摘要SHA-256 `49BFF569...6087B02`，专项15项与完整644项测试。

## D-097：P3采用共享TrialRunner开展同预算优化器对照（2026-11-22，PROVISIONAL）

- 决策：下一研究任务不增加正式Recipe数量，而是在独立分支建立共享`TrialRunner`和可插拔`Random/TPE/Qwen`优化器。三臂必须复用相同父checkpoint、数据fold、条件搜索空间、候选执行器、评价器、选择器及候选/物理训练/work-unit预算；静态父模型只作零训练参考。
- 历史反馈：Qwen输入新增逐trial的recipe、请求/实际参数、同作用域父/候选指标、有向收益、选择/拒绝、失败、CPU/墙钟/RSS、work units和延迟收益；不含逐样本、原始路径或密钥。必须设置`Qwen-No-History`消融，真实服务标识缺失或使用本地替身时Qwen臂无效。
- 实验顺序：先只在C Engine官方train内部按完整unit完成6候选可行性探针；不读公开validation。协议通过后才能预注册A/B/C三任务、三配对种子、每臂10候选的大矩阵，且大矩阵仍需用户再次明确批准。
- 发布边界：`0.11.0rc1`、正式镜像白名单、XJTU密封和全部历史实验冻结；Optuna/PyTRiO研究依赖不进入正式镜像。本地train内部结果只能证明相对优化效率，不能冒充隐藏泛化。
- 依据：用户P3任务书；50轮收据字段完整但仅两种重复recipe的只读审计；`superpowers/specs/2026-11-22-adaptive-optimizer-competition-design.md`；O-OPTUNA-001。

## D-098：P5采用稳健双窗口证据链作为待审批设计（2026-11-22，PROVISIONAL）

- 决策：P5最小方案采用稳健位置/尺度、一维Wasserstein和KS辅助统计组成的双窗口监测；阈值由历史稳定窗口经验校准，特征多重比较使用FDR与效应量双门，漂移确认要求持续证据。诊断严格拆分统计事实、可能解释和未知项，禁止把输入漂移写成设备故障。
- 集成边界：在`TaskProfiler`与第一次`QwenExperimentAgent`调用之间加入`DriftMonitor → DiagnosisAttributor → EvidenceProjection`；Qwen提案必须引用有效事实ID。训练、指标、ArtifactSelector、回滚、checkpoint、SDK和预测不改。冻结`0.11.0rc1`不原地修改。
- 状态边界：该方案只有书面设计，没有代码、合成验证、工业验证或正式镜像证据；用户审批前`P5-DRIFT-DIAGNOSIS-IMPLEMENT-001`保持阻塞。
- 依据：P4五大能力审计、L-DRIFT-001及`designs/P5-DRIFT-DIAGNOSIS-2026-11-22/`五份文档。

## D-099：P5第一阶段采用相关性感知校准和双参考池状态机（2026-11-22，LOCKED_PHASE1）

- 决策：特征内位置/尺度/Wasserstein/KS统计合并为联合得分；特征间满足块交换性时采用同步完整块置换`maxT`，无法使用maxT时提供BY保守降级。BH不作为无条件默认。调整后显著性与标准化效应量必须同时过门；经验p值分辨率不足时返回`insufficient_calibration`而不是稳定。
- 序贯与状态：运行级误报由已知/开放时域alpha-spending账本约束；活动参考池与隔离候选池分离，WARNING/CONFIRMED冻结旧参考，短暂波动经RECOVERY回旧epoch，持续新状态只有达到候选稳定窗口要求后才能原子建立新epoch。
- 实施边界：本阶段只冻结`DriftReport/DiagnosisReport/DriftState`接口并实现漂移统计和状态核心；不接入`round_core`、诊断归因、Qwen、训练器、选择器、Docker或正式RC。冻结`0.11.0rc1`归档和受保护源码保持原样。
- 证据：`results/P5-IMPLEMENTATION-001.md/json`；24项专项、676项全量回归；128维/2047置换A2墙钟`5.546296s`、CPU`6.90625s`、峰值RSS`76,218,368B`。A1朴素实现43.885秒负证据保留，未降低统计预算。
## D-100：P5-1A最终统计配置与种子冻结（2026-11-22，LOCKED_VALIDATION）

- 决策：P5漂移核心验收主臂固定为24/34/128维、80行窗口、完整块大小4、2047次同步置换、`alpha_run=0.05`、10窗口等额alpha-spending和效应量门2.0；独立流seed是统计重复单位。
- 最终种子：无漂移`530001..530040`、效应`540001..540008`、恢复`550001..550008`、相关结构`560001..560006`、性能`570001`；校准/开发使用互斥`510001..510004`与`520001..520004`。精确配置见`configs/p5_drift_statistical_validation.json`。
- 判定：中/大效应承担检出门，小效应只描述；运行级误报同时要求点估计≤0.05与Wilson 95%上界≤0.10；1秒是优化目标，30秒/1GiB才是工程硬门。最终验证出现后，不得修改配置、检测器或重跑相同种子以改善结果。
- 边界：本决策不改变冻结RC或P5检测算法，不产生正式工业有效性结论。

## D-101：P5漂移核心未通过完整统计门，不得接入正式RC（2026-11-22，LOCKED_RESULT）

- 判定：P5-1A完成48校准、48开发、666最终独立流和8核/4核资源测量；180项机器检查中36项门控失败，状态为`FAIL_STATISTICAL_GATES_STOP`。
- 通过边界：主无漂移运行级误报0/40且Wilson上界0.0876；中等均值、联合、渐进漂移recall 1.0；非法块maxT 18/18失败关闭；alpha无超支；128维单窗口约5.3—5.7秒且RSS增量约33—35MiB。
- 失败边界：中等方差、噪声与组组成检出未达0.80；异常值未确认但污染参考池；相关结构附加臂每格n=6无法把运行误报Wilson上界压到0.10且三个窗口FPR格超门；BY合法块过于保守，非法交换性fallback未进入冻结最终矩阵。
- 后果：不修改冻结RC，不接入Harness，不进入诊断或Qwen；等待人工审查。未来若批准修复，必须新建实验ID和全新最终种子，不能用本次最终结果调好后重报同一验证。

## D-102：P5-1A失败归并为四类代码/能力缺口与一类验证规模不足（2026-11-22，LOCKED_ANALYSIS）

- 根因：异常值参考污染来自“未检出漂移”被自动当作“可纳入参考池”；中等方差/噪声的主缺口是严格高维门下功效不足且最终收据缺少逐统计贡献；组组成场景缺少组身份接口；BY路径仍依赖合法块置换且2047次经验p分辨率不可能通过24—128维BY第一顺位门。
- 验证问题：相关结构每格只有6条独立流，0/6运行假警报的Wilson 95%上界仍为0.3903；至少35条独立流才能在零失败时把上界压到0.10。该部分不能写成已证明算法误报失控。
- 修复边界：P5-1A配置、结果和最终种子永久保留。任何后续修复必须先补诊断收据、分离参考纳入资格，再用全新开发种子竞争尺度候选；BY只校正已有有效边际p，无有效校准则失败关闭。相关结构确认使用至少35、建议40条新独立流。
- 状态：只读分析完成，修复实施尚未批准；不得自行修改源码、进入诊断归因/Qwen或接入正式RC。
- 依据：`designs/P5-1B-ROOT-CAUSE-2026-11-22/`四份文档及L-EVIDENCE-015。

## D-103：P5-1C保留最小可靠修复并拒绝负向尺度组合（2026-11-22，LOCKED_RESULT）

- 决策：保留显式非准入观察、五统计贡献收据、稀疏异常质量门、合法group/time hints和BY第一秩经验p分辨率失败关闭；这些能力在全新开发种子及698项回归中获得证据。它们仍只属于研究分支，不替换冻结`0.11.0rc1`。
- 负向决策：A2 Brown-Forsythe组合在全新种子上由A1的15/19下降为14/19，未改善噪声并使方差结果更差，故回退算法代码但保留全部负结果。不得因理论成熟度或个别样本表现绕过实测结果。
- 未解决边界：128维中等方差及三维噪声开发门仍失败；P5-1C每格只有4条开发流，不是独立最终统计验收。未解决前不得声称P5统计门通过或接入正式RC。
- 依据：`results/P5-1C-IMPLEMENTATION-REPORT.md`、`P5-1C-TARGETED-REPAIR.json`及D盘A1/A2原始收据。

## D-104：FINAL-SPRINT只接入可追溯诊断和证据引用（2026-11-23，LOCKED_IMPLEMENTATION）

- 决策：从P5-1C研究实现增量接入`DriftReport → DiagnosisReport → Qwen提案 → 轮收据`；诊断严格分为FACT、HYPOTHESIS和UNKNOWN，无同作用域指标证据时性能影响必须为`unknown`。`ArtifactSelector`、准入、训练和回滚不改。
- 证据引用：Qwen提案接口广告`evidence_refs`、预期影响和风险；引用不存在的fact/hypothesis ID时失败关闭到父兼容fallback。缺失引用不伪装成“已使用诊断”，但为保持已验证官方训练链不将其改写为不同Recipe；轮收据显式记录`validated_refs=[]`/`evidence_recipe_match=unverifiable`。
- 参考边界：最小运行链只使用已合法开放的历史轮次块，不以行号伪造group identity。前三个历史轮不足时返回`insufficient_history`；之后的maxT收据必须持续标注`round_blocks_assumed_exchangeable`，不得把假设写成官方已确认。
- 统计边界：D-101/D-103仍有效；尺度/噪声功效未通过，本接入不提升为完整统计验收或正式RC证据。
- 依据：`FINAL-SPRINT-003`用户授权；63项新增/受影响接口定向测试。

## D-105：FINAL-SPRINT-003性能冲刺运行边界（2026-11-23，LOCKED）

- 固定使用三个官方初始checkpoint作为起点，不替换基线。
- 新实验只读取各包`public/train.jsonl`并使用内部顺序/分组证据；禁止读取已封存或禁止的validation、XJTU和隐藏数据。
- 决策模型目标配置为远程`Qwen/Qwen3.8-27B`；本地工业训练按4核4GB验收。未产生真实27B收据前不得宣称其已经驱动实验。
- 先运行未执行过的成熟优化器有界矩阵，保留官方Adam和简单回放强对照；只将实测有效、父兼容且资源可接受的方法候选化。
- 论文复现不是硬门；性能、稳定性、恢复和资源证据优先。
## D-106：正式候选采用合同指标路由的三项稳定Recipe（2026-11-23，LOCKED_IMPLEMENTATION）

- 决策：分类合同使用`class_weighted_current_fast`作为预验证先验/服务降级；普通RMSE回归使用`regression_asymmetric_current_stable`；显式含NASA辅助指标的回归使用`averaged_current_stable`。路由只依赖任务与指标合同，不依赖Gas/Bearing/Engine名称。
- Agent边界：Qwen3.8-27B仍可从完整白名单提出其他合法Recipe；提示中明确给出train内部稳定先验。非法输出或服务失败时执行上述真实训练Recipe，平台不返回逐轮指标也不影响本地同作用域评估与确定性选择。
- 依据：`OFFICIAL-TASK-INTENSITY-001-A1`、`OFFICIAL-TASK-STABILITY-001-A1`多阶段收益；真实`QWEN38-RECIPE-PROBE-001-A2`三场景3/3选择一致；`FORMAL-STABLE-30R-001-A1`完成三任务30轮部署/保留/回滚复演。
- 边界：不修改冻结`0.11.0rc1`；新源码只有完成正式镜像白名单、4核4GB和材料绑定验收后才能形成替代RC。开发代理收益不是官方成绩。

## D-107：正式Agent读取最近三轮聚合实验结果，发布门只强制A/B/C（2026-11-24，LOCKED_IMPLEMENTATION）

- 决策：从持久化`round-ledger.json`向第一次Qwen调用提供最近三轮的Recipe、父/候选聚合指标、部署结果、失败、选择原因和候选墙钟；不提供样本、标签、原始特征或凭据。窗口固定三轮以控制上下文，并保留完整本地ledger供审计。
- 发布审计只把官方A/B/C各十轮作为本阶段硬门；旧`opaque-*`画像是团队额外压力测试，不是最新官方硬门，不再因缺失而把A/B/C候选误判为不合规。
- ArtifactSelector、训练、指标、回滚和D-104统计边界均不改变；本修改只补足真实历史反馈上下文与审计口径。
- 依据：用户最新锁定只针对三个官方任务；独立审计指出旧历史摘要只有计数、旧审计器把自定义opaque测试当官方门；新增/受影响测试41项及发布审计7项通过。

## D-108：多指标取舍由Qwen在Pareto非支配集合内决定（2026-11-24，LOCKED_IMPLEMENTATION）

- 决策：对同一合法验证作用域上的父模型、候选和合法历史，Harness先按任务合同的全部官方指标构造Pareto非支配集合。Qwen请求的artifact只要非支配且无硬失败即可采用；不再由主指标词典序自动覆盖MAE/RMSE或Accuracy/Macro-F1之间的真实取舍。
- 确定性边界：硬失败、指标非有限、验证作用域不一致、被另一artifact在全部声明指标上支配，或完全相同指标下消耗更多资源时，Harness必须覆盖Qwen请求。Qwen未给出合法选择时，才在非支配集合上使用合同主指标、辅助指标和资源的确定性回退。
- 禁止：不得自创官方未给出的指标加权总分、百分比改善门或事后平台分数；不同验证作用域不得比较。
- 依据：真实27B B单轮Smoke中候选RMSE改善但MAE恶化，Qwen请求保留父模型，旧选择器却按RMSE强制部署；A/C及既有错误部署反例仍要求支配/硬失败覆盖。Competition Core专项`119 passed`。

## D-109：正式提交区分Agent模型与工业checkpoint权重（2026-11-24，LOCKED_RELEASE）

- 决策：正式提交选择平台基础模型`Qwen/Qwen3.8-27B`作为Agent，不绑定未达到采用门或平台校验不稳定的持久化Sampler。PyTRiO只在镜像外验证/训练Agent并提供真实采样收据；正式平台运行由官方SDK的`rnd.model()`调用宿主模型服务。
- 工业模型边界：A/B/C每轮产出的`checkpoint.npz`必须从平台提供的父checkpoint在4核4GB CPU环境真实续训、评估并部署/保留/回滚；不得用PyTRiO训练工业模型，也不得从头训练另一模型替代父checkpoint。
- 记录边界：SwanLab记录工业模型训练、指标、资源、Token和选择的脱敏聚合；Sampler路径、API Key、逐样本数据和父/候选权重均不得写入公开记录或镜像。
- 依据：官方提交页同时提供“基础模型”和“持久化Sampler微调权重”两种模型类型；官方SDK 1.0.2要求模型调用经宿主`rnd.model()`，而工业产物继续遵守父checkpoint和`checkpoint.npz`协议。A7正式镜像与本地真实27B宿主复演验证了该职责分离。

## D-110：真实训练提案执行与Engine NASA合同属于发布硬门（2026-11-24，LOCKED_RELEASE)

- 决策：正式发布不得只统计模型调用次数和候选数量；每轮训练提案必须无解析错误、证据引用有效且实际进入Recipe执行。任何确定性fallback都必须在收据中显式记录，并使“完整双阶段Agent”发布门失败。
- Recipe契约：Qwen的`parameters`只允许覆盖`epochs`、`learning_rate_multiplier`、`parent_average_alpha`和`loss_parameters`。与注册Recipe完全一致的`loss/class_weighting/balanced_sampling`回显可安全剥离；任何实际机制改写继续失败关闭。
- 指标契约：Engine端到端发布验收必须使用`rmse_nasa`，同时产生MAE、RMSE和NASA指标并经过多指标选择路径；仅验证RMSE/MAE不足以晋级。
- 结果边界：A7因训练提案30/30 fallback和C缺NASA合同被否决；上述修复只有在新镜像A8真实27B Smoke、30轮、容器验收和独立终审全部通过后才能形成新正式候选。

## D-111：A9作为本地正式上传候选，证据复用限于字节级相同镜像（2026-11-24，LOCKED_RELEASE）

- 决策：A9 `0.12.7rc1`晋级为`LOCAL_RELEASE_READY`。正式上传归档为`D:/brace-msi-release/COMPETITION-CORE-RC-002-A9/harness.tar`，SHA-256 `f98cef296a69768018cfb840938f1acd89b49fd2044e72cd3cc4d968c135ba16`，运行内容绑定提交`fcb185e`。
- 证据复用：A9与完成真实27B 30轮的A8具有完全相同的镜像ID和白名单树；只允许在`evidence-reuse.json`同时绑定源acceptance哈希、源/目标镜像ID和内容树时复用运行证据。A9已单独重跑黑盒，禁止把此规则扩展到任何运行内容不同的镜像。
- 验收：真实27B提案30/30执行、C NASA合同10/10、4核4GB、父链、预测、回滚、重载、Docker归档和发布审计均PASS；SwanLab `elucs19m`由只读API确认30轮聚合曲线实存。独立终审结论PASS。
- 外部边界：本决策不代表平台已导入、模型校验已通过或取得官方成绩；这些结论只能来自实际平台回执。

## D-112：在已披露性能边界下先提交A9（2026-11-24，LOCKED_USER_RELEASE_CHOICE）

- 决策：用户在获知A9本地公开validation结果提升有限、协议验收十轮重复物化同一公开开发投影且不能作为性能模拟后，仍明确选择先采用A9。A9继续作为协议和工程候选提交，不把其本地指标改写为隐藏成绩或“每项提升10%”。
- 材料边界：提交材料必须同时保留A9的版本、镜像、源码、SwanLab和证据边界；不得删除B任务MAE退化、公开validation暴露或本地协议复演限制。PPT不进入本次总包。
- 镜像边界：用户提供的平台截图显示“镜像14”已可用；由于`harness.tar`超过50 MiB材料阈值，总材料ZIP只提供镜像14选择说明、精确归档哈希和本机路径，镜像仍在平台独立选择。不得把源码ZIP或材料ZIP冒充Docker归档。
- 依据：用户当前明确发布选择；D-111本地发布证据；材料表对模型配置、镜像、实验链接、运行说明、项目说明、源码和大小的要求。

## D-113：当前提交改为平台镜像14对应的0.10.6rc1（2026-11-24，LOCKED_USER_RELEASE_CHOICE）

- 决策：用户明确纠正D-112的实际提交对象，确认平台“镜像14”就是历史`brace-msi:0.10.6rc1`，当前材料必须严格以该镜像、源码提交`c653e0e`和O-PLATFORM-019试运行证据为准。D-113替代D-112作为当前发布选择，但不删除或改写A9历史。
- 版本绑定：Docker归档81,208,320字节、SHA-256 `F7518609974EAB3C156C07F6D0AA7CBFE6CF9253B43C5D20B3DC71B4C91D89CB`，镜像ID`sha256:52333ab152aa11a4a6b14a8270fcebe3e1e2290813f18ac77bf46e1810ca7504`，源码提交`c653e0e04297b655b93e28a90abd9f36e2ff761d`。
- 材料边界：镜像14材料不得引用A9新增功能、运行或SwanLab收据；官方试运行不写成正式成绩。Harness tar与作品材料ZIP分开交付，禁止把材料ZIP或源码ZIP冒充Docker归档。
- 依据：L-AUTH-020；历史release manifest与Docker归档哈希；O-PLATFORM-019原始报告。
