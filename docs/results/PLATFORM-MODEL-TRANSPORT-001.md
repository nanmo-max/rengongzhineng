# PLATFORM-MODEL-TRANSPORT-001

## 结论

`BRACE-MSI-0.8.3rc1`已在本地修复平台指出的模型传输协议缺口。训练入口不再要求外部把Chat Completions重写成PyTRiO私有Sampler协议；镜像原生接收一个可调用的`workspace_io.model_transport`，由镜像构造请求、解析响应并验证Token。

该结论是本地接口与容器验收，不是平台“校验通过”或隐藏成绩。真实平台服务仍需重新上传确认。

## 根因与修复

- 0.8.2唯一LLM入口使用PyTRiO `ServiceClient`/Sampler私有协议；平台桥接只提供Chat Completions，忠实薄桥接无法完成。
- 新增`ChatCompletionsSamplingTransport`，协议为`openai.chat.completions.v1`。
- `start_round(..., model_transport=...)`在原生代码内建立受控Advisor；CLI支持直接注入或解析`workspace_io.model_transport`。
- 平台模式每轮强制发起模型调用；输入或输出Token非正值视为失败。
- 两次失败后只发布父checkpoint，候选不训练，禁止零调用静默继续。
- `describe`显式公开绑定、协议和训练阶段必需性。

## 验证

- 单元与平台专项：73项通过。
- 完整回归：430项通过，161.05秒。
- 容器：linux/amd64，UID10001，4核、8GB、断网、只读根文件系统。
- 平台替身：挂载`workspace_io.model_transport`，实际收到`Qwen/Qwen3.5-4B`请求，返回123输入Token/45输出Token。
- 训练：官方A父`checkpoint.npz`和445条公开train进入原生候选训练；候选由Gate拒绝后正确保留父模型，证明模型调用不绕过SafetyGate。
- 预测：独立`submit`完成1,244条输出。
- 失败路径：替身连续异常时调用2次，随后`noop/retain`，`candidate_trained=false`。
- 依赖与禁入：`pip check`无冲突；镜像内未发现`.npz/.jsonl/.joblib/.pkl/.tar`、密钥或原始数据。

## 交付

- 镜像：`brace-msi:0.8.3rc1`，249,015,083字节。
- Docker归档：`D:/brace-msi-platform-bridge/BRACE-MSI-0.8.3rc1/brace-msi-0.8.3rc1-harness.tar`，249,039,360字节。
- SHA-256：`4BE4327D29B8D25A2480427776AC58696FB6A48EA63AB576C35944240EA3A694`。
- `docker load`：成功。
- SwanLab：<https://swanlab.cn/@nanmo-max/brace-msi-platform-native>。
- 源码：<https://github.com/nanmo-max/rengongzhineng/tree/codex/native-competitive-rc>。
