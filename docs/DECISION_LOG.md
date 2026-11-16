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

## 已被替代的历史决策

- 早期草稿中的“稳定跑完 > 演示效果 > 客观性能”顺序已被D-001方案替代。当前顺序为：硬性资格、超过静态基线、单位资源收益、可复现审计、答辩展示、额外创新。
- 早期草稿把11月16日作为主要节点。当前按H-005处理，并以11月13日作为内部最早风险节点，等待学校正式通知。
- 早期单一MLP/微调路线已被D-002、D-003和D-009替代。
- D-032的三任务同参身份盲策略及D-034的简单统一候选已被D-035替代为历史研究证据；其81作业和负结果保留，不打开末期数据。
