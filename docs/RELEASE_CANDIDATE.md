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
实际镜像构建、2GB镜像检查及4核8GB断网Smoke已写入CI工作流，但因本机没有容器运行时且仓库
无可触发远端，仍保持BLOCKED，不能用上下文大小替代镜像大小。

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
| 实际Docker镜像 | BLOCKED | 本机无Docker/Podman，相关Windows功能未启用；没有镜像文件或大小证据 |
| Linux 4核8GB容器 | BLOCKED | 同上；A2的4核亲和性/RSS观测不替代容器限额 |
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

`image_artifact`在没有真实镜像时必须为`null`，不得用源码压缩包或Docker上下文大小替代。

## 真实平台到货后的唯一工作方向

1. 登记并校验SDK、数据、评分与SwanLab规范的版本和哈希；
2. 实现插件内真实字段映射及数据/预测出入站；
3. 构建并验收4核8GB、无公网、低于2GB的Linux镜像；
4. 只在官方开发流上做评分优化，不重开既有代理密封段。
