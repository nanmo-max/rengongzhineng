# PLATFORM-PREFLIGHT-001 空挂载镜像预检兼容修复

## 结论

`BRACE-MSI-0.8.2rc1`修复了一个可稳定复现的镜像启动回归：`0.8.1rc1`把默认命令设为`start`，平台尚未挂载四个目录时，非root容器会尝试创建`/workspace`并以退出码1终止。历史首个完成平台试运行的镜像默认命令为`--help`，不会在镜像校验阶段误启动训练。

本补丁只恢复无输入安全启动；显式`start`、`submit`、父哈希、轮次、候选策略、SafetyGate、PyTRiO和SwanLab逻辑均未改变。由于平台反馈文本被截断，本证据不能证明默认命令是平台停止的唯一原因，也不冒充官方兼容通过。

## 红绿证据

- 红灯：新测试要求`CMD ["--help"]`，在0.8.1树上按预期失败；本机裸运行0.8.1复现`PermissionError: [Errno 13] Permission denied: '/workspace'`，退出码1。
- 绿灯：Docker默认命令恢复为`--help`，裸运行0.8.2输出CLI帮助并退出0。
- 运行提交：`856680737df8563c93db3ededcee6fb94a2075f4`。
- 完整回归：首轮`424 passed in 158.19s`；最终复核曾出现一次Windows训练子进程无stderr返回`4294967295`，对应C父链用例立即单测通过，随后完整复跑为`424 passed in 160.27s`。该偶发失败未隐藏，也没有通过修改测试规避。

## 双路径容器验收

- 镜像：`brace-msi:0.8.2rc1`，linux/amd64，非root用户`brace`。
- 裸启动：无挂载、无网络，退出0。
- 原生训练：4核、8GB、断网、只读根，以官方A训练包父`checkpoint.npz`和当前带标签批次显式执行`start --advisor deterministic --expected-round-index 1`，退出0；产物`checkpoint.npz`为132,180字节，父哈希校验通过。
- 独立预测：对官方A公开validation显式执行`submit`，退出0并生成1,244条`id/outputs`预测。
- 包版本：`0.8.2rc1`；`pip check`无冲突；`/app`禁入后缀扫描为0。
- 镜像大小：248,956,508字节；归档大小：248,980,992字节，低于2GB。
- 归档：`D:/brace-msi-platform-bridge/BRACE-MSI-0.8.2rc1/brace-msi-0.8.2rc1-harness.tar`。
- SHA-256：`7CA09B029946E8D5B94BEFA8A53EDEFC0DF168051750FA0D4CB8C3FFBBE7784F`；`docker load`成功。

## 保留的外部阻塞

- 平台真实薄桥接器、完整frame schema和调用生命周期仍不可见。
- 平台真实凭据注入和在线PyTRiO Token仍须在下一次平台试运行验证。
- 本次未调用在线PyTRiO、未同步新SwanLab、未读取隐藏数据、未消耗官方试运行次数。
