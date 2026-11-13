# 平台提交清单

> 本清单不保存任何API Key。表中“已准备”仅表示本地材料存在，不代表官方平台已经校验或正式评测通过。

## 提交表单

| 平台字段 | 应填写内容 | 当前状态 | 证据/注意事项 |
|---|---|---|---|
| 模型类型 | 持久化 Sampler 微调权重 | 已准备 | A3已生成持久化Sampler |
| 完整Sampler权重路径 | 从Git外`D:/brace-msi-pytrio/PYTRIO-SFT-001-A3/result.json`读取`sampler_model_path` | 已准备 | 完整`trio://`路径不写入Git或作品文档；不要自行拼接 |
| 训练记录链接 | `https://swanlab.cn/@nanmo-max/brace-msi-final` | 已同步并核验 | 公开项目含Gas/Bearing/Engine三个`FINISHED`实验，每项10条聚合记录 |
| Harness镜像 | `BRACE-MSI-0.4.0rc1-image-clean.tar` | 已准备 | SHA-256：`97bb0a9fcfed688ba1b7feadadf09528e232fea578d06a1d782f2dccee306dfa` |
| 源码仓库链接 | `https://github.com/nanmo-max/rengongzhineng/tree/codex/paper-fusion-sprint` | 推送后核验 | 当前分支含RC4源码、测试、正负实验与容器证据；未覆盖远端main或RC3标签 |
| PyTRiO API Key | 由队长在平台字段中粘贴 | 人工填写 | 不通过聊天、Git、作品文档或日志传递 |
| 作品文档 | `D:/brace-msi-release/BRACE-MSI-0.4.0rc1-submission-materials/BRACE-MSI-作品说明书.docx` | 已生成并校验 | 无官方模板；指导教师暂不填写；PDF预览为`BRACE-MSI-作品说明书-最终版.pdf` |

作品说明书DOCX SHA-256：`765cf9e5488511be727b9bbd7463fafa20127085002ab19c4f4d5e2ca55bb16d`；PDF SHA-256：`5780a08d1bdd8267cfbb201a7e0c8bc76eb72df72c8dfc0f77ba6d7387ecfdfa`。DOCX结构校验通过，PDF共10页并逐页检查无截断或表格拆行。

## 镜像上传核对

- 上传的是`docker save`生成的`.tar`，不是源码ZIP或Docker构建上下文；
- 本地文件大小为240,723,968字节；镜像内部大小为240,701,023字节；
- 镜像平台为linux/amd64，默认用户UID 10001；
- 镜像不含原始数据、A/B/C检查点、Sampler权重、Embedding或密钥；
- 平台选择镜像后再执行“校验并保存新版本”；
- 校验失败时先保存平台原始错误文本和时间，不重复盲试消耗正式机会。

## GitHub推送核对

- 只推送源码、配置、测试和脱敏聚合证据；
- 不推送`D:/brace-msi-*`运行目录、官方训练包、模型检查点、镜像tar、API Key或逐样本日志；
- RC3分支和标签保持不变；RC4只推送独立`codex/paper-fusion-sprint`分支；
- 不覆盖main，不移动`brace-msi-v0.3.0-rc3`标签；RC4是否另建标签由队长在最终平台校验后决定；
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
5. 粘贴GitHub分支链接`https://github.com/nanmo-max/rengongzhineng/tree/codex/paper-fusion-sprint`；
6. 上传作品说明书；
7. 指导教师字段按当前要求留空；
8. 截图保存平台校验成功页面和版本号。

