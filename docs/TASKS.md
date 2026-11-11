# 可执行任务清单

状态定义见 [WORKFLOW.md](WORKFLOW.md)。任务状态只在本文件维护。

## 当前任务图

```text
DOC-001
  -> CORE-001 -> SDK-001 -> CORE-002 -> CORE-003
  -> DATA-001 -> BASE-001/BASE-002/BASE-003
  -> CORE-004 -> CORE-005 -> LOG-001
  -> INT-001 -> PKG-001 -> REPRO-001 -> MAT-001
  -> EXP-001 -> EXP-002 -> PAPER-001

CORE-001
  -> LOCAL-DATA-001 -> LOCAL-CORE-001 -> LOCAL-LOOP-001
  -> LOCAL-SMOKE-001 -> LOCAL-EXP-001

LOCAL-EXP-001
  -> SYS-001 -> SYS-002 -> SYS-003 -> SYS-004 -> SYS-005

SYS-005
  -> RR-001 -> RR-002 -> RR-003 -> RR-004 -> RR-005
```

## P0：11月13日前最低版本

### DOC-001 文档与恢复体系

- 状态：`DONE`
- 依赖：无
- 产物：`AGENTS.md`、`docs/`正式文档、初始文件审计
- 完成标准：要求文档全部存在；内部链接有效；证据分类明确；新会话恢复步骤可执行；未修改原始数据
- 停止条件：发现原始文件缺失或需要覆盖历史文件
- 证据：`docs/`文档树；必需文件、相对链接、证据ID和原始数据哈希一致性检查通过；Git基线见首次提交

### CORE-001 模拟SDK事件协议与防泄漏状态机

- 状态：`DONE`
- 依赖：DOC-001
- 优先级：P0
- 完成标准：支持两种候选协议；同一评分样本不能先用标签训练；批次只能按适配器允许的事件推进；单元测试覆盖非法顺序
- 停止条件：需要猜测正式SDK字段或调用真实服务
- 备注：只构建模拟接口，不训练模型
- 实施计划：`docs/plans/CORE-001.md`
- 证据：`src/brace_msi/protocol/__init__.py`、`tests/protocol/test_state_machine.py`；`D:\anaconda3\python.exe -m pytest -q --tb=short`于2026-11-06通过，结果为`13 passed`

### SDK-001 正式平台与SDK核验

- 状态：`BLOCKED`
- 依赖：CORE-001、官方平台开放
- 优先级：P0
- 完成标准：登记SDK版本、事件顺序、数据模式、输出格式、标签规则、模型白名单、计费、迭代定义和SwanLab机制；更新全部H项
- 停止条件：只有转写或二手消息，没有正式文档/可运行SDK
- 当前阻塞：截至2026-11-06，仓库内没有正式SDK、平台文档或可运行平台入口；不能仅依据宣讲转写解除

### LOCAL-DATA-001 代理数据审计与冻结切分

- 状态：`DONE`
- 依赖：CORE-001、L-AUTH-001
- 优先级：P0，本地独立路径
- 完成标准：Gas与C-MAPSS结构、哈希、任务类型、标签构造、组/时间字段和冻结切分有代码与审计证据；训练/开发/密封样本互斥；原始数据只读
- 停止条件：压缩包哈希变化、数据损坏、标签含义无法从本地资料确认
- 实施计划：`docs/plans/LOCAL-PROXY-PIPELINE.md` Task 1
- 证据：`src/brace_msi/data/`、`scripts/audit_proxy_data.py`、`tests/data/`、`docs/source_notes/PROXY_DATA_AUDIT.md`；完整测试`23 passed`

### LOCAL-CORE-001 本地模型、预算、监测与SafetyGate

- 状态：`DONE`
- 依赖：LOCAL-DATA-001
- 优先级：P0，本地独立路径
- 完成标准：通用分类/回归模型能力、增量/重拟合、漂移与性能证据、训练前预算、候选评估、部署/拒绝均有自动测试
- 停止条件：需要未来批次信息或重依赖不符合CPU路线
- 实施计划：`docs/plans/LOCAL-PROXY-PIPELINE.md` Task 2
- 证据：`src/brace_msi/modeling.py`、`evidence.py`、`budget.py`、`safety.py`、`resources.py`及`tests/core/`；完整测试`34 passed`

