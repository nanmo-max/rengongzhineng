# P5 实施路线图

## P5-R1 修订记录（2026-11-22）

- 将统计主线修订为特征内联合统计量、特征间依赖校准和运行级alpha-spending。
- 增加双参考池状态机、漂移恢复与新基准重建实现任务。
- 将Qwen验收从fact_id格式检查升级为Recipe能力匹配、完整结果账本和反事实验证。
- 按新增统计与恢复测试重新估算开发/验证成本。
- 本文件仍是待人工批准的实施计划，不授权编码、训练或远程调用。

## 1. 当前结论

最适合当前三个任务和未知同格式任务的MVP不是单一KS、PSI或逐特征ADWIN，而是：

> **稳健双窗口多统计量检测 + 特征内联合统计量 + 相关性感知的同步块置换`maxT`（BY保守降级）+ 效应量门 + 运行级alpha-spending + 双参考池恢复状态机 + 事实/假设分层诊断。**

该方案不假设特征和统计量相互独立；BH仅在依赖条件有依据时使用，无法构造合法同步置换时使用BY。方案预计能用NumPy在24/34/128维数值表格上运行并提供特征级定位，但性能和成本必须由合成验证确认。ADWIN仅作为性能误差流或全局漂移分数的可选增强，不是第一版硬依赖。

## 2. 实施阶段

本文件是待审批计划，不授权本轮编码、训练、远程调用、Docker构建或平台操作。

### Task 1：冻结接口和红灯测试

- 新增`DriftReport`、`DiagnosisReport`、`DriftState`和Recipe能力合同schema测试。
- 冻结事实ID、作用域哈希、Qwen evidence refs、alpha账本、参考epoch和轮收据字段。
- 建立未来窗口、无标签、小样本、p值分辨率不足、常量列、状态污染和损坏状态红灯测试。

完成标准：接口不依赖任务名称，不含逐样本输出，不改变现有checkpoint/SDK/selection。

预计：3—4工程小时。

### Task 2：实现稳健漂移监测器

- NumPy实现稳健位置/尺度、一维Wasserstein、KS距离、特征内联合统计量和加一经验p值。
- 实现同步分组/时间块置换`maxT`、BY降级、条件BH和效应量双门。
- 实现经验p值分辨率检查、alpha-spending和运行级误报账本。
- 覆盖24/34/128维单元与属性测试。

完成标准：八类合成场景可运行；无漂移FPR、检出、延迟和资源均可机器计算。

预计：7—10工程小时。

### Task 3：实现诊断归因

- 建立事实、假设、未知和禁止结论分层。
- 实现输入漂移/性能漂移四象限诊断。
- 输出experiment needs和Recipe能力匹配输入，但不直接调用训练或选择。

完成标准：受控场景类型识别、无标签边界和物理故障过度归因测试通过。

预计：4—5工程小时。

### Task 4：实现参考状态机与恢复

- 实现活动参考池与隔离候选参考池，禁止WARNING/CONFIRMED同轮或事后污染旧参考。
- 实现`CALIBRATING/STABLE/WARNING/CONFIRMED/RECOVERY/REBASE_PENDING/STABLE_NEW_BASELINE`原子状态转移。
- 保存参考epoch、来源窗口哈希、替换原因和恢复/重建证据。
- 验证短暂波动、重复短暂波动、反向恢复和持续新基准四类场景。

完成标准：活动参考污染率为0；恢复与重建状态和哈希可复算；损坏状态失败关闭。

预计：6—8工程小时。

### Task 5：接入Qwen与RoundReceipt

- 在TaskProfile后计算P5证据。
- 聚合投影进入第一次Qwen调用；第二次调用保留事实和真实实验结果。
- 要求`evidence_refs`并验证引用及Recipe能力合同；无效或不匹配均fallback。
- 记录引用事实、Recipe、参数、理由、预期效果、实际结果、部署/拒绝/回滚原因和相关性状态。
- 状态原子保存、恢复和hash一致。

完成标准：P5关闭时旧行为兼容；P5开启时每轮证据—实验—结果链可追溯；诊断屏蔽/无关替换反事实可执行。

预计：5—7工程小时。

### Task 6：完整合成验证与正式候选门

- 按`SYNTHETIC_VALIDATION_PLAN.md`冻结种子和场景。
- 比较KS、BH、BY、同步块置换`maxT`、均值/方差、完整方案及消融。
- 分别验证单窗口、连续确认和完整运行期误报，以及恢复/错误重建风险。
- 记录CPU、墙钟、RSS和状态大小。
- 运行专项和完整回归；只在通过后更新正式allowlist并构建新候选。

