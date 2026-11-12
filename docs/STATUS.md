# 当前状态

- 最近同步：2026-11-12（Asia/Shanghai）
- 当前阶段：BRACE-MSI-0.2.0rc2本地Release与真实容器验收保持冻结；独立开展正式PyTRiO Sampler微调准备
- 当前路线：**Qwen3.5-4B PyTRiO Agent + BRACE确定性Harness + 官方A/B/C工业模型 + 经验证的开源优化方法** `[D-035]`
- 当前唯一任务：`PYTRIO-SFT-001`（`IN_PROGRESS`）；A3一次性合规语料已冻结并预注册，下一步执行36步有界SFT、新留出和真实A/B/C首轮动作验证。无论正负均按D-042停止继续调参。L-AUTH-011继续约束累计PyTRiO预算不超过10元。`FORMAL-RELEASE-001`仍为`BLOCKED_OFFICIAL_MATERIALS`。
- 稳定边界：`BRACE-MSI-0.1.0rc1`历史标签保持不变；当前冲刺候选为`BRACE-MSI-0.2.0rc2`，仍在`task/core-001`且不合并main
- 官方试运行：0次；不得用于基础调试

## 已确认

1. A/B/C官方训练包、真实初始检查点、公开切分、训练器和主指标已完成只读审计与本地续训验证 `[O-PLATFORM-005]`。
2. PyTRiO官方客户端支持Sampler推理、LoRA训练/持久化、环境变量鉴权和OpenAI兼容接口 `[O-PYTRIO-001]`。
3. 平台已校验通过Qwen3.5-4B基础模型；持久化Sampler先前失败源于权重未持久化，现已解决 `[B-PLATFORM-002]`。
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

## 当前执行入口

`SPRINT-HARNESS-001`与RC2本地发布均完成。最终Harness镜像归档为`D:/brace-msi-release/BRACE-MSI-0.2.0rc2/BRACE-MSI-0.2.0rc2-image-clean.tar`，SHA-256 `7b64490b...2e09327`；镜像保持冻结，不重训A/B/C。PyTRiO A1/A2证据目录均已锁定；当前从A2的持久化Sampler进入独立Harness对照，模型路径只从本地收据/运行时配置读取，不写入公开配置。

正式路线、已知能力与未知边界见[FORMAL_ROUTE.md](FORMAL_ROUTE.md)。实验必须遵守[EXPERIMENT_PROTOCOL.md](EXPERIMENT_PROTOCOL.md)。

## 外部阻塞

- 正式评测入口、挂载目录、批次事件和输出字段仍未知 `[H-001]`；只在适配器中保留配置点。
- 比赛环境实际Base URL、凭据注入、模型白名单与Token计量待核验 `[H-002]`。
- 完整评分公式与资源计量实现待发布 `[H-003]`。
- SwanLab比赛项目、必填字段及无公网同步责任待发布 `[H-004]`。
- Docker宿主机阻塞已解除；真实镜像、体积、禁入文件、非root身份、4核8GB断网Smoke和可重载`docker save`归档均有证据，见`results/RC2_CONTAINER_ACCEPTANCE.json`。

这些缺口不阻塞PyTRiO SFT。L-AUTH-011允许在累计10元内自动继续；每次仍使用新目录、固定预注册语料和本地Token收据，费用接近上限时停止。

## 禁止事项

- 不修改或覆盖官方训练包、原始数据、RC标签、历史成功或失败证据。
- 不把公开开发结果、代理结果或重复使用的验证集写成隐藏评测/官方成绩。
- 不把API Key、Sampler凭据、私有样本或可逆特征写入Git、公开日志或SwanLab。
- 不让大模型直接执行任意代码、绕过工具白名单、预算或SafetyGate。
- 不消耗官方十次试运行进行基础调试；不在最终模型冻结前生成正式SwanLab记录。
- 不再运行已停止的统一策略末期测试，不以新路线改写其负结果。
