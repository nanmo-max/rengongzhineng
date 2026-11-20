# GENERALIZATION-MATRIX-001-A1 零训练策略重放

## 结论

四种预注册策略已通过纯决策重放的最低安全门。O-PLATFORM-019中三条已确认退化候选均未被部署；这只证明策略边界正确，不证明模型性能提高。

## 输入与边界

- 输入：Gas第5轮、Bearing第2轮、Engine第4轮已确认父/候选主指标关系。
- 原始证据通过SOURCE_REGISTRY中的O-PLATFORM-019及其SHA-256引用。
- 未读取公开validation或confirmation，未运行训练、PyTRiO远程、SwanLab同步、Docker或官方试运行。

## 验证结果

- 专项测试：`11 passed in 0.14s`。
- 严格父子门：3/3退化反例保留父模型。
- 有限探索：只有容忍度、剩余预算和可回滚条件同时满足才允许。
- 条件历史冠军：只有在当前作用域重新评价且产物可恢复时可选。
- recipe反馈：性能退化只有限冷却；硬失败永久隔离。
- 非有限候选失败关闭；策略接口不接收数据集名称。

## 机器产物

- `D:/brace-msi-generalization/GENERALIZATION-MATRIX-001-A1/decision-replay.json`
- SHA-256：`CDD3D5C98BE12F899E85C207AAD9D3C714659ECF191AD51D66D6616B6516C170`

## 下一步

在既有合法十轮流上预注册A2训练矩阵；只使用每轮Update/Gate和下一轮到达证据，不读取公开确认集作选择。
