# 当前状态

- 最近同步：2026-11-17（Asia/Shanghai）
- 当前阶段：第一性原理重建；最小正式运行核和白名单Docker已完成，进入父链兼容性能候选集成
- 当前路线：**官方SDK 1.0.2 + 每轮真实宿主模型调用 + 平台父checkpoint原生续训/retain + 最小白名单镜像** `[D-079]` `[D-080]` `[D-081]`
- 当前唯一核心任务：`FORMAL-PERF-001 (IN_PROGRESS)`；train内部A1矩阵完成并已集成，等待精确新镜像30轮验收后决定是否冻结。
- 稳定边界：全部历史RC和实验不改写；`0.5.0rc1`只作研究证据，不得上传。正式线从D-058开始只输出原生官方MLP续训checkpoint。A3之后禁止继续LLM调参 `[D-043]`
- 官方试运行：平台当前记录共4条（2成功、2失败），正式评测仍为0/2；剩余试运行次数以平台页面实时显示为准 `[O-PLATFORM-015]`

## 已确认

0. `EVIDENCE-RSI-001`已完成：13张宣讲截图逐文件登记SHA-256，证据等级为宣讲材料；D-051/D-052锁定十批决策事务与受控双闭环语义，未把截图冒充正式SDK。
0a. 官方公告`O-PLATFORM-007`新增硬门：`docker save`归档、真实父检查点续训、独立预测入口、`checkpoint.npz`及模型产物总量不超过64 MiB；内部字段与挂载路径仍未知，不猜测。
0b. 旧提交平台拒绝截图`O-PLATFORM-008`确认“另一套模型替代baseline”会被拒绝；该截图不是`0.5.0rc1`结果，但足以触发D-058将异构模型与正式提交线隔离。
0c. `FORMAL-CONTINUATION-RC-001`已完成：正式镜像禁用HGB/PaperFusion命令，A/B/C均以官方训练器完成十轮/3候选原生续训，三项机器复算有效；333项回归、4核8GB断网、独立预测、64 MiB与`docker save/load`门通过。
0d. `PLATFORM-NATIVE-001`已完成：`describe/start/submit`直接消费平台四挂载，不再要求完整包树；A/B/C在最终`0.6.0rc1`镜像中各完成10轮、10决策和10次真实候选，30轮父链、门控和独立预测全部通过。完整回归348项，镜像241,855,558字节，归档SHA-256 `F98FB679...CBC62D`。断网验收未冒充在线PyTRiO通过。
0e. `NATIVE-COMPETITIVE-RC-001` Task 2已完成：竞争模式允许真实retain，候选固定在第1/5/9轮；首轮可训练但因无历史证据不得部署，B/C高强度候选移至第5轮；小幅安全收益、辅助指标、Anchor和Replay风险按任务契约门控。专项32项和完整回归365项通过。DEV-A1/A2负结果保留，未读取公开validation。
0f. `PLATFORM-REPORT-SIM-001`已完成但经D-067降级：A/B/C均10/10轮，但V1逐轮重复公开validation并据此模拟选择第9/1/9轮，存在选择污染；只保留为界面演示，不是性能、泛化或有效选轮证据。
0g. `PYTRIO-ONLINE-001`已完成：Qwen3.5-4B基础模型在三个独立宿主进程中3/3返回严格合法非零Token结构化提案，累计1,103/581 Token，至少1次建议实际进入受控Harness；`0.7.1rc1`镜像内置固定哈希的tokenizer-only资产后，在4核8GB只读容器中不挂载宿主缓存也取得330/184 Token并执行候选。断网两次失败后只retain父模型。平台正式Token报告仍待试运行。
0h. `UNSEEN-SIM-001`已完成负结果：Battery/Hydraulic/Mill各10轮，A4调用Qwen3.5-4B PyTRiO取得16次有效响应、15次执行，协议/Agent门通过；但确认集严格改善0/3，最佳均为静态round 0。结果仅为模拟父模型本地压力测试，不是官方成绩。
0i. `UNSEEN-REPORT-001`已完成：单页HTML包含三任务摘要、最终确认指标、30轮模型选择和可展开实验记录；JSON提供同一机器字段。页面显著标注“本地独立确认集、非官方”，见`results/UNSEEN-REPORT-001.md`。
0j. `OFFICIAL-DATA-REPORT-001`已完成后经D-067降级：页面具备三任务30个展开记录，但继承V1的validation选择污染，只保留为样式演示；不得作为性能或泛化证据。修正版见下一条。
0k. `REPORT-EVIDENCE-FIX-001`已完成：确认旧V1没有训练数据直接泄漏证据，但逐轮重复公开validation并据此选轮次，属于选择污染。V1降级为界面演示；V2逐轮只展示Gate稳定/候选指标，冻结后每任务只评估最终checkpoint一次，不再含validation选轮字段。专项7项、完整回归390项通过，见`results/REPORT-EVIDENCE-FIX-001.md`。
0l. `OFFICIAL-FLOW-SIM-001`已完成：Gas按自然批次/时间、Bearing按寿命进度、Engine按完整unit构造十轮；每轮先预测封存再开放反馈，Prequential与候选Gate分离，未来轮和确认不提前物化。三任务10/10轮、父链与零交叉硬门通过；A/C保持静态，B一次部署后本地确认退化，作为负证据保留。完整回归399项，见`results/OFFICIAL-FLOW-SIM-001.md`。
0m. `DELAYED-GAIN-SIM-001`已完成混合结论：A/B/C各10轮，当前到达指标进入策略；仅在上一轮部署后于下一批对同样本运行直接前任影子模型并结算延迟收益。A2暴露B第9轮部署后第10轮延迟收益`-310.293697 RMSE`却继续保留坏模型，确认RMSE退化至`993.202677`；A3新增一轮可审计直接前任回滚后恢复至`241.980799`。A/C候选均被Gate拒绝并保持父模型。完整回归407项，见`results/DELAYED-GAIN-SIM-001.md`。
0n. `METHOD-PORTFOLIO-PILOT-001`已完成：不读取confirmation/public validation，在A/B/C各9个`t训练→t+1未见评价`上比较7种教师/基线和17种正式MLP候选，再对9种MLP recipe运行连续父链。A的近期窗口3轮、B的当前批3轮×3学习率、C的25%候选权重插值分别形成最强或最稳趋势；A3学习率累乘失败保留，A4修复后全链完成。证据见`results/METHOD-PORTFOLIO-PILOT-001.md`。
0o. `COMPETITIVE-POLICY-002`已完成：A1—A6筛选并淘汰B灾难性早触发；A5因报告ID失配判无效，最终A6严格隔离Gate。正式`start_round`十轮重放中A/B/C平均有向收益为`+0.319620` Macro-F1、`+21.850812`和`+0.438766` RMSE降低，确认/public validation读取0。`0.8.0rc1`完成421项回归、三任务4核8GB断网容器、PyTRiO失败retain、禁入扫描及`docker save/load`，见`results/COMPETITIVE-POLICY-002.md`。
0p. `PLATFORM-BRIDGE-001`已完成：`0.8.1rc1`显式校验平台顶层父哈希和期望轮次，部署/拒绝/retain均声明实际`checkpoint.npz`；54项平台专项、424项完整回归、官方A父链两轮、1,244条独立预测及`docker save/load`通过。平台旧草稿适配器无效，正式兼容性仍未判定，见`results/PLATFORM-BRIDGE-001.md`。
0q. `PLATFORM-PREFLIGHT-001`已完成：本机确认0.8.1默认`start`在空挂载裸启动时因`/workspace`权限退出1，而历史可运行镜像默认`--help`。0.8.2恢复安全默认命令，裸启动退出0；显式A父checkpoint `start`和1,244条独立`submit`仍通过。424项回归、禁入扫描、`pip check`及`docker save/load`通过；平台真实兼容仍未判定，见`results/PLATFORM-PREFLIGHT-001.md`。
0r. `PLATFORM-MODEL-TRANSPORT-001`已完成：平台反馈确认0.8.2只有PyTRiO私有Sampler路径，无法忠实绑定`workspace_io.model_transport`的Chat Completions协议。0.8.3将标准Chat Completions请求/解析和Token硬门纳入原生`start_round`，`start`强制调用平台模型传输；两次失败后retain且不训练。替身平台传输在4核8GB断网只读容器内实际收到调用并产生123/45 Token，官方A父checkpoint完成候选训练，`submit`输出1,244条预测；430项回归和`docker save/load`通过。平台真实服务仍待上传复验，见`results/PLATFORM-MODEL-TRANSPORT-001.md`。
0s. `O-PLATFORM-014`补齐正式SDK：协议为`contest.harness.workspace.v2`，模型经宿主`rnd.model()`/`rnd.transport()`调用，每轮必须提交真实`model_call_ids`；候选、状态、父产物和逐行预测均有明确契约。D-078据此替代D-077的正式接法；0.8.3保留历史但不再上传。官方SDK在Linux 4核8GB断网容器中15/15测试通过。
0t. `OFFICIAL-SDK-V2-001`本地完成：vendored官方SDK九个源文件逐哈希一致；正式镜像只含固定入口且未安装PyTRiO/SwanLab；A/B/C各10轮共30次宿主模型调用、候选/retain、父链/状态和15行预测通过；平台测量拒绝时状态链与公开收据同步保留父模型；完整回归435项。正式A4归档151,393,280字节，SHA-256 `dc0147706e5c20a62360bf309a280b890ac6cea2707eee4aa66f8f7169c57cbc`，见`results/OFFICIAL-SDK-V2-001.md`。
0u. `WORKSPACE-V2-INDEPENDENT-TEST-001`已完成：从A4归档删除原标签后重新加载全新独立标签，在全新状态目录以4核8GB断网容器完成A/B/C各10轮、30次宿主调用、2次候选提交和15行预测；官方风格HTML/JSON包含全部30轮并显著标注“本地协议模拟，不计正式成绩”。完整回归437项；见`results/WORKSPACE-V2-INDEPENDENT-TEST-001.md`。
1. `DUAL-DATA-001`已完成：四缓冲区、Gate一轮隔离、Update+Replay候选集合、只读manifest、训练/评估分离句柄和未来诱饵阻断通过4项专项测试；完整回归`275 passed`。
2. `DUAL-TXN-001`已完成：每批单决策、0至2候选、首候选结果触发升级、十批前缀、原子提交/恢复及影子配对收益通过5项专项测试；完整回归`280 passed`。
3. `DUAL-VALUE-001`已完成：每任务隔离统计、身份无关证据画像、弱先验、延迟收益专用更新和性能—CPU/RSS/Token/模型体积Pareto前沿通过5项专项测试；完整回归`285 passed`。
4. `DUAL-QWEN-001`已完成：五类证据触发、稳定轮零调用、一次重试、非法/异常收据和确定性恢复通过9项专项测试；完整回归`294 passed`，未调用真实服务。
5. `DUAL-PLUGIN-001`已完成：固定纯函数槽、AST白名单、独立子进程、CPU/RSS/超时、形状/有限值、重复确定性及差异测试通过13项攻击/契约测试；完整回归`307 passed`。
6. `DUAL-MODEL-001`已完成：Tier0/1能力门、四类CPU模型训练—保存—加载同预测、Tier2全条件准入、真实父检查点/父链、独立预测CLI和64 MiB产物门通过9项专项测试；完整回归`316 passed`。正式checkpoint字段仍待SDK映射。
7. `DUAL-INTEGRATION-001`已完成平台无关集成：分类/回归十轮、每批单事务、最多两候选、四缓冲区生命周期、门控、影子配对收益、审计、中断续跑和任务重命名不变性通过4项专项测试；完整回归`320 passed`。CLI产物显式标记合成且不可用于正式提交；尚未把本地SGD初始化冒充官方父检查点续训。
8. `DUAL-EXPERIMENT-001`完成混合结论：A1双闭环A/B/C为0.715596 Macro-F1、700.803581/53.155215 RMSE，暴露同批Gate通过但跨批遗忘；A2加入初始合法Replay、保守门控和影子负收益回滚后为0.714552、681.159833、52.378784，三项均不低于静态但增益不足。A2总摘要SHA-256为`62AD2DA12E3D7BC5F27A32827E572760CD4AFCD86313C171EB59647172436C68`；未调用PyTRiO、SwanLab或官方试运行。
9. `GENERALIST-MODEL-001-A1`按冻结协议只用train内部组折选择模型、再一次打开validation：A固定混合退化被拒；B选择HGB父集成，RMSE 675.010677、MAE 544.886250、NASA 3.5278e24；C选择HGB父集成，RMSE 49.336020、MAE 35.423070、NASA 2.4038e9。B/C接受，A保持父模型；三产物均远低于64 MiB，摘要SHA-256为`1CE6A72E272DD1426A0BB5FF468C303DBA050BA55001F5E37B70288253ABEB06`。

