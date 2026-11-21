# 研究与工程进度

本文件按时间追加，不回写历史记录。当前状态仍以 [STATUS.md](STATUS.md) 为准。

## 2026-11-17：冻结A4归档独立官方协议模拟

- 用户明确授权后登记`WORKSPACE-V2-INDEPENDENT-TEST-001-A1`；先复核A4归档SHA-256，再删除原镜像标签并由`docker load`恢复、创建独立测试标签，未从工作树重新构建镜像。
- 在全新状态目录、4核8GB、断网、非root容器中完成A/B/C各10轮；30轮均引用非空宿主模型调用收据，A/B retain，C提交2个候选，最终完成15行独立预测，机器结果`valid=true`。
- 测试先行新增官方页面风格报告生成器：HTML/JSON展示30/30轮、模型调用、候选/retain、最终artifact和预测样本；隐藏指标、官方Token结算及正式成绩明确不可用。缺少模型调用收据时失败关闭。
- 产物位于`D:/brace-msi-workspace-v2/WORKSPACE-V2-INDEPENDENT-TEST-001-A1/`；最终完整回归`437 passed in 150.59s`。该结果不消耗官方试运行次数，不是隐藏测试或官方成绩，也不改变A4正式归档。

## 2026-11-17：官方Workspace V2正式候选0.9.0rc1

- 登记官方`contest_harness` 1.0.2归档和说明哈希，以固定`describe/train/predict`替换0.8.3猜测式Chat Completions桥接；模型只经宿主`rnd.model()`，每轮完成记录必须引用真实`model_call_ids`。
- vendored九个SDK源文件与官方解压件逐文件SHA-256一致；上游Linux 4核8GB断网测试`15/15 OK`。新增薄适配器复用既有原生父checkpoint续训、竞争策略、SafetyGate和预测内核，不重训性能模型、不改变checkpoint schema。
- 平台测量拒绝候选的分支先以红灯测试复现“父artifact已选中但持久状态/公开收据仍标记候选部署”，随后同步回写父checkpoint哈希、`deployed=false`、`retained_parent`与`platform_measurement_rejected`；官方SDK专项`5/5`、完整代码回归`435 passed in 142.62s`。正式镜像内容审计确认`/app`仅两个固定入口，未安装PyTRiO/SwanLab且无测试、模拟器、数据、权重、密钥或报告。
- 最终A4镜像在4核8GB、断网、非root真实Docker中完成A/B/C各10轮、30次宿主网关模型RPC、两次候选提交、合法retain和15行独立预测；机器结果`valid=true`且明确标记非官方成绩。
- 镜像linux/amd64、151,369,904字节；`docker save`归档151,393,280字节，SHA-256 `dc0147706e5c20a62360bf309a280b890ac6cea2707eee4aa66f8f7169c57cbc`，删除tag后`docker load`和`describe`通过。正式平台导入、真实Qwen Token和隐藏评测仍未执行。

## 2026-11-16：平台Chat Completions原生模型传输修复

- 登记平台失败`O-PLATFORM-013`：0.8.2只提供PyTRiO私有Sampler协议，无法由Chat Completions桥接器忠实绑定，且失败降级可能零模型调用。
- 以红绿测试新增`ChatCompletionsSamplingTransport`，请求构造、响应解析、Token正值校验由镜像所有；`start_round`可直接注入平台模型传输，平台模式每轮强制触发，失败重试一次后retain且不训练。
- 完整回归`430 passed`。`brace-msi:0.8.3rc1`在4核8GB、断网、只读根、非root容器中通过替身`workspace_io.model_transport`产生123/45 Token并完成官方A候选训练；独立`submit`生成1,244条预测。
- 镜像249,015,083字节，`pip check`通过，禁入文件扫描0；`docker save`归档249,039,360字节并重载通过，SHA-256为`4BE4327D29B8D25A2480427776AC58696FB6A48EA63AB576C35944240EA3A694`。
- 以上只证明本地接口和容器行为；平台真实模型服务、Token结算和最终评测仍为外部验证，不写成通过。

## 2026-11-13：DUAL-INTEGRATION-001平台无关十轮集成

- 新增`ControlledDualLoopHarness`与`controlled-loop-smoke`入口，贯通十批预测后反馈、四缓冲区生命周期、身份无关证据、动作值排序、0至2候选、SafetyGate、前任影子收益、原子控制器提交、本地审计和干净中断续跑。
- 分类与回归均覆盖十轮；同一数据仅更改任务名称时动作、决策和指标完全一致；回归在第4轮暂停后恢复至第10轮且无重复批次。
- 专项命令`python -m pytest tests/dual_loop/test_controlled_harness.py -q`为`4 passed in 9.57s`；完整命令`python -m pytest -q`为`320 passed in 73.31s`。
- 该实现使用本地`TaskStream`和本地SGD初始化，只证明平台无关核心集成；CLI写入`synthetic=true`和`formal_eligible=false`。本任务未运行A/B/C、未调用PyTRiO、未使用SwanLab、未消耗官方试运行，也未生成可提交`checkpoint.npz`。

## 2026-11-13：DUAL-EXPERIMENT-001 A1/A2父检查点顺序流

- 新增公开validation十批冻结器、输入专用隔离预测worker及官方父checkpoint逐轮续训适配；真实延续权重、Adam、标准化、epoch和step，worker代码根不包含`public/`。专项6项、完整回归`326 passed in 88.07s`。
- A1九运行完成但双闭环B/C劣于静态，保留为负结果。A2只针对该失败增加初始合法Replay、保守门控和负影子收益回滚；A/B/C双闭环分别为0.714552 Macro-F1、681.159833 RMSE、52.378784 RMSE，均不低于静态，Engine改善0.93%。
- A2仍未达到新RC要求，按预注册停止继续使用同一公开validation调参；PyTRiO臂未通过确定性性能门而未启动。两轮均未调用SwanLab或官方试运行，结果明确`historically_exposed=true/formal_eligible=false`。

## 2026-11-13：GENERALIST-MODEL-001-A1父模型通用集成

- 实现身份盲数值表格加载、Group/Stratified折、共享Linear/HGB/ExtraTrees池、自包含父checkpoint集成NPZ、哈希后受控joblib加载、64 MiB门和独立JSONL预测入口；meta、id和answer均不作特征。
- 三任务全部先完成train内部组折并冻结固定50/50混合，随后一次打开历史暴露validation。A候选被门控拒绝；B/C父集成RMSE为675.010677/49.336020，相对父模型改善0.90%/6.68%，MAE与NASA同步改善。
- 三产物仅115,392/239,908/200,613字节，实际嵌入父checkpoint并验证父预测与官方预测器一致。专项8项、完整回归`328 passed in 92.10s`；官方试运行、Token和SwanLab使用均0。

## 2026-11-13：受控双闭环证据与规格锁定

- 对仓库外13张智训引擎宣讲截图逐文件计算SHA-256并登记为`B-RSI-002`；明确其证据等级低于正式规则/SDK，未据此编造字段或平台权限。
- D-051锁定十批即十次决策事务及0至2候选语义；D-052锁定四缓冲区物理隔离、ActionValueTable、影子配对收益、证据触发Qwen、受限插件和分层模型注册。
- 正式设计与执行计划分别保存于`docs/superpowers/specs/2026-11-13-controlled-dual-loop-design.md`和`docs/superpowers/plans/2026-11-13-controlled-dual-loop.md`。既有RC、历史正负实验和公开验证暴露均保持不变；尚未运行新训练或产生新性能结果。
- 用户转发新的官方镜像/续训公告后登记`O-PLATFORM-007`与D-053：后续模型门必须证明真实父检查点加载、独立预测入口、`checkpoint.npz`和64 MiB产物上限；镜像只接受`docker save`归档。未猜测公告未提供的SDK字段。

## 2026-11-13：DUAL-DATA-001四缓冲区与数据能力边界

- 测试先行新增`online_data.py`：Anchor/Update/Gate/Replay为显式类型，数组只读；Gate在创建轮之后隔离完整一轮，达到`round+2`才能晋升Replay。
- 候选训练集合构造器只允许Update或Update+eligible Replay，拒绝Anchor/Gate和未到期Replay；训练、评估物化到两个独立目录，manifest只保存相对路径、批次、用途、样本摘要与文件哈希。
- 未来批次诱饵位于物化目录外，训练句柄既不记录源根也拒绝`..`越界解析。专项`4 passed`，完整回归`275 passed in 61.94s`；未运行训练或平台调用。

## 2026-11-13：DUAL-TXN-001单决策事务与影子配对收益

- 新增可恢复`DualLoopController`：提交历史必须是连续前缀，每批只建立一次计划；首候选产生结果前禁止第二候选，只有失败/收益不足、新证据、不同机制和预算同时成立才允许升级，单批硬上限2、全程默认8。
- pending状态、round commit和派生PolicyState均落盘；round commit带SHA-256并先原子写入，重启可从pending继续或从commit前缀恢复，重复批次和跳轮失败关闭。
- 影子收益在相同样本上计算分类Macro-F1/Accuracy或回归RMSE/MAE配对差并提供固定种子bootstrap区间；无影子时只接受显式历史基线并标记`historical_low`。专项`5 passed`，完整回归`280 passed in 63.27s`。

## 2026-11-13：DUAL-VALUE-001轻量动作收益与Pareto

- 新增每任务隔离、可持久化`ActionValueTable`；任务ID只作存储命名空间，证据画像只含任务类型和归一化退化/漂移/失败/预算/不确定性字段，重命名任务不会改变算法排序。
- 只有`delayed_shadow`或显式`historical_fallback`更新动作收益；即时Gate证据只更新尝试、成功和资源统计。配对收益权重1，低置信历史归因权重0.25；弱先验伪计数被限制在0至0.5并可被一次真实观测覆盖。
- 排序保留性能增益、CPU、峰值内存、Token和模型体积的非支配集合，不构造官方综合分。专项`5 passed`，完整回归`285 passed in 62.32s`。

## 2026-11-13：DUAL-QWEN-001证据触发建议器

- `AgentTrigger`只在严重性能退化、复杂漂移、连续失败、动作收益高不确定或Pareto无法区分时启用；稳定轮返回`not_triggered`且不调用传输层。
- `RetryingProposalAdvisor`只接受严格验证的`source=pytrio`提案；异常或客户端内部fallback视为失败，最多重试一次。两次失败后执行确定性提案并记录触发原因、尝试数、错误类别、Token和总延迟，来源明确为`deterministic_recovery`。
- D-054明确新双闭环恢复语义不会把确定性结果冒充Qwen贡献。专项`9 passed`，完整回归`294 passed in 64.10s`；本任务真实PyTRiO调用0次。

## 2026-11-13：DUAL-PLUGIN-001受限纯函数补丁

- 新增三个固定槽：特征变换、样本权重和预测后处理。源代码只允许一个签名精确的函数；禁止import、文件、网络、子进程、反射、动态执行、循环/推导式和不在白名单的NumPy调用。
- 每次执行在spawn子进程和临时只读工作区完成，尽可能设置CPU/地址空间/core限制，并强制墙钟超时与输出字节上限；同一输入执行两次验证确定性，再检查类型、行数/形状、权重、NaN/Inf和相对identity差异。
- 文件/网络/反射、无限循环、明显OOM、硬超时、5倍特征、负权重、非有限输出和非确定结果均失败关闭。专项`13 passed`，agent+dual-loop`69 passed`，完整回归`307 passed in 63.21s`。

## 2026-11-13：DUAL-MODEL-001分层模型与正式产物门

- Tier0登记官方初始模型、SGD与Linear；Tier1登记HistGradientBoosting与ExtraTrees；MLP未进入新正式池。四类CPU适配器均在小型分类探针上完成训练—pickle保存—加载—逐项同预测，且能力声明不把Linear/树模型误报为增量。
- Tier2只能在依赖体积、4核8GB、输入、预算、保存加载、预测协议和产物兼容全部通过后登记；当前未启用CatBoost或新增依赖。
- `FormalArtifactGate`验证父文件实际哈希、加载哈希、子哈希、epoch/step连续、继承元数据、`checkpoint.npz`可安全加载、模型文件总量不超过64 MiB和独立预测探针。新增平台无关`checkpoint-predict` NPY入口，避免猜测正式SDK字段。
- 专项`9 passed`，完整回归`316 passed in 63.48s`；正式平台的checkpoint字段与挂载命令仍由H-001阻塞。

## 2026-11-11：官方训练包只读审计与接入设计

- 用户提供A/B/C三个官方训练包，共64文件、60,328,967字节；测试后复核原目录无新增缓存或文件，关键数据和检查点哈希保持不变。
- 三个官方检查点公开验证指标均可用随包代码精确复算；训练/验证ID和设备分组无交叉。A/C随包测试各9项通过，B核心10项通过，另2项因未分发打包工具模块而保留为上游缺陷证据。
- B官方架构确认为34→24 tanh→1，D-028替代D-026的正式接入用途；A/C分别为128→32→6和24→32→1。
- 接入设计提交`51765d7`，采用原包只读、隔离子进程调用官方训练器、BRACE十轮监督和原子断点恢复；设计等待用户书面规格确认后进入实施计划。
- 审计详见`source_notes/OFFICIAL_TRAINING_PACKAGE_AUDIT_2026-11-11.md`。

## 2026-11-11：规则对齐三任务无人值守训练完成

- 以TDD实现参数量匹配MLP、平台已公布指标、三任务10轮无密封流、原子检查点、可恢复9实验队列、机器验收和静态HTML/Markdown报告；实现提交`512d477`，报告提交`9c7bdba`。
- 完整回归`116 passed`，`compileall`与`git diff --check`通过。前三个静态实验健康检查有效后，PID 6084从断点独立完成余下6个实验并正常退出；终态`validation.json`为`valid=true`。
- Gas BRACE相对静态提高0.229939 Macro-F1；Engine BRACE减少0.248934 RMSE；Bearing BRACE增加35.086308 RMSE而失败。没有隐藏负结果，也没有构造官方综合分。
- D-027冻结下一步：不在同一开发流继续调参；Gas/Engine等待平台检查点复验，Bearing默认不更新。机器产物位于`D:/brace-msi-official-dev/OFFICIAL-RULES-ALIGNED-DEV-001/`，聚合说明见`results/OFFICIAL-RULES-ALIGNED-DEV-001.md`。
- 全程未打开Gas 8–10、FD001 81–100或XJTU密封轴承，未运行SwanLab、未提交平台、未消耗最多10次试运行，也未修改RC标签。

## 2026-11-11：最新平台赛前规则接入