### LOCAL-LOOP-001 本地策略与无人值守闭环

- 状态：`DONE`
- 依赖：LOCAL-CORE-001
- 优先级：P0，本地独立路径
- 完成标准：静态、性能触发和BRACE策略使用同一数据可见性运行；动作由证据选择；日志可审计且不含原始特征
- 停止条件：无法公平共享初始模型、切分或预算
- 实施计划：`docs/plans/LOCAL-PROXY-PIPELINE.md` Task 3
- 证据：`src/brace_msi/policies.py`、`runner.py`、`audit.py`及`tests/loop/`；完整测试`42 passed`

### LOCAL-SMOKE-001 代理数据低成本Smoke Test

- 状态：`DONE`
- 依赖：LOCAL-LOOP-001
- 优先级：P0，本地独立路径
- 完成标准：Gas与FD001均完成三策略小样本运行；至少出现一次增量和一次重拟合候选；资源、门控、失败和脱敏日志齐全
- 停止条件：任一数据防泄漏检查失败或运行超过预注册Smoke预算
- 实施计划：`docs/plans/LOCAL-PROXY-PIPELINE.md` Task 4
- 证据：执行提交`64ccce2`；`configs/local_smoke.json`、`docs/results/LOCAL-SMOKE-001.md`及本地忽略产物；六个运行完成，动作计数增量10/重拟合3，机器验收通过

### LOCAL-EXP-001 完整代理基线与迭代比较

- 状态：`DONE`
- 依赖：LOCAL-SMOKE-001
- 优先级：P0，本地独立路径
- 完成标准：两任务完成静态、性能触发和BRACE配对比较；全局至少三次真实候选训练/评估；分类与回归阶段指标及CPU资源有可复核产物
- 停止条件：Smoke未通过、密封段已被用于调参或策略被简单基线全面支配后仍试图增加模块
- 实施计划：`docs/plans/LOCAL-PROXY-PIPELINE.md` Task 5
- 证据：执行提交`f9647dd`；DEV与唯一密封运行均6/6完成并机器验收通过；`docs/results/LOCAL-EXP-001.md`；全局增量9/重拟合5

### CORE-002 TaskBootstrap

- 状态：`BLOCKED`
- 依赖：SDK-001
- 优先级：P0
- 完成标准：官方初始模型、合法初训数据、官方弃权/默认路径均有明确处理；不兼容任务拒绝跨任务复用
- 停止条件：SDK未定义新任务首批初始化方式

### SYS-001 平台无关TaskBootstrap、CPU模型池与注册表

- 状态：`DONE`
- 依赖：LOCAL-EXP-001、L-AUTH-002
- 优先级：P0，本地正式候选路径
- 完成标准：任务描述与兼容性检查、未知同领域任务合法初始化、四类CPU模型能力适配、候选配置、原子注册与回滚均有自动测试；持久化预测一致
- 停止条件：实现需要猜测官方SDK字段或打开已消费密封段
- 实施计划：`docs/plans/FORMAL-CANDIDATE-SYSTEM.md` Task 1
- 证据：`src/brace_msi/bootstrap.py`、`modeling.py`、`registry.py`和`tests/system/test_bootstrap_models_registry.py`；四类模型在分类/回归上完成构造与预测，非法增量调用、任务不兼容、持久化与回滚均有测试；完整测试`58 passed`

### SYS-002 证据路由、预算动作选择与有限HPO

- 状态：`DONE`
- 依赖：SYS-001
- 优先级：P0，本地正式候选路径
- 完成标准：数据质量/性能/漂移/历史/预算证据统一路由；回放、族切换、有限HPO和自动停止均受训练前预算约束；失败候选不污染稳定模型
- 停止条件：简单确定性策略被替换为无法审计或运行时动态代码
- 实施计划：`docs/plans/FORMAL-CANDIDATE-SYSTEM.md` Task 2
- 证据：`src/brace_msi/decision.py`、`search.py`、扩展的`budget.py`/`policies.py`及`tests/system/test_decision_search.py`；数据质量阻断、证据升级、预算余量、有限搜索、耐心停止、回放上限和稳定模型隔离均通过测试；完整测试`64 passed`