完成标准：所有MVP接受门满足；失败和负结果保留；未读禁止数据。

预计：4—7工程小时；4核CPU合成矩阵预计2—4小时，峰值内存目标低于1GiB。实际成本必须以运行收据替代估计。

## 3. 总时间与资源估计

| 项目 | 预计成本 | 说明 |
| --- | --- | --- |
| 开发 | 21—29小时 | 联合校准、状态机、能力合同与集成，不含用户审阅 |
| 测试与合成验证 | 8—12小时 | 含依赖结构、运行级误报、恢复、故障和集成测试 |
| 总工程时间 | 29—41小时 | 约4—6个工作日 |
| 本地计算 | 4核CPU约2—4小时 | 含同步置换合成矩阵，不运行工业模型训练 |
| 内存 | 目标小于1GiB | 主要是合成窗口和测试进程 |
| 远程Token/费用 | 0 | P5实现和合成验证不需要Qwen/PyTRiO |
| 官方试运行 | 0 | 新镜像完成全部本地门后另行授权 |

## 4. 决策门

### Gate A：统计有效

- 无漂移FPR达到预注册目标；
- 单窗口、连续确认和完整运行期误报均达到预注册目标；
- 经验p值分辨率足够，非法交换性能够正确降级；
- 中等持续漂移检出与延迟达标；
- 异常值不会单窗口触发确认；
- 特征定位准确。

失败：只修检测/校准，不进入Harness集成。

### Gate B：诊断诚实

- 事实与假设分层；
- 无标签不声称性能影响；
- 工况变化不声称设备故障；
- 未知项明确输出。
- Recipe能力合同与引用事实匹配；合法但不相关的fact_id不能过门。

失败：不得传给Qwen。

### Gate C：集成不回归

- 现有训练、评估、选择、回滚和预测测试保持通过；
- P5异常可降级；
- Qwen引用可验证；
- alpha账本、参考epoch、恢复与重建状态可恢复；
- 状态可恢复且确定。

失败：不更新formal allowlist，不构建候选镜像。

### Gate D：竞争价值

在后续独立任务中比较`Qwen-With-Diagnosis`与`Qwen-Without-Diagnosis`：

- 固定候选预算；
- 比较无效实验率、策略重复率、达到相同性能所需预算和最终性能；
- 若诊断没有改善实验效率或结果，只保留监测/审计能力，不宣传其优化收益。
- 增加诊断屏蔽和无关诊断替换反事实，排除Qwen只是复述fact_id或固定输出同一Recipe。

Gate D不属于P5最小实现的完成条件，但属于正式竞争力陈述的必要证据。

## 5. 六个最终问题

### 哪种漂移算法最适合当前三个任务？

稳健双窗口多统计量检测最适合MVP：中位数/MAD/IQR负责位置和尺度，标准化一维Wasserstein负责整体形状，KS作为辅助；同一特征内合并为联合统计量，满足块交换性时以同步置换`maxT`保留跨特征相关性，无法合法置换时用BY保守降级。BH只在依赖条件有依据时使用。效应量门、alpha-spending和状态机分别控制工程意义、运行期累计误报和恢复。

### 如何防止误报？

使用特征内联合统计、相关性感知`maxT`或BY降级、效应量门、连续窗口确认、alpha-spending、稳健统计和校准不足降级。实际验证分别报告单窗口、确认级和完整运行期误报，不能用连续确认代替累计误报控制。

### 如何区分数据漂移与真实设备故障？

系统只能确认数据/误差统计变化。设备故障属于需要外部维护、工况和物理传感证据验证的假设。输出将统计事实、可能解释和未知项分层，并禁止仅凭漂移报告生成“设备已故障”结论。

### 如何让Qwen真正使用诊断结果？

要求提案返回可验证`evidence_refs`，Harness还要核对Recipe能力合同，并把“引用事实—Recipe—理由—预期—实际结果—选择/拒绝”写入轮收据。后续通过有诊断、屏蔽诊断和无关诊断替换的同预算反事实验证策略是否真正响应相关证据；仅返回正确fact_id或把文本放入prompt均不算使用证据。

### 最小可验证版本需要修改哪些模块？

新增`drift.py`、`diagnosis.py`、`drift_state.py`及三组测试；扩展Recipe能力合同，最小修改`agent.py`、`round_core.py`和formal allowlist。`profile.py`只允许补聚合字段。SDK、model、metrics、selection、prediction、checkpoint与Docker入口不改。

