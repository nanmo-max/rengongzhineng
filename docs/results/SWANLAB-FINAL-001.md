# SWANLAB-FINAL-001 最终工程记录

## 结论

在不改变RC3、A3 Sampler或三任务冻结参数的前提下，A/B/C各完成一次10轮、3候选的最终工程记录运行。三项均通过原Harness机器复算，随后将严格脱敏的聚合指标以SwanLab 0.10.4同步到公开项目。该运行只用于提交记录，未用于继续选型、调参或形成隐藏评测结论。

## 执行边界

- 执行提交：`b64bf7f21f3a7bccd4ab79edbb1c210326afc480`；
- 本地根：`D:/brace-msi-final-record/SWANLAB-FINAL-001/`；
- 配置：`configs/formal_agent_competitive.json`；
- 工业模型：官方A/B/C训练包随附NumPy训练器与真实检查点；
- 决策模型：冻结A3持久化Sampler，完整路径只从Git外收据读取；
- 官方试运行：0；隐藏数据：0；参数搜索：0；
- SwanLab只含聚合指标和资源，不含原始样本、标签、预测、检查点哈希、输出目录、密钥或Sampler路径。

## 训练与验证结果

| 任务 | 轮次/候选 | 接受 | 最终主指标 | 次指标 | CPU秒 | 峰值RSS | 输入/输出Token |
|---|---:|---:|---:|---:|---:|---:|---:|
| A Gas | 10 / 3 | 1 | Macro-F1 0.725695424 | Accuracy 0.885852090 | 2.515625 | 52,617,216 | 6,845 / 776 |
| B Bearing | 10 / 3 | 1 | RMSE 637.180224 | MAE 540.456251 | 4.406250 | 69,120,000 | 6,711 / 762 |
| C Engine | 10 / 3 | 2 | RMSE 51.635999 | MAE 37.758009 | 32.734375 | 259,006,464 | 6,780 / 757 |

三项`validate-only`均返回`valid=true`。总输入/输出Token为20,336/2,295，总候选CPU时间39.65625秒。

## SwanLab公开证据

- 项目：<https://swanlab.cn/@nanmo-max/brace-msi-final>
- Gas：<https://swanlab.cn/@nanmo-max/brace-msi-final/runs/bkj7sd0m/chart>
- Bearing：<https://swanlab.cn/@nanmo-max/brace-msi-final/runs/adjunafu/chart>
- Engine：<https://swanlab.cn/@nanmo-max/brace-msi-final/runs/fk7k38tq/chart>

SwanLab API复核结果为项目`visibility=PUBLIC`、实验总数3、三项`state=FINISHED`、每项`record_count=10`，并能读取`brace/primary_metric`、`brace/secondary_metric`、`brace/candidate_count`、`brace/accepted`、`brace/cpu_seconds`、`brace/peak_rss_bytes`等曲线。

## 失败与恢复记录

Gas第一次同步已经创建远端实验，但Windows GBK终端无法输出SwanLab CLI的emoji，导致在确认上传前抛出`UnicodeEncodeError`，远端状态暂为`RUNNING`。根因定位为Rich旧式Windows控制台编码，而非训练或网络失败。随后设置`PYTHONUTF8=1`和`PYTHONIOENCODING=utf-8`，并用同一远端run ID幂等恢复；最终上传145条记录且状态为`FINISHED`。Bearing和Engine直接在UTF-8环境一次成功。失败日志保留在本地运行根，未删除或创建重复Gas实验。

## 证据边界

公开验证集已经历史暴露，因此本次结果不是独立测试或官方成绩。SwanLab通用记录已经完成；比赛专用项目命名、额外必填字段或无公网评测同步责任仍须服从后续平台正式规范。