### SYS-003 无人值守Harness、恢复与记录接口

- 状态：`DONE`
- 依赖：SYS-002
- 优先级：P0，本地正式候选路径
- 完成标准：两种模拟协议、检查点恢复、CLI、公开记录队列和私有审计组成可无人值守运行的统一Harness；恢复不重复已提交训练
- 停止条件：需要把未确认的SwanLab同步方式写成正式事实
- 实施计划：`docs/plans/FORMAL-CANDIDATE-SYSTEM.md` Task 3
- 证据：`src/brace_msi/harness.py`、`checkpoint.py`、`recording.py`、`cli.py`、`simulation.py`和`tests/system/test_unified_harness.py`；两种协议、可替换适配器、三次真实候选、故障拒绝、批次级恢复、私有审计、公开聚合队列和非交互CLI均通过测试；完整测试`71 passed`

### SYS-004 Docker、入口与静态HTML报告

- 状态：`DONE`
- 依赖：SYS-003
- 优先级：P0，本地正式候选路径
- 完成标准：Dockerfile、一键入口、锁定依赖、合规清单、接入说明和离线HTML报告齐全；构建上下文小于2GB且不含数据/权重/密钥
- 停止条件：本机没有Docker时仅阻塞实际镜像构建，不阻塞文件与静态验收
- 实施计划：`docs/plans/FORMAL-CANDIDATE-SYSTEM.md` Task 4
- 证据：`Dockerfile`、`.dockerignore`、`requirements.lock`、`run.ps1`/`run.sh`、`src/brace_msi/reporting.py`、`packaging.py`、`docs/RUNBOOK.md`、`SDK_INTEGRATION.md`和`OPEN_SOURCE_COMPLIANCE.md`；静态上下文审计73文件/251,854字节、无禁入文件；PowerShell一键Smoke完成3次候选；完整测试`74 passed`。本机无Docker/Podman，实际镜像构建另列阻塞任务

### SYS-005 三任务模拟正式评测与资源验收

- 状态：`DONE`
- 依赖：SYS-004
- 优先级：P0，本地正式候选路径
- 完成标准：Gas开发流、FD001开发流、明确标注的合成轴承流完成初始化、至少三次候选、部署/拒绝、故障回滚、恢复、4核8GB监测、日志和HTML证据包；不打开旧密封段
- 停止条件：任何泄漏检查失败、资源超限或需要重用已消费密封段选型
- 实施计划：`docs/plans/FORMAL-CANDIDATE-SYSTEM.md` Task 5
- 证据：A1`ce3e907`因真实候选误计标记INVALID并保留；A2执行`7ef3829`，三任务真实候选4/4/3，动作覆盖增量7、回放1、有限HPO3；4核亲和性、RSS、幂等日志、注册表和HTML经独立验收；完整测试`80 passed`；详见`docs/results/LOCAL-FORMAL-SIM-001.md`

### PKG-RUNTIME-001 实际Docker镜像构建与4核8GB容器验收

- 状态：`BLOCKED`
- 依赖：SYS-004、本机或可用环境提供Docker/Podman运行时
- 优先级：P0，外部环境阻塞
- 完成标准：实际构建镜像并测量小于2GB；`--network=none --cpus=4 --memory=8g`完整运行；镜像内无数据、权重和密钥
- 停止条件：没有容器运行时，不得用静态上下文大小冒充镜像大小
- 当前阻塞：2026-11-07检查PATH及常见Docker/Podman安装位置均未找到运行时

### RR-001 实际容器运行时验收

- 状态：`BLOCKED`
- 依赖：SYS-005、L-AUTH-003
- 优先级：P0，Release Readiness
- 完成标准：实际Linux镜像小于2GB；4核8GB、断网容器完成非密封Smoke；镜像内无数据、权重和密钥
- 停止条件：本机无Docker/Podman/可用Linux容器运行时，或安装需要重启/管理员交互
- 执行清单：`docs/plans/RELEASE-READINESS.md`任务1
- 阻塞证据：2026-11-07检查确认Docker/Podman不存在；WSL、VirtualMachinePlatform、Hyper-V和Containers Windows功能均为`Disabled`，启用需系统级变更与重启。本轮未修改宿主机。

