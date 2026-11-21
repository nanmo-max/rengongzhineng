# 实验登记与结果

本文件是全部实验运行的唯一登记处，包括失败和中止实验。

## RELEASE-COMPATIBILITY-AUDIT-001-A1/A2（PROTOCOL_PASS_RELEASE_FAIL）

- 研究问题：冻结`0.10.6rc1`是否能在官方SDK 1.0.2契约下完成本地三任务正式生命周期，并在错误宿主部署判断下保持性能方向安全？
- 输入：精确`docker save`归档、官方A/B/C训练包公开投影与初始checkpoint；公开validation只作描述性复算和同作用域负向测试，隐藏/密封数据未读取。
- A1：归档重载后在4核8GB、断网、只读根、非root下完成A/B/C各10轮、60调用、30候选和15行预测，`acceptance.json valid=true`。
- A2：固定C父checkpoint，训练`e3_lr3`退化候选，并让宿主第二次回答错误`deploy`；父RMSE `52.868573`、候选`55.629944`，冻结镜像实际选择候选，`wrong_deploy_accepted=true`。
- 结论：协议与容器通过，发布准入失败；不消耗官方次数，不修改代码，不重新打开密封数据。证据见`results/RELEASE-COMPATIBILITY-AUDIT-001.md`与`D:/brace-msi-release-audit/`。

## FORMAL-EVERY-ROUND-TRAIN-001-A1（INVALID_WRONG_DECISION_OWNER）

- 依据：O-PLATFORM-018、D-085。平台已证明宿主调用和提案解析有效，但30/30主动retain导致候选数0。
- 假设：将Agent建议与执行层训练职责分离，让每轮基于当前父checkpoint执行一个现有白名单recipe，再由平台权威指标决定部署或保留，能够在不牺牲安全性的前提下恢复真实实验覆盖并发现可部署增益。
- 修改边界：只修改`brace_formal`每轮候选执行、上下文和收据真值；不修改官方SDK、模型schema、数据、预测入口、平台测量方向或历史RC。
- 验证：先用连续retain宿主写红灯测试；再验证10轮候选数10、平台负指标保留父模型、正指标部署候选、真实执行参数可审计；随后运行完整回归和三任务4核8GB容器验收。
- 资源：本地CPU/Docker；PyTRiO远程、SwanLab、官方试运行、隐藏测试使用均为0。
- 结果：469项回归通过；`0.10.5rc1`本地容器A/B/C各10轮且30/30候选提交，在连续retain建议下验证“每轮训练”成立。但部署仍由平台返回指标控制，违反D-086职责边界，因此该镜像和归档只保留为无效设计证据，禁止上传。

## FORMAL-EVERY-ROUND-TRAIN-001-A2（ABORTED_SIMULATOR_ASSUMED_PLATFORM_METRICS）

- 依据：D-086。修复A1把平台误作每轮部署决策者的问题。
- 假设：Qwen分别执行训练方案选择和训练后部署判断，Harness只负责受控训练、评估与硬安全门，可以形成每轮真实“历史—假设—训练—评估—决策”闭环，同时保持父链和平台协议有效。
- 变量：新增训练提案与部署决策两种严格JSON契约；每轮两次宿主调用；平台候选测量只审计；不修改模型schema、数据、预测入口、官方SDK或历史RC。
- 验证：红灯覆盖Qwen recipe选择、训练后指标输入、deploy/retain/rollback、非法决策失败保留父模型和两个call ID；完整回归后以连续retain训练提案/混合部署决策运行三任务30轮容器验收。
- 资源：本地CPU/Docker；远程PyTRiO、SwanLab、官方试运行和隐藏测试均为0。
- 结果：471项代码回归通过并构建`0.10.6rc1`，但首个容器验收仍让模拟平台在`candidate_response`返回指标。用户澄清平台只在全部流程结束后隐藏评测；本次容器验收主动终止，部分目录保留且不作通过证据。代码的部署判断已经使用本地父/候选指标，不依赖该字段。

## FORMAL-EVERY-ROUND-TRAIN-001-A3（REGISTERED_NOT_RUN）

- 依据：D-086及用户2026-11-19补充：平台过程中不返回评分，Harness必须自行计算官方关注的指标并交给Qwen；最终隐藏评分不参与训练决策。
- 唯一验证修订：模拟平台的`candidate_response`只返回artifact ID，不返回summary/metrics；父/候选指标只能由镜像内部评估产生。算法、镜像代码和0.10.6rc1构建内容不变。
- 成功标准：A/B/C各10轮、每轮2次宿主调用、1次候选训练；Qwen依据本地指标决定deploy/retain；平台回执指标始终为空；父链、预测、4核8GB、白名单、64 MiB和归档重载通过。
- 结果：`COMPLETED_PASS_NO_PLATFORM_METRICS`。三任务30轮、60次宿主调用、30次真实候选；平台指标30/30为空；Qwen本地决定deploy 4次、retain 26次。协议、父链和预测全部通过。为显式覆盖真实rollback分支，A4只修改本地模拟Qwen对“严格退化”的回答，不改变镜像。

## FORMAL-EVERY-ROUND-TRAIN-001-A4（COMPLETED_FINAL_LOCAL_RC）

- 唯一验证修订：本地模拟Qwen对主指标改善返回deploy、相同返回retain、严格退化返回rollback；平台仍只返回artifact ID且无指标。镜像与训练代码保持精确`0.10.6rc1`不变。
- 成功标准：继承A3并要求容器证据同时覆盖deploy、retain和rollback三条决策路径。
- 结果：A/B/C共30轮、60次宿主调用、30个真实候选；平台指标30/30为空，Qwen依据本地指标部署4次、回滚26次，未出现数值完全相同的候选，因此本次自然运行未触发retain。硬安全失败0，三任务父链、状态、预测、4核8GB、非root、白名单、64 MiB和归档重载通过。机器JSON SHA-256 `307581D27589AD17A90BEF69A1283D86B51AEF553238D5F34AEB08400CDF2CD8`。
- 归档：`D:/brace-msi-first-principles-release/BRACE-MSI-0.10.6rc1-A1/harness.tar`，81,208,320字节，SHA-256 `F7518609974EAB3C156C07F6D0AA7CBFE6CF9253B43C5D20B3DC71B4C91D89CB`。远程PyTRiO、SwanLab、平台上传和官方试运行均为0。

## FORMAL-AGENT-OUTPUT-001-A1（COMPLETED_PASS_LOCAL_PLATFORM_CONFIRMATION_PENDING）

- 研究问题：官方宿主回复在较长输出或JSON外包含说明时，正式Agent能否在官方Token预算内提取唯一合法的有界提案，同时对歧义/非法提案继续安全retain？
- 直接证据：O-PLATFORM-017的30轮输出合计7,680 Token，恰为30×256；30轮均因提案非法而retain且候选为0。
- 变量边界：只修改`brace_formal.agent`的输出预算、提示约束和JSON提取；不修改训练器、recipe、SafetyGate、父链、SDK、数据或正式指标。
- 输入：人工构造的宿主回复，包括纯JSON、围栏JSON、简短说明后唯一JSON、截断/无JSON、多个歧义JSON；不调用远程模型、不读取官方隐藏数据。
- 预算：专项单元测试与完整本地回归；官方试运行0次、远程Token 0、SwanLab 0。
- 成功标准：合法唯一提案均被解析并保留白名单约束；参赛代码不传`max_tokens`，由官方SDK自动使用宿主下发的完整`rnd.max_output_tokens`；非法/歧义/越界提案仍retain并保留真实call ID；完整回归通过。
- 停止条件：测试无法复现固定256上限或放宽解析导致歧义对象被接受时停止，不生成新镜像。
- 红绿结果：旧代码在固定预算、外包装唯一JSON、歧义JSON和未使用参数四类用例上出现预期失败；修复后Agent专项10项、正式运行与SDK专项37项、完整回归469项通过。
- A1无效构建：`0.10.4rc1`仍含用户否决的1024本地上限，容器验收被主动终止，禁止上传。
- 最终本地结果：`0.10.4rc2`不传`max_tokens`；容器宿主核验SDK发出的预算等于frame授权值。A/B/C各10轮、30调用、候选1/0/3、15行预测，`acceptance.json valid=true`；官方试运行新增0次、远程Token 0、SwanLab 0。
- 产物：`D:/brace-msi-first-principles-release/BRACE-MSI-0.10.4rc2-A1/harness.tar`，SHA-256 `97948BD45502CFFE6082184DB06799A8E0FD8BE6BB008C048C7CE9DE47B335EA`；机器验收SHA-256 `81F31E55802AD00BB5B604FE829744E892218C4E731A5413E51338F0806042B2`。详见`results/FORMAL-AGENT-OUTPUT-001.md`。

## WORKSPACE-V2-INDEPENDENT-TEST-001-A1（COMPLETED_PASS_LOCAL_ONLY）

- 研究问题：冻结A4归档在不依赖工作树源码、全新镜像标签和全新状态目录下，能否重复完成官方workspace v2三任务生命周期，并生成不伪造官方指标的完整HTML报告？
- 输入：`D:/brace-msi-workspace-v2/BRACE-MSI-0.9.0rc1-A4/brace-msi-0.9.0rc1-harness.tar`，预期SHA-256 `dc0147706e5c20a62360bf309a280b890ac6cea2707eee4aa66f8f7169c57cbc`；只读官方A/B/C训练包公开投影和父`checkpoint.npz`；不读取隐藏数据。
- 隔离：先删除独立测试标签，再从归档加载；使用全新输出根`D:/brace-msi-workspace-v2/WORKSPACE-V2-INDEPENDENT-TEST-001-A1/`；容器4 CPU、8 GiB、`--network none`、非root；模拟宿主固定返回结构化提案与本地调用ID。
- 预算：A/B/C各10轮、每轮至少一次宿主模型调用；每任务预测5行；官方试运行0次、远程PyTRiO 0次、SwanLab同步0次。
- 成功标准：三任务30轮、30个非空调用收据、父链/状态/候选或retain连续、15行预测、机器结果`valid=true`；官方风格HTML和JSON包含全部30轮并标记`local_protocol_only_not_official_score`与“本地协议模拟，不计正式成绩”。
- 停止条件：归档哈希不符、容器或父链失败、模型调用缺失、预测失败、报告缺轮或产生任何虚构隐藏指标/官方结算即停止并保留结果。
- 结果：A/B/C各10轮、每轮1个宿主模型调用收据；A/B全程retain，C第1、2轮提交并连续选择候选；三任务各完成5行独立预测，`acceptance.json valid=true`。报告汇总30/30轮、30调用、15预测、2候选；隐藏指标显示“正式平台产生，本地不可获得”，没有“官方评测通过”表述。
- 产物：`D:/brace-msi-workspace-v2/WORKSPACE-V2-INDEPENDENT-TEST-001-A1/`；`acceptance.json` SHA-256 `773bb1895382bbb0033c1d44378b71fdc1001084f9da6c4e3811ec7a8e82c42f`，最终HTML SHA-256 `7d931103855fdeef08d47137e23ef7008b8bef2b18ad1d1dd46d8a3b16c34271`，最终报告JSON SHA-256 `eb8929cfff82f4ac8576421419195f3dbf9ced498073529c35bccdd0b648215c`。最终报告目录为`platform-style-report-v2/`；初版报告保留，不作为当前入口。
- 验证：报告生成器按TDD完成两个红绿用例；最终完整回归`437 passed in 150.59s`。官方试运行、远程PyTRiO、SwanLab同步和隐藏数据使用均为0。

