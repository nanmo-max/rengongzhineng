# IMAGE14-DEBIAN-001：镜像14 Debian兼容性迁移

日期：2026-11-25。源码基线：`c653e0e04297b655b93e28a90abd9f36e2ff761d`。当前验收状态以报告末尾及STATUS为准。

Bookworm当前是Debian12 oldstable LTS，amd64支持至2028-06-30；当前最新stable为Debian13。本次选择Bookworm旨在保持较成熟的系统ABI和Python3.12兼容，未把旧稳定版冒充最新版本。来源：https://www.debian.org/releases/bookworm/ 。

## 修改与启动故障边界

历史镜像14的`Dockerfile.formal`使用Azure Linux Python 3.12固定digest，运行依赖`numpy==1.26.4`，通过tdnf安装shadow-utils。新构建使用Docker Official Image `python:3.12-slim-bookworm`固定digest `sha256:44cf1793efa7c7a476bb0f2cff81443f4a072c90c1cb127e2924933daa3e8c64`。Python保持3.12.16，NumPy保持1.26.4，保留SDK1.0.2及全部镜像14业务源码。

本地旧镜像和Debian镜像的`/bin/true`、`/bin/sh`、Python、默认帮助、describe均启动成功。官方转述的“命令执行前全部退出”尚未在本机复现；Azure Linux较少见与平台运行时不兼容是待核实假设，不能写成已证实根因。若Debian在官方仍出现同样现象，应获取平台容器创建阶段的OCI错误、exit code和实际argv/working-directory/mount，而不是修改训练算法。

新镜像保留`ENTRYPOINT ["python3","/app/harness.py"]`、`CMD ["--help"]`、工作目录`/app`、UID/GID10001。平台直接执行`python3 /app/harness.py describe|train|predict`；Shell预检须以exec方式或覆盖entrypoint运行，不能将`/bin/true`作为harness子命令。输入/父模型挂载只读，workspace可写；缺失数据时不能进行训练。

## 依赖与代码范围

- 正式业务运行只需要NumPy1.26.4及Python标准库；SDK为vendored源码。没有新增apt系统包、编译器、Git、Torch、SciPy、sklearn、PyTRiO、SwanLab或论文仓库。
- 系统包清单、Python包清单、每个发布Python文件SHA-256在`artifacts/image14-debian/verification.json`。19个/app文件维持历史白名单；测试工具与测试依赖只在独立`debian1-test`镜像，后者禁止上传。
- 平台模型服务经`rnd.model()`/官方宿主RPC接入。60次本地协议调用通过并验证调用ID；这不是60次真实远程PyTRiO调用。
- SwanLab保持镜像外观测方式。本次没有生成冒充云端的实验运行；本机SwanLab0.10.5/PyTRiO0.2.9可发现，历史接口测试包含在回归中。实际平台鉴权、模型网关、云端同步没有在本轮在线复验，状态为EXTERNAL_NOT_REVERIFIED。

## 论文与代码来源独立核查

| 实际机制 | 核实来源 | 实际采用范围与许可证边界 |
|---|---|---|
| Adam | Kingma、Ba，Adam: A Method for Stochastic Optimization，ICLR2015；2014年arXiv初稿：https://arxiv.org/abs/1412.6980 | `brace_formal/model.py`原生NumPy前反向和Adam；继承官方MLP契约，并非复制作者论文仓库。论文真实存在，年代早不影响真实性；未据论文许可推定项目代码许可。 |
| 父/候选权重插值 | Wortsman等，Model soups，ICML2022，PMLR162:23965–23998：https://proceedings.mlr.press/v162/wortsman22a.html | `portfolio.py:fit_recipe`仅做0.75父权重+0.25候选权重。属于简化独立实现，不能声称完整复现作者多模型greedy soup或其论文性能。 |
| Model soups作者代码 | https://github.com/mlfoundations/model-soups ，MIT许可证：https://raw.githubusercontent.com/mlfoundations/model-soups/main/LICENSE | 仓库真实公开、未归档/未禁用，2026-11-25查询API显示最后代码push为2024-07-15；属于研究参考，不能说持续活跃维护。正式镜像未复制或依赖该仓库，无其Torch/CLIP依赖。 |
| NumPy | https://github.com/numpy/numpy/blob/v1.26.4/LICENSE.txt | BSD-3-Clause；wheel包含依赖许可证，固定1.26.4为旧锁定兼容版本，不声称最新。 |
| Python基础镜像 | https://github.com/docker-library/python | Docker Official Image，Debian Bookworm Slim；镜像打包代码MIT，Python/系统库分别适用其各自许可证。 |

