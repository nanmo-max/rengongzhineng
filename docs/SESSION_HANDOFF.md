# 新会话恢复与交接

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