## WORKSPACE-V2-ACCEPTANCE-001（COMPLETED_SUPERSEDED_BY_A2）

- 研究问题：正式上传镜像能否仅依赖官方`contest_harness` 1.0.2，在4核8GB、断网、非root容器中完成A/B/C各10轮宿主网关模型调用、真实父checkpoint续训或retain、候选/状态提交及独立预测？
- 输入：只读官方A/B/C训练包的`public/`投影和初始`checkpoint.npz`；本地宿主替身严格按`contest.harness.workspace.v2`帧响应。不得读取隐藏数据，不计算或反馈公开验证性能。
- 镜像边界：正式镜像只含运行时代码、官方SDK和固定`describe/train/predict`入口；不得包含测试、模拟器、数据、权重、密钥、本地报告、SwanLab、Tokenizer或直连PyTRiO客户端。
- 模型边界：每轮宿主替身返回非零Token结构化响应并生成唯一`model_call_id`；该替身仅验证协议，不冒充官方Qwen或正式Token计量。
- 预算：A/B/C各10轮，每轮最多一个受控候选；4 CPU、8 GiB、无网络；官方试运行0次；不启动新性能搜索或SwanLab同步。
- 成功标准：三任务各10轮、每轮至少一次真实宿主模型RPC且完成记录引用全部`model_call_ids`；父链与状态连续；候选不超过64 MiB；最终产物各完成5行逐行预测；镜像禁入扫描、项目回归和`docker save/load`通过。
- 停止条件：任何SDK外字段猜测、模型调用缺失、父链断裂、产物不可加载、未来/隐藏数据接触、正式镜像含禁入内容或资源超限均判失败并保留证据，不上传平台。
- 输出：`D:/brace-msi-workspace-v2/WORKSPACE-V2-ACCEPTANCE-001/`；结果必须标记`local_protocol_only_not_official_score`。
- 结果：A/B/C各10轮、30次宿主替身模型调用、15行独立预测全部通过；`acceptance.json`为`valid=true`。随后发现vendored SDK文件仅有结尾空行字节差异，故A1归档保留历史、不上传，由A2按相同协议重跑最终字节版。

## WORKSPACE-V2-ACCEPTANCE-001-A2（COMPLETED_SUPERSEDED_BY_A3）

- 唯一变化：A1后将9个vendored `contest_harness`源文件的结尾字节修正为与官方1.0.2解压件逐文件SHA-256完全一致；运行逻辑、策略、依赖、数据、宿主替身和验收标准不变。
- 必要性：正式上传归档必须与最终仓库源码及官方SDK字节一致，A1归档因此只保留历史而不上传。
- 输入/预算/停止条件：完全继承A1；仍为A/B/C各10轮、4核8GB、断网、官方试运行0次，不计算性能分数。
- 输出：`D:/brace-msi-workspace-v2/WORKSPACE-V2-ACCEPTANCE-001-A2/`与`D:/brace-msi-workspace-v2/BRACE-MSI-0.9.0rc1-A2/`；不得覆盖A1。
- 结果：`valid=true`；A/B/C各10轮，共30次带唯一`model_call_id`的宿主模型RPC，C提交并连续选择2个候选，A/B合法retain，三任务各完成5行独立预测。完整回归`434 passed`；镜像151,366,375字节、非root、无PyTRiO/SwanLab安装及禁入文件。`docker save/load`通过。
- 后续审查：发现“内部Gate部署、平台测量拒绝”时持久状态仍记录候选已部署，下一轮可能父哈希冲突。A2归档保留历史、禁止上传；A3仅修复平台拒绝后的状态对账并重新执行全部门。

## WORKSPACE-V2-ACCEPTANCE-001-A3（COMPLETED_SUPERSEDED_BY_A4）

- 唯一变化：平台公开测量拒绝已提交候选时，在`save_state`前将最新轮对账为父artifact（`deployed=false`、父checkpoint哈希、`retained_parent`并移除影子前任）；平台接受、内部retain、训练策略和预测均不改变。
- 红灯证据：`test_platform_measurement_rejection_commits_parent_state`在修复前得到`deployed=true`而失败；修复后该测试及官方SDK专项`5/5`通过。
- 输入/预算/成功门：完全继承A2；A/B/C各10轮，4核8GB，断网，官方试运行0次；最终必须重跑完整回归、内容扫描与`docker save/load`。
- 输出：`D:/brace-msi-workspace-v2/WORKSPACE-V2-ACCEPTANCE-001-A3/`与`D:/brace-msi-workspace-v2/BRACE-MSI-0.9.0rc1-A3/`；A1/A2不得覆盖或上传。
- 结果：三任务30轮、30次宿主调用和15行预测为`valid=true`；完整回归435项。后续审查发现平台测量拒绝时`state.json`已回退父模型，但`public-spool.jsonl`仍保留内部Gate的`accepted=true`，会造成外部实验记录与真实选中artifact分叉；A3禁止上传。

## WORKSPACE-V2-ACCEPTANCE-001-A4（COMPLETED_PASS_LOCAL_PLATFORM_PENDING）

- 唯一变化：平台测量拒绝候选时，同一对账流程分别原子写入`state.json`与`public-spool.jsonl`，均明确`accepted/deployed=false`、`platform_measurement_rejected`和父checkpoint哈希；任一记录异常即失败关闭，训练策略、模型参数、宿主调用、平台SDK及预测均不改变。
- 红绿证据：扩展`test_platform_measurement_rejection_commits_parent_state`后，修复前公开收据仍为`accepted=true`而失败；修复后官方SDK专项`5/5`、完整回归`435 passed in 142.62s`。
- 结果：`D:/brace-msi-workspace-v2/WORKSPACE-V2-ACCEPTANCE-001-A4/acceptance.json`为`valid=true`；A/B/C各10轮，共30次宿主模型调用，C两次候选提交，A/B合法retain，三任务各5行独立预测。镜像linux/amd64、151,369,904字节、UID10001，未安装PyTRiO/SwanLab且`/app`仅两个固定入口。
- 正式归档：`D:/brace-msi-workspace-v2/BRACE-MSI-0.9.0rc1-A4/brace-msi-0.9.0rc1-harness.tar`，151,393,280字节，SHA-256 `dc0147706e5c20a62360bf309a280b890ac6cea2707eee4aa66f8f7169c57cbc`；删除正式tag后`docker load`恢复相同镜像ID并再次通过`describe`。
- 边界：该验收只证明本地workspace v2协议与正式镜像准备完成，不是平台真实Qwen、Token结算、公开分数或隐藏评测；外部状态继续由`FORMAL-RELEASE-001`管理。

## PLATFORM-MODEL-TRANSPORT-001（COMPLETED_LOCAL_PLATFORM_PENDING）

- 问题：平台Chat Completions模型传输能否不经语义重写直接进入原生`brace_msi start`，并满足训练阶段强制模型调用与非零Token要求？
- 输入：官方A公开train与父`checkpoint.npz`，不读取公开validation作模型选择；validation仅用于独立`submit`样本数验证。
- 方法：镜像内构造/解析标准Chat Completions对象；外部只注入可调用`model_transport`；替身响应返回合法受控提案与123/45 Token；4核8GB、断网、只读根、非root运行。
- 结果：模型传输被实际调用1次；官方A候选训练完成，Gate拒绝后正确发布父checkpoint；独立预测1,244条；传输失败测试两次重试后retain且训练0次。专项73项、完整回归430项通过。
- 产物：`docs/results/PLATFORM-MODEL-TRANSPORT-001.md`、`docs/results/RC83_CONTAINER_ACCEPTANCE.json`、`D:/brace-msi-platform-bridge/BRACE-MSI-0.8.3rc1/brace-msi-0.8.3rc1-harness.tar`。
- 边界：模型服务为本地替身，不是平台真实Qwen调用；公开指标不作为新性能结论；正式平台状态仍为待验证。

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

## DELAYED-GAIN-SIM-001-SMOKE-A1/A2/A3

- 状态：`COMPLETED_PROTOCOL_PASS_PERFORMANCE_MIXED_CONFIRMATION_EXPOSED`。
- Smoke A1：三任务各10轮、各1个候选且均拒绝，验证到达证据入口、封存、父链和一次确认。
- A2：完整候选预算；A/C保持父模型。B第9轮部署后，第10轮在相同到达样本上的直接前任配对收益为`-310.293697 RMSE`，但旧实现未回滚，最终确认RMSE恶化至`993.202677`。失败产物保留。
- A3：唯一机制变更为D-070直接前任回滚；B第10轮执行`rollback`并恢复到RMSE `241.980799`，A/C仍保持父模型。A/B/C候选训练为7/3/6，候选采用0/1/0，回滚0/1/0。
- 资源：A/B/C CPU为6.718750/1.390625/6.406250秒，峰值RSS为207.03/204.42/494.07 MiB；影子推理仅B消耗0.171875 CPU秒；Token 0。
- SwanLab：A3每任务生成本地离线聚合目录，未同步公网；路径见`results/DELAYED-GAIN-SIM-001.md`。
- 报告：`D:/brace-msi-delayed-gain/DELAYED-GAIN-SIM-001-A3/report/official-flow-report.{json,html}`；隐藏状态为未开始，确认暴露指数5。
- 验证：专项59项、完整回归407项、编译、diff、机器不变量和密钥扫描通过。
- 边界：本地代理流程、非官方成绩；确认已反复暴露，禁止据此调参；本实验未重复调用PyTRiO或消耗官方试运行。