1. A/B/C官方训练包、真实初始检查点、公开切分、训练器和主指标已完成只读审计与本地续训验证 `[O-PLATFORM-005]`。
2. PyTRiO官方客户端支持Sampler推理、LoRA训练/持久化、环境变量鉴权和OpenAI兼容接口 `[O-PYTRIO-001]`。
3. 平台已校验通过Qwen3.5-4B基础模型；持久化Sampler在用户再次校验时仍失败，平台未给出足以定位具体根因的错误，当前正式路线使用基础模型 `[B-PLATFORM-003]` `[D-050]`。
4. 防泄漏状态机、预算、候选隔离、SafetyGate、回滚、恢复、本地审计及官方训练器子进程边界已有自动测试。
5. 统一策略开发搜索81/81已结束：复杂共享策略被简单触发策略支配。该负结果保留，但D-032/D-034已由D-035替代为历史路线，不执行其末期测试。
6. `PYTRIO-001`已完成：Qwen3.5-4B配置化Sampler、严格提案schema、秘密字段拒绝、Token/延迟收据和确定性降级通过8项专项测试；完整回归`189 passed`，未调用真实服务。
7. `OFFICIAL-HARNESS-002`已完成：同一CLI入口可选择PyTRiO或确定性提供者，A/B/C真实训练器集成Smoke各完成1个候选，3/3机器复算`valid=true`；全量回归`196 passed`。该Smoke只证明链路，公开验证改善不是新独立性能结论。
8. `ACTION-SANDBOX-001`已完成：执行侧使用可指纹化工具注册表，任务/参数/预算/输出路径均先检查；论文插件登记必须具备固定根、许可证和文件哈希。全量回归`201 passed`。
9. `PERF-A-001`已完成有界诊断：过采样实验为负；因果回放实验15候选中`current_only`通过开发选择，两种回放均未超过+0.005门。冻结确认上`current_only` Macro-F1均值0.469553，高于静态0.324722，但Batch 6—7历史暴露，不当作独立泛化证据。官方试运行/PyTRiO/SwanLab使用均0；全量回归`212 passed`。
10. 2026-11-12本机`trio login`成功；只读服务能力查询确认当前模型白名单为`Qwen/Qwen3.5-4B`与`Qwen/Qwen3.8-27B`。未读取、打印或提交真实API Key，用户粘贴的Key仅为官方示例占位内容。
11. `PYTRIO-SFT-001`本地准备完成：24训练/12留出，训练和留出archetype不交叉；assistant-only loss、预算安全率、持久化收据、逐样本Token/哈希、失败保留和预注册SHA fail-closed均有自动测试。该条的“远程调用0次”只属于A1启动前的历史状态，已由下一条真实A1证据取代。
12. `PYTRIO-SFT-001-A1`真实远程尝试失败并停止：基础模型12例严格schema有效率0，输入4,213 Token、输出2,425 Token；首个训练调用已返回，随后本地`TensorData`解析报`TypeError`，未生成Sampler。失败收据完整保留；已增加`TensorData.to_numpy()`兼容，专项20项及完整回归235项通过，A2未启动。
13. `PYTRIO-SFT-001-A2`完成18/18远程优化步，最终监督Token损失0.009076，并返回持久化`trio://` Sampler。PyTRiO文本保留Qwen `<|im_end|>`导致原始严格解析误记全0；该原始文件不修改。仅剥离精确终止标记后，同一Sampler在冻结12例留出上schema与预算安全率100%、action/tool/policy匹配率66.67%；完整回归236项通过。基础模型五项均为0。费用按公开单价和本地Token收据保守估算仍低于0.25元，实际以平台用量页为准。
14. `PYTRIO-HARNESS-001-A2`完成确定性/PyTRiO两臂×A/B/C完整10轮对照，六运行均`valid=true`且各3个真实候选。最终指标逐项相同；Sampler 30/30建议noop，9次最低候选由守卫覆盖，增加20,072/1,961 Token而无性能增益。负结果见`results/PYTRIO-HARNESS-001-A2.md`。
15. `PYTRIO-SFT-001-A3`完成36/36远程步骤，最终loss 0.017709；新留出schema/action/tool/budget/policy均100%，A/B/C真实首轮3/3主动提出并执行更新，0守卫覆盖。持久化Sampler路径只保存在Git外收据。
16. `PYTRIO-COMPETITIVE-001-A1`三任务各10轮/3候选，均`valid=true`、0守卫覆盖、0服务回退；A/B/C最终为0.725695 Macro-F1、637.180224 RMSE、51.635999 RMSE。性能来自冻结参数日程与门控，Agent贡献限于合规动作意图；2次预算耗尽后额外建议均在训练前拒绝。
17. `BRACE-MSI-0.3.0rc3`真实镜像为linux/amd64、240,579,085字节、UID10001，含PyTRiO0.2.9但无Torch、数据、权重或密钥；4核8GB断网双协议Smoke、`pip check`和`docker load`通过；最终代码回归246项、打包前干净环境回归243项通过。证据见`results/RC3_CONTAINER_ACCEPTANCE.json`。
18. `SWANLAB-FINAL-001`完成A/B/C各10轮/3候选且机器复算`valid=true`；公开项目`https://swanlab.cn/@nanmo-max/brace-msi-final`含三个`FINISHED`实验。GitHub`task/core-001`分支和RC3标签已推送，作品说明书DOCX/PDF已生成。证据见`results/SWANLAB-FINAL-001.md`。
19. `PAPER-FUSION-SPRINT-001`完成并停止：Gas蒸馏与Bearing融合未超过RC3，SafetyGate拒绝；Engine异构CPU融合公开验证RMSE为42.330230，相对RC3改善18.02%、相对初始公开基线改善19.93%。该验证集历史暴露，结果标记`PASS_WITH_EXPOSURE`，不是隐藏测试或官方成绩。
20. `BRACE-MSI-0.4.0rc1`镜像linux/amd64、240,701,023字节、UID10001；4核8GB断网Engine冻结候选训练、264项回归、`pip check`、禁入文件扫描和`docker load`通过。归档SHA-256为`97bb0a9fcfed688ba1b7feadadf09528e232fea578d06a1d782f2dccee306dfa`；证据见`results/RC4_CONTAINER_ACCEPTANCE.json`与`results/RC4_VERIFICATION.json`。
21. 官方首次试运行旧提交三任务均完成10轮但Token为0，A/B/C隐藏主指标为0.413368 Macro-F1、691.660970 RMSE、56.220512 RMSE；旧代码存在CLI默认确定性、客户端回退及Harness二次回退三条零Token完成路径。RC4尚未提交，不能据此评价RC4 `[O-PLATFORM-006]`。
22. `BRACE-MSI-0.4.0rc2`完成失败关闭修复：正式provider必须显式选择，PyTRiO正式模式要求持久化Sampler路径，传输/解析/Harness异常均失败关闭，SDK请求与重试受30秒默认预算约束。完整回归271项；4核8GB断网负向测试12.726秒退出且无运行文件；镜像归档SHA-256为`daf42786f73862214336154848782cffb9cb3468181959542d1687435e307d32`。
23. 基础模型兼容源代码已允许`provider=pytrio`且`model_path=None`，仍禁止provider隐式默认与正式静默回退；专项27项、完整回归271项通过。`PYTRIO-BASE-SMOKE-001`本机唯一在线调用约90秒无可核验响应后终止，无Token/响应收据，不能声称基础模型调用已在本机通过。
24. `BRACE-MSI-0.4.1rc1`镜像为linux/amd64、240,662,396字节、UID10001；4核8GB断网Smoke、`pip check`、禁入文件扫描、基础模型无Sampler路径失败关闭与`docker load`均通过。归档SHA-256为`63fff3634c9eacbe258a60e2847e585b4d5114238c5de98d8ee6dfed8454e48e`。
25. `BRACE-MSI-0.5.0rc1`本地验收完成：新增单包train-only通用训练入口和独立预测入口；329项回归通过；linux/amd64镜像241,051,292字节、UID10001、无数据/权重/密钥；4核8GB断网十轮Smoke、B/C完整训练与独立预测通过。运行时B/C产物239,914/200,616字节并实际嵌入父checkpoint；归档由`docker save`生成、删除标签后`docker load`成功，SHA-256为`e3cc5f1c3c2a879344632e083623001864c8dac380c6ebb87239ac5de9799747`。A保持父模型，未声称严格提升；平台各状态均未验证。

