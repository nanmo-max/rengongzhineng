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
