# 平台提交清单

> 本清单不保存任何API Key。表中“已准备”仅表示本地材料存在，不代表官方平台已经校验或正式评测通过。

## 提交表单

| 平台字段 | 应填写内容 | 当前状态 | 证据/注意事项 |
|---|---|---|---|
| 模型类型 | 持久化 Sampler 微调权重 | 已准备 | A3已生成持久化Sampler |
| 完整Sampler权重路径 | 从Git外`D:/brace-msi-pytrio/PYTRIO-SFT-001-A3/result.json`读取`sampler_model_path` | 已准备 | 完整`trio://`路径不写入Git或作品文档；不要自行拼接 |
| 训练记录链接 | `https://swanlab.cn/@nanmo-max/brace-msi-final` | 已同步并核验 | 公开项目含Gas/Bearing/Engine三个`FINISHED`实验，每项10条聚合记录 |
| Harness镜像 | `BRACE-MSI-0.3.0rc3-image-clean.tar` | 已准备 | SHA-256：`0daef2e0e66cd2d3bc809a5d836a03020d1f90d677df91830fedc4feeb6d325a` |
| 源码仓库链接 | `https://github.com/nanmo-max/rengongzhineng/tree/task/core-001` | 已推送 | 当前分支含RC3源码、测试、证据和提交材料；未覆盖远端main |
| PyTRiO API Key | 由队长在平台字段中粘贴 | 人工填写 | 不通过聊天、Git、作品文档或日志传递 |
| 作品文档 | `D:/brace-msi-release/BRACE-MSI-0.3.0rc3-submission-materials/BRACE-MSI-作品说明书.docx` | 已生成并校验 | 无官方模板；指导教师暂不填写；另附PDF预览版 |

作品说明书DOCX SHA-256：`0822ae41d618a8da584881b00ca29736bf1521e082b7c9f06ca7f79b5f132213`；PDF SHA-256：`cc67c2c46f99a1a85741e160b153ab297ee6ce337983e211eed2b9afae63f292`。

## 镜像上传核对

- 上传的是`docker save`生成的`.tar`，不是源码ZIP或Docker构建上下文；
- 本地文件大小为240,602,112字节；镜像内部大小为240,579,085字节；
- 镜像平台为linux/amd64，默认用户UID 10001；
- 镜像不含原始数据、A/B/C检查点、Sampler权重、Embedding或密钥；
- 平台选择镜像后再执行“校验并保存新版本”；
- 校验失败时先保存平台原始错误文本和时间，不重复盲试消耗正式机会。

## GitHub推送核对

- 只推送源码、配置、测试和脱敏聚合证据；
- 不推送`D:/brace-msi-*`运行目录、官方训练包、模型检查点、镜像tar、API Key或逐样本日志；
- 当前正式候选提交为`c528420`，新材料提交不得改变RC3镜像哈希；
- 已推送`task/core-001`分支，并创建指向冻结提交`c528420`的`brace-msi-v0.3.0-rc3`标签；是否合并main仍由队长决定；
- 公布仓库前必须由权利人选择项目源码许可证。没有许可证时不得写“本项目已按某许可证开源”。

## SwanLab核对

- 使用SDK 0.10.0及以上；当前冻结环境为0.10.4；
- 项目建议名：`brace-msi-final`；实验名分别为`gas-final`、`bearing-final`、`engine-final`，或按比赛平台最终规范调整；
- 记录至少包括轮次、候选动作、主/次指标、是否接受、CPU秒、墙钟、峰值RSS、候选数和回滚数；
- 不记录特征、标签、样本ID、预测明细、密钥、完整Sampler路径或私有平台字段；
- 已由SwanLab API确认项目公开、三个实验均`FINISHED`且指标曲线存在；提交前仍建议用未登录浏览器人工打开一次；
- 若比赛要求一个统一实验链接，则建立项目概览或分组页面，不拼造不存在的URL。

## 最终人工操作

1. 在平台选择已经上传并校验的Harness镜像；
2. 从本机Git外收据复制完整Sampler路径；
3. 在平台直接填写PyTRiO API Key；
4. 粘贴SwanLab项目链接`https://swanlab.cn/@nanmo-max/brace-msi-final`；
5. 粘贴GitHub分支链接`https://github.com/nanmo-max/rengongzhineng/tree/task/core-001`；
6. 上传作品说明书；
7. 指导教师字段按当前要求留空；
8. 截图保存平台校验成功页面和版本号。