## 当前执行入口

首个第一性原理协议候选为`D:/brace-msi-first-principles-release/BRACE-MSI-0.10.0rc1-FINAL-PROVENANCE-OFF/harness.tar`，81,201,152字节，SHA-256 `DC73FAFC73906D1A841BE3AC47DBCBF3A69915C380711B07E28A2C5C0C05C39E`。它已通过本地协议与容器门，但在`FORMAL-PERF-001`完成前仅作为可恢复协议RC，不上传消耗试运行。`0.9.0rc1`及更早归档不得再次上传。

正式路线、已知能力与未知边界见[FORMAL_ROUTE.md](FORMAL_ROUTE.md)。实验必须遵守[EXPERIMENT_PROTOCOL.md](EXPERIMENT_PROTOCOL.md)。

提交材料入口见[SUBMISSION_CHECKLIST.md](SUBMISSION_CHECKLIST.md)。源码入口为`https://github.com/nanmo-max/rengongzhineng/tree/codex/native-competitive-rc`；公开训练记录为`https://swanlab.cn/@nanmo-max/brace-msi-platform-native`。0.8.3只修复模型传输边界，没有重新训练A/B/C，不伪造新的训练记录。

## 外部阻塞

- 正式评测入口、挂载目录、批次事件和输出字段仍未知 `[H-001]`；只在适配器中保留配置点。
- 比赛环境实际Base URL、凭据注入、模型白名单与Token计量待核验 `[H-002]`。
- 完整评分公式与资源计量实现待发布 `[H-003]`。
- SwanLab比赛项目、必填字段及无公网同步责任待发布 `[H-004]`。
- Docker宿主机阻塞已解除；0.5.0rc1真实镜像、体积、禁入文件、非root身份、4核8GB断网训练/预测和可重载归档均有证据，见`results/DUAL_RC_CONTAINER_ACCEPTANCE.json`。

这些缺口不阻塞已授权的提交材料与`SWANLAB-FINAL-001`最终记录。A3是最后一次SFT，D-043禁止继续微调或扩大LLM搜索；最终记录只复用冻结Sampler和参数，不用于再选型。

## 禁止事项

- 不修改或覆盖官方训练包、原始数据、RC标签、历史成功或失败证据。
- 不把公开开发结果、代理结果或重复使用的验证集写成隐藏评测/官方成绩。
- 不把API Key、Sampler凭据、私有样本或可逆特征写入Git、公开日志或SwanLab。
- 不让大模型直接执行任意代码、绕过工具白名单、预算或SafetyGate。
- 不消耗官方十次试运行进行基础调试；不在最终模型冻结前生成正式SwanLab记录。
- 不再运行已停止的统一策略末期测试，不以新路线改写其负结果。