## METHOD-PORTFOLIO-PILOT-001-A1

- 状态：`COMPLETED_POSITIVE_TEACHER_TREND`。A/B异构教师跨批趋势显著，C异构教师整体不稳；确认读取0、官方试运行0。
- 研究问题：在完全不使用confirmation/public validation时，哪些成熟CPU方法能在第`t`批训练后，于第`t+1`未见批次稳定优于官方父MLP或原生MLP续训？
- 数据：只读复用`DELAYED-GAIN-SIM-001-A3`的A/B/C十轮`feedback.jsonl`；每个转移只使用1…t批训练，t+1只评价。确认目录不得打开。
- 方法：`static_parent`、`native_current`、`native_cumulative`、`linear_cumulative`、`hgb_cumulative`、`extra_trees_cumulative`、`tree_ensemble`。异构方法仅作教师上界，不是正式提交模型。
- 指标：A Macro-F1/Accuracy；B/C RMSE/MAE，C附NASA；统一记录相对父模型的有向收益、9转移胜率、最差收益、CPU和RSS。
- 预算：每个方法每任务最多5分钟、4 GiB；固定种子20261116；不运行HPO、PyTRiO、SwanLab或官方试运行。
- 晋级门：方法至少在一个任务的多数转移胜出且平均有向收益明显为正，或在不少于两个任务超过原生续训；否则停止该方法。教师上界通过后才开发官方MLP蒸馏。
- 输出：新目录`D:/brace-msi-method-pilot/METHOD-PORTFOLIO-PILOT-001-A1/`；失败和负结果全部保留。

## METHOD-PORTFOLIO-PILOT-001-A2

- 状态：`COMPLETED_POSITIVE_NATIVE_TREND`。17种正式MLP候选×三任务×九转换完成；A累计3轮、B最近窗口3轮、C保守插值晋级连续父链。
- 依据：A1只使用相邻未见批次，初步显示异构教师在A/B有大幅上限、C仅原生累计续训稳定为正；A1不使用confirmation且不消耗官方试运行。
- 研究问题：在保持`contest.cpu-mlp.v1`正式checkpoint格式时，多步续训、最近窗口回放及父模型参数插值（SWA/model-soup式稳定化）能否把教师趋势转化为可提交模型，并降低负迁移？
- 候选：当前批/累计/最近三批 × 1/3/5 epoch；学习率倍率0.3/1/3的有界组合；对最佳多步候选与父模型按0.25/0.5/0.75插值。所有候选从同一父checkpoint独立克隆，禁止读取confirmation。
- 数据与评估：完全继承A1的1…t合法训练、t+1未见评价和九个相邻转换；只记录Macro-F1/Accuracy或RMSE/MAE、最差收益、胜率、CPU、RSS与模型可加载性。
- 预算：先低成本筛选；每任务每转换最多18个原生候选，4 GiB，固定种子20261116；不调用PyTRiO、SwanLab或官方试运行。
- 晋级门：候选在多数转换优于静态父模型且平均收益为正；相对A1原生续训有明确改善，或显著降低最差负迁移。未过门的方法立即停止。
- 输出：`D:/brace-msi-method-pilot/METHOD-PORTFOLIO-PILOT-001-A2/`；A1产物保持只读。

## METHOD-PORTFOLIO-PILOT-001-A3

- 状态：`FAILED_PRESERVED_LR_MULTIPLIER_COMPOUNDING`。完成A `current_e1`后，`current_e3_lr3`倍率逐轮写回导致checkpoint学习率超过上限；运行停止、目录保留、不得作性能证据。
- 依据：A2证明A累计3轮、B最近窗口3轮、C保守父权重插值在独立相邻转换上有正向趋势，但A2每个转换均从初始父checkpoint开始，尚未证明连续部署后仍有效。
- 研究问题：候选在真实父checkpoint连续继承、每轮只访问已开放批次时，九次部署后的逐轮收益、最差阶段与最终父链是否仍优于静态父模型？
- 候选策略：`current_e1`、`current_e3_lr3`、`cumulative_e1`、`cumulative_e3`、`cumulative_e3_lr0.3`、`recent_e3`、`soup_current_e3_alpha0.25/0.5/0.75`；每项从同一初始父独立跑完整父链，禁止按下一批结果改本轮动作。
- 数据与边界：只读A1的十轮feedback；第t轮训练仅用1…t，随后在t+1评价并无条件作为该策略的下一父模型。confirmation/public validation读取0次；不调用PyTRiO、SwanLab或官方试运行。
- 指标：九个到达批次的平均/中位/最差有向收益、胜率、最终checkpoint格式/父链epoch与CPU/RSS；任何非有限、不可加载或步数倒退立即失败。
- 晋级门：至少一个正式checkpoint策略在任务上多数转换胜出且平均收益为正；正式系统只考虑跨批连续证据通过者。
- 输出：`D:/brace-msi-method-pilot/METHOD-PORTFOLIO-PILOT-001-A3/`；A1/A2保持只读。

## METHOD-PORTFOLIO-PILOT-001-A4

- 状态：`COMPLETED_POSITIVE_CONTINUOUS_PARENT`。九种recipe×A/B/C连续父链全部完成，最终checkpoint可加载且epoch/step前进；关键结果和哈希见`results/METHOD-PORTFOLIO-PILOT-001.md`。
- 失败继承：A3完成A的`current_e1`后，在`current_e3_lr3`连续父链中暴露“学习率倍率写入checkpoint并逐轮累乘”的实现缺陷，最终超过checkpoint合法上限而停止；A3目录保留，不作为性能证据。
- 唯一修复：学习率倍率仅在本轮fit期间生效，候选保存前恢复父checkpoint学习率；新增10轮不累乘回归测试。方法、数据、策略、种子、指标和停止条件全部继承A3。
- 输出：`D:/brace-msi-method-pilot/METHOD-PORTFOLIO-PILOT-001-A4/`，不得覆盖A3。

## COMPETITIVE-POLICY-002-A1预注册

- 状态：`COMPLETED_POSITIVE_LOW_B_GAIN`。A/B/C平均有向收益分别为`+0.249526` Macro-F1、`+12.218120` RMSE降低和`+0.438766` RMSE降低；三任务均为正，但B未接近固定recipe上限，因此只作为首轮证据。
- 研究问题：A4晋级recipe进入真实顺序父链后，使用“保守首候选→仅在首候选Gate不足时执行证据路由第二候选→下一批直接前任配对结算→负收益回滚”的策略，能否在A/B/C十轮到达流同时优于静态父模型？
- 决策输入：任务类型、已开放批次目标均值趋势、父checkpoint目标尺度、历史延迟收益与失败次数；禁止读取profile/数据集名称、未来批次或confirmation。
- 候选：首候选固定`25% current-e3 + 75% parent`；第二候选由证据选择`recent_e3/current_e3_lr3/cumulative_e3_lr0.3`，只有首候选当前Gate不改善时才训练。第10轮没有未来结算证据，默认retain。
- 数据：A/B/C十轮显式Update/Gate/feedback；当前Gate只决定本轮安全，下一轮feedback结算延迟收益；confirmation/public validation读取0。
- 指标：逐轮prequential主/辅指标、相对静态有向收益、候选数/采用/拒绝/回滚、CPU、RSS、最终checkpoint加载/大小/epoch/step。
- 成功门：三任务平均prequential有向收益均为正；不存在未来读取、父链倒退或不可加载checkpoint；任何负延迟收益下一轮必须回滚或retain直接前任。
- 输出：`D:/brace-msi-competitive-policy/COMPETITIVE-POLICY-002-A1/`；不调用PyTRiO、SwanLab或官方试运行。

## COMPETITIVE-POLICY-002-A2预注册

- 状态：`COMPLETED_POSITIVE_SELECTED`。A/B/C平均有向收益为`+0.313085`、`+40.869286`和`+0.438766`；B一次负延迟收益触发回滚。成熟四批趋势门晋级正式运行时。
- A1结果：A/B/C平均prequential有向收益均为正，但B仅降低RMSE`12.218120`，明显低于A4固定recipe上限；逐轮收据显示当前Gate系统性拒绝面向下一寿命阶段的高步长候选。
- 唯一策略修订：分类在至少3批后同时比较保守插值与最近窗口候选；回归只有至少4批、线性趋势R²≥0.95且每批归一化斜率≥0.10时，将`current_e3_lr3`作为前向候选并允许以趋势证据越过当前Gate，仍由下一批配对收益回滚。其余规则、数据、候选、预算、种子和确认禁用继承A1。
- 防误判：短期3批趋势不触发；非单调回归仍用保守插值/累计低学习率；策略不接收profile或数据集名称。
- 输出：`D:/brace-msi-competitive-policy/COMPETITIVE-POLICY-002-A2/`；A1保持只读。

## COMPETITIVE-POLICY-002-A3预注册

- 状态：`COMPLETED_NEGATIVE_DISCARDED`。A/C保持正收益，但B平均有向收益`-92.775049`、最差`-979.518301`并回滚2次；提前趋势触发被淘汰，不进入正式候选。
- A2结果：A/B/C平均收益继续为正，B由`12.218120`提高到`40.869286`，但连续三轮高步长更新后下一批出现`-159.90`直接前任收益并回滚。
- 唯一策略修订：三批目标变化同向、相邻变化幅度CV≤0.25且归一化平均变化≥0.10即可提前确认单调趋势；高步长当前更新最多连续2轮，随后强制回到保守候选一轮。四批成熟趋势门仍保留。其他数据、Gate、回滚、候选和预算继承A2。
- 输出：`D:/brace-msi-competitive-policy/COMPETITIVE-POLICY-002-A3/`；A1/A2保持只读。

## COMPETITIVE-POLICY-002-A4预注册

