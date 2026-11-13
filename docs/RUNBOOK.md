# BRACE-MSI 运行说明

## 本地Smoke

PowerShell：

```powershell
.\run.ps1 synthetic-smoke --output outputs/smoke --protocol predict_then_feedback
```

Linux/macOS：

```sh
./run.sh synthetic-smoke --output outputs/smoke --protocol predict_then_feedback
```

输出目录包含私有检查点、模型注册表、脱敏审计、公开待同步队列和`summary.json`。
合成任务只用于协议与安装验收，不是轴承数据成绩。

## 静态报告

```powershell
.\run.ps1 render-report --input outputs/report.json --output outputs/report.html
```

HTML不加载网络资源，可离线打开。

## Docker

```sh
docker build -t brace-msi:candidate .
docker run --rm --network=none --cpus=4 --memory=8g -v "$PWD/outputs:/outputs" brace-msi:candidate synthetic-smoke --output /outputs/smoke
```

镜像构建上下文可在没有Docker时先运行：

```powershell
$env:PYTHONPATH='src'; python scripts/audit_package.py
```

该静态检查不能替代实际镜像构建、离线安装和大小检查。

当前本地已验收归档（平台状态仍未验证）：

```text
D:/brace-msi-release/BRACE-MSI-0.5.0rc1/BRACE-MSI-0.5.0rc1-image-clean.tar
SHA-256: e3cc5f1c3c2a879344632e083623001864c8dac380c6ebb87239ac5de9799747
```

平台要求的是`docker save`归档，不是源码ZIP。上传后选择该Harness镜像。不要把A/B/C检查点、Sampler权重或API Key另行打入镜像。

## 父模型集成训练与独立预测

`generalist-fit`是平台字段无关的单包入口。它使用只读训练包和父`checkpoint.npz`，只根据train内部组折选择CPU候选，不使用validation指标选型：

```powershell
python -m brace_msi generalist-fit `
  --package-config configs/official_package_dev.json `
  --package-root 'C:/path/to/training-packages' `
  --profile B `
  --output 'D:/runtime/B'
```

产物为`D:/runtime/B/checkpoint.npz`和不含逐样本数据的`training-result.json`。独立预测请求每行只允许`task`（可选）和`inputs`：

```powershell
python -m brace_msi generalist-predict `
  --checkpoint 'D:/runtime/B/checkpoint.npz' `
  --input-jsonl requests.jsonl `
  --output-jsonl predictions.jsonl
```

正式平台事件、挂载和输出字段尚未发布；到货后只在SDK适配层映射，不修改上述模型选择与父链语义。

## 干净环境回归

运行依赖锁定在`requirements.lock`，测试工具锁定在`requirements-dev.lock`。在全新环境中：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --only-binary=:all: -r requirements.lock -r requirements-dev.lock
.\.venv\Scripts\python.exe -m pip install --no-deps .
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest -q --tb=short
```

若机器级pip配置指向失效镜像，应显式传入组织批准的索引；不得用`trusted-host`关闭TLS验证。

## SwanLab

SwanLab是可选发布依赖，不影响无模型服务的核心Harness。安装、离线导出、安全边界和显式同步
流程见 [SWANLAB_INTEGRATION.md](SWANLAB_INTEGRATION.md)。任何同步都必须由操作者在核实官方
项目、公开范围和认证方式后单独执行。

## PyTRiO结构化提案Sampler

先完成`trio login`，不要把API Key写入命令、配置或Git。零远程调用地生成并核验冻结语料：

```powershell
D:\anaconda3\python.exe scripts\run_pytrio_sft.py `
  --output-dir D:\brace-msi-pytrio\PYTRIO-SFT-001
```

只有账户额度已确认且`docs/EXPERIMENTS.md`中的`PYTRIO-SFT-001`预注册未变化时，才显式加入
`--execute`。该模式会先评测基础模型，再执行rank 8、3 epoch的有界SFT，保存持久化Sampler，
最后用同一留出集评测。产物只保存响应哈希、Token计数和聚合得分，不保存API Key或原始响应：

```powershell
D:\anaconda3\python.exe scripts\run_pytrio_sft.py `
  --output-dir D:\brace-msi-pytrio\PYTRIO-SFT-001-A2 `
  --execute
```

`PYTRIO-SFT-001-A1`是失败历史，A2是格式成功但三任务30/30 noop的负对照，均不得复用或覆盖。D-042允许的最后一次A3已经成功，路径位于Git外：

```text
D:/brace-msi-pytrio/PYTRIO-SFT-001-A3/result.json -> sampler_model_path
```

A3路径只保留为历史实验收据，不用于当前提交。按D-050，平台模型类型选择基础模型`Qwen/Qwen3.5-4B`，不填写Sampler路径；API Key只填平台表单。按D-043不再运行新的SFT。服务异常收据与负结果不得删除。
