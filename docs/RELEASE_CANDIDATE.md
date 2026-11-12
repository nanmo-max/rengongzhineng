# BRACE-MSI 0.2.0rc2 Release Candidate

## 结论

本RC在不改写`BRACE-MSI-0.1.0rc1`历史标签的前提下，纳入官方A/B/C公开训练包候选、
一次性回归矩阵和三任务十轮确定性Harness，停止本地算法探索。A1`run-ce3e907`继续标记为
`INVALID`，A2`run-7ef3829`继续标记为本地代理工程验收`SUCCEEDED`。第三任务仅是
`protocol_only`合成轴承流，不是实际轴承性能证据。

RC不包含原始数据、模型权重、私有审计日志、API密钥或正式平台字段。源码交付包由
`scripts/build_release_candidate.py`从Git跟踪文件的白名单确定性生成；公开证据包只复制A1/A2
的`summary.json`、离线HTML和脱敏`public-spool.jsonl`。

最终证据：代码环境与全新venv均为`221 passed`，全新环境安装wheel版本`0.2.0rc2`，
`pip check`无冲突，编译检查通过。Docker上下文静态审计为208文件、1,409,262字节且无禁入文件。
实际镜像已在Docker Engine 28.5.1、linux/amd64上构建。镜像170,356,869字节，以UID 10001
非root运行，`pip check`通过且镜像内无数据、权重、Embedding或密钥；在`--network=none --cpus=4
--memory=8g --pids-limit=256`下完成3候选协议Smoke。机器证据见
`docs/results/RC2_CONTAINER_ACCEPTANCE.json`。

## 交付矩阵

| 项目 | 状态 | 证据或阻塞 |
|---|---|---|
| 统一Harness与CPU模型 | PASS | `src/brace_msi/`及自动测试 |
| 两种内部事件协议 | PASS | `protocol/`与防泄漏测试 |
| 干净依赖安装 | PASS | RR-002：隔离环境`pip check`及Linux cp312轮子解析 |
| SwanLab通用离线记录 | PASS | RR-003：真实0.10.4生成`run-*`，未执行云端同步 |
| 正式SDK插件准备 | PASS | RR-004：清单、动态加载、fail-closed契约CLI |
| B/C有界性能矩阵 | PASS | B RMSE改善6.46%；C改善0.95%；MAE均改善；公开开发证据 |
| 三任务十轮Harness | PASS | 每任务10轮、3候选、7 no-op；三任务机器复算有效 |
| Docker上下文静态审计 | PASS | 小于2GB，无数据/权重/密钥 |
| 实际Docker镜像 | PASS | linux/amd64；170,356,869字节；UID 10001；无禁入文件；`docker save`归档可重载 |
| Linux 4核8GB容器 | PASS | 断网、4核、8GB、256 PID下协议Smoke完成，`candidate_count=3` |
| 比赛SwanLab公开同步 | BLOCKED | 等待比赛项目、字段、可见性、认证和同步责任规范 `[H-004]` |
| 正式SDK/数据/评分 | BLOCKED | 等待官方材料 `[H-001]` `[H-002]` `[H-003]` |

## 构建交付包

必须在干净Git工作树和完成最终回归后执行：

```powershell
$env:PYTHONPATH='src'
python scripts/build_release_candidate.py `
  --output D:/brace-msi-release/BRACE-MSI-0.2.0rc2 `
  --verification-evidence docs/results/RC2_VERIFICATION.json
```

输出：

- `BRACE-MSI-0.2.0rc2-source.zip`：源码、配置、测试与正式文档；
- `public-evidence/`：A1/A2公开聚合证据，保留各自状态；
- `release-manifest.json`：提交、SHA-256、证据边界、PASS/BLOCKED发布门。

历史源码清单生成时`image_artifact`为`null`；实际镜像到位后只允许用真实`docker save`归档及
SHA-256补充，不得用源码压缩包或Docker上下文大小替代。

当前已生成交付包：`D:/brace-msi-release/BRACE-MSI-0.2.0rc2/`。发布源提交为
`5d13b78f1efabc97fef93b2a2906b5195c3eaa9c`，源码归档SHA-256为
`da9e4a4cc04596177ed960a119cc738869097972ef6db27e2311929afbd8b7ae`，发布清单SHA-256为
`28e8a752ee2e5e2f9cdc9bc7463c3f2803ac3222c520e73ee120cbf7e3e71502`。

最终上传用Harness镜像归档为
`D:/brace-msi-release/BRACE-MSI-0.2.0rc2/BRACE-MSI-0.2.0rc2-image-clean.tar`，来自干净提交
`e28113cc9a1c641fab9e24e32eafd29f2cdb2fb2`，大小170,378,752字节，SHA-256为
`7b64490b0456c4b36bdc6189f34c9ce5e372894b911d76a3b40a6e8142e09327`。旧的非`clean`归档保留
为构建过程证据，不作为最终上传入口。

## 真实平台到货后的唯一工作方向

1. 登记并校验SDK、评分与SwanLab规范的版本和哈希；
2. 实现插件内真实字段映射及数据/预测出入站；
3. 将正式SDK字段和平台挂载规则接入已通过容器验收的Harness镜像；
4. 只在官方开发流上做评分优化，不重开既有代理密封段。