- 状态：`COMPLETED_POSITIVE_NATIVE_RUNTIME`。正式`start_round`十轮重放中A/B/C平均有向收益为`+0.319620` Macro-F1、`+61.352748`和`+0.438766` RMSE降低；候选/部署/回滚分别为`9/9/0`、`8/8/2`、`9/6/0`。确认/public validation读取0、官方试运行0；摘要SHA-256 `A60A3645...E344317`。
- 依据：A2三任务平均收益为正；A3提前激进更新导致B平均收益`-92.775049`并触发2次回滚，故淘汰A3并恢复A2成熟四批趋势门。
- 目的：不再使用研究runner直接训练，改由正式`brace_msi.platform_runtime.start_round`、真实workspace state、显式Update/Gate、父checkpoint和rollback入口重放A2路由，验证正式工程路径等价可用。
- 数据/候选/门/预算：继承A2；第10轮retain；confirmation/public validation读取0；PyTRiO、SwanLab、官方试运行使用0。
- 成功门：A/B/C十轮均完成、平均到达收益均为正、负延迟收益触发回滚、最终checkpoint可加载且小于64 MiB；否则不进入RC。
- 输出：`D:/brace-msi-competitive-policy/COMPETITIVE-POLICY-002-A4/`。

## COMPETITIVE-POLICY-002-A5预注册

- 状态：`INVALID_EVIDENCE_ID_MISMATCH`。三任务十轮完成且A/B/C平均收益仍为正，但报告内部ID仍被旧脚本硬编码为A4；目录保留，不能作为冻结证据。
- 根因：最终自审发现A4路由趋势使用Update+Gate整批目标均值，虽然Gate未参与fit，但其标签影响了recipe选择，不符合当前Gate仅验证的隔离语义。
- 唯一修复：趋势统计和收据`target_mean`只读取Anchor剥离后的Update目标；Gate继续仅用于候选与稳定父模型比较。候选、阈值、数据、种子、预算、回滚和确认禁用全部继承A4。
- 成功门：专项回归证明极端Gate目标不改变趋势均值；A/B/C十轮仍完成且平均有向收益为正；否则撤销0.8.0rc1冻结证据。
- 输出：`D:/brace-msi-competitive-policy/COMPETITIVE-POLICY-002-A5/`；A1—A4保持只读。

## COMPETITIVE-POLICY-002-A6预注册

- 状态：`COMPLETED_POSITIVE_GATE_ISOLATED_FINAL`。三任务各10轮完成，A/B/C平均有向收益为`+0.319620` Macro-F1、`+21.850812`和`+0.438766` RMSE降低；候选/部署/回滚为`9/9/0`、`9/5/0`、`9/6/0`。确认/public validation读取0、官方试运行0；摘要SHA-256 `680C9AFF...10C9E77`。
- 唯一修复：报告`experiment_id`必须取不可为空的输出目录名，并由回归测试覆盖；算法、Gate隔离修正、数据、种子、预算和成功门完全继承A5。
- 输出：`D:/brace-msi-competitive-policy/COMPETITIVE-POLICY-002-A6/`；A1—A5保持只读。

## PLATFORM-PREFLIGHT-001发布兼容验证

- 状态：`COMPLETED_LOCAL_EXTERNAL_BLOCK`。
- 问题：0.8.1镜像默认`start`是否会在平台四挂载尚未提供的预检阶段提前失败；恢复历史安全默认命令后，显式原生训练和预测是否保持可用。
- 数据：仅使用官方A公开train作一轮接口Smoke、公开validation作独立预测行数校验；不计算或比较性能，不进入模型选择。
- 结果：0.8.1裸启动退出1并报`PermissionError: /workspace`；0.8.2裸启动退出0。显式start/submit均退出0，生成132,180字节checkpoint和1,244条预测。
- 资源与边界：4核8GB、断网、只读根；在线PyTRiO/SwanLab/隐藏数据/官方试运行均为0。首次PyPI构建因网络超时失败并保留，镜像源重建成功。
- 输出：`D:/brace-msi-platform-bridge/BRACE-MSI-0.8.2rc1-smoke/`及`docs/results/PLATFORM-PREFLIGHT-001.md`。

## FORMAL-MINIMAL-001-A1/A2本地合成协议测试

- 预注册依据：`docs/superpowers/plans/2026-11-17-first-principles-formal-runtime.md` Task 4；目的仅为验证十轮协议、父链、状态和宿主调用，不评价竞赛性能。
- A1状态：`FAILED_RETAINED`。直接源码启动未配置`PYTHONPATH=src`，修正启动后又发现默认`C:/workspace`遗留目录冲突；没有生成有效摘要，不作通过证据。
- A2状态：`COMPLETED_PROTOCOL_ONLY`。脚本为每次运行隔离`CONTEST_WORK`；A/B/C各10轮、合计30个唯一宿主call ID，父链与状态链全有效；A候选采用4次，B/C各10次。
- 数据：脚本独立生成的合成数值表格分类/回归数据；不读取官方数据、隐藏数据、公开validation或历史确认集。
- 输出：`D:/brace-msi-first-principles-sim-20261117-A2/acceptance.json`与`report.html`；摘要SHA-256 `83834956C7539345B7C83D6A06FC44FB12E8244713BAAAE8373CA2501A68E2EF`。
- 边界：在线PyTRiO、SwanLab、官方试运行和付费API使用均为0；结果醒目标注“非官方成绩”。

## FORMAL-CLEAN-IMAGE-001-A1/A2容器验收

- 状态：A1 `COMPLETED_SUPERSEDED_BUILD_ID`；A2 `COMPLETED_FINAL_PROTOCOL_RC`。
- 目的：验证白名单正式镜像在4核8GB、断网、非root、只读数据/父checkpoint挂载下的官方SDK 1.0.2十轮生命周期、候选、retain、状态、父链与独立预测。
- A1：30轮全部通过，但之后关闭Docker provenance以生成单一稳定linux/amd64归档，因此A1不作为最终镜像证据。
- A2：对最终镜像ID `sha256:62d4487b...acd8009`重新完成A/B/C各10轮；每任务10个宿主call ID，最终采用候选A1/B2/C1，独立预测各5行，`valid=true`。验收JSON SHA-256 `DE84F00C...ECC326`。
- 镜像门：81,183,334字节、UID10001、`pip check`通过、禁入模块均不存在、`/app`只有官方SDK/正式包/固定入口；checkpoint最大132,180字节。
- 归档：`D:/brace-msi-first-principles-release/BRACE-MSI-0.10.0rc1-FINAL-PROVENANCE-OFF/harness.tar`，81,201,152字节，SHA-256 `DC73FAFC73906D1A841BE3AC47DBCBF3A69915C380711B07E28A2C5C0C05C39E`；删tag后`docker load`恢复同一ID。
- 边界：平台真实模型服务、SwanLab、官方试运行和隐藏评分均未执行；该记录不含性能结论。

## FORMAL-PERF-001-A1预注册

- 状态：`COMPLETED_MIXED_INTEGRATED`。
- 研究问题：在不改变官方`contest.cpu-mlp.v1`schema、不读取公开validation/历史confirmation的前提下，train内部证据能否从`retain / e1_lr1 / e3_lr3 / soup_e3_alpha0.25`中稳定选择比固定1 epoch更好的父链兼容recipe。
- 数据：官方A/B/C训练包只读；仅`public/train.jsonl`。数据指纹在运行产物中记录；`public/validation.jsonl`读取次数固定为0。
- 切分：三折。可从ID可靠提取设备/轨迹组时按组分折；否则分类按类别分层确定性分折、回归按样本ID哈希确定性分折。任何样本不跨train/holdout。
- 对照：retain与1 epoch×原学习率；候选为3 epoch×3学习率和3 epoch后参数0.25父候选融合。所有候选保持父预处理、架构、类空间和checkpoint字段。
- 指标：A Macro-F1/Accuracy；B/C RMSE/MAE；同时记录CPU时间、折数、样本数、recipe胜出次数和最差折相对退化。
- 预算：本机CPU，最多A/B/C各4个recipe×3折；不调用PyTRiO/SwanLab，不构建新镜像，不使用官方试运行。墙钟上限20分钟，异常或非有限值立即停止该recipe。
- 种子：`20261117`；分折只由不可逆ID哈希、标签/组和该种子决定。
- 成功标准：每任务选择的recipe相对retain平均有向收益为正、至少2/3折不劣于retain，且最差折相对退化不超过5%；若复杂recipe未超过e1则保留e1，不为追求复杂度晋级。
- 预期输出：`D:/brace-msi-first-principles-performance/FORMAL-PERF-001-A1/`中的JSON、资源记录和数据指纹；失败与负结果同样保留。
- 结果：A选择`e1_lr1`，3折平均Macro-F1有向增益`+0.004902644`、2/3折不劣；B所有续训recipe均在跨轴承组留出退化，选择retain；C选择`soup_e3_alpha0.25`，3/3折改善、平均RMSE降低`0.189824503`。
- 资源：A/B/C总CPU约`0.125/0.688/11.25`秒；公开validation读取0；在线模型、SwanLab和官方次数均0。摘要SHA-256 `FE5158C0EE76A6179E7641195E9CC394105F0E00AA2389279F81A31787B08968`。
- 集成：正式每轮仅在Agent选择train时运行同一train内部portfolio；只有内部证据通过成功门的recipe才形成候选。若证据选择retain，则将Agent训练提案记录为`train_vetoed_by_internal_cv`并保留父模型，不能用一次宿主建议覆盖三折负证据；最后仍由当前官方validation门控。完整折明细不写入持久状态，只保存紧凑摘要。

## FORMAL-PERF-001-A2/A3正式候选集成

- A2状态：`SUPERSEDED_UNSAFE_FALLBACK`。`0.10.1`在训练内部选择retain时仍执行Agent的e1建议；该行为被新增回归测试捕获，产物和诊断保留但不得上传。
- A3状态：`COMPLETED_FINAL_LOCAL_RC`。修复后训练内部retain拥有否决权；B十轮全部记录`train_vetoed_by_internal_cv`，不生成候选。A第1轮部署e1、C前三轮部署0.25父候选soup；其余轮次由当前Gate拒绝或训练内证据retain。
- 数据与选择：recipe选择只读取官方train内部三折；公开validation在策略、参数和轮次冻结后每任务只读取一次作描述性诊断，不能反向选择。
- 公开暴露诊断：A Macro-F1 `0.714030 → 0.725695`；B RMSE保持`681.159833`；C RMSE `52.868573 → 52.331755`。不是隐藏测试或官方成绩。
- 协议与资源：A/B/C各10轮、30个唯一宿主call ID、15行独立预测；最大checkpoint 132,180字节；portfolio累计CPU约0.743/3.927/28.980秒。
- 机器证据：`D:/brace-msi-first-principles-performance/FORMAL-PERF-001-A3-FINAL-CONTAINER/acceptance.json`，SHA-256 `B8D613065EE92BC5CD0786745D74D2F4FD3A7AD8E3D884D7FD1641A54739687B`。
- 冻结归档：`D:/brace-msi-first-principles-release/BRACE-MSI-0.10.2rc1-FINAL/harness.tar`，81,205,248字节，SHA-256 `1F4B4C70061E2228977A98984ED3DF8D6E4C691E23D35DB95517A83173C5C6C0`；删除tag后重载为同一镜像ID。
- 验证：`458 passed in 143.01s`；`pip check`、白名单、非root、4核8GB断网、64MiB和`docker save/load`通过。PyTRiO私有API、SwanLab、平台上传及官方次数均为0。

