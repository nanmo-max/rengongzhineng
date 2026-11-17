# BRACE-MSI 最小正式运行核设计

## 目标

构建一套只实现官方 `contest.harness.workspace.v2` 契约的正式镜像：每轮真实调用宿主管理的 Qwen 模型，基于平台父 checkpoint 进行原生续训或 retain，提交可独立预测的 `checkpoint.npz`，跨十轮保持状态与历史，并且不携带研究、模拟、密钥、数据或外部服务客户端。

## 权威边界

1. 官方 SDK 1.0.2 是运行接口唯一权威。
2. 每次 `train` 启动对应一轮；轮次由宿主给出。
3. 每轮在任何策略分支前调用一次 `rnd.model()`；模型名、端点、密钥和计量由宿主控制。
4. `max_tokens=min(256, rnd.max_output_tokens)`，响应只依赖 `receipt.text` 和 `receipt.call_id`，不要求响应包含 usage。
5. 模型调用成功但输出非法时可保守 retain；没有真实 call ID 时该轮失败关闭，禁止伪造。
6. 父文件只经 `rnd.parent.path()`读取；训练只能从父 checkpoint 续接。
7. 每轮使用全新的 `/workspace/round-<round_index>-<stage_id>/state` 和 `candidate` 目录；状态从 SDK 的只读 state mount 复制。
8. 正式候选命令使用官方文档指定的 `python3 /app/harness.py predict`。
9. 隐藏数据不可见；本地模拟数据只进入测试容器，不进入发布镜像。

## 组件

### `brace_formal/model.py`

只包含 `contest.cpu-mlp.v1` checkpoint 的严格加载、预测、Adam续训和确定性保存。不得依赖 sklearn、scipy、psutil 或研究代码。

### `brace_formal/data.py`

严格读取本轮 `train.jsonl`/`validation.jsonl`，校验 ID、数值特征、标签和父模型 schema。只向 Agent 提供聚合统计，不发送逐样本数据。

### `brace_formal/agent.py`

在每轮开头直接调用 `rnd.model()`。接受最小 JSON：`action`为`retain`或`train`，`epochs`为1..5，`learning_rate_multiplier`为0.3/1/3；非法值降级为 retain。安全内核可以收紧建议，但不能跳过模型调用。

### `brace_formal/submission.py`

读取历史和平台父 checkpoint；调用 Agent；对当前训练数据生成最多一个候选；使用本轮公开 validation 只做候选安全判断；提交后以平台返回测量为准；保存状态并完成轮事务。没有候选时选择父 artifact。

### `brace_formal/predict.py`

只从 `CONTEST_ARTIFACT_PATH` 加载选中 checkpoint；分类输出唯一最高分，回归输出非负有限值；不访问训练目录、网络或模型服务。

## 决策策略

- 第1轮允许一个低成本1 epoch候选以建立有效实验链。
- 后续轮次由真实历史、父模型公开验证摘要和当前数据画像决定 retain 或一个候选。
- Agent只能在父模型兼容的 epochs/LR 三档中选择；正式首版不允许任意代码修改、模型家族切换、Bandit、影子模型或私有PyTRiO协议。
- 平台测量回归时 retain 父 artifact；候选不能替换父checkpoint schema。
- 至少三次真实实验由实际十轮历史产生，但不为凑次数强制每轮训练。

## 发布镜像

镜像仅包含：官方九个 SDK 文件、`/app/harness.py`、`/app/contest_submission.py`、`brace_formal`最小模块和 NumPy。不得包含 PyTRiO/SwanLab SDK、API Key、Tokenizer、模型权重、数据、测试、模拟器、HTML、论文实验或历史报告。

SwanLab记录由正式平台完成后的外部公开工程记录生成，不在无公网正式镜像内主动同步。

## 验收

1. 官方 SDK 原包15项Linux测试通过。
2. 低 `max_output_tokens`、非硬编码模型名、无 usage 响应、retain/rollback语义均产生真实 call ID。
3. 同一数据集连续10轮不会复用已存在的 state/candidate目录。
4. A/B/C各10轮、本轮父链、候选/retain、状态恢复和独立逐行预测通过。
5. checkpoint可加载、总产物<=64MiB；Docker 4核8GB、断网、非root、`docker save/load`通过。
6. 镜像禁入扫描为0；本地模拟报告明确标记非官方，不进入镜像。

## 明确不承诺

本地模拟无法保证隐藏数据数值一致；正式平台内部评分公式未知。成功标准是契约正确、真实Agent调用、父链合法和公开数据上的可复核性能改善，不虚构隐藏成绩。
