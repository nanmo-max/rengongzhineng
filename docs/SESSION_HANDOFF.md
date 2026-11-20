# 新会话恢复与交接

## 2026-11-20 一次性泛化验收后的当前恢复入口

1. 当前分支`codex/first-principles-rebuild`；`FINAL-GENERALIZATION-VALIDATION-001`以协议无效且数值门失败结束，没有新的本地READY任务。
2. XJTU密封摘要位于`D:/brace-msi-final/FINAL-GENERALIZATION-VALIDATION-001-A1/summary.json`，SHA-256 `22D4143B...38AA05`。密封RMSE/MAE改善，但开发最差阶段`-99.61%`，且A1延迟收益复用当前Gate、峰值RSS/恢复未验证。
3. 密封组已经打开，禁止用其结果调整阈值、recipe、模型结构或重跑；A4分类复合方法仍没有新的真实独立分类证明。
4. 保持历史Protocol RC冻结；`FORMAL-RC-NEXT-001`继续`BLOCKED_BY_LOCAL_GATES`。只有新的未暴露数据或官方材料才能创建下一性能任务。
5. 镜像外Advisor与SwanLab证据不变：公开运行`https://swanlab.cn/@nanmo-max/BRACE-MSI/runs/k4jvqkuj`，Sampler未通过提交页校验前不得声称正式采用。

## 2026-11-20 Advisor完成后的历史恢复入口

1. 当前分支`codex/first-principles-rebuild`；选择可靠性、A6开发策略、A4原生方法和镜像外Advisor均已收口。当前唯一READY任务是`FINAL-GENERALIZATION-VALIDATION-001`。
2. 冻结开发候选：A6 `bounded_exploration` + A4分类`balanced_current_e3/native_recent_e3`；回归保持A6原生recipe。它们仍不是正式RC，必须通过D-088一次性独立替代流/任务留出。
3. Advisor结果见`results/PYTRIO-ADVISOR-OPT-001.md`。新Sampler镜像外留出与重载四项100%，SwanLab运行`https://swanlab.cn/@nanmo-max/BRACE-MSI/runs/k4jvqkuj`；平台提交页未校验前不得声称正式采用，Sampler路径不得写入Git或镜像。
4. 不再重跑Advisor语料、增加epoch或做LLM HPO；不读取已暴露公开confirmation。独立留出一旦打开，禁止根据结果调阈值/方法。
5. 历史Protocol RC `0.10.6rc1`和归档保持冻结；未获用户单独上传授权前不得消耗官方次数。

## 2026-11-19 D-086双阶段Qwen正式候选恢复入口（当前）

1. 当前分支为`codex/first-principles-rebuild`；先读`STATUS.md`、`TASKS.md`、D-085/D-086、O-PLATFORM-018和`results/FORMAL-EVERY-ROUND-TRAIN-001.md`。
2. 正式语义：每轮Qwen先选择受控recipe，Harness真实续训并本地评估，Qwen再根据父/候选主辅指标、资源和历史决定deploy/retain/rollback；SafetyGate只管硬约束。平台逐轮指标不参与训练或部署。
3. 本地候选为`0.10.6rc1`；A/B/C共30轮、60次宿主调用、30个候选，平台指标30/30为空，Qwen本地部署4次、回滚26次，硬安全失败0。
4. 唯一可考虑上传的归档为`D:/brace-msi-first-principles-release/BRACE-MSI-0.10.6rc1-A1/harness.tar`，81,208,320字节，SHA-256 `F7518609974EAB3C156C07F6D0AA7CBFE6CF9253B43C5D20B3DC71B4C91D89CB`。旧0.10.4及A1/A2无效产物不得上传代替。
5. 当前唯一任务为`FORMAL-RELEASE-001 (BLOCKED_EXTERNAL)`。只有用户明确决定消耗平台次数后才能上传并进行一次受控试运行；需核对每轮两个真实call ID、非零Token、30个候选、部署/回滚收据和14,773条预测。
6. 已暴露公开validation的A/B/C描述性结果只用于诊断，不得称为独立或隐藏成绩。SwanLab、源码与作品材料必须在正式平台运行后绑定同一提交、镜像哈希和真实记录。

## 2026-11-17 第一性原理重建恢复入口（历史）

1. 当前分支为`codex/first-principles-rebuild`；先读`STATUS.md`、`TASKS.md`、D-079至D-084和`results/FORMAL-AGENT-OUTPUT-001.md`。不要上传`0.10.4rc1`、`0.10.3rc1`或更早归档。
2. 第一性原理本地重建已完成：正式入口为`submission/contest_submission.py → brace_formal.submission`；每轮在任何retain/train分支前直接调用官方`rnd.model()`，最多一个父链兼容候选，train内部portfolio可否决无证据的训练。
3. O-PLATFORM-017已证明正式宿主调用和Token计量有效，但0.10.3的30轮提案全因固定256上限/格式契约失效。D-084禁止参赛者自设Token上限；模型只输出train/retain，执行参数由确定性portfolio控制。
4. 当前正式候选归档为`D:/brace-msi-first-principles-release/BRACE-MSI-0.10.4rc2-A1/harness.tar`，81,206,784字节，SHA-256 `97948BD45502CFFE6082184DB06799A8E0FD8BE6BB008C048C7CE9DE47B335EA`。`0.10.4rc1`含被否决的1024上限且验收中止，禁止上传。
5. 最终本地证据为469项完整回归和精确0.10.4rc2容器A/B/C各10轮：30调用、候选1/0/3、父链/状态链与15行预测有效；镜像白名单、依赖和重载同ID通过。
6. 对应源码提交为`80537a0`。当前唯一任务为`FORMAL-RELEASE-001 (BLOCKED_EXTERNAL)`。只有用户明确决定消耗平台次数后，才上传精确归档并进行一次受控试运行；重点核对30轮不再全部`host proposal was invalid`、至少产生真实候选、Token和预测完整。SwanLab/源码/材料必须引用最终平台运行与同一提交，不得用本地模拟冒充。