- 视觉核验`新增`目录4张平台截图并登记SHA-256。确认A/B/C任务分别为气体6类Macro-F1、轴承RUL分钟RMSE/MAE、发动机RUL循环RMSE/NASA非对称分；每任务10轮优化。
- 客观35分拆为平均性能提升15、最终阶段与恢复速度10、稳定性5、资源效率5；平台要求至少3次完整历史—实验—决策记录，每队最多10次试运行、正式评测最多2次。
- 本机只发现4张截图与公开原始数据，未发现平台训练包或初始权重；浏览器自动下载因无法可靠识别Edge URL被安全机制终止，没有点击平台或消耗试运行次数。
- 参数量4326/865/833与32隐藏单元MLP的128→32→6、25→32→1、24→32→1精确吻合。D-026将其冻结为可替换本地检查点推断，不能声称与平台代码或权重相同。
- 预注册`OFFICIAL-RULES-ALIGNED-DEV-001`与`FORMAL-DEV-001`；展示材料暂不进入关键路径，下一步实施9实验×10轮无人值守训练。

## 2026-11-11：XJTU-SY本地串行训练启动准备

- 用户授权暂不等待平台，对新增XJTU-SY完成当前阶段本地训练；SwanLab继续推迟到最终工程模型正式重训。
- 预注册`XJTU-LOCAL-DEV-001`：按15个轴承身份冻结9/3/3初训、开发、密封组，自定剩余采样分钟数为本地RUL回归目标，明确不冒充官方任务或成绩。
- 新增单CSV独立双通道时频特征、逐轴承原子缓存、可恢复五轮串行队列和独立后台入口；输入不包含轨迹总长度、剩余寿命或未来文件信息。
- TDD红灯为缺少XJTU模块；随后串行恢复测试发现单group初训会产生空训练集，已按根因改为单group时间切分。
- 验证：`D:\anaconda3\python.exe -m pytest -q --tb=short`为`100 passed`；`compileall`与`git diff --check`通过。训练实现提交`2460577`，尚未在此记录中声称真实数据轮次完成。

## 2026-11-11：XJTU-SY本地串行训练完成

- 六个原始RAR分卷哈希再次核验通过；派生解压约11.382GiB，12个允许使用的轴承形成43维原子特征缓存，初训7032条、开发1679条；三个密封轴承未进入特征缓存或模型运行。
- A1完成五轮后，审查发现静态模型使用全部9个初训轴承而策略留出2个锚点，不满足公平可见性；A1标记INVALID并完整保留，未覆盖结果。
- 修正静态轮次为与策略相同的7轴承/4165条训练、2轴承锚点后执行A2。五轮开发RMSE依次为335.5579、599.3000、524.7143、650.0440、650.0440；这些是自定本地RUL指标，不是官方成绩。
- BRACE实际训练3个候选，两个因验证样本不足、一个因锚点退化超限而拒绝；稳定模型未被错误替换。简单性能触发未达到阈值，0次候选，作为负结果保留。
- A2机器验收：5/5轮、有限指标、3次真实候选、`valid=true`；运行结束且没有残留后台进程。聚合解释见`results/XJTU-LOCAL-DEV-001.md`。

## 2026-11-11：正式实验记录阶段澄清

- 用户确认实验记录是最终完成品中工程模型正式重新训练的记录；当前数据审计和平台接入准备阶段不需要修改或运行SwanLab。
- 现阶段继续使用本地私有审计保存可复核证据，不生成、不同步、不公开新的SwanLab运行。
- 等平台提供剩余SDK、任务、评分和记录规范，最终工程模型冻结后再预注册并执行一次正式记录重训。

## 2026-11-10：正式数据到货首轮审计

- 用户指定`C:\Users\Administrator\Desktop\官方`为三个官方公开数据集目录，并授权进入正式接入。
- Gas 10批与既有代理数据逐文件SHA-256完全一致；C-MAPSS的FD001-FD004训练、测试、RUL及readme与既有内层压缩包逐文件SHA-256完全一致。
- XJTU-SY六个RAR5分卷完整性测试返回0；归档包含15个轴承、3种工况、9,216个唯一双通道振动CSV，解压总大小约12.22GB。审计发现RAR跨卷列表会重复5个跨卷文件，已改用唯一归档路径计数并与数据集说明书核对一致。
- 数据集说明书确认25.6kHz采样、每分钟采集32768点/1.28秒、完整run-to-failure轨迹及公开使用/引用要求；该说明不等同标准许可证，比赛任务目标与许可仍待H-006。
- 本轮没有训练模型、修改原始数据或覆盖旧实验。两套重复数据复用加载器和指纹，不重复下载；旧代理结果继续保持`proxy_only`。
- 目录不含组委会manifest、轴承任务目标、官方切分、指标、评分脚本或许可证，`DATA-001`进入`IN_PROGRESS`但未完成；确认性正式训练按H-006保持停止。

## 2026-11-07：Release Readiness RR-001

- 只读检查Docker、Podman、WSL及常见安装路径，未找到可用Linux容器运行时。
- Windows功能查询确认`Microsoft-Windows-Subsystem-Linux`、`VirtualMachinePlatform`、`Microsoft-Hyper-V-All`和`Containers`均为`Disabled`。
- 结论：实际镜像构建、镜像大小与`--cpus=4 --memory=8g --network=none`运行保持`BLOCKED`；没有以静态上下文审计冒充通过，也未修改或重启宿主机。

## 2026-11-07：Release Readiness RR-002

- 首次干净安装暴露全局pip镜像证书错误；通过显式使用官方PyPI解决，未绕过TLS校验。
- CPython 3.12 manylinux二进制审计发现`psutil==5.9.0`无可用轮子，`python:3.12-slim`会因无编译工具而失败；测试先失败后将锁版本修正为`5.9.8`，Docker安装增加`--only-binary=:all:`。
- 新建完整运行与测试锁文件；全新隔离环境`pip check`为`No broken requirements found`，完整回归`81 passed`，非密封CLI Smoke完成3次候选。
- Linux轮子审计成功下载全部运行依赖的cp312 manylinux或纯Python轮子；这证明依赖可安装性，不替代真实Docker构建。

## 2026-11-07：Release Readiness RR-003

- 依据SwanLab官方通用文档新增可选离线导出器：只读取`public-spool.jsonl`并二次白名单过滤，默认私有且不自动同步。
- 提供CLI离线导出和只打印不执行的`swanlab sync`命令；命令接口不接受API Key，避免密钥进入日志。
- 真实安装SwanLab 0.10.4后发现Windows GBK终端无法输出SDK Emoji；按TDD在适配器调用前将可重配置流切换UTF-8。
- 真实SDK离线导出成功生成`run-*`目录并写入8条聚合记录，`pip check`无冲突；没有执行云端同步。
- 比赛专用字段、项目可见性与离线评测后的同步流程仍等待官方规范，`LOG-001`不解除阻塞。

## 2026-11-07：Release Readiness RR-004

- 新增正式SDK插件清单与动态加载边界，只登记模块、无副作用工厂、SDK版本和SHA-256，不接收密钥或未知字段映射。
- 插件必须返回完整`EventProtocolAdapter`；缺模块、非法清单、无效哈希和不完整接口均fail-closed，不会静默使用模拟SDK。
- 新增`sdk-contract-check`验证两种内部协议的适配器契约，并提供不含真实字段的清单模板和到货核验步骤。
- 真实事件字段、数据流构造、预测提交、标签权限和错误语义仍未实现且明确属于`SDK-001`外部阻塞。

## 2026-11-07：Release Readiness RR-005

- 发布版本冻结为`BRACE-MSI-0.1.0rc1`；新增确定性源码归档、跟踪文件白名单、A1/A2证据边界审计和机器可读发布门清单。
- 发布包只纳入源码、配置、测试、正式文档以及A1/A2的公开聚合证据；排除原始数据、模型权重、私有审计和密钥。
- 全新隔离环境从锁文件安装运行/测试/SwanLab依赖，构建并安装wheel后确认版本`0.1.0rc1`，`pip check`通过。
- 安装包CLI分别完成`predict_then_feedback`三候选和`labeled_train_then_predict`四候选Smoke；真实SwanLab 0.10.4离线导出8条聚合事件。
- 完整自动测试`95 passed`；编译检查通过；Docker上下文124文件、487,662字节、无禁入文件。
- 实际Docker镜像、4核8GB Linux容器、正式SDK/数据/评分及比赛SwanLab同步仍明确`BLOCKED`，未制造通过证据。
- 最终自审修复两项重要发布缺口：默认Docker构建现在安装锁定SwanLab依赖；RC打包器会亲自运行pytest、`pip check`和编译检查，任一失败均拒绝写入PASS清单。

## 2026-11-07：SYS-001统一任务引导、CPU模型池与注册表

- 新增平台无关`TaskDefinition`/`TaskSignature`和TaskBootstrap兼容性守卫；未知同领域任务可从合法初训数据初始化，不兼容特征、任务类型或标签空间会被拒绝。
- CPU模型池覆盖SGD、Logistic/Ridge、HistGradientBoosting和ExtraTrees；能力声明阻止批量模型误用`partial_fit`。
- 新增只追加版本的本地模型注册表，模型和清单采用临时文件加原子替换，支持稳定加载和显式回滚。
- 验证：`D:\anaconda3\python.exe -m pytest -q --tb=short`，结果`58 passed`。

## 2026-11-07：SYS-002证据路由、预算决策与有限搜索

- 新增数据质量、性能退化、协变量漂移、历史失败和预算余量的统一证据对象；非有限输入会在训练前阻断。
- 动作规划按真实失败反馈从增量更新升级到回放重拟合和有限HPO，不执行动态生成代码。
- 新增有上限的经验回放、有限候选搜索、耐心停止和逐候选预算记账；候选从新模型构造，不污染稳定模型。
- 验证：`D:\anaconda3\python.exe -m pytest -q --tb=short`，结果`64 passed`。

## 2026-11-07：SYS-003无人值守Harness、恢复与记录

- 统一Harness已连接两种内部协议、任务初始化、证据路由、动作规划、候选训练、有限搜索、三层门控、模型注册与批次检查点。
- 协议通过`EventProtocolAdapter`注入，正式SDK到达后只需实现映射，不需要改训练决策核心。
- 批次提交后原子保存私有检查点；重新启动会重建协议历史并从下一个批次继续，不重复已经提交的候选训练。
- 公开记录仅进入本地聚合待同步队列，未声称SwanLab云端成功；私有审计和公开记录均过滤原始特征、逐样本标签和密钥。
- 新增`python -m brace_msi synthetic-smoke`非交互CLI，合成轴承流明确标注为`protocol_only`。
- 验证：`D:\anaconda3\python.exe -m pytest -q --tb=short`，结果`71 passed`。

## 2026-11-07：SYS-004交付包装与静态报告

- 新增Python 3.12 slim Dockerfile、锁定依赖、严格Docker忽略表和PowerShell/Unix一键入口；镜像上下文不包含数据、实验产物、权重、密钥或测试缓存。
- 新增离线、自包含、HTML转义的静态报告生成器及CLI；不加载任何公网脚本或样式。
- 新增运行手册、正式SDK适配步骤和直接依赖开源合规清单。
- 静态上下文审计：73个文件、251,854字节、禁入文件0；PowerShell一键合成Smoke实际完成，3个真实候选。
- 本机PATH与常见安装位置均未找到Docker/Podman，因此没有声称镜像已构建或镜像实际小于2GB；该项转入`PKG-RUNTIME-001`阻塞。
- 验证：`D:\anaconda3\python.exe -m pytest -q --tb=short`，结果`74 passed`。

## 2026-11-07：SYS-005三任务完整系统模拟

- 预注册`LOCAL-FORMAL-SIM-001`后，用提交`ce3e907`执行Gas 1–7、FD001发动机1–80和合成轴承协议流；旧密封段未暴露给Harness。
- 三任务均无人干预完成4批次和4次真实候选；动作合计增量8、回放2、有限HPO2。Gas接受4/4，FD001接受3/4，合成故障/HPO安全拒绝4/4并保持初始稳定模型。
- 4逻辑CPU亲和性实际生效；操作边界最大RSS 146,702,336字节；公开日志脱敏、批次提交唯一性、模型注册表可加载和离线HTML均通过独立机器验收。
- 未强制8GB容器内存上限，也未构建Docker镜像；本机无容器运行时，保持`PKG-RUNTIME-001`阻塞。
- 验证：独立输出验收`valid=true`；`D:\anaconda3\python.exe -m pytest -q --tb=short`结果`77 passed`。

## 2026-11-07：最终自审发现并修复验收缺陷

- 发现A1把预算拒绝和注入失败尝试计入“真实候选”；重新定义`candidate_count`只统计`training_started=true`，A1因此标记INVALID，不删除其负证据。
- 发现批次检查点已保存但审计追加中断时，恢复会跳过缺失记录；新增稳定`record_id`与启动时对账，保证候选、批次和完成事件幂等补写。
- TaskBootstrap原先对字符串分类标签调用`np.isfinite`；现仅对回归目标强制数值有限，对分类标签支持字符串并拒绝None/NaN。
- 三项回归测试均先观察失败后修复；完整测试增加到`80 passed`。A2只复验工程资格，不改变数据、阈值或性能策略。

## 2026-11-07：LOCAL-FORMAL-SIM-001-A2通过

- 修复提交`7ef3829`在相同开发段、相同门控和预算下重新运行；A2独立验收`valid=true`。
- 三任务真实训练候选为4/4/3；动作计数增量7、回放1、有限HPO3。两次合成注入失败保留为尝试记录但不再计入真实候选。
- CPU亲和性4核；操作边界RSS 148,017,152字节；三个任务公开日志无禁入字段，私有批次提交均4/4唯一。
- A1继续保留为INVALID负结果，未删除或覆盖。

## 2026-11-07：最终环境检查

- 完整测试`80 passed`、compileall通过、A2独立验收通过、Markdown相对链接无断链、Git跟踪文件不含数据/权重/密钥。
- 当前Docker上下文77文件/285,280字节、禁入文件0；仍不能等同于镜像大小。
- 全局Anaconda的`pip check`报告3个无关应用包冲突（anaconda-cli-base、streamlit、tensorflow）；候选直接依赖均已实际导入和运行，但干净环境依赖复验等待Docker/venv条件，登记为R-016。

## 2026-11-06：需求收敛与资料审计

- 完成官方规则PDF五页视觉核验。
- 核验三张宣讲截图：五步闭环、赛题背景、35/65评分幻灯片。
- 确认本地Gas代理数据存在10批、共13,910行。
- 确认C-MAPSS外层及内层压缩包存在，包含FD001-FD004文件。
- 未发现轴承代理数据。
- 确认尚未运行正式训练或实验。
- 将BRACE-MSI V4.1锁定为研究主线，不再继续设计V5。