### 预计开发、测试和资源成本？

预计29—41工程小时，约4—6个工作日；合成验证4核CPU约2—4小时、内存目标小于1GiB，无远程Token、无工业模型训练、无官方试运行。全部数值是规划估计，只有实测收据才能升级为事实。

## 6.1 P5-R1五项验收答复

1. **多重检验是否具有明确统计依据？** 有。特征内用同步置换校准联合统计量；特征间以满足交换性条件的联合`maxT`为主、BY为保守fallback、BH仅在依赖条件有依据时使用，并同时要求效应量门。经验p值使用加一校正并显式检查分辨率。
2. **长时间运行是否控制累计误报？** 设计上有。预注册`alpha_run`和可求和alpha-spending权重，记录每轮与累计消耗，并以完整独立无漂移流验证`run_level_false_alarm`。这仍需实现和实测，当前不能写成已通过。
3. **历史基准是否可能被漂移污染？** 任何实现都存在风险；修订设计以活动/候选双池、WARNING/CONFIRMED冻结、延迟纳入、参考epoch和不可回填规则降低并审计该风险。验收要求活动参考污染率为0。
4. **能否检测漂移恢复？** 设计覆盖短暂波动、重复短暂波动、缓慢漂移反向恢复和持续漂移后新基准建立，并定义`RECOVERY/REBASE_PENDING/STABLE_NEW_BASELINE`状态；是否能可靠检测仍需合成验证。
5. **能否证明Qwen使用了相关诊断证据？** 不能仅靠fact_id证明。必须同时具备能力合同匹配、完整证据到结果账本，以及有诊断/屏蔽/无关替换的反事实行为证据；未完成这些只能声称接口接入。

## 7. 停止条件

- 需要读取公开validation、XJTU密封或隐藏数据才能校准；
- 检测器在无漂移最终种子上无法控制误报；
- 诊断输出无法区分事实与物理原因推测；
- 集成破坏父checkpoint、现有选择或回滚；
- P5数据进入公开日志或Qwen上下文包含逐样本内容；
- 为达到指标而在验证种子结果后调整阈值再重跑。
- 经验p值分辨率不足却被解释为无漂移，或无法满足交换性却继续声称置换已校准。
- WARNING/CONFIRMED/未确认恢复窗口进入活动参考池。
- 仅因fact_id合法就认定Qwen使用诊断，未做Recipe能力匹配。

## 8. 参考资料

- Bifet, A., & Gavaldà, R. (2007). Learning from Time-Changing Data with Adaptive Windowing. SIAM SDM. <https://doi.org/10.1137/1.9781611972771.42>
- Gama, J., Žliobaitė, I., Bifet, A., Pechenizkiy, M., & Bouchachia, A. (2014). A Survey on Concept Drift Adaptation. *ACM Computing Surveys*, 46(4). <https://doi.org/10.1145/2523813>
- Benjamini, Y., & Hochberg, Y. (1995). Controlling the False Discovery Rate. *JRSS B*, 57(1), 289–300. <https://doi.org/10.1111/j.2517-6161.1995.tb02031.x>
- Benjamini, Y., & Yekutieli, D. (2001). The Control of the False Discovery Rate in Multiple Testing under Dependency. *The Annals of Statistics*, 29(4), 1165–1188. <https://doi.org/10.1214/aos/1013699998>
- Meinshausen, N., Maathuis, M. H., & Bühlmann, P. (2011). Asymptotic Optimality of the Westfall–Young Permutation Procedure for Multiple Testing under Dependence. *The Annals of Statistics*, 39(6), 3369–3391. <https://doi.org/10.1214/11-AOS946>
- Lan, K. K. G., & DeMets, D. L. (1983). Discrete Sequential Boundaries for Clinical Trials. *Biometrika*, 70(3), 659–663. <https://doi.org/10.1093/biomet/70.3.659>
- NIST/SEMATECH e-Handbook: Two-sample Kolmogorov–Smirnov test. <https://www.itl.nist.gov/div898/handbook/prc/section2/prc212.htm>
- SciPy reference: one-dimensional Wasserstein distance. <https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.wasserstein_distance.html>
- Kassis, T., Agarwal, V., He, Y., Patel, D., & Brueckner, A. M. (2026). Scientific Agent Skills: A Library of Procedural Knowledge for Research Agents. arXiv:2609.00065. <https://doi.org/10.48550/arXiv.2609.00065>

最后一项是本设计采用的证据分层与科学审计方法来源，不是官方赛题要求。
