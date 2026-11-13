# 研究与工程进度

本文件按时间追加，不回写历史记录。当前状态仍以 [STATUS.md](STATUS.md) 为准。

## 2026-11-13：受控双闭环证据与规格锁定

- 对仓库外13张智训引擎宣讲截图逐文件计算SHA-256并登记为`B-RSI-002`；明确其证据等级低于正式规则/SDK，未据此编造字段或平台权限。
- D-051锁定十批即十次决策事务及0至2候选语义；D-052锁定四缓冲区物理隔离、ActionValueTable、影子配对收益、证据触发Qwen、受限插件和分层模型注册。
- 正式设计与执行计划分别保存于`docs/superpowers/specs/2026-11-13-controlled-dual-loop-design.md`和`docs/superpowers/plans/2026-11-13-controlled-dual-loop.md`。既有RC、历史正负实验和公开验证暴露均保持不变；尚未运行新训练或产生新性能结果。

## 2026-11-13：DUAL-DATA-001四缓冲区与数据能力边界

- 测试先行新增`online_data.py`：Anchor/Update/Gate/Replay为显式类型，数组只读；Gate在创建轮之后隔离完整一轮，达到`round+2`才能晋升Replay。
- 候选训练集合构造器只允许Update或Update+eligible Replay，拒绝Anchor/Gate和未到期Replay；训练、评估物化到两个独立目录，manifest只保存相对路径、批次、用途、样本摘要与文件哈希。
- 未来批次诱饵位于物化目录外，训练句柄既不记录源根也拒绝`..`越界解析。专项`4 passed`，完整回归`275 passed in 61.94s`；未运行训练或平台调用。

## 2026-11-13：DUAL-TXN-001单决策事务与影子配对收益

- 新增可恢复`DualLoopController`：提交历史必须是连续前缀，每批只建立一次计划；首候选产生结果前禁止第二候选，只有失败/收益不足、新证据、不同机制和预算同时成立才允许升级，单批硬上限2、全程默认8。
- pending状态、round commit和派生PolicyState均落盘；round commit带SHA-256并先原子写入，重启可从pending继续或从commit前缀恢复，重复批次和跳轮失败关闭。
- 影子收益在相同样本上计算分类Macro-F1/Accuracy或回归RMSE/MAE配对差并提供固定种子bootstrap区间；无影子时只接受显式历史基线并标记`historical_low`。专项`5 passed`，完整回归`280 passed in 63.27s`。

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