## 2026-11-06：文档体系建立

- 建立单一事实来源、任务图、实验协议、风险、决策、进度和恢复规范。
- 新增根目录`AGENTS.md`，约束未来Codex的启动与收尾流程。
- 保留原始数据和历史草稿，不移动、不删除、不覆盖。
- 验证结果：18个必需文件存在；相对链接无断链；37个被引用证据ID均有定义；原始Gas与C-MAPSS压缩包SHA256保持不变；DOC-001之外没有虚构完成项。
- Git基线：见仓库首次提交历史。

## 2026-11-06：CORE-001模拟事件协议

- 新增两种内部协议：`predict_then_feedback`与`labeled_train_then_predict`。
- 新增任务、批次、预测提交、反馈、批次提交及结束事件的确定性状态守卫。
- 用不透明内部样本ID阻止训练样本与待评分样本重叠，不映射或猜测官方SDK字段。
- 单元测试覆盖两种合法序列、非法跨协议事件、预测前反馈、训练/评分重叠、未提交批次、重复预测请求、拒绝事件原子性及ID一致性。
- TDD红灯证据：实现前测试因`ModuleNotFoundError: No module named 'brace_msi'`失败；新增重复请求用例在修复前显示`DID NOT RAISE`。
- 完成验证：`D:\anaconda3\python.exe -m pytest -q --tb=short`，结果`13 passed in 0.03s`。
- 未启动训练，未调用真实平台或网络服务，未改动原始数据。

## 2026-11-06：LOCAL-DATA-001代理数据审计

- 新增Gas严格稀疏格式解析器与C-MAPSS FD001分组轨迹解析器。
- 冻结Gas批次1–3/4–7/8–10和FD001发动机ID 60%/20%/20%切分；样本与发动机组互斥检查通过。
- 原始归档SHA256与`SOURCE_REGISTRY.md`一致，审计过程只读。
- 机器可读聚合证据写入本地忽略路径`artifacts/data_audit/proxy_data_audit.json`；正式说明见`source_notes/PROXY_DATA_AUDIT.md`。
- 验证：`D:\anaconda3\python.exe -m pytest -q --tb=short`，结果`23 passed in 0.20s`。
- 尚未运行任何模型训练或报告性能指标。

## 2026-11-06：LOCAL-CORE-001本地闭环核心

- 新增分类/回归SGD模型适配器，显式声明增量、概率输出和序列化能力；稳定模型与候选通过深拷贝隔离。
- 新增性能退化与逐特征KS漂移证据、训练前预算账本、边界资源计量及三层SafetyGate。
- 自动测试覆盖增量更新、同族重拟合、候选隔离、预算拒绝、分类/回归门控接受与拒绝。
- 验证：`D:\anaconda3\python.exe -m pytest -q --tb=short`，结果`34 passed in 0.78s`。
- 仅使用合成测试数据，尚未运行真实代理数据训练。

## 2026-11-06：LOCAL-LOOP-001本地策略与运行器

- 新增静态、性能触发式单动作及BRACE证据/历史反馈策略；BRACE不使用固定训练菜单。
- 新增严格prequential运行器：提交预测后登记反馈，再计算指标并执行训练前预算、候选训练、SafetyGate和部署/拒绝。
- 增量失败候选也消耗候选预算，且稳定模型保持隔离；密封阶段只能预测与评分，不触发训练。
- 新增只允许聚合字段的本地JSONL审计，自动移除特征、标签和样本ID。
- 验证：`D:\anaconda3\python.exe -m pytest -q --tb=short`，结果`42 passed in 1.14s`。
- 仅使用合成测试流，尚未运行真实代理数据训练。

## 2026-11-06：LOCAL-SMOKE-001代理Smoke

- 在提交`64ccce2`上完成Gas分类与FD001回归的静态、性能触发和BRACE共6个运行。
- 共执行10次增量与3次同族重拟合候选；六个运行均完成且机器验收通过。
- 代理Smoke聚合指标、候选接受/拒绝、训练样本和资源见`results/LOCAL-SMOKE-001.md`。
- 日志字段白名单检查通过；未保存模型权重，未打开完整密封段，未修改原始数据。
- 该结果只证明低成本管线可运行，不形成BRACE优于对照的正式结论。

## 2026-11-06：LOCAL-EXP-001完整代理比较

- 在提交`f9647dd`先完成全量开发流，机器验收通过后未修改配置，对完整密封段只运行一次。
- 最终运行共14次真实候选：9次增量、5次同族重拟合；Gas 8/8候选上线，FD001 1/6候选上线，其余被SafetyGate拒绝。
- Gas密封Accuracy：静态0.4663、简单触发0.6274、BRACE 0.6872；FD001密封RMSE：静态/简单21.9451、BRACE 21.3805。
- BRACE在两个代理任务上主指标和最差阶段更好，但训练样本和候选耗时明显更高；没有出现简单策略对BRACE的全面支配。
- 完整逐批、资源和解释边界见`results/LOCAL-EXP-001.md`；这些结果不是官方成绩。

## 2026-11-11：OFFICIAL-PKG-001 Task 1只读清单审计器

- 新增官方A/B/C训练包只读清单配置和审计器，不导入或执行随包训练代码。
- 对真实训练包核验关键SHA-256、公开训练/验证行数、ID与设备组隔离、NPZ安全schema、Adam状态、模型拓扑和公开验证基线；B固定为34输入、24隐藏、865参数。
- 篡改副本测试证明检查点哈希不符会在训练启动前失败；原训练包未产生缓存或新文件。
- TDD红灯：实现前`ModuleNotFoundError: No module named 'brace_msi.official_package'`；绿灯：`3 passed`。
- 边界保持`official_package=true`、`official_scoring_ready=false`；尚未运行候选训练。

## 2026-11-11：OFFICIAL-PKG-001 Task 2真实续训适配器

- 通过独立子进程调用原版`baselines.train`，限制单线程、白名单epoch/学习率/批大小，候选目录不可覆盖。
- 对原版A训练器完成全状态继承证明：同一父检查点连续2 epoch与1 epoch后续1 epoch的所有NPZ数组、累计epoch/step及预测完全相同。
- 每个候选核验真实父/子SHA、输入数据SHA、权重与Adam变化、预处理状态不变、报告schema和逐epoch历史；不以自报父哈希代替继承证据。
- 超时测试保留独立失败收据且不生成候选目录；训练包源码在审计后变化会在启动子进程前失败。
- TDD红灯包括缺少模块及源码变化未被拒绝；绿灯：定向`5 passed`，全量`124 passed`。
- 调试记录：一次手工上游测试收集在原包生成`__pycache__`，已定位并删除该次自生成缓存；随后全量测试确认原包不再含`.pyc`或`__pycache__`。

## 2026-11-11：OFFICIAL-PKG-001 Task 3候选适应决策轮

- 新增可恢复的低成本续训对照（内部ID`performance_triggered`）和BRACE监督器，固定10个“候选适应决策轮”，显式记录`real_drift_stream=false`。本次无真实流实验中该对照只执行一次无条件续训，不能解释成在线性能触发。
- 每轮最多一个候选；BRACE在预算内至少执行3次真实候选，严格公开验证改善才部署，相等或退化均保留旧稳定模型。
- 父SHA链机器校验只允许已部署检查点成为后续父模型；测试中的第二个退化候选被拒绝，第三个候选正确继承第一个已接受检查点。
- 每次公开验证读取和指标计算均进入`validation-usage.jsonl`，声明不用于训练或预处理拟合；状态、审计和验证账本均原子重写，恢复不会重复已完成候选。
- TDD红灯：缺少`brace_msi.official_rounds`；绿灯：定向`5 passed`，全量`129 passed`。

## 2026-11-11：OFFICIAL-PKG-001 Task 4三任务可恢复套件

- 新增固定队列：A/B/C各1次Smoke、A/B/C单次低成本续训对照、A/B/C BRACE，共9个可恢复作业；已完成作业不会重复候选。
- 在任何训练前按包内历史耗时、候选/epoch上限和检查点体积生成CPU、墙钟、磁盘保守估算；三Smoke完成后按实测资源更新估算并再次门控。
- 汇总`source-manifest.json`、`resource-estimate.json`、`validation-usage.jsonl`、`summary.json`、Markdown/HTML报告和机器验收；HTML输出转义外部标题。
- B包上游现状固定为“核心10项通过、缺少打包工具导致2项错误”，不伪造成全绿，也不误报为训练失败。
- TDD红灯：缺少`brace_msi.official_package_suite`；绿灯：定向`3 passed`、全量`132 passed`，`compileall`和`git diff --check`通过。
- 本阶段只完成代码和模拟套件测试；真实A/B/C Smoke及十轮候选尚未运行，不能登记结果。

## 2026-11-11：OFFICIAL-PACKAGE-DEV-001预注册

- 在任何真实候选运行前，将三包输入哈希、原版训练器继承要求、9作业顺序、候选白名单、公开验证暴露风险、资源上限、成功/停止条件和禁止项登记到`EXPERIMENTS.md`。
- 配置显式冻结每策略最多3候选、CPU/墙钟各600秒及完整队列CPU 3600秒、墙钟1800秒、磁盘200MiB上限。
- 运行证据包将记录实际Git HEAD和工作树是否干净；尚未产生真实指标或训练运行。
- 首次Smoke启动在导入阶段失败：脚本从干净检出直接运行时未将`src/`加入模块搜索路径，`ModuleNotFoundError`发生在任何训练前。新增CLI冷启动回归测试和失败状态归档测试，修复后全量`134 passed`；A1负证据不删除。

## 2026-11-11：OFFICIAL-PACKAGE-DEV-001完成

- 在干净提交`34098bf`完成A/B/C三个真实Smoke及六个策略作业；全部六个策略各10个候选适应决策轮，BRACE每任务3个真实候选。
- 共15个训练候选、CPU 64.781秒、候选墙钟69.547秒、峰值RSS 256,630,784字节；资源预估和实测均未越界。
- A Macro-F1：静态0.714030，低成本对照/BRACE均0.725695；B RMSE：静态681.159833，低成本对照/BRACE均657.645417；C RMSE：静态52.868573，低成本对照52.350178，BRACE51.889566。
- BRACE接受4/9候选；5个退化候选被拒绝且未进入后续父模型链。验证账本15次文件读取、33次指标计算，均未参与训练或预处理拟合。
- `validation.json`为`valid=true`；原包仍64文件、60,328,967字节、无Python缓存。完整解释、A1负证据和机器验收见`results/OFFICIAL-PACKAGE-DEV-001.md`。
- 按D-031停止在同一公开验证集继续调参或重跑，等待正式SDK和隐藏评测。

## 2026-11-11：OFFICIAL-PKG-001独立终审修复

- 独立只读终审复核15个候选检查点哈希均与收据一致，同时发现路径重叠、可信清单、资源停止恢复、收据落盘中断、机器验收复算、执行清单冻结、实际资源门控和验证暴露语义等缺口。
- 新增包级全树可信SHA、运行根重叠写入前拒绝、相对输出绝对化、完整收据恢复、Smoke恢复、配置/提交清单冻结、恢复前资源停止、实际CPU/墙钟/RSS部署门控及逐检查点/收据/汇总复算。
- 新增10项针对性回归覆盖；定向官方包测试25项、全量144项通过。冻结的15候选未重新训练或覆盖，严格验收器对原运行只读复验仍为`valid=true`。
- 原验证账本的15次读取被澄清为成功训练器加载；事后补充区分12次套件审计读取、15次候选预检哈希、15次训练器加载和33次指标计算，不伪造未插桩测试/审计的总打开次数。

## 2026-11-12：UNIFIED-POLICY-001启动

- 根据D-032/D-033建立统一策略优化设计与实施计划；旧D-031实验、RC标签和历史结果保持不变。
- 已实现无量纲指标退化、身份盲共享动作策略、三阶段manifest/末期一次性锁、任务级leave-one-task-out排序以及可恢复的四策略搜索运行器。
- 新路径要求Gas、Bearing、Engine共享同一策略参数和预算原则；TaskAdapter可以适配任务类型与模型接口，但决策器无法接收任务ID、数据集/Profile和批次名称。
- `UNIFIED-POLICY-OPT-001-SMOKE`已预注册，尚未运行真实训练；末期数据和官方十次测试机会均未使用。
- Smoke A1在提交`cf3adcc`完成15/15作业后，发现CLI训练迭代数未进入执行manifest，存在不同训练协议混合恢复风险；A1立即标记INVALID并保留，未打开末期数据。修复为配置内冻结迭代数并新增评估器协议SHA后，A2另建运行根重跑。
- Smoke A2在提交`72898b9`完成15/15真实开发作业和3个任务级留出fold，严格验收`valid=true`、官方测试次数0；所有策略按任务共享检查点和阶段manifest。该结果只证明统一搜索链可运行，正式共享参数仍需完整有界搜索确定。

## 2026-11-12：UNIFIED-POLICY-OPT-001-DEV-A1完成并触发停止规则

- 在干净执行提交`e057589`完成24组共享配置、9个基线和72个复杂BRACE作业，共81/81；严格复算返回`valid=true`、3个任务级留出fold、官方测试次数0。
- 留出Bearing时复杂策略与简单策略性能持平但多用0.968750 CPU秒；留出Engine与Gas时复杂策略相对简单策略归一化增益分别为-0.001265与-0.021493，且CPU成本分别为33.843750与16.640625秒。
- 复杂BRACE在3/3留出fold均无优势并消耗更多资源，触发预注册停止规则；没有打开任何末期数据，也没有根据末期反馈调参。
- 按D-034冻结`normalized_performance_triggered`为最终候选；复杂全中期排序最优项`shared-f8881ba9c291`仅保留为一次性末期对照。
- 证据：`docs/results/UNIFIED-POLICY-OPT-001.md`、`configs/unified_policy_frozen.json`及`D:/brace-msi-unified/UNIFIED-POLICY-OPT-001-DEV-A1/`。

## 2026-11-12：正式路线D-035锁定

- 根据PyTRiO官方文档、Qwen3.5-4B平台校验结果、官方A/B/C训练包和用户当前授权，将正式路线锁定为“Qwen3.5-4B PyTRiO Agent + BRACE确定性Harness + 官方A/B/C工业模型 + 经验证的开源优化方法”。
- 新建`docs/FORMAL_ROUTE.md`，并同步STATUS、TASKS、IMPLEMENTATION_PLAN、ARCHITECTURE、WORKFLOW、EXPERIMENT_PROTOCOL、SOURCE_REGISTRY、DECISION_LOG、RISK_REGISTER和SESSION_HANDOFF。
- D-032/D-034统一策略路线停止为历史研究；81/81开发作业和复杂策略负结果保留，不执行末期测试，也不改写既有RC与训练包证据。
- 当前任务切换为`PYTRIO-001`。本条只记录路线与文档治理完成，不声称PyTRiO代码、真实服务调用或三任务新增性能已经实现。