### RR-002 干净环境依赖与完整回归

- 状态：`DONE`
- 依赖：RR-001完成或有可核验的BLOCKED结论
- 优先级：P0，Release Readiness
- 完成标准：隔离环境只按锁文件安装；`pip check`、完整测试、CLI Smoke、编译及包审计均有日志
- 停止条件：锁文件无法在支持的Python/Linux范围解析，或需要修改算法才能安装
- 执行清单：`docs/plans/RELEASE-READINESS.md`任务2
- 证据：全新`tmp/release-venv-final`仅安装`requirements.lock`、`requirements-dev.lock`及本项目；`pip check`无冲突，`81 passed`，两协议CLI Smoke分别完成3/4候选；CPython 3.12 manylinux二进制轮子解析成功。发布审计发现并修复`psutil==5.9.0`无cp312 Linux轮子问题。

### RR-003 SwanLab离线适配与同步准备

- 状态：`DONE`
- 依赖：RR-002
- 优先级：P0，Release Readiness
- 完成标准：可选依赖、离线记录、公开字段白名单、显式同步命令和失败降级均有自动测试与文档
- 停止条件：需要猜测比赛专用字段、自动上传私有数据或使用未知凭据
- 执行清单：`docs/plans/RELEASE-READINESS.md`任务3
- 证据：`swanlab_adapter.py`、CLI离线导出/同步命令、4项自动测试及`SWANLAB_INTEGRATION.md`；真实SwanLab 0.10.4离线生成`run-*`目录并记录8条聚合事件，`pip check`无冲突。未执行云端同步。

### RR-004 正式SDK接入适配器准备

- 状态：`DONE`
- 依赖：RR-002
- 优先级：P0，Release Readiness
- 完成标准：可配置字段映射、动态官方模块边界、协议契约测试和接入检查表齐全；核心Harness不依赖官方包
- 停止条件：任何实现需要编造官方字段、标签权限、模型服务或错误语义
- 执行清单：`docs/plans/RELEASE-READINESS.md`任务4
- 证据：`official_sdk.py`、`sdk-contract-check`、5项契约测试、清单模板及扩展后的`SDK_INTEGRATION.md`；缺模块、非法清单、接口不完整均fail-closed。实际字段和数据出入站仍归`SDK-001`阻塞。

### RR-005 Release Candidate最终审计

- 状态：`DONE`
- 依赖：RR-003、RR-004及RR-001可核验结论
- 优先级：P0，Release Readiness
- 完成标准：生成版本清单、哈希、交付审计、完整测试证据和阻塞表；Git提交且不合并main
- 停止条件：存在未登记的P0失败、证据与文档冲突或工作树不干净
- 执行清单：`docs/plans/RELEASE-READINESS.md`任务5
- 证据：`BRACE-MSI-0.1.0rc1`、确定性源码打包器及发布树测试；全新环境安装的wheel实际CLI完成两协议Smoke和SwanLab 0.10.4离线导出，完整回归`95 passed`、`pip check`通过、上下文124文件/487,662字节且无禁入文件。实际镜像与容器任务保持RR-001 BLOCKED。

### CORE-003 模型能力声明与CPU模型适配

- 状态：`BLOCKED`
- 依赖：CORE-002
- 优先级：P0
- 完成标准：模型能力可机读；批量模型不调用`partial_fit`；保存/加载一致；资源上限可配置
- 停止条件：正式任务类型或指标仍未知

### DATA-001 官方三任务数据审计

