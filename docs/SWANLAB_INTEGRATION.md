# SwanLab离线记录与显式同步

> 当前阶段边界：D-023的“最终工程模型冻结后再记录”条件已满足。`SWANLAB-FINAL-001`已按D-044执行并同步；后续禁止重复生成替代记录。比赛专用字段仍等待H-004。

## 证据边界

本接口依据SwanLab官方通用文档实现：`swanlab.init(mode="offline")`生成本地日志，随后对
实际`run-*`目录执行`swanlab sync [options] [logdir]`。当前固定SDK版本为`0.10.4`，因为
官方说明离线日志格式与同步CLI版本必须匹配 `[O-SWANLAB-001]`。

SwanLab页面要求新版记录使用SDK 0.10.0及以上，当前冻结版本0.10.4满足该条件 `[O-SWANLAB-002]`。
比赛专用字段、认证注入和无公网评测结束后的正式同步责任仍等待官方规范 `[H-004]`。

## 安装

核心Harness不强依赖SwanLab。需要导出官方离线日志时，在相同隔离环境额外安装：

```powershell
python -m pip install -r requirements-swanlab.lock
```

## 生成离线日志

Harness先生成经过白名单过滤的`public-spool.jsonl`，再显式转换：

```powershell
python -m brace_msi swanlab-offline-export `
  --spool outputs/run/public-spool.jsonl `
  --logdir outputs/run/swanlog `
  --project brace-msi `
  --experiment-name formal-run
```

默认`public=False`。只有正式规范确认必须公开且目标项目正确时才添加`--public`。导出器只把
公开白名单中的数值型聚合字段写入SwanLab，不写特征、标签、样本ID、预测明细或密钥。

## 同步

导出不会自动联网。先检查生成的`run-*`目录，再打印待人工执行的命令：

```powershell
python -m brace_msi swanlab-sync-command `
  --run-dir outputs/run/swanlog/run-xxx `
  --workspace OFFICIAL_WORKSPACE `
  --project OFFICIAL_PROJECT
```

程序只打印命令，不执行同步，也不接受API Key参数。认证必须按官方机制从安全环境注入。正式
同步前检查SDK/CLI版本均为`0.10.4`，并再次确认公开日志没有私有测试数据。

Windows终端执行同步前应设置UTF-8，避免Rich输出emoji时被GBK编码中断：

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
swanlab sync outputs/run/swanlog/run-xxx --workspace nanmo-max --project brace-msi-final
```

已完成的正式记录项目为`https://swanlab.cn/@nanmo-max/brace-msi-final`，三个运行及失败恢复证据见
`docs/results/SWANLAB-FINAL-001.md`。不得再次同步到新的项目来掩盖历史或制造重复记录。

## 失败降级

- 未安装SwanLab：核心Harness继续运行，离线导出命令明确失败并提示安装锁文件。
- 无公网：使用`mode="offline"`保留本地日志，不影响训练闭环。
- Windows非UTF-8终端：适配器在调用SwanLab前把可重配置文本流切换为UTF-8，避免SDK欢迎信息导致GBK编码失败。
- 同步失败：保留原`run-*`目录；禁止删除或重复生成实验来掩盖失败。
