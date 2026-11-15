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

这证明本机PyTRiO服务链和RC入口可工作，不代替平台容器内的凭据注入、网络可达性和Token计量验证。