- 状态：`BLOCKED`
- 依赖：官方数据发布
- 优先级：P0
- 完成标准：数据字典、任务类型、标签、组/时间字段、指标、批次协议、许可证和哈希登记；泄漏风险清单完成
- 停止条件：数据来源或许可证不明
- 已完成：2026-11-10完成三套本地原件只读清点、重复数据逐文件哈希比对和XJTU-SY分卷完整性/结构审计；证据见`docs/source_notes/OFFICIAL_DATA_INTAKE_2026-11-10.md`。
- 已更新：O-PLATFORM-001已确认三任务目标、单位和主指标，轴承目标不再未知。
- 新证据：O-PLATFORM-005已提供三任务训练器、真实初始权重、公开train/validation、任务说明与指标；本任务开始验证清单、schema、父检查点和续训行为。
- 已完成子项：训练包原目录只读复核、关键SHA-256、数据schema/分组/ID隔离、NPZ结构、公开基线复算及随包测试已审计；证据见`docs/source_notes/OFFICIAL_TRAINING_PACKAGE_AUDIT_2026-11-11.md`。
- 当前阻塞：训练包本地审计子项已完成；正式SDK/批次协议、隐藏测试、完整评分公式、平台资源计量和许可证仍缺失 `[H-006]`。这些外部缺口阻塞完整DATA-001验收和正式平台成绩，但不阻塞官方训练包本地续训。

### OFFICIAL-PKG-001 官方训练包适配与十轮续训

- 状态：`DONE`
- 依赖：训练包审计、书面规格与实施计划均已批准；忽略不影响本地续训的外部缺口
- 优先级：P0，官方训练包本地开发路径
- 完成标准：原包只读哈希清单；A/B/C真实检查点Smoke；单次固定低成本续训对照（内部ID`performance_triggered`）与BRACE各10个候选适应决策轮；BRACE每任务至少3次真实候选；1+1/连续2 epoch继承证明、拒绝候选父链隔离、验证使用账本、训练前后资源估算、门控、恢复、静态报告和机器验收齐全。
- 当前证据：Task 1只读清单审计器已实现；真实A/B/C拓扑、关键哈希、行数及ID/设备组隔离通过，篡改检查点在训练前被拒绝。证据：`tests/official_package/test_manifest.py`、`src/brace_msi/official_package.py`。
- 当前证据：Task 2隔离训练适配器已实现；原版A训练器的连续2 epoch与1+1恢复训练产生逐数组相同检查点和相同预测，父/子epoch、step、权重、Adam、标准化及输入哈希均核验；超时保留失败收据，包代码审计后变化会在子进程前拒绝。证据：`tests/official_package/test_trainer.py`、`src/brace_msi/official_trainer.py`。
- 当前证据：Task 3十轮监督器已实现；十轮明确为候选适应决策，BRACE最低候选、严格改善门控、拒绝候选父链隔离、验证使用账本、原子状态和五轮后恢复均通过测试。证据：`tests/official_package/test_rounds.py`、`src/brace_msi/official_rounds.py`。
- 当前证据：Task 4三任务套件与CLI已实现；训练前/Smoke后资源估算、3个Smoke、6个策略作业、全局验证账本、B包上游测试缺口、静态Markdown/HTML和机器验收通过自动测试。证据：`tests/official_package/test_suite.py`、`src/brace_msi/official_package_suite.py`、`scripts/run_official_package_dev.py`。
- 完成证据：执行提交`34098bf`；运行根`D:/brace-msi-official-package/OFFICIAL-PACKAGE-DEV-001/`；9/9作业、15候选、六策略各10轮、BRACE每任务3候选，`validation.json`为`valid=true`。结果与负证据见`docs/results/OFFICIAL-PACKAGE-DEV-001.md`。
- 停止条件：见`docs/superpowers/specs/2026-11-11-official-package-integration-design.md`。
- 边界：`official_package=true`、`official_scoring_ready=false`；不运行SwanLab、不提交平台、不使用隐藏测试、不消耗平台试跑次数、不修改RC标签。

### FORMAL-DEV-001 最新规则对齐无人值守训练

