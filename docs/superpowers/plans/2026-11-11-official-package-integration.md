# Official Training Package Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 接入三个只读官方训练包，使用真实初始检查点完成三任务Smoke、简单策略和BRACE各十轮可恢复续训、机器验收及结果交接。

**Architecture:** 仓库只保存训练包清单、适配器、策略和审计代码；数据与权重继续位于外部只读目录。候选训练由隔离子进程调用原版`baselines.train`，十轮监督器只基于既往公开验证结果选择有限动作，并通过父检查点哈希、指标和资源门控决定是否部署。

**Tech Stack:** Python 3.12、NumPy 1.26.4、标准库`subprocess/json/hashlib/pathlib`、psutil、pytest。

**Spec:** `docs/superpowers/specs/2026-11-11-official-package-integration-design.md`

## Global Constraints

- 原训练包`C:/Users/Administrator/Desktop/人工智能创新大赛/训练包`保持只读，不生成缓存、不修改文件、不复制数据或权重进Git/镜像。
- 运行根固定为`D:/brace-msi-official-package/OFFICIAL-PACKAGE-DEV-001/`，所有候选输出目录只创建一次且不得覆盖。
- 结果必须标记`official_package=true`、`official_scoring_ready=false`；不得称为隐藏测试、平台试跑或正式成绩。
- 不运行SwanLab、不访问外部API、不提交平台、不消耗平台试跑次数、不修改`brace-msi-v0.1.0-rc1`标签。
- A/B/C分别使用真实4326/865/833参数检查点；B必须是34输入、24隐藏单元，不得回退到历史25×32推断。
- 每个策略每任务10个决策轮；BRACE每任务至少3次实际启动并产出可验证检查点的候选。
- 公开验证只用于本地候选门控；验证样本不得进入训练、标准化或目标缩放拟合。
- 十轮统一称为“候选适应决策轮”，不得称为真实时间批次或真实漂移流评测。
- 每次公开验证读取均写入验证使用账本；每轮最多一个候选，完成后不得根据同一验证结果修改动作空间重跑。
- 完整队列启动前必须先生成保守CPU时间、磁盘和墙钟估算，Smoke后用实测修正并确认不超过本地预算。

## Review Focus

- 原包任何关键哈希变化必须在启动子进程前失败；Task 1加入篡改清单测试。
- 三个同名`baselines`包不能在同一解释器缓存串包；Task 2用独立子进程与包工作目录测试。
- 已拒候选不能成为下一轮父检查点；Task 3验证完整父SHA链。
- 父模型继承不能只相信报告字段；Task 2验证1+1恢复训练与连续2 epoch的权重、Adam、epoch、step和预测完全等价。
- 崩溃恢复不能重复已完成候选或覆盖目录；Task 3加入中断恢复哈希测试。
- B包两项缺失打包工具测试不能被误判为训练失败或伪造成全绿；Task 4在验收报告中固定记录该缺口。

---

### Task 1: 官方训练包清单与只读审计器

**Files:**
- Create: `src/brace_msi/official_package.py`
- Create: `tests/official_package/test_manifest.py`
- Create: `configs/official_package_dev.json`
- Modify: `docs/TASKS.md`

**Interfaces:**
- Produces: `PackageSpec`, `PackageAudit`, `audit_package_root(root: Path, config: Mapping[str, Any]) -> dict[str, PackageAudit]`
- Produces: `PackageAudit`中的包ID、任务、profile、输入维度、hidden、参数量、关键文件SHA、训练/验证行数、主指标和基线值。

- [ ] **Step 1: 写失败测试**

覆盖真实配置解析、三包必需文件、B的34×24拓扑、关键哈希、训练/验证ID和设备组隔离，以及复制fixture后篡改检查点必须失败。

- [ ] **Step 2: 运行红灯测试**

Run: `D:\anaconda3\python.exe -m pytest -q tests/official_package/test_manifest.py --tb=short`
Expected: FAIL，缺少`brace_msi.official_package`。

- [ ] **Step 3: 实现清单审计**

实现只读JSONL流式摘要、NPZ `allow_pickle=False`元数据验证和SHA核验；不导入或执行训练包代码。

- [ ] **Step 4: 验证绿灯与原包不变**

Run: `D:\anaconda3\python.exe -m pytest -q tests/official_package/test_manifest.py --tb=short`
Expected: PASS；训练包仍64文件且无`__pycache__`。

- [ ] **Step 5: 提交**

```powershell
git add src/brace_msi/official_package.py tests/official_package/test_manifest.py configs/official_package_dev.json docs/TASKS.md
git commit -m "feat: audit official training packages"
```

