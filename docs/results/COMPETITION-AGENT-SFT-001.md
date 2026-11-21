# COMPETITION-AGENT-SFT-001 结果

## 结论

PyTRiO远程训练、持久化Sampler、重建采样客户端和同一冻结留出复评均已真实完成，但严格采用门未通过，因此该Sampler不进入正式提交配置。正式候选继续使用平台已校验的`Qwen/Qwen3.5-4B`基础模型；Competition Core的确定性recipe校验、同作用域指标比较和父模型回退保持有效。

本结果是镜像外Agent研究证据，不是工业模型成绩、官方试运行或隐藏评测。

## A1：不可学习语料负结果

- 远程优化步：36/36；持久化权重成功并可重新加载。
- 基础模型：schema 87.50%，总体策略匹配25.00%，提案16.67%，部署33.33%。
- SFT与重载：schema 87.50%，总体41.67%，提案16.67%，部署66.67%。
- 判定：未采用。六类近似提示缺少区分机制证据，却指定不同recipe；该缺陷不能靠增加epoch解决。
- `result.json` SHA-256：`EDA5EA4EB8C9CC79088C1DC60ADEAF2744235D83D81B5FB098E5287A59D48242`。

## A2：语料缺陷修复

- 唯一变更：在身份无关聚合历史中加入漂移、历史相似度、既往同作用域收益和机制失败证据；评估使用与正式运行一致的单JSON对象提取。模型、rank、epoch、batch和学习率不变。
- 冻结语料：48条训练、24条场景族隔离留出；训练SHA-256 `8AA31CC91DB02A501E1CF72B2EEC6A0D696D2549AF192BA1A6571418FA1D0192`，留出SHA-256 `B5BB211CD8FEBAFBE84522C1C2B6816BF071795FA99A94C051D04A11D4638EFF`。
- 训练：Qwen3.5-4B，LoRA rank 8，3 epoch，batch 4，学习率`1e-4`，36/36远程优化步；最终监督Token损失`0.010448397`。
- 基础模型：schema 87.50%，总体41.67%，提案50.00%，部署33.33%。
- SFT及重载：schema 100%，总体87.50%，提案75.00%，部署100%；重载聚合指标与首次Sampler评估一致。
- 三个严格标签差异都位于回归recipe选择；模型给出的recipe均为注册表内可执行项且history policy合法，但严格唯一标签门仍按失败计。为避免观察留出后放宽标准，本轮不事后改门、不追加训练。
- 判定：未达到预注册的总体至少90%和数值安全100%，故不建议提交页选择该Sampler。
- `result.json` SHA-256：`14012171F3517B1FFFD5069F83521230CE64D5AC20CD312DAC2BE0980746CF42`；重载评估SHA-256 `404CFF9235DA947303D389AC78EEB3C12B9D980C497537DF93AE84E99F15D29D`。

## SwanLab与隐私边界

- 公开运行：[competition-agent-sft-001-a2](https://swanlab.cn/@nanmo-max/BRACE-MSI/runs/ph2ztekq)
- 本地公开spool：39条训练/评估聚合记录，SHA-256 `24A0C3826C529F7E5B3C08D827A73068F32E2E3D2EBFC6FA500001F9AFCB1DCB`。
- 扫描未发现`trio://`、API Key、Authorization、prompt、原始回复、模型路径或工业样本字段。
- 持久化Sampler路径只保存在仓库外受控产物中，不进入Git、SwanLab或正式镜像。

## 发布影响

Task 11完成了PyTRiO训练链与SwanLab证据链，但没有产生可采用的新Sampler。Task 12应绑定平台已校验的Qwen3.5-4B基础模型，并验证正式镜像仍只通过官方`rnd.model()`调用宿主模型；不得把PyTRiO、SwanLab、Tokenizer或Sampler打入正式镜像。