- 状态：`DONE`
- 依赖：O-PLATFORM-001至004、L-AUTH-007、已有三数据加载器与统一Harness
- 优先级：P0，正式平台前开发路径
- 完成标准：三任务使用参数量匹配的可替换MLP本地初始检查点；各自构造10个合法开发批次；静态、性能触发和BRACE共享初始检查点并串行运行；官方指标、最差阶段、恢复速度、稳定性和资源分别记录；前三个实验人工健康检查通过后后台独立继续；自动生成汇总分析和下一轮冻结建议；全部产物可断点恢复。
- 停止条件：原始哈希变化、训练/开发/密封身份交叉、非有限指标、超过4核8GB本地观测边界、输出目录已有冲突证据，或需要把本地重建权重冒充平台权重。
- 边界：`official_rules_aligned=true`、`official_checkpoint=false`；不消耗平台试运行，不提交平台，不运行SwanLab，不打开既有密封段，不改变RC标签。
- 实施计划：`docs/plans/OFFICIAL-RULES-ALIGNED-TRAINING.md`
- 证据：实现提交`512d477`、报告提交`9c7bdba`；`D:/brace-msi-official-dev/OFFICIAL-RULES-ALIGNED-DEV-001/validation.json`为`valid=true`；9/9实验各10轮完成，前三实验健康检查有效，后台PID 6084正常退出；汇总见`docs/results/OFFICIAL-RULES-ALIGNED-DEV-001.md`；完整回归116项通过。
- 后续：按D-027停止复用同一开发流调参；平台训练包与初始权重到达后另建正式实验ID，`DATA-001`继续`BLOCKED`。

### XJTU-LOCAL-001 新增轴承数据本地串行训练

- 状态：`DONE`
- 依赖：DATA-001已完成的XJTU-SY只读结构审计、L-AUTH-006
- 优先级：P0，本地独立路径
- 完成标准：冻结按轴承分组且互斥的初训/开发/密封切分；完成可恢复的独立CSV特征缓存；静态强CPU基线、性能触发和BRACE串行运行；前三个实验轮次经日志/有限指标/资源检查；后台进程可脱离会话继续并保存状态；最终保留本地审计与失败证据。
- 停止条件：原始分卷哈希变化、分组交叉、特征使用未来寿命/未来批次、非有限数据无法清理、派生空间不足，或运行目录包含已有证据且可能被覆盖。
- 边界：`local_development_only=true`；不运行SwanLab，不改变RC标签，不复训Gas/FD001，不把自定RUL协议称为官方任务或成绩。
- 实施计划：`docs/plans/XJTU-LOCAL-SERIAL.md`
- 证据：实现提交`2460577`、公平切分与验收修正`2e29ae7`；`D:/brace-msi-xjtu/XJTU-LOCAL-DEV-001/`；A1因静态/策略初训可见性不一致标记INVALID并保留，A2`experiments-a2/`完成5/5轮、3次真实候选且`validation-experiments-a2.json`为`valid=true`；聚合结果见`docs/results/XJTU-LOCAL-DEV-001.md`；完整回归101项通过。

### BASE-001/002/003 三任务静态基线

- 状态：`BLOCKED`
- 依赖：DATA-001、CORE-003
- 优先级：P0
- 完成标准：气体、轴承、RUL分别完成官方静态基线和强CPU基线；配置、资源和本地审计齐全。SwanLab正式记录仅在最终工程模型重训阶段生成 `[D-023]`
- 停止条件：任一任务的数据切分或指标无法确认

### CORE-004 候选实验与预算账本

- 状态：`BLOCKED`
- 依赖：CORE-003、SDK-001
- 优先级：P0
- 完成标准：真实候选事件、训练前预算、超时降级、至少三次迭代计数均可配置和审计
- 停止条件：官方迭代计数仍存在会导致资格风险的歧义

### CORE-005 三层SafetyGate与回滚

- 状态：`BLOCKED`
- 依赖：CORE-004、BASE任务
- 优先级：P0
- 完成标准：硬约束、统计评估、部署决策分离；失败候选不污染稳定模型；原子回滚通过故障测试
- 停止条件：没有合法验证数据或检查点无法恢复

### LOG-001 SwanLab与私有审计

- 状态：`BLOCKED`
- 依赖：SDK-001、CORE-004
- 优先级：P0
- 完成标准：官方要求字段完整；公开/私有记录隔离；断网缓存与正式同步机制经官方确认
- 停止条件：同步方案可能泄露B包或不被官方认可
- 阶段边界：当前不执行。等待平台提供规范并冻结最终工程模型后，通过正式重新训练一次性生成所需记录 `[L-AUTH-005]` `[D-023]`。

### INT-001 端到端无人值守闭环

