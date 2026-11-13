# 开源依赖与合规清单

当前候选镜像的核心直接Python依赖如下，版本以三个锁文件为准：

| 依赖 | 当前锁定版本 | 上游许可证口径 | 用途 |
|---|---:|---|---|
| NumPy | 1.26.4 | BSD-3-Clause | 数组计算 |
| SciPy | 1.13.1 | BSD-3-Clause | 统计与scikit-learn依赖 |
| scikit-learn | 1.5.1 | BSD-3-Clause | CPU模型与指标 |
| psutil | 5.9.8 | BSD-3-Clause | 进程资源计量 |
| PyTRiO | 0.2.9 | MIT（以安装包元数据为准） | 受控Sampler推理与训练接口 |
| SwanLab | 0.10.4 | Apache-2.0（以安装包元数据为准） | 最终聚合实验记录 |

`requirements.lock`还固定`cloudpickle 3.1.2`、`joblib 1.6.0`和`threadpoolctl 3.8.0`；
`requirements-swanlab.lock`包含SwanLab的传递依赖。正式公开前必须从最终镜像导出完整SBOM
和许可证文本复核，不能仅依赖本摘要。

本项目不授权打包任何数据、预训练权重、Sampler权重或第三方密钥；Docker上下文审计会拒绝
常见权重与密钥后缀。官方A/B/C训练包和检查点仅在运行时挂载，不进入Git或镜像。

## 项目源码许可证

仓库当前没有项目级`LICENSE`文件。项目源码许可证属于权利人的法律选择，Codex不能代替团队
决定。公开GitHub仓库可以用于赛事审查，但在权利人选择许可证前，不得声称第三方已经获得
复制、修改或再分发源码的许可。该项在正式对外发布前必须由队长确认。

## 第三方研究与数据

- 未经许可证和固定版本审计的论文代码不进入正式Harness；
- RC4未打包第三方论文仓库、外部权重或下载数据；论文方法均用现有NumPy/scikit-learn依赖独立实现；
- 数据集和官方训练包的使用范围服从赛事与上游条款，本仓库不再分发原始数据；
- 作品说明书引用本地实验事实时必须保留“公开验证历史暴露、非官方成绩”边界。

| 研究来源 | 代码与许可证核对 | RC4采用边界 |
|---|---|---|
| Lin & Zhan 2026 Gas知识蒸馏 | 作者仓库`abob7/gas-drift`声明MIT | 审查方法与代码后独立实现折内标准化的KD核心；未引入仓库文件或权重，实验为负并被SafetyGate拒绝 |
| Özcan 2025 C-MAPSS集成 | 仓库README声明MIT，但实际许可证文件仍需复制前复核 | 仅采用异构树模型组合思想，以项目已锁定的scikit-learn独立实现；未复制作者仓库代码 |
| Li et al. 2018 Hyperband | JMLR论文算法思想 | 独立实现有限Successive Halving；未迁移第三方实现 |

论文、仓库和适配边界的证据登记见`SOURCE_REGISTRY.md`的P-PAPER-001至P-PAPER-003。未获得权威分区证据的期刊不在材料中标为“一区”。