## 2026-11-17 0.9.0rc1官方Workspace V2恢复入口（历史）

1. `OFFICIAL-SDK-V2-001`已完成全部本地门；当前唯一核心任务为`FORMAL-RELEASE-001 (BLOCKED_EXTERNAL)`。不要重跑性能搜索、公开validation或A/B/C宿主协议复演。
2. 正式协议为官方`contest_harness` 1.0.2：`python3 /app/harness.py describe|train|predict`。模型只经宿主`rnd.model()`调用，完成记录必须引用本轮`model_call_ids`；0.8.3猜测式桥接已废止。
3. 唯一上传归档为`D:/brace-msi-workspace-v2/BRACE-MSI-0.9.0rc1-A4/brace-msi-0.9.0rc1-harness.tar`，151,393,280字节，SHA-256 `dc0147706e5c20a62360bf309a280b890ac6cea2707eee4aa66f8f7169c57cbc`。A1/A2/A3和更早归档不得上传代替。
4. 本地证据：官方上游15项、项目435项回归；A/B/C各10轮共30次宿主模型调用、候选/retain、状态/父链及15行预测；平台测量拒绝时状态链和公开收据同步回退父模型；镜像linux/amd64、UID10001、无PyTRiO/SwanLab安装及禁入文件；`docker save/load`通过。详见`results/OFFICIAL-SDK-V2-001.md`。
5. 用户授权的独立模拟已完成；机器结果与官方风格HTML/JSON位于`D:/brace-msi-workspace-v2/WORKSPACE-V2-INDEPENDENT-TEST-001-A1/`，30/30轮、30次本地宿主调用、15行预测，明确为非官方成绩。不要重复该模拟或用报告数值代替隐藏评测。
6. 下一步由用户上传A4，等待“镜像可用”后只发起一次受控试运行；核对平台非零Token、30轮父链、候选/retain、逐行预测和报告。任何失败先保存原始文本/截图并登记，不盲目重试。SwanLab链接为`https://swanlab.cn/@nanmo-max/brace-msi-platform-native`，源码分支为`https://github.com/nanmo-max/rengongzhineng/tree/codex/native-competitive-rc`。

## 2026-11-16 0.8.3rc1平台模型传输恢复入口（历史）

1. `PLATFORM-MODEL-TRANSPORT-001`已本地完成；当前唯一核心任务为`FORMAL-RELEASE-001 (BLOCKED_EXTERNAL)`。不要重跑A1—A6或重新读取暴露确认集。
2. 平台原始失败`O-PLATFORM-013`指出0.8.2的PyTRiO私有Sampler无法忠实绑定`workspace_io.model_transport`。0.8.3将标准Chat Completions语义纳入原生入口，平台模式强制模型调用，失败后retain且不训练。
3. 当前上传归档为`D:/brace-msi-platform-bridge/BRACE-MSI-0.8.3rc1/brace-msi-0.8.3rc1-harness.tar`，SHA-256 `4BE4327D29B8D25A2480427776AC58696FB6A48EA63AB576C35944240EA3A694`。0.8.2及更早版本不得上传代替。
4. 本地证据：430项回归；4核8GB、断网、只读根、非root容器中替身平台传输实际产生123/45 Token并完成官方A候选训练；独立预测1,244条；`pip check`、禁入扫描及`docker save/load`通过。这不是平台真实兼容通过。
5. 下一步仅上传0.8.3并保存平台原始结果；若仍失败，先登记新错误，不盲目消耗试运行。训练记录链接为`https://swanlab.cn/@nanmo-max/brace-msi-platform-native`，源码分支为`https://github.com/nanmo-max/rengongzhineng/tree/codex/native-competitive-rc`。

## 2026-11-16 0.8.2rc1空挂载预检恢复入口（历史）

1. `PLATFORM-PREFLIGHT-001`已本地完成；当前唯一核心任务仍为`FORMAL-RELEASE-001 (BLOCKED_EXTERNAL)`。不要重跑A1—A6，不读取已第5次暴露的confirmation/public validation。
2. 运行时补丁提交为`8566807`；结果入口为`docs/results/PLATFORM-PREFLIGHT-001.md`。0.8.1裸启动在空挂载时复现`PermissionError: /workspace`/退出1；0.8.2默认`--help`退出0。
3. 当时上传归档为`D:/brace-msi-platform-bridge/BRACE-MSI-0.8.2rc1/brace-msi-0.8.2rc1-harness.tar`，SHA-256 `7CA09B029946E8D5B94BEFA8A53EDEFC0DF168051750FA0D4CB8C3FFBBE7784F`；现已由本文件顶部0.8.3入口替代。
4. `0.8.2rc1`已通过424项完整回归、空挂载退出0、官方A父checkpoint显式start、1,244条独立submit、4核8GB只读断网、禁入扫描、`pip check`及`docker save/load`；这些是本地证据，不是官方兼容判定。
5. 下一动作只能是平台重新上传/导入/校验；若进入真实试运行，必须核对十轮父链、模型产物、非零PyTRiO Token及独立预测。新的平台原始错误先登记SOURCE_REGISTRY，再决定是否修改。

