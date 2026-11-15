# OFFICIAL-FLOW-SIM-001 结果

## 结论

任务自然流、预测封存、标签反馈、候选Gate、父链提交和一次性本地确认的完整生命周期已经实现并通过回归。旧`platform_simulation.py`按行均切十段的入口只保留历史RC复现，并在机器摘要中显式标记`legacy_equal_row_slice/not_official_flow`；新的执行入口为`scripts/run_official_flow_simulation.py`。

本任务证明本地协议与数据可见性可以按官方流程高保真复演，不证明数值与尚未开始的正式隐藏测试一致。A2性能为混合/负结果，不能替换冻结RC。

## 数据构造

- Gas：父模型已见Batch 1；Batch 2—9按自然批次和类内时间构成十轮，Batch 10作本地确认。父训练/流/确认的ID和特征哈希交叉均为0。
- Bearing：未见轴承按归一化寿命进度进入十轮，完整Bearing1_4作本地确认；同轮Update/Gate按完整轴承分开，未来snapshot不提前物化。
- Engine：未见`source_subset+unit`确定性分成十轮和确认；同一unit不跨轮、Update/Gate或确认边界。
- JSONL文件名和输入行顺序不改变Bearing/Engine归属；专项测试已覆盖。

## 运行语义

每轮先只物化无标签预测视图，稳定父模型预测并由`ScoreVault`封存哈希；封存后才物化当前反馈、Update和Gate。未来轮与确认集不提前物化。Prequential指标只写外部ScoreVault，不进入Runtime/Advisor；候选只使用Update、合法Replay和独立Gate。十轮完成后才物化并读取确认集一次，最终模型由真实部署链决定，不按确认指标回选轮次。

## 机器结果

运行根：

- 静态Smoke：`D:/brace-msi-official-flow/OFFICIAL-FLOW-SIM-001-SMOKE-A1/`
- 冻结策略A2：`D:/brace-msi-official-flow/OFFICIAL-FLOW-SIM-001-A2/`

| 任务 | 十轮样本 | 候选/采用 | 静态流均值 | A2流均值 | A2本地确认 | CPU | 峰值RSS |
|---|---:|---:|---:|---:|---:|---:|---:|
| A Gas | 9,865 | 3/0 | Macro-F1 0.406345 | 0.406345 | Accuracy 0.414722；Macro-F1 0.380649（3,600条） | 5.734 s | 202.6 MiB |
| B Bearing | 1,557 | 10/1 | RMSE 623.356135 | 612.887552 | MAE 437.807241；RMSE 495.437675（122条） | 1.797 s | 204.5 MiB |
| C Engine | 18,521 | 3/0 | RMSE 52.619608 | 52.619608 | MAE 36.699396；RMSE 48.691951；NASA 159,892,920.236953（4,528条） | 6.203 s | 493.9 MiB |

B在第2轮因同批Gate通过部署；第3—6轮相对静态较好，第7—10轮转差。A2本地确认相对静态Smoke的B RMSE 241.980799恶化到495.437675，说明同轴承阶段Gate不能保证对完整未见轴承泛化。该结果保留为负证据；确认集已由Smoke先暴露，A2报告明确标记为第2次历史暴露，只能描述，不能调参。

A/C均未部署候选，因此A2与静态流及本地确认完全一致。Gas从Batch 2首轮Macro-F1 0.714030下降到末轮0.185163，Batch 10确认0.380649，真实呈现跨自然批次漂移；不再出现旧报告重复同一validation的伪稳定数值。

## Agent与SwanLab边界

- A2使用冻结确定性策略，Token为0；没有把它包装成PyTRiO运行。新执行脚本支持`--advisor pytrio`并复用已经通过`PYTRIO-ONLINE-001`的受控Advisor、重试和确定性恢复，但本任务没有再次消耗额度。
- A2为A/B/C各生成一个SwanLab 0.10.5离线聚合目录，未同步公网；无逐样本特征、标签、密钥或checkpoint上传。

## 验证

- 新增专项：StreamPlan、自然分组、输入顺序不变、父/流/确认交叉、显式Update/Gate、预测先于反馈、未来不物化、ScoreVault单次确认、报告证据等级。
- 平台Runtime专项：50项通过。
- 最终完整回归：`399 passed in 153.34s`。
- `git diff --check`通过。

主要文件：

- `src/brace_msi/official_flow_simulation.py`
- `src/brace_msi/platform_runtime.py`
- `scripts/run_official_flow_simulation.py`
- `scripts/render_official_flow_report.py`
- `tests/platform_runtime/test_official_flow_streams.py`
- `tests/system/test_official_flow_report.py`

机器摘要SHA-256：

- `suite-summary.json`：`D548FD1E16AEEC47814F80DD7216D1BB999AF07C9F746BB557620EB23F696701`
- `official-flow-report.json`：`AE89EA9C8FC4A63284E7A3E04575EC8200BC1E557D987AF20BCCACD40A409344`
- `official-flow-report.html`：`79068974F23A63B1D9EA39B31B5ECBF77BFC4369DF2938A707A881722D4CA9EF`

## 证据边界

正式隐藏测试状态是`not_started_not_available`。以上数值不是官方隐藏成绩，也不能据此预测排名。A/B/C本地确认数据均已暴露，禁止再用于参数、Gate或轮次选择；新的性能策略只能使用合法训练内部证据，并等待正式隐藏评测最终确认。
