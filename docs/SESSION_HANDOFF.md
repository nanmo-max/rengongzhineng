# 新会话恢复与交接

## 2026-11-12统一策略搜索恢复入口

1. 检查后台命令是否仍含`run_unified_policy_optimization.py ... UNIFIED-POLICY-OPT-001-DEV-A1`；交接时Python PID为7416，但PID可能自然退出。
2. 读取`D:/brace-msi-unified/UNIFIED-POLICY-OPT-001-DEV-A1/state.json`并统计`jobs/**/receipt.json`。预期总作业81；交接快照为74。
3. 若进程已退出且81/81完成，执行：`D:/anaconda3/python.exe scripts/run_unified_policy_optimization.py --runtime-root D:/brace-msi-unified/UNIFIED-POLICY-OPT-001-DEV-A1 --validate-only`。
4. 若进程已退出但未完成，使用`EXPERIMENTS.md`登记的同一提交、配置和原命令恢复；执行manifest会拒绝源码、配置或评估协议漂移。
5. 严格验收通过前不得读取末期数据、冻结最终配置或更新为成功结论；不得使用官方十次测试机会。

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
- 本机无Docker/Podman，`PKG-RUNTIME-001`保持阻塞；不得把`audit_package.py`的上下文大小写成镜像大小。
- 完整系统模拟：`results/LOCAL-FORMAL-SIM-001.md`；有效A2机器产物位于`artifacts/formal_simulation/LOCAL-FORMAL-SIM-001/run-7ef3829/`；A1`run-ce3e907`为INVALID负证据。
- 模拟输出已通过`validate_simulation_output`：三任务、每任务至少3候选、动作覆盖、唯一批次提交、公开日志白名单和注册表加载均有效。
- 旧密封段锁继续生效；完整系统开发与模拟评测不得打开或据其结果选型。

## Release Candidate恢复边界

- 当前版本：`BRACE-MSI-0.1.0rc1`；入口见`docs/RELEASE_CANDIDATE.md`。
- RR-002至RR-005完成；全新安装包通过95项测试、两协议Smoke、SwanLab 0.10.4离线导出和静态交付审计。
- RR-001保持`BLOCKED`：本机无Docker/Podman且所需Windows虚拟化功能未启用，实际镜像和4核8GB容器没有通过证据。
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
