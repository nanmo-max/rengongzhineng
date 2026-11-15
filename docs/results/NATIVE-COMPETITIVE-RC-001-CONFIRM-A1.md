# NATIVE-COMPETITIVE-RC-001 冻结确认与发布组合

## CONFIRM-A1

- 冻结提交：`55a9621`；冻结配置SHA-256：`5D9147818562FA5A4F17E8269B1A1E68E71D3A4EBFE7669BB486B6AAE1DF5E8A`。
- 这是本轮唯一一次公开validation读取；结果不再用于修改竞争参数或重开确认。
- A：Macro-F1 `0.725695`，Accuracy `0.885852`；优于`0.6.0rc1`的`0.714030`。
- B：RMSE `681.159833`，MAE `563.105841`；竞争策略retain回官方父模型，低于`0.6.0rc1`的`660.076488`，因此竞争策略单独不可发布。
- C：RMSE `51.949287`，MAE `38.091484`；优于`0.6.0rc1`的`52.868573`。
- 摘要：`D:/brace-msi-native-competitive/NATIVE-COMPETITIVE-RC-001-CONFIRM-A1/summary.json`；SHA-256 `73371324359ABA3B59BA60BBF661E9861DF7BB14A366FB8D57C682AFE32609B9`。

## 发布组合

- A/C使用冻结竞争策略；B精确复用已验证`0.6.0rc1` protocol策略。该组合复用既有不可变证据，不依据CONFIRM-A1搜索新B参数，也不再次读取validation。
- `protocol_profiles=["B"]`路由与纯protocol模式的候选数、接受数、最终指标和checkpoint哈希差分一致。
- COMPOSE-A1因候选上限误设为3而标记`INVALID_CONFIGURATION`。
- COMPOSE-A2修正上限为10：A/B/C候选数`3/10/3`，接受数`1/1/1`，父链均有效；训练内部A/C复现DEV-A5，B复现旧protocol训练行为。
- COMPOSE-A2摘要SHA-256：`CBF2FF87DF6DB1252E54F827FD2A6C131F4D2A7236C0AEB09B28E0E859D115C5`；发布组合配置SHA-256：`66BAE85D4DA6A50BA66EB64C89E431A049BC30F4D18170C3388F77DDA6C20314`。
- 公开性能证据的组合值为A `0.725695`、B `660.076488`、C `51.949287`；其中B来自冻结`0.6.0rc1`既有确认，而非本轮第二次validation运行。