## 2026-11-16 METHOD-PORTFOLIO-PILOT-001

- 新增`method_pilot.py`与两套研究runner，在confirmation/public validation读取0次的前提下完成A/B/C各9个相邻未见转换：A1为7种教师/基线，A2为17种正式MLP候选，A4为9种正式MLP recipe连续父链。
- A1证明A/B存在显著方法上限；C的异构树负迁移。A2/A4证明正式MLP通过累计、最近窗口、临时学习率和父权重插值也可显著跨批改善。
- A3暴露学习率倍率逐轮累乘缺陷并停止；失败证据保留。修复采用训练期临时倍率，新增10轮不累乘测试，A4全部27条父链完成并保存可加载checkpoint。
- 专项测试命令：`python -m pytest tests/research/test_method_pilot.py -q`，结果`6 passed`；完整回归`python -m pytest -q`结果`413 passed in 166.18s`，`compileall`与`git diff --check`通过。
- 结果与边界见`results/METHOD-PORTFOLIO-PILOT-001.md`；不把本地代理收益写成官方隐藏成绩。

## 2026-11-12：PYTRIO-001完成

- 新增`src/brace_msi/pytrio_agent.py`，按PyTRiO官方Sampler API惰性创建`ServiceClient`与sampling client；默认模型为已确认的`Qwen/Qwen3.5-4B`，模型路径和SDK环境由运行时注入。
- Agent只能输出`brace-msi.experiment-proposal.v1`严格JSON；动作/工具映射、参数键、候选数、CPU提案上限和停止条件在本地校验。原始提示词/响应不进入收据，只保存SHA-256、Token数、延迟和错误类别。
- 非法JSON、越权工具、传输异常均回退到调用方提供的确定性提案；含API Key等秘密字段的上下文在调用传输层前失败关闭。
- 验证：`D:\anaconda3\python.exe -m pytest tests/agent -q --tb=short`为`8 passed`；全量`D:\anaconda3\python.exe -m pytest -q --tb=short`为`189 passed in 58.84s`。未使用真实凭据、外部模型调用或付费资源。

## 2026-11-12：OFFICIAL-HARNESS-002完成

- 新增`official_agent_harness.py`及`official-agent-run` CLI：HistoryReader只暴露聚合历史；提案经schema、动作、参数、Token、候选和CPU预算检查后才进入官方原版训练器；候选收据、严格改善门控和接受链可独立复算。
- PyTRiO和确定性提供者使用同一执行路径；服务异常或调用预算耗尽时可确定性降级。原始训练包、稳定父模型、候选目录和部署指针分离。
- 预注册并运行`FORMAL-AGENT-SMOKE-001`：提交`24c70c8`上A/B/C各执行1个1-epoch真实候选，均通过公开验证严格改善门控；机器复算3/3为`valid=true`，合计CPU 12.75秒，Token和官方试运行均为0。
- 指标改善只用于链路验收：A 0.714030→0.725695 Macro-F1，B 681.159833→657.645417 RMSE，C 52.868573→52.350178 RMSE。公开验证已重复使用，不能称为独立泛化或官方成绩。
- 全量验证：`196 passed in 58.41s`。结果见`docs/results/FORMAL-AGENT-SMOKE-001.md`。

## 2026-11-12：ACTION-SANDBOX-001完成

- 新增版本化`ToolRegistry`，只有`noop`、官方训练器1-epoch低成本更新和全训练集回放重拟合可生成执行计划；任务、允许参数、学习率倍数、batch size和epoch均失败关闭。
- 训练前根据官方基线训练时间估计CPU成本，并同时检查候选、CPU和墙钟余量；输出必须位于独立运行根且不能与官方训练包重叠。
- 论文插件仅建立审计注册表，不自动授予执行权；注册要求固定插件根、文件SHA-256、许可证和任务兼容，文件变化后立即拒绝。
- 纠正了此前提案`replay_fraction=0.5`与官方训练器实际读取完整训练集之间的证据偏差：当前官方工具只接受可真实执行的`replay_fraction=1.0`。
- 验证：专项`20 passed`（Agent、沙箱和官方Harness），全量`201 passed in 68.83s`。

## 2026-11-12：PERF-A-OVER-001负结果

- 先冻结Batch 2的871条开发/373条确认身份，再从官方初始检查点运行6个仅使用Batch 1的过采样候选。
- 六候选全部无法恢复Acetaldehyde，开发F1均为0；最高开发Macro-F1 0.743187虽相对基线0.737945约+0.00524，但未通过目标类F1≥0.05门。
- 按预注册停止，不打开确认子集、不扩大倍数或学习率搜索。官方试运行和PyTRiO调用均为0。
- 该结果排除了“简单复制源域少数类即可解决Batch 2失败”的当前实现，下一假设转向先预测后标签反馈、面向下一批恢复的持续学习/回放。

## 2026-11-12：PERF-A-REPLAY-001完成并停止Gas本地扩展

- 实现了Batch 2—7严格“先预测—后反馈—候选只影响后续批次”的Gas因果更新运行器，并与官方A包Batch 1/2转换结果逐行语义对齐。
- A1在训练前因Batch 4指纹手工漏写一位被守卫拒绝，候选0次；失败证据保留。新增64位SHA-256契约测试后，A2从更正的官方原件指纹执行。
- A2完成三策略、18个预测轮、15个真实候选；5个候选上线、10个被SafetyGate拒绝。父链、派生训练/留出ID、禁止Batch 8—10和外部使用审计通过。
- 开发平均Macro-F1：静态0.579941、`current_only` 0.587581、两种回放均0.580352；复杂回放未通过相对简单策略+0.005门。
- 冻结确认平均Macro-F1：静态0.324722、`current_only` 0.469553、两种回放均0.439323。Batch 6—7为历史暴露，不宣称独立泛化。
- 候选累计CPU 10.1875秒、墙钟11.326秒、峰值RSS 57,888,768字节；官方试运行、PyTRiO、SwanLab使用均0。
- 按D-016/D-038保留`current_only + SafetyGate`并停止Gas本地回放扩展；结果详见`results/PERF-A-REPLAY-001.md`，下一任务转入`PERF-B-001`。
## 2026-11-12：REGRESSION-SPRINT-001 / Bearing

- 首次启动在训练前因官方包目录已有运行时`__pycache__`导致整树指纹不一致而停止，未生成候选；修正指纹只覆盖交付文件、忽略Python缓存，原包未删除或改写。
- B按整轴承`*_1/*_2/*_3`完成训练/开发/确认。9/9矩阵候选成功，开发选择`e5-lr3p0`，确认RMSE 829.314480→822.969735。
- 冻结配置从官方检查点续训后，历史暴露公开validation RMSE 681.159833→637.180224（改善6.4566%），MAE 563.105841→540.456251，SafetyGate接受。
- 合计11次训练作业、墙钟13.814秒、峰值RSS 67,186,688字节；官方试运行、PyTRiO、SwanLab均为0。机器校验`valid=true`，按D-039停止B搜索并进入C。

## 2026-11-12：REGRESSION-SPRINT-001 / Engine

- C按整发动机FD001+FD002/FD003/FD004完成训练/开发/确认，9/9矩阵候选成功；开发选择`e5-lr1p0`，确认RMSE 72.143834→71.526244。
- 冻结配置从官方检查点续训后，历史暴露公开validation RMSE 52.868573→52.367735（改善0.9473%），MAE 38.899830→38.322199，SafetyGate接受。
- 合计11次训练作业、墙钟68.592秒、峰值RSS 257,630,208字节；官方试运行、PyTRiO、SwanLab均为0。B/C汇总机器校验`valid=true`，按D-039停止回归搜索。

## 2026-11-12：SPRINT-HARNESS-001

- 在干净提交`09770c6`上将三个冻结候选日程接入同一官方训练器Harness；A/B/C各完成10轮、3次真实候选和7次日程完成no-op，三份机器复算均`valid=true`。
- A/B/C接受候选数为1/1/2；最终主指标分别为0.725695 Macro-F1、637.180224 RMSE和51.635999 RMSE。C的第二个低学习率候选进一步改善且MAE同步降至37.758009；其余拒绝候选未进入父链。
- 合计CPU 40.094秒；三任务峰值RSS均低于512MiB。Token、官方试运行、SwanLab均为0；本地运行明确不是实时漂移流。

## 2026-11-12：BRACE-MSI-0.2.0rc2本地发布验收

- 冲刺运行时代码提交`3af2afc3727cc2a74fe4afe3e29073896c48c597`完整回归`221 passed`；全新venv安装锁定依赖、SwanLab与wheel `0.2.0rc2`后，`pip check`无冲突、完整回归同为`221 passed`，编译检查通过。
- Docker上下文静态审计208文件、1,409,262字节、无数据/权重/密钥禁入项。实际镜像和4核8GB断网容器仍无本地运行时证据；CI验收入口存在但尚未执行。
- 发布校验记录固化于`results/RC2_VERIFICATION.json`；后续纯文档和发布工具变更不得改动运行时代码，否则必须重新完整回归。
- 确定性交付包已由干净提交`5d13b78`生成：源码归档193个跟踪文件，SHA-256 `da9e4a4c...bd8b7ae`；发布清单同时保留A1 INVALID、A2 SUCCEEDED、回归矩阵和十轮Harness证据边界，`image_artifact=null`未伪造容器通过。

## 2026-11-12：Docker运行时启用等待重启

- 检测到Docker Desktop 28.5.1客户端和后台进程，但Linux Engine API返回500；`wsl --status`明确报告`WSL_E_WSL_OPTIONAL_COMPONENT_REQUIRED`。
- 已用Windows可选功能接口启用`Microsoft-Windows-Subsystem-Linux`与`VirtualMachinePlatform`，不执行自动重启；系统登记Component Based Servicing `RebootPending`。
- 本轮未构建镜像、未生成`docker save`归档，也未把静态检查冒充容器验收。重启后只需验证引擎并执行Docker构建/断网Smoke/save，不重复模型训练、数据核验或完整回归。

## 2026-11-12：BRACE-MSI-0.2.0rc2真实Docker验收

- Windows重启后Docker Engine 28.5.1恢复为linux/amd64；原Docker Hub DNS错误解析导致官方`python:3.12-slim`不可达，因此改用可核验的Microsoft Azure Linux Python 3.12基础镜像，并固定摘要`sha256:379135d4...9266746`。
- 首次官方PyPI线路下载因低速发生SciPy内容哈希不符，pip正确拒绝安装。未绕过校验；Dockerfile保留官方PyPI默认值并增加可审计`PIP_INDEX_URL`构建参数，本机构建显式使用清华PyPI镜像，核心与SwanLab依赖均成功安装。
- 在干净提交`e28113c`上缓存重建`brace-msi:0.2.0rc2`：linux/amd64、170,356,869字节、非root用户`brace`/UID 10001、`pip check`无冲突，镜像内无数据、权重、Embedding、密钥或受禁目录。
- 使用`--network=none --cpus=4 --memory=8g --pids-limit=256`运行`synthetic-smoke`，状态`completed`且`candidate_count=3`；这只证明协议/容器运行，不是正式数据性能实验。
- 最终`docker save`归档为`D:/brace-msi-release/BRACE-MSI-0.2.0rc2/BRACE-MSI-0.2.0rc2-image-clean.tar`，170,378,752字节，SHA-256 `7b64490b0456c4b36bdc6189f34c9ce5e372894b911d76a3b40a6e8142e09327`；重新加载验证可读。发布相关定向测试`8 passed`，未重跑训练或完整回归。

## 2026-11-12：PYTRIO-SFT-001本地准备与审计

- 审计并安装官方`SwanHubX/pytrio-skill` v0.2.3；本机`pytrio 0.2.9`登录状态有效，只读能力查询实时返回`Qwen/Qwen3.5-4B`和`Qwen/Qwen3.8-27B`。未读取或保存真实API Key。
- 新增BRACE提案Agent的普通生成式SFT链：24条训练场景、12条archetype隔离留出场景；prompt权重为0，只监督严格assistant JSON和EOS。训练/留出固定SHA已写入代码与实验预注册。
- 留出评测记录schema/action/tool/预算安全/policy匹配率；每次远程响应后原子保存哈希和Token，不保存原始响应。远程输出目录不可复用，持久化Sampler保存后立即落独立收据，后续失败仍保留`trio://`路径。
- 远程执行在创建ServiceClient前核对固定seed与两份语料SHA；SDK导入、预检、部分采样、训练、保存和后评测失败均生成`failure.json`。模型服务失败时原有确定性Harness降级边界不变。
- 验证：专项`27 passed`，完整回归`233 passed in 63.48s`，编译、wheel包含性、diff与敏感信息扫描通过；独立代码审查无剩余Critical/Important。prepare-only产物位于`D:/brace-msi-pytrio/PYTRIO-SFT-001/`，真实采样/训练调用0次。
- 当前阻塞：用户截图时账户余额曾显示0，SDK无余额查询接口。必须先由用户确认当前可用额度大于0，再用全新`PYTRIO-SFT-001-A1`目录执行收费SFT；不得把本地准备写成微调完成。

## 2026-11-12：PYTRIO-SFT-001-A1失败与根因修复

- 用户确认充值10元后启动A1。按官方Qwen3.5-4B公开价格与字符/token最坏上界，完整A1预估约0.65元；未扩展预注册范围。
- 基础模型12条留出评测完成：输入4,213 Token、输出2,425 Token，严格schema/action/tool/budget/policy有效率均为0，说明结构化SFT有明确作用空间。
- 首个`forward_backward`和`optim_step`返回后，本地计算loss时将PyTRiO 0.2.9的`TensorData`直接传给`np.asarray`，触发`TypeError`。进程按失败边界停止，后续17步、持久化保存和微调复评均未执行；A1目录和失败收据保留。
- 根因是本地假客户端只返回NumPy数组，没有覆盖SDK真实强类型张量。修复为优先调用`TensorData.to_numpy()`、其次`tolist()`，再展平为数值数组；另区分远程已提交步与本地已记录loss步。
- 新增真实`TensorData`形态及远程请求/完成计数分离的红绿回归测试；专项20项、完整回归`235 passed in 62.58s`。未启动A2；按照L-AUTH-010，A2需用户重新授权并使用全新目录。

## 2026-11-12：PYTRIO-SFT-001-A2持久化Sampler