## 2026-11-16 0.8.1rc1平台桥接恢复入口（历史）

1. `PLATFORM-BRIDGE-001`已本地完成；当前唯一核心任务为`FORMAL-RELEASE-001 (BLOCKED_EXTERNAL)`。不要重跑A1—A6，不读取已第5次暴露的confirmation/public validation。
2. 当前运行时代码提交为`e3b00d1`；桥接结果入口为`docs/results/PLATFORM-BRIDGE-001.md`，性能结果仍引用`docs/results/COMPETITIVE-POLICY-002.md`。
3. 最终A6经平台原生`start_round`十轮重放：A/B/C平均有向收益`+0.319620` Macro-F1、`+21.850812`和`+0.438766` RMSE降低；A3灾难性提前策略与A5无效ID证据均保留。
4. 当时上传归档为`D:/brace-msi-platform-bridge/BRACE-MSI-0.8.1rc1/brace-msi-0.8.1rc1-harness.tar`，SHA-256 `9B1A1822E9062229CF940D0CF9FDBD7D33F1301A94A993FE111B56E36184ED7E`；现已由本文件顶部0.8.2入口替代。
5. `0.8.1rc1`已通过54项平台专项、424项完整回归、官方A父链两轮、4核8GB只读断网、retain产物声明、1,244条独立预测、禁入扫描、`pip check`与`docker save/load`；这些是本地工程证据，不是官方兼容判定或隐藏成绩。
6. 平台旧草稿适配器被判有缺陷；平台侧需用无mode argv prefix重写薄桥接器，并映射顶层父哈希、轮次、空输出挂载和模型产物声明。恢复后只处理新的平台桥接/导入/在线Token/SwanLab正式规范或官方评测证据。

## 2026-11-16序贯延迟收益模拟恢复入口（当前）

1. `DELAYED-GAIN-SIM-001`已`DONE_MIXED`，当前唯一任务回到`FORMAL-RELEASE-001 (BLOCKED_EXTERNAL)`。不要重复Smoke/A2/A3或再次使用本地确认调参。
2. A3产物位于`D:/brace-msi-delayed-gain/DELAYED-GAIN-SIM-001-A3/`；易读报告在`report/official-flow-report.html`，机器JSON同目录。正式隐藏测试未开始，确认已经是第5次历史暴露。
3. 序贯语义为：稳定模型先预测到达批次，标签开放后到达指标进入策略，候选Gate决定部署，下一批才以直接前任同样本配对结算上一轮收益。B在A3第10轮因`-310.293697`延迟收益回滚直接前任，避免A2的RMSE 993.202677退化。
4. A3最终本地确认：A Macro-F1 0.380649，B RMSE 241.980799，C RMSE 48.691951。A/C无候选部署，不得声称三任务性能提升；这些也不是官方成绩。
5. SwanLab仅有A3本地离线聚合目录，未公开同步；PyTRiO本轮Token为0，在线能力继续引用独立`PYTRIO-ONLINE-001`，不要为了重复证明接口消费余额。
6. 当前HEAD完整回归407项通过。恢复后先读`results/DELAYED-GAIN-SIM-001.md`；只有正式平台生命周期、SDK或新官方数据证据才能创建下一项READY任务。

## 2026-11-15官方生命周期模拟恢复入口（当前）

1. `OFFICIAL-FLOW-SIM-001`已完成，当前无本地`READY`任务；唯一核心任务回到`FORMAL-RELEASE-001 (BLOCKED_EXTERNAL)`。不要重复A1/A2或再次读取本地确认集调参。
2. 新正式本地复演入口为`scripts/run_official_flow_simulation.py`和`src/brace_msi/official_flow_simulation.py`；旧`platform_simulation.py`按行均切入口仅用于历史RC复现，机器摘要明确标记`not_official_flow`。
3. A2产物位于`D:/brace-msi-official-flow/OFFICIAL-FLOW-SIM-001-A2/`；官方要素报告为`report/official-flow-report.html`与JSON。正式隐藏测试尚未开始，报告不可作为官方成绩。
4. A2三任务10/10轮、父链有效，候选/采用为A 3/0、B 10/1、C 3/0；B本地确认显著退化，属于负证据。A1已经先打开确认，A2为第2次历史暴露，禁止反向修改策略。
5. PyTRiO在线有效性继续引用`PYTRIO-ONLINE-001`；A2本身Token为0。新脚本支持`--advisor pytrio`，但没有必要为接口证明重复消耗余额。A2 SwanLab仅离线聚合，未同步公网。
6. 当前HEAD完整回归为399项通过。恢复后先读`results/OFFICIAL-FLOW-SIM-001.md`，不得把协议通过提升为性能或隐藏泛化通过。

## 2026-11-15未知任务复演后恢复入口（当前）

