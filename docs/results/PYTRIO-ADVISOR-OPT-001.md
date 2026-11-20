# PYTRIO-ADVISOR-OPT-001 结果

## 结论

基础`Qwen/Qwen3.5-4B`能稳定生成合法JSON，但会忽略部分硬风险。一次预注册、镜像外LoRA SFT已在全新留出上把schema、精确决策、硬风险安全和policy match全部提高到100%，持久化Sampler重新加载复评保持不变。

该结果证明镜像外Advisor的结构化部署判断可以改善，不证明工业模型性能提高，也不证明比赛提交页已经接受Sampler。正式镜像继续只调用官方宿主`rnd.model()`，不包含PyTRiO/SwanLab/Tokenizer/Sampler或密钥。

## A1基础模型

- 12个冻结正式deployment场景；12/12非零Token，schema 100%。
- 精确`retain/deploy`标签6/12；其中4例只是`rollback`替代`retain`，仍在可行集合内。
- 两个硬风险场景错误请求deploy，是实际安全关键缺陷。
- 输入/输出Token：4,337/323；采样延迟7.00秒。
- 结果：`D:/brace-msi-pytrio/PYTRIO-ADVISOR-OPT-001-A1/result.json`，SHA-256 `61D7FC88F568E24A44F6B23A3736464A1A75F5567397C413EA0E8E98906CE6CB`。

## A2有界SFT

- 语料：24训练、12全新留出；仅合成聚合指标，按风险类型与历史组合隔离。
- 训练：Qwen3.5-4B、rank 8、3 epoch、batch 4、`1e-4`、18步assistant-only SFT。
- 最终loss：`0.001425805`；墙钟82.41秒。
- 基础同留出：schema 100%、decision 66.67%、safety 91.67%、policy 66.67%。
- 新Sampler：四项100%；持久化路径重新创建客户端后四项仍100%。
- 结果：`D:/brace-msi-pytrio/PYTRIO-ADVISOR-OPT-001-A2/result.json`，SHA-256 `E192DB1FE667087F9D104971B18E30868AF5A62A5BEC38BB2595227A6703B5DF`。
- 重载：`D:/brace-msi-pytrio/PYTRIO-ADVISOR-OPT-001-A2-RELOAD/summary.json`，SHA-256 `179F6BEC8CA28AC163F36F79D994990E0BEA0956D4D0D7D95B8A28B849CCC09D`。

## SwanLab

- 公开运行：https://swanlab.cn/@nanmo-max/BRACE-MSI/runs/k4jvqkuj
- 20条聚合训练/评估记录；敏感扫描零匹配。
- spool SHA-256：`6FBB96626BE8E829C9BC0C469C25A43D3D23B28EEEB836923182D247D51BF694`。

## 采用边界

Sampler仅是镜像外候选。只有比赛提交页对该持久化权重校验通过，才可建议绑定；校验失败时仍使用已通过的基础模型和确定性Harness。没有消耗官方试运行次数。
