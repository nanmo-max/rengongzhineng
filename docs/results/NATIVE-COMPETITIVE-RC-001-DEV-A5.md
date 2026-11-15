# NATIVE-COMPETITIVE-RC-001 DEV-A5

- 状态：训练内部候选冻结；尚未读取本轮公开validation。
- 输入：三套官方公开`train.jsonl`，原始包只读；每任务10轮决策、3个候选、7次retain。
- 参数：A第1/5/9轮均`1 epoch, 1x LR`；B为`1 epoch/1x`、`1 epoch/0.3x`、`5 epoch/3x`；C为`1 epoch/1x`、`1 epoch/0.3x`、`5 epoch/1x`；Replay上限100000。
- A：Macro-F1 `0.955754 -> 0.990778`，Accuracy `0.973034 -> 0.991011`，接受1/3。
- B：RMSE/MAE保持`233.357824/167.222270`，接受0/3；明显损害当前批主辅指标的候选被拒绝。
- C：RMSE `55.380385 -> 54.967102`，MAE `40.580370 -> 40.047855`，接受1/3。
- 资源：A/B/C累计CPU约`1.02/5.78/22.11`秒；峰值RSS约`85.1/160.0/247.7`MB；Token均0；官方试运行0次。
- 机器证据：`D:/brace-msi-native-competitive/NATIVE-COMPETITIVE-RC-001-DEV-A5/summary.json`，SHA-256 `A5981B9F8FABE02CC5475AF609CE61F095ADB35BB99126C4236975CF2C965FCF`。
- 冻结配置：`configs/platform_native_competitive_frozen.json`，SHA-256 `5D9147818562FA5A4F17E8269B1A1E68E71D3A4EBFE7669BB486B6AAE1DF5E8A`。
- 冻结规则：确认结果只决定发布或退回`0.6.0rc1`，不得用于修改参数、Gate或候选日程后重开validation。