SAM、SWA、L2-SP、DIR、PROCEED、Type-LDA、PaperFusion等历史研究代码不在镜像14正式`/app`白名单中；没有因本次迁移把这些代码带入镜像。项目源码和官方SDK的再分发授权仍按赛事及权利人条款，不擅自补写MIT/Apache。

## 验收证据

- 原始日志：`artifacts/image14-debian/`。训练Smoke仅用官方train和父checkpoint；预测输入为train前5行另存到测试投影。未使用隐藏或XJTU密封集，Smoke不作泛化或性能提升结论。
- `verification.json`：A/B/C各10轮、30真实候选、60协议调用、15行独立预测、所有正式Python源码哈希一致；4核4GiB、断网、只读根运行114.86秒。
- `resource-smoke/resources.json`：A/B/C额外单轮墙钟0.877/1.710/8.288秒，cgroup峰值内存28,815,360/53,653,504/244,559,872字节；`memory.max=4294967296`、`cpu.max=400000 100000`。包含容器/协议开销，不等同官方评测总时长。
- 本地完整历史回归初轮469通过/2失败，原因是导出树缺Git索引；补齐隔离测试树索引后原失败项及所在文件4/4通过。原始失败日志保留。完整旧测试本身包含公开validation描述性评估，这些读取不用于调参或选型；与仅train的Smoke分别登记。
- Linux完整回归首轮401通过/39失败/30错误/1跳过，原因包括Windows绝对路径、测试Git、研究依赖缺失和正式开关影响研究测试。所有修正仅在独立测试环境，日志保留，二轮结果待追加。
- Linux后续测试环境修正：隔离测试树补Git索引/本地fixture提交；测试模块中的Windows包路径/Python路径映射到只读`/official`和Linux解释器；研究开关只在测试镜像关闭；多进程测试入口加`__main__`保护。未改变测试断言和正式源码。中间轮次日志保留；最终结果见后续验收状态。
- SwanLab镜像外离线事件真实写入`artifacts/image14-debian/swanlab-offline-retry/`，初轮GBK编码失败、UTF-8重试成功，`swanlab-interface.json`明确cloud_synced=false；这不是训练实验或云端完成证据。
- Docker正式镜像：`brace-msi:0.10.6rc1-debian1`；镜像ID `sha256:036f7afb3b2f633bd17a45f2fb524ab0133ebf92a6980a5c654f5ff78b891da6`；镜像66,900,098字节。
- `docker save`归档：`artifacts/image14-debian/harness-debian.tar`，66,918,400字节，SHA-256 `3C8F01CD7D84A3F226111BF81AABE02E1DDC9CD53426997D16A6704FA0837F7C`，小于2GiB；save/load及重载后启动通过。旧镜像14归档不覆盖。

真实平台尚未上传或消耗次数；本地通过不能代替官方容器运行时验证。

## 最终本地验收：LOCAL_READY_PENDING_PLATFORM

最终Linux完整历史回归：**470 passed, 1 skipped in 157.25s**，零失败。跳过项`tests/performance/test_gas_replay.py:117`依赖未挂载Gas原始研究数据；没有为补齐研究测试读取受限数据。日志`linux-regression5.log`。主入口保护修复后多进程插件测试也通过，正式源码和断言均未变。

本地通过后形成独立Debian候选，历史Azure镜像14继续保留。候选正式tar为`harness-debian.tar`；`source-debian.zip`含固定历史运行代码及新Dockerfile；`release-manifest.json`绑定基础digest、镜像ID、源码基线、归档和验收哈希。`DEBIAN-兼容性验收与源码.zip`仅含代码/收据/报告，不包含tar、数据、权重或密钥。测试镜像`debian1-test`不属于交付。

未验证外部项：真实平台OCI启动、实际PyTRiO宿主网关和在线SwanLab同步。本次只证明本地Linux容器兼容和接口链条，未提高或重新申报模型成绩。