- 按L-AUTH-011从新目录执行同一冻结语料和配置：Qwen3.5-4B、rank 8、3 epoch、batch 4、学习率1e-4。18/18远程优化步完成，最终监督Token损失0.009076，保存89,565,048字节持久化Sampler收据；不记录凭据或原始工业数据。
- 原始训练后评测被本地解析器全部判为无效；单例诊断证明模型输出是完整JSON后附PyTRiO/Qwen的`<|im_end|>`。原始`result.json`与`tuned_evaluation.json`保持不变，作为误判证据。
- 通过红绿测试只允许剥离精确终止标记，任意其他尾随文本仍拒绝。对同一Sampler和同一冻结12例重新采样，`tuned_evaluation_rescored.json`得到schema/budget 100%，action/tool/policy 66.67%；基础模型对应五项均为0。
- 训练语料每epoch 10,097 Token、三轮30,291 Token；连同A1/A2采样和少量诊断，按公开单价保守估算累计低于0.25元，实际费用仍以平台用量页为准。官方十次评测机会使用0。专项20项、完整回归`236 passed in 63.40s`。

## 2026-11-12：PYTRIO-HARNESS-001-A2公平对照

- A1首轮Smoke中A/B/C均返回合法noop，暴露最低三次候选要求未进入聚合证据。新增`minimum_candidate_events`配置、身份无关控制提示和确定性守卫；大模型不能用noop绕过最低真实实验数，覆盖原因和原始建议均审计保留。
- 确定性与PyTRiO两个独立臂各运行A/B/C十轮；六运行都完成3个真实候选并由机器复算`valid=true`。最终A/B/C主指标逐项相同：0.725695 Macro-F1、656.351785 RMSE、52.350178 RMSE。
- A2 Sampler共30次调用，原始建议30次均为noop；每任务前三次由守卫覆盖，合计输入20,072、输出1,961 Token，没有新增工业模型性能。结果按负证据保留，不声称Agent带来性能增益。
- D-042只允许一次针对最低候选证据的有界SFT与新留出；若失败，停止LLM调参并以确定性BRACE为正式默认。

## 2026-11-12：PYTRIO-SFT-001-A3合规Sampler

- 使用冻结的48训练/12新留出合规语料执行D-042允许的唯一一次追加SFT；Qwen3.5-4B、rank8、3 epoch、batch4、学习率`1e-4`，36/36远程步骤完成，最终监督Token损失0.017709。
- 基础模型在新留出上的schema/budget/action/tool/policy分别为83.33%/66.67%/50%/50%/50%；A3持久化Sampler五项均为100%。完整`trio://`路径只在Git外`result.json`收据，不写公开配置。
- A/B/C真实首轮均由模型主动提出`incremental_update`，3/3候选通过门控且0最低候选守卫覆盖；满足预注册成功标准。按D-043停止全部后续LLM调参。

## 2026-11-12：PYTRIO-COMPETITIVE-001-A1

- A3 Sampler负责结构化动作意图，确定性BRACE只应用已经冻结的任务参数日程并保留预算、沙箱和SafetyGate；不新增工业模型参数搜索。
- A/B/C各完成10轮和3个真实候选，逐任务`validate-only`均返回`valid=true`，0守卫覆盖、0服务回退。最终主指标为0.725695 Macro-F1、637.180224 RMSE和51.635999 RMSE；B/C MAE同步改善。
- 总输入/输出Token为20,362/2,272；三任务CPU为2.516/4.812/33.750秒，峰值RSS均低于512MiB。A第8轮、C第10轮各一次预算耗尽后的额外训练建议在训练前被拒绝，没有资源消耗或父链污染。
- 结论边界：Agent实现了自主合规动作选择，但工业模型性能来自冻结参数和门控，不把二者混写为LLM性能增益。公开验证历史暴露，官方试运行0次。

## 2026-11-12：BRACE-MSI-0.3.0rc3本地发布验收

- 源提交`66f1cae`构建`brace-msi:0.3.0rc3`，linux/amd64、240,579,085字节、非root UID10001；镜像内`brace-msi 0.3.0rc3`、`pytrio 0.2.9`、无Torch、无数据/模型权重/API密钥，`pip check`通过。
- 在`--network=none --cpus=4 --memory=8g --pids-limit=256`下，两种内部协议Smoke均完成，候选数分别3与4。`docker save`归档240,602,112字节，SHA-256 `0daef2e0e66cd2d3bc809a5d836a03020d1f90d677df91830fedc4feeb6d325a`，`docker load`验证通过。
- 打包前代码回归`243 passed in 66.60s`；发布工具增加证据强校验后最终全量回归`246 passed in 69.62s`。全新venv安装锁定依赖、PyTRiO和项目后`pip check`通过，回归`243 passed in 65.46s`。第一次项目构建隔离因本机配置镜像TLS证书链失败，未绕过TLS；在已安装锁定构建依赖后用`--no-build-isolation`成功，失败事实保留在RC3验证记录。
- 发布工具新增真实容器证据和镜像归档哈希强校验，相关定向回归15项通过。该证据只证明本地Harness交付，不是官方隐藏评测成绩。

## 2026-11-13：提交材料与SWANLAB-FINAL-001

- 生成正式作品说明书Markdown、DOCX和PDF；DOCX通过OOXML验证并经Word转PDF目视抽查10页。建立平台字段清单，明确Sampler路径、API Key和镜像的安全填写边界。
- 新增最终记录脱敏转换器，先验证缺失模块测试失败，再实现部署链指标映射；专项6项通过。输出不包含检查点哈希、输出目录、Sampler路径或凭据。
- 在提交`b64bf7f`上以冻结A3与参数运行A/B/C各10轮/3候选，三项`validate-only`均为`valid=true`；结果为0.725695424 Macro-F1、637.180224 RMSE、51.635998675 RMSE，不用于再选型。
- SwanLab 0.10.4公开项目`nanmo-max/brace-msi-final`同步3个实验并由API确认全部`FINISHED`、各10条记录。Gas首次同步在远端创建后因Windows GBK无法输出emoji而中止，使用UTF-8和同一run ID幂等恢复，未产生重复实验。
- GitHub远端已有独立main初始提交，按稳定边界未覆盖main；推送`task/core-001`分支及指向冻结提交`c528420`的`brace-msi-v0.3.0-rc3`标签。
- 最终全量回归为`248 passed in 70.75s`；Markdown相对链接检查通过。作品说明书DOCX通过OOXML验证并生成10页PDF，DOCX/PDF SHA-256分别为`0822ae41...f132213`和`cc67c2c4...e63f292`。

## 2026-11-13：PAPER-FUSION-SPRINT-001

- 在独立`codex/paper-fusion-sprint`分支实现因果特征、组折验证、8候选Successive Halving、异构CPU集成、Gas蒸馏候选、原子恢复和单次validation锁；新增`paper-fusion-run` CLI及C-only容器配置。
- 内部开发：A教师集成Macro-F1 0.978493、蒸馏学生0.869930；B组折RMSE 1546.212091；C组折RMSE 47.298452。完整候选训练峰值RSS为3,019,251,712字节。
- 冻结后公开validation只打开一次：A 0.687918 Macro-F1、B 644.113606 RMSE、C 42.330230 RMSE。只C相对RC3改善18.02%，相对静态改善19.93%；A/B由门控保留RC3。
- `validate-only`返回`valid=true/stage=completed`；结果和负证据见`docs/results/PAPER-FUSION-SPRINT-001.md`。公开validation历史暴露，不是隐藏测试或官方成绩；官方试运行仍为0。

## 2026-11-13：BRACE-MSI-0.4.0rc1发布收口

- 冻结A/B沿用RC3、C采用PaperFusion的混合候选；未再打开公开validation，也未消耗官方十次试运行。完整回归`264 passed`。
- 构建linux/amd64镜像`brace-msi:0.4.0rc1`，镜像内部240,701,023字节、非root UID10001、含PyTRiO 0.2.9且无PyTorch/数据/权重/密钥。4核8GB、断网、256 PID限制下完成C冻结候选训练，峰值RSS 3,198,783,488字节。
- `docker save`归档位于`D:/brace-msi-release/BRACE-MSI-0.4.0rc1/BRACE-MSI-0.4.0rc1-image-clean.tar`，240,723,968字节，SHA-256 `97bb0a9fcfed688ba1b7feadadf09528e232fea578d06a1d782f2dccee306dfa`，`docker load`验证通过。
- 作品说明书DOCX/PDF完成10页逐页渲染检查；最终表格行禁止跨页，未发现截断、重叠或缺失字形。材料只报告公开暴露验证和本地容器证据，不表述为隐藏测试或官方成绩。
- 发布包重建曾因材料生成脚本被误判为运行时代码而失败；新增红绿回归测试后，仅将`scripts/build_submission_document.js`加入发布后非运行时白名单，核心运行时变更仍会失败关闭。
- 独立分支`codex/paper-fusion-sprint`已推送至GitHub；未合并main、未移动`brace-msi-v0.3.0-rc3`标签。最新发布包源码归档SHA-256为`fb5d66966f764c280c7563e1c5895fc3fa9e9ea5ca863f7999c2fc551fd74d23`。

## 2026-11-13：PLATFORM-TRIAL-V1诊断与失败关闭修复

- 登录官方平台只读核验提交与运行页：首次试运行属于旧提交v2，已使用1/10次，正式评测0/2；用户确认RC4尚未提交。
- 原始报告SHA-256为`8B7B5CEC3C50775BD5621DCBEB8DE7337BC39F0F6123767B27E36E004BBA5368`。三任务均完成10轮并选择第1轮，但平台Token为0；隐藏主指标为A 0.413368 Macro-F1、B 691.660970 RMSE、C 56.220512 RMSE。
- 代码审计定位三条可复现静默路径：CLI默认确定性、PyTRiO客户端传输/解析回退、Harness异常二次回退。无法仅凭平台报告区分实际触发层，也无法确认旧提交绑定的镜像编号。
- TDD红阶段新增4项用例并得到4失败/22通过；实现显式provider和正式PyTRiO双层失败关闭后，专项`26 passed in 1.87s`。完整回归和新镜像验收由`RC5-FAILCLOSED-001`继续，RC4归档保持不变。
- Docker断网负向验收进一步发现PyTRiO SDK初始化/控制请求不受`APIFuture.result(timeout=...)`单点约束；通过官方`pytrio.configure`统一限制请求、控制重试、采样重试、容量等待和流式采样超时，保留一次被人工终止的长等待作为失败证据。
- `BRACE-MSI-0.4.0rc2`最终完整回归`271 passed in 60.04s`；镜像linux/amd64、240,662,563字节、UID10001、`pip check`通过且无Torch/权重/数据/密钥。严格断网PyTRiO测试在12.726秒以`transport_error`退出，运行文件0项；`docker save`归档240,685,568字节、SHA-256 `daf42786...307d32`并重载成功。

## 2026-11-13：Qwen3.5-4B基础模型提交路线

- 平台重复拒绝持久化Sampler而基础模型校验通过，登记B-PLATFORM-003与D-050；不猜测平台Sampler失败的具体根因。
- TDD先将“无Sampler路径的PyTRiO正式选择”改为预期行为并观察1项失败，再以最小改动移除Sampler强制路径；显式provider、严格schema、超时配置与Harness失败关闭保持不变。版本独立推进为`0.4.1rc1`，不覆盖`0.4.0rc2`。
- `PYTRIO-BASE-SMOKE-001`唯一远程尝试在本机约90秒内无可核验响应后被终止，无proposal、Token或响应哈希收据；按预注册停止且不自动重试。专项27项、完整回归271项通过；容器构建与验收继续由同一任务完成。
- `BRACE-MSI-0.4.1rc1`真实镜像验收完成：linux/amd64、240,662,396字节、UID10001、无Torch/权重/数据/密钥；4核8GB断网Smoke完成，基础模型无Sampler路径入口8.696秒以`transport_error`失败关闭且运行文件0项。`docker save`归档240,685,056字节，SHA-256 `63fff363...54e48e`并重载成功。

## 2026-11-13：DUAL-RC-001

- TDD新增`generalist-fit`单包入口：只用train内部证据选择模型，生成实际嵌入父checkpoint的单个`checkpoint.npz`；`generalist-predict`继续作为独立预测入口。专项与发布测试14项通过。
- `BRACE-MSI-0.5.0rc1`在Docker Desktop Linux引擎真实构建。镜像为linux/amd64、241,051,292字节、UID10001；容器版本0.5.0rc1、`pip check`与`compileall`通过，禁入文件扫描为空。
- 在`--network=none --cpus=4 --memory=8g --pids-limit=256`下完成十轮受控闭环Smoke；B/C从只读官方包全量训练并分别生成239,914/200,616字节父集成产物，独立预测成功。运行时产物只在挂载输出卷，未进入镜像。
- 由于Linux/Windows序列化哈希不同，按冻结门仅做一次跨平台等价性验收；B/C预测指标与D-056完全一致并通过原安全门，未修改算法或参数。
- 完整回归`329 passed in 93.98s`。主机全局Anaconda仍有历史无关依赖冲突，未冒充干净环境；发布容器本身`pip check`通过。
- `docker save`归档为241,074,176字节，SHA-256 `e3cc5f1c3c2a879344632e083623001864c8dac380c6ebb87239ac5de9799747`；删除本地镜像标签后`docker load`成功。A仍保留父模型，没有虚构严格提升；平台状态仍全部待验证。

## 2026-11-15：FORMAL-CONTINUATION-RC-001

- 登记旧提交平台拒绝截图为O-PLATFORM-008，明确它不是0.5.0结果；D-058据此将异构HGB/PaperFusion从正式提交线剥离并保留历史研究证据。
- TDD新增正式镜像命令边界和A/B/C两代父链验证；红阶段复现研究命令仍会执行，修复后镜像环境`BRACE_FORMAL_RELEASE=1`使四个异构模型命令失败关闭。
- A/B/C分别从官方baseline执行原生续训并继续从子checkpoint续训；schema、标准化、权重、Adam、epoch、step和父哈希链验证通过。完整回归`333 passed in 131.98s`。
- `BRACE-MSI-0.5.1rc1`在4核8GB、断网、256 PID下完成三任务各十轮/3候选，三项`validate-only`为`valid=true`，官方独立预测入口三项通过。公开指标只作历史暴露续训链证据，不用于新调参。
- 镜像linux/amd64、241,750,529字节、UID10001，无数据/权重/密钥；`docker save`归档241,774,080字节，SHA-256 `6331280b...34e181`，删除标签后`docker load`恢复成功。官方试运行、PyTRiO、SwanLab调用均0。

