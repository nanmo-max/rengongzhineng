# FINAL-SPRINT-003 工程证据增量

## 轮次—SwanLab关联

未重跑训练。`formal_observation.py`读取既有0.11.0rc1精确镜像验收的A/B/C各10轮摘要及逐轮ledger，验证连续轮次后生成30条脱敏聚合记录。来源`acceptance.json` SHA-256为`39999D0BE238CE128C3C1035B79127CDD87D72007880CD2B3249D24DEB03632F`；公开spool SHA-256为`2CF31EADB55D3FFD33D9F6CD0FC1CCA7C7EB639FCD3185F0EC3630BBD2047731`。

SwanLab 0.10.5已真实生成30步离线运行，位置`D:/brace-msi-final-sprint/FINAL-SPRINT-003/swanlab-offline/`。未自动同步云端；同步前仍需核对正式项目与公开字段。该记录是本地精确镜像验收观测，不是官方成绩，也不冒充真实27B调用。

## 镜像与源码一致性

- 冻结镜像：`brace-msi:0.11.0rc1`，归档SHA-256 `B7BA01BCC8A60502896082B58578B56C60C539A5460BB373285FF0ABE4503E30`，已有4核8GB验收。
- 当前增量源码：提交`31200accdd2982ce25f9ff8df746afd01a91e226`后包含诊断证据链；冻结镜像不包含该提交，禁止将二者表述为同一发布物。
- 当前Docker客户端存在但服务端不可用，因此本轮没有伪造新镜像digest或4核4GB容器通过证据。服务恢复后必须以当前候选提交重新构建、4核4GB验收并生成新`docker save`归档。

## 当前提交约束

用户当前确认正式决策模型为远程`Qwen/Qwen3.8-27B`、工业模型运行环境按4核4GB。该配置尚无当前候选真实平台收据；作品材料只能写“目标配置/待平台验证”，不能写成已通过。