## FORMAL-AUDIT-FIX-001-A1至A5终审修复验收

- 状态：A1/A2/A3为失败或被替代的调试证据；A4为预最终镜像验收；A5为`COMPLETED_FINAL_LOCAL_RC`。全部历史目录保留，不用A4冒充最终镜像。
- 目标：验证平台测量权威门、真实执行声明、独立组不足retain、dataset工作区隔离、父哈希报告和只读容器范围。
- A5机器结果：`D:/brace-msi-first-principles-performance/FORMAL-AUDIT-FIX-001-A5-FINAL-CONTAINER/acceptance.json`，SHA-256 `6AB82222A3C015F42B07315A103E749CEAF2B8D9FA15D999F75281FB41DBDF35`，`valid=true`。
- A5结果：A/B/C各10轮、各10个宿主call ID、各5行独立预测；候选数A/B/C为1/0/3；最大checkpoint 132,180字节。
- 验证：项目完整回归465项；官方SDK Linux离线15项通过、2项在线测试因缺少官方凭据按条件跳过；`pip check`、linux/amd64、UID10001、4核8GB、断网、只读根、白名单及`docker save/load`同ID通过。
- 冻结归档：`D:/brace-msi-first-principles-release/BRACE-MSI-0.10.3rc1-FINAL/harness.tar`，81,206,272字节，SHA-256 `D08535F0B4A410A9EFF6CBB191505F32B767462B3E42CDC6093E8ABC385CA86A`。
- 外部使用：PyTRiO私有API、SwanLab、平台上传和官方试运行均为0；下一步只允许受控平台验证。

## SELECTION-RELIABILITY-001-A1（COMPLETED_PASS_CODE_ONLY）

- 研究问题：在不改变训练recipe、父checkpoint schema、官方SDK和双Qwen调用次数的前提下，能否消除指标方向错误、数值关系与部署字段冲突、跨作用域历史选优和硬门后提交风险，并生成可用于后续泛化矩阵的可信收据？
- 输入：O-PLATFORM-019冻结反例摘要；现有`brace_formal`代码和单元测试；本地构造的相同/不同validation指纹、合法/非法Qwen结构化决策和硬门失败产物。不读取隐藏标签，不重开公开validation。
- 变量：唯一`MetricContract`、确定性有向收益与关系、验证作用域指纹、结构化部署可行集合、state v2产物血缘、硬门前置和聚合阶段计时。训练recipe、epoch、学习率、父模型、SDK、预测入口和调用次数保持不变。
- 预算：先只运行专项单元测试和完整代码回归；本阶段官方试运行0次、PyTRiO远程0次、SwanLab同步0次、正式训练0次。
- 成功标准：冻结反例的指标方向判断100%正确；`macro_f1+lower`、`rmse+higher`和未知不兼容组合失败关闭；不同作用域不得选历史最佳；Qwen矛盾deploy保留父模型；硬门失败不调用`submit_candidate`；计时字段完整且不含原始数据/prompt；完整回归通过。
- 停止条件：若修复必须改变recipe、训练数值、父链、官方SDK或读取公开确认集，则停止A1并拆分任务；不得在本阶段生成上传镜像。
- 结果：MetricContract、同作用域有向收益、requested/applied部署事实、NaN失败关闭、state v2血缘、显式NASA合同和脱敏阶段计时均完成。正式运行核50项、全量487项通过；独立复审无剩余P0/P1。提交`afa9038`。
- 资源与边界：未运行模型训练、远程PyTRiO、SwanLab同步、Docker构建、官方上传或试运行；不得把本结果写成性能或平台通过。

## GENERALIZATION-MATRIX-001-A1（COMPLETED_PASS_ZERO_TRAINING_REPLAY）

- 研究问题：四种身份无关的选择策略能否在不训练模型、不读取公开确认集的前提下，正确处理O-PLATFORM-019已确认的三类错误部署，并保持作用域、恢复能力和资源预算边界？
- 冻结输入：O-PLATFORM-019中已核实的Gas第5轮、Bearing第2轮和Engine第4轮父/候选主指标关系；原始报告只以已登记SHA-256引用，不在本实验重新解释未确认轮次。
- 策略：`strict_parent_gate`、`bounded_exploration`、`conditional_champion`、`recipe_feedback`。四者共享有向收益、验证作用域、候选可加载性、历史产物可恢复性和显式探索预算；禁止读取数据集名称决定动作。
- 成功标准：三条已确认退化候选在严格门下100%不部署；历史冠军仅在同作用域且产物可恢复时可选；有限探索仅在显式容忍度、剩余预算和可回滚条件同时满足时允许；性能退化只产生有限冷却，硬失败才永久隔离recipe；任务重命名不改变结果。
- 停止条件：任何跨作用域比较、不可恢复产物选择、非有限指标放行、按任务名称分支或预算外探索立即判该策略失败，不进入训练矩阵。
- 预算与边界：CPU单元测试与纯JSON重放；训练0次、公开validation/confirmation读取0次、PyTRiO远程0次、SwanLab同步0次、官方试运行0次。
- 预期产物：`D:/brace-msi-generalization/GENERALIZATION-MATRIX-001-A1/decision-replay.json`和仓库内脱敏结果摘要；失败结果同样保留。
- 结果：三条已确认退化反例在`strict_parent_gate`下3/3保留父模型；四策略在冻结反例上均未部署退化候选。作用域、可恢复冠军、有限探索、非有限值和recipe有限冷却共11项测试通过。
- 机器证据：`D:/brace-msi-generalization/GENERALIZATION-MATRIX-001-A1/decision-replay.json`，SHA-256 `CDD3D5C98BE12F899E85C207AAD9D3C714659ECF191AD51D66D6616B6516C170`；训练、公开确认读取、PyTRiO远程、SwanLab同步和官方试运行均为0。

## GENERALIZATION-MATRIX-001-A2（COMPLETED_NEGATIVE_NO_PROMOTION）

- 研究问题：在相同父checkpoint、相同合法十轮流和相同身份无关候选recipe下，严格父子门、有限探索、当前作用域重评历史模型、recipe有限反馈中，哪种策略能同时改善三任务平均到达表现、最差阶段与恢复速度，而不引入灾难性退化？
- 数据：只读`OFFICIAL-FLOW-SIM-001-A2/{A,B,C}/runtime-inputs/round-01..10`中的Update/Gate/feedback；禁止访问其`confirmation`目录。A按自然批次/时间、B按轴承寿命阶段、C按完整unit构造；这些是已登记的本地代理流，不冒充官方隐藏生命周期。
- 父模型：官方训练包A/B/C原始`checkpoint.npz`；不得从历史最佳或公开validation选择起点。
- 候选：每轮至少训练一个真实原生MLP候选；候选集合只由任务类型、已开放Update历史、延迟收益和趋势证据生成，最多两种，来自`current_e1 / soup_current_e3_alpha0.25 / recent_e3 / current_e3_lr3 / cumulative_e3_lr0.3`。禁止按A/B/C名称选动作。
- 四策略：`strict_parent_gate`只部署当前Gate严格改善候选；`bounded_exploration`仅在候选硬合法、父模型可恢复、尚有预算且回退幅度不超过分类0.002或回归父指标1%时探索；`conditional_champion`只在当前Gate重新评价可恢复历史模型后比较；`recipe_feedback`对性能退化冷却2轮、对训练/产物硬失败永久隔离。
- 延迟收益与回滚：第t轮部署候选后，第t+1轮在同一到达批次同时评价候选和直接前任；候选变差时先恢复直接前任，再执行本轮训练。第10轮仍训练和作Gate决策，但没有伪造下一轮延迟收益。
- 指标：A Macro-F1/Accuracy；B/C RMSE/MAE；报告每策略每任务平均/最差到达有向收益、胜率、负阶段数、回滚数、恢复轮数、候选/部署数、CPU、墙钟、RSS、Token=0、checkpoint大小。自然滚动转换作为多起点，目标/指标变化幅度作为观察到的漂移强度，不合成额外隐藏分布。
- 成功标准：三任务平均有向收益均非负且至少两个为正；任一任务最差相对退化不超过其静态指标5%；零未来/confirmation读取、零跨作用域选优、所有checkpoint可加载且小于64 MiB。至少一策略在三任务聚合和最差任务上优于当前正式严格策略才可晋级。
- 停止条件：检测到确认集访问、未来轮访问、身份硬编码、非有限指标、父链不可加载或任一任务超过5%灾难性退化，立即停止对应策略并保留失败证据。
- 资源：本机CPU；每策略×任务10轮、每轮1—2候选；单策略墙钟上限20分钟，总矩阵上限60分钟。PyTRiO远程、SwanLab同步、Docker和官方试运行均为0。
- 预期输出：`D:/brace-msi-generalization/GENERALIZATION-MATRIX-001-A2/`，不得覆盖A1和既有流。
- 结果：12/12策略—任务运行均完成，每轮均训练真实候选；但四策略全部因B最差阶段超过5%灾难门而不得晋级。严格门A/B/C平均有向收益为`+0.313085 / -10.860323 / +0.128450`；recipe反馈为`+0.313085 / +29.449707 / +0.524004`，但B最差相对退化`-109.33%`。
- 诊断：B代理流不同轴承的绝对RUL尺度交替，当前单组Gate与下一阶段分布不一致；当前策略在第7或第9轮把单组Gate高收益候选部署后，下一批出现大幅负延迟收益。该结果不能证明官方隐藏B必然失败，但足以淘汰A2本地候选。
- 机器证据：`D:/brace-msi-generalization/GENERALIZATION-MATRIX-001-A2/summary.json`，SHA-256 `517AA24C2064A1231A13D06A27CDD7458E50262CE671BB52C070DDEB8C138223`。JSON中的`valid=true`仅表示执行完整；晋级门为0/4通过，后续runner显式增加`promotion_pass`字段。

## GENERALIZATION-MATRIX-001-A3（INVALID_EVIDENCE_ID_MISMATCH）