## 2026-11-15：PLATFORM-NATIVE-001

- 复现旧`0.5.1rc1`失败根因：平台仅挂载`/data`、`/previous`、`/workspace`、`/output`，而旧入口在训练前强制审计完整官方包树，因此必然在训练前失败；未削弱旧审计，新增独立原生适配层。
- TDD实现`describe/start/submit`、父MLP/Adam/标准化/计数续接、当前批Update/Gate、固定Anchor、合法Replay、严格门控、原子输出及私有状态恢复；增加每轮结构化决策收据和PyTRiO受控建议边界。
- 专项15项及完整回归348项通过。最终`0.6.0rc1`在A/B/C各完成10/10决策、10/10真实候选和独立预测，共30轮；父链全部连续，A/C候选全部被严格门拒绝、B接受1次。
- 最终镜像linux/amd64、241,855,558字节、非root、无数据/权重/密钥；4核8GB断网、只读根、256 PID验收通过。`docker save/load`归档241,879,040字节，SHA-256 `F98FB679...CBC62D`。
- 官方试运行0次；断网验收Token为0并明确记录，未把PyTRiO自动测试冒充在线服务成功。精确平台启动与凭据注入仍等待外部材料。

## 2026-11-15：NATIVE-COMPETITIVE-RC-001 Task 1

- 修正成绩归属：早期冻结日程与`0.6.0rc1`分开记录，后者公开观察为A/B/C `0.714030/660.076488/52.868573`。
- 新增A/B/C官方`Model.fit`与`_NativeModel.fit`逐状态差分：一轮loss、权重、Adam、mean/scale、metadata和预测逐值一致；Native 1+1与连续2 epoch一致。
- TDD红阶段发现Native会接受负Adam二阶矩及官方模型拒绝的非法metadata；补齐device、schema、整数、架构、数值、参数量、预处理和Adam状态验证后转绿。
- 相关验证`37 passed in 57.95s`。既有30轮只读反事实为A/B/C正收益0/4/6、实际接受0/1/0；没有新增训练或读取公开validation。

## 2026-11-15：NATIVE-COMPETITIVE-RC-001 Task 2

- TDD实现竞争模式的真实retain：十轮仍逐轮决策，但只有第1/5/9轮产生候选；retain不训练、不计作拒绝候选。PyTRiO合法`NOOP`同样进入retain路径。
- Gate不再使用统一5%/Anchor零退化：分类与回归分别检查主辅指标，B/C最小相对收益为0.5%，相对Anchor容忍度2%，且Replay历史退化超过2%即拒绝。
- DEV-A1把三个候选集中在前期，B部署后全历史RMSE从233.357824恶化到239.789618；DEV-A2虽把候选分散到1/5/9轮，B首轮部署后恶化到299.846993，C仅从55.380385改善到55.342797但MAE退化。两次均为train内部负/混合证据，未读取公开validation。
- 针对实际根因，首轮仍训练以形成真实实验，但没有Replay历史时强制拒绝部署；B/C强候选移到第5轮，使用四批合法历史作风险证据。专项`32 passed`，完整回归`365 passed in 144.39s`。

## 2026-11-15：NATIVE-COMPETITIVE-RC-001 Task 3

- DEV-A3安全但零增益；DEV-A4利用安全Replay收益使A train Macro-F1提升；DEV-A5在不放宽主指标/Anchor/Replay门的前提下，加入1%当前辅助指标容忍，A/C train内部改善且B保持父模型。
- 冻结提交`55a9621`后只打开一次公开validation：A Macro-F1 `0.725695`、C RMSE `51.949287`，均优于0.6；B竞争策略回到官方父模型`681.159833`，未达到0.6的`660.076488`，不单独发布。
- 发布组合通过显式能力路由复用两个已验证策略：A/C竞争策略，B旧protocol；差分测试证明B路由与纯protocol最终checkpoint一致。COMPOSE-A2在train内部完成A/B/C `3/10/3`候选，父链有效；没有第二次读取validation。

## 2026-11-15：NATIVE-COMPETITIVE-RC-001 Task 4—5

- Native基础Qwen在线A1/A2取得2次非零Token响应，A2有1次合法建议被执行；第三次在新进程仍为服务RuntimeError，按停止条件登记`BLOCKED_EXTERNAL`，未继续消耗余额。失败或断网时只执行`noop/retain`，不静默训练。
- COMPOSE-A2三任务聚合记录经敏感字段扫描后同步至SwanLab公开项目，每任务112条记录；未上传逐样本特征、标签、checkpoint或凭据。
- 独立审计发现PyTRiO提案可越过冻结轮次/参数；新增红绿测试后，Agent只保留训练/retain意图，A/C候选轮、B协议轮、动作、epoch和学习率由冻结策略约束，约束写入收据。三任务对照证明带训练意图与确定性冻结策略最终checkpoint一致。
- `BRACE-MSI-0.7.0rc1`修复后镜像为linux/amd64、241,874,808字节、UID10001；377项完整回归通过。4核8GB、断网、只读根和256 PID下，A/B/C分别完成3/10/3候选及完整十轮，父链连续，独立`submit`生成1,244条预测。
- A/B/C最大RSS为94,965,760/113,430,528/238,686,208字节，最终checkpoint为132,180/36,600/28,848字节。归档241,897,984字节，SHA-256 `B4EF8820...5FB1BD7`，`docker load`通过。
- 本轮容器只作工程验收，不产生新的独立性能选择；发布性能仍以冻结后唯一公开确认A `0.725695`、B复用`0.6`的`660.076488`、C `51.949287`为边界。

## 2026-11-15：PLATFORM-REPORT-SIM-001

> 后续更正：本节V1对同一公开validation逐轮评估并据此选轮，已由D-067判定为选择污染；仅保留历史追溯，修正见`REPORT-EVIDENCE-FIX-001`。

- 新增三张旧官方试运行完整报告截图和两张平台公告截图已按哈希登记；它们确认旧提交14,773条隐藏预测、三任务10/10轮、最终均采用第1轮及详细CPU/运行时字段，但没有新增正式调用命令。
- 使用修复后RC7容器轮次checkpoint，逐轮只读评估官方公开validation并生成官方页面字段形态的JSON/HTML；不训练、不改模型、不调用PyTRiO或官方平台。
- V1曾按重复公开validation模拟选择第9/1/9轮并报告0.725695 Macro-F1、660.076488/51.949287 RMSE；该选轮结论已判无效，数值仅作为历史暴露validation的描述性记录保留。
- 产物位于`D:/brace-msi-native-competitive/RC7-OFFICIAL-REPORT-SIM/`；JSON/HTML SHA-256为`5137E3C8...37F92CC8`、`AB9D81BD...AC182F80`。

## 2026-11-15：PYTRIO-ONLINE-001

- 只读能力查询确认本机鉴权有效，PyTRiO 0.2.9仍返回`Qwen/Qwen3.5-4B`与`Qwen/Qwen3.8-27B`；正式验收仅使用已通过平台校验的4B基础模型。
- 三个独立进程均在第一次请求取得严格合法提案，累计输入/输出Token为1103/581；第1轮建议真实训练候选，第2/3轮被冻结日程约束为retain。公开validation、LoRA/SFT和官方试运行使用均为0。
- 三次延迟为13.626、16.559、13.335秒；旧15秒默认位于正常延迟边缘。TDD先得到默认15秒断言失败，再将Native入口默认调整为60秒；相关72项与完整382项回归通过。
- 机器摘要位于`D:/brace-msi-pytrio/PYTRIO-ONLINE-001-A1/summary.json`，SHA-256为`3005C56B...D063C7AF`。本机在线门已通过，平台容器内网络、凭据注入和Token报告仍需正式试运行确认。
- 发布容器补验收：发现干净镜像没有Tokenizer缓存时会尝试公网下载并立即失败；因此只打包7个固定哈希的Tokenizer/配置资产，不打包模型权重。重建后的`0.7.1rc1`在4核8GB、只读根、256 PID容器中不挂载宿主缓存取得330/184 Token的合法提案并实际训练候选；断网测试两次失败后只保留父模型。最终`383 passed in 154.27s`，镜像248,863,860字节，`docker save`归档248,888,320字节且重载通过。

## 2026-11-15：UNSEEN-SIM-001

- A1在训练前发现Battery 25条放电记录的`Capacity`为空数组并失败关闭；A2完成流程但报告实验ID与目录不一致，标记INVALID。两次负证据均保留。
- A3确定性对照与A4 PyTRiO对照均完成Battery/Hydraulic/Mill各10轮，父链、分组隔离、checkpoint加载和协议检查通过。
- A4使用`Qwen/Qwen3.5-4B`基础模型，16次有效响应、15次结构化建议执行，输入/输出Token 8,100/3,470；Agent门通过，未使用Sampler、SwanLab或官方试运行。
- 独立confirmation结果为Battery RMSE 0.335763→0.409475、Hydraulic Macro-F1 0.238964→0.092620、Mill RMSE 0.392140→0.392140；严格改善0/3，性能成功标准失败。
- 三个round 10 checkpoint独立加载复算与报告一致，大小均远低于64 MiB；当前HEAD完整回归`383 passed in 171.63s`。完整证据见`results/UNSEEN-SIM-001.md`。

## 2026-11-15：UNSEEN-REPORT-001

- 依据O-PLATFORM-010的界面要素，从冻结A4机器JSON生成单页HTML和机器JSON；未重新训练、调用PyTRiO、同步SwanLab或消耗官方试运行。
- 三任务各10轮，报告包含完成轮次、最终采用、确认样本、CPU/运行时间、最终指标、逐轮适应指标、模型选择及30个可展开实验记录。
- HTML/JSON SHA-256为`F9EFD518...A5EC798`/`BC5CCAF5...FDD65FE`；字段、展开记录和敏感标记扫描通过。完整说明见`results/UNSEEN-REPORT-001.md`。
- 生成器专项2项及当前HEAD完整回归`385 passed in 156.71s`。

## 2026-11-15：OFFICIAL-DATA-REPORT-001

> 后续更正：本节展示继承V1选择污染，只保留界面样式证据；修正见`REPORT-EVIDENCE-FIX-001`。

- 未重训、未重新读取公开validation、未调用PyTRiO或官方试运行；只转换`PLATFORM-REPORT-SIM-001`已冻结的Gas/Bearing/Engine十轮机器报告。
- 生成三任务单页HTML及机器JSON：A/B/C各10轮，共30个可展开记录；展示公开验证样本、CPU/运行时间、Accuracy/Macro-F1或MAE/RMSE/NASA、模型选择、动作、Token和资源。
- V1页面曾显示A第9轮、B第1轮、C第9轮；其validation选轮语义已判无效。V2改由Harness部署链确定相同模型来源，冻结后validation只描述最终checkpoint，不参与选择。
- HTML/JSON SHA-256为`A15445AB...90BEDEA`/`AB64E5A7...0B40ED1`；页面显著标注“历史暴露公开验证、非官方隐藏测试”，敏感标记扫描未发现API Key。完整说明见`results/OFFICIAL-DATA-REPORT-001.md`。
- 生成器专项`4 passed`；当前HEAD完整回归`387 passed in 156.61s`。

## 2026-11-15：REPORT-EVIDENCE-FIX-001

- 审计确认训练批次ID、特征和设备组没有与公开validation直接重叠证据；问题位于报告层：V1对同一公开validation逐轮重复评估并用其选择第9/1/9轮，构成验证集选择污染。
- TDD新增报告证据链测试后，将V2改为逐轮只读取冻结收据中的稳定/候选Gate指标及真实部署决定；策略冻结后，仅对各任务`round-10/checkpoint.npz`评估一次公开validation。
- 机器复算：三任务30轮，`public_validation_evaluations=3`，零`selected_round`/`selected_metrics`字段，零逐轮`public_validation_metrics`；最终来源由部署链确定为A第9轮、B第1轮、C第9轮。
- V1和原展示文件保留并追加污染警示；最终V2-A2位于`D:/brace-msi-native-competitive/RC7-OFFICIAL-REPORT-SIM-V2-A2/`，页面视觉检查通过。
- 专项`7 passed in 0.81s`；最终HEAD完整回归`390 passed in 151.76s`。

## 2026-11-15：OFFICIAL-FLOW-SIM-001

- 将正式本地复演从“父模型已见train按行均切十段”替换为任务自然`StreamPlan`：Gas自然批次/时间、Bearing寿命进度、Engine完整unit；旧入口只保留历史并标记低保真。
- 新增预测封存与外部`ScoreVault`：每轮无标签预测先落盘并哈希，之后才物化反馈、Update和Gate；未来轮及最终确认不提前物化，Prequential指标不进入ActionPolicy。
- `start_round`新增向后兼容的独立Gate能力；专项证明当前Gate不进入训练、Anchor或Replay。
- 官方数据A2三任务均10/10轮、父链有效，候选/采用为3/0、10/1、3/0。B在同批Gate采用后跨未见轴承确认明显退化，作为负证据保留；A/C保持静态。
- 生成本地官方要素JSON/HTML，明确`hidden_test_status=not_started_not_available`及确认集第2次历史暴露。最终完整回归`399 passed in 153.34s`；详情见`results/OFFICIAL-FLOW-SIM-001.md`。

## 2026-11-16：DELAYED-GAIN-SIM-001

- 在V1未来隔离和预测封存上，将`arrival_metric_t`结构化送入决策；上一轮有部署时，在第`t+1`批对当前模型与直接前任运行同样本影子预测，按主指标统一为“正值更好”的配对延迟收益。
- 测试先行新增序贯训练/retain、下一批结算、同样本配对、分类/回归方向和HTML报告测试。A2完整运行发现B第9轮部署后第10轮延迟收益`-310.293697`，但状态机继续保留坏模型，最终确认RMSE `993.202677`。
- 新增严格兼容的直接前任回滚：负延迟收益优先原子回滚，不训练候选、不消耗候选预算，收据保存回滚checkpoint哈希。A3 B第10轮回滚后确认RMSE恢复至`241.980799`；A/C候选均未通过Gate，保持父模型。
- A3三任务各10轮、父链有效、确认各读一次；本地确认第5次暴露且正式隐藏状态未开始。SwanLab只生成三个离线聚合运行，PyTRiO本轮未调用。
- 验证：专项`59 passed in 27.33s`；完整回归`407 passed in 146.63s`；compileall、diff、机器不变量和密钥扫描通过。结果见`results/DELAYED-GAIN-SIM-001.md`。

## 2026-11-16：COMPETITIVE-POLICY-002与0.8.0rc1

