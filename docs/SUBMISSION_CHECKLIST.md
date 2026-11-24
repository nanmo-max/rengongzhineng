# 平台提交清单

> 本清单不保存API Key。表中“已准备”只表示本地材料存在或平台已显示对应状态，不等于正式评测通过。

> 2026-11-24唯一正式候选：`D:/brace-msi-release/COMPETITION-CORE-RC-002-A9/harness.tar`。A9本地发布审计已通过，但尚未在平台完成导入、校验或试运行；历史A7/A8及0.11.0rc1不得代替。

## 提交表单

| 平台字段 | 应填写内容 | 当前状态 | 注意事项 |
|---|---|---|---|
| 模型类型 | 基础模型（需二次确认，可正式参赛） | 待用户选择 | 不选择未达采用门的Sampler |
| 基础模型 | `Qwen/Qwen3.8-27B` | 官方允许的27B基础模型 | 不填写Sampler权重路径 |
| 训练记录链接 | `https://swanlab.cn/@nanmo-max/BRACE-MSI/runs/elucs19m` | 已完成 | A9三任务30轮聚合记录；不含样本、标签、特征、权重、提示词或凭据 |
| Harness镜像 | 上传A9的`harness.tar`，处理完成后选择“用于新版本” | 待平台导入 | 本地归档81,257,984字节；SHA-256见下文 |
| 源码仓库链接 | `https://github.com/nanmo-max/rengongzhineng/tree/codex/final-sprint-003` | 已推送至`7fa01ae` | 镜像运行代码绑定`fcb185e`，后续`7fa01ae`仅更新文档 |
| PyTRiO API Key | 由队长在平台字段中粘贴 | 人工填写 | 不通过聊天、Git、作品文档或日志传递 |
| 作品文档 | `output/pdf/BRACE-MSI-0.12.7rc1-作品说明书.pdf` | 已生成并逐页验收 | 9页A4；指导教师暂不填写 |

正式镜像归档SHA-256：`f98cef296a69768018cfb840938f1acd89b49fd2044e72cd3cc4d968c135ba16`。

作品说明书DOCX SHA-256：`E3B0487732DF64B68F6582BF1036D99401800539A69C09783D475E784B783E62`。

作品说明书PDF SHA-256：`0334F7BEE42F6D8F448707D4F4802DC3CAC36D689DB69ECD8D5DB090C2A77CD4`。

提交包机器清单：`D:/brace-msi-release/COMPETITION-CORE-RC-002-A9/submission-bundle-manifest.json`，SHA-256 `0562FE1FE97D5E1D035E1CEF3B7CF672CA1A8AA11EE752B6D3010D23D4269A98`。该清单同时绑定Harness、发布清单、发布审计、PDF、DOCX及本地平台样式报告；状态显式为`NOT_YET_IMPORTED_OR_VALIDATED`。

## 镜像与文档核对

- 上传的是`docker save`产生的`harness.tar`，不是源码ZIP、Dockerfile或`docker export`文件；
- 镜像平台为linux/amd64，默认非root；正式白名单不含数据、父权重、测试、模拟器、报告、PyTRiO、SwanLab、Tokenizer、Sampler或密钥；
- 正式模型调用只经官方SDK的`rnd.model()`，模型选择由平台表单绑定；
- 平台“镜像可用”只代表导入完成，不代表模型校验、十轮运行或隐藏评测通过；
- PDF必须不超过10页A4，文本可提取，逐页渲染不得存在裁切、重叠或表格不可读；
- 文档明确区分本地验收、公开开发结果和正式隐藏成绩，不包含旧版本哈希或未采用Sampler的发布声明。

## GitHub与SwanLab核对

- GitHub只推送源码、配置、测试和脱敏聚合证据，不推送训练包、checkpoint、镜像tar、密钥或逐样本日志；
- 当前远端分支`codex/final-sprint-003`已包含A9运行代码提交`fcb185e`及后续文档提交；
- SwanLab公开记录只含聚合训练和决策数据，不含工业逐样本数据、密钥或完整私有权重路径；
- 训练记录链接使用A9三任务30轮的SwanLab聚合运行；它记录自主工业模型训练过程，不宣称基础Qwen经过本次微调。

## 最终人工操作

1. 上传A9的`harness.tar`，等待状态变为“镜像可用”，再点击“用于新版本”；
2. 模型类型选择“基础模型”，模型选择`Qwen/Qwen3.8-27B`；
3. 在平台直接填写PyTRiO API Key；
4. 填写源码仓库`https://github.com/nanmo-max/rengongzhineng/tree/codex/final-sprint-003`；
5. 填写A9 SwanLab训练记录链接；
6. 上传`output/pdf/BRACE-MSI-0.12.7rc1-作品说明书.pdf`；
7. 点击“核对并保存新版本”，保存完整成功页面或原始错误提示；
8. 只有版本校验通过后才启动一次试运行；失败时先定位，不盲目重复消耗机会。