1. `PYTRIO-ONLINE-001`、`UNSEEN-SIM-001`、`UNSEEN-REPORT-001`、`OFFICIAL-DATA-REPORT-001`和`REPORT-EVIDENCE-FIX-001`均已结束；当前唯一核心任务为`FORMAL-RELEASE-001 (BLOCKED_EXTERNAL)`。不要重跑A3/A4、Gas/Bearing/Engine或使用已经打开的validation/confirmation调参。
2. A4确实调用`Qwen/Qwen3.5-4B` PyTRiO：16次有效响应、15次建议执行、8,100/3,470输入/输出Token；协议和Agent门通过，但Battery/Hydraulic退化、Mill持平，严格改善0/3。证据见`docs/results/UNSEEN-SIM-001.md`。
3. `0.7.1rc1`本地发布验收已完成：内置固定哈希tokenizer-only资产、容器真实PyTRiO 330/184 Token、断网retain、383项回归、禁入扫描及`docker save/load`通过。正式上传归档为`D:/brace-msi-native-competitive/RC71-CONTAINER-ACCEPTANCE-FINAL/brace-msi-0.7.1rc1-harness.tar`，SHA-256 `6BA798571F88CC88A6FB298FA63E99CE723DFCC057A3BDEB9EF103E69DCF3CFE`。
4. 下一动作只允许由用户执行平台上传/校验/正式试运行，或在获得新的官方接口证据后登记接入任务。平台试运行前继续核对非零Token、父链、独立预测和64 MiB；不得再训练Qwen或重开工业模型参数。
5. 官方要素风格的本地报告已生成于`D:/brace-msi-unseen/UNSEEN-SIM-001-A4/platform-style-report.html`，机器JSON同目录；只用于查看A4本地证据，不得作为隐藏成绩提交。生成器与哈希见`docs/results/UNSEEN-REPORT-001.md`。
6. Gas/Bearing/Engine修正版V2报告位于`D:/brace-msi-native-competitive/RC7-OFFICIAL-REPORT-SIM-V2-A2/platform-style/platform-style-report.html`，机器JSON同目录；逐轮只展示Gate指标，公开validation在冻结后每任务读取一次且不参与选轮。旧V1存在validation选择污染，只保留界面演示。证据见`docs/results/REPORT-EVIDENCE-FIX-001.md`。

## 2026-11-15原生竞争RC恢复入口（历史上传基线）

1. `NATIVE-COMPETITIVE-RC-001`已完成全部本地工作，当前唯一任务为`FORMAL-RELEASE-001 (BLOCKED_EXTERNAL)`；不要重复三任务30轮、重新打开公开validation或继续LLM调参。
2. 当前正式上传归档为`D:/brace-msi-native-competitive/RC7-CONTAINER-ACCEPTANCE-FINAL/brace-msi-0.7.0rc1-harness.tar`，SHA-256 `B4EF8820FE38B4479B16657A85594719EB86CA7BAD157C0B484DDF4715FB1BD7`。旧0.5.x/0.6.0不得上传代替。
3. 原生入口为`describe/start/submit`，直接消费`/data`、`/previous/checkpoint.npz`、`/workspace`和`/output`；旧整包审计入口继续保留作研发证据，不是平台前置。
4. 最终镜像A/B/C各完成10轮，候选3/10/3、部署1/1/1并通过独立预测；完整回归377项。PyTRiO训练意图不能越过冻结轮次、动作或参数。证据见`docs/results/NATIVE-COMPETITIVE-RC-001-RELEASE.md`和`D:/brace-msi-native-competitive/RC7-CONTAINER-ACCEPTANCE-FINAL/`。
5. 断网默认PyTRiO测试明确两次失败后`noop/retain`、Token为0且不静默训练；在线仅有2次非零响应/1次建议执行。下一次平台试运行必须核对非零Token、advisor收据、30轮父链和独立预测，不能把本地接口测试写成在线成功。
6. 平台精确启动命令、凭据注入、镜像导入和模型校验仍是外部阻塞；获得材料后先登记`SOURCE_REGISTRY.md`再追加决策。

## 2026-11-13受控双闭环重构恢复入口（历史）

> 历史更新：O-PLATFORM-008记录旧提交被平台以“未基于baseline/父检查点真实续训”拒绝，随后形成`0.5.1rc1`。该入口已被本文件顶部的`0.7.0rc1`原生竞争RC恢复入口替代；此段只保留追溯。

1. 当前路线以D-051/D-052/D-057及`docs/superpowers/specs/2026-11-13-controlled-dual-loop-design.md`为准；既有`0.4.1rc1`与历史实验冻结，不得改写。
2. `GENERALIST-MODEL-001`与`DUAL-RC-001`已`DONE`：A保留父模型，B/C冻结固定HGB父集成；禁止重开validation调权重。当前唯一任务为`FORMAL-RELEASE-001 (BLOCKED_EXTERNAL)`。
3. 宣讲截图证据登记见`B-RSI-002`和`source_notes/RSI_LECTURE_EVIDENCE_2026-11-13.md`；它们不提供正式SDK字段。
4. 不消耗官方剩余9次试运行；`BRACE-MSI-0.5.0rc1`归档位于`D:/brace-msi-release/BRACE-MSI-0.5.0rc1/BRACE-MSI-0.5.0rc1-image-clean.tar`，SHA-256为`e3cc5f1c3c2a879344632e083623001864c8dac380c6ebb87239ac5de9799747`。本地Docker通过不等于平台镜像/模型/续训/评测通过；真实SDK字段仍等待H-001。
5. 每完成一个任务运行专项与完整回归，更新SSOT并提交；外部SDK阻塞不得阻止平台无关核心实现。
6. 新增`O-PLATFORM-007`/D-053：模型门必须验证真实父检查点续训、独立预测入口、`checkpoint.npz`和64 MiB总产物；RC归档必须由`docker save`生成并可重载。未知字段继续阻塞，不得猜测。

