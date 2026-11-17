# FORMAL-AUDIT-FIX-001 终审修复记录

## 结论

`0.10.2rc1`因终审发现权威平台测量、执行声明真实性、独立组不足降级、跨任务工作区隔离和验收口径缺口而撤回上传资格。上述缺口在新版本`0.10.3rc1`中修复；历史RC和失败证据均未覆盖。

本记录只证明本地官方SDK契约、父链、宿主调用边界、候选门控和容器交付门。它不证明平台导入、真实Qwen Token、隐藏测试性能或官方得分。

## 修复项

1. 候选部署以`submit_candidate`返回的`summary.metrics`为权威；缺失、非有限或未改善时保留父artifact。
2. 收据同时记录Agent请求参数和实际执行的recipe、epoch、学习率倍率、有效学习率、父checkpoint优化器seed及分折seed，不再把请求参数冒充实际训练参数。
3. 可识别设备/轨迹组不足3个，或无法构造三个独立折时，返回可审计的`retain`，不降级为同行随机分折。
4. workspace路径加入dataset key，并继续包含stage与round，防止A/B/C同一持久卷发生目录碰撞。
5. 本地宿主模拟为候选返回实际计算的非空指标；验收报告分别保留入站父checkpoint哈希和最终选中checkpoint哈希。
6. train与predict均在4核、8GB、断网、只读根文件系统和独立可写挂载下运行。

## 自动验证

- 项目完整回归：`465 passed in 143.76s`。
- 官方SDK 1.0.2 Linux离线测试：15项通过；2项真实在线测试因未注入`PYTRIO_API_KEY`/`CONTEST_PI`按官方条件跳过，没有伪造在线通过。
- 镜像依赖：`python3 -m pip check`返回`No broken requirements found`。
- 镜像身份：linux/amd64，非root用户`10001:10001`，镜像ID`sha256:b503c3407d2a368686f7d4bd4f7b8d945cafd78f5fff2a998883a826433d6a59`，大小`81,188,446`字节。
- `/app`白名单：两个固定入口、`brace_formal`九个源码文件、官方`contest_harness`九个源码文件；没有数据、checkpoint、密钥、PyTRiO、SwanLab、测试、HTML或历史报告。
- 最大本地产物checkpoint：`132,180`字节，低于64 MiB上限。
- 删除本地镜像tag后从归档重新`docker load`，恢复相同镜像ID。

## 30轮精确容器验收

- 机器结果：`D:/brace-msi-first-principles-performance/FORMAL-AUDIT-FIX-001-A5-FINAL-CONTAINER/acceptance.json`。
- SHA-256：`6AB82222A3C015F42B07315A103E749CEAF2B8D9FA15D999F75281FB41DBDF35`。
- A/B/C各10轮、各10个宿主模型调用ID、各5行独立预测；候选提交数分别为1、0、3。
- B因训练内部独立组证据不支持更新而十轮retain，不是运行失败。
- 报告中的candidate host metrics均由独立宿主模拟器实际计算并返回；本地指标不是官方成绩。

## 冻结归档

- 路径：`D:/brace-msi-first-principles-release/BRACE-MSI-0.10.3rc1-FINAL/harness.tar`
- 大小：`81,206,272`字节
- SHA-256：`D08535F0B4A410A9EFF6CBB191505F32B767462B3E42CDC6093E8ABC385CA86A`
- 格式：`docker save`生成的OCI/Docker镜像归档；不得上传源码ZIP、容器export或改名tar。

## PyTRiO与平台模型边界

历史两次官方成功运行均为0 Token，不能证明PyTRiO参与。正式SDK要求的是每轮通过宿主`rnd.model()`产生真实调用ID；平台负责模型、端点、密钥和计量。`0.10.3rc1`因此不内置PyTRiO私有SDK或Sampler权重。下一次平台试运行必须核对非零Token、30个轮调用收据、父链、候选/retain和逐行预测。

## 外部阻塞

归档尚未上传，平台导入、模型绑定、非零Token、正式训练报告和隐藏性能均未验证。只有用户明确决定消耗试运行次数后，才进入`FORMAL-RELEASE-001`。
