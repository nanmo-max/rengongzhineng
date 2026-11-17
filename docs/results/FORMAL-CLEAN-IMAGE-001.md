# FORMAL-CLEAN-IMAGE-001 验收记录

## 冻结结论

`BRACE-MSI-0.10.0rc1`已形成首个第一性原理协议RC。它可作为后续性能集成失败时的恢复基线，但在`FORMAL-PERF-001`完成前不消耗官方试运行。

## 最终归档

- 路径：`D:/brace-msi-first-principles-release/BRACE-MSI-0.10.0rc1-FINAL-PROVENANCE-OFF/harness.tar`
- 格式：`docker save`
- 大小：81,201,152字节
- SHA-256：`DC73FAFC73906D1A841BE3AC47DBCBF3A69915C380711B07E28A2C5C0C05C39E`
- 镜像ID：`sha256:62d4487ba426db3d35b9da5935684ac9aaf00044d06e97017b5866eeaacd8009`
- 删除原tag后`docker load`恢复相同镜像ID。

## 镜像边界

- Linux amd64；镜像大小81,183,334字节；运行用户`10001:10001`。
- SDK：`contest_harness` 1.0.2；协议`contest.harness.workspace.v2`；模型访问`host_gateway_rpc`。
- 运行依赖仅NumPy 1.26.4。
- `/app`仅包含官方SDK九个源码文件、`brace_formal`七个源码文件、`harness.py`和`contest_submission.py`。
- 未安装或打包旧`brace_msi`、PyTRiO私有客户端、SwanLab、sklearn、SciPy、psutil、数据、权重、实验报告、密钥或Python缓存。

## 容器验收

- 精确最终镜像在`--network none --cpus 4 --memory 8g`下完成官方A/B/C训练包各10轮。
- 共30个唯一宿主模型调用；每轮完成记录均引用当前call ID。
- 最终候选：A第1轮、B第2轮、C第1轮；其余轮次真实retain。
- 三任务各完成5行独立预测；候选checkpoint最大132,180字节，远低于64 MiB。
- `pip check`通过；只读describe、非root、禁入扫描通过。
- A2验收：`D:/brace-msi-first-principles-release/FORMAL-CLEAN-IMAGE-001-A2-FINAL/acceptance.json`，SHA-256 `DE84F00C622B85F848B213F5DE364F3235BBCCDADCAFD2198770D49238ECC326`。
- 完整代码回归：`455 passed in 148.45s`。

## 证据边界

这些结果只证明本地官方协议模拟与容器工程门。模型响应由本地宿主模拟器提供，不是平台Qwen调用；没有SwanLab同步、隐藏数据、官方试运行或正式成绩。