## 2026-11-13首次平台试运行诊断与修复恢复入口（当前）

0. 最新变更：平台持久化Sampler再次校验失败而基础模型通过，D-050将正式模型来源切回`Qwen/Qwen3.5-4B`基础模型。`0.4.1rc1`专项27项、全量271项和容器验收通过；上传入口为`D:/brace-msi-release/BRACE-MSI-0.4.1rc1/BRACE-MSI-0.4.1rc1-image-clean.tar`，SHA-256 `63fff3634c9eacbe258a60e2847e585b4d5114238c5de98d8ee6dfed8454e48e`。
1. 官方平台已消耗1/10次试运行；旧提交v2的报告Token为0，A/B/C隐藏主指标分别为0.413368 Macro-F1、691.660970 RMSE、56.220512 RMSE。证据见O-PLATFORM-006和`docs/source_notes/PLATFORM_TRIAL_V1_2026-11-13.md`。
2. 用户明确确认`BRACE-MSI-0.4.0rc1`尚未提交；不得把旧试运行归因于RC4，也不得再次上传旧镜像。
3. `RC5-FAILCLOSED-001`已`DONE`：完整回归271项；linux/amd64镜像在4核8GB断网下通过Smoke，严格PyTRiO负向测试12.726秒失败关闭且运行文件0项。
4. 下一上传入口为`D:/brace-msi-release/BRACE-MSI-0.4.0rc2/BRACE-MSI-0.4.0rc2-image-clean.tar`，SHA-256 `daf42786f73862214336154848782cffb9cb3468181959542d1687435e307d32`。RC4归档和哈希保持冻结历史。
5. 当前唯一任务为`FORMAL-RELEASE-001 (BLOCKED_EXTERNAL)`；本地基础模型镜像已完成，由用户执行平台上传/校验。`PYTRIO-BASE-SMOKE-001`唯一在线尝试约90秒无收据后已停止；不得写成成功。新试运行必须确认基础模型、镜像和源码绑定，并以非零Agent调用收据为准入门槛。

## 2026-11-13论文融合RC4恢复入口（历史）

1. 当前分支为`codex/paper-fusion-sprint`，RC3标签、`task/core-001`和main均未改写。`PAPER-METHOD-001`已`DONE`；唯一任务为`FORMAL-RELEASE-001 (BLOCKED_EXTERNAL)`。
2. 完整实验位于`D:/brace-msi-paper-fusion/PAPER-FUSION-SPRINT-001/`；`summary.json`已单次打开公开validation，禁止再次调用`--open-validation`。机器`--validate-only`结果为`valid=true/stage=completed`。
3. D-046/D-047冻结混合选择：A/B使用RC3；C使用PaperFusion（公开验证RMSE 42.330230）。Gas蒸馏和Bearing融合均为负结果，不得删除或包装为提升；所有公开指标均有历史暴露，不是官方成绩。
4. 当前上传镜像为`D:/brace-msi-release/BRACE-MSI-0.4.0rc1/BRACE-MSI-0.4.0rc1-image-clean.tar`，SHA-256 `97bb0a9fcfed688ba1b7feadadf09528e232fea578d06a1d782f2dccee306dfa`。4核8GB断网冻结训练、264项回归和`docker load`证据见RC4结果JSON。
5. 作品说明书与提交清单位于`D:/brace-msi-release/BRACE-MSI-0.4.0rc1-submission-materials/`和`docs/SUBMISSION_CHECKLIST.md`。SwanLab公开项目仍是RC3最终工程记录；不得把RC4 C融合写成已经同步的SwanLab实验。
6. 后续只接入正式SDK/挂载字段、评分规则与平台验证；不重训本轮A/B/C矩阵、不重开公开validation、不继续论文扩展或LLM调参、不消耗官方十次试运行。

## 2026-11-12正式路线恢复入口（当前）

