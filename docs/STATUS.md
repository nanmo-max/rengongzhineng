# 当前状态

- 最近同步：2026-11-13（Asia/Shanghai）
- 当前阶段：持久化Sampler重复平台校验失败后，按`D-050`切换为平台已接受的Qwen3.5-4B基础模型；`BRACE-MSI-0.4.1rc1`已完成本地候选验收，旧RC与证据保持冻结
- 当前路线：**Qwen3.5-4B PyTRiO Agent + BRACE确定性Harness + 官方A/B/C工业模型 + 经验证的开源优化方法** `[D-035]`
- 当前唯一任务：`FORMAL-RELEASE-001`（`BLOCKED_EXTERNAL`）；基础模型兼容镜像已就绪，等待用户执行平台上传/校验。任何新试运行前必须核对基础模型、镜像、源码和非零Agent调用门槛。
- 稳定边界：`BRACE-MSI-0.1.0rc1`、`0.2.0rc2`、`0.3.0rc3`历史保持不变；当前候选为`BRACE-MSI-0.4.0rc1`，位于`codex/paper-fusion-sprint`且不合并main。A3之后禁止继续LLM调参 `[D-043]`
- 官方试运行：已使用1/10次，剩余9/10次；该运行对应旧提交v2，不是RC4，正式评测仍为0/2 `[O-PLATFORM-006]`

## 已确认

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

## 当前执行入口

下一次基础模型上传入口为`D:/brace-msi-release/BRACE-MSI-0.4.1rc1/BRACE-MSI-0.4.1rc1-image-clean.tar`，SHA-256 `63fff3634c9eacbe258a60e2847e585b4d5114238c5de98d8ee6dfed8454e48e`。不要把只接受Sampler路径的`0.4.0rc2`用于基础模型提交。RC4/RC5归档与哈希保持冻结历史；平台上传、校验和试运行尚未执行。

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
