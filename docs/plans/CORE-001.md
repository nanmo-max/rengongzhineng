# CORE-001 实施计划：模拟SDK事件协议

## 目标

在不猜测官方SDK字段的前提下，实现两种内部模拟协议及防泄漏状态机，为11月9日正式SDK适配提供稳定边界。

## 范围

- `predict_then_feedback`：预测请求 -> 提交预测 -> 标签反馈 -> 批次提交。
- `labeled_train_then_predict`：有标签训练批次 -> 不同样本的预测请求 -> 提交预测 -> 批次提交。
- 同一评分样本在预测提交前不得进入训练集合。
- 新批次必须等待上一批次提交完成。
- 任务存在未关闭批次时不得结束。
- 记录内部事件历史，供后续审计层消费。

不包含模型、训练、指标、漂移检测、官方SDK字段或网络调用。

## 接口

模块：`brace_msi.protocol`

- `ProtocolMode`
- `ProtocolViolation`
- `ProtocolPhase`
- `ProtocolSnapshot`
- `SimulatedSdkAdapter`
  - `open_task(task_id)`
  - `provide_training_batch(batch_id, sample_ids)`
  - `request_predictions(batch_id, sample_ids)`
  - `submit_predictions(batch_id, sample_ids)`
  - `provide_feedback(batch_id, sample_ids)`
  - `request_batch_commit(batch_id)`
  - `finish_task()`
  - `snapshot()`
  - `history`

所有ID仅为内部不透明字符串，不对应或推测官方字段。

## 测试与完成标准

1. 两种合法协议均能完成任务。
2. 预测提交前的反馈被拒绝。
3. 有标签训练样本与评分样本重叠时被拒绝。
4. 新批次必须等待上一批次提交完成。
5. 任务存在未提交批次时不得结束。
6. 事件历史可供后续审计。