1. 当前路线以`docs/FORMAL_ROUTE.md`和D-043为准：A3 Qwen3.5-4B PyTRiO Agent + BRACE确定性Harness + 官方A/B/C训练器 + 冻结安全参数日程。
2. `PYTRIO-SFT-001`已`DONE`。A3完成36/36步，新留出五项100%，A/B/C首轮3/3主动训练；按D-043禁止继续LLM调参。当前唯一任务为`FORMAL-RELEASE-001 (BLOCKED_EXTERNAL)`，只等待正式SDK/挂载、比赛模型服务注入、评分和SwanLab规范。
3. 三任务竞争运行位于`D:/brace-msi-pytrio/PYTRIO-COMPETITIVE-001-A1/`，各10轮/3候选且`valid=true`。最终A/B/C为0.725695 Macro-F1、637.180224 RMSE、51.635999 RMSE；公开验证历史暴露，不是官方成绩。
4. A3完整Sampler路径只从Git外`D:/brace-msi-pytrio/PYTRIO-SFT-001-A3/result.json`的`sampler_model_path`读取。不要把路径或API Key写入公开配置、镜像或日志。
5. 当前上传镜像为`D:/brace-msi-release/BRACE-MSI-0.3.0rc3/BRACE-MSI-0.3.0rc3-image-clean.tar`，SHA-256 `0daef2e0...6d325a`。这是`docker save`归档；不得用源码ZIP替代。
6. RC3镜像linux/amd64、240,579,085字节、UID10001，含PyTRiO0.2.9但无Torch/数据/权重/密钥；4核8GB断网双协议Smoke和重载通过；最终代码246项、打包前干净环境243项回归通过。
7. A/B/C官方训练器入口位于`src/brace_msi/official_trainer.py`和`official_agent_harness.py`；必须继续使用只读清单、隔离子进程、ActionSandbox、候选预算与SafetyGate，不得让模型文本直接执行代码。
8. A第8轮和C第10轮各出现一次候选预算耗尽后的训练建议，均在训练前被拒绝。该负边界必须保留；不要扩大候选预算迎合模型。
9. `BRACE-MSI-0.1.0rc1`、`0.2.0rc2`、A1失败、A2负对照和INVALID历史都不修改。新代码仍在`task/core-001`，不合并main。
10. 无新官方材料时保持冻结：不重训Gas/FD001/Bearing，不重开公开验证；`SWANLAB-FINAL-001`已经完成，禁止重复同步或再生成替代记录；不消耗官方十次试运行，不重复哈希核验。

## 2026-11-13提交材料恢复入口（历史RC3）

1. `MAT-001`已完成。作品说明书源为`docs/SUBMISSION_DOCUMENT.md`，平台字段清单为`docs/SUBMISSION_CHECKLIST.md`；DOCX/PDF位于`D:/brace-msi-release/BRACE-MSI-0.3.0rc3-submission-materials/`。
2. `SWANLAB-FINAL-001`已完成且只作记录，不得用于再调参。公开项目为`https://swanlab.cn/@nanmo-max/brace-msi-final`，三个运行链接与恢复细节见`docs/results/SWANLAB-FINAL-001.md`。
3. GitHub当前正式源码入口为`https://github.com/nanmo-max/rengongzhineng/tree/task/core-001`；远端main未覆盖，RC3标签为`brace-msi-v0.3.0-rc3`。
4. 项目级许可证仍由队长决定。不要自动添加MIT/Apache许可证，也不要在材料中声称已获得未确认的项目源码许可。
5. 当前唯一核心任务重新回到`FORMAL-RELEASE-001 (BLOCKED_EXTERNAL)`。没有新官方SDK/评分/SwanLab比赛字段时保持冻结。

以下旧恢复入口保留历史上下文；若与本节冲突，以`STATUS.md`、`TASKS.md`和本节为准。

## 2026-11-12统一策略末期评估恢复入口

1. 完整开发搜索已完成81/81并严格验收`valid=true`；不存在需要恢复的后台进程，不得重复运行开发矩阵。
2. 读取`docs/results/UNIFIED-POLICY-OPT-001.md`和`configs/unified_policy_frozen.json`；最终候选为简单`normalized_performance_triggered`，复杂`shared-f8881ba9c291`仅作对照。
3. 复杂BRACE在3/3任务级留出fold无优势且资源更高，D-034禁止继续增加复杂机制或用末期结果调参。
4. 下一步只实现并验证prediction-only一次性末期入口；必须先提交冻结配置与末期协议，随后才能打开末期数据。
5. Gas与FD001末期必须标记历史暴露；只有未打开的XJTU密封轴承可标记virgin。不得使用官方十次测试机会。

## 恢复指令

在新的Codex会话中，将工作目录设为本项目根目录，然后发送：

> 请先完整读取 `AGENTS.md`、`docs/STATUS.md`、`docs/TASKS.md`、`docs/DECISION_LOG.md` 和 `docs/SOURCE_REGISTRY.md`，执行 `git status --short`，只根据仓库证据恢复项目。报告当前阶段、唯一当前任务、阻塞、下一步和禁止事项；不要从旧聊天猜测，不要启动训练，随后继续 `READY` 的最高优先级任务。

## Agent恢复步骤

1. 读取根目录 `AGENTS.md`。
2. 读取 `STATUS.md`，确认最近同步时间和当前执行入口。
3. 读取 `TASKS.md`，找到唯一`IN_PROGRESS`任务；若没有，则选择依赖满足的最高优先级`READY`任务。
4. 读取与该任务相关的架构、工作流和实验协议。
5. 读取 `DECISION_LOG.md` 中全部`LOCKED`决策。
6. 在 `SOURCE_REGISTRY.md` 核对任务引用的证据与待核实假设。
7. 检查Git状态、最近提交和已有产物；不得重复已有证据的实验。
8. 向用户报告恢复摘要后继续执行。

## 恢复时必须报告

- 当前Gate和方案版本；
- 当前任务ID、依赖和完成标准；
- 已有可核验证据；
- 当前阻塞及负责解除它的来源；
- 本次准备执行的一个动作；
- 明确禁止事项。

## 当前恢复结果

实时内容不在此复制，必须从 [STATUS.md](STATUS.md) 和 [TASKS.md](TASKS.md) 读取，避免交接文档与执行状态分叉。

