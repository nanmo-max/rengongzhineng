# FORMAL-CONTINUATION-RC-001 验收报告

## 结论

`BRACE-MSI-0.5.1rc1`已完成本地正式续训候选验收。它不再把`0.5.0rc1`的HGB父集成作为正式模型：Docker内设置`BRACE_FORMAL_RELEASE=1`，异构研究训练/预测命令全部失败关闭；正式工作流只调用官方训练包中的NumPy训练器，从官方baseline或当前稳定父`checkpoint.npz`继续训练。

本结论只证明本地代码、父链和容器满足当前可核验要求。正式SDK字段、平台挂载与模型校验仍未发生，不能写成平台已经通过。

## 证据来源

- 平台旧提交拒绝提示：`O-PLATFORM-008`，截图SHA-256 `F51B3CB2...D2F783D`。用户明确该截图属于旧提交，不是本RC结果。
- 实现提交：`04818664feb0e21ae52f6cf60e98f9626620207e`。
- 机器证据：`FORMAL_CONTINUATION_RC_VERIFICATION.json`、`FORMAL_CONTINUATION_RC_CONTAINER_ACCEPTANCE.json`。
- Git外运行根：`D:/brace-msi-formal/FORMAL-CONTINUATION-RC-001-A1/`。

## 父检查点续训证明

- A/B/C均通过`baseline -> child -> grandchild`两代专项测试。
- 每个子模型与直接父模型拥有完全相同的NPZ字段集合；`mean`和`scale`逐数组相同。
- 模型权重与Adam状态均真实变化；`initial_epochs/steps`严格等于直接父模型的最终状态，最终epoch/step继续增加。
- checkpoint中不存在异构`model_blob`，最大checkpoint仅132,180字节，远低于64 MiB。
- 333项完整回归通过；正式边界与三任务父链专项共18项通过。

## 4核8GB断网容器

三任务均在`--network=none --cpus=4 --memory=8g --pids-limit=256`下完成十轮和3次真实候选，并由`--validate-only`机器复算为`valid=true`。A/B/C最终公开历史暴露指标分别为0.725695 Macro-F1、656.351785 RMSE、52.350178 RMSE；这些数值只证明冻结续训链可运行，不是隐藏测试或新独立泛化证据。

镜像为linux/amd64、241,750,529字节、非root UID10001，`pip check`与`compileall`通过，镜像文件扫描未发现数据、checkpoint、权重或凭据。A/B/C最终稳定checkpoint均通过官方`baselines.predict`独立入口。

## 上传文件

- 路径：`D:/brace-msi-release/BRACE-MSI-0.5.1rc1/BRACE-MSI-0.5.1rc1-image-clean.tar`
- 字节数：241,774,080
- SHA-256：`6331280b384b89b2315cfad12551fbdf7855cac2c2ef2d9712464cf23334e181`
- 格式：`docker save`归档；删除本地标签后已用`docker load`恢复并核对镜像ID。

## 未完成的外部门

- 平台镜像上传与“镜像可用”状态；
- 正式SDK事件、父checkpoint挂载和输出字段映射；
- 平台模型校验、续训协议校验和正式评测；
- 正式PyTRiO模型服务与SwanLab比赛字段。

因此下一步只能上传`0.5.1rc1`归档并按平台新版本校验；不得上传`0.5.0rc1`或把本地通过表述为平台通过。