- 唯一变更：当回归任务已开放Update目标均值跨度/父`target_scale ≥ 1.0`、无负延迟收益且失败连续少于2轮时，把`current_e3_lr3`加入第二候选。该条件只依赖任务契约和已开放数值证据，不接收A/B/C或数据集名称。
- 依据：A4连续父链中B的`current_e3_lr3`在9/9相邻未见阶段优于静态，平均RMSE降低287.436；A2的B已开放目标跨度约1.79，而C约0.47，因此该门预期只处理高尺度异质回归，不改变C保守路线。
- 其余冻结：A2四策略、父checkpoint、十轮流、每轮训练、Gate、延迟收益、回滚、预算、指标、5%灾难门和零confirmation/官方调用全部不变。
- 成功标准：至少一个策略三任务平均有向收益均非负、至少两个为正、无任务最差相对退化超过5%；否则淘汰该触发条件，不再调阈值。
- 输出：`D:/brace-msi-generalization/GENERALIZATION-MATRIX-001-A3/`，不得覆盖A1/A2。
- 运行结果：有限探索和条件冠军的三任务数值均通过预注册性能门，但`summary.json`内部`experiment_id`仍硬编码为A2，因此A3只保留为趋势证据，不作为冻结机器证据。

## GENERALIZATION-MATRIX-001-A4（COMPLETED_TECHNICAL_AUDIT_BLOCKED）

- 唯一修复：`experiment_id`必须从不可为空的输出目录名取得，并由单元测试覆盖。
- 算法、数据、父checkpoint、四策略、尺度异质触发、候选、预算、阈值、成功门和零confirmation/外部调用全部逐项继承A3，不允许其他变更。
- 输出：`D:/brace-msi-generalization/GENERALIZATION-MATRIX-001-A4/`；A3保持只读。
- 结果：12/12策略—任务链完成、120/120轮均训练真实候选。原始机器门将有限探索与条件历史冠军标为通过，但独立复审确认该结论不能用于晋级：有限探索在第10轮仍错误声称可用下一轮延迟收益回滚；条件历史冠军没有验证正式artifact持久化和恢复。A4是有效技术运行证据，不是稳定泛化通过证据。
- 有限探索A/B/C平均有向收益：`+0.312990 Macro-F1 / +89.198667 RMSE降低 / +0.173614 RMSE降低`；全局最差相对退化`-1.3983%`，0个灾难任务。
- 条件历史冠军A/B/C平均有向收益：`+0.313085 / +63.414421 / +0.147862`；B十轮最差收益0、全局最差相对退化同为`-1.3983%`，0个灾难任务。
- 资源：完整矩阵墙钟42.17秒，各策略累计CPU约2.23—3.38秒，峰值RSS每任务不超过约152 MiB，Token=0；checkpoint 28,848—132,184字节且均可加载。
- 机器证据：`D:/brace-msi-generalization/GENERALIZATION-MATRIX-001-A4/summary.json`，SHA-256 `AB1870F5710CF9499B13B17D4466ABF5FEA9946A4E8E31F28F14DAEE69FFFB31`。

## GENERALIZATION-MATRIX-001-A5（COMPLETED_TECHNICAL_AUDIT_BLOCKED）

- 研究问题：在不改变A4数据、候选recipe、训练参数和选择阈值的前提下，修正末轮不存在延迟回滚证据、输入路径未失败关闭、最终checkpoint未入晋级门和历史冠军artifact未证明恢复的缺陷后，是否仍有策略超过严格父子门？
- 唯一允许变更：第10轮不允许`bounded_exploration`依赖不存在的下一轮回滚；输入只允许已物化的`feedback/update/gate`且拒绝越界或符号链接；记录Update/Gate样本数；晋级门检查最后一轮选择安全、每轮真实训练、零confirmation读取并且不劣于`strict_parent_gate`聚合值/最差值。`conditional_champion`在正式artifact持久化与恢复未验证前固定不得晋级。
- 冻结项：官方A/B/C父checkpoint、A4同一代理十轮流、四策略、候选recipe、尺度异质触发、阈值、CPU预算、指标方向和零外部调用。不读取confirmation/public validation，不使用官方试运行。
- 成功标准：12条链、120轮都完整；末轮不部署退化探索候选；所有路径与样本数可审计；至少一个非冠军策略在三任务平均收益均非负、至少两项为正、无5%灾难退化，且聚合相对收益和最差相对收益均不劣于严格父子门。
- 停止条件：任何路径逃逸、第10轮虚假回滚、最终退化候选仍部署、不可加载checkpoint、非有限指标或任一任务超过5%灾难门时该策略不得晋级；不继续调阈值。
- 资源：本机CPU，预计不超过60分钟；PyTRiO远程、SwanLab同步、Docker和官方试运行均为0。
- 预期输出：`D:/brace-msi-generalization/GENERALIZATION-MATRIX-001-A5/`，不覆盖A1—A4。
- 结果：12/12策略—任务链、120/120轮真实候选完成，无运行失败。`bounded_exploration`是唯一通过修正后机器门的策略；A/B/C平均有向收益为`+0.312990 / +89.198667 / +0.173614`，最差相对收益`-1.3983%`，0个5%灾难任务。
- 末轮验证：B/C第10轮候选退化时均保留父模型，未消耗探索预算；12条链的`final_selection_safe=true`。`conditional_champion`即使数值正向也因正式artifact恢复未验证而`promotion_pass=false`。
- 资源与边界：矩阵墙钟42.27秒；各策略累计CPU约2.33—3.03秒；confirmation/public validation读取0，PyTRiO、SwanLab和官方试运行均为0。A5仍是用于形成尺度异质触发条件的同一开发代理流，只能产生开发候选，不是独立泛化或正式RC准入证据。
- 独立复审：本次实际目录未发现reparse point，因此没有实际泄漏证据；但runner先`resolve()`再检查链接，同根symlink/junction可绕过输入边界。同时晋级门只检查末轮选择安全，没有把重新加载的最终checkpoint状态与选中模型绑定。因此A5数值保留，但不得作为开发候选晋级证据。
- 机器证据：`D:/brace-msi-generalization/GENERALIZATION-MATRIX-001-A5/summary.json`，SHA-256 `9903249414FE93D6B4708A348D7E00CDF2DC73F0E9F683BB4C52FED55070B252`。

## GENERALIZATION-MATRIX-001-A6（COMPLETED_DEVELOPMENT_CANDIDATE）

- 唯一修复：在解析路径前拒绝`runtime-inputs`根和轮目录的symlink/junction，并用对抗测试覆盖同根链接；最终模型保存前计算选中内存状态指纹，重新加载后比较全部参数、Adam一/二阶矩、预处理、元数据和末轮Gate预测，且`promotion_pass`必须检查该绑定。
- 冻结项：A5数据、父checkpoint、候选recipe、选择策略、预算、阈值、指标和成功标准均不变；不读取confirmation/public validation，不调用PyTRiO/SwanLab，不使用官方试运行。
- 成功标准：三类真实symlink/junction对抗测试通过；12条链的`final_checkpoint_verified=true`；该字段缺失或为false时晋级门必须失败；A5其余数值趋势可复算。
- 预期输出：`D:/brace-msi-generalization/GENERALIZATION-MATRIX-001-A6/`，不覆盖A1—A5。
- 结果：12/12策略—任务链、120/120轮真实候选完成；所有最终checkpoint重新加载后的全状态指纹与末轮Gate预测都与选中内存模型一致，12/12`final_checkpoint_verified=true`。
- 策略结果：`bounded_exploration`为唯一`promotion_pass=true`的开发候选，A/B/C平均有向收益`+0.312990 / +89.198667 / +0.173614`，最差相对收益`-1.3983%`，0个5%灾难任务。历史冠军仍因artifact恢复未验证而不得晋级。
- 安全证据：内部目录symlink、`runtime-inputs`根symlink和Windows junction三类对抗测试均先红后绿；A6实际输入根的reparse point为0。
- 资源与边界：墙钟42.41秒；confirmation/public validation读取0，PyTRiO、SwanLab和官方试运行均为0。A6只是开发流候选，仍需D-088规定的方法冻结后独立替代流/任务留出验收。
- 机器证据：`D:/brace-msi-generalization/GENERALIZATION-MATRIX-001-A6/summary.json`，SHA-256 `BA850904FFE1A839CD839F87C0F6999A53751FE786E5BC12296A8E9F6B126F68`。
- 独立复审：修复后无剩余技术P0/P1；只批准`bounded_exploration`作为开发候选，不把A6视为独立泛化或正式RC证据。

## PERFORMANCE-METHOD-PILOT-001-A1（COMPLETED_MIXED）

- 目的：在不改变`contest.cpu-mlp.v1`结构和父链语义的前提下，筛选能改善相邻未见阶段的低成本训练目标与校准方法；先看趋势，不直接进入正式镜像。
- 数据范围：只使用冻结代理流第`t`轮已开放feedback/update训练，并在`t+1`轮未见feedback评价；不读取confirmation/public validation，不消费官方试运行。
- 候选上限：分类比较原生近期回放、类平衡交叉熵和类先验偏置校准；回归比较原生高强度/权重插值、Huber、有限近期回放、轻量NASA方向非对称Huber和训练内稳健偏差校准。每类最多6个方法，不做开放式HPO。
- 共享约束：方法只由任务契约（分类/回归及指标方向）启用，不按A/B/C名称选动作；保留原参数形状、Adam状态字段、标准化、epoch/step和可加载性；非有限值或任一连续父链出现5%灾难退化即淘汰。
- 成功标准：至少一项方法相对现有开发基线同时改善平均有向收益或C的RMSE/NASA趋势，且最差阶段和CPU成本不恶化到门外；否则保留A6的`bounded_exploration`与既有recipe，不集成新方法。
- 预期输出：`D:/brace-msi-performance-pilot/PERFORMANCE-METHOD-PILOT-001-A1/`及仓库内脱敏摘要；失败和混合结果同样登记。
- 结果：分类`balanced_current_e3`平均/最差Macro-F1收益`+0.399821/+0.023635`，优于`native_recent_e3`的`+0.386974/+0.017072`且CPU更低；两者同时改变训练范围和损失，因此只证明复合候选趋势，不证明类平衡单因素因果有效。B的非对称Huber改善最差RMSE和NASA但平均RMSE略逊；C所有新稳健方法均未超过既有25%权重插值。
- 机器证据：摘要SHA-256 `98C75FB2A992BCC6068486E73219E8E29EB85B30DABE83683FC4836AF4A95E2F`。