### Task 2: 隔离子进程候选训练适配器

**Files:**
- Create: `src/brace_msi/official_trainer.py`
- Create: `tests/official_package/test_trainer.py`

**Interfaces:**
- Consumes: Task 1 `PackageAudit`
- Produces: `CandidateConfig(epochs, learning_rate, batch_size)`
- Produces: `CandidateReceipt(stage_id, parent_sha256, checkpoint_sha256, metrics_before, metrics_after, wall_seconds, cpu_seconds, peak_rss_bytes, output_dir)`
- Produces: `OfficialTrainer.run_candidate(package, parent, output_dir, config, stage_id) -> CandidateReceipt`

- [ ] **Step 1: 写失败测试**

用最小临时官方包fixture验证：独立工作目录执行、父SHA绑定、输出报告/检查点实物哈希、不可覆盖、错误schema拒绝、超时/非零退出保留失败收据；从同一父模型连续2 epoch与1 epoch后从子检查点续1 epoch必须得到相同权重、Adam、epoch、step和预测。

- [ ] **Step 2: 运行红灯测试**

Run: `D:\anaconda3\python.exe -m pytest -q tests/official_package/test_trainer.py --tb=short`
Expected: FAIL，缺少训练适配器。

- [ ] **Step 3: 实现适配器**

使用参数数组调用包内`python -m baselines.train`；设置`PYTHONDONTWRITEBYTECODE=1`、`BASELINE_CPU_THREADS=1`，白名单epochs 1/2/3/5、学习率倍率0.25/0.5/1.0、批大小基线或2倍；验证候选checkpoint和`training.json`。检查子模型epoch/step增加且权重或Adam状态真实变化，不能只验证`parent_checkpoint_sha256`字段。

- [ ] **Step 4: 运行绿灯测试**

Run: `D:\anaconda3\python.exe -m pytest -q tests/official_package/test_trainer.py --tb=short`
Expected: PASS，fixture原目录无变化。

- [ ] **Step 5: 提交**

```powershell
git add src/brace_msi/official_trainer.py tests/official_package/test_trainer.py
git commit -m "feat: adapt official baseline trainer"
```

### Task 3: 十轮策略、门控和原子恢复

**Files:**
- Create: `src/brace_msi/official_rounds.py`
- Create: `tests/official_package/test_rounds.py`

**Interfaces:**
- Consumes: `OfficialTrainer.run_candidate(...)`与`CandidateReceipt`
- Produces: `RoundPolicy = Literal["performance_triggered", "brace"]`
- Produces: `run_policy(package, policy, runtime_dir, config, trainer) -> PolicyResult`
- Produces: `validate_policy_result(runtime_dir, expected_rounds=10, minimum_candidates=3) -> dict[str, Any]`

- [ ] **Step 1: 写失败测试**

使用确定性假训练器覆盖10轮候选适应决策、无收益noop、失败升级、预算拒绝、至少3候选、接受/拒绝父链、被拒SHA绝不成为下一轮父模型、原子状态、第五轮中断后恢复不重复、验证暴露账本及已存在冲突目录失败。

- [ ] **Step 2: 运行红灯测试**

Run: `D:\anaconda3\python.exe -m pytest -q tests/official_package/test_rounds.py --tb=short`
Expected: FAIL，缺少十轮监督器。

- [ ] **Step 3: 实现策略与恢复**

每轮先从已完成收据恢复历史，再选择一个有限动作或noop；候选通过硬约束且主指标严格改善才部署，相等保留稳定模型。每轮后原子写`state.json`和脱敏`audit.jsonl`，并写验证使用账本；报告明确这些不是时间批次或真实漂移流。

- [ ] **Step 4: 运行绿灯测试**

Run: `D:\anaconda3\python.exe -m pytest -q tests/official_package/test_rounds.py --tb=short`
Expected: PASS。

- [ ] **Step 5: 提交**

```powershell
git add src/brace_msi/official_rounds.py tests/official_package/test_rounds.py
git commit -m "feat: add resumable official package rounds"
```

### Task 4: 三任务套件、CLI、报告与机器验收

**Files:**
- Create: `src/brace_msi/official_package_suite.py`
- Create: `scripts/run_official_package_dev.py`
- Create: `tests/official_package/test_suite.py`
- Modify: `docs/EXPERIMENTS.md`

**Interfaces:**
- Consumes: Task 1审计器、Task 2训练器、Task 3监督器。
- Produces: `run_official_package_suite(package_root, runtime_root, config, max_jobs=None) -> SuiteState`
- Produces: `validate_official_package_suite(runtime_root) -> dict[str, Any]`

