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