## PERFORMANCE-METHOD-PILOT-001-A2（COMPLETED_NEGATIVE）

- 触发证据：A1中C的原生`soup_current_e3_alpha0.25`仍是RMSE与NASA综合最优；将Huber、非对称Huber和偏差校正同时组合后反而变差，不能判断偏差校正单因素是否有效。
- 唯一变量：在同一25%权重插值候选之后，仅当当前训练数据的稳健中位预测误差显示RUL过估时，对输出偏置作向下修正并清零该偏置的Adam一/二阶矩；比较固定强度0.10与0.25，不改变其他参数、数据、父链和选择规则。
- 数据与边界：复用A1冻结的C相邻未见开发流，runner通过`--profiles C`限定本次研究范围；方法函数本身未接收MetricContract，不把它表述为正式`rmse_nasa`契约路由。不读取confirmation/public validation，不调用PyTRiO/SwanLab，不消费官方试运行。A2仍是同一开发流证据，不是独立泛化。
- 成功标准：相对未校正soup，C平均RMSE有向收益和NASA改善率至少一项提高，另一项不得退化超过1%，最差阶段不得扩大到5%灾难门；否则永久淘汰该校正。
- 预期输出：`D:/brace-msi-performance-pilot/PERFORMANCE-METHOD-PILOT-001-A2/`，不覆盖A1。
- 结果：0.10/0.25向下偏差校正均降低C的平均RMSE收益、NASA改善率和最差阶段，方法淘汰。
- 机器证据：摘要SHA-256 `EAC9D9752E97588F8909C0760526AB91A0D07EAFE7CEC2FC41C21C14EF7E4820`。

## PERFORMANCE-METHOD-PILOT-001-A3（INVALID_NEGATIVE_NO_PROMOTION）

- 目的：把A1单因素结果放入A6已经通过技术门的四策略十轮矩阵，验证候选质量与选择/回滚能否协同，而不是用单方法连续强制部署结论替代Harness。
- 身份无关路由：分类使用`balanced_current_e3`与既有`native_recent_e3`；回归目标均值范围相对父`target_scale`至少1时使用`native_current_e3_lr3`与`asymmetric_current_e3_lr3`，否则使用既有`soup_current_e3_alpha0.25`与`huber_recent_e3`。路由不读取profile名称。
- 冻结项：沿用A6数据、四选择策略、预算、门控、延迟回滚、路径边界和最终checkpoint验证；不采用A2失败的偏差校正，不改变指标或阈值。
- 成功标准：开发候选在A/B/C均无5%灾难退化、三任务平均有向收益非负、至少两任务为正；整体平均相对收益、最差相对阶段、CPU和checkpoint验证不劣于A6的`bounded_exploration`。否则仅保留单因素证据，不进入正式策略。
- 边界：同一开发代理流，不是D-088独立验收；confirmation/public validation、PyTRiO、SwanLab、官方试运行均为0。
- 预期输出：`D:/brace-msi-performance-pilot/PERFORMANCE-METHOD-PILOT-001-A3/`，不覆盖A1/A2。
- 结果：B最差相对阶段`-5.9527%`超过灾难门；recipe反馈C分支因方法冷却后的跨族回退执行失败，suite `valid=false`。数值和失败均保留，不晋级。
- 机器证据：摘要SHA-256 `2EC495B4DCAB7EA1789EC101F90A0B0DACA225E029D27EEDE32921240D13113F`。

## PERFORMANCE-METHOD-PILOT-001-A4（COMPLETED_DEVELOPMENT_CANDIDATE）

- 触发证据：A3证明把A1全部回归方法直接替换进十轮策略会使B出现5.95%最差阶段退化，且recipe反馈分支因新方法冷却后回退到旧`current_e1`而执行不完整；A3按无效/负结果保留，不晋级。
- 唯一方法变更：只把A1中稳定正向的分类`balanced_current_e3 + native_recent_e3`候选接入；所有回归候选、选择策略、阈值、预算、数据和checkpoint门精确恢复A6语义。recipe反馈无可用新候选时回退到当前方法组合首项，不跨方法族。
- 成功标准：A的平均/最差相对收益优于A6；B/C数值可复算为A6基线或仅有计时噪声；12条链完整、无5%灾难、最终checkpoint 12/12绑定、开发晋级门通过。
- 边界：同一开发代理流，不是独立泛化；confirmation/public validation、PyTRiO、SwanLab、官方试运行均为0。
- 预期输出：`D:/brace-msi-performance-pilot/PERFORMANCE-METHOD-PILOT-001-A4/`，不覆盖A1—A3。
- 结果：120/120轮、12/12最终checkpoint绑定、0个5%灾难任务；A平均有向收益`0.312990→0.360481`且最差相对收益`-0.5470%→0`，B/C checkpoint与A6相同；`bounded_exploration`开发门通过。
- 机器证据：摘要SHA-256 `4237A9F445E2E42456D3FD434B579D246046274A0B956278E36D764E110637BD`；不替代D-088独立留出。
- 独立复审：无技术P0；B/C四策略8条链及checkpoint与A6逐项一致。唯一P1为禁止把复合候选收益归因于类平衡单因素，文档已修正；无需A5重跑。

## PYTRIO-ADVISOR-OPT-001-A1（REGISTERED）

- 目的：在不训练新Sampler前，使用正式`brace_formal.agent.request_deployment_decision`提示与冻结脱敏反例，检验基础`Qwen/Qwen3.5-4B`的JSON结构有效率、指标方向/数值关系正确率、硬风险一致性、Token、延迟和费用证据。
- 数据：仅使用合成聚合指标与已登记反例的数值形态；不包含工业逐样本特征、标签、数据集名称、隐藏数据、公开confirmation或凭据。分类/回归均覆盖改善、退化、持平、硬风险与历史场景。
- 预算：基础模型每个冻结场景恰好一次temperature=0调用；不重试以免选择性重采样；输出长度仅采用现有研究客户端的已验证JSON上限，不改变正式镜像或平台调用限制。官方试运行0次。
- 成功标准：全部调用有非零Token收据；schema有效率至少95%；所有候选明确退化或硬风险场景均不得建议deploy；总体预期决策正确率至少90%。任一安全关键错误，或至少两个同类结构/数值错误，判定存在系统性缺陷并进入A2有界SFT；否则保留基础模型，不训练新Sampler。
- 产物：`D:/brace-msi-pytrio/PYTRIO-ADVISOR-OPT-001-A1/`，仅保存case ID、提示/响应哈希、结构化决策、错误类别、Token、延迟和聚合统计；原始响应与提示不落盘。
- SwanLab：A1完成后仅从脱敏聚合摘要生成离线记录；通过敏感扫描后才允许显式同步。正式镜像保持无PyTRiO/SwanLab/Tokenizer/Sampler/密钥。
- 结果：`COMPLETED_BASE_FAILED`。12/12响应均为严格schema且Token非零，但精确预期决策仅6/12；两个“候选指标更好但存在硬安全失败”的场景仍建议deploy，触发安全关键失败门。输入/输出Token为4,337/323，总采样延迟7.00秒；结果SHA-256 `61D7FC88F568E24A44F6B23A3736464A1A75F5567397C413EA0E8E98906CE6CB`。按预注册进入A2。

## PYTRIO-ADVISOR-OPT-001-A2（REGISTERED）

- 目的：针对A1已证实的硬风险忽略与数值决策不稳定，训练一个镜像外、只负责正式deployment JSON的Qwen3.5-4B LoRA Sampler；不修改工业模型、正式Harness或平台调用协议。
- 语料：24条训练和12条全新留出，均为身份无关的合成聚合指标场景；使用与正式`request_deployment_decision`逐字同源的提示，训练/留出数值与A1冻结反例不重合。assistant-only loss，prompt权重0，completion及EOS权重1。
- 固定训练：Qwen3.5-4B、rank 8、3 epoch、batch 4、learning rate `1e-4`、固定seed；18个远程优化步。训练前固化语料哈希；不依据训练loss提前选择轮次或追加搜索。
- 成功标准：持久化`trio://` Sampler成功；新留出schema有效率100%、硬风险安全率100%、总体决策正确率至少90%，并严格优于同一留出基础模型；否则保留基础模型和确定性Harness，不采用Sampler。
- 预算/边界：累计费用上限10元，官方试运行0次；不含原始数据、隐藏标签、公开confirmation、API Key或逐样本信息。原始失败与负结果均保留。
- 预期产物：`D:/brace-msi-pytrio/PYTRIO-ADVISOR-OPT-001-A2/`与脱敏聚合SwanLab离线记录。
- 结果：`COMPLETED_EXTERNAL_CANDIDATE`。18/18远程优化步完成，最终监督Token损失`0.001425805`；同一全新留出上基础Qwen的schema/decision/safety/policy为`100%/66.67%/91.67%/66.67%`，新Sampler为`100%/100%/100%/100%`并通过采用门。持久化Sampler重新创建客户端复评仍四项100%。结果SHA-256 `E192DB1FE667087F9D104971B18E30868AF5A62A5BEC38BB2595227A6703B5DF`；重载摘要SHA-256 `179F6BEC8CA28AC163F36F79D994990E0BEA0956D4D0D7D95B8A28B849CCC09D`。
- 记录：SwanLab公开聚合运行`https://swanlab.cn/@nanmo-max/BRACE-MSI/runs/k4jvqkuj`；仅20条训练step/评估聚合记录，spool SHA-256 `6FBB96626BE8E829C9BC0C469C25A43D3D23B28EEEB836923182D247D51BF694`，密钥、`trio://`、原始提示/响应、父候选指标对象、特征和标签扫描零匹配。首次sync在远端创建后因Windows GBK打印emoji中止，随后以同一run ID和UTF-8确认上传完成；未重复创建正式记录。
- 边界：Sampler路径保存在本地受控产物中用于平台提交页校验，不进入Git或镜像；比赛提交页尚未验证该新Sampler，因此只标记镜像外候选。官方试运行使用0次。

## FINAL-GENERALIZATION-VALIDATION-001-A1（COMPLETED_INVALID_PROTOCOL_AND_FAIL_GATE）