- [ ] **Step 1: 写失败测试**

覆盖训练前资源估算、三任务Smoke、静态基线、六个策略作业、断点续跑、公开指标方向、验证暴露统计、资源聚合、B上游测试缺口声明、候选适应轮次标签、HTML转义和`official_scoring_ready=false`。

- [ ] **Step 2: 运行红灯测试**

Run: `D:\anaconda3\python.exe -m pytest -q tests/official_package/test_suite.py --tb=short`
Expected: FAIL，缺少套件模块。

- [ ] **Step 3: 实现套件和入口**

队列固定为A/B/C Smoke，A/B/C简单策略，A/B/C BRACE；`--max-jobs 3`只做前三个Smoke，默认从状态恢复全部。启动前根据历史`training_seconds`、最大候选数、epochs和检查点体积生成`resource-estimate.json`，Smoke后写实测修正版。生成`source-manifest.json`、`validation-usage.jsonl`、`summary.json`、`report.md/html`和`validation.json`。

- [ ] **Step 4: 验证绿灯与全量回归**

Run: `D:\anaconda3\python.exe -m pytest -q --tb=short`
Expected: 全部PASS；`compileall`与`git diff --check`通过。

- [ ] **Step 5: 提交**

```powershell
git add src/brace_msi/official_package_suite.py scripts/run_official_package_dev.py tests/official_package/test_suite.py docs/EXPERIMENTS.md
git commit -m "feat: orchestrate official package development"
```

### Task 5: 真实Smoke、后台十轮续训与结果分析

**Files:**
- Modify: `docs/EXPERIMENTS.md`
- Modify: `docs/STATUS.md`
- Modify: `docs/TASKS.md`
- Create: `docs/results/OFFICIAL-PACKAGE-DEV-001.md`

**Interfaces:**
- Consumes: `scripts/run_official_package_dev.py`
- Produces: `D:/brace-msi-official-package/OFFICIAL-PACKAGE-DEV-001/`完整证据包。

- [ ] **Step 1: 预注册实验并提交**

登记代码提交、输入哈希、策略、预算、资源估算上限、公开验证暴露风险、成功/停止条件和结果边界；十轮定义为候选适应决策，不得先运行后补写。

- [ ] **Step 2: 从干净提交运行前三个Smoke**

Run: `D:\anaconda3\python.exe scripts\run_official_package_dev.py --config configs\official_package_dev.json --package-root "C:\Users\Administrator\Desktop\人工智能创新大赛\训练包" --runtime-root "D:\brace-msi-official-package\OFFICIAL-PACKAGE-DEV-001" --max-jobs 3`
Expected: A/B/C各1 epoch候选完成，父SHA正确、epoch/step及模型状态证明真实续训、指标有限、原包哈希不变；Smoke实测资源不超过预估停止上限。

- [ ] **Step 3: 启动隐藏后台完整队列**

以`Start-Process -WindowStyle Hidden`启动同一入口，不带`--max-jobs`，重定向stdout/stderr并记录PID。进程必须脱离聊天继续，状态原子落盘。

- [ ] **Step 4: 终态验收与失败分析**

进程结束后运行机器验收；比较静态、简单策略与BRACE的主指标、最差轮、候选/接受数、CPU/墙钟/RSS和训练样本。负结果原样保留，不根据同一公开验证流继续调参重跑。

- [ ] **Step 5: 更新SSOT并提交**

更新`STATUS/TASKS/EXPERIMENTS/RESEARCH_PROGRESS/RISK_REGISTER/SESSION_HANDOFF`和结果文档；保留外部缺口为BLOCKED，但本地目标标记完成。

### Task 6: 最终完成审计

**Files:**
- Modify only if verification exposes an evidence/documentation gap.

**Interfaces:**
- Consumes: 全部代码、测试、Git与运行证据。
- Produces: 逐要求完成矩阵和干净可恢复提交。

- [ ] **Step 1: 运行完整验证**

Run: `D:\anaconda3\python.exe -m pytest -q --tb=short`
Run: `D:\anaconda3\python.exe -m compileall -q src scripts`
Run: `git diff --check`
Expected: 全部成功。

- [ ] **Step 2: 验证运行证据**

检查三任务、每策略10轮、BRACE每任务至少3候选、父SHA链、错误日志、无SwanLab/平台调用、原包哈希、后台进程终态、报告和机器验收。

- [ ] **Step 3: 验证版本边界**

确认`task/core-001`工作树干净、所有新提交可追溯、`brace-msi-v0.1.0-rc1`仍指向`73c8212`且未合并`main`。
