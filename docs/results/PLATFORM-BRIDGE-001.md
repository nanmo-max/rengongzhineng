# PLATFORM-BRIDGE-001 平台薄桥接边界加固

## 结论

平台反馈确认此前草稿适配器有缺陷，因此旧失败不能作为镜像不兼容结论。`BRACE-MSI-0.8.1rc1`在不改变训练器、Portfolio策略、SafetyGate、PyTRiO或模型参数的前提下，补齐外部薄桥接器所需的三项显式契约：父checkpoint哈希、期望轮次和始终存在的模型产物声明。

平台私有`workspace_io.py`和完整frame schema仍未发布，本实现没有猜测这些字段。外部桥接器应从start frame顶层读取父哈希和轮次，将其转换为Native CLI参数；argv prefix为`["python3", "-m", "brace_msi"]`，具体`start`/`submit`操作由桥接器追加。

## 修复内容

- `start --expected-parent-sha256`在读取训练数据前校验挂载父文件，支持裸64位SHA-256和`sha256:`前缀。
- `start --expected-round-index`与持久化`/workspace/state.json`历史严格匹配；缺失历史时不能伪装为第2—10轮。
- 部署、拒绝和retain收据均包含`model_artifact`，声明`checkpoint.npz`相对路径、SHA-256、字节数和处置类型。
- retain仍原样复制父checkpoint，模型文件哈希不改变；没有通过修改权重或metadata伪造轮次。
- `describe`暴露无mode的argv prefix，保留现有`describe/start/submit`操作集合。

## 自动测试

- 新测试先观察到5项预期失败，再完成最小实现。
- 平台运行时专项：`54 passed in 26.69s`。
- 完整回归：`424 passed in 153.12s`。
- `git diff --check`通过。

## 真实容器验收

- 代码提交：`e3b00d1`。
- 镜像：`brace-msi:0.8.1rc1`，linux/amd64，非root用户`brace`。
- 限制：`--network none --cpus 4 --memory 8g --pids-limit 256 --read-only`。
- 官方A父checkpoint连续运行两轮；第1轮显式期望轮次1，第2轮显式期望轮次2并绑定第1轮产物SHA-256。
- 两轮均由Gate retain父模型；两轮收据都声明有效`checkpoint.npz`，声明哈希与挂载输出文件一致。
- 独立预测完成1,244条；`pip check`无冲突；镜像扫描未发现工业模型/Qwen权重、`.npz/.pt/.pth/.onnx/.safetensors`或密钥文件。
- 镜像大小：249,004,758字节；归档大小：249,029,120字节，低于2GB。
- `docker save`归档：`D:/brace-msi-platform-bridge/BRACE-MSI-0.8.1rc1/brace-msi-0.8.1rc1-harness.tar`。
- 归档SHA-256：`9B1A1822E9062229CF940D0CF9FDBD7D33F1301A94A993FE111B56E36184ED7E`。
- 删除正式tag后从归档`docker load`，恢复的镜像ID与保存前一致：`sha256:a4a23e7a1a82901d56ce3654ca3e025853d8a90ef63e47d2acd16f482868cc44`。

## 未解除的外部阻塞

- 平台侧薄桥接器源码、完整start frame和artifact declaration schema仍不可见。
- 平台是否跨轮恢复workspace/history必须由正式适配器验证；若不恢复，本镜像会在期望轮次校验处失败关闭。
- 空`/data`和`/previous`只能做静态入口预检，不能证明真实训练行为；正式兼容性仍需平台带实际挂载复验。
- 本次没有消耗官方试运行次数，没有调用在线PyTRiO，也没有生成新的SwanLab正式记录。