- 研究问题：冻结的`bounded_exploration`选择策略及A6原生回归recipe，在一个没有参与阈值、recipe或方法选择的真实工业退化任务上，能否同时保持平均收益、最差阶段与资源安全，并在一次性密封轴承留出上优于同源静态父模型？
- 数据：XJTU-SY固定9/3/3轴承切分。9个初训轴承建立静态父模型；3个开发轴承仅按各自寿命进度形成10轮开发流；`Bearing1_5/Bearing2_5/Bearing3_5`在本条登记时尚无特征缓存，全部开发决策冻结后才允许一次性提取并仅作预测确认。
- 冻结实现：父模型为`contest.cpu-mlp.v1`回归MLP，hidden=32、30 epochs、lr=0.003、batch=32、seed=20261120；每轮80% Update/20% Gate；策略为`bounded_exploration`，总探索预算2，回归容忍度为同Gate父RMSE的1%；回归候选沿用A6的身份无关`_candidate_recipes`与`fit_native_recipe`，不启用A4分类复合方法。
- 冻结验收：开发流平均有向收益不低于0、最差相对收益不低于-5%；密封全局RMSE和MAE均不劣于静态父模型，至少2/3密封轴承RMSE改善，最差单轴承相对收益不低于-5%；CPU<=600秒、墙钟<=900秒、RSS<=8GiB、checkpoint<=64MiB；样本ID三分区零交叉，最终checkpoint保存加载预测一致。
- 一次性边界：打开密封数据后不得修改阈值、recipe、模型结构或本条验收标准；失败只允许保留既有Protocol RC或回退冻结A6，不得针对密封结果继续调参。公开validation/confirmation读取0次、官方试运行0次、PyTRiO远程0次、SwanLab同步0次。
- 预期产物：`D:/brace-msi-final/FINAL-GENERALIZATION-VALIDATION-001-A1/summary.json`、一次性打开锁、密封派生缓存清单、开发轮收据、静态/候选密封预测指标和仓库内脱敏结果摘要。
- 结果：开发10轮、16候选、10部署、2回滚；平均RMSE有向收益`+188.967744`，但最差相对收益`-99.61%`，未通过冻结的最差阶段门。密封全局RMSE `243.718016→220.922262`、MAE `184.328347→168.207564`，2/3轴承改善，最差轴承退化2.04%；资源、泄漏和checkpoint门通过。
- 判定：机器promotion=false并直接失败`development_worst_relative_gain_min`；独立审查进一步发现开发延迟收益复用当前Gate、A1峰值RSS和恢复未验证。密封最终预测只保留描述性证据；根据D-091不晋级、不重跑、不基于密封结果调参。摘要SHA-256 `22D4143B53074CE6A3CF8C913937157EE42403400FA462E0C2AE66ACEF38AA05`。

## COMPETITION-CORE-SMOKE-001（REGISTERED）

- 目的：验证Competition Core模拟器能以官方`contest.harness.workspace.v2`的Round/RPC对象完成分类与回归各10轮、每轮两次宿主模型调用、一次真实父checkpoint候选训练、同作用域选择、状态/历史/父链和冻结后一次确认预测。
- 数据：由`configs/competition_simulation.json`固定seed生成的两个身份不透明同格式代理任务；仅用于协议与报告Smoke，不是官方A/B/C、隐藏数据或独立性能证据。
- 隔离：确认分区在十轮结束前不读取，确认哈希不进入任何轮收据或Agent上下文；正式上传镜像不包含模拟器、代理数据、报告或测试工具。
- 成功标准：两任务各10轮、20次模型调用、10个真实候选、11节点父链、32/48条最终预测（按配置），报告`valid=true`，JSON与HTML同源并明确标注非官方成绩。
- 资源与外部调用：本机CPU；PyTRiO远程、SwanLab同步、官方试运行和平台上传均为0。模型Token为本地宿主替身的协议计量，不冒充PyTRiO或平台结算。
- 输出：`D:/brace-msi-competition/COMPETITION-CORE-SMOKE-001/`，若目录已存在则失败关闭，不覆盖历史产物。
- 结果：`COMPLETED_VALID_PROTOCOL_SMOKE`。分类/回归各10轮、20次模型调用、10个真实候选、10条历史和11节点父链；最终预测各48条，确认分区各读取一次。
- 代理确认指标：分类Accuracy `0.812500`、Macro-F1 `0.805480`；回归MAE `0.351059`、RMSE `0.504862`。这些数值只验证合成任务链路，不是官方A/B/C、隐藏成绩或新独立泛化证据。
- 机器证据：`D:/brace-msi-competition/COMPETITION-CORE-SMOKE-001/report.json`，SHA-256 `D7EBB3E3A814D12E28163085EF7BF141E07AFA68895EE51515A8D97E3BD180B8`；同目录`report.html`由该JSON生成。

## COMPETITION-CORE-EXP-001（REGISTERED）

- 研究问题：在不使用官方隐藏数据或平台次数的前提下，Competition Core的身份无关注册recipe与同作用域选择，相对静态父模型和每轮固定更新，能否同时改善官方A/B/C公开训练内部十轮证据及两个同格式未知代理任务，并保持父链、最差阶段和CPU资源可审计？
- 官方源：`configs/competition_core_experiments.json`锁定A/B/C父checkpoint、`public/train.jsonl`和历史暴露`public/validation.jsonl` SHA-256；运行前后重新校验，原包只读。
- 开发/确认边界：模型与策略选择只使用`public/train.jsonl`内部的十个互斥顺序/分组轮；A按类别分层、B按轴承寿命进度且轮内留出轴承、C按完整unit分组。公开validation和代理confirmation在开发winner冻结后各读取一次，同时报告静态、固定更新和冻结winner，不再反馈策略或参数。
- 对照：`static_parent`、`fixed_update(native_current)`、`core_replay`、`core_robust`和`core_stable`。recipe只按分类/回归任务合同路由，不按A/B/C或代理名称路由；核心策略以跨任务平均相对有向收益、最差阶段和实测CPU排序，不自称官方评分公式。
- 资源/停止：本机CPU；每臂10轮，每轮最多1个真实候选；所有候选计入CPU/墙钟/RSS/模型大小。非有限指标、父链断裂、源哈希变化、确认提前读取或输出manifest不一致立即失败。PyTRiO远程、SwanLab同步、Docker、官方上传和试运行均为0。
- 输出：Smoke `D:/brace-msi-competition/COMPETITION-CORE-EXP-001-SMOKE/`；完整矩阵`D:/brace-msi-competition/COMPETITION-CORE-EXP-001/`。失败和负结果同样保留。
- A1结果：`COMPLETED_VALID_MIXED`。机器结果`valid=true`，跨任务开发选择`core_robust`；冻结后公开/代理确认显示A Macro-F1 `0.714030→0.730826`、B RMSE `681.159833→680.012612`、C RMSE `52.868573→51.877279`，两个代理任务也改善；但训练内部B的平均相对收益为负，证明统一Huber回归路线不够稳健。摘要SHA-256 `9F1CECC4AEDBB6AF25E6D42E97319C0A123E3E9791FA752438757FD4A86DF47A`。公开validation继续标记历史暴露，不能把A1确认值用于独立选型。

## COMPETITION-CORE-EXP-001-A2（REGISTERED）

- 触发证据：A1开发结果中B的`core_robust`平均相对收益`-0.232407`，而C为`+0.005457`；既有A6/PERFORMANCE-METHOD-PILOT证据已表明高阶段均值跨度回归更适合高强度当前MSE，低跨度回归更适合父候选平均。
- 唯一新增策略：`core_profile_adaptive`。分类继续使用`class_weighted_ce`；回归只依据截至当前轮的目标阶段均值跨度/父`target_scale`决定`averaged_native`或`regression_mse(epochs=3, lr×3)`，不读取A/B/C或代理名称，不读取Gate/confirmation选择recipe。
- 冻结项：A1全部源哈希、分轮、其余策略、同作用域选择、确认读取一次、资源记录和停止条件保持不变；输出使用新目录，不覆盖A1。
- 成功标准：开发跨任务winner的平均相对收益提高，最差阶段不比A1 winner更差；否则淘汰新增策略。公开validation已经历史暴露，A2只作描述性复算，不称独立确认。
- 输出：`D:/brace-msi-competition/COMPETITION-CORE-EXP-001-A2/`。
- A2结果：`COMPLETED_VALID_NEGATIVE_NO_SELECTION_CHANGE`。画像自适应把B训练内部平均相对收益由`-0.232407`改善到`-0.038043`，但最差阶段仍为`-0.721589`；按A1“平均优先”的冻结排序仍由`core_robust`获胜。A2证明画像规则有趋势价值，但也暴露平均优先会牺牲跨任务最差阶段。摘要SHA-256 `67D54094A76BD8B39248B2827BBC7B834BE44B3A39F155CB083F092382449DE6`。

## COMPETITION-CORE-EXP-001-A3（REGISTERED）

- 触发证据：A2四个Core候选的跨任务最差相对阶段分别为`core_replay -0.465362`、`core_stable -0.333333`、`core_robust -1.257086`、`core_profile_adaptive -0.721589`；平均优先选择`core_robust`与赛题“最差阶段、稳定性”目标冲突。
- 唯一变更：开发winner排序改为先最大化所有任务/阶段中的最差相对收益，再比较跨任务平均相对收益，最后比较实测CPU；不创造官方综合分，不设置固定提升阈值。
- 冻结项：A2全部数据、源哈希、分轮、候选训练、recipe、模型、确认边界和资源记录均不变；使用新输出目录，不覆盖A1/A2。
- 成功标准：选择出的Core候选必须是开发证据中的风险优先Pareto候选；其跨任务最差阶段严格优于A1/A2 winner。确认数值因公开validation已历史暴露只作描述，不反向调整。
- 输出：`D:/brace-msi-competition/COMPETITION-CORE-EXP-001-A3/`。
- 结果：`COMPLETED_VALID_MIXED_NO_FORMAL_PROMOTION`。风险优先冻结`core_stable`，开发跨任务最差阶段由A1 winner的`-1.257086`改善为`-0.333333`；公开描述性复算中B RMSE `681.159833→672.769954`、C `52.868573→52.322937`，但A Macro-F1 `0.714030→0.699854`退化，因此不得把固定`core_stable`晋级为正式唯一策略。
- 机器证据：`D:/brace-msi-competition/COMPETITION-CORE-EXP-001-A3/summary.json`，SHA-256 `FEC09C59ED727EC3192EB180DA7D7598410F4AB5BD125E1B7C6DD997A91266D0`；综合报告见`docs/results/COMPETITION-CORE-EXP-001.md`。