- 在确认/public validation读取0的条件下，先完成教师上界、17种原生MLP候选及九种连续父链recipe筛选；学习率倍率累乘和B提前激进更新两类失败均保留并修复/淘汰。
- A2成熟趋势门在三任务平均有向收益均为正；A3提前触发令B平均收益降至`-92.775049`，因此恢复A2逻辑。最终自审发现A4的趋势均值包含Gate标签；A5修复后因报告ID失配判无效，A6严格只用Update目标并取得A/B/C平均有向收益`+0.319620` Macro-F1、`+21.850812`和`+0.438766` RMSE降低。
- 正式运行时新增身份无关Portfolio路由、受控recipe、自动到达证据、直接前任影子比较和负收益回滚；移除容器对B的旧protocol强制覆盖。PyTRiO仍只表达受限动作意图，断网两次失败后retain。
- `BRACE-MSI-0.8.0rc1`完成421项回归、三任务4核8GB只读断网容器、禁入扫描、`pip check`、版本核验及`docker save/load`。最终归档SHA-256为`CB9F28D1...FC232E6EA`；修正前归档保留但不得上传。这些均为本地代理/工程证据，不是官方隐藏成绩。

## 2026-11-16：PLATFORM-BRIDGE-001与0.8.1rc1

- 登记平台反馈O-PLATFORM-011：旧草稿适配器有缺陷，尚不能判断镜像兼容；平台侧指出空输出挂载、顶层父哈希、十轮预算、retain产物声明和无mode argv prefix五个映射点。
- 按TDD新增显式父SHA-256和期望轮次参数；哈希不匹配在读取训练数据前失败，轮次必须由持久化workspace历史证明。每轮收据新增实际`checkpoint.npz`产物声明，retain保持父文件哈希不变。
- 平台运行时54项、完整回归424项通过。官方A父checkpoint在4核8GB断网只读容器中连续运行两轮，均正确retain并声明有效产物；独立预测1,244条，`pip check`与禁入扫描通过。
- 冻结`0.8.1rc1`桥接补丁：镜像249,004,758字节，`docker save`归档249,029,120字节，SHA-256 `9B1A1822...184ED7E`，删除tag后重载ID一致。未消费正式试运行、未调用在线PyTRiO、未生成新SwanLab记录；平台私有桥接与真实生命周期仍为外部阻塞。

## 2026-11-16：PLATFORM-PREFLIGHT-001与0.8.2rc1

- 新平台反馈只完成静态preflight且在`Because native PyTR...`处截断，明确没有宣称成功。对首个平台完成版与0.8.1做启动差分后，本机稳定复现：0.8.1无挂载裸启动因默认`start`尝试创建`/workspace`，非root退出1；历史版默认`--help`退出0。
- 测试先行把无输入安全启动写入容器契约；红灯确认0.8.1不满足，随后只将默认命令恢复为`--help`，显式`start`/`submit`和全部训练决策逻辑保持不变。运行时提交`8566807`。
- 完整回归首轮`424 passed in 158.19s`；最终复核一度出现C父链Windows子进程无stderr返回`4294967295`，该用例立即单测通过，随后完整复跑`424 passed in 160.27s`。0.8.2裸启动退出0；官方A父checkpoint在4核8GB断网只读容器显式start成功，输出132,180字节checkpoint；独立submit生成1,244条预测。
- 镜像248,956,508字节，禁入扫描0、`pip check`通过；`docker save`归档248,980,992字节，SHA-256 `7CA09B02...BBE7784F`并成功重载。首次使用PyPI构建因下载NumPy超时失败，改用国内镜像后成功；失败未冒充验收。
- 未调用在线PyTRiO、未同步新SwanLab、未使用隐藏数据或官方试运行。平台真实兼容性仍为外部阻塞。

## 2026-11-17：第一性原理重建取证

- 只读核验官方平台运行页四条试运行：两条成功、两条失败；正式评测0/2。没有点击重跑、保存、上传或正式评测。
- 两次成功均为A/B/C各10轮、总Token 0且逐轮/隐藏指标完全一致，证明旧流程可跑但不证明Agent工作。
- 保存两次失败原文：私有PyTRiO协议无法桥接宿主Chat Completions；最新入口没有真实模型调用且固定workspace目录无法跨轮。
- 官方SDK 1.0.2逐项核验：每轮真实宿主模型调用、父artifact、候选/retain、状态、历史和逐行预测为最小正式契约。
- 建立`codex/first-principles-rebuild`分支、取证报告、最小正式运行核规格和实施计划；未训练、未调用付费API、未消耗官方次数。
- Agent C只读性能审计建议先保留窗口/训练强度与父候选权重融合，复杂回放、异构模型、论文大模块退出正式首版。
- `FORMAL-MINIMAL-001` Task 1按TDD完成：5项边界测试先因`brace_formal`缺失失败，随后直接宿主模型调用覆盖低Token上限、模型别名、无usage、非法提案retain以及十轮唯一工作目录； focused `5 passed`，完整回归`442 passed in 148.23s`。
- `FORMAL-MINIMAL-001` Task 2按TDD完成：3项差分测试先因正式模型核心缺失失败；随后最小NumPy续训实现与已验证`_NativeModel`在同一父checkpoint、同一样本顺序和同一超参数下的loss、全部权重、Adam一二阶矩、epoch/step及预测逐项一致，保存重载同预测且产物小于64 MiB。focused `3 passed`，完整回归`445 passed in 149.62s`；未启动新训练或官方试运行。
- `FORMAL-MINIMAL-001` Task 3按TDD完成：4项入口测试先因`brace_formal.submission`缺失失败；实现每轮先调用宿主模型、最多一个父链候选、公开validation安全门、retain、唯一workspace状态、候选提交和独立预测。另以真实官方`Round`对象验证retain转录顺序为`history_request→model_request→state_request→round_complete`且引用真实call ID。focused `18 passed`，完整回归`450 passed in 148.54s`；正式薄入口已切换至`brace_formal`，未调用平台。
- `FORMAL-MINIMAL-001` Task 4完成：先红灯确认十轮模拟器缺失，再以独立合成A/B/C数据执行各10轮。A2为30/30轮、30个唯一宿主call ID、三任务父链与状态链全有效；A候选采用4/10、B/C各10/10，接受与拒绝均被覆盖。A1因源码直跑缺`PYTHONPATH`及遗留默认workspace冲突判失败并保留；A2显式隔离工作目录后通过。机器JSON SHA-256 `83834956...A68E2EF`；完整回归`451 passed in 149.89s`。所有报告均标注本地合成协议测试、非官方成绩。
- `FORMAL-CLEAN-IMAGE-001`完成：allowlist红灯先确认`Dockerfile.formal`与最小锁文件缺失，随后只复制官方SDK、`brace_formal`和两个固定入口；递归`.pyc`首次进入镜像被审计发现并由新增红绿测试排除。最终镜像linux/amd64、81,183,334字节、UID10001，只含NumPy，无旧`brace_msi`、PyTRiO、SwanLab、sklearn、SciPy或psutil。精确最终镜像在4核8GB断网/只读数据与父模型挂载下完成A/B/C各10轮、30次宿主调用和各5行独立预测；候选最大132,180字节，`pip check`通过。`docker save`归档81,201,152字节、SHA-256 `DC73FAFC...C05C39E`，删除tag后重载ID一致；完整回归`455 passed in 148.45s`。
- `FORMAL-PERF-001-A1`按预注册只读取官方train内部三折：A的e1平均Macro-F1增益`+0.004902644`并胜出；B跨轴承组留出中e1/e3lr3/soup全部为负，retain胜出；C的0.25父候选融合3/3折改善、平均RMSE降低`0.189824503`。正式入口新增相同身份无关portfolio；若内部证据只能retain，即使Agent要求train也记录安全否决并保留父模型。首次0.10.1容器探针在该否决修正前已生成，现降级为过渡证据，不作为最终RC；尚需0.10.2精确镜像验收。
- `FORMAL-PERF-001-A3`完成：精确0.10.2镜像在4核8GB断网容器完成A/B/C各10轮，共30个唯一宿主调用和15行独立预测；B十轮全部由训练内负证据否决训练，A/C分别部署1/3次。
- 冻结后公开validation描述性诊断为A Macro-F1 0.725695、B RMSE 681.159833、C RMSE 52.331755；该数据历史暴露且不参与选择，不作为独立或官方成绩。
- 完整回归`458 passed in 143.01s`；镜像依赖、白名单、非root、64MiB、归档哈希和删除tag后同ID重载全部通过。
- 正式归档：`D:/brace-msi-first-principles-release/BRACE-MSI-0.10.2rc1-FINAL/harness.tar`；SHA-256 `1F4B4C70061E2228977A98984ED3DF8D6E4C691E23D35DB95517A83173C5C6C0`。本阶段未上传、未调用私有PyTRiO/SwanLab、未消耗官方次数。
- 独立终审随后撤回`0.10.2rc1`上传资格：发现平台测量未作为最终部署权威、请求参数与实际recipe声明混淆、独立组不足降级不安全、跨任务工作区缺少dataset隔离以及验收父哈希/只读范围缺口。历史产物保留，不回写。
- `FORMAL-AUDIT-FIX-001`完成：`0.10.3rc1`关闭上述缺口。完整回归`465 passed in 143.76s`；官方SDK Linux离线15项通过、2项在线条件测试按缺少凭据跳过；A/B/C各10轮共30个宿主调用、15行独立预测；最大checkpoint 132,180字节。精确镜像linux/amd64、UID10001、81,188,446字节，`pip check`、白名单、4核8GB只读断网及删tag后同ID重载通过。
- 新归档：`D:/brace-msi-first-principles-release/BRACE-MSI-0.10.3rc1-FINAL/harness.tar`，81,206,272字节，SHA-256 `D08535F0B4A410A9EFF6CBB191505F32B767462B3E42CDC6093E8ABC385CA86A`。本轮未上传、未调用私有PyTRiO/SwanLab、未消耗官方次数。
- 2026-11-18平台报告O-PLATFORM-017证明`0.10.3rc1`完成30次宿主调用并结算21,969 Token，但30轮全部提案非法、候选数0；输出7,680恰为30×256，定位到参赛代码自设上限与严格JSON解析边界，而非模型未调用。
- `FORMAL-AGENT-OUTPUT-001`按TDD完成：删除所有参赛者`max_tokens`，由官方SDK使用完整宿主授权预算；Agent只提供train/retain意图，执行参数继续由确定性portfolio控制；唯一JSON容错且歧义失败关闭。专项10项、正式运行与SDK专项37项、完整回归`469 passed in 155.18s`。
- `0.10.4rc2`在4核8GB、只读、断网容器完成A/B/C各10轮、30调用、候选1/0/3及15行预测；`pip check`、19文件白名单和删tag重载同ID通过。归档81,206,784字节，SHA-256 `97948BD45502CFFE6082184DB06799A8E0FD8BE6BB008C048C7CE9DE47B335EA`。本地修复没有自动消耗新平台次数。

## 2026-11-19：每轮真实训练与Qwen双阶段部署决策

- O-PLATFORM-018证明0.10.4rc2的正式模型调用与提案解析已恢复，但30/30有效提案均主动retain，导致候选数0；据此登记D-085每轮真实训练要求。
- 用户进一步确认平台过程中不返回指标且不参与部署决策，登记D-086替代D-085的平台裁决部分：Qwen每轮先选择训练recipe，Harness真实训练并本地计算主辅指标，Qwen第二次调用决定deploy/retain/rollback，SafetyGate仅执行硬约束。
- TDD新增训练提案与部署判断两种严格契约、平台指标缺失/冲突不影响Qwen选择、每轮两call ID、真实候选、回滚和本地指标/资源/历史上下文覆盖。
- A1因错误平台决策权判无效，A2因模拟器仍返回平台指标中止；A3在平台指标30/30为空时通过；A4显式覆盖严格退化rollback。
- 精确0.10.6rc1容器A/B/C共30轮、60次宿主调用、30个真实候选，Qwen本地部署4次、回滚26次，硬安全失败0。镜像81,190,622字节，归档81,208,320字节且重载同ID，SHA-256 `F7518609974EAB3C156C07F6D0AA7CBFE6CF9253B43C5D20B3DC71B4C91D89CB`。
- 历史暴露公开validation仅作描述性诊断：A Macro-F1 `0.714030→0.725695`，B RMSE `681.159833→656.351785`，C RMSE `52.868573→52.350178`。不作为独立泛化或官方成绩。本阶段未调用远程PyTRiO/SwanLab、未上传、未消耗新平台次数。

## 2026-11-20：选择可靠性与泛化重构启动

- 重新核验两份官方试运行报告及一份临时分析附件的SHA-256，登记O-PLATFORM-019；未把“镜像14v16”猜成任一本地RC。
- 多Agent只读审计确认：Gas第5轮、Bearing第2轮、Engine第4轮存在确定性数值关系与deploy冲突；当前rollback等同retain；正式路径缺少唯一MetricContract、作用域指纹和合法历史best；墙钟/CPU差缺少阶段归因。
- 用户批准分阶段设计后追加D-087：Qwen在确定性指标事实和合法证据可行集合内决策；正式镜像继续只使用宿主`rnd.model()`，PyTRiO训练和SwanLab只在镜像外研究/记录层。
- 新增设计与实施计划：`superpowers/specs/2026-11-20-selection-generalization-runtime-design.md`、`superpowers/plans/2026-11-20-selection-generalization-runtime.md`；预注册`SELECTION-RELIABILITY-001-A1`，尚未运行训练、远程调用、SwanLab同步或官方试运行。
- 验证：`git diff --check`通过；下一步按TDD实现MetricContract与选择一致性。
- `SELECTION-RELIABILITY-001-A1`按TDD完成：5个初始红灯覆盖错误方向、未知指标回退、退化deploy和硬门后提交；随后补充scope双指纹、NaN整轮完成、历史过滤、v1迁移、requested/applied、显式NASA方向和计时边界。
- 运行核专项最终`50 passed in 1.43s`，完整回归`487 passed in 143.52s`；独立代码复审第一轮提出6个P1、第二轮提出1个P1，全部修复后复审无剩余P0/P1。代码提交`afa9038`。
- 本阶段没有训练、远程服务、SwanLab、Docker或平台次数；下一步是GENERALIZATION-MATRIX-001的零训练重放和预注册本地矩阵。
# 2026-11-20 GENERALIZATION-MATRIX-001-A1