## 已建立的稳定恢复边界

- 内部模拟协议入口：`src/brace_msi/protocol/__init__.py`。
- 协议回归测试：`tests/protocol/test_state_machine.py`。
- 正式SDK到达后只增加适配映射；不得绕过现有状态守卫，也不得把宣讲中的字段名写成正式接口事实。
- 恢复后先运行`D:\anaconda3\python.exe -m pytest -q --tb=short`验证稳定边界，再依据`TASKS.md`选择任务。

## 本地代理闭环恢复边界

- 数据审计与切分：`source_notes/PROXY_DATA_AUDIT.md`。
- Smoke结果：`results/LOCAL-SMOKE-001.md`；完整结果：`results/LOCAL-EXP-001.md`。
- 完整密封段已在提交`f9647dd`上于2026-11-06执行一次；不得依据其结果调参后重跑同一密封段。
- 机器产物位于Git忽略的`artifacts/experiments/`；若本地缺失，只能依据已提交聚合证据恢复，不能虚构逐事件记录。

## 正式候选系统开发恢复边界

- 实施计划：`plans/FORMAL-CANDIDATE-SYSTEM.md`；任务状态仍只看`TASKS.md`。
- 平台无关TaskBootstrap：`src/brace_msi/bootstrap.py`；CPU模型池：`modeling.py`；原子注册与回滚：`registry.py`。
- 统一Harness：`src/brace_msi/harness.py`；原子检查点：`checkpoint.py`；公开待同步队列：`recording.py`；非交互入口：`python -m brace_msi synthetic-smoke`。
- 交付入口：根目录`run.ps1`/`run.sh`、`Dockerfile`和`docs/RUNBOOK.md`；静态报告由`python -m brace_msi render-report`生成。
- 历史静态上下文证据已由真实Docker验收替代；`PKG-RUNTIME-001`现为DONE，实际镜像大小和归档哈希见`docs/results/RC2_CONTAINER_ACCEPTANCE.json`。
- 完整系统模拟：`results/LOCAL-FORMAL-SIM-001.md`；有效A2机器产物位于`artifacts/formal_simulation/LOCAL-FORMAL-SIM-001/run-7ef3829/`；A1`run-ce3e907`为INVALID负证据。
- 模拟输出已通过`validate_simulation_output`：三任务、每任务至少3候选、动作覆盖、唯一批次提交、公开日志白名单和注册表加载均有效。
- 旧密封段锁继续生效；完整系统开发与模拟评测不得打开或据其结果选型。

## Release Candidate恢复边界

- 当前版本：`BRACE-MSI-0.1.0rc1`；入口见`docs/RELEASE_CANDIDATE.md`。
- RR-002至RR-005完成；全新安装包通过95项测试、两协议Smoke、SwanLab 0.10.4离线导出和静态交付审计。
- RR-001已完成：Docker Engine 28.5.1、linux/amd64镜像、非root/禁入文件检查、4核8GB断网Smoke及可重载归档均有证据。
- 正式SDK插件入口：`src/brace_msi/official_sdk.py`和`python -m brace_msi sdk-contract-check`；未知字段不得写入核心。
- SwanLab入口：`src/brace_msi/swanlab_adapter.py`与`docs/SWANLAB_INTEGRATION.md`；同步必须由人工显式执行。
- 发布包生成：在干净工作树设置`PYTHONPATH=src`后运行`scripts/build_release_candidate.py`；机器清单必须保留BLOCKED门。
- 本地代理算法探索已经停止；下一会话只处理Docker运行时或新到官方SDK/数据/评分/SwanLab规范。

## 官方数据接入恢复边界

- 用户于2026-11-10指定`C:\Users\Administrator\Desktop\官方`为三套官方公开数据原件；首轮只读审计见`docs/source_notes/OFFICIAL_DATA_INTAKE_2026-11-10.md`。
- Gas与C-MAPSS逐文件等同既有代理原件；可复用代码和数据指纹，不得把既有`proxy_only`结果改名为官方成绩，也不得因文件相同绕过正式预注册。
- XJTU-SY六个分卷完整，包含15个轴承和9,216个唯一CSV；RAR跨卷列表的5个重复记录必须去重。尚未确定比赛目标、切分和指标，不得自行选择分类或RUL任务后声称正式实验。
- 当前唯一任务为`DATA-001`。先取得并登记比赛manifest、任务定义、切分、指标、评分脚本和许可证，再决定是否需要重跑Gas/C-MAPSS并开始轴承训练。
- SwanLab不是当前任务。依据`D-023`，只在平台规范与最终工程模型冻结后，通过正式重新训练生成最终记录；此前不运行、修改或同步SwanLab。

## XJTU-SY本地串行训练恢复边界

- 当前任务以`STATUS.md`和`TASKS.md`中的`XJTU-LOCAL-001`为准；实施计划为`docs/plans/XJTU-LOCAL-SERIAL.md`。
- 配置与入口：`configs/xjtu_local_serial.json`、`scripts/run_xjtu_local.py`；机器派生根为`D:/brace-msi-xjtu/XJTU-LOCAL-DEV-001/`。
- 运行已结束，无后台进程。A1在`experiments/`因公平可见性缺陷标记INVALID；有效A2在`experiments-a2/`，以`validation-experiments-a2.json`和`docs/results/XJTU-LOCAL-DEV-001.md`为准。
- 当前队列只读取9个初训和3个开发轴承；3个密封轴承不进入特征缓存或训练。逐轴承缓存和运行证据可恢复但不得无理由重跑。全部结果必须保留`local_development_only`边界，不解除H-006。

