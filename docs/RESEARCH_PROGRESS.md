# 研究与工程进度

本文件按时间追加，不回写历史记录。当前状态仍以 [STATUS.md](STATUS.md) 为准。

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
- 完整自动测试`93 passed`；编译检查通过；Docker上下文124文件、484,111字节、无禁入文件。
- 实际Docker镜像、4核8GB Linux容器、正式SDK/数据/评分及比赛SwanLab同步仍明确`BLOCKED`，未制造通过证据。

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