- 完成四策略零训练重放及11项专项测试。
- O-PLATFORM-019三条确认退化反例3/3在严格门下保留父模型；四策略均未部署这些退化候选。
- 机器产物SHA-256：`CDD3D5C98BE12F899E85C207AAD9D3C714659ECF191AD51D66D6616B6516C170`。
- 本阶段训练、确认集读取、PyTRiO远程、SwanLab同步和官方试运行均为0。
- `GENERALIZATION-MATRIX-001-A2`完成12条十轮链，但四策略均因B最差阶段超过5%门而淘汰；A2技术执行完整不等于性能晋级。摘要SHA-256 `517AA24C2064A1231A13D06A27CDD7458E50262CE671BB52C070DDEB8C138223`。
- A3仅预注册一个身份无关修订：高尺度异质回归加入`current_e3_lr3`第二候选；不改数据、选择策略或阈值，不读取confirmation。
- A3取得正向数值但`experiment_id`错误，按无效证据保留；A4只修ID并精确复跑。
- A4 120/120轮真实训练技术完成，但独立复审发现有限探索在第10轮仍依赖不存在的延迟回滚，条件历史冠军未证明正式artifact恢复。摘要SHA-256 `AB1870F5710CF9499B13B17D4466ABF5FEA9946A4E8E31F28F14DAEE69FFFB31`保留，不再作为晋级证据。
- A5已预注册：只修末轮探索、输入路径失败关闭、最终checkpoint门和历史artifact恢复证据；不改数据、recipe、训练参数或选择阈值。
- A5数值复演完成，有限探索原始机器门为true；但独立复审的P0链接边界和P1最终checkpoint绑定阻止该结论晋级。A5摘要SHA-256 `9903249414FE93D6B4708A348D7E00CDF2DC73F0E9F683BB4C52FED55070B252`保留。
- A6已预注册为只修链接/junction失败关闭与最终checkpoint全状态/预测绑定；其余数据和算法冻结。
- A6 120/120轮完成，12/12最终checkpoint状态指纹与预测绑定通过；symlink/junction三类对抗测试均先红后绿。`bounded_exploration`是唯一开发候选；摘要SHA-256 `BA850904FFE1A839CD839F87C0F6999A53751FE786E5BC12296A8E9F6B126F68`。
- 独立二次复审确认无剩余技术P0/P1；GENERALIZATION-MATRIX-001只以“开发策略筛选完成”收尾。D-088的方法冻结后独立替代流/任务留出已在TASKS中编码为正式RC前置。
- A6收口验证：专项`24 passed`，完整回归`511 passed in 145.39s`；开发候选之外不作隐藏泛化或正式RC主张。

# 2026-11-20 PERFORMANCE-METHOD-PILOT-001

- A1在相邻未见阶段完成原生schema单因素筛选：分类`balanced_current_e3`优于近期回放基线；B非对称Huber改善最差阶段/NASA但平均RMSE略逊；C的新稳健方法均未超过既有25%权重插值。
- A2将C偏差校正单独拆出后仍同时损害RMSE、NASA和最差阶段，方法淘汰。
- A3把全部新回归方法接入十轮矩阵后触发B 5.95%灾难退化，并暴露recipe冷却后跨方法族回退缺口；按无效/负结果保留。
- A4只接入`balanced_current_e3 + native_recent_e3`复合分类候选：120/120轮、12/12最终checkpoint绑定、0个5%灾难任务；A平均收益`0.312990→0.360481`、最差相对收益`-0.5470%→0`，B/C checkpoint与A6完全相同。因为训练范围与损失同时变化，不作类平衡单因素因果主张。机器摘要SHA-256 `4237A9F445E2E42456D3FD434B579D246046274A0B956278E36D764E110637BD`。
- confirmation/public validation、远程PyTRiO、SwanLab同步和官方试运行使用均为0；下一步按冻结轨迹验收基础Qwen，最终仍需D-088独立替代流。
- 收口验证：方法/矩阵专项`26 passed`，完整回归`518 passed in 142.91s`；独立复审无技术P0，P1证据措辞已修正。

# 2026-11-20 PYTRIO-ADVISOR-OPT-001

- A1使用12个冻结、脱敏的正式deployment场景验收基础Qwen：schema/非零Token 12/12，但2个硬风险场景仍请求deploy；精确标签6/12中另有4例为无害`rollback`替代`retain`。
- 用户明确授权训练与预算后，以D-090替代D-043的停止调参边界，仅允许一次镜像外有界SFT。24条训练与12条全新留出按风险类型和历史组合隔离，语料哈希在远程调用前冻结。
- A2完成18/18步，最终loss `0.001425805`；新留出基础policy 66.67%/安全91.67%，Sampler四项100%，重新加载复评仍四项100%。
- SwanLab只同步20条聚合记录；敏感扫描零命中，公开链接为`https://swanlab.cn/@nanmo-max/BRACE-MSI/runs/k4jvqkuj`。首次同步仅在Windows GBK打印链接阶段失败，随后同run ID UTF-8确认137条底层记录上传完成。
- 未修改或构建正式镜像，未上传比赛平台，未消耗官方试运行。下一任务为D-088独立泛化验收。

# 2026-11-20 FINAL-GENERALIZATION-VALIDATION-001

- 在提交`5f03a17`冻结配置与代码后，首次且唯一一次提取`Bearing1_5/Bearing2_5/Bearing3_5`；原持久缓存目录打开前无密封缓存，三分区样本ID交叉0。
- 开发流10/10轮、16候选、10部署、2延迟回滚；平均RMSE有向收益`+188.967744`，但第10轮最差相对收益`-99.61%`，违反预注册最差阶段门。
- 密封预测总体为正：RMSE `243.718016→220.922262`（改善9.35%），MAE `184.328347→168.207564`（改善8.75%）；2/3轴承改善、最差轴承仅退化2.04%。
- CPU `17.97s`、墙钟`12.49s`、结束时RSS约108.3MiB、checkpoint 42,320字节；A1峰值RSS和右截尾恢复未验证。checkpoint重载预测一致；公开确认读取、PyTRiO、SwanLab、官方试运行均0。
- 独立审查发现A1延迟收益使用当前Update+Gate后又以同一Gate评价候选，不满足Gate单一验证用途；未来执行器改为Update-only，但密封不重开。依据D-088/D-091判`DONE_INVALID_PROTOCOL_AND_NEGATIVE_NO_FORMAL_PROMOTION`。摘要SHA-256 `22D4143B53074CE6A3CF8C913937157EE42403400FA462E0C2AE66ACEF38AA05`。

# 2026-11-20 RELEASE-COMPATIBILITY-AUDIT-001

- 精确复核`0.10.6rc1`归档SHA-256为`F7518609974EAB3C156C07F6D0AA7CBFE6CF9253B43C5D20B3DC71B4C91D89CB`，从`docker save`归档重载后镜像ID为`sha256:52333ab1...ca7504`；镜像19个运行文件与源码提交`c653e0e`逐文件SHA-256一致。
- 4核8GB、断网、只读、非root复演A/B/C各10轮；总计60个宿主调用ID、30个真实候选和15行独立预测，父链/状态链有效；机器摘要SHA-256 `307581D27589AD17A90BEF69A1283D86B51AEF553238D5F34AEB08400CDF2CD8`。
- 公开validation只作描述性复算：A Macro-F1 `0.714030→0.725695`，B RMSE `681.159833→656.351785`，C RMSE `52.868573→52.350178`；这些不是独立泛化或官方成绩。
- 负向测试证明冻结镜像会接受错误deploy：C候选RMSE `55.629944`劣于父模型`52.868573`仍被选中。当前源码已修但没有新正式归档，D-091亦阻止研究组合晋级；结论为`DONE_AUDIT_FAIL_RELEASE`。
- 新鲜验证：正式运行专项`62 passed`；官方SDK离线`15 passed, 2 skipped`；当前源码完整回归`533 passed in 157.64s`。没有上传、官方试运行、远程PyTRiO/SwanLab写入或密封数据重开。

# 2026-11-20 COMPETITION-CORE-DESIGN-001

- 重新从官方规则、SDK 1.0.2、O-PLATFORM-019和赛题考察点区分正式试运行、正式评测与本地模拟；不重复已经通过的SDK/容器取证。
- 用户逐项确认：每轮必须真实训练；隐藏评测可出现A/B/C之外但同格式的新任务；官方直接调用镜像；历史数据可用；不增加非官方限制；测试镜像与正式镜像分离；PyTRiO训练Qwen Agent进入正式方案。
- 形成唯一Competition Core书面规格：七单元运行链、双阶段Qwen、父checkpoint兼容recipe、同作用域历史选择、镜像外PyTRiO/SwanLab和双镜像供应链。
- 本阶段未修改产品代码、未训练模型、未调用PyTRiO/SwanLab、未构建镜像、未上传平台或消耗试运行。

# 2026-11-20 COMPETITION-CORE-PLAN-001

- 用户批准书面规格并要求实行后，按`writing-plans`将唯一架构拆为12个顺序任务。
- 计划从冻结平台边界测试开始，依次实现任务画像、历史、注册recipe、Qwen提案、同作用域选择、正式轮编排、双镜像、本地模拟、性能实验、PyTRiO/SwanLab及最终发布验收。
- 每项任务均包含精确接口、红灯测试、验证命令和Git提交边界；计划未增加非官方Token、候选、epoch或提升阈值。
- 本阶段未修改产品代码、未训练模型、未调用远程服务、未构建镜像或使用官方试运行。

# 2026-11-20 COMPETITION-CORE Task 1

- 新增5项Competition Core平台边界特征测试，分别覆盖分类/回归单轮真实续训与预测，以及空模型收据、父checkpoint哈希不匹配、候选checkpoint不可加载三类负向边界。
- 专项命令：`D:\anaconda3\python.exe -m pytest tests/competition_core/test_platform_boundary.py tests/competition_core/test_current_round_characterization.py -q`，结果`5 passed in 0.21s`。
- 全量命令：`D:\anaconda3\python.exe -m pytest -q`，结果`538 passed in 163.22s`。
- 本任务只冻结已验证平台边界，未修改产品代码，未训练模型、调用远程服务、构建镜像或消耗官方试运行。

# 2026-11-21 COMPETITION-CORE Task 2

- 新增不受Gas/Bearing/Engine或其他`dataset_key`名称影响的不可变`TaskProfile`；任务类型、主指标、方向、特征/类别数、标签分布、数据质量、分组/时间提示和合同指纹均来自任务合同、父checkpoint与聚合数据。
- 按TDD先观测`ModuleNotFoundError: brace_formal.profile`红灯，再实现最小画像接口。
- 专项命令：`D:\anaconda3\python.exe -m pytest tests/competition_core/test_task_profile.py tests/formal_runtime/test_metric_contract.py tests/formal_dev/test_official_metrics.py -q`，结果`17 passed in 3.62s`。
- 全量命令：`D:\anaconda3\python.exe -m pytest -q`，结果`544 passed in 158.45s`。
- 未启动训练、PyTRiO/SwanLab、镜像或官方试运行。

# 2026-11-21 COMPETITION-CORE Task 3

- 新增`DataBatch.select/concat`、压缩`HistoryStore`与只经官方API恢复的`HistoryArtifactRef`；没有引入参赛者自定样本数上限。
- 容量压力测试证明：当全部原始行不能装入官方状态限额时，保留全部轮次审计摘要和能完整装入的最新合法批次，不截断批次。
- 专项命令：`D:\anaconda3\python.exe -m pytest tests/competition_core/test_history_store.py tests/formal_runtime/test_agent_workspace.py tests/formal_runtime/test_model_core.py -q`，结果`23 passed in 0.72s`。
- 全量命令：`D:\anaconda3\python.exe -m pytest -q`，结果`552 passed in 154.30s`。
- 未读取原始数据或运行模型训练，未调用PyTRiO/SwanLab、构建镜像或消耗官方试运行。

# 2026-11-21 COMPETITION-CORE Task 4

- `FormalModel.fit`在保持无选项原生路径的同时，增加样本权重、加权交叉熵、加权MSE、Huber与非对称回归梯度，延续Adam状态、确定性打乱和梯度裁剪。
- 新`RecipeRegistry`只暴露与`TaskProfile`兼容的父checkpoint续训能力；支持类别加权/平衡采样、三类回归损失、当前/历史回放、epoch/学习率覆盖与父候选平均；不包含训练前`retain`。
- 专项命令：`D:\anaconda3\python.exe -m pytest tests/competition_core/test_recipe_registry.py tests/formal_runtime/test_model_core.py tests/formal_runtime/test_portfolio.py tests/formal_dev/test_official_model.py -q`，结果`23 passed in 1.02s`。
- 全量命令：`D:\anaconda3\python.exe -m pytest -q`，结果`562 passed in 154.50s`。
- 本任务运行的仅是小型自动化单元训练测试，未使用官方数据、PyTRiO/SwanLab、镜像或官方试运行。

# 2026-11-21 COMPETITION-CORE Task 5

- 新`request_experiment_proposal`调用官方宿主模型时不自设Token上限，并要求返回可由`RecipeRegistry.resolve`执行的recipe、参数、历史策略、假设与理由。
- 模型返回含糊、recipe不可执行或服务异常时，使用对当前任务合法的`native_current`真实训练fallback；已有调用ID保留，异常记入`parse_error`。
- 部署阶段可请求父、候选或历史的合法产物ID，而不再只输出含糊`deploy/retain/rollback`。
- 专项命令：`D:\anaconda3\python.exe -m pytest tests/competition_core/test_experiment_agent.py tests/formal_runtime/test_agent_workspace.py tests/formal_runtime/test_release_host.py -q`，结果`21 passed in 0.21s`。
- 全量命令：`D:\anaconda3\python.exe -m pytest -q`，结果`570 passed in 154.29s`。
- 未调用真实远程模型、PyTRiO/SwanLab、镜像或官方试运行。

# 2026-11-21 COMPETITION-CORE Task 6

- 新增不可变`ArtifactEvaluation`和`SelectionResult`，以父模型当前验证指纹作为唯一可比较作用域；不同指纹、非有限主指标和硬失败产物均从选择集合排除。
- 选择顺序为任务合同主指标方向、合同声明的辅助指标、所有并列产物共同具备的实测资源；没有新增固定提升比例或自造官方综合分。
- Qwen请求只作为可审计建议：O-PLATFORM-019 Gas/Bearing/Engine退化反例与旧RC `RMSE 52.868573→55.629944`均不能错误部署；合法恢复且在当前作用域重评的历史产物可被选择。
- 专项命令：`D:\anaconda3\python.exe -m pytest tests/competition_core/test_artifact_selection.py tests/formal_runtime/test_metric_contract.py -q`，结果`21 passed in 0.20s`。
- 全量命令：`D:\anaconda3\python.exe -m pytest -q`，结果`583 passed in 154.34s`。
- 本任务未训练模型、未调用PyTRiO/SwanLab、未构建镜像、未使用官方试运行次数。