## 最新官方规则对齐训练恢复边界

- `FORMAL-DEV-001`已完成，计划`docs/plans/OFFICIAL-RULES-ALIGNED-TRAINING.md`，实验`OFFICIAL-RULES-ALIGNED-DEV-001`。
- 最新平台事实来自`SOURCE_REGISTRY.md`的O-PLATFORM-001至004；四张截图只确认任务、指标、参数量、10轮、评分维度与次数规则，不提供训练包或权重。
- 本地MLP检查点拓扑匹配平台参数量但`official_checkpoint=false`；平台包到达后另建正式实验ID，不重命名本地结果。
- 运行根`D:/brace-msi-official-dev/OFFICIAL-RULES-ALIGNED-DEV-001/`已完成9/9，`validation.json`为`valid=true`；后台PID 6084已正常退出，不得重复已完成实验。
- 结果见`docs/results/OFFICIAL-RULES-ALIGNED-DEV-001.md`。D-027已停止在同一开发流继续调参：Gas/Engine等待平台检查点复验，Bearing使用静态安全默认。
- 当前禁止平台提交、SwanLab、密封段和RC修改。浏览器自动化本轮因URL不可验证停止，不再重试。

## 官方训练包接入恢复边界

- 官方包路径：`C:/Users/Administrator/Desktop/人工智能创新大赛/训练包`；必须保持只读，不生成`__pycache__`，不复制数据/检查点到Git或镜像。
- 只读审计：`docs/source_notes/OFFICIAL_TRAINING_PACKAGE_AUDIT_2026-11-11.md`；证据ID为O-PLATFORM-005。
- 已批准设计与实施计划分别位于`docs/superpowers/specs/2026-11-11-official-package-integration-design.md`和`docs/superpowers/plans/2026-11-11-official-package-integration.md`。
- D-028规定正式包必须使用随包NumPy训练器和真实检查点；B为34输入、24隐藏单元。D-026仅是历史本地推断。
- `OFFICIAL-PKG-001`已完成，执行提交`34098bf`；运行根`D:/brace-msi-official-package/OFFICIAL-PACKAGE-DEV-001/`包含9/9作业、15个真实候选、资源估算、验证暴露账本、静态报告和`valid=true`机器验收。
- 结果见`docs/results/OFFICIAL-PACKAGE-DEV-001.md`；内部`performance_triggered`在本次实验中实际是单次固定低成本续训对照。A/B上BRACE与该对照持平但成本更高，C上BRACE公开验证RMSE更低。D-031禁止在同一公开验证集继续调参或重跑。
- A1 CLI导入失败发生在训练前，Git和运行根事后索引保留；不得删除或伪装成候选训练失败。
- 当前无后台进程。继续禁止SwanLab、平台提交、隐藏测试、同流算法探索和RC修改；等待正式SDK、评分/许可证或容器运行条件。
# 2026-11-17 第一性原理重建恢复入口

当前分支为`codex/first-principles-rebuild`。先按本文件原有通用流程读取SSOT，然后执行：

1. 阅读`docs/replans/FIRST-PRINCIPLES-REBUILD-FORENSICS-2026-11-17.md`。
2. 阅读`docs/superpowers/specs/2026-11-17-first-principles-formal-runtime-design.md`。
3. 阅读`docs/superpowers/plans/2026-11-17-first-principles-formal-runtime.md`。
4. 当前任务只能从`FORMAL-MINIMAL-001`继续；`0.9.0rc1`和更早RC全部冻结。
5. 禁止上传、重跑或消耗平台次数，直到FORMAL-CLEAN-IMAGE-001完成。

## 2026-11-20 选择可靠性与泛化恢复入口

1. 实时状态以`STATUS.md`和`TASKS.md`顶部的`SELECTION-RELIABILITY-001`为准；`FORMAL-RELEASE-001`继续外部阻塞，不是当前可执行任务。
2. 阅读O-PLATFORM-019和D-087，再阅读`superpowers/specs/2026-11-20-selection-generalization-runtime-design.md`及对应plan。
3. `SELECTION-RELIABILITY-001`、`GENERALIZATION-MATRIX-001`和`PERFORMANCE-METHOD-PILOT-001`已完成开发筛选；A4只在A6基础上增加`balanced_current_e3 + native_recent_e3`复合分类候选，B/C保持A6。不要把收益归因于类平衡单因素。当前唯一READY任务为`PYTRIO-ADVISOR-OPT-001`。
4. 现有`0.10.6rc1`归档冻结为Protocol RC，不原地改写；新正式候选必须在独立提交与归档中生成。
5. 正式镜像只走`rnd.model()`；PyTRiO训练和SwanLab记录在镜像外，且只有本地证据通过后才影响新候选。
6. Advisor是否采用冻结后，必须执行`FINAL-GENERALIZATION-VALIDATION-001`的独立替代流/任务留出；A6/A4均不得直接解锁正式RC。方法结果见`results/PERFORMANCE-METHOD-PILOT-001.md`。
