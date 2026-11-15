# Native PyTRiO 与 SwanLab 发布证据

## PyTRiO

- 模型：平台已校验的`Qwen/Qwen3.5-4B`基础模型；未使用LoRA/Sampler，不训练大模型。
- A1第1轮获得376/311 Token的合法响应，但包含Native未执行参数，建议被安全拒绝；后续调用RuntimeError并retain。
- 收紧提示词后，A2第1轮获得362/208 Token，`incremental_update`建议通过白名单并实际执行；后两轮RuntimeError并retain。
- A3以新进程继续已有3轮历史，服务仍两次RuntimeError且Token为0，正确retain。
- 非零Token服务响应共2次，实际执行建议1次；未达到计划的3次非零调用门，因此在线稳定性标记`BLOCKED_EXTERNAL`，不制造成功证据。运行时已证明Token零不计Agent证据、服务失败不训练。
- A1/A2/A3摘要SHA-256分别为`D05760D35998D314DB16125E2218528CAEBC3C17B16D61F83076EFCE6E3F64FF`、`742B34691B99CE35DF78794A89F549ED102ABEC35BF32613F31BD299AC13173D`、`DA70C131F519304CA63D2DECA4A9B450E2467B94F49CA8DBDA336CC02E8E7B64`。

## SwanLab

- 项目：`https://swanlab.cn/@nanmo-max/brace-msi-platform-native`
- A：`https://swanlab.cn/@nanmo-max/brace-msi-platform-native/runs/m4lwkv40`
- B：`https://swanlab.cn/@nanmo-max/brace-msi-platform-native/runs/8ady3o81`
- C：`https://swanlab.cn/@nanmo-max/brace-msi-platform-native/runs/392575n6`
- 三个运行均来自COMPOSE-A2，每项112条聚合记录；公开字段只含轮次、任务类型、主指标、候选/接受、CPU、墙钟、RSS、样本计数和状态。
- 同步前敏感词扫描无命中；不包含逐样本特征/标签、checkpoint哈希、Sampler路径、API Key或凭据。
- A首次同步在远端上传后因Windows GBK输出emoji异常退出；设置UTF-8后以同一run ID幂等恢复，三项最终均返回`Upload complete: 112 records`。
