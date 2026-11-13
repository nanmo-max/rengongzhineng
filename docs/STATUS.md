# 当前状态

- 最近同步：2026-11-13（Asia/Shanghai）
- 当前阶段：受控双闭环本地Release Candidate已冻结；既有`BRACE-MSI-0.4.1rc1`与全部历史实验继续保留，新候选`BRACE-MSI-0.5.0rc1`位于独立分支且尚未通过平台校验
- 当前路线：**Qwen3.5-4B基础模型受控建议 + BRACE确定性双闭环 + 四缓冲区物理隔离 + 官方A/B/C工业模型** `[D-050]` `[D-052]`
- 当前唯一任务：`FORMAL-RELEASE-001`（`BLOCKED_EXTERNAL`）；等待正式SDK字段、平台挂载/输出契约和平台校验。`DUAL-RC-001`已`DONE`：A安全保留父模型，B/C父模型集成、本地训练/预测、完整回归和容器验收完成。
- 稳定边界：`BRACE-MSI-0.1.0rc1`、`0.2.0rc2`、`0.3.0rc3`、`0.4.0rc1/rc2`与`0.4.1rc1`历史保持不变；新本地候选为`BRACE-MSI-0.5.0rc1`，位于`codex/generalist-q1-sprint`且不合并main。A3之后禁止继续LLM调参 `[D-043]`
- 官方试运行：已使用1/10次，剩余9/10次；该运行对应旧提交v2，不是RC4，正式评测仍为0/2 `[O-PLATFORM-006]`

## 已确认

0. `EVIDENCE-RSI-001`已完成：13张宣讲截图逐文件登记SHA-256，证据等级为宣讲材料；D-051/D-052锁定十批决策事务与受控双闭环语义，未把截图冒充正式SDK。
0a. 官方公告`O-PLATFORM-007`新增硬门：`docker save`归档、真实父检查点续训、独立预测入口、`checkpoint.npz`及模型产物总量不超过64 MiB；内部字段与挂载路径仍未知，不猜测。
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

新本地候选归档为`D:/brace-msi-release/BRACE-MSI-0.5.0rc1/BRACE-MSI-0.5.0rc1-image-clean.tar`，SHA-256 `e3cc5f1c3c2a879344632e083623001864c8dac380c6ebb87239ac5de9799747`。它尚未上传且未通过平台镜像、模型、续训或评测校验；原`0.4.1rc1`入口继续作为历史稳定归档，不被覆盖。机器证据见`docs/results/DUAL-RC-001.md`。

正式路线、已知能力与未知边界见[FORMAL_ROUTE.md](FORMAL_ROUTE.md)。实验必须遵守[EXPERIMENT_PROTOCOL.md](EXPERIMENT_PROTOCOL.md)。

提交材料入口见[SUBMISSION_CHECKLIST.md](SUBMISSION_CHECKLIST.md)。源码分支为`https://github.com/nanmo-max/rengongzhineng/tree/codex/paper-fusion-sprint`，SwanLab项目仍是RC3最终工程记录`https://swanlab.cn/@nanmo-max/brace-msi-final`；RC4的C融合容器证据保留在本地与Git聚合记录中，未冒充已同步SwanLab运行。

## 外部阻塞

- 正式评测入口、挂载目录、批次事件和输出字段仍未知 `[H-001]`；只在适配器中保留配置点。
- 比赛环境实际Base URL、凭据注入、模型白名单与Token计量待核验 `[H-002]`。
- 完整评分公式与资源计量实现待发布 `[H-003]`。
- SwanLab比赛项目、必填字段及无公网同步责任待发布 `[H-004]`。
- Docker宿主机阻塞已解除；RC4真实镜像、体积、禁入文件、非root身份、4核8GB断网冻结候选训练和可重载归档均有证据，见`results/RC4_CONTAINER_ACCEPTANCE.json`。

这些缺口不阻塞已授权的提交材料与`SWANLAB-FINAL-001`最终记录。A3是最后一次SFT，D-043禁止继续微调或扩大LLM搜索；最终记录只复用冻结Sampler和参数，不用于再选型。

## 禁止事项

- 不修改或覆盖官方训练包、原始数据、RC标签、历史成功或失败证据。
- 不把公开开发结果、代理结果或重复使用的验证集写成隐藏评测/官方成绩。
- 不把API Key、Sampler凭据、私有样本或可逆特征写入Git、公开日志或SwanLab。
- 不让大模型直接执行任意代码、绕过工具白名单、预算或SafetyGate。
- 不消耗官方十次试运行进行基础调试；不在最终模型冻结前生成正式SwanLab记录。
- 不再运行已停止的统一策略末期测试，不以新路线改写其负结果。
