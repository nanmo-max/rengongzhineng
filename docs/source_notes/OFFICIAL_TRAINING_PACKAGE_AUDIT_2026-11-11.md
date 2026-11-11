# 官方训练包只读审计（2026-11-11）

## 范围与边界

- 来源：`C:/Users/Administrator/Desktop/人工智能创新大赛/训练包`
- 审计方式：只读目录清点、SHA-256、JSONL聚合解析、`numpy.load(..., allow_pickle=False)`、公开验证指标复算和随包单元测试。
- 原目录未写入：测试设置`PYTHONDONTWRITEBYTECODE=1`；复核仍为64个文件、60,328,967字节，未出现`__pycache__`或`.pyc`。
- 本审计不运行续训、不读取隐藏测试、不调用平台或SwanLab，也不把开发参考结果写成正式成绩。

## 关键文件指纹

| 包 | 文件 | SHA-256 |
|---|---|---|
| A | `checkpoint.npz` | `FD1E08B2AAD08B2E9754F9B2DFDC029481C0DA7ECDEDCA0ABB0EC6FCC818C757` |
| A | `public/train.jsonl` | `C724014FEB2C968D144E167F4997D2AD2125DF3825ABF4306C9C87C8F08DE6C0` |
| A | `public/validation.jsonl` | `6BE1370388BF67D017F7426A51E149A65BAF9BC1186F5F41F6731CE5006FFBEE` |
| B | `checkpoint.npz` | `C7D819FCEE9D25459C583B5FFDB35593D4A47B524ED152D0226BF81A283314B4` |
| B | `public/train.jsonl` | `71B2663FFFD3D7EF6DCA8A7B3FEB31C3FEB96C57F385335D03041A5FA431054A` |
| B | `public/validation.jsonl` | `23673A66BC22A166BF2F47B18F9C9D594F7E66A9AAD88DDBCCBCAEA2310D9EB3` |
| C | `checkpoint.npz` | `98EC6E30E38AEE56CA15B7D624A8F412226D46FE97B170667A567601C700BC4E` |
| C | `public/train.jsonl` | `FCFAEAF1E50A0CC01766DFBA5FD34C7369F1FE14BF583111837E847865FAC281` |
| C | `public/validation.jsonl` | `0CC747F9998C5D7EE1E4EAC6AEC0DB9F5ED4D2DE149A1B1CBE689CCE6B6AACA7` |

完整64文件指纹已在本轮终端输出中核验；正式运行清单将在`OFFICIAL-PKG-001`中原子写入独立运行目录，不把数据或权重复制进Git。

## 任务、数据和检查点

| 项目 | A Gas | B Bearing RUL | C Engine RUL |
|---|---|---|---|
| 类型/主指标 | 六分类 / Macro-F1↑ | 分钟回归 / RMSE↓ | 循环回归 / RMSE↓ |
| 输入 | 128数值特征 | 双通道各17特征，共34 | 3设置+21传感器，共24 |
| 网络 | 128→32 tanh→6 | 34→24 tanh→1 | 24→32 tanh→1 |
| 参数 | 4,326 | 865 | 833 |
| 训练/验证行 | 445 / 1,244 | 7,032 / 1,679 | 113,089 / 23,049 |
| 分组隔离 | Gas批次1 / 2 | 9 / 3根轴承 | 496 / 106台发动机 |
| ID交叉 | 0 | 0 | 0 |

三个NPZ均为`contest.cpu-mlp.v1`，只含固定schema的float64数组和Unicode JSON元数据；安全加载不允许pickle。检查点保存权重、Adam一阶/二阶矩、累计epoch/step、随机种子、特征路径、训练集均值/尺度和回归目标均值/尺度。

B任务正式纠正了训练包前的同参数量推断：865参数来自`34×24+24+24×1+1`，而不是`25×32+32+32×1+1`。D-026仅保留为训练包到达前的历史开发推断，正式接入采用D-028。

## 基线指标复算

使用随包`baselines.data.read_dataset`、`Model.load`和`baselines.train.metrics`重新计算：

| 任务 | `training.json.validation_after` | 实际检查点复算 | 是否一致 |
|---|---|---|---|
| A | Accuracy 0.8786173633440515；Macro-F1 0.7140297220788709 | 完全相同 | 是 |
| B | MAE 563.1058414514886；RMSE 681.1598326043113 | 浮点容差内相同 | 是 |
| C | MAE 38.89982982666355；RMSE 52.86857256611151 | 完全相同 | 是 |

训练包报告同时明确`purpose=development_reference`与`official_scoring_ready=false`，因此这些是公开验证基线，不是平台隐藏测试成绩。

## 随包测试

- A：9/9通过。
- C：9/9通过。
- B：训练、预测、全状态续训、父检查点绑定、数据隔离和schema防护等核心10项通过。
- B另有2项报错：`test_b_package_delivers_numeric_rul_code_and_weights_without_hidden_data`与`test_documented_edition_preserves_trained_code_weights_and_data`均导入未随包提供的`scripts.package_baselines`，得到`ModuleNotFoundError`。这是上游打包工具测试缺失依赖，不是模型续训失败；不得修改原包来制造全绿证据。

## 剩余外部缺口

正式SDK/批次事件、隐藏测试、35分完整数学公式、平台资源计量和许可证仍未提供。它们不阻塞官方训练包本地续训，但阻塞正式平台成绩与最终提交结论。
