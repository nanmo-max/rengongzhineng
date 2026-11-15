# PYTRIO-ONLINE-001 在线验收

## 结论

平台已校验的`Qwen/Qwen3.5-4B`基础模型在三个独立进程中均返回非零Token、严格schema合法的BRACE提案；三次均第一次请求成功。第1轮提案实际进入RC7候选训练，第2、3轮由冻结候选日程约束为retain，证明Agent建议可用且不能绕过确定性策略。

## 运行证据

| 轮次 | 输入/输出Token | 延迟（秒） | 建议 | 实际动作 | 结果 |
| --- | ---: | ---: | --- | --- | --- |
| 1 | 330 / 184 | 13.626 | incremental_update | incremental_update | 真实训练候选；首轮历史不足，拒绝部署 |
| 2 | 370 / 197 | 16.559 | incremental_update | noop | 不在冻结候选日程，retain |
| 3 | 403 / 200 | 13.335 | incremental_update | noop | 不在冻结候选日程，retain |

- 有效响应：3/3；非零Token响应：3/3；建议实际训练：1。
- 累计输入/输出Token：1103/581。
- 运行根：`D:/brace-msi-pytrio/PYTRIO-ONLINE-001-A1/`。
- 机器摘要：`summary.json`，SHA-256 `3005C56BAE0AF4A444B6CD231C449F34F66A1A049D351E4415B132F4D063C7AF`。
- 模型路径未配置；没有使用或训练LoRA/Sampler。
- 公开validation读取0次；官方试运行使用0次。
- 产物不含API Key、授权头、Sampler路径或原始响应。

## 根因与发布修正

历史成功响应约14.86秒；本次三次成功响应为13.33—16.56秒。旧Native入口默认15秒处在正常响应延迟边缘，足以解释此前间歇性`RuntimeError`。发布补丁将Native PyTRiO默认超时提高到60秒，不改变模型、提示schema、候选日程、训练参数、安全门或失败retain语义。

## 发布容器验收

`0.7.1rc1`镜像内置7个固定SHA-256的Qwen3.5-4B Tokenizer/配置资产，共22,912,511字节；明确不包含Qwen权重。容器只挂载运行时PyTRiO凭据，没有挂载宿主Tokenizer缓存：

- 4核、8GB、256 PID、只读根文件系统下，一次请求成功；330/184 Token、4.620秒；合法`incremental_update`提案进入真实候选训练。
- `--network none`下两次失败均有`RuntimeError`收据，随后执行`noop/retain`，候选训练为false，父checkpoint哈希保持不变。
- 完整回归`383 passed in 154.27s`；镜像248,863,860字节，无模型权重、数据、checkpoint或密钥。
- `docker save`归档已重载，SHA-256为`6BA798571F88CC88A6FB298FA63E99CE723DFCC057A3BDEB9EF103E69DCF3CFE`。

这证明本机PyTRiO服务链、干净发布容器和失败恢复可工作；不代替平台侧镜像导入、凭据注入、Token计量或正式评测。