- 状态：`BLOCKED`
- 依赖：BASE任务、CORE-005、LOG-001
- 优先级：P0
- 完成标准：三任务从初始化到三次候选、部署/拒绝、回滚和报告均无需人工操作
- 停止条件：任一基础资格门槛失败

### PKG-001 受限Docker镜像

- 状态：`BLOCKED`
- 依赖：INT-001
- 优先级：P0
- 完成标准：Linux 4核8GB、无公网运行；镜像小于2GB；无模型权重、Embedding和密钥
- 停止条件：镜像或运行时违反正式限制

### REPRO-001 独立复现

- 状态：`BLOCKED`
- 依赖：PKG-001
- 优先级：P0
- 完成标准：队友在干净环境按文档一键运行；产物哈希和关键指标一致
- 停止条件：需要作者手工修复或隐含环境状态

### MAT-001 最低提交材料

- 状态：`BLOCKED`
- 依赖：REPRO-001
- 优先级：P0
- 完成标准：镜像、Harness/配置/依赖与复现说明、公开实验记录、设计论证和开源合规材料齐全
- 停止条件：模板或学校提交清单尚未核实

## P1：企业赛竞争力

### UNIFIED-POLICY-001 三任务统一策略优化

- 状态：`IN_PROGRESS`
- 依赖：OFFICIAL-PKG-001、FORMAL-DEV-001、XJTU-LOCAL-001、L-AUTH-008
- 优先级：P0，当前唯一执行任务
- 完成标准：实现身份盲、无量纲的共享策略核心；冻结三阶段manifest；完成三个任务级leave-one-task-out fold；公平比较静态、固定低成本、性能触发和BRACE；冻结一组共享配置；末期只测且明确历史暴露等级；生成资源、失败、停止条件和机器验收证据。
- 停止条件：样本/设备组泄漏、策略读取任务身份、末期数据提前访问、BRACE被简单策略在至少两个任务级留出fold上全面支配、资源超限，或需要使用官方测试反馈继续调参。
- 设计：`docs/superpowers/specs/2026-11-11-unified-policy-optimization-design.md`
- 实施计划：`docs/superpowers/plans/2026-11-11-unified-policy-optimization.md`
- 边界：不修改D-031冻结实验、RC标签、main或原始数据；Gas/FD001末期为历史暴露，XJTU末期首次打开前必须预注册；不运行SwanLab和平台SDK。
- 当前运行：`UNIFIED-POLICY-OPT-001-DEV-A1`，提交`e057589`；24组共享配置、81个串行作业，运行根`D:/brace-msi-unified/UNIFIED-POLICY-OPT-001-DEV-A1/`。2026-11-12交接快照74/81收据，后台Python PID 7416。

### LOCAL-BASE-STRONG 强静态CPU基线补充

- 状态：`BLOCKED`
- 依赖：新的未见官方数据或新的合法密封代理切分
- 完成标准：分类与回归分别预注册至少一个强静态CPU模型，并在未见密封段与同族静态、简单触发和BRACE公平比较
- 停止条件：只能复用已经查看的`LOCAL-EXP-001`密封段；此时仅可标记为事后探索，不能补写成确认性基线
- 当前阻塞：Gas批次8–10和FD001发动机81–100已在2026-11-06查看；正式数据尚未发布

### EXP-001 性能触发式强对照

- 状态：`BLOCKED`
- 依赖：INT-001
- 完成标准：同数据可见性、初始模型和资源下完成性能触发式低成本更新
- 停止条件：协议无法公平对齐

### EXP-002 BRACE-MSI关键比较与消融

- 状态：`BLOCKED`
- 依赖：EXP-001
- 完成标准：平均增益、最差阶段和总资源均有配对比较；完整策略不被简单策略全面支配
- 停止条件：简单策略全面支配BRACE；返回动作策略，不增加模块

## P2：证明价值后再做

### PAPER-001 主干论文复现与组合

- 状态：`DEFERRED`
- 依赖：EXP-002证明明确失败点
- 完成标准：只复现能解决失败点、许可证清楚、CPU可执行的关键结论
- 停止条件：无法优于简单基线或破坏镜像/时间预算
